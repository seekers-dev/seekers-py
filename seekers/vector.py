from __future__ import annotations

import math
import typing


__all__ = [
    "Vector",
]


class Vector:
    __slots__ = ("x", "y")

    def __init__(self, x: float = 0, y: float = 0):
        self.x = x
        self.y = y

    @staticmethod
    def from_polar(angle: float, radius: float = 1) -> Vector:
        return Vector(math.cos(angle) * radius, math.sin(angle) * radius)

    def rotated(self, angle: float) -> Vector:
        return Vector(
            math.cos(angle) * self.x - math.sin(angle) * self.y,
            math.sin(angle) * self.x + math.cos(angle) * self.y,
        )

    def rotated90(self) -> Vector:
        return Vector(-self.y, self.x)

    def __iter__(self):
        return iter((self.x, self.y))

    def __getitem__(self, i: int):
        if i == 0:
            return self.x
        elif i == 1:
            return self.y

        raise IndexError

    def __add__(self, other: Vector):
        return Vector(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Vector):
        return Vector(self.x - other.x, self.y - other.y)

    def __mul__(self, factor: float):
        return factor * self

    def __rmul__(self, factor: float):
        if isinstance(factor, Vector):
            return NotImplemented
        else:
            return Vector(factor * self.x, factor * self.y)

    def __truediv__(self, divisor: float):
        if isinstance(divisor, Vector):
            return NotImplemented
        else:
            return Vector(self.x / divisor, self.y / divisor)

    def __rtruediv__(self, dividend: float):
        if isinstance(dividend, Vector):
            return NotImplemented
        else:
            return Vector(dividend / self.x, dividend / self.y)

    def __neg__(self):
        return -1 * self

    def __bool__(self):
        return self.x or self.y

    def dot(self, other: Vector) -> float:
        return self.x * other.x + self.y * other.y

    def squared_length(self) -> float:
        return self.x * self.x + self.y * self.y

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def norm(self):
        return self.length()

    def normalized(self):
        norm = self.length()
        if norm == 0:
            return Vector(0, 0)
        else:
            return Vector(self.x / norm, self.y / norm)

    def map(self, func: typing.Callable[[float], float]) -> Vector:
        return Vector(func(self.x), func(self.y))

    def copy(self) -> Vector:
        return Vector(self.x, self.y)

    def __repr__(self):
        return f"Vector({self.x}, {self.y})"

    def __format__(self, format_spec):
        return f"Vector({self.x:{format_spec}}, {self.y:{format_spec}})"
