"""Tests für die Input-Mapping-Foundation (WP-01A).

Prüft die Schicht `input_binding.py` + `default_bindings.py`:

- Default-Bindings
- geänderte Bindings (User-Overlay) und deren Rücknahme
- mehrere Bindings für dasselbe Command
- `command_for`-Auflösung (inkl. Modifier-Diskriminierung)
- Context-Verhalten (topology gewinnt; GLOBAL_CONTEXT-Fallback)
- Serialisierung/Dict-Roundtrip (keymap.json-Format)
- keine direkte Tasten-Kopplung im Window-/Tool-Dispatch (statischer Guard)

Läuft bewusst OHNE pyglet/Fenster/GPU.

Ausführen mit: python -m tests.test_input_binding   (aus dem Experiment-Ordner)
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    # Robuste Ausgabe unter Windows-cp1252-Konsolen (Unicode-Pfeile usw.).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from viewport import commands as cmd  # noqa: E402
from viewport.default_bindings import build_default_bindings  # noqa: E402
from viewport.input_binding import (  # noqa: E402
    BindingSet,
    GLOBAL_CONTEXT,
    Input,
    TOPOLOGY_CONTEXT,
)

_failures = 0


def check(label: str, condition: bool) -> None:
    global _failures
    status = "PASS" if condition else "FAIL"
    if not condition:
        _failures += 1
    print(f"[{status}] {label}")


def key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def wheel(direction: str) -> Input:
    return Input("wheel", direction)


def test_default_key_bindings() -> None:
    print("\n--- Default-Bindings (globale Belegung) ---")
    bs = build_default_bindings()
    check("V → SetVertexMode", bs.command_for(key("v"), GLOBAL_CONTEXT) == cmd.SET_VERTEX_MODE)
    check("1 → SetVertexMode", bs.command_for(key("1"), GLOBAL_CONTEXT) == cmd.SET_VERTEX_MODE)
    check("E → SetEdgeMode", bs.command_for(key("e"), GLOBAL_CONTEXT) == cmd.SET_EDGE_MODE)
    check("2 → SetEdgeMode", bs.command_for(key("2"), GLOBAL_CONTEXT) == cmd.SET_EDGE_MODE)
    check("F → SetFaceMode", bs.command_for(key("f"), GLOBAL_CONTEXT) == cmd.SET_FACE_MODE)
    check("3 → SetFaceMode", bs.command_for(key("3"), GLOBAL_CONTEXT) == cmd.SET_FACE_MODE)
    check("Strg+Z → Undo", bs.command_for(key("z", "ctrl"), GLOBAL_CONTEXT) == cmd.UNDO)
    check("Strg+Y → Redo", bs.command_for(key("y", "ctrl"), GLOBAL_CONTEXT) == cmd.REDO)
    check("Esc → Cancel", bs.command_for(key("ESCAPE"), GLOBAL_CONTEXT) == cmd.CANCEL)
    check("Alt+A → ClearSelection", bs.command_for(key("a", "alt"), GLOBAL_CONTEXT) == cmd.CLEAR_SELECTION)
    check("O → CycleDisplayMode", bs.command_for(key("o"), GLOBAL_CONTEXT) == cmd.CYCLE_DISPLAY_MODE)
    check("W → ToggleWireframeOverlay", bs.command_for(key("w"), GLOBAL_CONTEXT) == cmd.TOGGLE_WIREFRAME_OVERLAY)


def test_default_mouse_bindings() -> None:
    print("\n--- Default-Bindings (Maus) ---")
    bs = build_default_bindings()
    check("LMB → Select", bs.command_for(mouse("LEFT"), GLOBAL_CONTEXT) == cmd.SELECT)
    check("RMB → Orbit", bs.command_for(mouse("RIGHT"), GLOBAL_CONTEXT) == cmd.ORBIT)
    check("MMB → Pan", bs.command_for(mouse("MIDDLE"), GLOBAL_CONTEXT) == cmd.PAN)
    check("Wheel UP → Zoom", bs.command_for(wheel("UP"), GLOBAL_CONTEXT) == cmd.ZOOM)
    check("Wheel DOWN → Zoom", bs.command_for(wheel("DOWN"), GLOBAL_CONTEXT) == cmd.ZOOM)


def test_changed_binding() -> None:
    print("\n--- Geändertes Binding (User-Overlay) ---")
    bs = build_default_bindings()
    check("Default: O → CycleDisplayMode", bs.command_for(key("o"), GLOBAL_CONTEXT) == cmd.CYCLE_DISPLAY_MODE)
    bs.bind(key("o"), cmd.REDO)
    check("nach bind: O → Redo", bs.command_for(key("o"), GLOBAL_CONTEXT) == cmd.REDO)
    check("Command bleibt unverändert (keine Key-Kopplung in der Implementierung)", cmd.REDO == "Redo")
    bs.unbind(key("o"))
    check("nach unbind: O → wieder CycleDisplayMode", bs.command_for(key("o"), GLOBAL_CONTEXT) == cmd.CYCLE_DISPLAY_MODE)


def test_multiple_bindings_for_same_command() -> None:
    print("\n--- Mehrere Bindings für dasselbe Command ---")
    bs = build_default_bindings()
    for value in ("v", "1"):
        check(f"{value} → SetVertexMode", bs.command_for(key(value), GLOBAL_CONTEXT) == cmd.SET_VERTEX_MODE)
    check("E und 2 → SetEdgeMode",
          bs.command_for(key("e"), GLOBAL_CONTEXT) == cmd.SET_EDGE_MODE
          and bs.command_for(key("2"), GLOBAL_CONTEXT) == cmd.SET_EDGE_MODE)


def test_modifier_discrimination() -> None:
    print("\n--- Modifier-Diskriminierung ---")
    bs = build_default_bindings()
    check("Z ohne Strg ist NICHT Undo", bs.command_for(key("z"), GLOBAL_CONTEXT) is None)
    check("Z mit Strg ist Undo", bs.command_for(key("z", "ctrl"), GLOBAL_CONTEXT) == cmd.UNDO)
    check("C (topology) → Connect (kontextabhängig)",
          bs.command_for(key("c"), TOPOLOGY_CONTEXT) == cmd.CONNECT)
    check("Shift+C (topology) ist ungebunden (kein zweites Connect-Binding nötig)",
          bs.command_for(key("c", "shift"), TOPOLOGY_CONTEXT) is None)


def test_context_resolution() -> None:
    print("\n--- Context-Verhalten ---")
    bs = build_default_bindings()
    check("topology: S → SplitEdge", bs.command_for(key("s"), TOPOLOGY_CONTEXT) == cmd.SPLIT_EDGE)
    check("global:  S ist ungebunden", bs.command_for(key("s"), GLOBAL_CONTEXT) is None)
    check("topology: K → Collapse", bs.command_for(key("k"), TOPOLOGY_CONTEXT) == cmd.COLLAPSE)
    check("topology: L → EdgeLoop", bs.command_for(key("l"), TOPOLOGY_CONTEXT) == cmd.EDGE_LOOP)
    check("topology: R → EdgeRing", bs.command_for(key("r"), TOPOLOGY_CONTEXT) == cmd.EDGE_RING)
    check("topology: V fällt auf global zurück → SetVertexMode",
          bs.command_for(key("v"), TOPOLOGY_CONTEXT) == cmd.SET_VERTEX_MODE)
    check("topology: Ctrl+Z fällt auf global zurück → Undo",
          bs.command_for(key("z", "ctrl"), TOPOLOGY_CONTEXT) == cmd.UNDO)


def test_serialization_roundtrip() -> None:
    print("\n--- keymap.json-Format (User-Overlay-Roundtrip) ---")
    bs = build_default_bindings()
    bs.bind(key("g"), cmd.REDO, context=TOPOLOGY_CONTEXT)
    bs.bind(mouse("MIDDLE", "shift"), cmd.ORBIT)
    data = bs.to_dict()
    restored = BindingSet.from_dict(data)
    merged = build_default_bindings()
    merged.add_overrides(restored)
    check("G(topology) → Redo nach Roundtrip",
          merged.command_for(key("g"), TOPOLOGY_CONTEXT) == cmd.REDO)
    check("Shift+MMB → Orbit nach Roundtrip",
          merged.command_for(mouse("MIDDLE", "shift"), GLOBAL_CONTEXT) == cmd.ORBIT)
    check("Defaults unverändert: S(topology) → SplitEdge",
          merged.command_for(key("s"), TOPOLOGY_CONTEXT) == cmd.SPLIT_EDGE)
    check("Defaults unverändert: V → SetVertexMode",
          merged.command_for(key("v"), GLOBAL_CONTEXT) == cmd.SET_VERTEX_MODE)


def test_no_hardcoded_keys_in_windows() -> None:
    print("\n--- Keine direkte Kopplung von Window-/Tool-Code an Tasten ---")
    import re

    # Token- statt Substring-Match: `key.ESCAPE`/`key.SPACE` im Adapter sind
    # erlaubt (sie stehen im Input-Adapter, nicht im Command-Dispatch).
    hardcoded = re.compile(r"key\.(?:V|E|F|S|K|L|R|Z|Y|_1|_2|_3)(?!\w)")
    for rel in ("viewport/app.py", "viewport/topology_app.py"):
        src = (_THIS_DIR.parent / rel).read_text(encoding="utf-8")
        match = hardcoded.search(src)
        check(
            f"{rel} enthält keine hart kodierten pyglet-Key-Konstanten im Dispatch",
            match is None,
        )
    tools_src = (_THIS_DIR.parent / "viewport" / "topology_tools.py").read_text(encoding="utf-8")
    check("topology_tools.py enthält kein 'pyglet' (reine Domain-Logik)", "pyglet" not in tools_src)


def run_all() -> None:
    tests = [
        test_default_key_bindings,
        test_default_mouse_bindings,
        test_changed_binding,
        test_multiple_bindings_for_same_command,
        test_modifier_discrimination,
        test_context_resolution,
        test_serialization_roundtrip,
        test_no_hardcoded_keys_in_windows,
    ]
    for t in tests:
        t()
    print()
    if _failures:
        print(f"{_failures} Check(s) fehlgeschlagen.")
        sys.exit(1)
    print("Alle Input-Mapping-Checks validiert.")


if __name__ == "__main__":
    run_all()