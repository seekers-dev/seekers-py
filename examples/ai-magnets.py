from seekers import *


def decide(own_seekers: list[Seeker], other_seekers: list[Seeker], all_seekers: list[Seeker], goals: list[Goal],
           other_players: list[Player], own_camp: Camp, camps: list[Camp], world: World, passed_time: float):
    for i, s in enumerate(own_seekers):
        g = goals[i]
        dist = world.torus_distance(g.position, s.position)
        if dist < 40:
            # print("** AN")
            s.set_magnet_attractive()
            s.target = own_camp.position
        else:
            # print("** AUS")
            s.disable_magnet()
            s.target = g.position

    return own_seekers
