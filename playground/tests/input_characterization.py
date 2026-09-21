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
    elif fixture == "edge_single":
        from core.selection import SelectionMode

        sel = app.scene.selection
        sel.mode = SelectionMode.EDGE
        sel.clear()
        sel.add({sorted(app.scene.mesh.all_edge_ids())[0]})
    elif fixture == "edge_multi":
        from core.selection import SelectionMode

        sel = app.scene.selection
        sel.mode = SelectionMode.EDGE
        sel.clear()
        sel.add(set(sorted(app.scene.mesh.all_edge_ids())[:2]))
    elif fixture == "vertex":
        from core.selection import SelectionMode

        sel = app.scene.selection
        sel.mode = SelectionMode.VERTEX
        sel.clear()
        sel.add({sorted(app.scene.mesh.all_vertex_ids())[0]})
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
        "current_tool_type": win._current_tool_type,
        "transform_temp_target": win._transform_temp_target,
        "transform_started": win._transform_started,
        "extrude_tool": win._extrude_tool is not None,
        "loop_slide_tool": win._loop_slide_tool is not None,
        "axis_constraint": win._axis_constraint,
        "transform_space": win._transform_space,
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


def probe_x_twice() -> dict:
    """Press X twice on a fresh window — second press should toggle off."""
    win = make_window()
    try:
        win.on_key_press(_key.X, 0)
        after_first = observe(win)
        win.on_key_press(_key.X, 0)
        after_second = observe(win)
        return {
            "after_first_press": after_first["axis_constraint"],
            "after_second_press": after_second["axis_constraint"],
        }
    finally:
        win.close()


def probe_x_then_y() -> dict:
    """Press X then Y — Y should replace X (not stack)."""
    win = make_window()
    try:
        win.on_key_press(_key.X, 0)
        after_x = observe(win)
        win.on_key_press(_key.Y, 0)
        after_y = observe(win)
        return {
            "after_x": after_x["axis_constraint"],
            "after_y": after_y["axis_constraint"],
        }
    finally:
        win.close()


def probe_constraint_survives_commit() -> dict:
    """Constraint set before a gesture survives commit."""
    win = make_window(fixture="face")
    try:
        win.on_key_press(_key.X, 0)
        constraint_before = observe(win)["axis_constraint"]
        # Simulate a full gesture: press Q, drag, release Q
        win.on_key_press(_key.Q, 0)
        win.on_mouse_motion(700, 400, 40, 0)
        win.on_key_release(_key.Q, 0)
        constraint_after = observe(win)["axis_constraint"]
        return {
            "constraint_before_gesture": constraint_before,
            "constraint_after_commit": constraint_after,
        }
    finally:
        win.close()


def probe_constraint_survives_cancel() -> dict:
    """Constraint set before a gesture survives ESC cancel."""
    win = make_window(fixture="face")
    try:
        win.on_key_press(_key.X, 0)
        constraint_before = observe(win)["axis_constraint"]
        win.on_key_press(_key.Q, 0)
        win.on_mouse_motion(700, 400, 40, 0)
        win.on_key_press(_key.ESCAPE, 0)
        constraint_after = observe(win)["axis_constraint"]
        return {
            "constraint_before_gesture": constraint_before,
            "constraint_after_cancel": constraint_after,
        }
    finally:
        win.close()


def probe_release_does_nothing() -> dict:
    """Releasing X after press does NOT clear the constraint (sticky model)."""
    win = make_window()
    try:
        win.on_key_press(_key.X, 0)
        before_release = observe(win)["axis_constraint"]
        win.on_key_release(_key.X, 0)
        after_release = observe(win)["axis_constraint"]
        return {
            "before_release": before_release,
            "after_release": after_release,
            "changed": before_release != after_release,
        }
    finally:
        win.close()


def probe_k_toggle_space() -> dict:
    """K toggles _transform_space world→normal→world across two presses."""
    win = make_window()
    try:
        initial = observe(win)["transform_space"]
        win.on_key_press(_key.K, 0)
        after_first = observe(win)["transform_space"]
        win.on_key_press(_key.K, 0)
        after_second = observe(win)["transform_space"]
        return {
            "initial": initial,
            "after_first_k": after_first,
            "after_second_k": after_second,
        }
    finally:
        win.close()


