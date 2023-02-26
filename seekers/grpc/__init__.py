from __future__ import annotations

from collections import defaultdict

import grpc
from grpc._channel import _InactiveRpcError
from concurrent.futures import ThreadPoolExecutor
import time
import logging
import threading

import seekers
from seekers import Color
from seekers.grpc import seekers_proto_types as types
from seekers.grpc.converters import *
from seekers.colors import string_hash_color

_VERSION = "1"


class GrpcSeekersClientError(Exception): ...


class SessionTokenInvalidError(GrpcSeekersClientError): ...


class GameFullError(GrpcSeekersClientError): ...


class ServerUnavailableError(GrpcSeekersClientError): ...


class GrpcSeekersRawClient:
    """A client for a Seekers gRPC game.
    It is called "raw" because it is nothing but a wrapper for the gRPC services."""

    def __init__(self, name: str, address: str = "localhost:7777", color: Color = None):
        self.name = name
        self.color = string_hash_color(name) if color is None else color
        self.token = None

        self.channel = grpc.insecure_channel(address)
        self.stub = pb2_grpc.SeekersStub(self.channel)

        self.channel_connectivity_status = None
        self.channel.subscribe(self._channel_connectivity_callback, try_to_connect=True)

        self._logger = logging.getLogger(self.__class__.__name__)

    def _channel_connectivity_callback(self, state):
        self.channel_connectivity_status = state

    def join_session(self) -> str:
        """Try to join the game and return our player_id."""
        try:
            reply: types.JoinReply = self.stub.Join(JoinRequest(name=self.name, color=convert_color_back(self.color)))

            if reply.version == "":
                self._logger.warning("Empty version string: Server is running an unknown version of Seekers.")
            elif reply.version != _VERSION:
                raise GrpcSeekersClientError(
                    f"Server version {reply.version!r} is not supported. This is version {_VERSION!r}."
                )

            self.token = reply.token

            return reply.id
        except _InactiveRpcError as e:
            if e.code() in [grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.INVALID_ARGUMENT]:
                raise SessionTokenInvalidError(f"Session token {self.token!r} is invalid. It can't be empty.") from e
            elif e.code() == grpc.StatusCode.ALREADY_EXISTS:
                raise SessionTokenInvalidError(f"Session token {self.token!r} is already in use.") from e
            elif e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
                raise GameFullError("The game is full.") from e
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                raise ServerUnavailableError(
                    f"The server is unavailable. Is it running already?"
                ) from e
            raise

    def server_properties(self) -> dict[str, str]:
        return self.stub.Properties(PropertiesRequest()).entries

    def status(self) -> types.StatusReply:
        return self.stub.Status(StatusRequest(token=self.token))

    def send_command(self, id_: str, target: Vector, magnet: float) -> None:
        if self.channel_connectivity_status != grpc.ChannelConnectivity.READY:
            raise ServerUnavailableError("Channel is not ready. Or game ended.")

        self.stub.Command(CommandRequest(token=self.token, seeker_id=id_, target=target, magnet=magnet))

    def __del__(self):
        self.channel.close()


class GrpcSeekersClient:
    """A client for a Seekers gRPC game. It contains a ``GrpcSeekersRawClient`` and implements a mainloop.
    The ``decide_function`` is called in a loop and the output of that function is sent to the server."""

    def __init__(self, name: str, player_ai: seekers.LocalPlayerAi, address: str = "localhost:7777",
                 safe_mode: bool = False, careful_mode: bool = False):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.player_ai = player_ai
        self.client = GrpcSeekersRawClient(name, address, color=player_ai.preferred_color)

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

    def join(self):
        self._logger.info(f"Joining session with name={self.client.name!r}, "
                          f"color={convert_color_back(self.client.color)}")
        self.player_id = self.client.join_session()

        self._logger.info(f"Joined session as {self.player_id!r}")
        self._logger.debug(f"Properties: {self.client.server_properties()!r}")

    def run(self):
        """Join and start the mainloop. This function blocks until the game ends."""
        if not self.player_id:
            self.join()

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
            self._server_config = seekers.Config.from_properties(self.client.server_properties())

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
            status_reply = self.client.status()
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
            self.client.send_command(seeker.id, convert_vector_back(seeker.target), seeker.magnet.strength)

    def update_state(self, status_reply: types.StatusReply):
        self.last_gametime = status_reply.passed_playtime

        config = self.get_config()
        seekers_of_owner: dict[str, list[str]] = defaultdict(list)

        # 1. convert seekers
        for new_seeker in status_reply.seekers:
            try:
                seeker = self.seekers[new_seeker.super.id]

                seeker.position = convert_vector(new_seeker.super.position)
                seeker.velocity = convert_vector(new_seeker.super.velocity)
                seeker.target = convert_vector(new_seeker.target)
                seeker.magnet.strength = new_seeker.magnet

            except KeyError:
                # noinspection PyTypeChecker
                self.seekers |= {
                    # owner of seeker intentionally left None, it will get set when the player is updated
                    new_seeker.super.id: convert_seeker(new_seeker, None, config)
                }

            seekers_of_owner[new_seeker.player_id].append(new_seeker.super.id)

        # 2. convert players
        for new_player in status_reply.players:
            # The player's camp attribute is not set yet. This is done when converting the camps.
            try:
                player = self.players[new_player.id]
                player.color = convert_color(new_player.color)
                player.score = new_player.score
                player.name = new_player.name
            except KeyError:
                player = convert_player(new_player)

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
            self.camps[new_camp.id] = owner.camp = convert_camp(new_camp, owner)

        assert all(p.camp is not None for p in self.players.values()), \
            GrpcSeekersClientError("Invalid Response: Some players have no camp.")

        # 4. convert goals
        self.goals |= {g.super.id: convert_goal(g, self.camps, config) for g in status_reply.goals}


