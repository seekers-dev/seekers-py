from __future__ import annotations

from grpc._channel import _InactiveRpcError

from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import time
import logging
import threading

import seekers.colors
from seekers.grpc.converters import *
from .stubs.org.seekers.net.seekers_pb2 import *
from .stubs.org.seekers.net.seekers_pb2_grpc import *


class GrpcSeekersClientError(Exception): ...


class SessionTokenInvalidError(GrpcSeekersClientError): ...


class GameFullError(GrpcSeekersClientError): ...


class ServerUnavailableError(GrpcSeekersClientError): ...


class GrpcSeekersServiceWrapper:
    """A wrapper for the Seekers gRPC service."""

    def __init__(self, address: str = "localhost:7777"):
        self.name: str | None = None
        self.token: str | None = None

        self.channel = grpc.insecure_channel(address)
        self.stub = SeekersStub(self.channel)

        self.channel_connectivity_status = None
        self.channel.subscribe(self._channel_connectivity_callback, try_to_connect=True)

        self._logger = logging.getLogger(self.__class__.__name__)

    def _channel_connectivity_callback(self, state):
        self.channel_connectivity_status = state

    def join(self, name: str, color: seekers.Color = None) -> str:
        """Try to join the game and return our player id."""

        color = seekers.colors.string_hash_color(name) if color is None else color

        self._logger.info(f"Joining game as {name!r} with color {color!r}.")

        try:
            reply = self.stub.Join(JoinRequest(details=dict(name=name, color=color_to_grpc(color))))
            self.token = reply.token
            return reply.player_id
        except _InactiveRpcError as e:
            if e.code() in [grpc.StatusCode.UNAUTHENTICATED, grpc.StatusCode.INVALID_ARGUMENT]:
                raise SessionTokenInvalidError(f"Requested name {name!r} is invalid.") from e
            elif e.code() == grpc.StatusCode.ALREADY_EXISTS:
                raise SessionTokenInvalidError(f"Name {name!r} is already in use.") from e
            elif e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
                raise GameFullError("The game is full.") from e
            elif e.code() == grpc.StatusCode.UNAVAILABLE:
                raise ServerUnavailableError(
                    f"The server is unavailable. Is it running already?"
                ) from e
            raise

    def get_server_properties(self) -> dict[str, str]:
        return self.stub.Properties(Empty()).entries

    def get_status(self) -> StatusResponse:
        return self.stub.Status(Empty())

    def send_commands(self, commands: list[Command]) -> StatusResponse:
        if self.channel_connectivity_status != grpc.ChannelConnectivity.READY:
            raise ServerUnavailableError("Channel is not ready.")

        return self.stub.Command(CommandRequest(token=self.token, commands=commands)).status

    def __del__(self):
        self.channel.close()


