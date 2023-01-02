"""This file contains scaffolding classes that represent select gRPC types. This is useful for type hinting."""


class Vector:
    x: float
    y: float


class CampStatus:
    id: str
    player_id: str
    position: Vector
    width: float
    height: float


class PhysicalStatus:
    id: str
    acceleration: Vector
    position: Vector
    velocity: Vector


class SeekerStatus:
    super: PhysicalStatus
    player_id: str
    magnet: float
    target: Vector
    disable_counter: float


class GoalStatus:
    super: PhysicalStatus
    camp_id: str
    time_owned: float


class PlayerStatus:
    id: str
    seeker_ids: list[str]
    camp_id: str
    name: str
    color: str
    score: int


class StatusReply:
    players: list[PlayerStatus]
    camps: list[CampStatus]
    seekers: list[SeekerStatus]
    goals: list[GoalStatus]

    passed_playtime: float


class JoinReply:
    token: str
    id: str
    version: str
