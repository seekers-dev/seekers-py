from hash_color import *

import random
import math
import utils
import ctypes
import multiprocessing as mp


class Vector:
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def is_vector(obj) -> bool:
        return isinstance(obj, Vector)

    def __iter__(self):
        return (self.x, self.y).__iter__()

    def __getitem__(self, i):
        if i == 0:
            return self.x
        elif i == 1:
            return self.y
        else:
            raise IndexError

    def __add__(left, right):
        return Vector(left.x + right.x, left.y + right.y)

    def __sub__(left, right):
        return Vector(left.x - right.x, left.y - right.y)

    def __neg__(self):
        return self * (-1)

    def __mul__(self, factor):
        return Vector(self.x * factor, self.y * factor)

    def __rmul__(self, factor):
        return Vector(self.x * factor, self.y * factor)

    def __truediv__(self, divisor):
        return self * (1 / divisor)

    def dot(self, other):
        return (self.x * other.x + self.y * other.y)

    def norm(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalized(self):
        norm = self.norm()
        if (norm == 0):
            return Vector(0, 0)
        else:
            return Vector(self.x / norm, self.y / norm)

    def rotated(self):
        return Vector(-self.y, self.x)

    def fmap(self, f):
        return Vector(f(self.x), f(self.y))


class Physical:
    mass = 1
    friction = 0.02
    max_speed = 5
    base_thrust = max_speed * friction

    def __init__(self, position: Vector, velocity=Vector(0, 0)):
        self.position = Vector(position.x, position.y)
        self.velocity = Vector(velocity.x, velocity.y)
        self.acceleration = Vector(0, 0)

    def move(self, world):
        # friction
        self.velocity.x *= 1 - self.friction
        self.velocity.y *= 1 - self.friction
        # acceleration
        self.update_acceleration(world)
        a = self.acceleration
        self.velocity.x += a.x * self.thrust()
        self.velocity.y += a.y * self.thrust()
        # displacement
        self.position.x += self.velocity.x
        self.position.y += self.velocity.y
        world.normalize_position(self.position)

    def update_acceleration(self, world):
        pass

    def thrust(self):
        return self.base_thrust

    def collision(s, t, world, min_dist):
        # elastic collision
        d = world.torus_difference(s.position, t.position)
        if d.norm() != 0:
            dn = d.normalized()
            dv = t.velocity - s.velocity
            dvdn = dv.dot(dn)
            m = 2 / (s.mass + t.mass)
            if dvdn < 0:
                s.velocity += dn * (m * t.mass * dvdn)
                t.velocity -= dn * (m * s.mass * dvdn)
            ddn = d.dot(dn)
            if ddn < min_dist:
                s.position += dn * (ddn - min_dist)
                t.position -= dn * (ddn - min_dist)


class Goal(Physical):
    mass = 0.5
    radius = 6
    scoring_time = 150
    uid_counter = mp.Value(ctypes.c_int64, 0)

    def __init__(self, position, velocity=Vector(0, 0)):
        Physical.__init__(self, position, velocity)
        self.position = Vector(position.x, position.y)
        self.velocity = Vector(velocity.x, velocity.y)
        self.acceleration = Vector(0, 0)
        self.owner = None
        self.owned_for = 0
        with Goal.uid_counter.get_lock():
            self.uid = Goal.uid_counter.value
            Goal.uid_counter.value += 1

    def update_acceleration(self, world):
        pass

    def camp_tick(self, camp):
        if camp.contains(self.position):
            if self.owner == camp.owner:
                self.owned_for += 1
            else:
                self.owned_for = 0
                self.owner = camp.owner
            return self.owned_for >= self.scoring_time
        else:
            return False


class Magnet:
    def __init__(self, strength=0):
        self.strength = strength

    def is_magnet(obj):
        typ = isinstance(obj, Magnet) and isinstance(obj.strength, int)
        val = 1 >= obj.strength >= -8
        return typ and val

    def is_on(self):
        return not self.strength == 0

    def set_repulsive(self):
        self.strength = -8

    def set_attractive(self):
        self.strength = 1

    def disable(self):
        self.strength = 0


class Seeker(Physical):
    radius = 10
    magnet_slowdown = 0.2
    disabled_time = 250
    alterables = (('target', Vector.is_vector)
                  , ('magnet', Magnet.is_magnet))

    def __init__(self, uid, position, velocity=Vector(0, 0)):
        Physical.__init__(self, position, velocity)
        self.uid = uid
        self.target = self.position
        self.disabled_counter = 0
        self.magnet = Magnet()

    def disabled(self):
        return self.disabled_counter > 0

    def disable(self):
        self.disabled_counter = Seeker.disabled_time

    def update_acceleration(self, world):
        if self.disabled_counter == 0:
            a = world.torus_direction(self.position, self.target)
            self.acceleration = a
        else:
            self.acceleration = Vector(0, 0)

    def thrust(self):
        b = self.magnet_slowdown if self.magnet.is_on() else 1
        return Physical.thrust(self) * b

    def collision(s, t, world, min_dist):
        if s.magnet.is_on():
            s.disable()
            if t.magnet.is_on(): t.disable()
        elif t.magnet.is_on():
            t.disable()
        else:
            s.disable()
            t.disable()
        Physical.collision(s, t, world, min_dist)

    def copy_alterables(src, dest) -> bool:
        for attr, is_valid in Seeker.alterables:
            fallback = getattr(dest, attr)
            val = getattr(src, attr, fallback)
            if is_valid(val):
                setattr(dest, attr, val)
            else:
                return False
        return True

    def set_magnet_repulsive(self):
        self.magnet.set_repulsive()

    def set_magnet_attractive(self):
        self.magnet.set_attractive()

    def disable_magnet(self):
        self.magnet.disable()

    def set_magnet_disabled(self):
        self.magnet.disable()

    def magnetic_force(self, world, pos: Vector) -> Vector:
        r = world.torus_distance(self.position, pos) / world.diameter()
        d = world.torus_direction(self.position, pos)
        return Vector(0, 0) if self.disabled() else - d * (self.magnet.strength * utils.bump(r * 10))


class ScoreAnimation:
    duration = 20

    def __init__(self, position, color):
        self.position = position
        self.age = 0
        self.color = color


class Player:
    def __init__(self, name):
        self.name = name
        self.color = string_hash_color(name)
        self.score = 0
        self.seekers = []


class World:
    def __init__(self, width, height, debug=False):
        self.width = width
        self.height = height
        self.debug_mode = debug

    def normalize_position(self, pos: Vector):
        pos.x -= math.floor(pos.x / self.width) * self.width
        pos.y -= math.floor(pos.y / self.height) * self.height

    def size_vector(self) -> Vector:
        return Vector(self.width, self.height)

    def diameter(self) -> float:
        return self.size_vector().norm()

    def middle(self) -> Vector:
        return self.size_vector() / 2

    def torus_distance(self, left, right) -> Vector:
        def dist1d(l, a, b):
            delta = abs(a - b)
            return min(delta, l - delta)

        return Vector(dist1d(self.width, right.x, left.x)
                      , dist1d(self.height, right.y, left.y)).norm()

    def torus_difference(self, left: Vector, right: Vector) -> Vector:
        def diff1d(l, a, b):
            delta = abs(a - b)
            return b - a if delta < l - delta else a - b

        return Vector(diff1d(self.width, left.x, right.x)
                      , diff1d(self.height, left.y, right.y))

    def torus_direction(self, left: Vector, right: Vector) -> Vector:
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
        return Vector(random.uniform(0, self.width)
                      , random.uniform(0, self.height))

    def gen_camp(self, n, i, player: Player):
        r = self.diameter() / 4
        width = r / 5
        height = r / 5
        mid = self.middle()
        theta = lambda i: 2 * math.pi * i / n
        pos = mid + r * Vector(math.sin(theta(i))
                               , math.cos(theta(i)))
        return Camp(player, pos, width, height)

    def generate_camps(self, players) -> list:
        n = len(players)
        return [self.gen_camp(n, i, p) for i, p in enumerate(players)]


class Camp:
    def __init__(self, owner, position, width, height):
        self.owner = owner
        self.position = position
        self.width = width
        self.height = height

    def contains(self, pos: Vector) -> bool:
        delta = self.position - pos
        return 2 * abs(delta.x) < self.width and 2 * abs(delta.y) < self.height
