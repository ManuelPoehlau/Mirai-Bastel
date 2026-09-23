"""WP-STAB-03: Session Gate.

While a modal session (Knife, Extrude, Loop Slide, Articulation drag, Tweak,
Gizmo drag, Transform) owns input, nothing outside that session's own inputs,
camera navigation (orbit/pan/zoom) and Esc/commit may create or mutate state
(Artist decision Q4, 2026-09-23).

Uses a real, GL-backed `PlaygroundWindow` driven through the window's own
event handlers — same pattern as `test_wp_stab_04_transform_selection_or_hover.py`
/ `test_wp_stab_08_tweak_temp_target_overlay.py`. This is the headless
equivalent of a live manual check. Picking helpers are monkeypatched where a
test needs a guaranteed hit (Gizmo handle, Articulation pivot, Transform temp
target) so it does not depend on exact screen-to-world picking math.

The original audit's `probe_audit.py` was not in the repository; the cases
below were rebuilt from the WP-STAB-03 spec's repro list and a read of the
five event handlers. Against the pre-gate window (with only `_active_session()`
added so the helpers run) 214 of these tests fail — 182 of the 280 key-matrix
cases, the rest of the matrix being keys that happened to be no-ops already.
The own-key, Esc and own-commit cases (S*, and the "passes through" tests) are
regression guards: they pass before and after, and prove the gate did not take
a session's own inputs away.

    K*  Key matrix: every foreign key pressed during every session type leaves
        the full observable state unchanged (selection, mesh, session tools,
        transform flags, axis/space, focused family, all variant indices,
        display state, history, window not closed). Pre-fix e.g. Q/W/E armed a
        second tool, 1/2/3 cleared the selection, Ctrl+Z undid globally, M/Tab
        switched variants/focus, X/Y/Z/K rewrote constraint/space, F restored
        a bent pose — all mid-session.
    R1  (B1) Q during Knife: no phantom Transform / temp target; Esc ends only
        the Knife, and no leftover session absorbs or cascades further Escs.
    R2  1/2/3 during Extrude: no mode switch, no selection loss.
    R3  Ctrl+Z during Extrude: no global undo.
    R4  (B11) M during a running Extrude-hold / Knife: no variant switch; the
        session's own commit still works afterwards.
    R5  Transform: a *different* Q/W/E key mid-transform cannot swap
        `app.active_tool`; the same key still commits in the press models.
    M*  Mouse gate: Articulation press, Gizmo arm, Tweak-V2 arm, Box-select
        start and selection clicks are blocked inside a session; a gizmo
        handle click inside a Transform sets the constraint only.
    E*  Esc is routed to the owning session: an armed-but-not-dragged Gizmo or
        Tweak-V2 no longer falls through to `close()`, and a bent-idle
        Articulation no longer absorbs the Esc meant for a running Transform.
    V4  A Ctrl held from before Q cannot start a Tweak-V4 inside the Transform.
    C*  Camera orbit/pan/zoom work during every session type; a camera drag
        is not consumed by the session's drag branch and its release does not
        commit the session.
    S*  Esc and each session's own commit gesture still end every session
        type, exactly as before.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pyglet.window import key as _key  # noqa: E402
from pyglet.window import mouse as _mouse  # noqa: E402

from core.selection import SelectionMode  # noqa: E402

# Transform slot variant indices — see playground/window.py's `trans_slot`.
_PRESS_DRAG_CLICK = 0
_HOLD = 1
_PRESS_MODE = 2
_HOLD_KEY_HOVER = 3
# Topology slot: 0 = Extrude hold, 1 = Extrude LMB. Tweak slot: 0 = V2, 1 = V4.
_EXTRUDE_HOLD = 0
_EXTRUDE_LMB = 1
_TWEAK_V2 = 0
_TWEAK_V4 = 1

_CX, _CY = 640, 400       # window centre
_FAR_X, _FAR_Y = 5, 5     # corner — away from the gizmo pivot


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def win_app():
    from playground.app import PlaygroundApp
    from playground.window import PlaygroundWindow
    app = PlaygroundApp()
    win = PlaygroundWindow(app, initial_mesh="cube")
    real_close = type(win).close
    win.close_calls = 0

    def _spy_close():
        win.close_calls += 1
    win.close = _spy_close
    yield win, app
    real_close(win)


@pytest.fixture
def spy_selection(monkeypatch):
    """Record calls to the window's selection-mutating click/box dispatch."""
    import playground.window as window_mod
    calls = []
    monkeypatch.setattr(
        window_mod, "dispatch_click", lambda *a, **k: calls.append("click") or True,
    )
    monkeypatch.setattr(
        window_mod, "handle_box_select", lambda *a, **k: calls.append("box") or True,
    )
    return calls


