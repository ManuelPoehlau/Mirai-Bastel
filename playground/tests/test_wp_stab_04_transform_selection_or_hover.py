"""WP-STAB-04: Transform arms via selection-or-hover, refuses only when both
are empty.

Uses a real, GL-backed `PlaygroundWindow` driven through the window's own
key/mouse dispatch (`on_key_press`/`on_mouse_drag`/`on_mouse_release`/
`on_key_release`) — same pattern as `test_wp_stab_08_tweak_temp_target_overlay.py`
and `test_gizmo.py`. This is the "headless equivalent" of a live manual
check; a live GUI check was not possible in this environment.
`pick_component` is monkeypatched (same technique as
`test_wp_stab_08_tweak_temp_target_overlay.py`) so the test does not depend
on exact screen-to-world picking math.

Root cause (pre-fix): `press_mode`/`press_drag_click`/`hold` armed
`self.app.active_tool` (and `_transform_key_down`/`_transform_mode_on`)
unconditionally on Q/W/E, regardless of selection state. With an empty
selection and nothing under the cursor, `begin_transform()` then silently
failed on every subsequent motion/drag event — `active_tool` stayed set,
the HUD kept showing "Transform: ...", and a stray mouse move after arming
could look like a phantom, dead tool. `hold_key_hover` already added a
hit element as a temp target when the selection was empty, but still armed
`active_tool` unconditionally even when the hit-test also came up empty.

    S1  Hold model, empty selection + hit under cursor at key-press: arms via
        temp target, dragging transforms that element, highlight overlay is
        present and correct, clears on key-release commit.
    S2  Hold model, empty selection + nothing under cursor: refused — no
        `active_tool`, no `_transform_key_down`, HUD shows a refusal
        message, mesh unchanged. Regression check for the original bug:
        subsequent mouse motion produces no phantom transform (mesh
        unchanged, no crash).
    S3  Press-Drag-Click model (the default variant, index 0): same
        arm-via-temp-target behavior, committed via LMB release instead of
        key release.
    S4  Press-Drag-Click model: same refusal behavior as S2.
    S5  hold_key_hover: refusal behavior — the model already added a
        temp target when *something* was under the cursor, but previously
        never refused when nothing was.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.selection import SelectionMode  # noqa: E402


# Transform slot variant indices — see playground/window.py's `trans_slot`
# registration: 0=press_drag_click, 1=hold, 2=press_mode, 3=hold_key_hover.
_PRESS_DRAG_CLICK = 0
_HOLD = 1
_HOLD_KEY_HOVER = 3


def _window(initial_mesh: str = "cube"):
    from playground.app import PlaygroundApp
    from playground.window import PlaygroundWindow
    app = PlaygroundApp()
    win = PlaygroundWindow(app, initial_mesh=initial_mesh)
    return win, app


@pytest.fixture
def cube_win():
    win, app = _window("cube")
    yield win, app
    win.close()


def _empty_vertex_selection(app):
    sel = app.scene.selection
    sel.mode = SelectionMode.VERTEX
    sel.clear()
    assert sel.is_empty()
    return sel


def _patch_pick(monkeypatch, result):
    """Monkeypatch window.py's `pick_component` to return a fixed result
    (a vertex id, or None to simulate nothing under the cursor)."""
    import playground.window as window_mod
    monkeypatch.setattr(
        window_mod, "pick_component",
        lambda camera, mesh, s, sx, sy, w, h: result,
    )


# ---------------------------------------------------------------------------
# S1 — Hold model: arms via temp target and transforms it
# ---------------------------------------------------------------------------

def test_hold_arms_via_temp_target_and_transforms(cube_win, monkeypatch):
    from pyglet.window import key as _key
    from pyglet.window import mouse as _mouse
    win, app = cube_win
    win.app.activate_variant("transform", _HOLD)
    sel = _empty_vertex_selection(app)
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    before = app.scene.mesh.vertex_position(vid)
    _patch_pick(monkeypatch, vid)

    win.on_key_press(_key.Q, 0)  # Move
    assert vid in sel.vertices, "empty selection + hit must add a temp target"
    assert win.app.active_tool is not None
    assert win._transform_temp_target is True
    assert win._vlist_sel_verts is not None, "highlight overlay must be rebuilt immediately"

    win.on_mouse_drag(650, 400, 10, 10, _mouse.LEFT, 0)
    assert win._transform_started is True
    after_drag = app.scene.mesh.vertex_position(vid)
    assert after_drag != before, "dragging the temp target must move it"

    win.on_key_release(_key.Q, 0)  # commit
    assert win.app.active_tool is None
    assert win._transform_temp_target is False
    assert sel.is_empty(), "temp target must not leak into the real Selection"
    assert win._vlist_sel_verts is None


# ---------------------------------------------------------------------------
# S2 — Hold model: refuses when nothing is selected and nothing is hit
# ---------------------------------------------------------------------------

def test_hold_refuses_when_nothing_to_transform(cube_win, monkeypatch):
    from pyglet.window import key as _key
    win, app = cube_win
    win.app.activate_variant("transform", _HOLD)
    sel = _empty_vertex_selection(app)
    positions_before = [
        app.scene.mesh.vertex_position(v) for v in sorted(app.scene.mesh.all_vertex_ids())
    ]
    _patch_pick(monkeypatch, None)

    win.on_key_press(_key.Q, 0)  # Move

    assert win.app.active_tool is None, "must not arm when there is nothing to transform"
    assert win._transform_key_down is None
    assert win._transform_temp_target is False
    assert sel.is_empty()
    assert "Nothing to transform" in win._hud.action_line
    assert "Move" in win._hud.action_line

    # Regression check: subsequent mouse motion must not produce a phantom
    # transform (no crash, mesh unchanged).
    win.on_mouse_motion(650, 400, 5, 5)
    win.on_mouse_drag(660, 410, 10, 10, 1, 0)
    positions_after = [
        app.scene.mesh.vertex_position(v) for v in sorted(app.scene.mesh.all_vertex_ids())
    ]
    assert positions_after == positions_before


# ---------------------------------------------------------------------------
# S3 — Press-Drag-Click model (default variant): arms via temp target
# ---------------------------------------------------------------------------

def test_press_drag_click_arms_via_temp_target_and_transforms(cube_win, monkeypatch):
    from pyglet.window import key as _key
    from pyglet.window import mouse as _mouse
    win, app = cube_win
    win.app.activate_variant("transform", _PRESS_DRAG_CLICK)
    sel = _empty_vertex_selection(app)
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    before = app.scene.mesh.vertex_position(vid)
    _patch_pick(monkeypatch, vid)

    win.on_key_press(_key.Q, 0)  # Move
    assert vid in sel.vertices
    assert win.app.active_tool is not None
    assert win._transform_temp_target is True
    assert win._vlist_sel_verts is not None

    win.on_mouse_drag(650, 400, 10, 10, _mouse.LEFT, 0)
    assert win._transform_started is True
    assert app.scene.mesh.vertex_position(vid) != before

    win.on_mouse_release(650, 400, _mouse.LEFT, 0)  # commit
    assert win.app.active_tool is None
    assert win._transform_temp_target is False
    assert sel.is_empty()
    assert win._vlist_sel_verts is None


# ---------------------------------------------------------------------------
# S4 — Press-Drag-Click model: refuses when nothing to transform
# ---------------------------------------------------------------------------

def test_press_drag_click_refuses_when_nothing_to_transform(cube_win, monkeypatch):
    from pyglet.window import key as _key
    win, app = cube_win
    win.app.activate_variant("transform", _PRESS_DRAG_CLICK)
    sel = _empty_vertex_selection(app)
    positions_before = [
        app.scene.mesh.vertex_position(v) for v in sorted(app.scene.mesh.all_vertex_ids())
    ]
    _patch_pick(monkeypatch, None)

    win.on_key_press(_key.E, 0)  # Scale

    assert win.app.active_tool is None
    assert win._transform_mode_on is False
    assert win._transform_temp_target is False
    assert sel.is_empty()
    assert "Nothing to transform" in win._hud.action_line
    assert "Scale" in win._hud.action_line

    win.on_mouse_motion(650, 400, 5, 5)
    win.on_mouse_drag(660, 410, 10, 10, 1, 0)
    positions_after = [
        app.scene.mesh.vertex_position(v) for v in sorted(app.scene.mesh.all_vertex_ids())
    ]
    assert positions_after == positions_before


# ---------------------------------------------------------------------------
# S5 — hold_key_hover: refuses when nothing to transform (was previously
# arming unconditionally even with no hit)
# ---------------------------------------------------------------------------

def test_hold_key_hover_refuses_when_nothing_to_transform(cube_win, monkeypatch):
    from pyglet.window import key as _key
    win, app = cube_win
    win.app.activate_variant("transform", _HOLD_KEY_HOVER)
    sel = _empty_vertex_selection(app)
    _patch_pick(monkeypatch, None)

    win.on_key_press(_key.Q, 0)  # Move

    assert win.app.active_tool is None
    assert win._transform_key_down is None
    assert win._transform_temp_target is False
    assert sel.is_empty()
    assert "Nothing to transform" in win._hud.action_line
    assert "Move" in win._hud.action_line
