def decide(own_seekers, other_seekers, all_seekers, goals, other_players, camp, camps, world, passed_time):
    s = own_seekers[0]
    goal = world.nearest_goal(s.position, goals)
    dist = world.torus_distance(s.position, goal.position)

    if dist < 90:
        # print("** AN")
        s.set_magnet_attractive()
        s.target = camp.position
    else:
        # print("** AUS")
        s.disable_magnet()
        s.target = goal.position

    return own_seekers