def _first(ids):
    return sorted(ids)[0]


def _select(app, mode, ids):
    sel = app.scene.selection
    sel.mode = mode
    sel.clear()
    if ids:
        sel.add(set(ids))
    return sel


def _snapshot(win, app) -> dict:
    sel = app.scene.selection
    mesh = app.scene.mesh
    h = app.scene.history
    return {
        "sel": (sel.mode, frozenset(sel.vertices), frozenset(sel.edges), frozenset(sel.faces)),
        "positions": {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()},
        "counts": (len(list(mesh.all_vertex_ids())), len(list(mesh.all_edge_ids())),
                   len(list(mesh.all_face_ids()))),
        "session": win._active_session(),
        "tools": (id(win._knife_tool), id(win._extrude_tool), id(win._loop_slide_tool),
                  id(win._tweak_tool), id(win._gizmo_drag_tool), id(app.active_tool)),
        "transform": (win._transform_key_down, win._transform_mode_on,
                      win._transform_started, win._transform_temp_target),
        "tweak": (win._tweak_active, win._tweak_v2_armed, win._tweak_ctrl_held),
        "gizmo": (win._gizmo_drag_armed, win._gizmo_drag_started),
        "articulation": (id(win._articulation_state), win._articulation_dragging),
        "current_tool": win._current_tool_type,
        "axis": win._axis_constraint,
        "space": win._transform_space,
        "focused": app.focused_family,
        "variants": {fam: slot.active_index for fam, slot in app.slots.items()},
        "select_method": app.select_method,
        "show_vertices": app.show_vertices,
        "display": (app.display_state.mode, app.display_state.wireframe_overlay),
        "history": (len(h._undo_stack), len(h._redo_stack)),
        "box": (win._box_start, win._box_end),
        "closed": win.close_calls,
    }


def _camera(app) -> tuple:
    c = app.camera
    return (c.yaw, c.pitch, tuple(c.target), c.distance)


# -- session starters (real key/mouse paths) ---------------------------------

def _start_knife(win, app, monkeypatch):
    _select(app, SelectionMode.VERTEX, ())
    win.on_key_press(_key.C, 0)
    assert win._active_session() == "knife"


def _start_extrude(win, app, monkeypatch, variant=_EXTRUDE_HOLD):
    app.activate_variant("topology", variant)
    _select(app, SelectionMode.FACE, {_first(app.scene.mesh.all_face_ids())})
    win.on_key_press(_key.R, 0)
    assert win._active_session() == "extrude"


def _start_extrude_lmb(win, app, monkeypatch):
    _start_extrude(win, app, monkeypatch, _EXTRUDE_LMB)


def _start_loop_slide(win, app, monkeypatch):
    # Loop Slide needs a closed quad loop: Loop Insert (I) leaves one selected.
    _select(app, SelectionMode.EDGE, {_first(app.scene.mesh.all_edge_ids())})
    win.on_key_press(_key.I, 0)
    win.on_key_press(_key.G, 0)
    assert win._active_session() == "loop_slide"


def _start_transform(win, app, monkeypatch, variant=_PRESS_DRAG_CLICK):
    app.activate_variant("transform", variant)
    _select(app, SelectionMode.VERTEX, {_first(app.scene.mesh.all_vertex_ids())})
    win.on_key_press(_key.Q, 0)
    win.on_mouse_motion(_CX + 10, _CY + 10, 10, 10)
    assert win._active_session() == "transform"
    assert win._transform_started


def _start_transform_hold(win, app, monkeypatch):
    _start_transform(win, app, monkeypatch, _HOLD)


def _start_tweak_v2(win, app, monkeypatch):
    app.activate_variant("tweak", _TWEAK_V2)
    win._current_tool_type = "move"
    _select(app, SelectionMode.VERTEX, {_first(app.scene.mesh.all_vertex_ids())})
    win.on_key_press(_key.LCTRL, 0)
    win.on_mouse_press(_FAR_X, _FAR_Y, _mouse.LEFT, _key.MOD_CTRL)
    assert win._active_session() == "tweak"


