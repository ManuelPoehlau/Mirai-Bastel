"""Tests für `mirai.pyglet_input` (WP-SYM-LAB-01 Slice 1).

Headless-Import-Problem (Handoff §4.5): `from pyglet.window import key`
scheitert auf Linux ohne Display mit `NoSuchDisplayException`, weil pyglet
beim Import ein Shadow-Window über den Standard-(X11-)Display-Backend
anlegt. Mit `pyglet.options["headless"] = True` **vor** dem ersten
`pyglet.window`-Import verwendet pyglet stattdessen das EGL-Headless-
Backend, das ohne laufenden X-Server funktioniert (auf Linux verifiziert;
Windows-Verhalten laut Handoff nicht verifiziert, dort ist kein Display-
Problem zu erwarten, da dieser Test-Modul-weite Header dort ein no-op ist,
weil ein Fenstersystem vorhanden ist).

Gewählte Lösung: Dieses Test-Modul setzt `pyglet.options["headless"] = True`
ganz oben, vor jedem `pyglet`/`pyglet.window`-Import — sowohl im Testmodul
selbst als auch transitiv in `mirai.pyglet_input` (das pyglet lazy
importiert, siehe dortigen Modul-Docstring). Die Option ist global und
prozessweit; da `mirai.pyglet_input` pyglet erst beim ersten Aufruf einer
`*_from_pyglet`-Funktion importiert, reicht es, die Option hier zu setzen,
bevor irgendeine dieser Funktionen zum ersten Mal aufgerufen wird.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

import tests._bootstrap  # noqa: F401

pyglet = pytest.importorskip("pyglet")
pyglet.options["headless"] = True
from pyglet.window import key as _key, mouse as _mouse  # noqa: E402

from mirai.pyglet_input import (  # noqa: E402
    key_from_pyglet,
    mouse_from_pyglet,
    wheel_from_pyglet,
)
from mirai.interaction.input import GLOBAL_CONTEXT, Input  # noqa: E402
from mirai.interaction.bindings import build_default_bindings  # noqa: E402
from mirai.interaction import commands as cmd  # noqa: E402


class TestKeyFromPyglet:
    def test_letter_keys_lowercase(self):
        inp = key_from_pyglet(_key.Q, 0)
        assert inp == Input("key", "q", frozenset())

    def test_digit_keys(self):
        inp = key_from_pyglet(_key._1, 0)
        assert inp == Input("key", "1", frozenset())

    def test_escape_uppercase(self):
        inp = key_from_pyglet(_key.ESCAPE, 0)
        assert inp == Input("key", "ESCAPE", frozenset())

    def test_tab_lowercase(self):
        inp = key_from_pyglet(_key.TAB, 0)
        assert inp == Input("key", "tab", frozenset())

    def test_space_lowercase(self):
        inp = key_from_pyglet(_key.SPACE, 0)
        assert inp == Input("key", "space", frozenset())

    @pytest.mark.parametrize(
        "symbol,value",
        [
            (_key.UP, "up"),
            (_key.DOWN, "down"),
            (_key.LEFT, "left"),
            (_key.RIGHT, "right"),
        ],
    )
    def test_arrow_keys_lowercase(self, symbol, value):
        inp = key_from_pyglet(symbol, 0)
        assert inp == Input("key", value, frozenset())

    def test_unknown_symbol_returns_none(self):
        assert key_from_pyglet(999999, 0) is None

    def test_ctrl_modifier(self):
        inp = key_from_pyglet(_key.Z, _key.MOD_CTRL)
        assert inp.modifiers == frozenset({"ctrl"})

    def test_shift_modifier(self):
        inp = key_from_pyglet(_key.L, _key.MOD_SHIFT)
        assert inp.modifiers == frozenset({"shift"})

    def test_alt_modifier(self):
        inp = key_from_pyglet(_key.E, _key.MOD_ALT)
        assert inp.modifiers == frozenset({"alt"})

    def test_ctrl_shift_combined(self):
        mods = _key.MOD_CTRL | _key.MOD_SHIFT
        inp = key_from_pyglet(_key.Z, mods)
        assert inp.modifiers == frozenset({"ctrl", "shift"})

    def test_foreign_modifiers_ignored(self):
        mods = _key.MOD_CTRL | _key.MOD_NUMLOCK | _key.MOD_CAPSLOCK
        inp = key_from_pyglet(_key.Z, mods)
        assert inp.modifiers == frozenset({"ctrl"})


class TestMouseFromPyglet:
    @pytest.mark.parametrize(
        "button,value",
        [
            (_mouse.LEFT, "LEFT"),
            (_mouse.MIDDLE, "MIDDLE"),
            (_mouse.RIGHT, "RIGHT"),
        ],
    )
    def test_known_buttons(self, button, value):
        inp = mouse_from_pyglet(button, 0)
        assert inp == Input("mouse", value, frozenset())

    def test_known_buttons_with_modifier(self):
        inp = mouse_from_pyglet(_mouse.LEFT, _key.MOD_CTRL)
        assert inp == Input("mouse", "LEFT", frozenset({"ctrl"}))

    def test_unknown_button_returns_none(self):
        assert mouse_from_pyglet(999999, 0) is None


class TestWheelFromPyglet:
    def test_positive_is_up(self):
        assert wheel_from_pyglet(1.0) == Input("wheel", "UP", frozenset())

    def test_negative_is_down(self):
        assert wheel_from_pyglet(-1.0) == Input("wheel", "DOWN", frozenset())

    def test_zero_is_none(self):
        assert wheel_from_pyglet(0) is None


class TestIntegrationWithDefaultBindings:
    """Belegt, dass die Value-Strings zu `build_default_bindings()` passen."""

    def test_q_is_move(self):
        bindings = build_default_bindings()
        inp = key_from_pyglet(_key.Q, 0)
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == cmd.MOVE

    def test_ctrl_z_is_undo(self):
        bindings = build_default_bindings()
        inp = key_from_pyglet(_key.Z, _key.MOD_CTRL)
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == cmd.UNDO

    def test_ctrl_y_is_redo(self):
        bindings = build_default_bindings()
        inp = key_from_pyglet(_key.Y, _key.MOD_CTRL)
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == cmd.REDO

    def test_escape_is_cancel(self):
        bindings = build_default_bindings()
        inp = key_from_pyglet(_key.ESCAPE, 0)
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == cmd.CANCEL

    def test_lmb_is_select(self):
        bindings = build_default_bindings()
        inp = mouse_from_pyglet(_mouse.LEFT, 0)
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == cmd.SELECT


class TestSecondContextWithoutBindingSetChange:
    """Belegt den Checkpoint-Befund: ein beliebiger Kontext-String braucht
    keine Änderung an `BindingSet` — alles über die öffentliche API."""

    SYMMETRY_LAB_CONTEXT = "symmetry_lab"

    def test_context_specific_binding_wins(self):
        bindings = build_default_bindings()
        inp = key_from_pyglet(_key.Q, 0)
        bindings.set_default(inp, "SymmetryLabSpecialMove", context=self.SYMMETRY_LAB_CONTEXT)

        assert bindings.command_for(inp, self.SYMMETRY_LAB_CONTEXT) == "SymmetryLabSpecialMove"
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == cmd.MOVE

    def test_unbound_input_falls_back_to_global(self):
        bindings = build_default_bindings()
        inp = key_from_pyglet(_key.Z, _key.MOD_CTRL)

        assert bindings.command_for(inp, self.SYMMETRY_LAB_CONTEXT) == cmd.UNDO

    def test_explicit_unbind_suppresses_fallback(self):
        bindings = build_default_bindings()
        inp = key_from_pyglet(_key.Z, _key.MOD_CTRL)
        bindings.bind(inp, None, context=self.SYMMETRY_LAB_CONTEXT)

        assert bindings.command_for(inp, self.SYMMETRY_LAB_CONTEXT) is None
        assert bindings.command_for(inp, GLOBAL_CONTEXT) == cmd.UNDO


class TestInteractionStaysPygletFree:
    """Grenz-Invariante (Handoff §7): `import mirai.interaction` darf pyglet
    nicht laden — die Übersetzungsschicht ist ein separates Modul."""

    def test_pyglet_not_imported_by_mirai_interaction(self):
        import os
        from pathlib import Path

        repo_root = Path(__file__).resolve().parent.parent
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(repo_root / "src"), str(repo_root)])

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import mirai.interaction; "
                "print('pyglet' in sys.modules)",
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "False"
