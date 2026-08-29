"""Tests für den Display-State (WP-01A).

Prüft `display_state.py` pyglet-/GPU-frei: Moduswechsel, Wireframe-Overlay,
die fünf nutzbaren Kombinationen und gültige/ungültige Übergänge.

Ausführen mit: python -m tests.test_display_state   (aus dem Experiment-Ordner)
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

from viewport.display_state import DisplayMode, DisplayState  # noqa: E402

_failures = 0


def check(label: str, condition: bool) -> None:
    global _failures
    status = "PASS" if condition else "FAIL"
    if not condition:
        _failures += 1
    print(f"[{status}] {label}")


def test_defaults() -> None:
    print("\n--- Default-Zustand ---")
    state = DisplayState()
    check("Default-Modus ist Shaded", state.mode is DisplayMode.SHADED)
    check("Default-Overlay ist aus", state.wireframe_overlay is False)
    check("show_faces (Shaded)", state.show_faces is True)
    check("show_edges ohne Overlay (Shaded)", state.show_edges is False)
    check("Label 'Shaded'", state.label == "Shaded")


def test_set_modes() -> None:
    print("\n--- Moduswechsel ---")
    state = DisplayState()
    state.set_mode(DisplayMode.FLAT_SHADED)
    check("Flat Shaded aktiv", state.mode is DisplayMode.FLAT_SHADED)
    check("show_faces (Flat Shaded)", state.show_faces is True)
    check("show_edges (Flat Shaded, ohne Overlay)", state.show_edges is False)

    state.set_mode(DisplayMode.WIREFRAME)
    check("Wireframe aktiv", state.mode is DisplayMode.WIREFRAME)
    check("show_faces (Wireframe) ist False", state.show_faces is False)
    check("show_edges (Wireframe) ist True", state.show_edges is True)

    state.set_mode(DisplayMode.SHADED)
    check("zurück zu Shaded", state.mode is DisplayMode.SHADED)


def test_wireframe_overlay() -> None:
    print("\n--- Wireframe Overlay ON/OFF ---")
    state = DisplayState()
    state.toggle_wireframe_overlay()
    check("Overlay an", state.wireframe_overlay is True)
    check("Shaded + Overlay: show_faces", state.show_faces is True)
    check("Shaded + Overlay: show_edges", state.show_edges is True)
    check("Label 'Shaded + Wire'", state.label == "Shaded + Wire")

    state.set_mode(DisplayMode.FLAT_SHADED)
    check("Flat Shaded + Overlay: show_faces", state.show_faces is True)
    check("Flat Shaded + Overlay: show_edges", state.show_edges is True)
    check("Label 'Flat Shaded + Wire'", state.label == "Flat Shaded + Wire")

    state.set_mode(DisplayMode.WIREFRAME)
    check("Wireframe + Overlay: show_faces bleibt False (Normalisierung)", state.show_faces is False)
    check("Wireframe + Overlay: show_edges True", state.show_edges is True)

    state.set_wireframe_overlay(False)
    check("Overlay wieder aus", state.wireframe_overlay is False)


def test_cycle_order() -> None:
    print("\n--- Cycle-Reihenfolge ---")
    state = DisplayState(DisplayMode.SHADED)
    state.cycle()
    check("Shaded → Flat Shaded", state.mode is DisplayMode.FLAT_SHADED)
    state.cycle()
    check("Flat Shaded → Wireframe", state.mode is DisplayMode.WIREFRAME)
    state.cycle()
    check("Wireframe → Shaded", state.mode is DisplayMode.SHADED)


def test_invalid_mode_rejected() -> None:
    print("\n--- Gültige Übergänge ---")
    state = DisplayState()
    try:
        state.set_mode("Smooth")  # type: ignore[arg-type]
        check("String-Modus wird abgelehnt", False)
    except ValueError:
        check("String-Modus wird abgelehnt", True)
    state.set_mode(DisplayMode.SHADED)
    check("gültiger Modus-Wechsel funktioniert", state.mode is DisplayMode.SHADED)


def run_all() -> None:
    tests = [
        test_defaults,
        test_set_modes,
        test_wireframe_overlay,
        test_cycle_order,
        test_invalid_mode_rejected,
    ]
    for t in tests:
        t()
    print()
    if _failures:
        print(f"{_failures} Check(s) fehlgeschlagen.")
        sys.exit(1)
    print("Alle Display-State-Checks validiert.")


if __name__ == "__main__":
    run_all()