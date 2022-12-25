"""This file contains scaffolding classes that represent the gRPC types. This is useful for type hinting."""

import dataclasses


@dataclasses.dataclass
class _Vector:
    x: float
    y: float


@dataclasses.dataclass
class _CampStatus:
    id: str
    player_id: str
    position: _Vector
    width: float
    height: float


@dataclasses.dataclass
class _PhysicalStatus:
    id: str
    acceleration: _Vector
    position: _Vector
    velocity: _Vector


@dataclasses.dataclass
class _SeekerStatus:
    super: _PhysicalStatus
    player_id: str
    magnet: float
    target: _Vector
    disable_counter: float


@dataclasses.dataclass
class _GoalStatus:
    super: _PhysicalStatus
    camp_id: str
    time_owned: float


@dataclasses.dataclass
class _EntityReply:
    seekers: dict[str, _SeekerStatus]
    goals: dict[str, _GoalStatus]
    passed_playtime: float


@dataclasses.dataclass
class _PlayerStatus:
    id: str
    camp_id: str
    seeker_ids: list[str]
    color: str
    score: int


@dataclasses.dataclass
class _PlayerReply:
    players: dict[str, _PlayerStatus]
    camps: dict[str, _CampStatus]
