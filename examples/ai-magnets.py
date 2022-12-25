def decide(own_seekers, other_seekers, all_seekers, goals, other_players, camp, camps, world, passed_time):
    for i, s in enumerate(own_seekers):
        g = goals[i]
        dist = world.torus_distance(g.position, s.position)
        if dist < 40:
            # print("** AN")
            s.set_magnet_attractive()
            s.target = camp.position
        else:
            # print("** AUS")
            s.disable_magnet()
            s.target = g.position

    return own_seekers
