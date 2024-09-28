from __future__ import annotations

import abc
import typing
import math

import pygame

from .colors import *
from seekers.game.vector import *
from seekers.game.config import *
from seekers.game import player, seeker, camp, goal, world

__all__ = [
    "GameRenderer",
]


class Animation(abc.ABC):
    duration: float

    def __init__(self):
        self.age = 0

    @abc.abstractmethod
    def draw(self, renderer: "GameRenderer"):
        ...


class ScoreAnimation(Animation):
    duration = 40

    def __init__(self, position: Vector, color: Color, radius: float):
        super().__init__()
        self.position = position
        self.color = color
        self.radius = radius

    def draw(self, renderer: "GameRenderer"):
        t = self.age / self.duration
        r = self.radius + 50 * t

        renderer.draw_circle(self.color, self.position, int(r), 1)


class GameRenderer:
    def __init__(self, config: Config, debug_mode: bool = False):
        pygame.font.init()
        self.font = pygame.font.SysFont(["Cascadia Code", "Fira Code", "Consolas", "monospace"], 20, bold=True)
        self.background_color = (0, 0, 30)

        self.player_name_images = {}
        self.screen = None

        self.config = config
        self.debug_mode = debug_mode

        self.world = world.World(self.config.map_width, self.config.map_height)

    def init(self, players: typing.Iterable[player.Player]):
        pygame.init()

        for p in players:
            name = p.name

            if self.debug_mode:
                if isinstance(p, player.GrpcClientPlayer):
                    name += f" (gRPC)"
                elif isinstance(p, player.LocalPlayer):
                    name += f" (local)"

            self.player_name_images[p.id] = self.font.render(name, True, p.color)

        self.screen = pygame.display.set_mode(self.config.map_dimensions)
        pygame.display.set_caption("Seekers")

    def draw_torus(self, func: typing.Callable[[Vector], typing.Any], p1: Vector, p2: Vector):
        func(p1)

        if p2.x > self.config.map_width:
            func(p1 + Vector(-self.config.map_width, 0))

        if p1.x < 0:
            func(p1 + Vector(self.config.map_width, 0))

        if p2.y > self.config.map_height:
            func(p1 + Vector(0, -self.config.map_height))

        if p1.y < 0:
            func(p1 + Vector(0, self.config.map_height))

    def draw_text(self, text: str, color: Color, pos: Vector, center=True):
        dx, dy = self.font.size(text)
        adj_pos = pos - Vector(dx, dy) / 2 if center else pos
        self.screen.blit(self.font.render(text, True, color), tuple(adj_pos))

        # no torus drawing for text

    def draw_circle(self, color: Color, center: Vector, radius: float, width: int = 0):
        r = Vector(radius, radius)

        self.draw_torus(
            lambda pos: pygame.draw.circle(self.screen, color, tuple(pos + r), radius, width),
            center - r, center + r
        )

    def draw_line(self, color: Color, start: Vector, end: Vector, width: int = 1):
        self.draw_torus(
            lambda pos: pygame.draw.line(self.screen, color, tuple(start), tuple(end), width),
            start, end
        )

    def draw_rect(self, color: Color, p1: Vector, p2: Vector, width: int = 0):
        self.draw_torus(
            lambda pos: pygame.draw.rect(self.screen, color, pygame.Rect(tuple(pos), tuple(p2 - p1)), width),
            p1, p2
        )

    def draw(self, players: typing.Collection[player.Player], camps: typing.Iterable[camp.Camp],
             goals: typing.Iterable[goal.Goal],
             animations: list[Animation], clock: pygame.time.Clock):
        # clear screen
        self.screen.fill(self.background_color)

        # draw camps
        for camp_ in camps:
            self.draw_rect(camp_.owner.color, camp_.top_left, camp_.bottom_right, 5)

        # draw goals
        for goal_ in goals:
            color = (
                interpolate_color((255, 255, 255), goal_.owner.color,
                                  min(1.0, (goal_.time_owned / goal_.scoring_time) ** 2))
                if goal_.owner else (255, 255, 255)
            )
            self.draw_circle(color, goal_.position, goal_.radius)

        # draw jet streams
        for player_ in players:
            for seeker_ in player_.seekers.values():
                a = seeker_.acceleration
                if not seeker_.is_disabled and a.squared_length() > 0:
                    self.draw_jet_stream(seeker_, -a)

        # draw seekers
        for player_ in players:
            for i, seeker_ in enumerate(player_.seekers.values()):
                self.draw_seeker(seeker_, player_, str(i))

            for debug_drawing in player_.debug_drawings:
                debug_drawing.draw(self)

        # draw animations
        for animation in animations:
            animation.draw(self)

        # draw information (player's scores, etc.)
        self.draw_information(players, Vector(10, 10), clock)

        # update display
        pygame.display.flip()

    def draw_seeker(self, seeker_: seeker.Seeker, player_: player.Player, debug_str: str):
        color = player_.color
        if seeker_.is_disabled:
            color = interpolate_color(color, [0, 0, 0], 0.5)

        self.draw_circle(color, seeker_.position, seeker_.radius, width=0)
        self.draw_halo(seeker_, color)

        if self.debug_mode:
            self.draw_text(debug_str, (0, 0, 0), seeker_.position)

    def draw_halo(self, seeker_: seeker.Seeker, color: Color):
        adjpos = seeker_.position
        if seeker_.is_disabled:
            return

        mu = abs(math.sin((int(pygame.time.get_ticks() / 30) % 50) / 50 * 2 * math.pi)) ** 2
        self.draw_circle(interpolate_color(color, [0, 0, 0], mu), adjpos, 3 + seeker_.radius, 3)

        if not seeker_.magnet.is_on():
            return

        for offset in 0, 10, 20, 30, 40:
            mu = int(-seeker_.magnet.strength * pygame.time.get_ticks() / 50 + offset) % 50
            self.draw_circle(interpolate_color(color, [0, 0, 0], mu / 50), adjpos, mu + seeker_.radius, 2)

    def draw_jet_stream(self, seeker_: seeker.Seeker, direction: Vector):
        length = seeker_.radius * 3
        adjpos = seeker_.position

        self.draw_line((255, 255, 255), adjpos, adjpos + direction * length)

    def draw_information(self, players: typing.Collection[player.Player], pos: Vector, clock: pygame.time.Clock):
        # draw fps
        fps = int(clock.get_fps())
        self.draw_text(str(fps), (250, 250, 250), pos, center=False)

        dx = Vector(40, 0)
        dy = Vector(0, 30)
        pos += dy
        for p in players:
            self.draw_text(str(p.score), p.color, pos, center=False)
            self.screen.blit(self.player_name_images[p.id], tuple(pos + dx))
            pos += dy

    @staticmethod
    def close():
        pygame.quit()
