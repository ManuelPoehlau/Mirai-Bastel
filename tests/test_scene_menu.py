"""Der temporäre Scene-Loader (`src/scene_menu.py`), headless.

Zustand und Geometrie ohne GL: `open`/`motion`/`press`/`key` werden direkt
gefahren; das Laden abstrahiert über den injizierten `load`-Callback bzw.
läuft für `load_named_scene` durch eine echte `Application` (TraceStore).
`examples/` liegt wie in `tests/test_application_obj_scene` auf `sys.path`,
weil `scene_entries`/`load_named_scene` die Asset-Registry (AD-007) brauchen.
"""

from __future__ import annotations

import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

from mirai.application import Application
from mirai.interaction.input import Input
from scene_menu import (
    HEADER_HEIGHT,
    ROW_HEIGHT,
    SceneMenu,
    load_named_scene,
    scene_entries,
)

_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

_HEAD_ASSET = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"

SPACE = Input("key", "space", frozenset())
ESCAPE = Input("key", "ESCAPE", frozenset())
W = Input("key", "w", frozenset())
W_CTRL = Input("key", "w", frozenset({"ctrl"}))


def _menu(loaded: list) -> SceneMenu:
    def load(name: str) -> bool:
        loaded.append(name)
        return True

    return SceneMenu(scene_entries(), load=load)


def test_entries_are_cube_plus_the_registry_assets():
    from loaders.assets import asset_names

    assert scene_entries() == ("cube",) + tuple(asset_names())


def test_open_places_the_menu_at_the_cursor_and_clamps_it():
    menu = _menu([])

    menu.open(100.0, 300.0, 800, 600)
    assert menu.is_open
    assert menu.rect[0] == 100.0
    assert menu.rect[1] == 300.0

    # Oben rechts: bleibt vollständig im Fenster.
    menu.open(790.0, 590.0, 800, 600)
    x, y, width, height = menu.rect
    assert x + width <= 800
    assert y <= 600
    assert y - height >= 0

    # Unten: klappt über dem Cursor auf, statt unter den Rand zu rutschen.
    menu.open(10.0, 5.0, 800, 600)
    _, y, _, height = menu.rect
    assert y - height >= 0


def test_hover_follows_the_cursor_row_by_row():
    menu = _menu([])
    menu.open(100.0, 500.0, 800, 600)

    menu.motion(110.0, 500.0 - HEADER_HEIGHT - 5)
    assert menu.hover == 0
    menu.motion(110.0, 500.0 - HEADER_HEIGHT - ROW_HEIGHT - 5)
    assert menu.hover == 1
    menu.motion(5.0, 5.0)  # außerhalb
    assert menu.hover == -1


def test_a_click_on_a_row_loads_that_scene_and_closes():
    loaded: list = []
    menu = _menu(loaded)
    menu.open(100.0, 500.0, 800, 600)

    triggered = menu.press(110.0, 500.0 - HEADER_HEIGHT - ROW_HEIGHT - 5)

    assert triggered is True
    assert loaded == [scene_entries()[1]]
    assert not menu.is_open


def test_a_click_outside_closes_without_loading():
    loaded: list = []
    menu = _menu(loaded)
    menu.open(100.0, 500.0, 800, 600)

    assert menu.press(5.0, 5.0) is False

    assert loaded == []
    assert not menu.is_open


def test_space_and_escape_close_but_other_keys_do_not():
    menu = _menu([])

    menu.open(100.0, 500.0, 800, 600)
    assert menu.key(W) is False and menu.is_open
    assert menu.key(W_CTRL) is False and menu.is_open  # Modifier-Key schließt nicht
    assert menu.key(SPACE) is True and not menu.is_open

    menu.open(100.0, 500.0, 800, 600)
    assert menu.key(ESCAPE) is True and not menu.is_open


def test_load_named_scene_loads_the_cube():
    app = Application()
    app.init_scene("cube")

    assert load_named_scene(app, "cube") is True

    assert len(app.scene.mesh.all_vertex_ids()) == 8
    assert app.status_message == "Scene: cube"


@pytest.mark.skipif(not _HEAD_ASSET.is_file(), reason="head_basemesh fehlt (examples/meshes/)")
def test_load_named_scene_swaps_the_mesh_and_reports_failures_as_status():
    app = Application()
    app.init_scene("cube")

    assert load_named_scene(app, "head_basemesh") is True

    assert len(app.scene.mesh.all_vertex_ids()) == 326
    assert app.status_message == "Scene: head_basemesh"

    assert load_named_scene(app, "no_such_scene") is False
    assert "failed" in app.status_message
