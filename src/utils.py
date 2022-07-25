import math
import random
import copy


def foldr(f, a, xs):
    for x in xs:
        a = f(a, x)
    return a


def foldr1(f, xs):
    return foldr(f, xs[0], xs[1:])


def fmap(f, xs):
    return [f(x) for x in xs]


def flatten(nested):
    for xs in nested:
        for x in xs:
            yield x


def shuffled(xs: list) -> list:
    ys = copy.copy(xs)
    random.shuffle(ys)
    return ys


def bump(r) -> float:
    return math.exp(1 / (r ** 2 - 1)) if r < 1 else 0


def pop_split(xs, i):
    x = xs.pop(i)
    return (x, xs)
