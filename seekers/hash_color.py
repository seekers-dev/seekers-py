import random

import typing

Color = typing.Union[tuple[int, int, int], list[int]]


def string_hash_color(string) -> Color:
    """Assign a nice color to a string by hashing it."""
    original_state = random.getstate()
    random.seed(string.encode())
    hue = random.uniform(0, 1)
    random.setstate(original_state)
    return list(map(int, hue_color(hue)))


def hue_color(hue: float) -> Color:
    """Make a nice color from a hue given as a number between 0 and 1."""
    colors = [
        [255, 0, 0],
        [255, 255, 0],
        [0, 255, 0],
        [0, 255, 255],
        [0, 0, 255],
        [255, 0, 255],
        [255, 0, 0]
    ]
    n = len(colors) - 1
    i = int(hue * n)
    i = min(i, n - 1)
    return interpolate_color(colors[i], colors[i + 1], hue * n - i)


def interpolate_color(c1: Color, c2: Color, t: float) -> Color:
    return [int((1 - t) * a + t * b) for a, b in zip(c1, c2)]


def color_distance(c1: Color, c2: Color) -> float:
    return abs(c1[0] - c2[0])**2 + abs(c1[1] - c2[1])**2 + abs(c1[2] - c2[2])**2


def pick_new(old: list[Color], new: Color, threshold: float = 200) -> Color:
    """Pick a new color that is sufficiently different from the old ones."""
    if len(old) == 0:
        return new

    scatter = 2 * threshold / 3

    _new = new
    max_distance = 0
    max_distance_color = new
    for _ in range(10):
        d = min(color_distance(old_color, _new) for old_color in old)
        if d >= threshold:
            return _new

        if d > max_distance:
            max_distance = d
            max_distance_color = _new

        _new = tuple(map(
            lambda x: min(255, max(0, int(x + random.uniform(-scatter, scatter)))),
            new
        ))

    return max_distance_color
