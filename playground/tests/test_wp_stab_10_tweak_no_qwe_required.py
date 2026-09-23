"""WP-STAB-10: Tweak V2/V4 work from a fresh app start before any Q/W/E press.

_current_tool_type is None until Q/W/E is pressed. V2 and V4 previously gated
on `is not None` and silently no-opped, so a fresh-session Ctrl+drag did nothing.
Fix: use `self._current_tool_type or "move"`, matching the Gizmo precedent in
the same file.

    S1  V2 (Ctrl+LMB arm → drag): fresh session (no Q/W/E), vertex pre-selected,
        _tweak_v2_armed set directly, on_mouse_drag fires — vertex moves.
    S2  V4 (Ctrl held + motion): fresh session, vertex pre-selected,
        _tweak_ctrl_held set directly, on_mouse_motion fires — vertex moves.
    S3  Regression — V2: after an explicit Q/W/E press, that tool type is used
        (not overridden by the "move" fallback).
    S4  Regression — V4: same regression check.
    S5  _current_tool_type is NOT set as a side effect of the fallback — a
        fresh-session Ctrl+drag must not silently persist "move" as the standing
        tool (Gizmo's own behaviour: local default, not a global state change).
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
from pyglet.window import mouse as _mouse  # noqa: E402


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


def _select_vertex(app, win, vid):
    sel = app.scene.selection
    sel.mode = SelectionMode.VERTEX
    sel.clear()
    sel.add({vid})
    win._rebuild_selection_vbo()


def _switch_to_v4(app):
    slot = app.slots.get("tweak")
    assert slot is not None
    for i, entry in enumerate(slot.variants):
        if getattr(entry.experiment, "tweak_variant", None) == "v4":
            slot.activate(i)
            return
    pytest.skip("no V4 variant registered in tweak slot")


# ---------------------------------------------------------------------------
# S1 — V2: fresh session, no Q/W/E, Ctrl+LMB arm → drag moves vertex
# ---------------------------------------------------------------------------

def test_s1_v2_works_without_prior_qwe(cube_win):
    win, app = cube_win

    assert win._active_tweak_variant() == "v2", "expected V2 as default tweak variant"
    assert win._current_tool_type is None, "precondition: no Q/W/E pressed yet"

    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    _select_vertex(app, win, vid)
    pos_before = tuple(app.scene.mesh.vertex_position(vid))

    win._tweak_v2_armed = True
    win.on_mouse_drag(640, 400, 30, 0, _mouse.LEFT, 0)

    pos_after = tuple(app.scene.mesh.vertex_position(vid))
    assert pos_after != pos_before, "V2 Tweak did nothing — vertex did not move"

    win._tweak_commit()


# ---------------------------------------------------------------------------
# S2 — V4: fresh session, no Q/W/E, Ctrl held + motion moves vertex
# ---------------------------------------------------------------------------

def test_s2_v4_works_without_prior_qwe(cube_win):
    win, app = cube_win

    _switch_to_v4(app)
    assert win._active_tweak_variant() == "v4"
    assert win._current_tool_type is None, "precondition: no Q/W/E pressed yet"

    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    _select_vertex(app, win, vid)
    pos_before = tuple(app.scene.mesh.vertex_position(vid))

    win._tweak_ctrl_held = True
    win.on_mouse_motion(640, 400, 30, 0)

    pos_after = tuple(app.scene.mesh.vertex_position(vid))
    assert pos_after != pos_before, "V4 Tweak did nothing — vertex did not move"

    win._tweak_commit()


# ---------------------------------------------------------------------------
# S3 — V2 regression: explicit Q/W/E tool choice is honoured, not overridden
# ---------------------------------------------------------------------------

def test_s3_v2_respects_explicit_tool_type(cube_win, monkeypatch):
    win, app = cube_win

    assert win._active_tweak_variant() == "v2"

    # Simulate a Q press: set current tool to "rotate".
    win._current_tool_type = "rotate"

    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    _select_vertex(app, win, vid)

    # Capture what tool type _tweak_begin is actually called with.
    called_with = []
    original = win._tweak_begin
    monkeypatch.setattr(win, "_tweak_begin", lambda tt, x, y: called_with.append(tt) or original(tt, x, y))

    win._tweak_v2_armed = True
    win.on_mouse_drag(640, 400, 30, 0, _mouse.LEFT, 0)

    assert called_with, "_tweak_begin was not called at all"
    assert called_with[0] == "rotate", (
        f"expected 'rotate' (artist's Q/W/E choice), got '{called_with[0]}'"
    )

    win._tweak_commit()


# ---------------------------------------------------------------------------
# S4 — V4 regression: explicit Q/W/E tool choice is honoured
# ---------------------------------------------------------------------------

def test_s4_v4_respects_explicit_tool_type(cube_win, monkeypatch):
    win, app = cube_win

    _switch_to_v4(app)
    win._current_tool_type = "scale"

    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    _select_vertex(app, win, vid)

    called_with = []
    original = win._tweak_begin
    monkeypatch.setattr(win, "_tweak_begin", lambda tt, x, y: called_with.append(tt) or original(tt, x, y))

    win._tweak_ctrl_held = True
    win.on_mouse_motion(640, 400, 30, 0)

    assert called_with, "_tweak_begin was not called at all"
    assert called_with[0] == "scale", (
        f"expected 'scale' (artist's Q/W/E choice), got '{called_with[0]}'"
    )

    win._tweak_commit()


# ---------------------------------------------------------------------------
# S5 — fallback does NOT persist into _current_tool_type
# ---------------------------------------------------------------------------

def test_s5_fallback_does_not_set_current_tool_type(cube_win):
    win, app = cube_win

    assert win._active_tweak_variant() == "v2"
    assert win._current_tool_type is None

    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    _select_vertex(app, win, vid)

    win._tweak_v2_armed = True
    win.on_mouse_drag(640, 400, 30, 0, _mouse.LEFT, 0)

    assert win._current_tool_type is None, (
        "_current_tool_type must remain None after a fallback-'move' Ctrl+drag"
    )

    win._tweak_commit()
