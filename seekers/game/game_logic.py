from __future__ import annotations

import typing

from .vector import *
from ..graphics import draw
from . import physical, player, seeker, camp, goal, world

__all__ = [
    "tick",
]


def tick(
    players: typing.Iterable[player.Player],
    camps: list[camp.Camp],
    goals: list[goal.Goal],
    animations: list[draw.Animation],
    world_: world.World
):
    seekers = [s for p in players for s in p.seekers.values()]
    # move and recover seekers
    for s in seekers:
        s.move(world_)
        if s.is_disabled:
            s.disabled_counter -= 1

    # compute magnetic forces and move goals
    for g in goals:
        g.acceleration = Vector(0, 0)
        for s in seekers:
            g.acceleration += s.magnetic_force(world_, g.position)

        g.move(world_)

    # handle collisions
    # noinspection PyTypeChecker
    physicals = seekers + goals
    for i, phys1 in enumerate(physicals):
        j = i + 1
        while j < len(physicals):
            phys2 = physicals[j]

            d = world_.torus_difference(phys2.position, phys1.position).squared_length()

            min_dist = phys1.radius + phys2.radius

            if d < min_dist ** 2:
                if isinstance(phys1, seeker.Seeker) and isinstance(phys2, seeker.Seeker):
                    seeker.Seeker.collision(phys1, phys2, world_)
                else:
                    physical.Physical.collision(phys1, phys2, world_)

            j += 1

    # handle goals and scoring
    for i, g in enumerate(goals):
        for camp_ in camps:
            if g.camp_tick(camp_):
                goal_scored(camp_.owner, i, goals, animations, world_)
                break

    # advance animations
    for i, animation in enumerate(animations):
        animation.age += 1

        if animation.age >= animation.duration:
            animations.pop(i)


def goal_scored(
    player_: player.Player,
    goal_index: int,
    goals: list[goal.Goal],
    animations: list[draw.Animation],
    world_: world.World
):
    player_.score += 1

    goal_ = goals[goal_index]

    animations.append(draw.ScoreAnimation(goal_.position, player_.color, goal_.radius))

    goal_.position = world_.random_position()
    goal_.owner = None
    goal_.time_owned = 0