class CouldNotUpdateExistingStateError(GrpcSeekersClientError): ...


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

        self.players: dict[str, seekers.Player] | None = None
        self.seekers: dict[str, seekers.Seeker] | None = None
        self.camps: dict[str, seekers.Camp] | None = None
        self.goals: dict[str, seekers.Goal] | None = None

        self._status_response: StatusResponse | None = None

        self._last_time_ai_updated = time.perf_counter()

    def join(self, name: str, color: seekers.Color = None) -> None:
        self.player_id = self.service_wrapper.join(name, color)

    def run(self):
        """Start the mainloop. This function blocks until the game ends."""

        while 1:
            try:
                self.tick()

            except ServerUnavailableError as e:
                self._logger.info(f"Game ended. ({e})")
                break
            except GrpcSeekersClientError as e:
                if self.careful_mode:
                    raise
                self._logger.critical(f"Error: {e}")
            except grpc._channel._InactiveRpcError as e:
                if e.code() in [grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.CANCELLED]:
                    # assume game has ended
                    self._logger.info(f"Game ended. ({e})")
                    break
                elif e.code() in [grpc.StatusCode.UNKNOWN] and not self.careful_mode:
                    self._logger.error(f"Received status code UNKNOWN: {e}")
                else:
                    raise GrpcSeekersClientError("gRPC request resulted in unhandled error.") from e
            except AssertionError as e:
                if self.careful_mode:
                    raise

                self._logger.critical(f"Assertion not met: {e.args[0]!r}")

                # for safety reset all caches
                self._server_config = None

    def get_config(self):
        if self._server_config is None:
            self._server_config = seekers.Config.from_properties(self.service_wrapper.get_server_properties())

        return self._server_config

    def get_ai_input(self) -> seekers.AiInput:
        config = self.get_config()

        try:
            me = self.players[self.player_id]
        except KeyError as e:
            raise GrpcSeekersClientError(
                f"Invalid Response: Own player_id ({self.player_id}) not in PlayerReply.players."
            ) from e

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

    def tick(self):
        """Call the decide function and send the output to the server."""

        if self._status_response is None:
            self._status_response = self.service_wrapper.get_status()

        self.update_state(self._status_response)

        ai_input = self.get_ai_input()

        # periodically update the AI in case the file changed
        t = time.perf_counter()
        if t - self._last_time_ai_updated > 1:
            self.player_ai.update()
            self._last_time_ai_updated = t

        new_seekers = self.player_ai.decide_function(*ai_input)

        self.send_updates(new_seekers)

    def send_updates(self, new_seekers: list[seekers.Seeker]) -> None:
        self._status_response = self.service_wrapper.send_commands([
            Command(seeker_id=seeker.id, target=vector_to_grpc(seeker.target), magnet=seeker.magnet.strength)
            for seeker in new_seekers
        ])

    def update_state(self, status_reply: StatusResponse):
        self.last_gametime = status_reply.passed_playtime

        if self.seekers is None:
            self.create_new_state(status_reply)
        else:
            try:
                self.update_existing_state(status_reply)
            except CouldNotUpdateExistingStateError as e:
                self._logger.error(f"Could not update existing state ({e}), creating new state.")
                self.create_new_state(status_reply)

    def update_existing_state(self, status_reply: StatusResponse):
        for new_seeker in status_reply.seekers:
            try:
                seeker = self.seekers[new_seeker.super.id]
            except KeyError as e:
                raise CouldNotUpdateExistingStateError(
                    f"Invalid Response: Seeker ({new_seeker.super.id!r}) not in State.seekers. ({list(self.seekers)!r})"
                ) from e
            else:
                seeker.position = vector_to_seekers(new_seeker.super.position)
                seeker.velocity = vector_to_seekers(new_seeker.super.velocity)
                seeker.target = vector_to_seekers(new_seeker.target)
                seeker.magnet.strength = new_seeker.magnet

        for new_player in status_reply.players:
            try:
                player = self.players[new_player.id]
            except KeyError as e:
                raise CouldNotUpdateExistingStateError(
                    f"Invalid Response: Player ({new_player.id!r}) not in State.players. ({list(self.players)!r})"
                ) from e
            else:
                player.score = new_player.score
                # other attributes are assumed to be constant

        for new_goal in status_reply.goals:
            try:
                goal = self.goals[new_goal.super.id]
            except KeyError as e:
                raise CouldNotUpdateExistingStateError(
                    f"Invalid Response: Goal ({new_goal.super.id!r}) not in State.goals. ({list(self.goals)!r})"
                ) from e
            else:
                goal.position = vector_to_seekers(new_goal.super.position)
                goal.velocity = vector_to_seekers(new_goal.super.velocity)
                goal.time_owned = new_goal.time_owned
                goal.owner = self.camps[new_goal.camp_id].owner if new_goal.camp_id else None

        # camps assumed to be constant

    def create_new_state(self, status_reply: StatusResponse):
        config = self.get_config()

        camp_replies = {camp.id: camp for camp in status_reply.camps}
        seeker_replies = {seeker.super.id: seeker for seeker in status_reply.seekers}

        self.seekers = {}
        self.players = {}
        self.camps = {}

        for new_player in status_reply.players:
            new_player: Player
            player = player_to_seekers(new_player)

            for seeker_id in new_player.seeker_ids:
                seeker_data = seeker_replies[seeker_id]

                player.seekers[seeker_id] = self.seekers[seeker_id] = seeker_to_seekers(seeker_data, player, config)

            self.players[new_player.id] = player

            try:
                self.camps[new_player.camp_id] = player.camp = camp_to_seekers(camp_replies[new_player.camp_id], player)
            except KeyError as e:
                raise GrpcSeekersClientError(
                    f"Invalid Response: Player's camp {new_player.camp_id!r} not in State.camps. "
                    f"({list(camp_replies)!r})."
                ) from e

        self.goals = {
            goal.super.id: goal_to_seekers(goal, self.camps, config)
            for goal in status_reply.goals
        }

        self._logger.debug(f"Created {len(self.seekers)} seekers, {len(self.players)} players, "
                           f"{len(self.camps)} camps, {len(self.goals)} goals.")


