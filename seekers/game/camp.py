from __future__ import annotations

import dataclasses

from .vector import *
from . import player

__all__ = [
    "Camp"
]


@dataclasses.dataclass
class Camp:
    id: str
    owner: player.Player
    position: Vector
    width: float
    height: float

    def contains(self, pos: Vector) -> bool:
        delta = self.position - pos
        return 2 * abs(delta.x) < self.width and 2 * abs(delta.y) < self.height

    @property
    def top_left(self) -> Vector:
        return self.position - Vector(self.width, self.height) / 2

    @property
    def bottom_right(self) -> Vector:
        return self.position + Vector(self.width, self.height) / 2
