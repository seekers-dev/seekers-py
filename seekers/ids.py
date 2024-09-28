from __future__ import annotations

import collections
import random

__all__ = [
    "get_id",
]

_IDS = collections.defaultdict(list)


def get_id(obj: str):
    rng = random.Random(obj)

    while (id_ := rng.randint(0, 2 ** 32)) in _IDS[obj]:
        ...

    _IDS[obj].append(id_)

    return f"py-seekers.{obj}@{id_}"
