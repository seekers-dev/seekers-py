from seekers.debug_drawing import *


def decide(own_seekers, other_seekers, all_seekers, goals, other_players, camp, camps, world, passed_time):
    draw_circle(world.middle(), 100, color=(255, 0, 0), width=0)
    draw_circle(world.middle(), 10, color=(0, 255, 0), width=3)

    draw_line(own_seekers[0].position, own_seekers[1].position)

    return own_seekers