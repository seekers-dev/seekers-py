import math
import random
import typing

from seekers.vector import Vector
from .camp import Camp
from .config import Config, get_id


class World:
    """The world in which the game takes place. This class mainly handles the torus geometry."""

    def __init__(self, width, height):
        self.width = width
        self.height = height

    def normalize_position(self, pos: Vector):
        pos.x -= math.floor(pos.x / self.width) * self.width
        pos.y -= math.floor(pos.y / self.height) * self.height

    def normalized_position(self, pos: Vector):
        tmp = pos.copy()
        self.normalize_position(tmp)
        return tmp

    @property
    def geometry(self) -> Vector:
        return Vector(self.width, self.height)

    def diameter(self) -> float:
        return self.geometry.length()

    def middle(self) -> Vector:
        return self.geometry / 2

    def torus_difference(self, left: Vector, right: Vector, /) -> Vector:
        def diff1d(length, a, b):
            delta = abs(a - b)
            return b - a if delta < length - delta else a - b

        return Vector(diff1d(self.width, left.x, right.x),
                      diff1d(self.height, left.y, right.y))

    def torus_distance(self, left: Vector, right: Vector, /) -> float:
        return self.torus_difference(left, right).length()

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

    def nearest_goal(self, pos: Vector, goals: list):
        i = self.index_of_nearest(pos, [g.position for g in goals])
        return goals[i]

    def nearest_seeker(self, pos: Vector, seekers: list):
        i = self.index_of_nearest(pos, [s.position for s in seekers])
        return seekers[i]

    def random_position(self) -> Vector:
        return Vector(random.uniform(0, self.width),
                      random.uniform(0, self.height))

    def generate_camps(self, players: typing.Collection, config: Config) -> list["Camp"]:
        delta = self.height / len(players)

        if config.camp_height > delta:
            raise ValueError("Config value camp.height is too large. The camps would overlap. It must be smaller than "
                             "the height of the world divided by the number of players. ")

        for i, player in enumerate(players):
            camp = Camp(
                id=get_id("Camp"),
                owner=player,
                position=Vector(self.width / 2, delta * (i + 0.5)),
                width=config.camp_width,
                height=config.camp_height,
            )
            player.camp = camp

        return [player.camp for player in players]
