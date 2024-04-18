import os
import threading
import unittest

from seekers import Config
from seekers.seekers_types import LocalPlayerAi
from seekers.game import SeekersGame
from seekers.grpc.client import GrpcSeekersServiceWrapper, GrpcSeekersClient


class TestSeekers(unittest.TestCase):
    def test_seekers(self):
        """Test that a SeekersGame can be created and run without errors."""
        config = Config.from_filepath("config.ini")

        config.global_playtime = 200
        config.global_speed = 20

        game = SeekersGame(
            local_ai_locations=["examples/ai-decide.py", "examples/ai-simple.py"],
            config=config,
            grpc_address=False,
            debug=False,
            print_scores=False
        )

        game.listen()
        game.start()

    def test_speed_consistency(self):
        """Test that the outcome of a game is the same for different speeds."""
        scores = None
        prev_speed = None

        for speed in 1, 1, 10, 10, 20, 40:
            with self.subTest(msg=f"Speed: {speed}", speed=speed):
                new_scores = nogrpc_game(
                    playtime=2000,
                    speed=speed,
                    players=2,
                    seed=42,
                    filepaths=["examples/ai-decide.py", "examples/ai-simple.py"]
                )

                if scores is not None:
                    self.assertEqual(
                        new_scores, scores, msg=f"Outcome at speed {speed} is different from speed {prev_speed}."
                    )

                scores = new_scores
                prev_speed = speed


def start_grpc_client(filepath: str, address: str, joined_event: threading.Event):
    name, _ = os.path.splitext(filepath)

    service_wrapper = GrpcSeekersServiceWrapper(
        address=address
    )

    client = GrpcSeekersClient(
        service_wrapper,
        player_ai=LocalPlayerAi.from_file(filepath),
        careful_mode=True
    )
    client.join(name=name)
    joined_event.set()
    client.run()


def grpc_game(playtime: int, speed: int, players: int, seed: int, filepaths: list[str],
              address: str = "localhost:7778") -> dict[str, int]:
    config = Config.from_filepath("config.ini")

    config.global_fps = 1000
    config.global_playtime = playtime
    config.global_speed = speed
    config.global_wait_for_players = True
    config.global_players = players
    config.global_seed = seed

    game = SeekersGame(
        local_ai_locations=[],
        config=config,
        grpc_address=address,
        debug=True,
        print_scores=False
    )

    game.grpc.start_server()

    processes = []
    for filepath in filepaths:
        event = threading.Event()
        process = threading.Thread(target=start_grpc_client, args=(filepath, address, event))
        process.start()
        processes.append(process)

        event.wait()

    game.listen()
    game.start()

    for process in processes:
        process.join()

    return {player.name: player.score for player in game.players.values()}


def nogrpc_game(playtime: int, speed: int, players: int, seed: int, filepaths: list[str]) -> dict[str, int]:
    config = Config.from_filepath("config.ini")

    config.global_fps = 1000
    config.global_wait_for_players = True
    config.global_playtime = playtime
    config.global_speed = speed
    config.global_players = players
    config.global_seed = seed

    game = SeekersGame(
        local_ai_locations=filepaths,
        config=config,
        grpc_address=False,
        debug=True,
        print_scores=False
    )

    game.start()

    return {player.name: player.score for player in game.players.values()}


class TestGrpc(unittest.TestCase):
    def test_grpc(self):
        """Test that a SeekersGame can be created and a client can connect."""

        grpc_game(
            playtime=200,
            speed=10,
            players=2,
            seed=42,
            filepaths=["examples/ai-decide.py", "examples/ai-simple.py"],
            address="localhost:7778"
        )

    def test_grpc_nogrpc_consistency(self):
        """Test that the outcome of a game is the same for grpc and nogrpc."""
        for seed in 40, 41, 42, 43, 44, 45:
            with self.subTest(msg=f"Seed: {seed}", seed=seed):
                nogrpc_scores = nogrpc_game(
                    playtime=2000,
                    speed=10,
                    players=2,
                    seed=seed,
                    filepaths=["examples/ai-decide.py", "examples/ai-simple.py"]
                )

                grpc_scores = grpc_game(
                    playtime=2000,
                    speed=10,
                    players=2,
                    seed=seed,
                    filepaths=["examples/ai-decide.py", "examples/ai-simple.py"],
                    address="localhost:7778"
                )

                self.assertEqual(grpc_scores, nogrpc_scores,
                                 msg=f"Outcome of gRPC and non-gRPC games with seed {seed} is different.")


if __name__ == "__main__":
    unittest.main()
