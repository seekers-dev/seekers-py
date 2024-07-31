import math

from .config import Config
from seekers.vector import Vector
from .physical import Physical
from .world import World


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
    def __init__(self, owner, disabled_time: float, magnet_slowdown: float, base_thrust: float, *args,
                 **kwargs):
        Physical.__init__(self, *args, **kwargs)

        self.target = self.position.copy()
        self.disabled_counter = 0
        self.magnet = Magnet()

        self.owner = owner
        self.disabled_time = disabled_time
        self.magnet_slowdown = magnet_slowdown
        self.base_thrust = base_thrust

    @classmethod
    def from_config(cls, owner, id_: str, position: Vector, config: Config):
        return cls(
            owner=owner,
            disabled_time=config.seeker_disabled_time,
            magnet_slowdown=config.seeker_magnet_slowdown,
            base_thrust=config.seeker_thrust,
            id_=id_,
            position=position,
            velocity=Vector(),
            mass=config.seeker_mass,
            radius=config.seeker_radius,
            friction=config.seeker_friction,
        )

    def thrust(self) -> float:
        magnet_slowdown_factor = self.magnet_slowdown if self.magnet.is_on() else 1

        return self.base_thrust * magnet_slowdown_factor

    @property
    def is_disabled(self):
        return self.disabled_counter > 0

    def disable(self):
        self.disabled_counter = self.disabled_time

    def disabled(self):
        return self.is_disabled

    def magnetic_force(self, world: World, pos: Vector) -> Vector:
        def bump(difference) -> float:
            return math.exp(1 / (difference ** 2 - 1)) if difference < 1 else 0

        torus_diff = world.torus_difference(self.position, pos)
        torus_diff_len = torus_diff.length()

        r = torus_diff_len / world.diameter()
        direction = (torus_diff / torus_diff_len) if torus_diff_len != 0 else Vector(0, 0)

        if self.is_disabled:
            return Vector(0, 0)

        return - direction * (self.magnet.strength * bump(r * 10))

    def update_acceleration(self, world: World):
        if self.disabled_counter == 0:
            self.acceleration = world.torus_direction(self.position, self.target)
        else:
            self.acceleration = Vector(0, 0)

    def magnet_effective(self):
        """Return whether the magnet is on and the seeker is not disabled."""
        return self.magnet.is_on() and not self.is_disabled

    def collision(self, other: "Seeker", world: World):
        if not (self.magnet_effective() or other.magnet_effective()):
            self.disable()
            other.disable()

        if self.magnet_effective():
            self.disable()
        if other.magnet_effective():
            other.disable()

        Physical.collision(self, other, world)

    # methods below are left in for compatibility
    def set_magnet_repulsive(self):
        self.magnet.set_repulsive()

    def set_magnet_attractive(self):
        self.magnet.set_attractive()

    def disable_magnet(self):
        self.magnet.disable()

    def set_magnet_disabled(self):
        self.magnet.disable()

    @property
    def max_speed(self):
        return self.base_thrust / self.friction
