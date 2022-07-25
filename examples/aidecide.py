from seekers_types import *

tick = 0


def foo(x):
    return foo(abs(x) - 1) if x != 0 else 0


def decide(seekers, other_seekers, all_seekers, goals, otherPlayers, own_camp, camps, world):
    global tick
    tick += 1
    # print(tick)
    # print(foo(tick))

    for i, s in enumerate(seekers):
        g = goals[i]
        dist = world.torus_distance(g.position, s.position)
        if dist < 40:
            s.set_magnet_attractive()
            s.target = own_camp.position
        else:
            s.disable_magnet()
            s.target = g.position
    return seekers
