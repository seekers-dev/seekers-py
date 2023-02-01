import random
import typing
import colorsys

Color = typing.Union[tuple[int, int, int], list[int]]


def string_hash_hue(string: str):
    """Return a random number between 0 and 1 seeded by the string."""
    rng = random.Random(string.encode())
    return rng.uniform(0, 1)


def string_hash_color(string: str) -> Color:
    """Return a random color seeded by the string."""
    return from_hue(string_hash_hue(string))


def interpolate_color(c1: Color, c2: Color, t: float) -> Color:
    return [int((1 - t) * a + t * b) for a, b in zip(c1, c2)]


def hue_distance(h1: float, h2: float) -> float:
    """Return the distance between two hues."""
    return min(abs(h1 - h2), abs(h1 - h2 + 1), abs(h1 - h2 - 1))


def get_hue(color: Color) -> float:
    return colorsys.rgb_to_hsv(*[v / 255 for v in color])[0]


def from_hue(hue: float) -> Color:
    return list(map(lambda v: int(v * 255), colorsys.hsv_to_rgb(hue, 1, 1)))


def pick_new(old: list[Color], preferred_color: Color, threshold: float = 200) -> Color:
    """Pick a new color that is sufficiently different from the old ones."""
    rng = random.Random()

    old_hues = [get_hue(color) for color in old]

    if len(old) == 0:
        return preferred_color

    preferred_hue = get_hue(preferred_color)
    max_distance = 0
    max_distance_hue = preferred_hue
    for _ in range(10):
        d = min(hue_distance(preferred_hue, old_hue) for old_hue in old_hues)
        if d >= threshold:
            return from_hue(preferred_hue)

        if d > max_distance:
            max_distance = d
            max_distance_hue = preferred_hue

        scatter = 2 * (threshold - d)
        preferred_hue = min(1, max(0, preferred_hue + rng.uniform(-scatter, scatter)))

    return from_hue(max_distance_hue)
