import abc
import dataclasses
import typing
import pygame
from contextvars import ContextVar

from seekers import Vector


@dataclasses.dataclass
class DebugDrawing(abc.ABC):
    @abc.abstractmethod
    def draw(self, surface: pygame.Surface):
        ...


@dataclasses.dataclass
class TextDebugDrawing(DebugDrawing):
    text: str
    position: Vector
    color: tuple[int, int, int] = (255, 255, 255)
    size: int = 20

    def __post_init__(self):
        self.font = pygame.font.SysFont("monospace", self.size, bold=True)

    def draw(self, surface: pygame.Surface):
        # draw the text centered at the position
        text_surface = self.font.render(self.text, True, self.color)
        text_rect = text_surface.get_rect(center=tuple(self.position))
        surface.blit(text_surface, text_rect)


@dataclasses.dataclass
class LineDebugDrawing(DebugDrawing):
    start: Vector
    end: Vector
    color: tuple[int, int, int] = (255, 255, 255)
    width: int = 2

    def draw(self, surface: pygame.Surface):
        pygame.draw.line(surface, self.color, tuple(self.start), tuple(self.end), self.width)


@dataclasses.dataclass
class CircleDebugDrawing(DebugDrawing):
    position: Vector
    radius: float
    color: tuple[int, int, int] = (255, 255, 255)
    width: int = 2

    def draw(self, surface: pygame.Surface):
        pygame.draw.circle(surface, self.color, tuple(self.position), self.radius, self.width)


def draw_text(text: str, position: Vector, color: tuple[int, int, int] = (255, 255, 255), size: int = 20):
    add_debug_drawing_func_ctxtvar.get()(TextDebugDrawing(text, position, color, size))


def draw_line(start: Vector, end: Vector, color: tuple[int, int, int] = (255, 255, 255), width: int = 2):
    add_debug_drawing_func_ctxtvar.get()(LineDebugDrawing(start, end, color, width))


def draw_circle(position: Vector, radius: float, color: tuple[int, int, int] = (255, 255, 255), width: int = 2):
    add_debug_drawing_func_ctxtvar.get()(CircleDebugDrawing(position, radius, color, width))


add_debug_drawing_func_ctxtvar: \
    ContextVar[typing.Callable[[DebugDrawing], None]] = ContextVar("add_debug_drawing_func", default=lambda _: None)
