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
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import WINDOW_CONTEXT, Input
from scene_menu import (
    HEADER_HEIGHT,
    ROW_HEIGHT,
    SceneMenu,
    add_mesh_entries,
    add_named_reference,
    add_primitive_named,
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

    # The keys arrive resolved (`src/main.py`, AD-013 addendum 2026-10-28): the menu knows commands only.
    bindings = build_default_bindings()

    def resolve(inp):
        return bindings.command_for(inp, WINDOW_CONTEXT)

    menu.open(100.0, 500.0, 800, 600)
    assert menu.key(resolve(W)) is False and menu.is_open
    assert menu.key(resolve(W_CTRL)) is False and menu.is_open  # Modifier-Key schließt nicht
    assert menu.key(None) is False and menu.is_open
    assert menu.key(resolve(SPACE)) is True and not menu.is_open

    menu.open(100.0, 500.0, 800, 600)
    assert menu.key(resolve(ESCAPE)) is True and not menu.is_open


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


# -- AD-021 M1 (Q-10): Shift+click adds the row as a Reference ----------------------------


def _row1_y() -> float:
    return 500.0 - HEADER_HEIGHT - ROW_HEIGHT - 5


def test_shift_click_on_a_row_adds_it_instead_of_loading():
    loaded: list = []
    added: list = []
    menu = SceneMenu(scene_entries(), load=loaded.append, add=added.append)
    menu.open(100.0, 500.0, 800, 600)

    assert menu.press(110.0, _row1_y(), add=True) is True

    assert added == [scene_entries()[1]]
    assert loaded == []
    assert not menu.is_open
    menu.open(100.0, 500.0, 800, 600)
    menu.press(110.0, _row1_y())  # a plain click still loads
    assert loaded == [scene_entries()[1]]


def test_shift_click_without_an_add_callback_loads_as_before():
    loaded: list = []
    menu = _menu(loaded)
    menu.open(100.0, 500.0, 800, 600)
    menu.press(110.0, _row1_y(), add=True)
    assert loaded == [scene_entries()[1]]


def test_add_named_reference_adds_the_cube_as_a_reference():
    app = Application()
    app.init_scene("cube")
    edit = app.scene.edit_object_id

    assert add_named_reference(app, "cube") is True

    assert len(app.scene.objects) == 2
    assert app.scene.edit_object_id == edit
    assert app.status_message == "Added 'cube' as Reference"


@pytest.mark.skipif(not _HEAD_ASSET.is_file(), reason="head_basemesh fehlt (examples/meshes/)")
def test_add_named_reference_adds_a_registry_asset_under_its_name():
    app = Application()
    app.init_scene("cube")
    assert add_named_reference(app, "head_basemesh") is True
    (ref,) = [o for o in app.scene.objects.values() if o.id != app.scene.edit_object_id]
    assert ref.name == "head_basemesh"
    assert len(ref.mesh.all_vertex_ids()) == 326


def test_add_named_reference_reports_a_failure_as_status():
    app = Application()
    app.init_scene("cube")
    assert add_named_reference(app, "no_such_asset") is False
    assert app.status_message.startswith("Add 'no_such_asset' failed")
    assert len(app.scene.objects) == 1


def test_refresh_replaces_the_entries_on_every_open():
    """Szenen speichern/laden (2026-10-15): `refresh` liefert die Zeilen bei jedem Öffnen neu
    (neu gespeicherte Dateien erscheinen ohne Neustart)."""
    current = [("a", "b")]
    loaded: list = []
    menu = SceneMenu(("a", "b"), load=loaded.append, refresh=lambda: current[0])

    current[0] = ("new", "a", "b")
    menu.open(100.0, 500.0, 800, 600)

    assert menu.entries == ("new", "a", "b")
    assert menu.rect[3] == HEADER_HEIGHT + 3 * ROW_HEIGHT
    menu.press(110.0, 500.0 - HEADER_HEIGHT - 5)
    assert loaded == ["new"]


# -- Add Mesh (Track A1, 2026-10-23) ---------------------------------------------------------


def test_add_mesh_entries_are_the_four_primitives_in_order():
    assert add_mesh_entries() == ("plane", "cube", "sphere", "cylinder")


def test_add_primitive_named_adds_a_selected_normal_object():
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)

    assert add_primitive_named(app, "sphere") is True

    assert len(app.scene.objects) == 2
    assert app.status_message.startswith("Added 'sphere'")


def test_add_primitive_named_reports_a_failure_as_a_status_line():
    app = Application()
    app.init_scene("cube")

    assert add_primitive_named(app, "teapot") is False

    assert app.status_message == "Add 'teapot' failed: unknown primitive 'teapot'"
    assert len(app.scene.objects) == 1


def test_the_add_mesh_menu_uses_its_own_title_and_a_click_adds_the_row():
    added: list = []
    menu = SceneMenu(
        add_mesh_entries(),
        load=lambda name: added.append(name) or True,
        title="Add Mesh (Shift+A)",
    )
    menu.open(100.0, 300.0, 800, 600)
    x, top, _, _ = menu.rect
    # Row 2 = sphere.
    assert menu.press(x + 10, top - HEADER_HEIGHT - 2 * ROW_HEIGHT - 5) is True
    assert added == ["sphere"]
    assert not menu.is_open
