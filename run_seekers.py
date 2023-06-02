from __future__ import annotations

import argparse
import sys

# needed for compatibility with python on android
import pygame

pygame.init()

from seekers import *


def parse_config_overrides(overrides: list[str]) -> dict[str, str]:
    parsed = {}

    for override in overrides:
        if "=" not in override:
            raise ValueError(f"Invalid config override {override!r}. "
                             f"Use the form option=value, e.g. global.seed=43")

        option, value = override.split("=", maxsplit=1)

        parsed[option.strip()] = value.strip()

    return parsed


def main():
    parser = argparse.ArgumentParser(description="Run python seekers AIs.")
    parser.add_argument("--nogrpc", action="store_true", help="Don't host a gRPC server.")
    parser.add_argument("--nokill", action="store_true", help="Don't kill the process after the game is over.")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode. This will enable debug drawing.")
    parser.add_argument("-address", "-a", type=str, default="localhost:7777",
                        help="Address of the server. (default: localhost:7777)")
    parser.add_argument("-config", "-c", type=str, default="default_config.ini",
                        help="Path to the config file. (default: default_config.ini)")
    parser.add_argument("-config-override", "-co", action="append",
                        help="Override a config option. Use the form option=value, e.g. global.seed=43")
    parser.add_argument("-loglevel", "-log", "-l", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("ai_files", type=str, nargs="*", help="Paths to the AIs.")

    args = parser.parse_args()

    parsed_config_overrides = parse_config_overrides(args.config_override or [])

    config_dict = Config.from_filepath(args.config).to_properties() | parsed_config_overrides
    try:
        config = Config.from_properties(config_dict)
    except KeyError as e:
        raise ValueError(f"Invalid config option {e.args[0]!r}.") from e

    logging.basicConfig(level=args.loglevel, style="{", format=f"[{{name}}] {{levelname}}: {{message}}",
                        stream=sys.stdout)
    address = args.address if not args.nogrpc else False

    seekers_game = SeekersGame(
        local_ai_locations=args.ai_files,
        config=config,
        grpc_address=address,
        debug=args.debug,
        dont_kill=args.nokill
    )
    seekers_game.listen()
    seekers_game.start()


if __name__ == "__main__":
    main()