def _start_tweak_v4(win, app, monkeypatch):
    app.activate_variant("tweak", _TWEAK_V4)
    win._current_tool_type = "move"
    _select(app, SelectionMode.VERTEX, {_first(app.scene.mesh.all_vertex_ids())})
    win.on_key_press(_key.LCTRL, 0)
    win.on_mouse_motion(_CX + 10, _CY + 10, 10, 10)
    assert win._active_session() == "tweak"
    assert win._tweak_active


def _start_gizmo(win, app, monkeypatch):
    import playground.window as window_mod
    monkeypatch.setattr(window_mod, "pick_gizmo_handle", lambda *a, **k: "x")
    _select(app, SelectionMode.VERTEX, {_first(app.scene.mesh.all_vertex_ids())})
    win.on_mouse_press(_CX, _CY, _mouse.LEFT, 0)
    assert win._active_session() == "gizmo"


def _start_articulation(win, app, monkeypatch):
    import playground.window as window_mod
    vid = _first(app.scene.mesh.all_vertex_ids())
    monkeypatch.setattr(window_mod, "pick_nearest_vertex", lambda *a, **k: vid)
    app.focused_family = "articulation"
    win.on_mouse_press(_CX, _CY, _mouse.LEFT, 0)
    assert win._active_session() == "articulation"


_STARTERS = {
    "knife": _start_knife,
    "extrude_hold": _start_extrude,
    "extrude_lmb": _start_extrude_lmb,
    "loop_slide": _start_loop_slide,
    "transform_pdc": _start_transform,
    "transform_hold": _start_transform_hold,
    "tweak_v2": _start_tweak_v2,
    "tweak_v4": _start_tweak_v4,
    "gizmo": _start_gizmo,
    "articulation": _start_articulation,
}

# Sessions in which LMB is already held (a second LMB press is impossible).
_LMB_HELD = {"tweak_v2", "gizmo", "articulation"}


# ---------------------------------------------------------------------------
# K* — key matrix
# ---------------------------------------------------------------------------

_KEYS = [
    ("Q", _key.Q, 0), ("W", _key.W, 0), ("E", _key.E, 0),
    ("R", _key.R, 0), ("Shift+R", _key.R, _key.MOD_SHIFT),
    ("S", _key.S, 0), ("C", _key.C, 0), ("Shift+C", _key.C, _key.MOD_SHIFT),
    ("I", _key.I, 0), ("G", _key.G, 0), ("Shift+L", _key.L, _key.MOD_SHIFT),
    ("1", _key._1, 0), ("2", _key._2, 0), ("3", _key._3, 0),
    ("M", _key.M, 0), ("Shift+M", _key.M, _key.MOD_SHIFT), ("Tab", _key.TAB, 0),
    ("D", _key.D, 0), ("Shift+D", _key.D, _key.MOD_SHIFT), ("V", _key.V, 0),
    ("X", _key.X, 0), ("Y", _key.Y, 0), ("Z", _key.Z, 0),
    ("Shift+X", _key.X, _key.MOD_SHIFT), ("K", _key.K, 0), ("F", _key.F, 0),
    ("Ctrl+Z", _key.Z, _key.MOD_CTRL), ("Ctrl+Y", _key.Y, _key.MOD_CTRL),
    ("Ctrl+Shift+Z", _key.Z, _key.MOD_CTRL | _key.MOD_SHIFT),
    ("Enter", _key.ENTER, 0),
]

# The owning session's own keys (per the ownership matrix) — excluded here,
# covered by the dedicated tests further down.
_OWN = {
    "knife": {"Enter", "Ctrl+Z", "Ctrl+Y", "Ctrl+Shift+Z"},
    "transform_pdc": {"Q", "X", "Y", "Z", "Shift+X", "K"},
    "articulation": {"F"},
    # Hold models: the held key is physically down, so it cannot be pressed
    # again — and its release is the session's own commit.
    "extrude_hold": {"R", "Shift+R"},
    "loop_slide": {"G"},
    "transform_hold": {"Q", "X", "Y", "Z", "Shift+X", "K"},
}

_MATRIX = [
    pytest.param(s, label, sym, mods, id=f"{s}-{label}")
    for s in _STARTERS
    for (label, sym, mods) in _KEYS
    if label not in _OWN.get(s, set())
]


