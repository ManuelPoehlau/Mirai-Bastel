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

Gate 6 (Input Config) ergänzt:

- validiertes Laden der externen `keymap.json` (Pflicht-`schemaVersion`,
  kontrollierter `KeymapConfigError` bei ungültiger Konfiguration)
- Override von Default-Bindings über gültiges JSON
- explizites Unbind über `command: null` (unterdrückt die Default-Auflösung)
- Duplikate im selben Context: der spätere Eintrag gewinnt
- schemaVersion als Bestandteil des Dict/JSON-Roundtrips

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
from mirai.interaction.input import (
    KEYMAP_SCHEMA_VERSION,
    KeymapConfigError,
    BindingSet,
    GLOBAL_CONTEXT,
    Input,
    TOPOLOGY_CONTEXT,
)


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def _wheel(direction: str) -> Input:
    return Input("wheel", direction)


def _entry(context: str, kind: str, value, modifiers, command) -> dict:
    """Ein keymap.json-Bindungs-Eintrag im Gate-6-Format."""
    return {
        "context": context,
        "input": {"kind": kind, "value": value, "modifiers": modifiers},
        "command": command,
    }


def _keymap(*entries: dict) -> dict:
    """Ein keymap.json-Dokument mit gültiger schemaVersion."""
    return {"schemaVersion": KEYMAP_SCHEMA_VERSION, "bindings": list(entries)}


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
                        "schemaVersion": KEYMAP_SCHEMA_VERSION,
                        "bindings": [
                            {
                                "input": {"kind": "key", "value": "g", "modifiers": []},
                                "command": cmd.MOVE,
                            }
                        ],
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

    def test_schema_version_in_to_dict(self):
        bs = BindingSet()
        self.assertEqual(bs.to_dict()["schemaVersion"], KEYMAP_SCHEMA_VERSION)

    def test_schema_version_roundtrip(self):
        bs = BindingSet()
        bs.bind(_key("g"), cmd.MOVE)
        restored = BindingSet.from_dict(json.loads(bs.to_json()))
        self.assertEqual(restored.to_dict()["schemaVersion"], KEYMAP_SCHEMA_VERSION)

    def test_dict_roundtrip_preserves_explicit_unbind(self):
        bs = BindingSet()
        bs.bind(_key("m"), None)
        restored = BindingSet.from_dict(bs.to_dict())
        self.assertIsNone(restored.command_for(_key("m")))
        self.assertEqual(restored.to_dict()["bindings"][0]["command"], None)


class KeymapOverrideTests(unittest.TestCase):
    """Gate 6: gültige keymap.json-Konfiguration überschreibt Defaults."""

    def test_keymap_overrides_default_binding(self):
        bs = build_default_bindings()
        overlay = BindingSet.from_dict(
            _keymap(_entry(GLOBAL_CONTEXT, "key", "m", [], cmd.SCALE))
        )
        bs.add_overrides(overlay)
        self.assertEqual(bs.command_for(_key("m")), cmd.SCALE)

    def test_keymap_override_keeps_other_defaults(self):
        bs = build_default_bindings()
        overlay = BindingSet.from_dict(
            _keymap(_entry(GLOBAL_CONTEXT, "key", "m", [], cmd.SCALE))
        )
        bs.add_overrides(overlay)
        self.assertEqual(bs.command_for(_key("z", "ctrl")), cmd.UNDO)
        self.assertEqual(bs.command_for(_key("v")), cmd.SET_VERTEX_MODE)

    def test_keymap_override_via_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keymap.json"
            path.write_text(
                json.dumps(_keymap(_entry(GLOBAL_CONTEXT, "key", "m", [], cmd.SCALE))),
                encoding="utf-8",
            )
            bs = build_default_bindings()
            load_keymap_overrides(bs, path)
            self.assertEqual(bs.command_for(_key("m")), cmd.SCALE)

    def test_default_bindings_unchanged_without_config(self):
        # Bestehende Defaults funktionieren unverändert, wenn keine Config da ist.
        bs = build_default_bindings()
        self.assertEqual(bs.command_for(_key("m")), cmd.MOVE)
        self.assertEqual(bs.command_for(_key("s"), TOPOLOGY_CONTEXT), cmd.SPLIT_EDGE)


class ExplicitUnbindTests(unittest.TestCase):
    """Gate 6: `command: null` ist ein explizites Unbind (unterdrückt Defaults)."""

    def test_null_command_unbinds_default_binding(self):
        bs = build_default_bindings()
        overlay = BindingSet.from_dict(
            _keymap(_entry(GLOBAL_CONTEXT, "key", "m", [], None))
        )
        bs.add_overrides(overlay)
        self.assertIsNone(bs.command_for(_key("m")))

    def test_bind_none_has_same_semantics(self):
        bs = build_default_bindings()
        bs.bind(_key("m"), None)
        self.assertIsNone(bs.command_for(_key("m")))

    def test_unbind_does_not_affect_other_defaults(self):
        bs = build_default_bindings()
        overlay = BindingSet.from_dict(
            _keymap(_entry(GLOBAL_CONTEXT, "key", "m", [], None))
        )
        bs.add_overrides(overlay)
        self.assertEqual(bs.command_for(_key("z", "ctrl")), cmd.UNDO)
        self.assertEqual(bs.command_for(_key("v")), cmd.SET_VERTEX_MODE)

    def test_unbind_is_scoped_to_context(self):
        # topology: s → null; global: s → Scale bleibt erhalten.
        bs = build_default_bindings()
        overlay = BindingSet.from_dict(
            _keymap(_entry(TOPOLOGY_CONTEXT, "key", "s", [], None))
        )
        bs.add_overrides(overlay)
        self.assertIsNone(bs.command_for(_key("s"), TOPOLOGY_CONTEXT))
        self.assertEqual(bs.command_for(_key("s"), GLOBAL_CONTEXT), cmd.SCALE)

    def test_unbind_survives_json_roundtrip(self):
        bs = BindingSet()
        bs.bind(_key("m"), None)
        restored = BindingSet.from_dict(json.loads(bs.to_json()))
        self.assertIsNone(restored.command_for(_key("m")))


