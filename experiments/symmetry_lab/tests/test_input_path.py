"""Input-Pfad mit echten pyglet-Konstanten, ohne Fenster (Handoff Slice 2 §4.5, Slice 3 §4.2).

pyglet-Button/Taste/Modifier → `mirai.pyglet_input` → `app.bindings` im
Lab-Kontext → `LabDispatcher`. Headless-Behandlung: siehe `_pyglet_headless.py`.
"""

from __future__ import annotations

import pytest

from ._pyglet_headless import import_pyglet

import_pyglet()
from pyglet.window import key as _key, mouse as _mouse  # noqa: E402

from mirai.application import Application  # noqa: E402
from mirai.interaction import commands as cmd  # noqa: E402
from mirai.pyglet_input import key_from_pyglet, mouse_from_pyglet, wheel_from_pyglet  # noqa: E402

from symmetry_lab.lab_bindings import SYMMETRY_CYCLE, apply_lab_bindings  # noqa: E402
from symmetry_lab.lab_dispatch import LabDispatcher, MoveState  # noqa: E402
from symmetry_lab.lab_scene import load_asset_into  # noqa: E402


@pytest.fixture
def dispatcher():
    app = Application()
    apply_lab_bindings(app.bindings)
    load_asset_into(app, "subd_cube")
    return LabDispatcher(app, 1280, 800)


@pytest.mark.parametrize(
    "button,modifiers,expected",
    [
        (_mouse.LEFT, _key.MOD_ALT, cmd.ORBIT),
        (_mouse.LEFT, _key.MOD_SHIFT, cmd.PAN),
        (_mouse.MIDDLE, 0, cmd.PAN),
        (_mouse.LEFT, 0, cmd.SELECT),
        (_mouse.RIGHT, 0, None),
        # Lock-Tasten-Bits ignoriert pyglet_input — Alt+LMB bleibt Orbit.
        (_mouse.LEFT, _key.MOD_ALT | _key.MOD_NUMLOCK, cmd.ORBIT),
    ],
)
def test_pyglet_press_resolves_to_lab_gesture(dispatcher, button, modifiers, expected):
    dispatcher.press(mouse_from_pyglet(button, modifiers))
    assert dispatcher.active_command == expected


@pytest.mark.parametrize("scroll_y,closer", [(1.0, True), (-1.0, False)])
def test_pyglet_scroll_zooms(dispatcher, scroll_y, closer):
    d = dispatcher.app.camera.distance
    dispatcher.scroll(wheel_from_pyglet(scroll_y))
    assert (dispatcher.app.camera.distance < d) is closer


@pytest.mark.parametrize(
    "symbol,modifiers,expected",
    [
        (_key.S, _key.MOD_SHIFT, SYMMETRY_CYCLE),
        (_key.S, _key.MOD_SHIFT | _key.MOD_CAPSLOCK, SYMMETRY_CYCLE),
        (_key.Q, 0, cmd.MOVE),
        (_key.ESCAPE, 0, cmd.CANCEL),
        (_key.Z, _key.MOD_CTRL, cmd.UNDO),
        (_key.Y, _key.MOD_CTRL, cmd.REDO),
    ],
)
def test_pyglet_key_resolves_in_lab_context(dispatcher, symbol, modifiers, expected):
    assert dispatcher.resolve(key_from_pyglet(symbol, modifiers)) == expected


def test_pyglet_keys_drive_cycle_and_move(dispatcher):
    app = dispatcher.app
    assert dispatcher.key(key_from_pyglet(_key.S, _key.MOD_SHIFT)) is True
    assert app.scene.mesh.symmetry_definition is not None
    app.scene.selection.set({min(app.scene.mesh.all_vertex_ids())})
    assert dispatcher.key(key_from_pyglet(_key.Q, 0)) is True
    assert dispatcher.move_state is MoveState.ARMED
    assert dispatcher.key(key_from_pyglet(_key.ESCAPE, 0)) is True
    assert dispatcher.move_state is MoveState.READY
    # Leerlauf: ESC nicht behandelt → Fenster lässt pyglet schließen.
    assert dispatcher.key(key_from_pyglet(_key.ESCAPE, 0)) is False
