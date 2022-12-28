from __future__ import annotations

from .hash_color import Color
from .seekers_types import *
from . import game_logic, draw, hash_color

import logging
import time
import collections
import typing
import os
import glob
import pygame
import random

pygame.init()


class GameFullError(Exception): ...


class SeekersGame:
    """A Seekers game. Manages the game logic, players, the gRPC server and graphics."""

    def __init__(self, local_ai_locations: typing.Iterable[str], config: Config,
                 grpc_address: typing.Literal[False] | str = "localhost:7777", seed: float = 42,
                 debug: bool = True):
        self._logger = logging.getLogger("SeekersGame")

        self.config = config
        self.debug = debug
        self.seed = seed

        if grpc_address:
            from .grpc import GrpcSeekersServer
            self.grpc = GrpcSeekersServer(self, grpc_address)
        else:
            self.grpc = None

        self.players = self.load_local_players(local_ai_locations)
        self.world = World(*self.config.map_dimensions)
        self.goals = []
        self.camps = []


        self.animations = []

        self.ticks = 0

    def start(self):
        """Start the game. Run the mainloop and block until the game is over."""
        self._logger.info(f"Starting game. (Seed: {self.seed})")

        self.clock = pygame.time.Clock()

        random.seed(self.seed)

        # initialize goals
        self.goals = [InternalGoal(get_id("Goal"), self.world.random_position(), Vector(), self.config) for _ in
                      range(self.config.global_goals)]

        # initialize players
        for p in self.players.values():
            p.seekers = {
                (id_ := get_id("Seeker")): InternalSeeker(id_, self.world.random_position(), Vector(), p, self.config)
                for _ in range(self.config.global_seekers)
            }
            p.color = self.get_new_player_color(p.name)

        # set up camps
        self.camps = self.world.generate_camps(self.players.values(), self.config)

        #print(list(list(self.players.values())[0].seekers.values())[0])
        reference = list(list(self.players.values())[0].seekers.values())[0]
        reference = None
        reference = self.goals[0]
        self.renderer = draw.GameRenderer(self.config, \
                                          reference=reference\
                                          , debug_mode=self.debug)

        # prepare graphics
        self.renderer.init(self.players.values())

        if self.grpc:
            self.grpc.start_game()

        self.mainloop()

    def get_time(self):
        return self.ticks

    def mainloop(self):
        """Start the game. Block until the game is over."""
        running = True

        while running:
            # handle pygame events
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False

            # perform game logic
            for _ in range(self.config.updates_per_frame):
                for player in self.players.values():
                    player.poll_ai(self.config.global_wait_for_players, self.world,
                                   self.goals, self.players, self.get_time, self.debug)

                game_logic.tick(self.players.values(), self.camps, self.goals, self.animations, self.world)

                self.ticks += 1

                # end game if tournament_length has been reached
                if self.config.global_playtime and self.ticks >= self.config.global_playtime:
                    running = False
                    break

            # draw graphics
            self.renderer.draw(self.players.values(), self.camps, self.goals, self.animations, self.clock)

            self.clock.tick(self.config.global_fps)

        self._logger.info(f"Game over. (Ticks: {self.ticks:_})")

        self.print_scores()

        if self.grpc:
            self.grpc.stop()

    def listen(self):
        """Start the gRPC server. Block until all players have connected
        unless global.auto-play is set and unless grpc is disabled."""
        if self.grpc:
            self.grpc.start()

            if not self.config.global_auto_play:
                last_diff = None

                while len(self.players) < self.config.global_players:
                    new_diff = self.config.global_players - len(self.players)

                    if new_diff != last_diff:
                        self._logger.info(
                            f"Waiting for players to connect: {self.config.global_players - len(self.players)}"
                        )
                        last_diff = new_diff

                    time.sleep(0.1)

    @staticmethod
    def load_local_players(ai_locations: typing.Iterable[str]) -> dict[str, InternalPlayer]:
        """Return the players found in the given directories or files."""
        out: dict[str, InternalPlayer] = {}

        for location in ai_locations:
            if os.path.isdir(location):
                for filename in glob.glob(os.path.join(location, "ai*.py")):
                    player = LocalPlayer.from_file(filename)
                    out |= {player.id: player}
            elif os.path.isfile(location):
                player = LocalPlayer.from_file(location)
                out |= {player.id: player}
            else:
                raise Exception(f"Invalid AI location: {location!r} is neither a file nor a directory.")

        return out

    def add_player(self, player: InternalPlayer):
        """Add a player to the game and raise a GameFullError if the game is full."""
        if len(self.players) >= self.config.global_players:
            raise GameFullError(
                f"Game full. Cannot add more players. Max player count is {self.config.global_players}."
            )

        self.players |= {player.id: player}

    def print_scores(self):
        for player in sorted(self.players.values(), key=lambda p: p.score, reverse=True):
            print(f"{player.score} P.:\t{player.name}")

        if self.config.flags_t_test and len(self.players) == 2:
            p = self.renderer.students_ttest(self.players.values())
            print(f"T-Test (probability of null hypothesis): {p:.2e} ({p:.2%})")

    def get_new_player_color(self, name: str) -> Color:
        old_colors = [p.color for p in self.players.values() if p.color is not None]
        preferred = hash_color.string_hash_color(name)

        return hash_color.pick_new(old_colors, preferred, threshold=self.config.global_color_threshold)

    @property
    def seekers(self) -> collections.ChainMap[str, InternalSeeker]:
        return collections.ChainMap(*(p.seekers for p in self.players.values()))
