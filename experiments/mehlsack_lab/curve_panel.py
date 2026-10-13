"""Curve panel geometry: layout, picking, screen <-> curve mapping (handoff §4, Slice 2a E12) — no GL.

The panel sits bottom-left (pyglet window coordinates: y up). Its plot area maps x = d/r in
[0, 1] left → right and w in [-1, 1] bottom → top; the zero line is drawn clearly, the area
above it tinted warm, below it cool (drawing lives in `lab_window`).

Picking (E12): the element nearest to the cursor within `PICK_RADIUS_PX`; handles win over
knots when both are in reach (so a handle lying on its knot can be pulled out). The end
knots are fixed and not pickable, their handles are. A press on empty panel space picks
nothing. A drag moves the element by the cursor's motion (grab offset kept), so a click
without motion changes nothing — which is what makes the double click clean.

`DoubleClick` recognises two presses on the same knot within `DOUBLE_CLICK_S`; a handle
counts as its knot. Geometry values are `PROVISIONAL`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .signed_curve import FIRST, HANDLE_IN, HANDLE_OUT, INTERIOR, LAST, Y_MAX, Y_MIN, Point, SignedCurve

PANEL_MARGIN = 12
PANEL_WIDTH = 320
PANEL_HEIGHT = 190
#: Inner padding between panel border and plot area (room for the labels).
PLOT_PAD_X = 16
PLOT_PAD_Y = 18
#: PROVISIONAL pick reach in screen px.
PICK_RADIUS_PX = 12.0
#: PROVISIONAL double-click window (s) and how far the cursor may move between the clicks (px).
DOUBLE_CLICK_S = 0.4
DOUBLE_CLICK_PX = 6.0

KNOT = "knot"


@dataclass(frozen=True)
class Element:
    """A pickable part of the curve: `kind` is "knot", "in" or "out", `index` the knot."""

    kind: str
    index: int

    @property
    def is_handle(self) -> bool:
        return self.kind in (HANDLE_IN, HANDLE_OUT)


def element_position(curve: SignedCurve, element: Element) -> Point:
    if element.kind == KNOT:
        return curve.knots[element.index]
    if element.kind == HANDLE_IN:
        return curve.handles_in[element.index]
    return curve.handles_out[element.index]


def pickable_elements(curve: SignedCurve) -> list[Element]:
    handles = [Element(HANDLE_OUT, i) for i in range(FIRST, LAST)]
    handles += [Element(HANDLE_IN, i) for i in range(FIRST + 1, LAST + 1)]
    return handles + [Element(KNOT, i) for i in INTERIOR]


def move_element(curve: SignedCurve, element: Element, x: float, y: float,
                 break_alignment: bool = False) -> SignedCurve:
    """`curve` with `element` dragged to the curve-space point (x, y) (the curve clamps)."""
    if element.kind == KNOT:
        return curve.with_knot(element.index, x, y)
    return curve.with_handle(element.index, element.kind, x, y, break_alignment=break_alignment)


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

    def to_curve(self, sx: float, sy: float) -> tuple[float, float]:
        """Curve-space point of a screen point (not clamped; the curve clamps its edits)."""
        x0, y0, x1, y1 = self.plot
        return ((sx - x0) / (x1 - x0), Y_MIN + (sy - y0) / (y1 - y0) * (Y_MAX - Y_MIN))

    def zero_y(self) -> float:
        return self.to_screen(0.0, 0.0)[1]

    def pick(self, sx: float, sy: float, curve: SignedCurve) -> Optional[Element]:
        """Nearest element in reach; handles before knots (module docstring)."""
        best: dict[bool, tuple[float, Element]] = {}
        for element in pickable_elements(curve):
            px, py = self.to_screen(*element_position(curve, element))
            d = (px - sx) ** 2 + (py - sy) ** 2
            if d > PICK_RADIUS_PX ** 2:
                continue
            found = best.get(element.is_handle)
            if found is None or d < found[0]:
                best[element.is_handle] = (d, element)
        for is_handle in (True, False):
            if is_handle in best:
                return best[is_handle][1]
        return None

    def knot_points(self, curve: SignedCurve) -> list[tuple[float, float]]:
        """Screen positions of all six knots (endpoints first and last)."""
        return [self.to_screen(x, y) for x, y in curve.knots]

    def handle_lines(self, curve: SignedCurve) -> list[tuple[Element, tuple[float, float], tuple[float, float]]]:
        """(handle, knot screen point, handle screen point) for every handle."""
        lines = []
        for i, knot in enumerate(curve.knots):
            for kind, handle in ((HANDLE_IN, curve.handles_in[i]), (HANDLE_OUT, curve.handles_out[i])):
                if handle is not None:
                    lines.append((Element(kind, i), self.to_screen(*knot), self.to_screen(*handle)))
        return lines

    def polyline(self, curve: SignedCurve, per_segment: int = 24) -> list[tuple[float, float]]:
        return [self.to_screen(x, y) for x, y in curve.sample_points(per_segment)]


class DoubleClick:
    """Two presses on the same knot (a handle counts as its knot) within `DOUBLE_CLICK_S`
    and `DOUBLE_CLICK_PX`. Time is passed in, so this is testable without a clock."""

    def __init__(self) -> None:
        self._last: Optional[tuple[float, float, float, int]] = None

    def press(self, element: Optional[Element], sx: float, sy: float, now: float) -> Optional[int]:
        """Registers a press; returns the knot index if it completes a double click."""
        if element is None:
            self._last = None
            return None
        last = self._last
        if (last is not None and last[3] == element.index and now - last[0] <= DOUBLE_CLICK_S
                and (sx - last[1]) ** 2 + (sy - last[2]) ** 2 <= DOUBLE_CLICK_PX ** 2):
            self._last = None
            return element.index
        self._last = (now, sx, sy, element.index)
        return None
