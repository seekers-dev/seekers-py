import pygame
from typing import Iterable

from .hash_color import interpolate_color
from .seekers_types import *

player_name_images = {}
font = None
background_color = [0, 0, 30]

Color = tuple[int, int, int] | list[int]


class Animation(abc.ABC):
    duration: float

    def __init__(self):
        self.age = 0

    @abc.abstractmethod
    def draw(self, world, screen):
        ...


class ScoreAnimation(Animation):
    duration = 20

    def __init__(self, position: Vector, color: Color, radius: float):
        super().__init__()
        self.position = position
        self.color = color
        self.radius = radius

    def draw(self, world, screen):
        t = self.age / self.duration
        r = self.radius + 100 * t
        for dx, dy in repetition_offsets(world):
            pygame.draw.circle(screen, self.color, (int(self.position.x + dx), int(self.position.y + dy)), int(r), 1)


# TODO: Refactor below code into GameRenderer class

def init(players: Iterable[InternalPlayer]):
    global font
    global name_images

    font = pygame.font.SysFont("monospace", 20, bold=True)

    for p in players:
        player_name_images[p.name] = font.render(p.name, True, p.color)


def draw(players: Iterable[InternalPlayer], camps: Iterable[Camp], goals: Iterable[InternalGoal],
         animations: list[Animation], clock: pygame.time.Clock, world: World,
         screen: pygame.Surface):
    # clear screen
    screen.fill(background_color)

    # draw camps
    draw_camps(camps, screen)

    # draw goals
    for g in goals:
        draw_goal(g, world, screen)

    # draw jet streams
    for p in players:
        for s in p.seekers.values():
            a = s.acceleration
            if not s.is_disabled and a.length() > 0:
                draw_jet_stream(s, -a, world, screen)

    # draw seekers
    for p in players:
        for s in p.seekers.values():
            draw_seeker(s, p, world, screen)

        for debug_drawing in p.debug_drawings:
            debug_drawing.draw(screen)

    # draw animations
    for animation in animations:
        animation.draw(world, screen)

    # draw information (player's scores, etc.)
    draw_information(players, Vector(10, 10), clock, world, screen)

    # actually update display
    pygame.display.flip()


def draw_seeker(seeker, player, world, screen):
    color = player.color
    if seeker.is_disabled:
        color = interpolate_color(color, [0, 0, 0], 0.5)

    # if player.ai.is_dummy:
    #     color = interpolate_color(color, [1, 1, 1], 0.5)

    draw_item(color, seeker.position, seeker.radius, world, screen)
    draw_halo(seeker, color, screen)

    # TODO: game debug mode via cmd
    # if world.debug_mode:
    #     draw_text(seeker.id, [255, 255, 255], pos, screen)


def draw_goal(goal, world, screen):
    global font
    color = [205, 0, 250]
    pos = goal.position
    draw_item(color, pos, goal.radius, world, screen)


def draw_text(text: str, color: Color, pos: Vector, screen: pygame.Surface, center=True):
    global font
    (dx, dy) = font.size(text)
    adj_pos = pos - Vector(dx, dy) / 2 if center else pos
    screen.blit(font.render(text, False, color), tuple(adj_pos))


def draw_halo(seeker: InternalSeeker, color: Color, screen: pygame.Surface):
    if seeker.is_disabled:
        return

    mu = abs(math.sin((int(pygame.time.get_ticks() / 30) % 50) / 50 * 2 * math.pi)) ** 2
    pygame.draw.circle(screen, interpolate_color(color, [0, 0, 0], mu),
                       (int(seeker.position.x), int(seeker.position.y)), 3 + seeker.radius, 3)

    if not seeker.magnet.is_on():
        return

    for offset in 0, 10, 20, 30, 40:
        mu = int(-seeker.magnet.strength * pygame.time.get_ticks() / 50 + offset) % 50
        pygame.draw.circle(screen, interpolate_color(color, [0, 0, 0], mu / 50),
                           (int(seeker.position.x), int(seeker.position.y)), mu + seeker.radius, 2)


def draw_camps(camps: Iterable[Camp], screen: pygame.Surface):
    for camp in camps:
        x, y = camp.position.x, camp.position.y
        w = camp.width
        h = camp.height
        dx = w / 2
        dy = h / 2
        r = pygame.Rect((x - dx, y - dy), (w, h))
        color = camp.owner.color
        pygame.draw.rect(screen, color, r, 5)


def draw_item(color: Color, center: Vector, radius: float, world: World, screen: pygame.Surface):
    for (dx, dy) in repetition_offsets(world):
        pygame.draw.circle(screen, color, (int(center.x + dx), int(center.y + dy)), radius)


def draw_jet_stream(seeker: InternalSeeker, direction: Vector, world: World, screen: pygame.Surface):
    def line(a, b):
        for dx, dy in repetition_offsets(world):
            pygame.draw.line(screen, [255, 255, 255], (int(a.x + dx), int(a.y + dy)), (int(b.x + dx), int(b.y + dy)))

    for _ in range(0, 2):
        length = seeker.radius * 3
        line(seeker.position, seeker.position + direction * length)


def repetition_offsets(world: World):
    l = []
    for ix in [-1, 0, 1]:
        for iy in [-1, 0, 1]:
            l.append((ix * world.width, iy * world.height))
    return l


def draw_information(players: Iterable[InternalPlayer], pos: Vector, clock: pygame.time.Clock, world: World,
                     screen: pygame.Surface):
    global name_images
    global font

    # draw fps
    fps = int(clock.get_fps())
    draw_text(str(fps), [250, 250, 250], pos, screen, center=False)

    dx = Vector(40, 0)
    dy = Vector(0, 30)
    pos += dy
    for p in players:
        draw_text(str(p.score), p.color, pos, screen, center=False)
        screen.blit(player_name_images[p.name], tuple(pos + dx))
        pos += dy
