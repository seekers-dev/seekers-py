from .hash_color import *

import configparser
import math
import random
from collections import defaultdict

from typing import Callable
import dataclasses
import abc

_IDS = defaultdict(list)


def get_id(obj: str):
    while (id_ := random.randint(0, 2 ** 32)) in _IDS[obj]:
        ...

    _IDS[obj].append(id_)

    return f"py-seekers.{obj}@{id_}"


@dataclasses.dataclass(frozen=True)
class Config:
    global_auto_play: bool
    global_playtime: int
    global_speed: int
    global_players: int
    global_seekers: int
    global_goals: int

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
            global_auto_play=cp.getboolean("global", "auto-play"),
            global_playtime=cp.getint("global", "playtime"),
            global_speed=cp.getint("global", "speed"),
            global_players=cp.getint("global", "players"),
            global_seekers=cp.getint("global", "seekers"),
            global_goals=cp.getint("global", "goals"),

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
            goal_mass=cp.getfloat("goal", "mass")
        )

    @classmethod
    def from_filepath(cls, filepath: str) -> "Config":
        with open(filepath) as f:
            return cls.from_file(f)


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

    def __iter__(self):
        return iter((self.x, self.y))

    def __getitem__(self, i: int):
        if i == 0:
            return self.x
        elif i == 1:
            return self.y
        else:
            raise IndexError

    def __add__(self, other: "Vector"):
        return Vector(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector"):
        return Vector(self.x - other.x, self.y - other.y)

    def __neg__(self):
        return self * (-1)

    def __mul__(self, factor):
        return Vector(self.x * factor, self.y * factor)

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, divisor):
        return self * (1 / divisor)

    def __rtruediv__(self, other):
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

    def map(self, func: Callable[[float], float]) -> "Vector":
        return Vector(func(self.x), func(self.y))

    def __repr__(self):
        return f"Vector({self.x}, {self.y})"

    def __format__(self, format_spec):
        return f"Vector({self.x:{format_spec}}, {self.y:{format_spec}})"


class Physical:
    def __init__(self, id_: str, position: Vector, velocity: Vector, mass: float, radius: float):
        self.id = id_
        self.position = position
        self.velocity = velocity
        self.acceleration = Vector(0, 0)
        self.mass = mass
        self.radius = radius


class InternalPhysical(Physical):
    def __init__(self, id_: str, position: Vector, velocity: Vector, mass: float, radius: float, config: Config):
        super().__init__(id_, position, velocity, mass, radius)
        self.config = config

    def update_acceleration(self, world: "World") -> Vector:
        ...

    def move(self, world: "World"):
        # friction
        self.velocity *= 1 - self.config.physical_friction

        # acceleration
        self.update_acceleration(world)
        self.velocity += self.acceleration * self.thrust()

        # displacement
        self.position += self.velocity

        world.normalize_position(self.position)

    def thrust(self) -> float:
        return self.config.physical_max_speed * self.config.physical_friction

    def collision(self, other: "InternalPhysical", world: "World"):
        min_dist = self.radius + other.radius

        # elastic collision
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


class Goal(Physical): ...


class InternalGoal(InternalPhysical, Goal):
    def __init__(self, id_: str, position: Vector, velocity: Vector, config: Config):
        super().__init__(id_, position, velocity, config.goal_mass, config.goal_radius, config)
        self.owner = None
        self.owned_for = 0

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


class Magnet:
    def __init__(self, strength=0):
        self.strength = strength

    @property
    def strength(self):
        return self._strength

    @strength.setter
    def strength(self, value):
        assert 1 >= value >= -8

        self._strength = value

    def is_on(self):
        # TODO: to property
        return not self.strength == 0

    def set_repulsive(self):
        self.strength = -8

    def set_attractive(self):
        self.strength = 1

    def disable(self):
        self.strength = 0


class Seeker(Physical):
    def __init__(self, id_: str, position: Vector, velocity: Vector, mass: float, radius: float):
        super().__init__(id_, position, velocity, mass, radius)
        self.target = self.position
        self.disabled_counter = 0
        self.magnet = Magnet()

    @property
    def is_disabled(self):
        return self.disabled_counter > 0

    def magnetic_force(self, world, pos: Vector) -> Vector:
        def bump(r) -> float:
            return math.exp(1 / (r ** 2 - 1)) if r < 1 else 0

        r = world.torus_distance(self.position, pos) / world.diameter()
        d = world.torus_direction(self.position, pos)

        return Vector(0, 0) if self.is_disabled else - d * (self.magnet.strength * bump(r * 10))

    # TODO: deprecate all methods below
    def set_magnet_repulsive(self):
        self.magnet.set_repulsive()

    def set_magnet_attractive(self):
        self.magnet.set_attractive()

    def disable_magnet(self):
        self.magnet.disable()

    def set_magnet_disabled(self):
        self.magnet.disable()


class InternalSeeker(InternalPhysical, Seeker):
    def __init__(self, id_: str, position: Vector, velocity: Vector, config: Config):
        super().__init__(id_, position, velocity, config.seeker_mass, config.seeker_radius, config)
        self.target = self.position
        self.disabled_counter = 0
        self.magnet = Magnet()

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

    def collision(self, other: "InternalSeeker", world):
        if self.magnet.is_on():
            self.disable()
        if other.magnet.is_on():
            other.disable()

        if not (self.magnet.is_on() or other.magnet.is_on()):
            self.disable()
            other.disable()

        InternalPhysical.collision(self, other, world)


DecideCallable = Callable[
    [list[Seeker], list[Seeker], list[Seeker], list[Goal], list["Player"], "Camp", list["Camp"], "World", float], list[Seeker]
    # my seekers   other seekers all seekers   goals       other_players   my camp camps         world    time    new my seekers
]


@dataclasses.dataclass
class PlayerAI(abc.ABC):
    filepath: str
    timestamp: float
    decide_function: DecideCallable


@dataclasses.dataclass
class Player:
    id: str
    name: str
    score: int = dataclasses.field(default=0)
    seekers: list[Seeker] = dataclasses.field(default_factory=list)
    _color = None

    @property
    def color(self):
        if self._color:
            return self._color

        return string_hash_color(self.name)


@dataclasses.dataclass
class InternalPlayer:
    id: str
    name: str
    ai: PlayerAI
    score: int = dataclasses.field(default=0)
    seekers: list[InternalSeeker] = dataclasses.field(default_factory=list)

    @property
    def color(self):
        return string_hash_color(self.name)


class World:
    def __init__(self, width, height, debug_mode=True):
        self.width = width
        self.height = height
        self.debug_mode = debug_mode

    def normalize_position(self, pos: Vector):
        pos.x -= math.floor(pos.x / self.width) * self.width
        pos.y -= math.floor(pos.y / self.height) * self.height

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

    def gen_camp(self, n, i, player: Player):
        r = self.diameter() / 4
        width = height = r / 5

        pos = self.middle() + Vector.from_polar(2 * math.pi * i / n) * r
        return Camp(get_id("Camp"), player, pos, width, height)

    def generate_camps(self, players) -> list:
        return [self.gen_camp(len(players), i, p) for i, p in enumerate(players)]


@dataclasses.dataclass
class Camp:
    id: str
    owner: Player
    position: Vector
    width: float
    height: float

    def contains(self, pos: Vector) -> bool:
        delta = self.position - pos
        return 2 * abs(delta.x) < self.width and 2 * abs(delta.y) < self.height
