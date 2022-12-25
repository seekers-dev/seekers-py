# function definition
def foo(x):
    return foo(abs(x) - 1) if x != 0 else 0


def decide(seekers, other_seekers, all_seekers, goals, otherPlayers, own_camp, camps, world, tick):
    """This function gets called every tick the game processes;
    Only the target and the magnet state of the seekers you returned affect the game"""
    # print(tick)
    # print(foo(tick))

    for i, s in enumerate(seekers):  # i is the index of the seeker and s is the seeker object
        g = goals[i]  # selects the goal with the same index as the seeker
        dist = world.torus_distance(g.position,
                                    s.position)  # calculates the distance of the seeker to the selected goal
        if dist < 40:  # decides if seeker is close enough to the goal
            # if the seeker is close enough he enables his magnet and aims for the own camp
            s.set_magnet_attractive()
            s.target = own_camp.position
        else:
            # otherwise it disables its magnet and aims for the goal
            s.disable_magnet()
            s.target = g.position
    return seekers
