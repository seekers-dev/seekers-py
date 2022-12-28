from seekers import *


def decide(own_seekers: list[Seeker], other_seekers: list[Seeker], all_seekers: list[Seeker], goals: list[Goal],
           other_players: list[Player], own_camp: Camp, camps: list[Camp], world: World, passed_time: float):
    s = own_seekers[0]
    goal = world.nearest_goal(s.position, goals)
    dist = world.torus_distance(s.position, goal.position)

    if dist < 90:
        # print("** AN")
        s.set_magnet_attractive()
        s.target = own_camp.position
    else:
        # print("** AUS")
        s.disable_magnet()
        s.target = goal.position

    return own_seekers
