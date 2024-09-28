import argparse
import os
import sys
import logging
import seekers.net.client

from seekers.game.player import LocalPlayerAi


def run_ai(args: argparse.Namespace):
    name, _ = os.path.splitext(args.ai_file)

    logging.basicConfig(
        level=args.loglevel, style="{", format=f"[{name}] {{levelname}}: {{message}}",
        stream=sys.stdout, force=True
    )

    ai = LocalPlayerAi.from_file(args.ai_file)

    service_wrapper = seekers.net.client.GrpcSeekersServiceWrapper(address=args.address)
    client = seekers.net.client.GrpcSeekersClient(service_wrapper, ai, careful_mode=args.careful)

    try:
        client.join(name=name, color=ai.preferred_color)
    except seekers.net.client.ServerUnavailableError:
        logging.error(f"Server at {args.address!r} unavailable. "
                      f"Check that it's running and that the address is correct.")
    except seekers.net.client.GameFullError:
        logging.error("Game already full.")
    else:
        logging.info(f"Joined game with id={client.player_id!r}.")
        client.run()


def main():
    parser = argparse.ArgumentParser(description='Run a Python Seekers AI as a gRPC client.')
    parser.add_argument("--address", "-a", type=str, default="localhost:7777",
                        help="Address of the Seekers game. (default: localhost:7777)")
    parser.add_argument("--loglevel", "--log", "-l", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--careful", action="store_true", help="Enable careful mode for the gRPC clients. This will "
                                                               "raise an exception and stop the client when errors "
                                                               "occur that otherwise would be ignored.")
    parser.add_argument("ai_file", type=str, help="Path to the AI.")

    run_ai(parser.parse_args())


if __name__ == '__main__':
    main()
