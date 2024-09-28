"""Functions that convert between the gRPC types and the internal types."""
import dataclasses
from collections import defaultdict

from seekers.api.org.seekers.api.camp_pb2 import Camp
from seekers.api.org.seekers.api.goal_pb2 import Goal
from seekers.api.org.seekers.api.physical_pb2 import Physical
from seekers.api.org.seekers.api.player_pb2 import Player
from seekers.api.org.seekers.api.seeker_pb2 import Seeker
from seekers.api.org.seekers.api.vector2d_pb2 import Vector2D
from seekers.api.org.seekers.api.seekers_pb2 import Section

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
        friction=config.seeker_friction,
        base_thrust=config.seeker_thrust,
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
        friction=config.seeker_friction,
        base_thrust=config.seeker_thrust,
        scoring_time=config.goal_scoring_time
    )

    out.time_owned = goal.time_owned
    if goal.camp_id in camps:
        out.owner = camps[goal.camp_id].owner
    else:
        out.owner = None

    return out


def goal_to_grpc(goal: seekers.Goal) -> Goal:
    return Goal(
        super=physical_to_grpc(goal),
        camp_id=goal.owner.camp.id if goal.owner else "",
        time_owned=goal.time_owned
    )


def color_to_seekers(color: str) -> tuple[int, int, int]:
    # noinspection PyTypeChecker
    return tuple(int(color[i:i + 2], base=16) for i in (2, 4, 6))


def color_to_grpc(color: tuple[int, int, int]):
    return f"0x{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def player_to_seekers(player: Player) -> seekers.Player:
    out = seekers.Player(
        id=player.id,
        name=str(player.id),
        score=player.score,
        seekers={}
    )

    return out


def player_to_grpc(player: seekers.Player) -> Player:
    return Player(
        id=player.id,
        seeker_ids=[seeker.id for seeker in player.seekers.values()],
        # name=player.name,
        camp_id=player.camp.id,
        # color=color_to_grpc(player.color),
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


def config_to_grpc(config: seekers.Config) -> list[Section]:
    out = defaultdict(dict)

    for attribute_name, value in dataclasses.asdict(config).items():
        section, key = config.get_section_and_key(attribute_name)

        out[section][key] = config.value_to_str(value)

    return [Section(name=section, entries=data) for section, data in out.items()]


def config_to_seekers(config: list[Section], ignore_missing: bool = True) -> seekers.Config:
    config_field_types = {field.name: field.type for field in dataclasses.fields(seekers.Config) if field.init}

    all_fields_as_none = {k: None for k in config_field_types}

    kwargs = {}
    for section in config:
        for key, value in section.entries.items():
            field_name = seekers.Config.get_attribute_name(section.name, key)

            if field_name not in config_field_types:
                if not ignore_missing:
                    raise KeyError(section.name)
                else:
                    continue

            kwargs[field_name] = seekers.Config.value_from_str(value, config_field_types[field_name])

    return seekers.Config(**(all_fields_as_none | kwargs))
