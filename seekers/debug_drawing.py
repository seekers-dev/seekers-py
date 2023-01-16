import abc
import dataclasses
import typing
from contextvars import ContextVar

from seekers import Vector
from seekers.draw import GameRenderer


@dataclasses.dataclass
class DebugDrawing(abc.ABC):
    @abc.abstractmethod
    def draw(self, game_renderer: GameRenderer):
        ...


@dataclasses.dataclass
class TextDebugDrawing(DebugDrawing):
    text: str
    position: Vector
    color: tuple[int, int, int] = (255, 255, 255)
    center: bool = True

    def draw(self, game_renderer: GameRenderer):
        # draw the text centered at the position
        game_renderer.draw_text(self.text, self.color, self.position, center=self.center)


@dataclasses.dataclass
class LineDebugDrawing(DebugDrawing):
    start: Vector
    end: Vector
    color: tuple[int, int, int] = (255, 255, 255)
    width: int = 2

    def draw(self, game_renderer: GameRenderer):
        game_renderer.draw_line(self.color, self.start, self.end, self.width)


@dataclasses.dataclass
class CircleDebugDrawing(DebugDrawing):
    position: Vector
    radius: float
    color: tuple[int, int, int] = (255, 255, 255)
    width: int = 2

    def draw(self, game_renderer: GameRenderer):
        game_renderer.draw_circle(self.color, self.position, self.radius, self.width)


def draw_text(text: str, position: Vector, color: tuple[int, int, int] = (255, 255, 255), center: bool = True):
    add_debug_drawing_func_ctxtvar.get()(TextDebugDrawing(text, position, color, center))


def draw_line(start: Vector, end: Vector, color: tuple[int, int, int] = (255, 255, 255), width: int = 2):
    add_debug_drawing_func_ctxtvar.get()(LineDebugDrawing(start, end, color, width))


def draw_circle(position: Vector, radius: float, color: tuple[int, int, int] = (255, 255, 255), width: int = 2):
    add_debug_drawing_func_ctxtvar.get()(CircleDebugDrawing(position, radius, color, width))


add_debug_drawing_func_ctxtvar: \
    ContextVar[typing.Callable[[DebugDrawing], None]] = ContextVar("add_debug_drawing_func", default=lambda _: None)
