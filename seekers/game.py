from __future__ import annotations

import collections
import glob
import logging
import os
import random
import time
import typing

import pygame

from .config import *
from .ids import *
from . import (
    world,
    draw,
    seeker,
    player,
    goal,
    game_logic,
    colors
)

__all__ = [
    "SeekersGame",
    "GameFullError"
]


class GameFullError(Exception):
    ...


class SeekersGame:
    """A Seekers game. Manages the game logic, players, the gRPC server and graphics."""

    def __init__(self, local_ai_locations: typing.Iterable[str], config: Config,
                 grpc_address: typing.Literal[False] | str = "localhost:7777",
                 debug: bool = True, print_scores: bool = True, dont_kill: bool = False):
        self._logger = logging.getLogger("SeekersGame")

        self._logger.debug(f"Config: {config}")

        self.config = config
        self.debug = debug
        self.do_print_scores = print_scores
        self.dont_kill = dont_kill

        self.players = self.load_local_players(local_ai_locations)
        if self.players and not config.global_wait_for_players:
            self._logger.warning("Config option `global.wait-for-players=false` is not supported for local players.")

        if grpc_address and len(self.players) < config.global_players:
            from seekers.grpc.server import GrpcSeekersServer
            try:
                self.grpc = GrpcSeekersServer(self, grpc_address)
            except ImportError as e:
                self._logger.warning("gRPC server could not be started. Import error.", exc_info=e)
                self.grpc = None
        else:
            self.grpc = None

        self.world = world.World(*self.config.map_dimensions)
        self.goals = []
        self.camps = []

        self.renderer = draw.GameRenderer(
            self.config,
            debug_mode=self.debug
        )
        self.animations = []

        self.clock = None
        self.ticks = 0

    def start(self):
        """Start the game. Run the mainloop and block until the game is over."""
        self._logger.info(f"Starting game. (Seed: {self.config.global_seed}, Players: {len(self.players)})")

        self.clock = pygame.time.Clock()

        random.seed(self.config.global_seed)

        # initialize goals
        self.goals = [goal.Goal.from_config(get_id("Goal"), self.world.random_position(), self.config) for _ in
                      range(self.config.global_goals)]

        # initialize players
        for p in self.players.values():
            p.seekers = {
                (id_ := get_id("Seeker")): seeker.Seeker.from_config(p, id_, self.world.random_position(), self.config)
                for _ in range(self.config.global_seekers)
            }
            p.color = self.get_new_player_color(p)

        # set up camps
        self.camps = self.world.generate_camps(self.players.values(), self.config)

        # prepare graphics
        self.renderer.init(self.players.values())

        try:
            if self.grpc:
                self.grpc.start_game()

            self.mainloop()
        finally:
            if self.grpc:
                self.grpc.stop()

    def mainloop(self):
        """Start the game. Block until the game is over."""
        random.seed(self.config.global_seed)
        running = True

        while running:
            # self._logger.debug(f"Tick {self.ticks:_}")

            # handle pygame events
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False

            # perform game logic
            for _ in range(self.config.global_speed):
                if self.grpc:
                    self.grpc.new_tick()

                # end game if tournament_length has been reached
                if self.config.global_playtime and self.ticks >= self.config.global_playtime:
                    if self.dont_kill:
                        continue
                    else:
                        running = False
                        break

                for player_ in self.players.values():
                    # self._logger.debug(f"Polling AI for player {player.name}")
                    player_.poll_ai(self.config.global_wait_for_players, self.world, self.goals, self.players,
                                    self.ticks, self.debug)

                game_logic.tick(self.players.values(), self.camps, self.goals, self.animations, self.world)

                self.ticks += 1

            # draw graphics
            self.renderer.draw(self.players.values(), self.camps, self.goals, self.animations, self.clock)

            self.clock.tick(self.config.global_fps)

        self._logger.info(f"Game over. (Ticks: {self.ticks:_})")

        if self.do_print_scores:
            self.print_scores()

        self.renderer.close()

    def listen(self):
        """Block until all players have connected unless gRPC is disabled. This may start a gRPC server."""

        def wait_for_players():
            last_diff = None
            while len(self.players) < self.config.global_players:
                # start can be called multiple times
                self.grpc.start_server()

                new_diff = self.config.global_players - len(self.players)

                if new_diff != last_diff:
                    self._logger.info(
                        f"Waiting for players to connect: "
                        f"{len(self.players)}/{self.config.global_players}"
                    )
                    last_diff = new_diff

                time.sleep(0.1)

        if len(self.players) >= self.config.global_players:
            # already enough players
            return

        if self.grpc:
            wait_for_players()

    @staticmethod
    def load_local_players(ai_locations: typing.Iterable[str]) -> dict[str, player.Player]:
        """Return the players found in the given directories or files."""
        out: dict[str, player.Player] = {}

        for location in ai_locations:
            if os.path.isdir(location):
                for filename in glob.glob(os.path.join(location, "ai*.py")):
                    player_ = player.LocalPlayer.from_file(filename)
                    out |= {player_.id: player_}
            elif os.path.isfile(location):
                player_ = player.LocalPlayer.from_file(location)
                out |= {player_.id: player_}
            else:
                raise Exception(f"Invalid AI location: {location!r} is neither a file nor a directory.")

        return out

    def add_player(self, player_: player.Player):
        """Add a player to the game while it is not running yet and raise a GameFullError if the game is full.
        This function is used by the gRPC server."""

        if self.camps:
            raise GameFullError("Game must not be running to add a player.")

        if len(self.players) >= self.config.global_players:
            raise GameFullError(
                f"Game full. Cannot add more players. Max player count is {self.config.global_players}."
            )

        self.players |= {player_.id: player_}

    def print_scores(self):
        for player_ in sorted(self.players.values(), key=lambda p: p.score, reverse=True):
            print(f"{player_.score} P.:\t{player_.name}")

    def get_new_player_color(self, player_: player.Player) -> colors.Color:
        old_colors = [p.color for p in self.players.values() if p.color is not None]

        preferred = (
            colors.string_hash_color(player_.name) if player_.preferred_color is None else player_.preferred_color
        )

        return colors.pick_new(old_colors, preferred, threshold=self.config.global_color_threshold)

    @property
    def seekers(self) -> collections.ChainMap[str, seeker.Seeker]:
        return collections.ChainMap(*(p.seekers for p in self.players.values()))