@pytest.mark.parametrize("session,label,symbol,modifiers", _MATRIX)
def test_foreign_key_is_blocked_during_session(win_app, monkeypatch, session, label, symbol, modifiers):
    win, app = win_app
    _STARTERS[session](win, app, monkeypatch)
    before = _snapshot(win, app)
    win.on_key_press(symbol, modifiers)
    win.on_key_release(symbol, modifiers)
    after = _snapshot(win, app)
    changed = {k for k in before if before[k] != after[k]}
    assert not changed, f"{label} during {session} mutated: {sorted(changed)}"


# ---------------------------------------------------------------------------
# R* — spec repro set
# ---------------------------------------------------------------------------

def test_r1_q_during_knife_no_phantom_transform_esc_ends_only_knife(win_app, monkeypatch):
    import playground.window as window_mod
    win, app = win_app
    _start_knife(win, app, monkeypatch)
    vid = _first(app.scene.mesh.all_vertex_ids())
    # Something under the cursor: pre-gate, Q added it as a Transform temp target.
    monkeypatch.setattr(window_mod, "pick_component", lambda *a, **k: vid)

    win.on_key_press(_key.Q, 0)
    assert app.active_tool is None
    assert win._transform_mode_on is False and win._transform_key_down is None
    assert win._transform_temp_target is False
    assert app.scene.selection.is_empty()

    win.on_key_press(_key.ESCAPE, 0)
    assert win._knife_tool is None
    assert win._active_session() is None
    assert win.close_calls == 0, "Esc must end only the Knife"
    # Nothing left over to absorb a further Esc: the next Esc is the plain
    # "nothing active" Esc, exactly once.
    win.on_key_press(_key.ESCAPE, 0)
    assert win.close_calls == 1


def test_r2_mode_keys_during_extrude_keep_mode_and_selection(win_app, monkeypatch):
    win, app = win_app
    _start_extrude(win, app, monkeypatch)
    sel = app.scene.selection
    faces = frozenset(sel.faces)
    tool = win._extrude_tool
    for sym in (_key._1, _key._2, _key._3):
        win.on_key_press(sym, 0)
        assert sel.mode is SelectionMode.FACE
        assert frozenset(sel.faces) == faces
        assert win._extrude_tool is tool
    win.on_key_release(_key.R, 0)          # own commit still works
    assert win._extrude_tool is None


def test_r3_ctrl_z_during_extrude_is_not_global_undo(win_app, monkeypatch):
    win, app = win_app
    calls = []
    monkeypatch.setattr(app, "undo", lambda: calls.append("undo"))
    monkeypatch.setattr(app, "redo", lambda: calls.append("redo"))
    _start_extrude(win, app, monkeypatch)
    win.on_key_press(_key.Z, _key.MOD_CTRL)
    win.on_key_press(_key.Y, _key.MOD_CTRL)
    assert calls == []
    assert win._extrude_tool is not None
    win.on_key_press(_key.ESCAPE, 0)
    assert win._extrude_tool is None and win.close_calls == 0


def test_r4_m_during_extrude_hold_no_variant_switch(win_app, monkeypatch):
    win, app = win_app
    _start_extrude(win, app, monkeypatch)
    app.focused_family = "topology"
    n_faces = len(list(app.scene.mesh.all_face_ids()))
    win.on_key_press(_key.M, 0)
    assert app.slots["topology"].active_index == _EXTRUDE_HOLD
    # Pre-gate the model flipped to "lmb" here, so R release no longer committed.
    win.on_key_release(_key.R, 0)
    assert win._extrude_tool is None
    assert len(list(app.scene.mesh.all_face_ids())) == n_faces


def test_r4_m_during_knife_does_not_cancel_or_switch(win_app, monkeypatch):
    win, app = win_app
    app.focused_family = "knife"
    _start_knife(win, app, monkeypatch)
    knife = win._knife_tool
    win.on_key_press(_key.M, 0)
    win.on_key_press(_key.TAB, 0)
    assert win._knife_tool is knife
    assert app.slots["knife"].active_index == 0
    assert app.focused_family == "knife"


def test_r5_hold_transform_other_key_cannot_swap_tool(win_app, monkeypatch):
    win, app = win_app
    _start_transform_hold(win, app, monkeypatch)
    tool = app.active_tool
    win.on_key_press(_key.W, 0)
    assert app.active_tool is tool
    assert win._current_tool_type == "move"
    assert win._transform_key_down == "q"
    win.on_key_release(_key.W, 0)
    assert app.active_tool is tool
    win.on_key_release(_key.Q, 0)          # own commit
    assert win._active_session() is None


