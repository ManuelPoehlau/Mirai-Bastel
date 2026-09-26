"""Load pyglet for tests (rebuilt after `experiments/symmetry_lab/tests/_pyglet_headless.py`,
not imported — E1).

`pyglet.options["headless"] = True` must be set before the first
`pyglet.window` import, and only when there really is no display (Linux
without `DISPLAY`/`WAYLAND_DISPLAY`): pyglet's headless branch loads EGL on
every platform, which Windows usually lacks. With a display (Windows, desktop
Linux, Xvfb) the normal window system is used.
"""

from __future__ import annotations

import os
import sys

import pytest


def needs_headless() -> bool:
    if not sys.platform.startswith("linux"):
        return False
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def import_pyglet():
    """Imports pyglet (skip if not installed) and sets headless if needed."""
    pyglet = pytest.importorskip("pyglet")
    if needs_headless():
        pyglet.options["headless"] = True
    return pyglet
