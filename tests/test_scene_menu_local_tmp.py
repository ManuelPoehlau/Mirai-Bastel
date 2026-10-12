"""TEMPORÄRER lokaler Probe (wird gelöscht, nicht committen).

Derselbe Ablauf wie die Scene-Menü-Tests in `tests/test_main_wiring.py`, aber
ohne `pyglet.options["headless"]` — auf Windows importiert `pyglet.window`
sonst nicht (braucht EGL), die Original-Tests sind hier environment-skipped.
"""

from __future__ import annotations

import importlib.util
import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

pyglet = pytest.importorskip("pyglet")
try:
    from pyglet.window import key, mouse
except Exception as exc:  # pragma: no cover - environment-dependent
    pytest.skip(f"pyglet.window unavailable: {exc}", allow_module_level=True)

from mirai.application import Application
from scene_menu import HEADER_HEIGHT, ROW_HEIGHT, SceneMenu, load_named_scene, scene_entries

_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

_spec = importlib.util.spec_from_file_location("mirai_src_main_tmp", _REPO_ROOT / "src" / "main.py")
main_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(main_module)

WIDTH, HEIGHT = 800, 600
LOADED: list = []


class FakeWindow:
    def __init__(self, width: int = WIDTH, height: int = HEIGHT) -> None:
        self.width = width
        self.height = height
        self.handlers: dict = {}

    def event(self, func):
        self.handlers[func.__name__] = func
        return func

    def clear(self) -> None:
        pass


def build(menu=None):
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    window = FakeWindow()
    main_module.install_handlers(window, app, menu=menu)
    return window, app


def fake_load(name: str) -> bool:
    LOADED.append(name)
    return True


def test_probe_menu_wiring():
    LOADED.clear()

    # 1) SPACE öffnet am Cursor, danach modal.
    menu = SceneMenu(scene_entries(), load=fake_load)
    window, app = build(menu)
    h = window.handlers
    h["on_mouse_motion"](300, 200, 0, 0)
    assert h["on_key_press"](key.SPACE, 0) == pyglet.event.EVENT_HANDLED
    assert menu.is_open and menu.rect[0] == 300 and menu.rect[1] == 200, menu.rect
    assert h["on_key_press"](key.W, 0) == pyglet.event.EVENT_HANDLED
    assert app.transform_command is None
    h["on_mouse_motion"](310, 210, 0, 0)
    assert h["on_mouse_release"](310, 210, mouse.LEFT, 0) == pyglet.event.EVENT_HANDLED
    assert h["on_mouse_scroll"](310, 210, 0, 1) == pyglet.event.EVENT_HANDLED

    # 2) Klick auf Zeile 1 lädt die echte Szene (SPACE ohne Motion = Mitte).
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    window = FakeWindow()
    real_menu = SceneMenu(scene_entries(), load=lambda name: load_named_scene(app, name))
    main_module.install_handlers(window, app, menu=real_menu)
    h = window.handlers
    assert scene_entries()[1] == "head_basemesh"
    h["on_key_press"](key.SPACE, 0)
    assert real_menu.rect[0] == 400 and real_menu.rect[1] == 300, real_menu.rect
    h["on_mouse_press"](410, 300 - HEADER_HEIGHT - ROW_HEIGHT - 5, mouse.LEFT, 0)
    assert not real_menu.is_open
    assert len(app.scene.mesh.all_vertex_ids()) == 326
    assert app.status_message == "Scene: head_basemesh"
    assert not app.selection.vertices
    assert len(app.history) == 0

    # 3) Esc schließt; Klick daneben schließt ohne Laden; Fokusverlust schließt.
    window, app = build(SceneMenu(scene_entries(), load=fake_load))
    h = window.handlers
    h["on_mouse_motion"](40, 40, 0, 0)
    h["on_key_press"](key.SPACE, 0)
    assert h["on_key_press"](key.ESCAPE, 0) == pyglet.event.EVENT_HANDLED
    h["on_key_press"](key.SPACE, 0)
    h["on_mouse_press"](5, 5, mouse.LEFT, 0)
    h["on_key_press"](key.SPACE, 0)
    h["on_deactivate"]()
    assert len(app.scene.mesh.all_vertex_ids()) == 8
    assert LOADED == [], LOADED

    # 4) Ohne Menü: SPACE nur eine Taste; Hover-Klick und Orbit wie zuvor.
    window, app = build(None)
    assert window.handlers["on_key_press"](key.SPACE, 0) == pyglet.event.EVENT_HANDLED
    assert app.status_message == ""
    from mirai.viewport.picking import pick_nearest_vertex

    mesh = app.scene.mesh
    for candidate in sorted(mesh.all_vertex_ids()):
        sx, sy = app.camera.project_to_screen(mesh.vertex_position(candidate), WIDTH, HEIGHT)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == candidate:
            vid = candidate
            break
    else:
        raise AssertionError("kein sichtbarer Vertex")
    window.handlers["on_mouse_motion"](sx, sy, 0, 0)
    assert app.selection.hovered == vid
    window.handlers["on_mouse_press"](sx, sy, mouse.LEFT, 0)
    window.handlers["on_mouse_release"](sx, sy, mouse.LEFT, 0)
    assert app.selection.vertices == {vid}
    yaw = app.camera.yaw
    window.handlers["on_mouse_press"](10, 10, mouse.LEFT, key.MOD_ALT)
    window.handlers["on_mouse_drag"](40, 10, 30, 0, mouse.LEFT, key.MOD_ALT)
    window.handlers["on_mouse_release"](40, 10, mouse.LEFT, key.MOD_ALT)
    assert app.camera.yaw != yaw

    # 5) Kein Menü, solange eine Geste läuft (W gehalten).
    window, app = build(SceneMenu(scene_entries(), load=fake_load))
    h = window.handlers
    h["on_key_press"](key.W, 0)
    assert app.interaction_owner == "transform"
    h["on_key_press"](key.SPACE, 0)
    assert app.interaction_owner == "transform"
    h["on_key_release"](key.W, 0)

    # 6) Registry-Name lädt über denselben Loader wie CLI und Menü.
    app = Application()
    app.init_scene("cube")
    assert load_named_scene(app, "subd_cube") is True
    assert len(app.scene.mesh.all_vertex_ids()) == 26
