"""WP-STAB-02 (R-SEL-2, minimal): hover reset on mode change / Knife-begin.

Uses a real, GL-backed `PlaygroundWindow` (same pattern as
`test_ad017_knife_keys.py`), driven through the real `on_key_press`
dispatch that the UI itself uses. This is the "headless equivalent" of a
live manual check across all three component modes plus Knife-start,
documented in place of an interactive check that isn't possible in this
environment.

    S1  Pressing "2" (Edge mode) while a Vertex is hovered clears the hover
        (sel.hovered, the window-local hover key, and the hover overlay VBO).
    S2  Pressing "1" (Vertex mode) while an Edge is hovered clears the hover.
        Also covers Knife-begin: entering Knife (contextual C, empty
        selection) clears a leftover regular-selection hover.
    S10 An id collision across component kinds (vertex id 5 vs. edge id 5)
        does not suppress a hover update it should have produced. Before the
        fix, on_mouse_motion compared `hit != sel.hovered` as bare ids; a
        stale Vertex-mode hover of id 5 would then be indistinguishable from
        a genuine Edge-mode hover of id 5, so a legitimate hover change
        would have been silently dropped. The fix compares (mode, id) tuples
        via the window-local `_hover_key`.
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


def _seed_hover(win, app, mode: SelectionMode, hovered_id: int) -> None:
    """Simulate an already-active hover (as on_mouse_motion would set it)
    without needing a real mouse pick — same state, cheaper to set up."""
    from playground.vbo_builder import (
        build_selection_data, build_selection_edge_data, build_selection_vertex_data,
    )
    sel = app.scene.selection
    sel.mode = mode
    sel.hovered = hovered_id
    win._hover_key = (mode, hovered_id)
    if mode is SelectionMode.VERTEX:
        positions = build_selection_vertex_data(app.scene.mesh, {hovered_id})
        prim = 0
    elif mode is SelectionMode.EDGE:
        positions = build_selection_edge_data(app.scene.mesh, {hovered_id})
        prim = 1
    else:
        positions = build_selection_data(app.scene.mesh, {hovered_id})
        prim = 4
    n = len(positions) // 3
    win._vlist_hover = win._overlay_program.vertex_list(n, prim, position=("f", positions))


# ---------------------------------------------------------------------------
# S1 — mode switch (1/2/3) clears hover: Vertex -> Edge
# ---------------------------------------------------------------------------

def test_s1_mode_switch_to_edge_clears_vertex_hover(cube_win):
    from pyglet.window import key as _key
    win, app = cube_win
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    _seed_hover(win, app, SelectionMode.VERTEX, vid)
    assert win._vlist_hover is not None

    win.on_key_press(_key._2, 0)  # 2: Edge mode

    assert app.scene.selection.mode is SelectionMode.EDGE
    assert app.scene.selection.hovered is None
    assert win._hover_key is None
    assert win._vlist_hover is None


# ---------------------------------------------------------------------------
# S2 — mode switch (1/2/3) clears hover: Edge -> Vertex; Knife-begin clears hover
# ---------------------------------------------------------------------------

def test_s2_mode_switch_to_vertex_clears_edge_hover(cube_win):
    from pyglet.window import key as _key
    win, app = cube_win
    eid = next(iter(app.scene.mesh.all_edge_ids()))
    _seed_hover(win, app, SelectionMode.EDGE, eid)
    assert win._vlist_hover is not None

    win.on_key_press(_key._1, 0)  # 1: Vertex mode

    assert app.scene.selection.mode is SelectionMode.VERTEX
    assert app.scene.selection.hovered is None
    assert win._hover_key is None
    assert win._vlist_hover is None


def test_s2_knife_begin_clears_leftover_hover(cube_win):
    from pyglet.window import key as _key
    win, app = cube_win
    fid = next(iter(app.scene.mesh.all_face_ids()))
    _seed_hover(win, app, SelectionMode.FACE, fid)
    assert win._vlist_hover is not None
    app.scene.selection.clear()  # empty selection -> contextual C resolves to KNIFE

    win.on_key_press(_key.C, 0)

    assert win._knife_tool is not None
    assert app.scene.selection.hovered is None
    assert win._hover_key is None
    assert win._vlist_hover is None


# ---------------------------------------------------------------------------
# S10 — (mode, id) comparison: numeric-id collision across kinds
# ---------------------------------------------------------------------------

def test_s10_hover_key_id_collision_across_kinds_still_updates(cube_win, monkeypatch):
    """Leave a stale Vertex-mode hover of id N in place (bypassing
    _clear_hover — this isolates the comparison itself from the mode-switch
    reset tested by S1/S2), switch to Edge mode, and have picking report the
    SAME numeric id N as an edge. A bare `hit != sel.hovered` compare would
    see N == N and wrongly treat this as "no change"; the (mode, id) key
    must still see (EDGE, N) != (VERTEX, N) and update.
    """
    import playground.window as window_mod

    win, app = cube_win
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    _seed_hover(win, app, SelectionMode.VERTEX, vid)
    stale_vlist = win._vlist_hover

    # Switch mode WITHOUT going through the key handler (no _clear_hover call) —
    # deliberately isolates the id-collision comparison from the reset path.
    app.scene.selection.mode = SelectionMode.EDGE
    same_numeric_id = vid  # an edge id that happens to collide numerically

    monkeypatch.setattr(
        window_mod, "pick_component",
        lambda camera, mesh, sel, sx, sy, w, h: same_numeric_id,
    )

    win.on_mouse_motion(0, 0, 0, 0)

    assert app.scene.selection.hovered == same_numeric_id
    assert win._hover_key == (SelectionMode.EDGE, same_numeric_id)
    assert win._vlist_hover is not stale_vlist
    from playground.vbo_builder import build_selection_edge_data
    expected = build_selection_edge_data(app.scene.mesh, {same_numeric_id})
    assert win._vlist_hover.count == len(expected) // 3
