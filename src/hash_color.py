import random


# assign a nice color to a string by hashing it
def string_hash_color(string):
    original_state = random.getstate()
    random.seed(string.encode())
    hue = random.uniform(0, 1)
    random.setstate(original_state)
    return hue_color(hue)


# make a nice color from a hue given as a number between 0 and 1
def hue_color(hue):
    colors = [
        [255, 0, 0]
        , [255, 255, 0]
        , [0, 255, 0]
        , [0, 255, 255]
        , [0, 0, 255]
        , [255, 0, 255]
        , [255, 0, 0]]
    n = len(colors) - 1
    i = int(hue * n)
    i = min(i, n - 1)
    return interpolate_color(colors[i], colors[i + 1], hue * n - i)


def interpolate_color(c1, c2, t):
    return [(1 - t) * a + t * b for a, b in zip(c1, c2)]
