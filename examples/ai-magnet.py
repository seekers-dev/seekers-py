#bot

s = seekers[0]
goal = world.nearest_goal(s.position,goals)
dist = world.torus_distance(s.position,goal.position)

if dist < 90:
    # print("** AN")
    s.set_magnet_attractive()
    s.target = own_camp.position
else:
    # print("** AUS")
    s.disable_magnet()
    s.target = goal.position
