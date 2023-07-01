"""Functions that convert between the gRPC types and the internal types."""
from seekers.grpc.stubs.org.seekers.game.camp_pb2 import Camp
from seekers.grpc.stubs.org.seekers.game.goal_pb2 import Goal
from seekers.grpc.stubs.org.seekers.game.physical_pb2 import Physical
from seekers.grpc.stubs.org.seekers.game.player_pb2 import Player
from seekers.grpc.stubs.org.seekers.game.seeker_pb2 import Seeker
from seekers.grpc.stubs.org.seekers.game.vector2d_pb2 import Vector2D

import seekers


def vector_to_seekers(vector: Vector2D) -> seekers.Vector:
    return seekers.Vector(vector.x, vector.y)


def vector_to_grpc(vector: seekers.Vector) -> Vector2D:
    return Vector2D(x=vector.x, y=vector.y)


def seeker_to_seekers(seeker: Seeker, owner: seekers.Player, config: seekers.Config) -> seekers.Seeker:
    out = seekers.Seeker(
        id_=seeker.super.id,
        owner=owner,
        position=vector_to_seekers(seeker.super.position),
        velocity=vector_to_seekers(seeker.super.velocity),
        mass=config.seeker_mass,
        radius=config.seeker_radius,
        friction=config.physical_friction,
        base_thrust=config.seeker_thrust,
        experimental_friction=config.flags_experimental_friction,
        disabled_time=config.seeker_disabled_time,
        magnet_slowdown=config.seeker_magnet_slowdown
    )

    out.magnet.strength = seeker.magnet
    out.target = vector_to_seekers(seeker.target)
    out.disable_counter = seeker.disable_counter

    return out


def physical_to_grpc(physical: seekers.Physical) -> Physical:
    return Physical(
        id=physical.id,
        acceleration=vector_to_grpc(physical.acceleration),
        velocity=vector_to_grpc(physical.velocity),
        position=vector_to_grpc(physical.position)
    )


def seeker_to_grpc(seeker: seekers.Seeker) -> Seeker:
    return Seeker(
        super=physical_to_grpc(seeker),
        player_id=seeker.owner.id,
        magnet=seeker.magnet.strength,
        target=vector_to_grpc(seeker.target),
        disable_counter=seeker.disabled_counter
    )


def goal_to_seekers(goal: Goal, camps: dict[str, seekers.Camp], config: seekers.Config) -> seekers.Goal:
    out = seekers.Goal(
        id_=goal.super.id,
        position=vector_to_seekers(goal.super.position),
        velocity=vector_to_seekers(goal.super.velocity),
        mass=config.goal_mass,
        radius=config.goal_radius,
        friction=config.physical_friction,
        base_thrust=config.seeker_thrust,
        experimental_friction=config.flags_experimental_friction,
        scoring_time=config.goal_scoring_time
    )

    out.owned_for = goal.time_owned
    if goal.camp_id in camps:
        out.owner = camps[goal.camp_id].owner
    else:
        out.owner = None

    return out


def goal_to_grpc(goal: seekers.Goal) -> Goal:
    return Goal(
        super=physical_to_grpc(goal),
        camp_id=goal.owner.camp.id if goal.owner else "",
        time_owned=goal.owned_for
    )


def color_to_seekers(color: str) -> tuple[int, int, int]:
    # noinspection PyTypeChecker
    return tuple(int(color[i:i + 2], base=16) for i in (2, 4, 6))


def color_to_grpc(color: tuple[int, int, int]):
    return f"0x{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def player_to_seekers(player: Player) -> seekers.Player:
    out = seekers.Player(
        id=player.id,
        name=player.name,
        score=player.score,
        seekers={}
    )
    out.color = color_to_seekers(player.color),

    return out


def player_to_grpc(player: seekers.Player) -> Player:
    return Player(
        id=player.id,
        seeker_ids=[seeker.id for seeker in player.seekers.values()],
        name=player.name,
        camp_id=player.camp.id,
        color=color_to_grpc(player.color),
        score=player.score,
    )


def camp_to_seekers(camp: Camp, owner: seekers.Player) -> seekers.Camp:
    out = seekers.Camp(
        id=camp.id,
        owner=owner,
        position=vector_to_seekers(camp.position),
        width=camp.width,
        height=camp.height
    )

    return out


def camp_to_grpc(camp: seekers.Camp) -> Camp:
    return Camp(
        id=camp.id,
        player_id=camp.owner.id,
        position=vector_to_grpc(camp.position),
        width=camp.width,
        height=camp.height
    )