class KeymapValidationTests(unittest.TestCase):
    """Gate 6: ungültige Konfiguration wird an der I/O-Grenze abgelehnt."""

    @staticmethod
    def _load(data):
        return BindingSet.from_dict(data)

    def test_invalid_json_syntax_raises_controlled_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keymap.json"
            path.write_text("{ \"kaputt\"", encoding="utf-8")
            with self.assertRaises(KeymapConfigError):
                BindingSet.from_json_file(path)

    def test_missing_schema_version_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load({"bindings": []})

    def test_wrong_schema_version_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load({"schemaVersion": 2, "bindings": []})

    def test_non_integer_schema_version_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load({"schemaVersion": "1", "bindings": []})

    def test_top_level_must_be_object(self):
        with self.assertRaises(KeymapConfigError):
            self._load(["kein", "objekt"])

    def test_bindings_must_be_sequence(self):
        with self.assertRaises(KeymapConfigError):
            self._load(
                {"schemaVersion": KEYMAP_SCHEMA_VERSION, "bindings": "keine-liste"}
            )

    def test_binding_must_be_object(self):
        with self.assertRaises(KeymapConfigError):
            self._load(_keymap("kein-objekt"))

    def test_missing_input_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load(_keymap({"command": cmd.MOVE}))

    def test_missing_command_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load(
                _keymap({"input": {"kind": "key", "value": "g", "modifiers": []}})
            )

    def test_invalid_kind_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load(_keymap(_entry(GLOBAL_CONTEXT, "gesture", "g", [], cmd.MOVE)))

    def test_invalid_modifier_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load(_keymap(_entry(GLOBAL_CONTEXT, "key", "g", ["super"], cmd.MOVE)))

    def test_non_list_modifiers_raise(self):
        with self.assertRaises(KeymapConfigError):
            self._load(_keymap(_entry(GLOBAL_CONTEXT, "key", "g", "ctrl", cmd.MOVE)))

    def test_invalid_value_type_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load(_keymap(_entry(GLOBAL_CONTEXT, "key", 42, [], cmd.MOVE)))

    def test_invalid_command_type_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load(_keymap(_entry(GLOBAL_CONTEXT, "key", "g", [], 42)))

    def test_unknown_context_raises(self):
        with self.assertRaises(KeymapConfigError):
            self._load(_keymap(_entry("editor", "key", "g", [], cmd.MOVE)))


class KeymapContextTests(unittest.TestCase):
    """Gate 6: bestehende Context-Auflösung gilt auch für keymap-Overrides."""

    def test_topology_override_wins_over_global_default(self):
        bs = build_default_bindings()
        overlay = BindingSet.from_dict(
            _keymap(_entry(TOPOLOGY_CONTEXT, "key", "v", [], cmd.CLEAR_SELECTION))
        )
        bs.add_overrides(overlay)
        self.assertEqual(
            bs.command_for(_key("v"), TOPOLOGY_CONTEXT), cmd.CLEAR_SELECTION
        )
        self.assertEqual(bs.command_for(_key("v"), GLOBAL_CONTEXT), cmd.SET_VERTEX_MODE)

    def test_global_override_applies_in_topology_via_fallback(self):
        bs = build_default_bindings()
        overlay = BindingSet.from_dict(
            _keymap(_entry(GLOBAL_CONTEXT, "key", "g", [], cmd.MOVE))
        )
        bs.add_overrides(overlay)
        self.assertEqual(bs.command_for(_key("g"), TOPOLOGY_CONTEXT), cmd.MOVE)


class KeymapDuplicateTests(unittest.TestCase):
    """Gate 6: späterer identischer Eintrag gewinnt; Contexts bleiben getrennt."""

    def test_later_duplicate_wins(self):
        bs = BindingSet.from_dict(
            _keymap(
                _entry(GLOBAL_CONTEXT, "key", "m", [], cmd.MOVE),
                _entry(GLOBAL_CONTEXT, "key", "m", [], cmd.SCALE),
            )
        )
        self.assertEqual(bs.command_for(_key("m")), cmd.SCALE)

    def test_later_duplicate_null_wins(self):
        bs = BindingSet.from_dict(
            _keymap(
                _entry(GLOBAL_CONTEXT, "key", "m", [], cmd.MOVE),
                _entry(GLOBAL_CONTEXT, "key", "m", [], None),
            )
        )
        self.assertIsNone(bs.command_for(_key("m")))

    def test_later_binding_after_null_wins(self):
        bs = BindingSet.from_dict(
            _keymap(
                _entry(GLOBAL_CONTEXT, "key", "m", [], None),
                _entry(GLOBAL_CONTEXT, "key", "m", [], cmd.MOVE),
            )
        )
        self.assertEqual(bs.command_for(_key("m")), cmd.MOVE)

    def test_same_key_in_different_contexts_is_not_an_error(self):
        bs = BindingSet.from_dict(
            _keymap(
                _entry(GLOBAL_CONTEXT, "key", "m", [], cmd.MOVE),
                _entry(TOPOLOGY_CONTEXT, "key", "m", [], cmd.SCALE),
            )
        )
        self.assertEqual(bs.command_for(_key("m"), GLOBAL_CONTEXT), cmd.MOVE)
        self.assertEqual(bs.command_for(_key("m"), TOPOLOGY_CONTEXT), cmd.SCALE)


if __name__ == "__main__":
    unittest.main()