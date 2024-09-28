from __future__ import annotations

import abc
import copy
import dataclasses
import logging
import os
import textwrap
import threading
import typing

from .vector import *
from seekers.graphics.colors import *
from seekers.ids import *
from . import seeker, camp, goal, world

__all__ = [
    "Player",
    "LocalPlayerAi",
    "LocalPlayer",
    "GrpcClientPlayer",
    "InvalidAiOutputError",
    "DecideCallable",
    "AiInput",
]

AiInput = tuple[
    list["Seeker"], list["Seeker"], list["Seeker"], list["Goal"], list["Player"], "Camp", list["Camp"], "World", float
]
DecideCallable = typing.Callable[
    [
        list["Seeker"],  # my seekers
        list["Seeker"],  # other seekers
        list["Seeker"],  # all seekers
        list["Goal"],  # goals
        list["Player"],  # other_players
        "Camp",  # my camp
        list["Camp"],  # camps
        "World",  # world
        float  # time
    ],
    list["Seeker"]  # new my seekers
]


@dataclasses.dataclass
class Player:
    id: str
    name: str
    score: int
    seekers: dict[str, seeker.Seeker]

    color: Color | None = dataclasses.field(init=False, default=None)
    camp: camp.Camp | None = dataclasses.field(init=False, default=None)
    debug_drawings: list = dataclasses.field(init=False, default_factory=list)
    preferred_color: Color | None = dataclasses.field(init=False, default=None)

    @abc.abstractmethod
    def poll_ai(self, wait: bool, world_: world.World, goals: list[goal.Goal],
                players: dict[str, "Player"], time_: float, debug: bool):
        ...


class InvalidAiOutputError(Exception):
    ...


@dataclasses.dataclass
class LocalPlayerAi:
    filepath: str
    timestamp: float
    decide_function: DecideCallable
    preferred_color: Color | None = None

    @staticmethod
    def load_module(filepath: str) -> tuple[DecideCallable, Color | None]:
        try:
            with open(filepath) as f:
                code = f.read()

            if code.strip().startswith("#bot"):
                logging.info(f"AI {filepath!r} was loaded in compatibility mode. (#bot)")
                # Wrap code inside a decide function (compatibility).
                # The old function that did this was called 'mogrify'.

                func_header = (
                    "def decide(seekers, other_seekers, all_seekers, goals, otherPlayers, own_camp, camps, world, "
                    "passed_time):"
                )

                fist_line, code = code.split("\n", 1)

                code = func_header + fist_line + ";\n" + textwrap.indent(code + "\nreturn seekers", " ")

            mod = compile("".join(code), filepath, "exec")

            mod_dict = {}
            exec(mod, mod_dict)

            preferred_color = mod_dict.get("__color__", None)
            if preferred_color is not None:
                if not (isinstance(preferred_color, tuple) or isinstance(preferred_color, list)):
                    raise TypeError(f"__color__ must be a tuple or list, not {type(preferred_color)!r}.")

                if len(preferred_color) != 3:
                    raise ValueError(f"__color__ must be a tuple or list of length 3, not {len(preferred_color)}.")

            if "decide" not in mod_dict:
                raise KeyError(f"AI {filepath!r} does not have a 'decide' function.")

            return mod_dict["decide"], preferred_color
        except Exception as e:
            # print(f"Error while loading AI {filepath!r}", file=sys.stderr)
            # traceback.print_exc(file=sys.stderr)
            # print(file=sys.stderr)

            raise InvalidAiOutputError(f"Error while loading AI {filepath!r}. Dummy AIs are not supported.") from e

    @classmethod
    def from_file(cls, filepath: str) -> "LocalPlayerAi":
        decide_func, preferred_color = cls.load_module(filepath)

        return cls(filepath, os.path.getctime(filepath), decide_func, preferred_color)

    def update(self):
        new_timestamp = os.path.getctime(self.filepath)
        if new_timestamp > self.timestamp:
            logger = logging.getLogger("AiReloader")
            logger.debug(f"Reloading AI {self.filepath!r}.")

            self.decide_function, self.preferred_color = self.load_module(self.filepath)
            self.timestamp = new_timestamp


