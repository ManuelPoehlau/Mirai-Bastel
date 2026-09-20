"""Characterization harness for the real Playground key dispatch.

Purpose
-------
Drive ``PlaygroundWindow.on_key_press`` / ``on_key_release`` — the actual
runtime handlers — and record what observably happens. Nothing here asserts
that the behaviour is *correct*; it records what the behaviour *is*, so that
a later change can be shown to have altered only what was intended.

This is deliberately NOT a unit test of the binding table, the adapter or the
command handler. Those already have tests, and they all passed while the
dispatch was broken. The gap this fills is that no test drove the handlers.

Usage
-----
    PYGLET_HEADLESS=1 python playground/tests/input_characterization.py > snapshot.txt

Each probe runs against a FRESH window so that no state leaks between keys.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from playground._paths import ensure_paths  # noqa: E402

ensure_paths()

import pyglet  # noqa: E402
from pyglet.window import key as _key  # noqa: E402

from playground.app import PlaygroundApp  # noqa: E402
from playground.window import PlaygroundWindow  # noqa: E402


MOD = {
    "ctrl": _key.MOD_CTRL,
    "shift": _key.MOD_SHIFT,
    "alt": _key.MOD_ALT,
}


def make_window(family: str = "selection", fixture: str = "empty") -> PlaygroundWindow:
    app = PlaygroundApp()
    win = PlaygroundWindow(app, initial_mesh="cube")
    app.focused_family = family
    if fixture == "face":
        from core.selection import SelectionMode

        sel = app.scene.selection
        sel.mode = SelectionMode.FACE
        sel.clear()
        sel.add({sorted(app.scene.mesh.all_face_ids())[0]})
    return win


def observe(win: PlaygroundWindow) -> dict:
    """Everything an artist could notice, reduced to comparable values."""
    app = win.app
    sel = app.scene.selection
    tool = app.active_tool
    return {
        "active_tool": type(tool).__name__ if tool is not None else None,
        "transform_key_down": win._transform_key_down,
        "transform_mode_on": win._transform_mode_on,
        "tweak_v1_key": win._tweak_v1_key,
        "tweak_v3_key": win._tweak_v3_key,
        "tweak_active": win._tweak_active,
        "tweak_started": win._tweak_started,
        "tweak_persistent_mode": win._tweak_persistent_mode,
        "transform_started": win._transform_started,
        "extrude_tool": win._extrude_tool is not None,
        "loop_slide_tool": win._loop_slide_tool is not None,
        "axis_constraint": win._axis_constraint,
        "selection_mode": getattr(sel.mode, "name", str(sel.mode)),
        "selection_count": len(sel.faces) + len(sel.edges) + len(sel.vertices),
        "show_vertices": app.show_vertices,
        "select_method": getattr(getattr(app, "select_method", None), "name", None),
        "focused_family": app.focused_family,
        "slot_indices": {
            name: slot.active_index for name, slot in sorted(app.slots.items())
        },
        "hud_action": getattr(win._hud, "action_line", None),
        "hud_display": getattr(win._hud, "display_line", None),
        "hud_constraint": getattr(win._hud, "setting_line", None),
        "vertex_count": len(app.scene.mesh.all_vertex_ids()),
        "face_count": len(app.scene.mesh.all_face_ids()),
    }


def diff(before: dict, after: dict) -> dict:
    return {k: (before[k], after[k]) for k in before if before[k] != after[k]}


def probe(symbol: int, modifiers: int = 0, family: str = "selection",
          release: bool = True, fixture: str = "empty",
          drag: bool = False) -> dict:
    """Press (optionally drag, optionally release) one key on a fresh window."""
    win = make_window(family, fixture)
    try:
        base = observe(win)
        win.on_key_press(symbol, modifiers)
        after_press = observe(win)
        result = {"press": diff(base, after_press)}
        if drag:
            # Variants listen on different mouse events (V1 tweak on motion,
            # the transform slot on drag) — send both so the probe is neutral.
            win.on_mouse_motion(700, 400, 40, 0)
            win.on_mouse_drag(700, 400, 40, 0, 0, 0)
            after_drag = observe(win)
            result["drag"] = diff(after_press, after_drag)
            after_press = after_drag
        if release:
            win.on_key_release(symbol, modifiers)
            after_release = observe(win)
            result["release"] = diff(after_press, after_release)
        return result
    finally:
        win.close()


# label, symbol, modifiers, family, fixture, drag
GESTURES: list[tuple[str, int, int, str, str, bool]] = [
    ("Q drag   [face]", _key.Q, 0, "selection", "face", True),
    ("W drag   [face]", _key.W, 0, "selection", "face", True),
    ("E drag   [face]", _key.E, 0, "selection", "face", True),
    ("R        [face]", _key.R, 0, "selection", "face", False),
    ("R drag   [face]", _key.R, 0, "selection", "face", True),
]


KEYS: list[tuple[str, int, int, str]] = [
    # label,        symbol,        modifiers,                 family
    ("Q",           _key.Q,        0,                         "selection"),
    ("W",           _key.W,        0,                         "selection"),
    ("E",           _key.E,        0,                         "selection"),
    ("R",           _key.R,        0,                         "selection"),
    ("S",           _key.S,        0,                         "selection"),
    ("M",           _key.M,        0,                         "selection"),
    ("Shift+M",     _key.M,        _key.MOD_SHIFT,            "selection"),
    ("X",           _key.X,        0,                         "selection"),
    ("Y",           _key.Y,        0,                         "selection"),
    ("Z",           _key.Z,        0,                         "selection"),
    ("Shift+X",     _key.X,        _key.MOD_SHIFT,            "selection"),
    ("Ctrl+Z",      _key.Z,        _key.MOD_CTRL,             "selection"),
    ("Ctrl+Y",      _key.Y,        _key.MOD_CTRL,             "selection"),
    ("1",           _key._1,       0,                         "selection"),
    ("2",           _key._2,       0,                         "selection"),
    ("3",           _key._3,       0,                         "selection"),
    ("V",           _key.V,        0,                         "selection"),
    ("F",           _key.F,        0,                         "selection"),
    ("D",           _key.D,        0,                         "selection"),
    ("Shift+D",     _key.D,        _key.MOD_SHIFT,            "selection"),
    ("O",           _key.O,        0,                         "selection"),
    ("K",           _key.K,        0,                         "selection"),
    ("I",           _key.I,        0,                         "selection"),
    ("J",           _key.J,        0,                         "selection"),
    ("G",           _key.G,        0,                         "selection"),
    ("L",           _key.L,        0,                         "selection"),
    ("Shift+L",     _key.L,        _key.MOD_SHIFT,            "selection"),
    ("Shift+R",     _key.R,        _key.MOD_SHIFT,            "selection"),
    ("TAB",         _key.TAB,      0,                         "selection"),
    ("ESCAPE",      _key.ESCAPE,   0,                         "selection"),
    # topology context — same physical keys, different binding context
    ("R  [topo]",   _key.R,        0,                         "topology"),
    ("S  [topo]",   _key.S,        0,                         "topology"),
    ("L  [topo]",   _key.L,        0,                         "topology"),
    ("K  [topo]",   _key.K,        0,                         "topology"),
    ("C  [topo]",   _key.C,        0,                         "topology"),
]


def main() -> None:
    print("PLAYGROUND KEY DISPATCH — CHARACTERIZATION SNAPSHOT")
    print("Records observed behaviour of the real handlers. Not a correctness claim.")
    print("=" * 78)
    for label, symbol, modifiers, family in KEYS:
        try:
            result = probe(symbol, modifiers, family)
        except Exception as exc:  # noqa: BLE001 - characterization records crashes too
            print(f"\n{label:<12} family={family:<10} !! RAISED {type(exc).__name__}: {exc}")
            continue
        press = result.get("press", {})
        release = result.get("release", {})
        print(f"\n{label:<12} family={family}")
        if not press:
            print("   press  : (no observable change)")
        else:
            for k, (a, b) in sorted(press.items()):
                print(f"   press  : {k} = {a!r} -> {b!r}")
        if not release:
            print("   release: (no observable change)")
        else:
            for k, (a, b) in sorted(release.items()):
                print(f"   release: {k} = {a!r} -> {b!r}")

    print("\n" + "=" * 78)
    print("GESTURES — press, drag, release (one face selected, FACE mode)")
    print("=" * 78)
    for label, symbol, modifiers, family, fixture, drag in GESTURES:
        try:
            result = probe(symbol, modifiers, family, fixture=fixture, drag=drag)
        except Exception as exc:  # noqa: BLE001
            print(f"\n{label:<16} !! RAISED {type(exc).__name__}: {exc}")
            continue
        print(f"\n{label:<16} family={family}")
        for phase in ("press", "drag", "release"):
            changes = result.get(phase)
            if changes is None:
                continue
            if not changes:
                print(f"   {phase:<7}: (no observable change)")
            else:
                for k, (a, b) in sorted(changes.items()):
                    print(f"   {phase:<7}: {k} = {a!r} -> {b!r}")


if __name__ == "__main__":
    main()
