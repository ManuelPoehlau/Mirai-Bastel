"""DialAngle: Blender-style dial maths shared by every rotate gesture (gizmo ring, R/E key, Tweak, objects).

The cursor at the press and now are cast onto the plane (pivot, axis); the signed angle between the two
pivot->point vectors about the axis is the rotation, full turns are counted (Blender `dial_ghostarc_get_angles`).
The grab point therefore follows the cursor and a pixel near the pivot turns more degrees than one far away.

Where that plane is (nearly) edge-on to the view, or the press is too close to the pivot's screen position
(the angle is unstable there), the whole gesture uses the cursor travel along the screen tangent at the press
point divided by its distance to the pivot instead; the choice is made once at `begin`, so nothing jumps.

Modifiers (Blender): Shift = precision (the cursor's angle changes count x`PRECISION_GAIN`, continuous when
toggled), Ctrl = snap the result to `SNAP_STEP` (`SNAP_STEP_PRECISE` together with Shift). `PROVISIONAL`.
Pure maths: `camera` needs `screen_to_ray`, `project_to_screen` and `basis`.
"""

from __future__ import annotations

import math

from ..viewport import vecmath as v
from ..viewport.camera import ray_plane_point

#: Below this |cos| between the view ray and the axis the ring plane counts as edge-on.
GRAZING_COS = 0.12
#: A press closer than this to the pivot's screen position uses the tangent fallback.
MIN_PRESS_RADIUS_PX = 20.0
#: The fallback's lever arm is at least this long (px), so a press near the pivot turns ~0.57 deg/px, not wildly.
FALLBACK_MIN_RADIUS_PX = 100.0
PRECISION_GAIN = 0.2
SNAP_STEP = math.radians(5.0)
SNAP_STEP_PRECISE = math.radians(1.0)


class DialAngle:
    """One dial gesture: `update(x, y, ...)` returns the total angle (rad) about `axis` since the press."""

    def __init__(self, camera, pivot, axis, press, width: int, height: int) -> None:
        self._camera = camera
        self._pivot = pivot
        self._axis = axis
        self._press = (float(press[0]), float(press[1]))
        self._start = None  # pivot->press vector on the plane (ray mode)
        self._tangent = None  # (screen tangent, radius px) (fallback mode)
        self._last_delta = 0.0
        self._turns = 0
        self._last_raw = 0.0
        self._effective = 0.0
        self._begin(width, height)

    @property
    def grazing(self) -> bool:
        """True while the gesture uses the screen-tangent fallback."""
        return self._tangent is not None

    def _begin(self, width: int, height: int) -> None:
        origin, direction = self._camera.screen_to_ray(*self._press, width, height)
        centre = self._camera.project_to_screen(self._pivot, width, height)
        near_pivot = centre is not None and math.hypot(
            self._press[0] - centre[0], self._press[1] - centre[1]
        ) < MIN_PRESS_RADIUS_PX
        hit = None
        if abs(v.dot(direction, self._axis)) >= GRAZING_COS and not near_pivot:
            hit = ray_plane_point(origin, direction, self._pivot, self._axis)
        if hit is not None and v.length(v.sub(hit, self._pivot)) >= 1e-9:
            self._start = v.sub(hit, self._pivot)
            return
        self._tangent = self._screen_tangent(centre, width, height)

    def _screen_tangent(self, centre, width: int, height: int):
        """(unit screen tangent at the press point, radius in px); counter-clockwise on screen is a positive
        right-hand turn when the axis points at the viewer."""
        cx, cy = centre if centre is not None else (width / 2.0, height / 2.0)
        rx, ry = self._press[0] - cx, self._press[1] - cy
        dist = math.hypot(rx, ry)
        if dist < 1e-6:
            rx, ry, dist = 0.0, 1.0, 1.0  # press on the pivot: drag right = clockwise, like the old dx rotate
        tangent = (-ry / dist, rx / dist)
        forward, _, _ = self._camera.basis()
        if v.dot(self._axis, forward) > 0.0:
            tangent = (-tangent[0], -tangent[1])
        return tangent, max(dist, FALLBACK_MIN_RADIUS_PX)

    def raw(self, x: float, y: float, width: int, height: int) -> float:
        """Unmodified total angle for the cursor at (x, y); (x, y) may lie outside the window."""
        if self._tangent is not None:
            tangent, radius = self._tangent
            return ((x - self._press[0]) * tangent[0] + (y - self._press[1]) * tangent[1]) / radius
        origin, direction = self._camera.screen_to_ray(x, y, width, height)
        hit = ray_plane_point(origin, direction, self._pivot, self._axis)
        if hit is None:
            return self._last_delta + 2.0 * math.pi * self._turns
        rel = v.sub(hit, self._pivot)
        a = self._start
        delta = math.atan2(v.dot(self._axis, v.cross(a, rel)), v.dot(a, rel))
        # A sign flip after more than a quarter turn means the angle wrapped at +-pi: count the turn.
        if self._last_delta > math.pi / 2 and delta < 0:
            self._turns += 1
        elif self._last_delta < -math.pi / 2 and delta > 0:
            self._turns -= 1
        self._last_delta = delta
        return delta + 2.0 * math.pi * self._turns

    def update(
        self, x: float, y: float, width: int, height: int, precise: bool = False, snap: bool = False
    ) -> float:
        raw = self.raw(x, y, width, height)
        self._effective += (raw - self._last_raw) * (PRECISION_GAIN if precise else 1.0)
        self._last_raw = raw
        if not snap:
            return self._effective
        step = SNAP_STEP_PRECISE if precise else SNAP_STEP
        return round(self._effective / step) * step
