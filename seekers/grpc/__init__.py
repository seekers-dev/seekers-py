from __future__ import annotations

from collections import defaultdict

import grpc
from grpc._channel import _InactiveRpcError
import time
import logging
import threading

import seekers
from seekers.grpc.converters import *
from .stubs.org.seekers.net.hosting_pb2 import GameDescription
from .stubs.org.seekers.net.seekers_pb2 import PropertiesRequest, StatusResponse, StatusRequest, CommandRequest
from .stubs.org.seekers.net.seekers_pb2_grpc import SeekersStub

_VERSION = "1"


class GrpcSeekersClientError(Exception): ...


class SessionTokenInvalidError(GrpcSeekersClientError): ...


class GameFullError(GrpcSeekersClientError): ...


class ServerUnavailableError(GrpcSeekersClientError): ...


class GrpcSeekersServiceWrapper:
    """A wrapper for the Seekers gRPC service."""

    def __init__(self, token: str, player_id: str, game_description: GameDescription):
        self.name = player_id
        self.token = token

        self.channel = grpc.insecure_channel(f"{game_description.address}:{game_description.port}")
        self.stub = SeekersStub(self.channel)

        self.channel_connectivity_status = None
        self.channel.subscribe(self._channel_connectivity_callback, try_to_connect=True)

        self._logger = logging.getLogger(self.__class__.__name__)

    def _channel_connectivity_callback(self, state):
        self.channel_connectivity_status = state

    def server_properties(self) -> dict[str, str]:
        return self.stub.Properties(PropertiesRequest()).entries

    def status(self) -> StatusResponse:
        return self.stub.Status(StatusRequest(token=self.token))

    def send_command(self, seeker_id: str, target: seekers.Vector, magnet: float) -> None:
        if self.channel_connectivity_status != grpc.ChannelConnectivity.READY:
            raise ServerUnavailableError("Channel is not ready.")

        self.stub.Command(CommandRequest(token=self.token, seeker_id=seeker_id, target=target, magnet=magnet))

    def __del__(self):
        self.channel.close()


