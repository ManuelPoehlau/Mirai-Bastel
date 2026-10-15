"""`src/main.py` wiring, headless (WP-SYM-LAB-03 H6).

`install_handlers(window, app, menu=None)` is driven with a stand-in window
(records the `@window.event` handlers, no GL) and a headless `Application`
(TraceStore). The last tests wire the temporary SPACE scene menu
(`src/scene_menu.py`) through the same entry point.
Proves the split wiring still translates every event as `main()` did, so a
second host (the Symmetry Lab) can reuse it. pyglet's key/mouse constants
need pyglet's window module; it is imported headless as in
`tests/test_pyglet_input.py` and the module skips if that is unavailable.
"""

from __future__ import annotations

import importlib.util

import pytest

import tests._bootstrap  # noqa: F401

from tests._bootstrap import _REPO_ROOT, _SRC

from mirai.application import Application
from mirai.interaction import commands
from mirai.viewport.picking import pick_nearest_vertex
from scene_menu import (
    HEADER_HEIGHT,
    ROW_HEIGHT,
    SceneMenu,
    add_named_reference,
    load_named_scene,
    scene_entries,
)

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
        "soft_overlay_type",  # WP-SOFT-01 S2b: the influence-band sink
        "symmetry_overlay_type",  # AD-SYM-04 A2: plane outline + problem markers
    }
    assert main_module.GL_TYPES["soft_overlay_type"].__name__ == "GLSoftBandOverlay"
    assert main_module.GL_TYPES["symmetry_overlay_type"].__name__ == "GLSymmetryOverlay"


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


# -- Temporary scene menu (src/scene_menu.py, PROVISIONAL) ------------------

_HEAD_ASSET = _REPO_ROOT / "examples" / "meshes" / "head_basemesh.obj"


@pytest.fixture
def menu_wired():
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    window = FakeWindow()
    loaded: list = []

    def load(name: str) -> bool:
        loaded.append(name)
        return True

    menu = SceneMenu(scene_entries(), load=load)
    main_module.install_handlers(window, app, menu=menu)
    return window, app, menu, loaded


def test_space_opens_the_scene_menu_at_the_cursor_and_is_modal(menu_wired):
    window, app, menu, _ = menu_wired
    h = window.handlers
    h["on_mouse_motion"](300, 200, 0, 0)

    assert h["on_key_press"](key.SPACE, 0) == pyglet.event.EVENT_HANDLED

    assert menu.is_open
    assert menu.rect[0] == 300
    assert menu.rect[1] == 200
    # Modal: W erreicht die Application nicht mehr.
    assert h["on_key_press"](key.W, 0) == pyglet.event.EVENT_HANDLED
    assert app.transform_command is None


def test_a_click_on_a_row_loads_that_scene(menu_wired):
    window, app, menu, loaded = menu_wired
    h = window.handlers
    h["on_key_press"](key.SPACE, 0)
    mx, my, _, _ = menu.rect

    # Zeile 1 = head_basemesh (Reihenfolge: cube + Registry).
    h["on_mouse_press"](mx + 10, my - HEADER_HEIGHT - ROW_HEIGHT - 5, mouse.LEFT, 0)

    assert loaded == ["head_basemesh"]
    assert not menu.is_open


@pytest.mark.skipif(not _HEAD_ASSET.is_file(), reason="head_basemesh fehlt (examples/meshes/)")
def test_a_loaded_scene_reaches_the_application():
    # Echter Loader (kein Zähler-Stub): die Szene muss tatsächlich wechseln.
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    window = FakeWindow()
    menu = SceneMenu(scene_entries(), load=lambda name: load_named_scene(app, name))
    main_module.install_handlers(window, app, menu=menu)
    h = window.handlers

    h["on_key_press"](key.SPACE, 0)
    mx, my, _, _ = menu.rect
    h["on_mouse_press"](mx + 10, my - HEADER_HEIGHT - ROW_HEIGHT - 5, mouse.LEFT, 0)

    assert len(app.scene.mesh.all_vertex_ids()) == 326
    assert not app.selection.vertices
    assert app.status_message == "Scene: head_basemesh"


def test_escape_and_a_click_outside_close_the_menu(menu_wired):
    window, app, menu, loaded = menu_wired
    h = window.handlers
    h["on_mouse_motion"](40, 40, 0, 0)

    h["on_key_press"](key.SPACE, 0)
    assert h["on_key_press"](key.ESCAPE, 0) == pyglet.event.EVENT_HANDLED
    assert not menu.is_open

    h["on_key_press"](key.SPACE, 0)
    h["on_mouse_press"](5, 5, mouse.LEFT, 0)

    assert not menu.is_open
    assert loaded == []
    assert len(app.scene.mesh.all_vertex_ids()) == 8


def test_deactivate_closes_the_menu(menu_wired):
    window, app, menu, _ = menu_wired
    window.handlers["on_key_press"](key.SPACE, 0)
    assert menu.is_open

    window.handlers["on_deactivate"]()

    assert not menu.is_open


def test_shift_click_on_a_row_adds_it_as_a_reference():
    """AD-021 M1 (Q-10, Q-9): Shift+click in the open menu adds instead of loading; the scene,
    its edit object and the camera stay."""
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    window = FakeWindow()
    loaded: list = []
    menu = SceneMenu(
        scene_entries(),
        load=loaded.append,
        add=lambda name: add_named_reference(app, name),
    )
    main_module.install_handlers(window, app, menu=menu)
    h = window.handlers
    edit, eye = app.scene.edit_object_id, app.camera.eye()

    h["on_key_press"](key.SPACE, 0)
    mx, my, _, _ = menu.rect
    # Row 0 = cube.
    h["on_mouse_press"](mx + 10, my - HEADER_HEIGHT - 5, mouse.LEFT, key.MOD_SHIFT)

    assert loaded == []
    assert len(app.scene.objects) == 2
    assert app.scene.edit_object_id == edit
    assert app.camera.eye() == eye
    assert app.status_message == "Added 'cube' as Reference"