def test_r5_press_mode_same_key_commits_other_key_blocked(win_app, monkeypatch):
    win, app = win_app
    _start_transform(win, app, monkeypatch, _PRESS_MODE)
    vid = _first(app.scene.selection.vertices)
    moved = app.scene.mesh.vertex_position(vid)
    win.on_key_release(_key.Q, 0)          # press model: mode stays on
    win.on_key_press(_key.E, 0)
    assert win._transform_mode_on and win._current_tool_type == "move"
    win.on_key_press(_key.Q, 0)            # second press of the same key = commit
    assert win._active_session() is None
    assert app.scene.mesh.vertex_position(vid) == moved


def test_transform_axis_and_space_keys_pass_through(win_app, monkeypatch):
    win, app = win_app
    app.activate_variant("transform", _PRESS_MODE)
    _select(app, SelectionMode.VERTEX, {_first(app.scene.mesh.all_vertex_ids())})
    win.on_key_press(_key.Q, 0)
    win.on_key_press(_key.X, 0)
    assert win._axis_constraint == "x"
    win.on_key_press(_key.Z, _key.MOD_SHIFT)
    assert win._axis_constraint == "xy"
    win.on_key_press(_key.K, 0)
    assert win._transform_space == "normal" and win._axis_constraint is None
    assert win._active_session() == "transform"


def test_knife_own_keys_pass_through(win_app, monkeypatch):
    win, app = win_app
    _start_knife(win, app, monkeypatch)
    calls = []
    monkeypatch.setattr(win._knife_tool, "undo_step", lambda: calls.append("undo"))
    monkeypatch.setattr(win._knife_tool, "redo_step", lambda: calls.append("redo"))
    win.on_key_press(_key.Z, _key.MOD_CTRL)
    win.on_key_press(_key.Y, _key.MOD_CTRL)
    win.on_key_press(_key.Z, _key.MOD_CTRL | _key.MOD_SHIFT)
    assert calls == ["undo", "redo", "redo"]
    win.on_key_press(_key.ENTER, 0)
    assert win._knife_tool is None and win.close_calls == 0


def test_articulation_f_passes_through(win_app, monkeypatch):
    win, app = win_app
    _start_articulation(win, app, monkeypatch)
    win.on_key_press(_key.F, 0)
    assert win._articulation_state is None
    assert win._active_session() is None


# ---------------------------------------------------------------------------
# M* — mouse gate
# ---------------------------------------------------------------------------

def test_articulation_press_blocked_during_knife(win_app, monkeypatch):
    import playground.window as window_mod
    win, app = win_app
    vid = _first(app.scene.mesh.all_vertex_ids())
    monkeypatch.setattr(window_mod, "pick_nearest_vertex", lambda *a, **k: vid)
    app.focused_family = "articulation"
    _start_knife(win, app, monkeypatch)
    win.on_mouse_press(_CX, _CY, _mouse.LEFT, 0)
    assert win._articulation_state is None
    assert win._active_session() == "knife"
    win.on_mouse_release(_CX, _CY, _mouse.LEFT, 0)
    assert win._knife_tool is not None


def test_gizmo_press_during_extrude_lmb_does_not_arm_and_release_commits(win_app, monkeypatch):
    import playground.window as window_mod
    win, app = win_app
    monkeypatch.setattr(window_mod, "pick_gizmo_handle", lambda *a, **k: "x")
    _start_extrude_lmb(win, app, monkeypatch)
    win.on_mouse_press(_CX, _CY, _mouse.LEFT, 0)
    assert win._gizmo_drag_armed is False
    win.on_mouse_drag(_CX + 5, _CY + 30, 5, 30, _mouse.LEFT, 0)
    win.on_mouse_release(_CX + 5, _CY + 30, _mouse.LEFT, 0)
    # Pre-gate the gizmo branch swallowed the release; Extrude never committed.
    assert win._extrude_tool is None
    assert win._active_session() is None


def test_gizmo_click_during_transform_sets_constraint_only(win_app, monkeypatch):
    import playground.window as window_mod
    win, app = win_app
    _start_transform(win, app, monkeypatch)            # Press-Drag-Click, started
    tool = app.active_tool
    monkeypatch.setattr(window_mod, "pick_gizmo_handle", lambda *a, **k: "y")
    win.on_mouse_press(_CX, _CY, _mouse.LEFT, 0)
    assert win._axis_constraint == "y"
    assert win._gizmo_drag_armed is False and win._gizmo_drag_tool is None
    assert app.active_tool is tool
    win.on_mouse_release(_CX, _CY, _mouse.LEFT, 0)     # PDC's own commit
    assert win._active_session() is None


