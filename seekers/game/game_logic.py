import typing

from .player import Player
from .camp import Camp
from .goal import Goal
from .world import World
from seekers.vector import Vector
from .seeker import Seeker
from .physical import Physical
from seekers.draw import ScoreAnimation, Animation


def tick(players: typing.Iterable[Player], camps: list[Camp], goals: list[Goal],
         animations: list[Animation], world: World):
    seekers = [s for p in players for s in p.seekers.values()]
    # move and recover seekers
    for s in seekers:
        s.move(world)
        if s.is_disabled:
            s.disabled_counter -= 1

    # compute magnetic forces and move goals
    for g in goals:
        g.acceleration = Vector(0, 0)
        for s in seekers:
            g.acceleration += s.magnetic_force(world, g.position)

        g.move(world)

    # handle collisions
    # noinspection PyTypeChecker
    physicals = seekers + goals
    for i, phys1 in enumerate(physicals):
        j = i + 1
        while j < len(physicals):
            phys2 = physicals[j]

            d = world.torus_difference(phys2.position, phys1.position).squared_length()

            min_dist = phys1.radius + phys2.radius

            if d < min_dist ** 2:
                if isinstance(phys1, Seeker) and isinstance(phys2, Seeker):
                    Seeker.collision(phys1, phys2, world)
                else:
                    Physical.collision(phys1, phys2, world)

            j += 1

    # handle goals and scoring
    for i, g in enumerate(goals):
        for camp in camps:
            if g.camp_tick(camp):
                goal_scored(camp.owner, i, goals, animations, world)
                break

    # advance animations
    for i, animation in enumerate(animations):
        animation.age += 1

        if animation.age >= animation.duration:
            animations.pop(i)


def goal_scored(player: Player, goal_index: int, goals: list[Goal], animations: list[Animation], world: World):
    player.score += 1

    goal = goals[goal_index]

    animations.append(ScoreAnimation(goal.position, player.color, goal.radius))

    goal.position = world.random_position()
    goal.owner = None
    goal.time_owned = 0
