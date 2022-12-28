from __future__ import annotations

import grpc
from grpc._channel import _InactiveRpcError
from concurrent.futures import ThreadPoolExecutor
import time
import logging
import threading

from seekers import Color
from seekers.grpc import seekers_proto_types as types
from seekers.grpc.converters import *
from seekers.hash_color import string_hash_color

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

        try:
            self.stub.Command(CommandRequest(token=self.token, seeker_id=id_, target=target, magnet=magnet))
        except _InactiveRpcError as e:
            if e.code() == grpc.StatusCode.CANCELLED:
                # We don't know why this happens.
                # The CommandUnit procedure is called
                # though, so we can just ignore the error.
                # See GitHub https://github.com/seekers-dev/seekers-api/issues/8
                ...
            else:
                raise

    def __del__(self):
        self.channel.close()


class GrpcSeekersClient:
    """A client for a Seekers gRPC game. It contains a ``GrpcSeekersRawClient`` and implements a mainloop.
    The ``decide_function`` is called in a loop and the output of that function is sent to the server."""

    def __init__(self, name: str, player_ai: seekers.LocalPlayerAI, address: str = "localhost:7777",
                 safe_mode: bool = False):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.player_ai = player_ai
        self.client = GrpcSeekersRawClient(name, address, color=player_ai.preferred_color)

        self.safe_mode = safe_mode
        self.last_gametime = -1

        self.player_id: str | None = None
        self._server_config: None | seekers.Config = None
        self._player_reply: None | tuple[dict[str, seekers.Player], dict[str, seekers.Camp]] = None
        self._last_seekers: dict[str, seekers.Seeker] = {}

        self._last_time_ai_updated = time.perf_counter()

    def join(self):
        self._logger.info(f"Joining session with name={self.client.name!r}, color={self.client.color!r}")
        self.player_id = self.client.join_session()

        self._logger.info(f"Joined session as {self.player_id!r}")
        self._logger.debug(f"Properties: {self.client.server_properties()!r}")

    def run(self):
        """Join and start the mainloop. This function blocks until the game ends."""
        self.join()

        # Wait for the server to set up players and seekers.
        # If we don't wait, there can be inconsistencies in
        # the server's replies.
        time.sleep(1)
        # TODO: Try leaving this out since the message format is now different

        while 1:
            try:
                self.tick()
            except (grpc._channel._InactiveRpcError, ServerUnavailableError):
                self._logger.info("Game ended.")
                break

    def get_server_config(self):
        if self._server_config is None or self.safe_mode:
            self._server_config = seekers.Config.from_properties(self.client.server_properties())

        return self._server_config

    @staticmethod
    def convert_player_reply(camps: list[types.CampStatus], players: list[types.PlayerStatus],
                             all_seekers: dict[str, seekers.Seeker]
                             ) -> tuple[dict[str, seekers.Player], dict[str, seekers.Camp]]:
        """Convert a PlayerReply to the respective Player and Camp objects.
        Set the owner of the seekers in all_seekers, too."""

        converted_players = {}
        for player in players:
            # The player's camp attribute is not set yet. This is done when converting the camps.
            converted_player = convert_player(player)

            for seeker_id in player.seeker_ids:
                try:
                    converted_seeker = all_seekers[seeker_id]
                except KeyError as e:
                    raise GrpcSeekersClientError(
                        f"Invalid Response: Player {player.id!r} has seeker {seeker_id!r} but it is not in "
                        f"EntityReply.seekers."
                    ) from e
                converted_player.seekers[seeker_id] = converted_seeker
                converted_seeker.owner = converted_player

            converted_players[player.id] = converted_player

        assert all(s.owner is not None for s in all_seekers.values()), \
            GrpcSeekersClientError("Invalid Response: Some seekers have no owner.")

        converted_camps = {}
        for camp in camps:
            try:
                owner = converted_players[camp.player_id]
            except KeyError as e:
                raise GrpcSeekersClientError(
                    f"Invalid Response: Camp {camp.id!r} has invalid owner {camp.player_id!r}."
                ) from e

            converted_camp = convert_camp(camp, owner)

            # Set the player's camp attribute as stated above.
            owner.camp = converted_camp

            converted_camps[camp.id] = converted_camp

        assert all(p.camp is not None for p in converted_players.values()), \
            GrpcSeekersClientError("Invalid Response: Some players have no camp.")

        return converted_players, converted_camps

    def get_ai_input(self) -> seekers.AIInput:
        # Wait for the next game tick.
        while 1:
            status_reply = self.client.status()
            if status_reply.passed_playtime != self.last_gametime:
                break

            time.sleep(1 / 120)

        if (status_reply.passed_playtime - self.last_gametime) > 1:
            self._logger.debug(f"Missed time: {status_reply.passed_playtime - self.last_gametime - 1}")

        self.last_gametime = status_reply.passed_playtime
        all_seekers, goals = status_reply.seekers, status_reply.goals

        config = self.get_server_config()

        if (len(self._last_seekers) != len(all_seekers)) or self.safe_mode:
            # Create new Seeker objects.
            # Attribute 'owner' of seekers intentionally left None,
            # we set it when assigning the seekers to the players.
            # This is done in get_converted_player_reply. We ensure
            # this by setting self._player_reply to None.

            # noinspection PyTypeChecker
            converted_seekers = {s.super.id: convert_seeker(s, None, config) for s in all_seekers}
            self._last_seekers = converted_seekers
            self._player_reply = None
        else:
            # Just update the attributes of the seekers to save time.
            for seeker in all_seekers:
                converted_seeker = self._last_seekers[seeker.super.id]
                converted_seeker.position = convert_vector(seeker.super.position)
                converted_seeker.velocity = convert_vector(seeker.super.velocity)
                converted_seeker.target = convert_vector(seeker.target)
                converted_seeker.magnet.strength = seeker.magnet

            converted_seekers = self._last_seekers

        if self._player_reply is None or self.safe_mode:
            self._player_reply = self.convert_player_reply(
                status_reply.camps,
                status_reply.players,
                self._last_seekers
            )

        converted_players, converted_camps = self._player_reply

        try:
            me = converted_players[self.player_id]
        except IndexError as e:
            raise GrpcSeekersClientError("Invalid Response: Own player_id not in PlayerReply.players.") from e

        converted_other_seekers = [s for s in converted_seekers.values() if s.owner != me]
        converted_goals = [convert_goal(g, converted_camps, config) for g in goals]
        converted_other_players = [p for p in converted_players.values() if p != me]

        if config.map_width is None or config.map_height is None:
            raise GrpcSeekersClientError("Invalid Response: Essential properties map_width and map_height missing.")
        converted_world = seekers.World(config.map_width, config.map_height)

        return (
            list(me.seekers.values()),
            converted_other_seekers,
            list(converted_seekers.values()),
            converted_goals,
            converted_other_players,
            me.camp,
            list(converted_camps.values()),
            converted_world,
            status_reply.passed_playtime,
        )

    def tick(self):
        """Call the ``decide_function`` and send the output to the server."""

        ai_input = self.get_ai_input()

        t = time.perf_counter()
        if t - self._last_time_ai_updated > 1:
            self.player_ai.update()
            self._last_time_ai_updated = t

        new_seekers = self.player_ai.decide_function(*ai_input)

        self.send_updates(new_seekers)

    def send_updates(self, new_seekers: list[seekers.Seeker]):
        for seeker in new_seekers:
            self.client.send_command(seeker.id, convert_vector_back(seeker.target), seeker.magnet.strength)


