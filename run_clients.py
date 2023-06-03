import argparse
import os
import sys
import logging

import seekers.grpc


def run_ai(args: argparse.Namespace):
    name, _ = os.path.splitext(args.ai_file)

    logging.basicConfig(
        level=args.loglevel, style="{", format=f"[{name.ljust(18)}] {{levelname}}: {{message}}",
        stream=sys.stdout, force=True
    )

    ai = seekers.LocalPlayerAi.from_file(args.ai_file)

    hosting_client = seekers.grpc.GrpcHostingClient(args.address)

    # game = hosting_client.list_games()[0]

    color = seekers.colors.string_hash_color(name) if ai.preferred_color is None else ai.preferred_color

    join_response = hosting_client.join(name=name, color=color)

    service_wrapper = seekers.grpc.GrpcSeekersServiceWrapper(
        token=join_response.token,
        player_id=join_response.player_id,
        address="localhost:7777"
    )

    try:
        seekers.grpc.GrpcSeekersClient(service_wrapper, ai).run()
    except seekers.grpc.ServerUnavailableError:
        logging.error(f"Server at {args.address!r} unavailable. "
                      f"Check that it's running and that the address is correct.")
    except seekers.grpc.GameFullError:
        logging.error("Game already full.")


def main():
    parser = argparse.ArgumentParser(description='Run python seekers AIs as gRPC clients.')
    parser.add_argument("-address", "-a", type=str, default="localhost:7777",
                        help="Address of the server. (default: localhost:7777)")
    parser.add_argument("-game_id", "-game", "-g", type=str, default=None)
    parser.add_argument("-loglevel", "-log", "-l", type=str, default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--careful", action="store_true", help="Enable careful mode for the gRPC clients. This will "
                                                               "raise an exception and stop the client when errors "
                                                               "occur that otherwise would be ignored.")
    parser.add_argument("ai_file", type=str, help="Paths to the AIs.")

    run_ai(parser.parse_args())


if __name__ == '__main__':
    main()