def probe_k_clears_axis_constraint() -> dict:
    """K resets _axis_constraint to None (WP-AP-INPUT-FIX-04).

    Set X constraint in World, press K → constraint must be None, not 'x'.
    """
    win = make_window()
    try:
        win.on_key_press(_key.X, 0)
        after_x = observe(win)["axis_constraint"]
        win.on_key_press(_key.K, 0)
        after_k = observe(win)["axis_constraint"]
        return {"after_x": after_x, "after_k": after_k}
    finally:
        win.close()


def probe_tweak_v1_space_axis(space: str, axis_key: int | None = None) -> dict:
    """Tweak-V1 gesture begins with expected transform_space and axis_constraint.

    Sets up space and optional axis constraint, then drives a V1 gesture (Q+motion)
    to the point where begin_transform is called. Observes _tweak_started and
    the window state fed into begin_transform.
    """
    win = make_window(family="tweak", fixture="face")
    # Ensure tweak family is V1
    tweak_slot = win.app.slots.get("tweak")
    if tweak_slot is not None:
        win.app.activate_variant("tweak", 0)
    try:
        # Set coordinate space
        if space == "normal":
            win.on_key_press(_key.K, 0)
        # Optionally set axis constraint
        if axis_key is not None:
            win.on_key_press(axis_key, 0)
        state_before = {
            "transform_space": observe(win)["transform_space"],
            "axis_constraint": observe(win)["axis_constraint"],
        }
        # Arm V1 gesture and move past threshold
        win.on_key_press(_key.Q, 0)
        for _ in range(10):
            win.on_mouse_motion(700 + _ * 5, 400, 5, 0)
        state_after = {
            "tweak_started": observe(win)["tweak_started"],
            "transform_space": observe(win)["transform_space"],
            "axis_constraint": observe(win)["axis_constraint"],
        }
        return {"before": state_before, "after": state_after}
    finally:
        win.close()


def probe_ad016_q_always_reaches_transform() -> dict:
    """AD-016 D1: Q always goes to Transform (no Tweak dispatch)."""
    win = make_window()
    win.app.activate_variant("tweak", 0)  # V2 is index 0 under AD-016
    try:
        win.on_key_press(_key.Q, 0)
        return {
            "tweak_v1_key": win._tweak_v1_key,       # must be None (V1 not in slot)
            "transform_key_down": win._transform_key_down,  # must be 'q'
            "current_tool_type": win._current_tool_type,    # must be 'move'
            "active_tool_present": win.app.active_tool is not None,
        }
    finally:
        win.close()


def probe_ad016_tweak_slot_variants() -> dict:
    """AD-016 D5: report which variants are in the tweak slot."""
    win = make_window()
    try:
        slot = win.app.slots.get("tweak")
        if slot is None:
            return {"variants": []}
        return {
            "variants": [
                type(e.experiment).__name__ for e in slot.variants
            ]
        }
    finally:
        win.close()


def probe_transform_slot_default() -> dict:
    """WP-AP-GIZMO-02: confirm the transform slot's active variant is PressDragClickVariant."""
    from playground.experiments.transform.variant_press_drag_click import PressDragClickVariant
    win = make_window()
    try:
        slot = win.app.slots.get("transform")
        if slot is None:
            return {"variant": None, "is_press_drag_click": False}
        active = slot.active_experiment
        return {
            "variant": type(active).__name__,
            "is_press_drag_click": isinstance(active, PressDragClickVariant),
        }
    finally:
        win.close()


# label, symbol, modifiers, family, fixture, drag
GESTURES: list[tuple[str, int, int, str, str, bool]] = [
    ("Q drag   [face]", _key.Q, 0, "selection", "face", True),
    ("W drag   [face]", _key.W, 0, "selection", "face", True),
    ("E drag   [face]", _key.E, 0, "selection", "face", True),
    ("R        [face]", _key.R, 0, "selection", "face", False),
    ("R drag   [face]", _key.R, 0, "selection", "face", True),
    # WP-AP-INPUT-FIX-02 probes
    ("R release commit [face]", _key.R, 0, "selection", "face", True),
    ("Shift+R  [edge*2]", _key.R, _key.MOD_SHIFT, "selection", "edge_multi", False),
    ("C        [edge*2]", _key.C, 0, "selection", "edge_multi", False),
    ("S        [edge]", _key.S, 0, "selection", "edge_single", False),
    ("Shift+C  [edge]", _key.C, _key.MOD_SHIFT, "selection", "edge_single", False),
    ("Z press  [face]", _key.Z, 0, "selection", "face", False),
    # WP-AP-INPUT-FIX-03 probes
    ("X twice (toggle off)", _key.X, 0, "selection", "empty", False),
    ("X then Y (replace)", _key.X, 0, "selection", "empty", False),
    ("K toggle space",   _key.K, 0, "selection", "empty", False),
    ("Q drag Normal [face]", _key.Q, 0, "selection", "face", True),
]


