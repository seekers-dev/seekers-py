from __future__ import annotations

import logging
import os
import threading
import configparser
import math
import dataclasses
import abc
import random
import traceback
import typing
from multiprocessing.pool import ThreadPool
from collections import defaultdict

from . import Color

_IDS = defaultdict(list)


def get_id(obj: str):
    rng = random.Random(obj)

    while (id_ := rng.randint(0, 2 ** 32)) in _IDS[obj]:
        ...

    _IDS[obj].append(id_)

    return f"py-seekers.{obj}@{id_}"


@dataclasses.dataclass
class Config:
    """Configuration for the Seekers game."""
    global_wait_for_players: bool
    global_playtime: int
    global_fps: int
    global_speed: int
    global_players: int
    global_seekers: int
    global_goals: int
    global_color_threshold: float

    map_width: int
    map_height: int

    camp_width: int
    camp_height: int

    physical_max_speed: float
    physical_friction: float

    seeker_magnet_slowdown: float
    seeker_disabled_time: int
    seeker_radius: float
    seeker_mass: float

    goal_scoring_time: int
    goal_radius: float
    goal_mass: float

    flags_experimental_friction: bool
    flags_t_test: bool
    flags_relative_drawing_to: str

    @property
    def updates_per_frame(self):
        return self.global_speed

    @property
    def map_dimensions(self):
        return self.map_width, self.map_height

    @classmethod
    def from_file(cls, file) -> "Config":
        cp = configparser.ConfigParser()
        cp.read_file(file)

        return cls(
            global_wait_for_players=cp.getboolean("global", "wait-for-players"),
            global_playtime=cp.getint("global", "playtime"),
            global_fps=cp.getint("global", "fps"),
            global_speed=cp.getint("global", "speed"),
            global_players=cp.getint("global", "players"),
            global_seekers=cp.getint("global", "seekers"),
            global_goals=cp.getint("global", "goals"),
            global_color_threshold=cp.getfloat("global", "color-threshold"),

            map_width=cp.getint("map", "width"),
            map_height=cp.getint("map", "height"),

            camp_width=cp.getint("camp", "width"),
            camp_height=cp.getint("camp", "height"),

            physical_max_speed=cp.getfloat("physical", "max-speed"),
            physical_friction=cp.getfloat("physical", "friction"),

            seeker_magnet_slowdown=cp.getfloat("seeker", "magnet-slowdown"),
            seeker_disabled_time=cp.getint("seeker", "disabled-time"),
            seeker_radius=cp.getfloat("seeker", "radius"),
            seeker_mass=cp.getfloat("seeker", "mass"),

            goal_scoring_time=cp.getint("goal", "scoring-time"),
            goal_radius=cp.getfloat("goal", "radius"),
            goal_mass=cp.getfloat("goal", "mass"),

            flags_experimental_friction=cp.getboolean("flags", "experimental-friction"),
            flags_t_test=cp.getboolean("flags", "t-test"),
            flags_relative_drawing_to=cp.get("flags", "relative-drawing-to"),
        )

    @classmethod
    def from_filepath(cls, filepath: str) -> "Config":
        with open(filepath) as f:
            return cls.from_file(f)

    def to_properties(self) -> dict[str, str]:
        self_dict = dataclasses.asdict(self)

        def convert_specifier(specifier: str) -> str:
            specifier = specifier.replace("_", ".", 1)
            specifier = specifier.replace("_", "-")
            return specifier

        return {convert_specifier(k): str(v) for k, v in self_dict.items()}

    @classmethod
    def from_properties(cls, properties: dict[str, str]) -> "Config":
        """Converts a dictionary of properties, as received by a gRPC client, to a Config object."""
        all_kwargs = {field.name: field.type for field in dataclasses.fields(Config) if field.init}

        all_fields_as_none = {k: None for k in all_kwargs}

        kwargs = {}
        for key, value in properties.items():
            # field.name-example -> field_name_example
            field_name = key.replace(".", "_").replace("-", "_")
            # convert the value to the correct type
            try:
                type_ = eval(all_kwargs[field_name])  # annotations are strings for python 3.9 compatibility
            except KeyError:
                continue

            kwargs[field_name] = type_(value)

        kwargs = all_fields_as_none | kwargs

        return cls(**kwargs)


