from __future__ import annotations

from .vector import *
from . import world

__all__ = [
    "Physical",
]


class Physical:
    def __init__(self, id_: str, position: Vector, velocity: Vector,
                 mass: float, radius: float, friction: float):
        self.id = id_

        self.position = position
        self.velocity = velocity
        self.acceleration = Vector(0, 0)

        self.mass = mass
        self.radius = radius

        self.friction = friction

    def update_acceleration(self, world_: world.World):
        """Update self.acceleration. Ideally, that is a unit vector. This is supposed to be overridden by subclasses."""
        pass

    def thrust(self) -> float:
        """Return the thrust, i.e. length of applied acceleration. This is supposed to be overridden by subclasses."""
        return 1

    def move(self, world_: world.World):
        # friction
        self.velocity *= 1 - self.friction

        # acceleration
        self.update_acceleration(world_)
        self.velocity += self.acceleration * self.thrust()

        # displacement
        self.position += self.velocity

        world_.normalize_position(self.position)

    def collision(self, other: Physical, world_: world.World):
        # elastic collision
        min_dist = self.radius + other.radius

        d = world_.torus_difference(self.position, other.position)

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
