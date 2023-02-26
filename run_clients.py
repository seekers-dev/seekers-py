from multiprocessing import Process
import argparse
import os
import sys
import logging
from collections import defaultdict

import seekers.grpc


def run_ai(filepath: str, name: str, args: argparse.Namespace):
    logging.basicConfig(
        level=args.loglevel, style="{", format=f"[{name.ljust(18)}] {{levelname}}: {{message}}",
        stream=sys.stdout, force=True
    )

    ai = seekers.LocalPlayerAi.from_file(filepath)

    try:
        seekers.grpc.GrpcSeekersClient(name, ai, args.address).run()
    except seekers.grpc.ServerUnavailableError:
        logging.error(f"Server at {args.address!r} unavailable. "
                      f"Check that it's running and that the address is correct.")
    except seekers.grpc.GameFullError:
        logging.error("Game already full.")


def main():
    parser = argparse.ArgumentParser(description='Run python seekers AIs as gRPC clients.')
    parser.add_argument("-address", "-a", type=str, default="localhost:7777",
                        help="Address of the server. (default: localhost:7777)")
    parser.add_argument("-loglevel", "-log", "-l", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--careful", action="store_true", help="Enable careful mode for the gRPC clients. This will "
                                                               "raise an exception and stop the client when errors "
                                                               "occur that otherwise would be ignored.")
    parser.add_argument("ai_files", type=str, nargs="+", help="Paths to the AIs.")

    args = parser.parse_args()

    _AIS = defaultdict(int)

    def ai_name(filepath: str) -> str:
        name, _ = os.path.splitext(filepath)

        _AIS[name] += 1

        if _AIS[name] > 1:
            name += f"_{_AIS[name]}"

        return name

    processes = []

    for arg in args.ai_files:
        name = ai_name(arg)

        processes.append(
            Process(
                target=run_ai,
                args=(arg, name, args),
                daemon=True,
                name=f"AI {name!r}"
            )
        )

    for process in processes:
        process.start()

    for process in processes:
        process.join()


if __name__ == '__main__':
    main()