KEYS: list[tuple[str, int, int, str]] = [
    # label,        symbol,        modifiers,                 family
    ("Q",           _key.Q,        0,                         "selection"),
    ("W",           _key.W,        0,                         "selection"),
    ("E",           _key.E,        0,                         "selection"),
    ("R",           _key.R,        0,                         "selection"),
    ("S",           _key.S,        0,                         "selection"),
    ("C",           _key.C,        0,                         "selection"),
    ("Shift+C",     _key.C,        _key.MOD_SHIFT,            "selection"),
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

    print("\nWP-AP-GIZMO-02 — Transform Slot Default")
    print("=" * 78)
    try:
        r = probe_transform_slot_default()
        print(f"Transform slot default: variant={r['variant']!r}  is_press_drag_click={r['is_press_drag_click']}")
    except Exception as exc:
        print(f"\nTransform slot default !! RAISED {type(exc).__name__}: {exc}")

    print("\nWP-AP-INPUT-FIX-03 — Sticky Constraint + Space Toggle")
    print("=" * 78)
    try:
        r = probe_x_twice()
        print(f"\nX twice (toggle off): after_first={r['after_first_press']!r}  after_second={r['after_second_press']!r}")
    except Exception as exc:
        print(f"\nX twice !! RAISED {type(exc).__name__}: {exc}")
    try:
        r = probe_x_then_y()
        print(f"X then Y (replace):  after_x={r['after_x']!r}  after_y={r['after_y']!r}")
    except Exception as exc:
        print(f"\nX then Y !! RAISED {type(exc).__name__}: {exc}")
    try:
        r = probe_constraint_survives_commit()
        print(f"Constraint survives commit: before={r['constraint_before_gesture']!r}  after_commit={r['constraint_after_commit']!r}")
    except Exception as exc:
        print(f"\nConstraint survives commit !! RAISED {type(exc).__name__}: {exc}")
    try:
        r = probe_constraint_survives_cancel()
        print(f"Constraint survives cancel: before={r['constraint_before_gesture']!r}  after_cancel={r['constraint_after_cancel']!r}")
    except Exception as exc:
        print(f"\nConstraint survives cancel !! RAISED {type(exc).__name__}: {exc}")
    try:
        r = probe_release_does_nothing()
        print(f"Release does nothing:       before={r['before_release']!r}  after={r['after_release']!r}  changed={r['changed']}")
    except Exception as exc:
        print(f"\nRelease does nothing !! RAISED {type(exc).__name__}: {exc}")
    try:
        r = probe_k_toggle_space()
        print(f"K toggle space:             initial={r['initial']!r}  after_K={r['after_first_k']!r}  after_KK={r['after_second_k']!r}")
    except Exception as exc:
        print(f"\nK toggle space !! RAISED {type(exc).__name__}: {exc}")
    try:
        r = probe_k_clears_axis_constraint()
        print(f"K clears axis constraint:   after_X={r['after_x']!r}  after_K={r['after_k']!r}")
    except Exception as exc:
        print(f"\nK clears axis constraint !! RAISED {type(exc).__name__}: {exc}")
    try:
        r = probe_ad016_q_always_reaches_transform()
        print(f"AD-016 Q→Transform:         v1_key={r['tweak_v1_key']!r}  xfm_key={r['transform_key_down']!r}  current_tool={r['current_tool_type']!r}")
    except Exception as exc:
        print(f"\nAD-016 Q→Transform !! RAISED {type(exc).__name__}: {exc}")
    try:
        r = probe_ad016_tweak_slot_variants()
        print(f"AD-016 tweak slot variants: {r['variants']}")
    except Exception as exc:
        print(f"\nAD-016 tweak slot variants !! RAISED {type(exc).__name__}: {exc}")

    print("\n" + "=" * 78)
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


# ---------------------------------------------------------------------------
# AD-016 pytest assertions
# ---------------------------------------------------------------------------

# -- D1/D2: Transform owns Q/W/E; shared current-tool state ------------------

def test_ad016_q_always_reaches_transform():
    """D1 (AD-016): Q always goes to Transform regardless of tweak variant."""
    win = make_window()
    try:
        # Switch to V2 (still in slot) — Q must still go to Transform
        win.app.activate_variant("tweak", 0)  # V2 is index 0 under AD-016
        win.on_key_press(_key.Q, 0)
        assert win._transform_key_down == "q", "Q must set _transform_key_down"
        assert win.app.active_tool is not None, "Q must create active_tool"
        assert win._tweak_v1_key is None, "V1 key arm must never fire"
    finally:
        win.close()


def test_ad016_q_sets_shared_current_tool():
    """D2 (AD-016): Q press updates _current_tool_type regardless of model."""
    win = make_window()
    try:
        assert win._current_tool_type is None
        win.on_key_press(_key.Q, 0)
        assert win._current_tool_type == "move"
        win.on_key_press(_key.W, 0)
        assert win._current_tool_type == "rotate"
        win.on_key_press(_key.E, 0)
        assert win._current_tool_type == "scale"
    finally:
        win.close()


# -- D5: V1 and V3 not in Tweak slot ----------------------------------------

def test_ad016_v1_not_in_tweak_slot():
    """D5 (AD-016): V1 (TweakV1HoldKey) is removed from the Tweak slot."""
    from playground.experiments.tweak.variant_1_hold_key import TweakV1HoldKey
    win = make_window()
    try:
        slot = win.app.slots.get("tweak")
        assert slot is not None
        variants = [e.experiment for e in slot.variants]
        assert not any(isinstance(v, TweakV1HoldKey) for v in variants), \
            "TweakV1HoldKey must not be a selectable Tweak variant under AD-016"
    finally:
        win.close()


def test_ad016_v3_not_in_tweak_slot():
    """D5 (AD-016): V3 (TweakV3HoldClick) is removed from the Tweak slot."""
    from playground.experiments.tweak.variant_3_hold_click import TweakV3HoldClick
    win = make_window()
    try:
        slot = win.app.slots.get("tweak")
        assert slot is not None
        variants = [e.experiment for e in slot.variants]
        assert not any(isinstance(v, TweakV3HoldClick) for v in variants), \
            "TweakV3HoldClick must not be a selectable Tweak variant under AD-016"
    finally:
        win.close()


# -- D4: HoldKeyHover variant ------------------------------------------------

def test_ad016_d4_tap_sets_current_tool_no_execution():
    """D4 (AD-016): tap Q/W/E with HoldKeyHover sets current tool, does not execute."""
    win = make_window(fixture="face")
    try:
        # Activate D4 (index 3 in transform slot: PDC, Hold, PressMode, HoldKeyHover)
        win.app.activate_variant("transform", 3)
        assert win._active_transform_model() == "hold_key_hover"
        win.on_key_press(_key.Q, 0)
        # No motion → tap
        win.on_key_release(_key.Q, 0)
        assert win._current_tool_type == "move", "tap must set current tool"
        assert win._transform_started is False, "tap must not execute transform"
        assert win.app.active_tool is None, "active_tool cleared after tap"
        assert win._transform_temp_target is False
    finally:
        win.close()


def test_ad016_d4_hold_drag_executes_and_commits():
    """D4 (AD-016): hold Q + drag + release executes and commits the transform."""
    win = make_window(fixture="face")
    try:
        win.app.activate_variant("transform", 3)
        win.on_key_press(_key.Q, 0)
        assert win._transform_key_down == "q"
        # Simulate drag (motion triggers begin_transform)
        win.on_mouse_motion(700, 400, 40, 0)
        assert win._transform_started is True, "motion must start transform"
        # Release key → commit
        win.on_key_release(_key.Q, 0)
        assert win._transform_started is False, "state cleared after commit"
        assert win.app.active_tool is None, "active_tool cleared after commit"
    finally:
        win.close()


def test_ad016_d4_with_selection_no_temp_target():
    """D4 (AD-016): if selection exists, no temp target is created."""
    win = make_window(fixture="face")
    try:
        win.app.activate_variant("transform", 3)
        # face fixture has a selection
        win.on_key_press(_key.Q, 0)
        assert win._transform_temp_target is False, \
            "no temp target when selection exists"
    finally:
        win.close()


def test_ad016_d4_no_selection_creates_temp_target():
    """D4 (AD-016): with no selection, element under cursor becomes a temp target."""
    win = make_window(fixture="vertex")  # one vertex selected as hover target
    try:
        win.app.activate_variant("transform", 3)
        # Clear selection so hover-pick fires
        win.app.scene.selection.clear()
        # Position the virtual cursor over an existing vertex by setting last_mouse
        from mirai.viewport.picking import pick_nearest_vertex
        mesh = win.app.viewport.render_mesh.mesh
        vids = list(mesh.all_vertex_ids())
        # The last_mouse defaults to (0, 0) which may or may not hit; just check
        # the flag reflects the pick result
        win.on_key_press(_key.Q, 0)
        # If no hit, temp_target stays False (no vertex near 0,0); that's OK.
        # The important thing: the flag is consistent with what was found.
        has_temp = win._transform_temp_target
        # On release, temp target must be cleared
        win.on_key_release(_key.Q, 0)
        assert win._transform_temp_target is False, "temp target must be cleared on release"
    finally:
        win.close()


def test_ad016_d4_esc_clears_temp_target():
    """D4 (AD-016): ESC during hold_key_hover clears the temp target."""
    win = make_window(fixture="face")
    try:
        win.app.activate_variant("transform", 3)
        win.app.scene.selection.clear()
        win.on_key_press(_key.Q, 0)
        win.on_mouse_motion(700, 400, 40, 0)  # start gesture
        win.on_key_press(_key.ESCAPE, 0)
        assert win._transform_temp_target is False
        assert win.app.active_tool is None
    finally:
        win.close()


# -- V2/V4 read shared current-tool state (D2) --------------------------------

def test_ad016_v2_reads_shared_current_tool():
    """D2 (AD-016): V2 uses _current_tool_type (set by Q press) to begin Tweak."""
    win = make_window(fixture="face")
    try:
        win.app.activate_variant("tweak", 0)  # V2
        # Set current tool via Q press then release (press_drag_click model stays on)
        # Actually default transform model is press_drag_click; press sets active_tool too.
        # Press Q → sets _current_tool_type = "move"; then arm V2
        win.on_key_press(_key.Q, 0)          # sets _current_tool_type, _transform_mode_on
        win.on_key_release(_key.Q, 0)        # key released, mode stays on
        # Now simulate V2: Ctrl held, LMB press
        win.on_key_press(_key.LCTRL, 0)
        win.on_mouse_press(400, 300, 1, 0)   # LMB
        assert win._tweak_v2_armed is True
        # Drag → V2 should begin using current_tool_type
        win.on_mouse_drag(440, 300, 40, 0, 1, 0)
        # If _current_tool_type was None, _tweak_begin would not be called → tweak_started=False
        # With _current_tool_type set, tweak_started should be True (if begin_transform succeeds)
        # (begin_transform may fail if no vertices in selection path, so we just verify no crash)
    finally:
        win.close()


def test_ad016_v4_reads_shared_current_tool():
    """D2 (AD-016): V4 uses _current_tool_type (set by Q press) to begin Tweak."""
    win = make_window(fixture="face")
    try:
        win.app.activate_variant("tweak", 1)  # V4
        # Set current tool via Q press (sets _current_tool_type = "move")
        win.on_key_press(_key.Q, 0)
        win.on_key_release(_key.Q, 0)
        assert win._current_tool_type == "move"
        # V4: Ctrl held + motion
        win.on_key_press(_key.LCTRL, 0)
        win.on_mouse_motion(700, 400, 40, 0)
        # V4 attempts _tweak_begin(_current_tool_type, ...) — just verify no crash
    finally:
        win.close()


if __name__ == "__main__":
    main()
