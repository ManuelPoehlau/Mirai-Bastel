"""Curve panel geometry: layout, hit test, screen <-> curve mapping (handoff §4) — no GL.

The panel sits bottom-left (about 260 × 160 px, pyglet window coordinates: y up). Its
plot area maps x = d/r in [0, 1] left → right and w in [-1, 1] bottom → top; the zero
line is drawn clearly, the area above it tinted warm, below it cool (drawing lives in
`lab_window`). LMB inside the panel grabs the interior control point nearest to the
cursor and sets its y to the cursor's height (vertical only, x fixed); the press never
reaches the mesh. Geometry values are `PROVISIONAL`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .signed_curve import INTERIOR_X, KNOTS_X, Y_MAX, Y_MIN, SignedCurve

PANEL_MARGIN = 12
PANEL_WIDTH = 260
PANEL_HEIGHT = 160
#: Inner padding between panel border and plot area (room for the labels).
PLOT_PAD_X = 16
PLOT_PAD_Y = 18


@dataclass(frozen=True)
class CurvePanel:
    x: float = PANEL_MARGIN
    y: float = PANEL_MARGIN
    width: float = PANEL_WIDTH
    height: float = PANEL_HEIGHT

    @property
    def plot(self) -> tuple[float, float, float, float]:
        """(x0, y0, x1, y1) of the plot area."""
        return (self.x + PLOT_PAD_X, self.y + PLOT_PAD_Y,
                self.x + self.width - PLOT_PAD_X, self.y + self.height - PLOT_PAD_Y)

    def contains(self, sx: float, sy: float) -> bool:
        return self.x <= sx <= self.x + self.width and self.y <= sy <= self.y + self.height

    def to_screen(self, cx: float, cy: float) -> tuple[float, float]:
        x0, y0, x1, y1 = self.plot
        return (x0 + cx * (x1 - x0), y0 + (cy - Y_MIN) / (Y_MAX - Y_MIN) * (y1 - y0))

    def value_at(self, sy: float) -> float:
        """Curve y for a screen height, clamped to [-1, 1]."""
        _x0, y0, _x1, y1 = self.plot
        value = Y_MIN + (sy - y0) / (y1 - y0) * (Y_MAX - Y_MIN)
        return max(Y_MIN, min(Y_MAX, value))

    def zero_y(self) -> float:
        return self.to_screen(0.0, 0.0)[1]

    def nearest_point(self, sx: float, sy: float, curve: SignedCurve) -> int:
        """Index (0..3) of the interior control point nearest to the cursor (screen px)."""
        best, best_d = 0, float("inf")
        for i, cx in enumerate(INTERIOR_X):
            px, py = self.to_screen(cx, curve.interior[i])
            d = (px - sx) ** 2 + (py - sy) ** 2
            if d < best_d:
                best, best_d = i, d
        return best

    def control_points(self, curve: SignedCurve) -> list[tuple[float, float]]:
        """Screen positions of all six knots (endpoints first and last)."""
        return [self.to_screen(x, y) for x, y in zip(KNOTS_X, curve.ys)]

    def polyline(self, curve: SignedCurve, samples: int = 96) -> list[tuple[float, float]]:
        return [self.to_screen(i / samples, curve(i / samples)) for i in range(samples + 1)]