@pytest.mark.parametrize("session", ["knife", "extrude_hold", "loop_slide",
                                     "transform_hold", "tweak_v4"])
def test_selection_click_blocked_during_session(win_app, monkeypatch, spy_selection, session):
    win, app = win_app
    _STARTERS[session](win, app, monkeypatch)
    if session == "knife":
        # Knife's LMB is its own; a plain RMB click is foreign.
        button = _mouse.RIGHT
    else:
        button = _mouse.LEFT
    before = _snapshot(win, app)
    win.on_mouse_press(_FAR_X, _FAR_Y, button, 0)
    win.on_mouse_release(_FAR_X, _FAR_Y, button, 0)
    assert spy_selection == []
    assert _snapshot(win, app)["sel"] == before["sel"]
    assert win._active_session() == before["session"]


def test_box_select_not_started_during_session(win_app, monkeypatch, spy_selection):
    from playground.selector import SelectMethod
    win, app = win_app
    app.select_method = SelectMethod.BOX
    _start_transform(win, app, monkeypatch, _PRESS_MODE)
    win.on_mouse_press(_FAR_X, _FAR_Y, _mouse.LEFT, 0)
    assert win._box_start is None
    win.on_mouse_release(_FAR_X + 200, _FAR_Y + 200, _mouse.LEFT, 0)
    assert spy_selection == []


def test_tweak_v2_arm_blocked_during_transform(win_app, monkeypatch):
    win, app = win_app
    app.activate_variant("tweak", _TWEAK_V2)
    win.on_key_press(_key.LCTRL, 0)                    # held before the session
    _start_transform(win, app, monkeypatch, _PRESS_MODE)
    win.on_mouse_press(_FAR_X, _FAR_Y, _mouse.LEFT, _key.MOD_CTRL)
    assert win._tweak_v2_armed is False


def test_v4_motion_does_not_start_tweak_inside_transform(win_app, monkeypatch):
    win, app = win_app
    app.activate_variant("tweak", _TWEAK_V4)
    _select(app, SelectionMode.VERTEX, {_first(app.scene.mesh.all_vertex_ids())})
    win.on_key_press(_key.LCTRL, 0)                    # Ctrl held, no motion yet
    win.on_key_press(_key.Q, _key.MOD_CTRL)            # Transform armed
    win.on_mouse_motion(_CX + 10, _CY + 10, 10, 10)
    assert win._tweak_active is False
    assert win._transform_started is True


# ---------------------------------------------------------------------------
# E* — Esc routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("session", ["gizmo", "tweak_v2"])
def test_esc_on_armed_mouse_session_does_not_close_window(win_app, monkeypatch, spy_selection, session):
    win, app = win_app
    _STARTERS[session](win, app, monkeypatch)
    win.on_key_press(_key.ESCAPE, 0)
    assert win.close_calls == 0
    assert win._active_session() is None
    # The still-held LMB's release must not become a selection click.
    win.on_mouse_release(_CX, _CY, _mouse.LEFT, 0)
    assert spy_selection == []


def test_esc_during_transform_with_bent_articulation_cancels_transform(win_app, monkeypatch):
    win, app = win_app
    _start_articulation(win, app, monkeypatch)
    win.on_mouse_drag(_CX + 40, _CY, 40, 0, _mouse.LEFT, 0)
    win.on_mouse_release(_CX + 40, _CY, _mouse.LEFT, 0)
    assert win._articulation_state is not None and win._articulation_state.is_bent
    app.focused_family = "selection"
    _start_transform(win, app, monkeypatch, _PRESS_MODE)
    state = win._articulation_state
    win.on_key_press(_key.ESCAPE, 0)
    assert win._active_session() is None, "Esc must cancel the running Transform"
    assert win._articulation_state is state, "bent pose is not the Esc owner"


# ---------------------------------------------------------------------------
# C* — camera navigation during every session
# ---------------------------------------------------------------------------

def _session_state(win, app) -> dict:
    snap = _snapshot(win, app)
    return {k: snap[k] for k in ("positions", "counts", "session", "tools", "transform", "sel")}


