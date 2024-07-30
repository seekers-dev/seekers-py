import configparser
import dataclasses
import typing
import random
import collections


_IDS = collections.defaultdict(list)


def get_id(obj: str):
    rng = random.Random(obj)

    while (id_ := rng.randint(0, 2 ** 32)) in _IDS[obj]:
        ...

    _IDS[obj].append(id_)

    return f"py-seekers.{obj}@{id_}"


@dataclasses.dataclass
class Config:
    """Configuration for the Seekers game."""
    global_wait_for_players: bool
    global_playtime: int
    global_seed: int
    global_fps: int
    global_speed: int
    global_players: int
    global_seekers: int
    global_goals: int
    global_color_threshold: float

    map_width: int
    map_height: int

    camp_width: int
    camp_height: int

    seeker_thrust: float
    seeker_magnet_slowdown: float
    seeker_disabled_time: int
    seeker_radius: float
    seeker_mass: float
    seeker_friction: float

    goal_scoring_time: int
    goal_radius: float
    goal_mass: float
    goal_thrust: float
    goal_friction: float

    @property
    def map_dimensions(self):
        return self.map_width, self.map_height

    @classmethod
    def from_file(cls, file) -> "Config":
        cp = configparser.ConfigParser()
        cp.read_file(file)

        return cls(
            global_wait_for_players=cp.getboolean("global", "wait-for-players"),
            global_playtime=cp.getint("global", "playtime"),
            global_seed=cp.getint("global", "seed"),
            global_fps=cp.getint("global", "fps"),
            global_speed=cp.getint("global", "speed"),
            global_players=cp.getint("global", "players"),
            global_seekers=cp.getint("global", "seekers"),
            global_goals=cp.getint("global", "goals"),
            global_color_threshold=cp.getfloat("global", "color-threshold"),

            map_width=cp.getint("map", "width"),
            map_height=cp.getint("map", "height"),

            camp_width=cp.getint("camp", "width"),
            camp_height=cp.getint("camp", "height"),

            seeker_thrust=cp.getfloat("seeker", "thrust"),
            seeker_magnet_slowdown=cp.getfloat("seeker", "magnet-slowdown"),
            seeker_disabled_time=cp.getint("seeker", "disabled-time"),
            seeker_radius=cp.getfloat("seeker", "radius"),
            seeker_mass=cp.getfloat("seeker", "mass"),
            seeker_friction=cp.getfloat("seeker", "friction"),

            goal_scoring_time=cp.getint("goal", "scoring-time"),
            goal_radius=cp.getfloat("goal", "radius"),
            goal_mass=cp.getfloat("goal", "mass"),
            goal_thrust=cp.getfloat("goal", "thrust"),
            goal_friction=cp.getfloat("goal", "friction"),
        )

    @classmethod
    def from_filepath(cls, filepath: str) -> "Config":
        with open(filepath) as f:
            return cls.from_file(f)

    @staticmethod
    def value_to_str(value: bool | float | int | str) -> str:
        if isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, float):
            return f"{value:.2f}"
        else:
            return str(value)

    @staticmethod
    def value_from_str(value: str, type_: typing.Literal["bool", "float", "int", "str"]) -> bool | float | int | str:
        if type_ == "bool":
            return value.lower() == "true"
        elif type_ == "float":
            return float(value)
        elif type_ == "int":
            return int(float(value))
        else:
            return value

    @staticmethod
    def get_section_and_key(attribute_name: str) -> tuple[str, str]:
        """Split an attribute name into the config header name and the key name."""

        section, key = attribute_name.split("_", 1)

        return section, key.replace("_", "-")

    @staticmethod
    def get_attribute_name(section: str, key: str) -> str:
        return f"{section}_{key.replace('-', '_')}"

    @classmethod
    def get_field_type(cls, field_name: str) -> typing.Literal["bool", "float", "int", "str"]:
        field_types = {f.name: f.type for f in dataclasses.fields(cls)}
        return field_types[field_name]

    def import_option(self, section: str, key: str, value: str):
        field_name = self.get_attribute_name(section, key)
        field_type = self.get_field_type(field_name)

        setattr(self, field_name, self.value_from_str(value, field_type))

