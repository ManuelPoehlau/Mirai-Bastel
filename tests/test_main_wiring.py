"""`src/main.py` wiring, headless (WP-SYM-LAB-03 H6).

`install_handlers(window, app)` is driven with a stand-in window (records the
`@window.event` handlers, no GL) and a headless `Application` (TraceStore).
Proves the split wiring still translates every event as `main()` did, so a
second host (the Symmetry Lab) can reuse it. pyglet's key/mouse constants
need pyglet's window module; it is imported headless as in
`tests/test_pyglet_input.py` and the module skips if that is unavailable.
"""

from __future__ import annotations

import importlib.util

import pytest

import tests._bootstrap  # noqa: F401

from tests._bootstrap import _SRC

from mirai.application import Application
from mirai.interaction import commands
from mirai.viewport.picking import pick_nearest_vertex

pyglet = pytest.importorskip("pyglet")
pyglet.options["headless"] = True
try:
    from pyglet.window import key, mouse  # noqa: E402
except Exception as exc:  # pragma: no cover - environment-dependent (no EGL)
    pytest.skip(f"pyglet.window unavailable: {exc}", allow_module_level=True)

WIDTH, HEIGHT = 800, 600


def _load_main():
    spec = importlib.util.spec_from_file_location("mirai_src_main", _SRC / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


main_module = _load_main()


class FakeWindow:
    """Only what `install_handlers` touches: `event`, `width`/`height`, `clear`."""

    def __init__(self, width: int = WIDTH, height: int = HEIGHT) -> None:
        self.width = width
        self.height = height
        self.handlers: dict = {}
        self.cleared = 0

    def event(self, func):
        self.handlers[func.__name__] = func
        return func

    def clear(self) -> None:
        self.cleared += 1


@pytest.fixture
def wired():
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    window = FakeWindow()
    main_module.install_handlers(window, app)
    return window, app


def _visible_vertex_screen(app):
    mesh = app.scene.mesh
    for vid in sorted(mesh.all_vertex_ids()):
        sx, sy = app.camera.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == vid:
            return vid, (sx, sy)
    raise AssertionError("no visible vertex")


def test_install_handlers_registers_every_main_handler(wired):
    window, _ = wired
    assert set(window.handlers) == {
        "on_resize",
        "on_key_press",
        "on_key_release",
        "on_deactivate",
        "on_mouse_press",
        "on_mouse_drag",
        "on_mouse_release",
        "on_mouse_motion",
        "on_mouse_leave",
        "on_mouse_scroll",
        "on_draw",
    }


def test_main_composes_the_three_parts():
    # H6: main() = create_window + scene set-up + install_handlers + run.
    names = main_module.main.__code__.co_names
    for part in ("create_window", "install_handlers", "run"):
        assert part in names
    assert set(main_module.GL_TYPES) == {
        "store_type",
        "point_overlay_type",
        "line_overlay_type",
        "face_overlay_type",
    }


def test_resize_sets_viewport_size_from_window(wired):
    window, app = wired
    window.width, window.height = 640, 480
    assert window.handlers["on_resize"](640, 480) == pyglet.event.EVENT_HANDLED
    assert (app.viewport_width, app.viewport_height) == (640, 480)


def test_hover_click_and_key_path(wired):
    window, app = wired
    h = window.handlers
    vid, (sx, sy) = _visible_vertex_screen(app)
    h["on_mouse_motion"](sx, sy, 0, 0)
    assert app.selection.hovered == vid
    h["on_mouse_press"](sx, sy, mouse.LEFT, 0)
    h["on_mouse_release"](sx, sy, mouse.LEFT, 0)
    assert app.selection.vertices == {vid}
    assert h["on_key_press"](key.W, 0) == pyglet.event.EVENT_HANDLED
    assert app.transform_command == commands.MOVE
    h["on_key_release"](key.W, 0)
    assert app.transform_command is None
    h["on_mouse_leave"](sx, sy)
    assert app.selection.hovered is None


def test_escape_is_handled_and_only_cancels(wired):
    window, app = wired
    vid, (sx, sy) = _visible_vertex_screen(app)
    window.handlers["on_mouse_motion"](sx, sy, 0, 0)
    window.handlers["on_key_press"](key.W, 0)
    assert window.handlers["on_key_press"](key.ESCAPE, 0) == pyglet.event.EVENT_HANDLED
    assert app.transform_command is None
    assert app.status_message == "Move disarmed"


def test_shift_tracking_and_deactivate(wired, monkeypatch):
    window, app = wired
    calls = []
    monkeypatch.setattr(app, "set_shift_held", lambda held: calls.append(held))
    window.handlers["on_key_press"](key.LSHIFT, 0)
    window.handlers["on_key_press"](key.RSHIFT, 0)
    window.handlers["on_key_release"](key.LSHIFT, 0)
    window.handlers["on_deactivate"]()
    assert calls == [True, True, True, False]


def test_drag_orbits_and_scroll_zooms(wired):
    window, app = wired
    h = window.handlers
    yaw, distance = app.camera.yaw, app.camera.distance
    h["on_mouse_press"](10, 10, mouse.LEFT, key.MOD_ALT)
    h["on_mouse_drag"](40, 10, 30, 0, mouse.LEFT, key.MOD_ALT)
    h["on_mouse_release"](40, 10, mouse.LEFT, key.MOD_ALT)
    assert app.camera.yaw != yaw
    h["on_mouse_scroll"](10, 10, 0, 1)
    assert app.camera.distance < distance