class GrpcSeekersServicer(pb2_grpc.SeekersServicer):
    """A Seekers game servicer. It implements all needed gRPC services and is compatible with the
    ``GrpcSeekersRawClient``. It stores a reference to the game to have full control over it."""

    def __init__(self, seekers_game: seekers.SeekersGame, game_start_event: threading.Event):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.seekers_game = seekers_game
        self.game_start_event = game_start_event
        self.tokens: set[str] = set()

    def Join(self, request: JoinRequest, context: grpc.ServicerContext) -> JoinReply:
        # validate requested token
        requested_name = request.name.strip()

        if not requested_name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          f"Requested name must not be empty or only consist of whitespace.")
            return

        # add the player with a new name if the requested name is already taken
        _requested_name = requested_name
        i = 2
        while _requested_name in {p.name for p in self.seekers_game.players.values()}:
            _requested_name = f"{requested_name} ({i})"
            i += 1

        # create new player
        new_token = seekers.get_id("Token")
        player = seekers.GrpcClientPlayer(
            token=new_token,
            id=seekers.get_id("Player"),
            name=requested_name,
            score=0,
            seekers={},
            preferred_color=convert_color(request.color)
        )

        # add player to game
        try:
            self.seekers_game.add_player(player)
        except seekers.GameFullError:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Game is full.")
            return

        self.tokens.add(new_token)
        self._logger.info(f"Player {player.name!r} joined the game. ({player.id})")

        return JoinReply(token=player.token, id=player.id, version=_VERSION)

    def Properties(self, request: PropertiesRequest, context) -> PropertiesReply:
        return PropertiesReply(entries=self.seekers_game.config.to_properties())

    def Status(self, request: StatusRequest, context) -> StatusReply:
        if request.token not in self.tokens:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "Invalid token.")
            return

        self.game_start_event.wait()

        players = [
            convert_player_back(p) for p in self.seekers_game.players.values()
        ]
        camps = [convert_camp_back(c) for c in self.seekers_game.camps]

        return StatusReply(
            players=players,
            camps=camps,
            seekers=[convert_seeker_back(s) for s in self.seekers_game.seekers.values()],
            goals=[convert_goal_back(goal) for goal in self.seekers_game.goals],

            passed_playtime=self.seekers_game.ticks,
        )

    def Command(self, request: CommandRequest, context) -> CommandReply:
        self.game_start_event.wait()
        try:
            seeker = self.seekers_game.seekers[request.seeker_id]
        except KeyError:
            context.abort(grpc.StatusCode.NOT_FOUND, f"Seeker with id {request.id!r} not found in the game.")
            return

        # check if seeker is owned by player
        # noinspection PyTypeChecker
        owner: seekers.GrpcClientPlayer = seeker.owner
        if owner.token != request.token:
            context.abort(
                grpc.StatusCode.PERMISSION_DENIED,
                f"Seeker with id {request.seeker_id!r} is not owned by token {request.token!r}."
            )
            return

        seeker.target = convert_vector(request.target)
        seeker.magnet.strength = request.magnet

        # noinspection PyTypeChecker
        player: seekers.GrpcClientPlayer = seeker.owner
        # wait until the AI has updated all its seekers
        player.num_updates += 1
        if player.num_updates >= len(player.seekers):
            player.was_updated.set()
        player.num_updates %= len(player.seekers)

        return CommandReply()


class GrpcSeekersServer:
    """A wrapper around the ``GrpcSeekersServicer`` that handles the gRPC server."""

    def __init__(self, seekers_game: seekers.SeekersGame, address: str = "localhost:7777"):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.game_start_event = threading.Event()

        self.server = grpc.server(ThreadPoolExecutor())
        pb2_grpc.add_SeekersServicer_to_server(GrpcSeekersServicer(seekers_game, self.game_start_event), self.server)

        self._is_running = False
        self._address = address

    def start(self):
        if self._is_running:
            return

        self._logger.info(f"Starting server on {self._address!r}")
        self.server.add_insecure_port(self._address)
        self.server.start()
        self._is_running = True

    def start_game(self):
        self.game_start_event.set()

    def stop(self):
        self.server.stop(None)