@pytest.mark.parametrize("session", list(_STARTERS))
def test_camera_orbit_pan_zoom_during_session(win_app, monkeypatch, spy_selection, session):
    win, app = win_app
    _STARTERS[session](win, app, monkeypatch)
    before = _session_state(win, app)

    # Orbit: Alt+LMB, or Alt+RMB where LMB is already held by the session.
    orbit_button = _mouse.RIGHT if session in _LMB_HELD else _mouse.LEFT
    cam = _camera(app)
    win.on_mouse_press(_CX, _CY, orbit_button, _key.MOD_ALT)
    win.on_mouse_drag(_CX + 30, _CY + 20, 30, 20, orbit_button, _key.MOD_ALT)
    win.on_mouse_release(_CX + 30, _CY + 20, orbit_button, _key.MOD_ALT)
    assert _camera(app)[:2] != cam[:2], "orbit must reach the camera"

    # Pan: MMB drag.
    cam = _camera(app)
    win.on_mouse_press(_CX, _CY, _mouse.MIDDLE, 0)
    win.on_mouse_drag(_CX + 30, _CY + 20, 30, 20, _mouse.MIDDLE, 0)
    win.on_mouse_release(_CX + 30, _CY + 20, _mouse.MIDDLE, 0)
    assert _camera(app)[2] != cam[2], "pan must reach the camera"

    # Pan: Shift+LMB/RMB drag.
    cam = _camera(app)
    win.on_mouse_press(_CX, _CY, orbit_button, _key.MOD_SHIFT)
    win.on_mouse_drag(_CX + 30, _CY + 20, 30, 20, orbit_button, _key.MOD_SHIFT)
    win.on_mouse_release(_CX + 30, _CY + 20, orbit_button, _key.MOD_SHIFT)
    assert _camera(app)[2] != cam[2], "Shift-pan must reach the camera"

    # Zoom: scroll.
    cam = _camera(app)
    win.on_mouse_scroll(_CX, _CY, 0, 1)
    assert _camera(app)[3] != cam[3]

    # The session neither advanced, committed nor ended, and nothing got selected.
    assert _session_state(win, app) == before
    assert spy_selection == []


# ---------------------------------------------------------------------------
# S* — Esc and the session's own commit still end every session type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("session", list(_STARTERS))
def test_esc_ends_every_session(win_app, monkeypatch, session):
    win, app = win_app
    _STARTERS[session](win, app, monkeypatch)
    win.on_key_press(_key.ESCAPE, 0)
    assert win._active_session() is None
    assert win.close_calls == 0


def _commit(win, app, session):
    if session == "knife":
        win.on_key_press(_key.ENTER, 0)
    elif session == "extrude_hold":
        win.on_key_release(_key.R, 0)
    elif session in ("extrude_lmb",):
        win.on_mouse_press(_CX, _CY, _mouse.LEFT, 0)
        win.on_mouse_release(_CX, _CY, _mouse.LEFT, 0)
    elif session == "loop_slide":
        win.on_key_release(_key.G, 0)
    elif session == "transform_pdc":
        win.on_mouse_press(_FAR_X, _FAR_Y, _mouse.LEFT, 0)
        win.on_mouse_release(_FAR_X, _FAR_Y, _mouse.LEFT, 0)
    elif session == "transform_hold":
        win.on_key_release(_key.Q, 0)
    elif session == "tweak_v4":
        win.on_key_release(_key.LCTRL, 0)
    elif session in ("tweak_v2", "gizmo", "articulation"):
        win.on_mouse_release(_CX, _CY, _mouse.LEFT, 0)


@pytest.mark.parametrize("session", list(_STARTERS))
def test_own_commit_ends_every_session(win_app, monkeypatch, session):
    win, app = win_app
    _STARTERS[session](win, app, monkeypatch)
    _commit(win, app, session)
    assert win._active_session() is None
    assert win.close_calls == 0


def test_transform_press_mode_and_hold_key_hover_commit(win_app, monkeypatch):
    win, app = win_app
    _start_transform(win, app, monkeypatch, _PRESS_MODE)
    win.on_key_release(_key.Q, 0)
    win.on_key_press(_key.Q, 0)
    assert win._active_session() is None
    _start_transform(win, app, monkeypatch, _HOLD_KEY_HOVER)
    win.on_key_release(_key.Q, 0)
    assert win._active_session() is None
