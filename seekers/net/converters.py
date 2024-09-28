"""Functions that convert between the gRPC types and the internal types."""
import dataclasses
from collections import defaultdict

from seekers.api.org.seekers.api.camp_pb2 import Camp as CampAPI
from seekers.api.org.seekers.api.goal_pb2 import Goal as GoalAPI
from seekers.api.org.seekers.api.physical_pb2 import Physical as PhysicalAPI
from seekers.api.org.seekers.api.player_pb2 import Player as PlayerAPI
from seekers.api.org.seekers.api.seeker_pb2 import Seeker as SeekerAPI
from seekers.api.org.seekers.api.vector2d_pb2 import Vector2D as Vector2DAPI
from seekers.api.org.seekers.api.seekers_pb2 import Section as SectionAPI

from seekers import Camp, Player, Goal, Physical, Config
from seekers.game.vector import Vector
from seekers.game.seeker import Seeker

import seekers.game as game

def vector_to_seekers(vector: Vector2DAPI) -> Vector:
    return game.Vector(vector.x, vector.y)


def vector_to_grpc(vector: Vector) -> Vector2DAPI:
    return Vector2DAPI(x=vector.x, y=vector.y)


def seeker_to_seekers(seeker: SeekerAPI, owner: Player, config: Config) -> SeekerAPI:
    out = game.Seeker(
        id_=seeker.physical.id,
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


def physical_to_grpc(physical: Physical) -> PhysicalAPI:
    return PhysicalAPI(
        id=physical.id,
        acceleration=vector_to_grpc(physical.acceleration),
        velocity=vector_to_grpc(physical.velocity),
        position=vector_to_grpc(physical.position)
    )


def seeker_to_grpc(seeker: Seeker) -> SeekerAPI:
    return SeekerAPI(
        super=physical_to_grpc(seeker),
        player_id=seeker.owner.id,
        magnet=seeker.magnet.strength,
        target=vector_to_grpc(seeker.target),
        disable_counter=seeker.disabled_counter
    )


def goal_to_seekers(goal: GoalAPI, camps: dict[str, Camp], config: Config) -> Goal:
    out = Goal(
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


def goal_to_grpc(goal: Goal) -> GoalAPI:
    return GoalAPI(
        super=physical_to_grpc(goal),
        camp_id=goal.owner.camp.id if goal.owner else "",
        time_owned=goal.time_owned
    )


def color_to_seekers(color: str) -> tuple[int, int, int]:
    # noinspection PyTypeChecker
    return tuple(int(color[i:i + 2], base=16) for i in (2, 4, 6))


def color_to_grpc(color: tuple[int, int, int]):
    return f"0x{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def player_to_seekers(player: PlayerAPI) -> Player:
    out = Player(
        id=player.id,
        name=str(player.id),
        score=player.score,
        seekers={}
    )

    return out


def player_to_grpc(player: Player) -> PlayerAPI:
    return PlayerAPI(
        id=player.id,
        seeker_ids=[seeker.id for seeker in player.seekers.values()],
        # name=player.name,
        camp_id=player.camp.id,
        # color=color_to_grpc(player.color),
        score=player.score,
    )


def camp_to_seekers(camp: CampAPI, owner: Player) -> Camp:
    out = Camp(
        id=camp.id,
        owner=owner,
        position=vector_to_seekers(camp.position),
        width=camp.width,
        height=camp.height
    )

    return out


def camp_to_grpc(camp: Camp) -> CampAPI:
    return CampAPI(
        id=camp.id,
        player_id=camp.owner.id,
        position=vector_to_grpc(camp.position),
        width=camp.width,
        height=camp.height
    )


def config_to_grpc(config: Config) -> list[SectionAPI]:
    out = defaultdict(dict)

    for attribute_name, value in dataclasses.asdict(config).items():
        section, key = config.get_section_and_key(attribute_name)

        out[section][key] = config.value_to_str(value)

    return [SectionAPI(name=section, entries=data) for section, data in out.items()]


def config_to_seekers(config: list[SectionAPI], ignore_missing: bool = True) -> Config:
    config_field_types = {field.name: field.type for field in dataclasses.fields(Config) if field.init}

    all_fields_as_none = {k: None for k in config_field_types}

    kwargs = {}
    for section in config:
        for key, value in section.entries.items():
            field_name = Config.get_attribute_name(section.name, key)

            if field_name not in config_field_types:
                if not ignore_missing:
                    raise KeyError(section.name)
                else:
                    continue

            kwargs[field_name] = Config.value_from_str(value, config_field_types[field_name])

    return Config(**(all_fields_as_none | kwargs))