class GrpcSeekersClient:
    """A client for a Seekers gRPC game. It wraps GrpcSeekersServiceWrapper and implements a mainloop."""

    def __init__(self, service_wrapper: GrpcSeekersServiceWrapper, player_ai: seekers.LocalPlayerAi, *,
                 careful_mode: bool = False):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.player_ai = player_ai
        self.service_wrapper = service_wrapper

        self.careful_mode = careful_mode  # raise exceptions on errors that are otherwise ignored
        self.last_gametime = -1

        self.player_id: str | None = None
        self._server_config: None | seekers.Config = None

        self.players: dict[str, seekers.Player] = {}
        self.seekers: dict[str, seekers.Seeker] = {}
        self.camps: dict[str, seekers.Camp] = {}
        self.goals: dict[str, seekers.Goal] = {}

        self._last_seekers: dict[str, seekers.Seeker] = {}

        self._last_time_ai_updated = time.perf_counter()

    def run(self):
        """Start the mainloop. This function blocks until the game ends."""

        while 1:
            try:
                self.tick()

            except ServerUnavailableError:
                self._logger.info("Game ended.")
                break
            except GrpcSeekersClientError as e:
                if self.careful_mode:
                    raise
                self._logger.error(f"Error: {e}")
            except grpc._channel._InactiveRpcError as e:
                if not self.careful_mode and e.code() in {grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.CANCELLED}:
                    # assume game has ended
                    self._logger.info("Game ended.")
                    break
                elif e.code() in {grpc.StatusCode.UNKNOWN}:
                    self._logger.error(f"Received status code UNKNOWN: {e}")
                else:
                    raise GrpcSeekersClientError("gRPC request resulted in unhandled error.") from e
            except AssertionError as e:
                if self.careful_mode:
                    raise

                self._logger.error(f"Assertion not met: {e.args[0]!r}")

                # for safety reset all caches
                self._server_config = None
                self._player_reply = None
                self._last_seekers = {}

    def get_config(self):
        if self._server_config is None:
            self._server_config = seekers.Config.from_properties(self.service_wrapper.server_properties())

        return self._server_config

    def get_ai_input(self) -> seekers.AiInput:
        config = self.get_config()

        try:
            me = self.players[self.player_id]
        except KeyError as e:
            raise GrpcSeekersClientError("Invalid Response: Own player_id not in PlayerReply.players.") from e

        converted_other_seekers = [s for s in self.seekers.values() if s.owner != me]
        converted_other_players = [p for p in self.players.values() if p != me]

        if config.map_width is None or config.map_height is None:
            raise GrpcSeekersClientError("Invalid Response: Essential properties map_width and map_height missing.")
        converted_world = seekers.World(config.map_width, config.map_height)

        return (
            list(me.seekers.values()),
            converted_other_seekers,
            list(self.seekers.values()),
            list(self.goals.values()),
            converted_other_players,
            me.camp,
            list(self.camps.values()),
            converted_world,
            self.last_gametime,
        )

    def wait_for_next_tick(self):
        t = time.perf_counter()
        while 1:
            status_reply = self.service_wrapper.status()
            if status_reply.passed_playtime != self.last_gametime:
                break

            if self.careful_mode and time.perf_counter() - t > 4:
                raise GrpcSeekersClientError(f"Timeout while waiting for game tick. "
                                             f"Server's clock did not advance. (t={status_reply.passed_playtime}).")

            time.sleep(1 / 120)

        if (status_reply.passed_playtime - self.last_gametime) > 1:
            self._logger.debug(f"Missed time: {status_reply.passed_playtime - self.last_gametime - 1}")

        return status_reply

    def tick(self):
        """Call the decide function and send the output to the server."""

        status_reply = self.wait_for_next_tick()

        self.update_state(status_reply)

        ai_input = self.get_ai_input()

        # periodically update the AI in case the file changed
        t = time.perf_counter()
        if t - self._last_time_ai_updated > 1:
            self.player_ai.update()
            self._last_time_ai_updated = t

        new_seekers = self.player_ai.decide_function(*ai_input)

        self.send_updates(new_seekers)

    def send_updates(self, new_seekers: list[seekers.Seeker]):
        for seeker in new_seekers:
            self.service_wrapper.send_command(seeker.id, vector_to_grpc(seeker.target), seeker.magnet.strength)

    def update_state(self, status_reply: StatusResponse):
        self.last_gametime = status_reply.passed_playtime

        config = self.get_config()
        seekers_of_owner: dict[str, list[str]] = defaultdict(list)

        # 1. convert seekers
        for new_seeker in status_reply.seekers:
            try:
                seeker = self.seekers[new_seeker.super.id]

                seeker.position = vector_to_seekers(new_seeker.super.position)
                seeker.velocity = vector_to_seekers(new_seeker.super.velocity)
                seeker.target = vector_to_seekers(new_seeker.target)
                seeker.magnet.strength = new_seeker.magnet

            except KeyError:
                # noinspection PyTypeChecker
                self.seekers |= {
                    # owner of seeker intentionally left None, it will get set when the player is updated
                    new_seeker.super.id: seeker_to_seekers(new_seeker, None, config)
                }

            seekers_of_owner[new_seeker.player_id].append(new_seeker.super.id)

        # 2. convert players
        for new_player in status_reply.players:
            # The player's camp attribute is not set yet. This is done when converting the camps.
            try:
                player = self.players[new_player.id]
                player.color = color_to_seekers(new_player.color)
                player.score = new_player.score
                player.name = new_player.name
            except KeyError:
                player = player_to_seekers(new_player)

            # update seekers of player
            for seeker_id in new_player.seeker_ids:
                if seeker_id not in self.seekers:
                    raise GrpcSeekersClientError(
                        f"Invalid response: Player {new_player.id!r} has seeker {seeker_id!r} "
                        f"but it was not sent previously."
                    )

                seeker = player.seekers[seeker_id] = self.seekers[seeker_id]
                seeker.owner = player

            # the owner of a seeker might be specified in this field or the seekers of a player
            # this means we have to check both places
            # See https://github.com/seekers-dev/seekers-api/issues/25
            for seeker_id in seekers_of_owner.get(new_player.id, []):
                if None is not self.seekers[seeker_id].owner.id != new_player.id:
                    self._logger.error(f"Inconsistent response: Player {new_player.id!r} has seeker {seeker_id!r} "
                                       f"but it has owner {self.seekers[seeker_id].owner.id!r}.")

                # this should never fail since we created the seekers in the previous loop
                self.seekers[seeker_id].owner = player

            self.players[new_player.id] = player

        assert all(s.owner is not None for s in self.seekers.values()), \
            GrpcSeekersClientError(
                f"Invalid Response: Some seekers have no owner.\n"
                f"Players: { {pl.id: [s.id for s in pl.seekers.values()] for pl in self.players.values()} }\n"
                f"Seekers: { {seeker.id: seeker.owner for seeker in self.seekers.values()} }"
            )

        # 3. convert camps
        for new_camp in status_reply.camps:
            try:
                owner = self.players[new_camp.player_id]
            except KeyError as e:
                raise GrpcSeekersClientError(
                    f"Invalid Response: Camp {new_camp.id!r} has invalid non-existing owner {new_camp.player_id!r}."
                ) from e

            # set the player's camp attribute as stated above
            self.camps[new_camp.id] = owner.camp = camp_to_seekers(new_camp, owner)

        assert all(p.camp is not None for p in self.players.values()), \
            GrpcSeekersClientError("Invalid Response: Some players have no camp.")

        # 4. convert goals
        self.goals |= {g.super.id: goal_to_seekers(g, self.camps, config) for g in status_reply.goals}


class GrpcSeekersServicer:
    """A Seekers game servicer. It implements all needed gRPC services and is compatible with the
    ``GrpcSeekersRawClient``. It stores a reference to the game to have full control over it."""

    def __init__(self, seekers_game: seekers.SeekersGame, game_start_event: threading.Event):
        ...


class GrpcSeekersServer:
    """A wrapper around the ``GrpcSeekersServicer`` that handles the gRPC server."""

    def __init__(self, seekers_game: seekers.SeekersGame, address: str = "localhost:7777"):
        ...

    def start(self):
        ...

    def start_game(self):
        ...

    def stop(self):
        ...
