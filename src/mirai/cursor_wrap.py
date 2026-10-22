"""CursorWrapper: Blender-style "leave the viewport on one side, come back on the other" for drags.

While `app.cursor_wrap_active` (a running transform; later slider drags can share it) the pointer is warped to the
opposite edge as soon as it touches one, so a long drag is not limited by the window size. `Application` keeps the
jump (`cursor_wrapped`); every gesture runs on deltas (the rotate dial integrates them into a virtual cursor), which
stay unbroken because the event the warp itself causes is swallowed. Where the platform cannot warp the pointer
(`set_mouse_position` missing or failing, e.g. Wayland) wrapping switches itself off.
"""

from __future__ import annotations

import time

#: The pointer wraps when it is this close (px) to an edge ...
TRIGGER_PX = 1
#: ... and re-appears this far (px) inside the opposite edge (must exceed TRIGGER_PX, or it would wrap back).
INSET_PX = 8
#: After a warp, events within this distance (px) of the old position are stale (queued before the warp).
STALE_RADIUS_PX = 40
#: A warp is expected to be answered within this time (s); platforms that send no event never answer.
WARP_WINDOW_S = 0.25


class CursorWrapper:
    """Why `filter` computes the deltas itself: the platform's `dx`/`dy` are relative to *its* last position, so
    after a warp (and a swallowed reply) the next event would carry the whole jump across the viewport. Events
    that were already queued at the old edge when the warp happened are dropped for the same reason."""

    def __init__(self, window, app, clock=time.monotonic) -> None:
        self._window = window
        self._app = app
        self._clock = clock
        self._enabled = True
        self._last: tuple[float, float] | None = None  # the position the app has been told about
        self._warp: tuple[tuple[int, int], tuple[float, float], float] | None = None  # (target, old, deadline)
        self._own_deltas = False

    def filter(self, x: float, y: float, dx: float, dy: float):
        """The (dx, dy) to hand to the app for the event at (x, y), or None to drop the event."""
        now = self._clock()
        if self._warp is not None and now > self._warp[2]:
            self._warp = None
        if self._warp is not None:
            target, old, _ = self._warp
            if abs(x - target[0]) <= 1 and abs(y - target[1]) <= 1:
                self._warp = None  # the warp's own reply: the app already moved its cursor
                self._last = (x, y)
                return None
            if abs(x - old[0]) <= STALE_RADIUS_PX and abs(y - old[1]) <= STALE_RADIUS_PX:
                return None  # queued before the warp
        if not self._app.cursor_wrap_active:
            self._own_deltas = False
        if self._own_deltas and self._last is not None:
            dx, dy = x - self._last[0], y - self._last[1]
        self._last = (x, y)
        return dx, dy

    def after_event(self, x: float, y: float) -> bool:
        """Call after the app handled a pointer event at (x, y); True when the pointer was wrapped."""
        if not self._enabled or self._warp is not None or not self._app.cursor_wrap_active:
            return False
        width, height = self._window.width, self._window.height
        nx, ny = x, y
        if x <= TRIGGER_PX:
            nx = width - 1 - INSET_PX
        elif x >= width - 1 - TRIGGER_PX:
            nx = INSET_PX
        if y <= TRIGGER_PX:
            ny = height - 1 - INSET_PX
        elif y >= height - 1 - TRIGGER_PX:
            ny = INSET_PX
        if (nx, ny) == (x, y):
            return False
        try:
            self._window.set_mouse_position(int(nx), int(ny))
        except Exception:  # noqa: BLE001 - no pointer warping on this platform: stop trying
            self._enabled = False
            return False
        self._warp = ((int(nx), int(ny)), (x, y), self._clock() + WARP_WINDOW_S)
        self._last = (float(int(nx)), float(int(ny)))  # a platform without a reply event still continues from here
        self._own_deltas = True
        self._app.cursor_wrapped(nx - x, ny - y)
        return True
