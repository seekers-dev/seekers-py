import pygame
from typing import Iterable, Callable, Union, Collection

from .hash_color import interpolate_color
from .seekers_types import *


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
        self.font = pygame.font.SysFont("monospace", 20, bold=True)
        self.background_color = (0, 0, 30)

        self.player_name_images = {}
        self.screen = None

        self.config = config
        self.debug_mode = debug_mode

    def init(self, players: Iterable[InternalPlayer]):
        for p in players:
            self.player_name_images[p.id] = self.font.render(p.name, True, p.color)

        self.screen = pygame.display.set_mode(self.config.map_dimensions)

    def draw_torus(self, func: Callable[[Vector], typing.Any], p1: Vector, p2: Vector):
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
        self.screen.blit(self.font.render(text, False, color), tuple(adj_pos))

        # no torus drawing for text

    def draw_circle(self, color: Color, center: Vector, radius: float, width: int = 0):
        r = Vector(radius, radius)

        self.draw_torus(
            lambda pos: pygame.draw.circle(self.screen, color, tuple(pos + r), radius, width),
            center - r, center + r
        )

    def draw_line(self, color: Color, start: Vector, end: Vector, width: int = 1):
        d = end - start

        self.draw_torus(
            lambda pos: pygame.draw.line(self.screen, color, tuple(pos), tuple(pos + d), width),
            start, end
        )

    def draw_rect(self, color: Color, p1: Vector, p2: Vector, width: int = 0):
        self.draw_torus(
            lambda pos: pygame.draw.rect(self.screen, color, pygame.Rect(tuple(pos), tuple(p2 - p1)), width),
            p1, p2
        )

    def draw(self, players: Collection[InternalPlayer], camps: Iterable[Camp], goals: Iterable[InternalGoal],
             animations: list[Animation], clock: pygame.time.Clock):
        # clear screen
        self.screen.fill(self.background_color)

        # draw camps
        for camp in camps:
            self.draw_rect(camp.owner.color, camp.top_left, camp.bottom_right, 5)

        # draw goals
        for goal in goals:
            self.draw_circle((205, 0, 250), goal.position, goal.radius)

        # draw jet streams
        for player in players:
            for seeker in player.seekers.values():
                a = seeker.acceleration
                if not seeker.is_disabled and a.squared_length() > 0:
                    self.draw_jet_stream(seeker, -a)

        # draw seekers
        for player in players:
            for i, seeker in enumerate(player.seekers.values()):
                self.draw_seeker(seeker, player, str(i))

            for debug_drawing in player.debug_drawings:
                debug_drawing.draw(self.screen)

        # draw animations
        for animation in animations:
            animation.draw(self)

        # draw information (player's scores, etc.)
        self.draw_information(players, Vector(10, 10), clock)

        # update display
        pygame.display.flip()

    def draw_seeker(self, seeker: InternalSeeker, player: InternalPlayer, debug_str: str):
        color = player.color
        if seeker.is_disabled:
            color = interpolate_color(color, [0, 0, 0], 0.5)

        self.draw_circle(color, seeker.position, seeker.radius, width=0)
        self.draw_halo(seeker, color)

        if self.debug_mode:
            self.draw_text(debug_str, (255, 255, 255), seeker.position)

    def draw_halo(self, seeker: InternalSeeker, color: Color):
        if seeker.is_disabled:
            return

        mu = abs(math.sin((int(pygame.time.get_ticks() / 30) % 50) / 50 * 2 * math.pi)) ** 2
        self.draw_circle(interpolate_color(color, [0, 0, 0], mu), seeker.position, 3 + seeker.radius, 3)

        if not seeker.magnet.is_on():
            return

        for offset in 0, 10, 20, 30, 40:
            mu = int(-seeker.magnet.strength * pygame.time.get_ticks() / 50 + offset) % 50
            self.draw_circle(interpolate_color(color, [0, 0, 0], mu / 50), seeker.position, mu + seeker.radius, 2)

    def draw_jet_stream(self, seeker: InternalSeeker, direction: Vector):
        length = seeker.radius * 3

        self.draw_line((255, 255, 255), seeker.position, seeker.position + direction * length)

    @staticmethod
    def students_ttest(players: Collection[InternalPlayer]) -> float:
        if len(players) != 2:
            raise ValueError("Students t-test only works with 2 players.")

        # noinspection PyPackageRequirements
        from scipy import stats

        players = iter(players)

        score0 = next(players).score
        score1 = next(players).score

        t, p = stats.ttest_1samp([1] * score0 + [0] * score1, 0.5)
        return p

    def draw_information(self, players: Collection[InternalPlayer], pos: Vector, clock: pygame.time.Clock):
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

        # draw student's t-test
        if self.config.flags_t_test and len(players) == 2:
            p = self.students_ttest(players)

            self.draw_text(f"{p:.2e}", (255, 255, 255), Vector(100, 100))
