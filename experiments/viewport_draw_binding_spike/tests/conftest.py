"""Shared fixtures for the draw-binding spike test suite.

Needs a real GL context (Xvfb or a real display) — `xvfb-run -a pytest
experiments/viewport_draw_binding_spike/tests`. Tests skip cleanly (not
fail) when no context can be created, since this suite proves a live-GL
behavior, not something meaningfully fakeable headless (see README
"Why not TraceStore for these tests").
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(_ROOT / "src"), str(_ROOT / "examples"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")


@pytest.fixture(scope="session")
def gl_window():
    try:
        win = pyglet.window.Window(width=128, height=128, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


@pytest.fixture()
def cube_mesh(gl_window):
    from mirai.scene_factory import create_cube

    return create_cube(size=2.0)