class Vector:
    def __init__(self, x: float = 0, y: float = 0):
        self.x = x
        self.y = y

    @staticmethod
    def from_polar(angle: float, radius: float = 1) -> "Vector":
        return Vector(math.cos(angle) * radius, math.sin(angle) * radius)

    def rotated(self, angle: float) -> "Vector":
        return Vector(
            math.cos(angle) * self.x - math.sin(angle) * self.y,
            math.sin(angle) * self.x + math.cos(angle) * self.y,
        )

    def rotated90(self) -> "Vector":
        return Vector(-self.y, self.x)

    def __iter__(self):
        return iter((self.x, self.y))

    def __getitem__(self, i: int):
        if i == 0:
            return self.x
        elif i == 1:
            return self.y

        raise IndexError

    def __add__(self, other: "Vector"):
        return Vector(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector"):
        return Vector(self.x - other.x, self.y - other.y)

    def __neg__(self):
        return self * (-1)

    def __mul__(self, factor: Vector | float):
        if isinstance(factor, Vector):
            return Vector(self.x * factor.x, self.y * factor.y)

        return Vector(self.x * factor, self.y * factor)

    def __rmul__(self, other: Vector | float):
        return self * other

    def __truediv__(self, divisor: Vector | float):
        return self * (1 / divisor)

    def __rtruediv__(self, other: Vector | float):
        if other == 1:
            return Vector(1 / self.x, 1 / self.y)

        return 1 / self * other

    def __bool__(self):
        return self.x or self.y

    def dot(self, other: "Vector") -> float:
        return self.x * other.x + self.y * other.y

    def squared_length(self) -> float:
        return self.x * self.x + self.y * self.y

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalized(self):
        norm = self.length()
        if norm == 0:
            return Vector(0, 0)
        else:
            return Vector(self.x / norm, self.y / norm)

    def map(self, func: typing.Callable[[float], float]) -> "Vector":
        return Vector(func(self.x), func(self.y))

    def copy(self) -> "Vector":
        return Vector(self.x, self.y)

    def __repr__(self):
        return f"Vector({self.x}, {self.y})"

    def __format__(self, format_spec):
        return f"Vector({self.x:{format_spec}}, {self.y:{format_spec}})"


class Physical:
    def __init__(self, id_: str, position: Vector, velocity: Vector, mass: float, radius: float, config: Config):
        self.id = id_
        self.position = position
        self.velocity = velocity
        self.acceleration = Vector(0, 0)
        self.mass = mass
        self.radius = radius
        self.config = config

    def update_acceleration(self, world: "World") -> Vector:
        ...

    def thrust(self) -> float:
        return self.config.physical_max_speed * self.config.physical_friction

    def move(self, world: "World"):
        if self.config.flags_experimental_friction:
            vel_fact = (
                math.sqrt(
                    self.velocity.length() ** 2 - 2 * self.config.physical_friction * self.velocity.length()
                ) / self.velocity.length()

                if (self.velocity.length() ** 2 - 2 * self.config.physical_friction * self.velocity.length()) > 0
                else 0
            )

            acc_fact = math.sqrt(
                self.velocity.length() ** 2 + 2 * self.thrust()
            ) - self.velocity.length()
        else:
            vel_fact = 1 - self.config.physical_friction
            acc_fact = self.thrust()

        # friction
        self.velocity *= vel_fact

        # acceleration
        self.update_acceleration(world)
        self.velocity += self.acceleration * acc_fact

        # displacement
        self.position += self.velocity

        world.normalize_position(self.position)

    def collision(self, other: "InternalPhysical", world: "World"):
        # elastic collision
        min_dist = self.radius + other.radius

        d = world.torus_difference(self.position, other.position)

        dn = d.normalized()
        dv = other.velocity - self.velocity
        m = 2 / (self.mass + other.mass)

        dvdn = dv.dot(dn)
        if dvdn < 0:
            self.velocity += dn * (m * other.mass * dvdn)
            other.velocity -= dn * (m * self.mass * dvdn)

        ddn = d.dot(dn)
        if ddn < min_dist:
            self.position += dn * (ddn - min_dist)
            other.position -= dn * (ddn - min_dist)


class InternalPhysical(Physical):
    ...


class Goal(Physical):
    def __init__(self, id_: str, position: Vector, velocity: Vector, mass: float, radius: float, config: Config):
        super().__init__(id_, position, velocity, mass, radius, config)
        self.owner: "Player | None" = None
        self.owned_for: int = 0


class InternalGoal(InternalPhysical, Goal):
    def __init__(self, id_: str, position: Vector, velocity: Vector, config: Config):
        super().__init__(id_, position, velocity, config.goal_mass, config.goal_radius, config)
        self.owner: "Player | None" = None
        self.owned_for: int = 0

    def camp_tick(self, camp: "Camp"):
        if camp.contains(self.position):
            if self.owner == camp.owner:
                self.owned_for += 1
            else:
                self.owned_for = 0
                self.owner = camp.owner
            return self.owned_for >= self.config.goal_scoring_time
        else:
            return False

    def to_ai_input(self, players: dict[str, Player]) -> Goal:
        # TODO: config object needs to be copied
        g = Goal(self.id, self.position.copy(), self.velocity.copy(), self.mass, self.radius, self.config)
        g.owner = None if self.owner is None else players[self.owner.id]
        g.owned_for = self.owned_for
        return g


class Magnet:
    def __init__(self, strength=0):
        self.strength = strength

    @property
    def strength(self):
        return self._strength

    @strength.setter
    def strength(self, value):
        if 1 >= value >= -8:
            self._strength = value
        else:
            raise ValueError("Magnet strength must be between -8 and 1.")

    def is_on(self):
        return self.strength != 0

    def set_repulsive(self):
        self.strength = -8

    def set_attractive(self):
        self.strength = 1

    def disable(self):
        self.strength = 0


class Seeker(Physical):
    def __init__(self, id_: str, position: Vector, velocity: Vector, mass: float, radius: float, owner: "Player",
                 config: Config):
        super().__init__(id_, position, velocity, mass, radius, config)
        self.target = self.position
        self.disabled_counter = 0
        self.magnet = Magnet()
        self.owner = owner

    @property
    def is_disabled(self):
        return self.disabled_counter > 0

    def disabled(self):
        return self.is_disabled

    def magnetic_force(self, world, pos: Vector) -> Vector:
        def bump(r) -> float:
            return math.exp(1 / (r ** 2 - 1)) if r < 1 else 0

        r = world.torus_distance(self.position, pos) / world.diameter()
        d = world.torus_direction(self.position, pos)

        return Vector(0, 0) if self.is_disabled else - d * (self.magnet.strength * bump(r * 10))

    # methods below are left in for compatibility
    def set_magnet_repulsive(self):
        self.magnet.set_repulsive()

    def set_magnet_attractive(self):
        self.magnet.set_attractive()

    def disable_magnet(self):
        self.magnet.disable()

    def set_magnet_disabled(self):
        self.magnet.disable()


class InternalSeeker(InternalPhysical, Seeker):
    def __init__(self, id_: str, position: Vector, velocity: Vector, owner: "InternalPlayer", config: Config):
        super().__init__(id_, position, velocity, config.seeker_mass, config.seeker_radius, owner, config)
        self.target = self.position.copy()
        self.disabled_counter = 0
        self.magnet = Magnet()
        self.owner = owner

    def disable(self):
        self.disabled_counter = self.config.seeker_disabled_time

    def update_acceleration(self, world):
        if self.disabled_counter == 0:
            a = world.torus_direction(self.position, self.target)
            self.acceleration = a
        else:
            self.acceleration = Vector(0, 0)

    def thrust(self) -> float:
        b = self.config.seeker_magnet_slowdown if self.magnet.is_on() else 1
        return InternalPhysical.thrust(self) * b

    def magnet_effective(self):
        return self.magnet.is_on() and not self.is_disabled

    def collision(self, other: "InternalSeeker", world):
        if self.magnet_effective():
            self.disable()
        if other.magnet_effective():
            other.disable()

        if not (self.magnet_effective() or other.magnet_effective()):
            self.disable()
            other.disable()

        InternalPhysical.collision(self, other, world)

    def to_ai_input(self, owner: "Player") -> Seeker:
        s = Seeker(self.id, self.position.copy(), self.velocity.copy(), self.mass, self.radius, owner, self.config)
        s.disabled_counter = self.disabled_counter
        s.target = self.target.copy()

        return s


AIInput = tuple[
    list[Seeker], list[Seeker], list[Seeker], list[Goal], list["Player"], "Camp", list["Camp"], "World", float
]
DecideCallable = typing.Callable[
    [list[Seeker], list[Seeker], list[Seeker], list[Goal], list["Player"], "Camp", list["Camp"], "World", float],
    list[Seeker]
    # my seekers   other seekers all seekers   goals       other_players   my camp camps         world    time
    # new my seekers
]


@dataclasses.dataclass
class Player:
    id: str
    name: str
    score: int
    seekers: dict[str, Seeker]

    color: Color | None = dataclasses.field(init=False, default=None)
    camp: typing.Union["Camp", None] = dataclasses.field(init=False, default=None)


@dataclasses.dataclass
class InternalPlayer(Player):
    seekers: dict[str, InternalSeeker]

    debug_drawings: list = dataclasses.field(init=False, default_factory=list)

    preferred_color: Color | None = dataclasses.field(init=False, default=None)

    def to_ai_input(self) -> Player:
        player = Player(self.id, self.name, self.score, {})
        player.seekers = {s.id: s.to_ai_input(player) for s in self.seekers.values()}
        player.camp = self.camp.to_ai_input(player)

        return player

    @abc.abstractmethod
    def poll_ai(self, wait: bool, world: "World", goals: list[InternalGoal],
                players: dict[str, "InternalPlayer"], time: typing.Callable[[], float], debug: bool):
        ...


class InvalidAiOutputError(Exception): ...


@dataclasses.dataclass
class LocalPlayerAI:
    filepath: str
    timestamp: float
    decide_function: DecideCallable
    preferred_color: Color | None = None

    @staticmethod
    def load_module(filepath: str) -> tuple[DecideCallable, Color | None]:
        try:
            with open(filepath) as f:
                code = f.readlines()

            if code[0].strip() == "#bot":
                logging.info(f"AI {filepath!r} was loaded in compatibility mode. (#bot)")
                # Wrap code inside a decide function (compatibility).
                # The old function that did this was called 'mogrify'.

                func_header = (
                    "def decide(seekers, other_seekers, all_seekers, goals, otherPlayers, own_camp, camps, world, "
                    "passed_time):"
                )

                code.append("return seekers")

                code = [func_header] + list(map(lambda line: "    " + line, code))

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
    def from_file(cls, filepath: str) -> "LocalPlayerAI":
        decide_func, preferred_color = cls.load_module(filepath)

        return cls(filepath, os.path.getctime(filepath), decide_func, preferred_color)

    def update(self):
        new_timestamp = os.path.getctime(self.filepath)
        if new_timestamp > self.timestamp:
            logger = logging.getLogger("AIReloader")
            logger.debug(f"Reloading AI {self.filepath!r}.")

            self.decide_function, self.preferred_color = self.load_module(self.filepath)
            self.timestamp = new_timestamp


@dataclasses.dataclass
class LocalPlayer(InternalPlayer):
    """A player whose decide function is called directly. See README.md old method."""
    ai: LocalPlayerAI

    _thread_pool: ThreadPool = dataclasses.field(init=False, default_factory=lambda: ThreadPool(1))
    _waiting: int = dataclasses.field(init=False, default=0)

    @property
    def preferred_color(self) -> Color | None:
        return self.ai.preferred_color

    def get_ai_input(self,
                     world: "World",
                     _goals: list[InternalGoal],
                     _players: dict[str, "InternalPlayer"],
                     time: float
                     ) -> AIInput:
        players = {p.id: p.to_ai_input() for p in _players.values()}
        me = players[self.id]
        my_camp = me.camp
        my_seekers = list(me.seekers.values())
        other_seekers = [s for p in players.values() for s in p.seekers.values() if p is not me]
        all_seekers = my_seekers + other_seekers
        camps = [p.camp for p in players.values()]

        goals = [g.to_ai_input(players) for g in _goals]

        return my_seekers, other_seekers, all_seekers, goals, list(players.values()), my_camp, camps, world, time

    def _call_ai(self, ai_input: AIInput, debug: bool) -> typing.Any:
        def call():
            new_debug_drawings = []

            if debug:
                from .debug_drawing import add_debug_drawing_func_ctxtvar
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

    def _process_ai_output(self, ai_output: typing.Any):
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

            if not isinstance(ai_seeker, Seeker):
                raise InvalidAiOutputError(f"AI output must be a list of Seekers, not {type(ai_seeker)!r}.")

            if not isinstance(ai_seeker.target, Vector):
                raise InvalidAiOutputError(
                    f"AI output Seeker target must be a Vector, not {type(ai_seeker.target)!r}.")

            if not isinstance(ai_seeker.magnet, Magnet):
                raise InvalidAiOutputError(
                    f"AI output Seeker magnet must be a Magnet, not {type(ai_seeker.magnet)!r}.")

            own_seeker.target.x = float(ai_seeker.target.x)
            own_seeker.target.y = float(ai_seeker.target.y)

            own_seeker.magnet.strength = int(ai_seeker.magnet.strength)

    def _update_ai_action(self, world: "World", goals: list[InternalGoal], players: dict[str, "InternalPlayer"],
                          time: typing.Callable[[], float], debug: bool):
        ai_input = self.get_ai_input(world, goals, players, time())

        ai_output = self._call_ai(ai_input, debug)

        self._process_ai_output(ai_output)

    def poll_ai(self, wait: bool, world: "World", goals: list[InternalGoal],
                players: dict[str, "InternalPlayer"], time_: typing.Callable[[], float], debug: bool):
        if wait:
            self._update_ai_action(world, goals, players, time_, debug)

        else:
            if self._waiting > 2:
                # no more than two items in the queue
                return

            def error_callback(e):
                p = traceback.format_exception(e)
                logging.getLogger(self.name).error("".join(p))

            def run(*args, **kwargs):
                self._waiting -= 1
                # We have time as a function because in the time
                # leading up to this being called, game time may
                # have passed.
                # The seekers, goals and players objects stay the
                # same (no copies), so we do not need a function.
                self._update_ai_action(*args, **kwargs)

            self._waiting += 1
            self._thread_pool.apply_async(
                run,
                args=(world, goals, players, time_, debug),
                error_callback=error_callback
            )

    @classmethod
    def from_file(cls, filepath: str) -> "LocalPlayer":
        name, _ = os.path.splitext(filepath)

        return LocalPlayer(
            id=get_id("Player"),
            name=name,
            score=0,
            seekers={},
            ai=LocalPlayerAI.from_file(filepath)
        )

    def __del__(self):
        # to prevent exception when the program closes
        self._thread_pool.terminate()


class GrpcClientPlayer(InternalPlayer):
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

    def poll_ai(self, wait: bool, world: "World", goals: list[InternalGoal],
                players: dict[str, "InternalPlayer"], time: typing.Callable[[], float], debug: bool):
        if wait:
            self.wait_for_update()


class World:
    """The world in which the game takes place. This class mainly handles the torus geometry."""

    def __init__(self, width, height):
        self.width = width
        self.height = height

    def normalize_position(self, pos: Vector):
        pos.x -= math.floor(pos.x / self.width) * self.width
        pos.y -= math.floor(pos.y / self.height) * self.height

    def normalized_position(self, pos: Vector):
        tmp = pos
        self.normalize_position(tmp)
        return tmp

    @property
    def geometry(self) -> Vector:
        return Vector(self.width, self.height)

    def diameter(self) -> float:
        return self.geometry.length()

    def middle(self) -> Vector:
        return self.geometry / 2

    def torus_distance(self, left: Vector, right: Vector, /) -> float:
        def dist1d(l, a, b):
            delta = abs(a - b)
            return min(delta, l - delta)

        return Vector(dist1d(self.width, right.x, left.x),
                      dist1d(self.height, right.y, left.y)).length()

    def torus_difference(self, left: Vector, right: Vector, /) -> Vector:
        def diff1d(l, a, b):
            delta = abs(a - b)
            return b - a if delta < l - delta else a - b

        return Vector(diff1d(self.width, left.x, right.x),
                      diff1d(self.height, left.y, right.y))

    def torus_direction(self, left: Vector, right: Vector, /) -> Vector:
        return self.torus_difference(left, right).normalized()

    def index_of_nearest(self, pos: Vector, positions: list) -> int:
        d = self.torus_distance(pos, positions[0])
        j = 0
        for i, p in enumerate(positions[1:]):
            dn = self.torus_distance(pos, p)
            if dn < d:
                d = dn
                j = i + 1
        return j

    def nearest_goal(self, pos: Vector, goals: list) -> Goal:
        i = self.index_of_nearest(pos, [g.position for g in goals])
        return goals[i]

    def nearest_seeker(self, pos: Vector, seekers: list) -> Seeker:
        i = self.index_of_nearest(pos, [s.position for s in seekers])
        return seekers[i]

    def random_position(self) -> Vector:
        return Vector(random.uniform(0, self.width),
                      random.uniform(0, self.height))

    def generate_camps(self, players: typing.Collection[Player], config: Config) -> list["Camp"]:
        delta_x = self.width / len(players)

        if config.camp_width > delta_x:
            raise ValueError("Config value camp.width is too large. The camps would overlap. It must be smaller than "
                             "the width of the world divided by the number of players. ")

        for i, player in enumerate(players):
            camp = Camp(
                id=get_id("Camp"),
                owner=player,
                position=Vector(delta_x * (i + 0.5), self.height / 2),
                width=config.camp_width,
                height=config.camp_height,
            )
            player.camp = camp

        return [player.camp for player in players]


@dataclasses.dataclass
class Camp:
    id: str
    owner: InternalPlayer | Player
    position: Vector
    width: float
    height: float

    def contains(self, pos: Vector) -> bool:
        delta = self.position - pos
        return 2 * abs(delta.x) < self.width and 2 * abs(delta.y) < self.height

    def to_ai_input(self, owner: Player) -> "Camp":
        return Camp(self.id, owner, self.position, self.width, self.height)

    @property
    def top_left(self) -> Vector:
        return self.position - Vector(self.width, self.height) / 2

    @property
    def bottom_right(self) -> Vector:
        return self.position + Vector(self.width, self.height) / 2
