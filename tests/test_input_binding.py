"""Input-Mapping-Foundation: Tests für `mirai.interaction.input`/`bindings`.

Migriert aus `experiments/mirai_bastel_viewport_V1/tests/test_input_binding.py`
in den Produktions-Kontext (src/mirai). Prüft die Schicht Input → Binding →
Command des INPUT_COMMAND_TOOL_CONTRACT.md-Vertrags:

- Default-Bindings (inkl. M/R/S-Toolaktivierung, Undo/Redo, Display, Maus)
- geänderte Bindings (User-Overlay) und deren Rücknahme
- mehrere Bindings für dasselbe Command
- `command_for`-Auflösung (Modifier-Diskriminierung)
- Context-Verhalten (topology gewinnt; GLOBAL_CONTEXT-Fallback)
- Serialisierung/Dict-Roundtrip (keymap.json-Format)

Läuft bewusst OHNE pyglet/Fenster/GPU.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import tests._bootstrap  # noqa: F401

from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings, load_keymap_overrides
from mirai.interaction.input import BindingSet, GLOBAL_CONTEXT, Input, TOPOLOGY_CONTEXT


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def _wheel(direction: str) -> Input:
    return Input("wheel", direction)


class DefaultBindingsTests(unittest.TestCase):
    def setUp(self):
        self.bs = build_default_bindings()

    def test_tool_activation_keys(self):
        self.assertEqual(self.bs.command_for(_key("m"), GLOBAL_CONTEXT), cmd.MOVE)
        self.assertEqual(self.bs.command_for(_key("r"), GLOBAL_CONTEXT), cmd.ROTATE)
        self.assertEqual(self.bs.command_for(_key("s"), GLOBAL_CONTEXT), cmd.SCALE)

    def test_history_keys(self):
        self.assertEqual(self.bs.command_for(_key("z", "ctrl"), GLOBAL_CONTEXT), cmd.UNDO)
        self.assertEqual(self.bs.command_for(_key("y", "ctrl"), GLOBAL_CONTEXT), cmd.REDO)

    def test_cancel_and_clear_keys(self):
        self.assertEqual(self.bs.command_for(_key("ESCAPE"), GLOBAL_CONTEXT), cmd.CANCEL)
        self.assertEqual(
            self.bs.command_for(_key("a", "alt"), GLOBAL_CONTEXT), cmd.CLEAR_SELECTION
        )

    def test_selection_mode_keys(self):
        for value in ("v", "1"):
            self.assertEqual(self.bs.command_for(_key(value)), cmd.SET_VERTEX_MODE)
        for value in ("e", "2"):
            self.assertEqual(self.bs.command_for(_key(value)), cmd.SET_EDGE_MODE)
        for value in ("f", "3"):
            self.assertEqual(self.bs.command_for(_key(value)), cmd.SET_FACE_MODE)

    def test_display_keys(self):
        self.assertEqual(self.bs.command_for(_key("o")), cmd.CYCLE_DISPLAY_MODE)
        self.assertEqual(
            self.bs.command_for(_key("w")), cmd.TOGGLE_WIREFRAME_OVERLAY
        )

    def test_mouse_bindings(self):
        self.assertEqual(self.bs.command_for(_mouse("LEFT")), cmd.SELECT)
        self.assertEqual(self.bs.command_for(_mouse("RIGHT")), cmd.ORBIT)
        self.assertEqual(self.bs.command_for(_mouse("MIDDLE")), cmd.PAN)
        self.assertEqual(self.bs.command_for(_wheel("UP")), cmd.ZOOM)
        self.assertEqual(self.bs.command_for(_wheel("DOWN")), cmd.ZOOM)

    def test_unbound_input_resolves_to_none(self):
        self.assertIsNone(self.bs.command_for(_key("x")))


class BindingOverrideTests(unittest.TestCase):
    def test_user_override_shadows_default(self):
        bs = build_default_bindings()
        bs.bind(_key("g"), cmd.MOVE)
        self.assertEqual(bs.command_for(_key("g")), cmd.MOVE)

    def test_unbind_restores_default(self):
        bs = build_default_bindings()
        bs.bind(_key("g"), cmd.MOVE)
        self.assertTrue(bs.unbind(_key("g")))
        self.assertIsNone(bs.command_for(_key("g")))

    def test_multiple_bindings_for_same_command(self):
        bs = BindingSet()
        bs.set_default(_key("m"), cmd.MOVE)
        bs.set_default(_key("g"), cmd.MOVE)
        self.assertEqual(bs.command_for(_key("m")), cmd.MOVE)
        self.assertEqual(bs.command_for(_key("g")), cmd.MOVE)

    def test_modifier_discrimination(self):
        bs = build_default_bindings()
        # 'z' ohne Modifier ist ungebunden; Strg+Z ist Undo.
        self.assertIsNone(bs.command_for(_key("z")))
        self.assertEqual(bs.command_for(_key("z", "ctrl")), cmd.UNDO)


class ContextResolutionTests(unittest.TestCase):
    def test_topology_context_wins(self):
        bs = build_default_bindings()
        self.assertEqual(bs.command_for(_key("s"), TOPOLOGY_CONTEXT), cmd.SPLIT_EDGE)
        self.assertEqual(bs.command_for(_key("k"), TOPOLOGY_CONTEXT), cmd.COLLAPSE)
        self.assertEqual(bs.command_for(_key("l"), TOPOLOGY_CONTEXT), cmd.EDGE_LOOP)
        self.assertEqual(bs.command_for(_key("r"), TOPOLOGY_CONTEXT), cmd.EDGE_RING)

    def test_global_fallback_in_topology_context(self):
        bs = build_default_bindings()
        self.assertEqual(bs.command_for(_key("v"), TOPOLOGY_CONTEXT), cmd.SET_VERTEX_MODE)
        self.assertEqual(bs.command_for(_key("z", "ctrl"), TOPOLOGY_CONTEXT), cmd.UNDO)

    def test_global_scale_is_not_topology_split(self):
        # Im default/global context ist 's' Scale, im Topology-Kontext SplitEdge.
        bs = build_default_bindings()
        self.assertEqual(bs.command_for(_key("s"), GLOBAL_CONTEXT), cmd.SCALE)
        self.assertEqual(bs.command_for(_key("s"), TOPOLOGY_CONTEXT), cmd.SPLIT_EDGE)


class SerializationTests(unittest.TestCase):
    def test_dict_roundtrip_preserves_user_bindings(self):
        bs = build_default_bindings()
        bs.bind(_key("g"), cmd.REDO, context=TOPOLOGY_CONTEXT)
        bs.bind(_mouse("MIDDLE", "shift"), cmd.ORBIT)
        data = bs.to_dict()
        restored = BindingSet.from_dict(data)
        merged = build_default_bindings()
        merged.add_overrides(restored)
        self.assertEqual(merged.command_for(_key("g"), TOPOLOGY_CONTEXT), cmd.REDO)
        self.assertEqual(merged.command_for(_mouse("MIDDLE", "shift")), cmd.ORBIT)
        # Defaults unverändert.
        self.assertEqual(merged.command_for(_key("s"), TOPOLOGY_CONTEXT), cmd.SPLIT_EDGE)
        self.assertEqual(merged.command_for(_key("v")), cmd.SET_VERTEX_MODE)

    def test_json_roundtrip(self):
        bs = BindingSet()
        bs.bind(_key("g"), cmd.MOVE)
        restored = BindingSet.from_dict(json.loads(bs.to_json()))
        self.assertEqual(restored.command_for(_key("g")), cmd.MOVE)

    def test_load_keymap_overrides_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keymap.json"
            path.write_text(
                json.dumps(
                    {
                        "bindings": [
                            {
                                "input": {"kind": "key", "value": "g", "modifiers": []},
                                "command": cmd.MOVE,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            bs = build_default_bindings()
            load_keymap_overrides(bs, path)
            self.assertEqual(bs.command_for(_key("g")), cmd.MOVE)

    def test_missing_keymap_file_is_noop(self):
        bs = build_default_bindings()
        before = bs.command_for(_key("g"))
        load_keymap_overrides(bs, Path("does-not-exist.json"))
        self.assertEqual(bs.command_for(_key("g")), before)


if __name__ == "__main__":
    unittest.main()