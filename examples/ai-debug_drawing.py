from seekers import *
from seekers.debug_drawing import *


def decide(own_seekers: list[Seeker], other_seekers: list[Seeker], all_seekers: list[Seeker], goals: list[Goal],
           other_players: list[Player], own_camp: Camp, camps: list[Camp], world: World, passed_time: float):
    draw_circle(world.middle(), 100, color=(255, 0, 0), width=0)
    draw_circle(world.middle(), 10, color=(0, 255, 0), width=3)

    draw_line(own_seekers[0].position, own_seekers[1].position)

    return own_seekers
