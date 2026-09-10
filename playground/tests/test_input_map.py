"""Headless-Tests für PlaygroundInputMap (AP-03 Phase 0).

Kein GL, kein Fenster, kein pyglet-Display. Prüft:
    1. Default-Bindings entsprechen dem Dokumentierten (D/Z/V, LMB, Shift/Ctrl/Alt)
    2. Einzelne Felder können beim Konstruktor überschrieben werden
    3. Alle anderen Felder behalten ihren Default bei Teilüberschreibung
    4. PlaygroundApp hat kein input_map-Feld (liegt nur im Window)
    5. InputMap-Felder sind plain int (pyglet-Konstanten)
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
for _p in (str(_REPO_SRC), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pyglet.window import key, mouse  # noqa: E402

from playground.app import PlaygroundApp  # noqa: E402
from playground.input_map import PlaygroundInputMap  # noqa: E402


class TestDefaultBindings:

    def test_display_cycle_default(self):
        assert PlaygroundInputMap().display_cycle == key.D

    def test_wire_overlay_default(self):
        assert PlaygroundInputMap().wire_overlay == key.Z

    def test_show_vertices_default(self):
        assert PlaygroundInputMap().show_vertices == key.V

    def test_select_button_default(self):
        assert PlaygroundInputMap().select_button == mouse.LEFT

    def test_add_modifier_default(self):
        assert PlaygroundInputMap().add_modifier == key.MOD_SHIFT

    def test_remove_modifier_default(self):
        assert PlaygroundInputMap().remove_modifier == key.MOD_CTRL

    def test_toggle_modifier_default(self):
        assert PlaygroundInputMap().toggle_modifier == key.MOD_ALT


class TestCustomBindings:

    def test_override_display_cycle(self):
        imap = PlaygroundInputMap(display_cycle=key.M)
        assert imap.display_cycle == key.M

    def test_override_wire_overlay(self):
        imap = PlaygroundInputMap(wire_overlay=key.W)
        assert imap.wire_overlay == key.W

    def test_override_show_vertices(self):
        imap = PlaygroundInputMap(show_vertices=key.P)
        assert imap.show_vertices == key.P

    def test_override_select_button(self):
        imap = PlaygroundInputMap(select_button=mouse.RIGHT)
        assert imap.select_button == mouse.RIGHT

    def test_partial_override_leaves_others_at_default(self):
        imap = PlaygroundInputMap(display_cycle=key.M)
        assert imap.wire_overlay == key.Z
        assert imap.show_vertices == key.V
        assert imap.select_button == mouse.LEFT
        assert imap.add_modifier == key.MOD_SHIFT

    def test_all_fields_overridable(self):
        imap = PlaygroundInputMap(
            display_cycle=key.NUM_1,
            wire_overlay=key.NUM_2,
            show_vertices=key.NUM_3,
            select_button=mouse.RIGHT,
            add_modifier=key.MOD_CTRL,
            remove_modifier=key.MOD_SHIFT,
            toggle_modifier=key.MOD_WINDOWS,
        )
        assert imap.display_cycle == key.NUM_1
        assert imap.wire_overlay == key.NUM_2
        assert imap.show_vertices == key.NUM_3
        assert imap.select_button == mouse.RIGHT
        assert imap.add_modifier == key.MOD_CTRL
        assert imap.remove_modifier == key.MOD_SHIFT
        assert imap.toggle_modifier == key.MOD_WINDOWS


class TestFieldTypes:

    def test_all_fields_are_int(self):
        imap = PlaygroundInputMap()
        for field_name, value in vars(imap).items():
            assert isinstance(value, int), f"{field_name} is not int: {type(value)}"


class TestAppDoesNotHaveInputMap:

    def test_app_has_no_input_map(self):
        app = PlaygroundApp()
        assert not hasattr(app, "input_map")