class GrpcSeekersServicer(SeekersServicer):
    def __init__(self, seekers_game: seekers.SeekersGame, game_start_event: threading.Event):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.game = seekers_game
        self.game_start_event = game_start_event

        self.current_status: StatusResponse | None = None
        self.new_status_events: list[threading.Event] = []
        self.tokens: set[str] = set()

    def Properties(self, request: Empty, context) -> PropertiesResponse:
        return PropertiesResponse(entries=self.game.config.to_properties())

    def new_tick(self):
        """Invalidate the cached game status. Called by SeekersGame."""
        self.generate_status()

        for event in self.new_status_events:
            event.set()

        self.new_status_events.clear()

    def generate_status(self):
        players = [
            player_to_grpc(p) for p in self.game.players.values()
        ]
        camps = [camp_to_grpc(c) for c in self.game.camps]

        self.current_status = StatusResponse(
            players=players,
            camps=camps,
            seekers=[seeker_to_grpc(s) for s in self.game.seekers.values()],
            goals=[goal_to_grpc(goal) for goal in self.game.goals],

            passed_playtime=self.game.ticks,
        )

    def Status(self, request: Empty, context) -> StatusResponse:
        self.game_start_event.wait()

        if self.current_status is None:
            self.generate_status()

        return self.current_status

    def Command(self, request: CommandRequest, context: grpc.ServicerContext) -> CommandResponse | None:
        # self._logger.debug("Waiting for game start event.")
        self.game_start_event.wait()

        for command in request.commands:
            try:
                seeker = self.game.seekers[command.seeker_id]
            except KeyError:
                context.abort(grpc.StatusCode.NOT_FOUND, f"Seeker with id {command.seeker_id!r} not found in the game.")
                return

            # check if seeker is owned by player
            # noinspection PyTypeChecker
            if not isinstance(seeker.owner, seekers.GrpcClientPlayer) or seeker.owner.token != request.token:
                context.abort(
                    grpc.StatusCode.PERMISSION_DENIED,
                    f"Seeker with id {command.seeker_id!r} (owner player id: {seeker.owner.id!r}) "
                    f"is not owned by token {request.token!r}."
                )
                return

            seeker.target = vector_to_seekers(command.target)
            seeker.magnet.strength = command.magnet

        if request.commands:
            # noinspection PyUnboundLocalVariable
            seeker.owner.was_updated.set()

        new_status_event = threading.Event()
        self.new_status_events.append(new_status_event)
        new_status_event.wait()

        return CommandResponse(status=self.current_status, seekers_changed=len(request.commands))

    def join_game(self, name: str, color: seekers.Color) -> tuple[str, str]:
        # add the player with a new name if the requested name is already taken
        _requested_name = name
        i = 2
        while _requested_name in {p.name for p in self.game.players.values()}:
            _requested_name = f"{name} ({i})"
            i += 1

        # create new player
        new_token = seekers.get_id("Token")
        player = seekers.GrpcClientPlayer(
            token=new_token,
            id=seekers.get_id("Player"),
            name=_requested_name,
            score=0,
            seekers={},
            preferred_color=color
        )
        self.game.add_player(player)

        self.tokens.add(new_token)
        self._logger.info(f"Player {player.name!r} joined the game. ({player.id})")

        return new_token, player.id

    def Join(self, request: JoinRequest, context) -> JoinResponse | None:
        self._logger.debug(f"Received JoinRequest: {request!r}")

        # validate requested name
        try:
            requested_name = request.details["name"].strip()
        except KeyError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          "No 'name' key was provided in JoinRequest.details.")
            return

        if not requested_name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT,
                          f"Requested name must not be empty or only consist of whitespace.")
            return

        color = (
            seekers.colors.string_hash_color(requested_name)
            if request.details.get("color") is None
            else color_to_seekers(request.details["color"])
        )

        # add player to game
        try:
            new_token, player_id = self.join_game(requested_name, color)
        except seekers.GameFullError:
            context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Game is full.")
            return

        return JoinResponse(token=new_token, player_id=player_id)

    def Ping(self, request: Empty, context) -> PingResponse:
        return PingResponse(timestamp=int(time.time() * 1000))


class GrpcSeekersServer:
    """A wrapper around the GrpcSeekersServicer that handles the gRPC server."""

    def __init__(self, seekers_game: seekers.SeekersGame, address: str = "localhost:7777"):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.game_start_event = threading.Event()

        self.server = grpc.server(ThreadPoolExecutor())
        self.servicer = GrpcSeekersServicer(seekers_game, self.game_start_event)
        add_SeekersServicer_to_server(self.servicer, self.server)

        self._is_running = False
        self._address = address

    def start_server(self):
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

    def new_tick(self):
        self.servicer.new_tick()
