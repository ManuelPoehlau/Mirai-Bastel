"""CursorWrapper: Blender-style "leave the viewport on one side, come back on the other" for drags.

While `app.cursor_wrap_active` (a running transform; later slider drags can share it) the pointer is warped to the
opposite edge as soon as it touches one, so a long drag is not limited by the window size. `Application` keeps the
jump (`cursor_wrapped`); every gesture runs on deltas (the rotate dial integrates them into a virtual cursor), which
stay unbroken because the event the warp itself causes is swallowed. Where the platform cannot warp the pointer
(`set_mouse_position` missing or failing, e.g. Wayland) wrapping switches itself off.
"""

from __future__ import annotations

#: The pointer wraps when it is this close (px) to an edge ...
TRIGGER_PX = 1
#: ... and re-appears this far (px) inside the opposite edge (must exceed TRIGGER_PX, or it would wrap back).
INSET_PX = 8


class CursorWrapper:
    def __init__(self, window, app) -> None:
        self._window = window
        self._app = app
        self._pending: tuple[int, int] | None = None
        self._enabled = True

    def swallow(self, x: float, y: float) -> bool:
        """True for the event our own warp caused (to be ignored); any other event clears the expectation."""
        pending, self._pending = self._pending, None
        return pending is not None and abs(x - pending[0]) <= 1 and abs(y - pending[1]) <= 1

    def after_event(self, x: float, y: float) -> bool:
        """Call after the app handled a pointer event at (x, y); True when the pointer was wrapped."""
        if not self._enabled or not self._app.cursor_wrap_active:
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
        self._pending = (int(nx), int(ny))
        self._app.cursor_wrapped(nx - x, ny - y)
        return True
