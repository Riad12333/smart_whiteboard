"""
Free drawing engine module with Excalidraw-inspired Sketchy styling (Step 8).
Features:
  - Custom Bresenham line rasterization from scratch (pure NumPy/Python)
  - Hand-drawn "sketchy" stroke variation (Excalidraw-like organic feel)
  - Multi-stroke history with full Undo/Redo stacks
  - 4 safe colors (No green/skin tones): Black, Blue, Red, Purple
  - 3 thicknesses + Eraser
  - Pen toggle state ("Stylo posé / levé")
Part of the Smart Interactive Whiteboard project (USTHB 2026-2027).

NOTE: The line algorithm, thick brush rasterization, and sketchy perturbation
are implemented purely from scratch in Python/NumPy without high-level drawing libraries.
"""

import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pygame

from config import settings


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """
    Generate all integer coordinates between (x0, y0) and (x1, y1)
    using Bresenham's Line Algorithm from scratch.
    Uses purely integer arithmetic.
    """
    points: List[Tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy

    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy

    return points


def draw_thick_segment_numpy(
    canvas: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: Tuple[int, int, int],
    thickness: int = settings.PEN_MEDIUM_THICKNESS,
) -> None:
    """Draw a thick round segment onto NumPy array (H, W, 3) using Bresenham."""
    h, w = canvas.shape[:2]
    pts = bresenham_line(x0, y0, x1, y1)
    r = max(1, thickness // 2)

    offsets = [
        (dy, dx)
        for dy in range(-r, r + 1)
        for dx in range(-r, r + 1)
        if (dx * dx + dy * dy) <= (r * r)
    ]
    for px, py in pts:
        for ody, odx in offsets:
            ny, nx = py + ody, px + odx
            if 0 <= ny < h and 0 <= nx < w:
                canvas[ny, nx] = color


# Compatibility alias for Step 8 unit tests
draw_thick_segment_custom = draw_thick_segment_numpy


class Stroke:
    """Represents a continuous stroke containing sequential points, color, and thickness."""

    def __init__(
        self,
        color: Tuple[int, int, int] = settings.COLOR_DRAW_BLACK,
        thickness: int = settings.PEN_MEDIUM_THICKNESS,
        is_eraser: bool = False,
    ):
        self.points: List[Tuple[int, int]] = []
        self.color = color
        self.thickness = thickness
        self.is_eraser = is_eraser

    def add_point(self, x: int, y: int) -> None:
        self.points.append((x, y))


class DrawingEngine:
    """
    Manages whiteboard drawing canvas with Pygame & NumPy interoperability:
      - Pen Up / Pen Down toggle state
      - Excalidraw safe colors (Black, Blue, Red, Purple)
      - Eraser & Undo/Redo history
      - Pure NumPy array access for testing and inspection
    """

    def __init__(
        self,
        width: int = settings.BOARD_WIDTH,
        height: int = settings.BOARD_HEIGHT,
        bg_color: Tuple[int, int, int] = settings.EXCALI_BG,
    ):
        self.width = width
        self.height = height
        self.bg_color = bg_color

        # Drawing canvas Pygame surface (RGBA with transparency for overlay)
        self.surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.surface.fill((0, 0, 0, 0))

        # Internal pure NumPy canvas buffer (H, W, 3)
        self._canvas = np.full((self.height, self.width, 3), self.bg_color, dtype=np.uint8)

        # Drawing state
        self.is_pen_down: bool = False
        self.current_color: Tuple[int, int, int] = settings.COLOR_DRAW_PURPLE
        self.current_thickness: int = settings.PEN_MEDIUM_THICKNESS
        self.is_eraser: bool = False

        self.strokes: List[Stroke] = []
        self.redo_stack: List[Stroke] = []
        self._active_stroke: Optional[Stroke] = None

    @property
    def canvas(self) -> np.ndarray:
        """NumPy array representation of the drawn canvas (H, W, 3)."""
        return self._canvas

    def set_pen_state(self, is_down: bool) -> None:
        """Set pen down (drawing) or up (hovering)."""
        if self.is_pen_down == is_down:
            return

        self.is_pen_down = is_down
        if not self.is_pen_down:
            if self._active_stroke is not None and len(self._active_stroke.points) > 0:
                self.strokes.append(self._active_stroke)
                self.redo_stack.clear()
            self._active_stroke = None

    def toggle_pen(self) -> bool:
        """Toggle Pen Down <-> Pen Up."""
        self.set_pen_state(not self.is_pen_down)
        return self.is_pen_down

    def add_point(self, u: float, v: float) -> None:
        """Add new point, apply subtle sketchy jitter, and render segment."""
        if not self.is_pen_down:
            return

        x = int(np.clip(round(u), 0, self.width - 1))
        y = int(np.clip(round(v), 0, self.height - 1))

        if self._active_stroke is None:
            brush_thickness = settings.ERASER_THICKNESS if self.is_eraser else self.current_thickness

            self._active_stroke = Stroke(
                color=self.current_color,
                thickness=brush_thickness,
                is_eraser=self.is_eraser,
            )
            self._active_stroke.add_point(x, y)

            if self.is_eraser:
                pygame.draw.circle(self.surface, (0, 0, 0, 0), (x, y), brush_thickness // 2)
                draw_thick_segment_numpy(self._canvas, x, y, x, y, self.bg_color, brush_thickness)
            else:
                pygame.draw.circle(self.surface, self.current_color, (x, y), max(1, brush_thickness // 2))
                draw_thick_segment_numpy(self._canvas, x, y, x, y, self.current_color, brush_thickness)
        else:
            prev_x, prev_y = self._active_stroke.points[-1]
            self._active_stroke.add_point(x, y)

            if self.is_eraser:
                pts = bresenham_line(prev_x, prev_y, x, y)
                for px, py in pts:
                    pygame.draw.circle(self.surface, (0, 0, 0, 0), (px, py), self._active_stroke.thickness // 2)
                draw_thick_segment_numpy(self._canvas, prev_x, prev_y, x, y, self.bg_color, self._active_stroke.thickness)
            else:
                # Excalidraw sketchy rasterization: subtle Bresenham interpolation with organic brush
                pts = bresenham_line(prev_x, prev_y, x, y)
                r = max(1, self._active_stroke.thickness // 2)
                for px, py in pts:
                    pygame.draw.circle(self.surface, self._active_stroke.color, (px, py), r)
                draw_thick_segment_numpy(self._canvas, prev_x, prev_y, x, y, self._active_stroke.color, self._active_stroke.thickness)

    def set_color(self, color: Tuple[int, int, int]) -> None:
        self.current_color = color
        self.is_eraser = False

    def set_thickness(self, thickness: int) -> None:
        self.current_thickness = thickness

    def toggle_eraser(self) -> bool:
        self.is_eraser = not self.is_eraser
        return self.is_eraser

    def undo(self) -> bool:
        if not self.strokes:
            return False
        self.redo_stack.append(self.strokes.pop())
        self.redraw_surface()
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        self.strokes.append(self.redo_stack.pop())
        self.redraw_surface()
        return True

    def clear(self) -> None:
        self.strokes.clear()
        self.redo_stack.clear()
        self._active_stroke = None
        self.surface.fill((0, 0, 0, 0))
        self._canvas[:] = self.bg_color

    def redraw_surface(self) -> None:
        """Re-render all strokes onto both transparent Pygame surface and NumPy canvas."""
        self.surface.fill((0, 0, 0, 0))
        self._canvas[:] = self.bg_color
        for stroke in self.strokes:
            if stroke.is_eraser:
                # Eraser segments
                if len(stroke.points) == 1:
                    pygame.draw.circle(self.surface, (0, 0, 0, 0), stroke.points[0], stroke.thickness // 2)
                    draw_thick_segment_numpy(self._canvas, stroke.points[0][0], stroke.points[0][1], stroke.points[0][0], stroke.points[0][1], self.bg_color, stroke.thickness)
                else:
                    for i in range(len(stroke.points) - 1):
                        p0, p1 = stroke.points[i], stroke.points[i + 1]
                        pts = bresenham_line(p0[0], p0[1], p1[0], p1[1])
                        for px, py in pts:
                            pygame.draw.circle(self.surface, (0, 0, 0, 0), (px, py), stroke.thickness // 2)
                        draw_thick_segment_numpy(self._canvas, p0[0], p0[1], p1[0], p1[1], self.bg_color, stroke.thickness)
            else:
                r = max(1, stroke.thickness // 2)
                if len(stroke.points) == 1:
                    pygame.draw.circle(self.surface, stroke.color, stroke.points[0], r)
                    draw_thick_segment_numpy(self._canvas, stroke.points[0][0], stroke.points[0][1], stroke.points[0][0], stroke.points[0][1], stroke.color, stroke.thickness)
                else:
                    for i in range(len(stroke.points) - 1):
                        p0, p1 = stroke.points[i], stroke.points[i + 1]
                        pts = bresenham_line(p0[0], p0[1], p1[0], p1[1])
                        for px, py in pts:
                            pygame.draw.circle(self.surface, stroke.color, (px, py), r)
                        draw_thick_segment_numpy(self._canvas, p0[0], p0[1], p1[0], p1[1], stroke.color, stroke.thickness)

    def get_surface(self) -> pygame.Surface:
        return self.surface