class GrpcSeekersServicer(pb2_grpc.SeekersServicer):
    """A Seekers game servicer. It implements all needed gRPC services and is compatible with the
    ``GrpcSeekersRawClient``. It stores a reference to the game to have full control over it."""

    def __init__(self, seekers_game: seekers.SeekersGame, game_start_event: threading.Event):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.seekers_game = seekers_game
        self.game_start_event = game_start_event

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
        player = seekers.GRPCClientPlayer(
            seekers.get_id("Player"), requested_name, 0, {}
        )

        # add player to game
        try:
            self.seekers_game.add_player(player)
        except seekers.GameFullError:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Game is full.")
            return

        self._logger.info(f"Player {player.name!r} joined the game. ({player.id})")
        # return player id
        # token is just the player id, we don't need something more complex for now
        return JoinReply(token=player.id, id=player.id, version=_VERSION)

    def Properties(self, request: PropertiesRequest, context) -> PropertiesReply:
        return PropertiesReply(entries=self.seekers_game.config.to_properties())

    def Status(self, request: StatusRequest, context) -> StatusReply:
        if request.token not in self.seekers_game.players:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, "Invalid token.")
            return

        self.game_start_event.wait()

        players = [
            # filter out players whose camp has not been set yet, meaning they are still uninitialized
            # TODO: Do we still need this?
            convert_player_back(p) for p in self.seekers_game.players.values() if p.camp is not None
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
        if seeker.owner.id != request.token:
            context.abort(
                grpc.StatusCode.PERMISSION_DENIED,
                f"Seeker with id {request.seeker_id!r} is not owned by player {request.token!r}."
            )
            return

        seeker.target = convert_vector(request.target)
        seeker.magnet.strength = request.magnet

        # noinspection PyTypeChecker
        ai: seekers.GRPCClientPlayer = seeker.owner
        ai.was_updated.set()

        return CommandReply()


class GrpcSeekersServer:
    """A wrapper around the ``GrpcSeekersServicer`` that handles the gRPC server."""

    def __init__(self, seekers_game: seekers.SeekersGame, address: str = "localhost:7777"):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info(f"Starting server on {address=}")

        self.game_start_event = threading.Event()

        self.server = grpc.server(ThreadPoolExecutor())
        pb2_grpc.add_SeekersServicer_to_server(GrpcSeekersServicer(seekers_game, self.game_start_event), self.server)
        self.server.add_insecure_port(address)

    def start(self):
        self.server.start()

    def start_game(self):
        self.game_start_event.set()

    def stop(self):
        self.server.stop(None)