@dataclasses.dataclass
class LocalPlayer(Player):
    """A player whose decide function is called directly. See README.md old method."""
    ai: LocalPlayerAi

    _ai_seekers: dict[str, seeker.Seeker] = dataclasses.field(init=False, default=None)
    _ai_goals: list[goal.Goal] = dataclasses.field(init=False, default=None)
    _ai_players: dict[str, Player] = dataclasses.field(init=False, default=None)

    def __post_init__(self):
        self._logger = logging.getLogger(self.name)

    @property
    def preferred_color(self) -> Color | None:
        return self.ai.preferred_color

    def init_ai_state(self, goals: list[goal.Goal], players: dict[str, "Player"]):
        self._ai_goals = [copy.deepcopy(goal_) for goal_ in goals]

        self._ai_players = {}
        self._ai_seekers = {}

        for player in players.values():
            p = Player(
                id=player.id,
                name=player.name,
                score=player.score,
                seekers={},
            )
            p.color = copy.deepcopy(player.color)
            p.preferred_color = copy.deepcopy(player.preferred_color)
            p.camp = camp.Camp(
                id=player.camp.id,
                owner=p,
                position=player.camp.position.copy(),
                width=player.camp.width,
                height=player.camp.height
            )

            self._ai_players[player.id] = p

            for seeker_ in player.seekers.values():
                s = copy.deepcopy(seeker_)
                s.owner = p

                p.seekers[seeker_.id] = s
                self._ai_seekers[seeker_.id] = s

    def update_ai_state(self, goals: list[goal.Goal], players: dict[str, "Player"]):
        if self._ai_seekers is None:
            self.init_ai_state(goals, players)

        for ai_goal, goal_ in zip(self._ai_goals, goals):
            ai_goal.position = goal_.position.copy()
            ai_goal.velocity = goal_.velocity.copy()
            ai_goal.owner = self._ai_players[goal_.owner.id] if goal_.owner else None
            ai_goal.time_owned = goal_.time_owned

        for player in players.values():
            for seeker_id, seeker_ in player.seekers.items():
                ai_seeker = self._ai_seekers[seeker_id]

                ai_seeker.position = seeker_.position.copy()
                ai_seeker.velocity = seeker_.velocity.copy()
                ai_seeker.target = seeker_.target.copy()
                ai_seeker.disabled_counter = seeker_.disabled_counter
                ai_seeker.magnet.strength = seeker_.magnet.strength

    def get_ai_input(
        self,
        world_: world.World,
        goals: list[goal.Goal],
        players: dict[str, Player],
        time: float
    ) -> AiInput:
        self.update_ai_state(goals, players)

        me = self._ai_players[self.id]
        my_camp = me.camp
        my_seekers = list(me.seekers.values())
        other_seekers = [s for p in self._ai_players.values() for s in p.seekers.values() if p is not me]
        all_seekers = my_seekers + other_seekers
        camps = [p.camp for p in self._ai_players.values()]

        return (
            my_seekers,
            other_seekers,
            all_seekers,
            self._ai_goals.copy(),
            [player for player in self._ai_players.values() if player is not me],
            my_camp, camps,
            world.World(world_.width, world_.height),
            time
        )

    def call_ai(self, ai_input: AiInput, debug: bool) -> typing.Any:
        def call():
            new_debug_drawings = []

            if debug:
                from seekers.graphics.debug_drawing import add_debug_drawing_func_ctxtvar
                add_debug_drawing_func_ctxtvar.set(new_debug_drawings.append)

            ai_out = self.ai.decide_function(*ai_input)

            self.debug_drawings = new_debug_drawings

            return ai_out

        try:
            # only check for an updated file every 10 game ticks
            *_, passed_playtime = ai_input
            if int(passed_playtime) % 10 == 0:
                self.ai.update()

            return call()
        except Exception as e:
            raise InvalidAiOutputError(f"AI {self.ai.filepath!r} raised an exception") from e

    def process_ai_output(self, ai_output: typing.Any):
        if not isinstance(ai_output, list):
            raise InvalidAiOutputError(f"AI output must be a list, not {type(ai_output)!r}.")

        if len(ai_output) != len(self.seekers):
            raise InvalidAiOutputError(f"AI output length must be {len(self.seekers)}, not {len(ai_output)}.")

        for ai_seeker in ai_output:
            try:
                own_seeker = self.seekers[ai_seeker.id]
            except IndexError as e:
                raise InvalidAiOutputError(
                    f"AI output contains a seeker with id {ai_seeker.id!r} which is not one of the player's seekers."
                ) from e

            if not isinstance(ai_seeker, seeker.Seeker):
                raise InvalidAiOutputError(f"AI output must be a list of Seekers, not {type(ai_seeker)!r}.")

            if not isinstance(ai_seeker.target, Vector):
                raise InvalidAiOutputError(
                    f"AI output Seeker target must be a Vector, not {type(ai_seeker.target)!r}.")

            if not isinstance(ai_seeker.magnet, seeker.Magnet):
                raise InvalidAiOutputError(
                    f"AI output Seeker magnet must be a Magnet, not {type(ai_seeker.magnet)!r}.")

            try:
                own_seeker.target.x = float(ai_seeker.target.x)
                own_seeker.target.y = float(ai_seeker.target.y)
            except ValueError as e:
                raise InvalidAiOutputError(
                    f"AI output Seeker target Vector components must be numbers, not {ai_seeker.target!r}."
                ) from e

            try:
                own_seeker.magnet.strength = float(ai_seeker.magnet.strength)
            except ValueError as e:
                raise InvalidAiOutputError(
                    f"AI output Seeker magnet strength must be a float, not {ai_seeker.magnet.strength!r}."
                ) from e

    def poll_ai(self, wait: bool, world_: world.World, goals: list[goal.Goal], players: dict[str, Player],
                time_: float, debug: bool):
        # ignore wait flag, supporting it would be a lot of extra code, instead always wait (blocking)

        ai_input = self.get_ai_input(world_, goals, players, time_)

        try:
            ai_output = self.call_ai(ai_input, debug)

            self.process_ai_output(ai_output)
        except InvalidAiOutputError as e:
            self._logger.error(f"AI {self.ai.filepath!r} output is invalid.", exc_info=e)

    @classmethod
    def from_file(cls, filepath: str) -> "LocalPlayer":
        name, _ = os.path.splitext(filepath)

        return LocalPlayer(
            id=get_id("Player"),
            name=name,
            score=0,
            seekers={},
            ai=LocalPlayerAi.from_file(filepath)
        )


class GrpcClientPlayer(Player):
    """A player whose decide function is called via a gRPC server and client. See README.md new method."""

    def __init__(self, token: str, *args, preferred_color: Color | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.was_updated = threading.Event()
        self.num_updates = 0
        self.preferred_color = preferred_color
        self.token = token

    def wait_for_update(self):
        timeout = 5  # seconds

        was_updated = self.was_updated.wait(timeout)

        if not was_updated:
            raise TimeoutError(
                f"GrpcClientPlayer {self.name!r} did not update in time. (Timeout is {timeout} seconds.)"
            )

        self.was_updated.clear()

    def poll_ai(self, wait: bool, world_: world.World, goals: list[goal.Goal], players: dict[str, Player],
                time_: float, debug: bool):
        if wait:
            self.wait_for_update()
