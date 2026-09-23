"""WP-STAB-01 (R-SEL-1): selection overlay lifecycle across mesh rebuilds.

Uses a real, GL-backed `PlaygroundWindow` (same pattern as
`test_ad017_knife_keys.py`) and drives it through the actual key dispatch
(`on_key_press`/`on_key_release`) that the UI itself uses — this is the
"headless equivalent" of a live manual check: same production code path,
just driven from pytest instead of a mouse/keyboard.

Before the fix, `_rebuild_vbo()` deleted/cleared only `_vlist_selection`
(the face overlay) and left `_vlist_sel_verts`/`_vlist_sel_edges` (vertex-
and edge-mode overlays) untouched — so after a topology-changing rebuild
those two could keep pointing at stale, pre-rebuild geometry even though
the current Selection no longer matched them. `_rebuild_vbo()` now always
calls `_rebuild_selection_vbo()` at the end, so all three overlays are
rebuilt from the current Selection on every mesh rebuild.

    S3  Split (Edge -> Vertex mode residue) on the head mesh: the vertex
        overlay is rebuilt to match the new selection; the stale face/edge
        overlays are cleared.
    S4  Face highlight specifically survives a direct `_rebuild_vbo()` call
        (not just the selection-only path via `_rebuild_selection_vbo()`).
    S5  Undo (Ctrl+Z) clears the selection — regression check that ALL
        THREE selection overlays (face/vertex/edge) are cleared, not just
        the face one this was previously guaranteed for.
    S6  Loop Insert (edge selection) and a subsequent Loop Slide gesture
        (G hold, cube mesh — same loop-slide precondition as
        test_topology_loop_slide.py) leave the edge overlay matching the
        current edge selection throughout.
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
from playground.vbo_builder import (  # noqa: E402
    build_selection_data,
    build_selection_edge_data,
    build_selection_vertex_data,
)


def _window(initial_mesh: str = "head"):
    from playground.app import PlaygroundApp
    from playground.window import PlaygroundWindow
    app = PlaygroundApp()
    win = PlaygroundWindow(app, initial_mesh=initial_mesh)
    return win, app


@pytest.fixture
def head_win():
    win, app = _window("head")
    yield win, app
    win.close()


@pytest.fixture
def cube_win():
    win, app = _window("cube")
    yield win, app
    win.close()


def _first_edge(app):
    return next(iter(app.scene.mesh.all_edge_ids()))


# ---------------------------------------------------------------------------
# S3 — Split residue (Vertex mode): overlay matches the new selection
# ---------------------------------------------------------------------------

def test_s3_split_residue_vertex_overlay_matches_selection(head_win):
    """C-key Split on 1 selected edge leaves Vertex-mode overlay = new vertex."""
    from pyglet.window import key as _key
    win, app = head_win
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    sel.clear()
    sel.add({_first_edge(app)})

    win.on_key_press(_key.C, 0)  # contextual C -> SPLIT (1 edge selected)

    assert sel.mode is SelectionMode.VERTEX
    assert len(sel.vertices) == 1

    expected = build_selection_vertex_data(app.scene.mesh, sel.vertices)
    assert win._vlist_sel_verts is not None
    assert win._vlist_sel_verts.count == len(expected) // 3
    # Stale overlays from the pre-split (edge) selection must be gone.
    assert win._vlist_selection is None
    assert win._vlist_sel_edges is None


# ---------------------------------------------------------------------------
# S4 — Face highlight survives a direct _rebuild_vbo() call
# ---------------------------------------------------------------------------

def test_s4_face_highlight_survives_rebuild_vbo(head_win):
    """Selecting faces then calling _rebuild_vbo() directly must rebuild the
    face overlay too, not just the mesh VBOs — this is the core R-SEL-1 fix:
    _rebuild_vbo() now calls _rebuild_selection_vbo() at the end."""
    win, app = head_win
    sel = app.scene.selection
    sel.mode = SelectionMode.FACE
    sel.clear()
    faces = set(list(app.scene.mesh.all_face_ids())[:2])
    sel.add(faces)

    # A rebuild triggered by something other than a selection change (e.g. a
    # scene/topology change) must still leave the face overlay in sync.
    win._rebuild_vbo()

    expected = build_selection_data(app.scene.mesh, sel.faces)
    assert win._vlist_selection is not None
    assert win._vlist_selection.count == len(expected) // 3
    assert win._vlist_sel_verts is None
    assert win._vlist_sel_edges is None


# ---------------------------------------------------------------------------
# S5 — Undo clears ALL selection overlays (regression: stale sel_verts/sel_edges)
# ---------------------------------------------------------------------------

def test_s5_undo_clears_all_selection_overlays(head_win):
    """Ctrl+Z after a Split clears the Selection; before the fix, the
    resulting _rebuild_vbo() call did not clear _vlist_sel_verts/_edges
    (only _vlist_selection was in the deletion list), so a stale
    vertex-overlay VBO from the pre-undo mesh could survive."""
    from pyglet.window import key as _key
    win, app = head_win
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    sel.clear()
    sel.add({_first_edge(app)})

    win.on_key_press(_key.C, 0)  # Split -> Vertex-mode selection + overlay
    assert win._vlist_sel_verts is not None

    win.on_key_press(_key.Z, _key.MOD_CTRL)  # global undo (on_key_press clears selection)

    assert app.scene.selection.is_empty()
    assert win._vlist_selection is None
    assert win._vlist_sel_verts is None
    assert win._vlist_sel_edges is None


# ---------------------------------------------------------------------------
# S6 — Loop Insert + Loop Slide: edge overlay tracks the edge selection
# ---------------------------------------------------------------------------

def test_s6_loop_insert_edge_overlay_matches_selection(cube_win):
    """I-key Loop Insert selects the new loop edges; overlay must match."""
    from pyglet.window import key as _key
    win, app = cube_win
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    sel.clear()
    sel.add({_first_edge(app)})

    win.on_key_press(_key.I, 0)

    assert sel.mode is SelectionMode.EDGE
    assert len(sel.edges) >= 1
    expected = build_selection_edge_data(app.scene.mesh, sel.edges)
    assert win._vlist_sel_edges is not None
    assert win._vlist_sel_edges.count == len(expected) // 3
    assert win._vlist_selection is None
    assert win._vlist_sel_verts is None


def test_s6_loop_slide_preserves_edge_overlay(cube_win):
    """G hold-drag-release (Loop Slide) keeps the edge-selection overlay in
    sync with the (unchanged) edge selection after the commit rebuild."""
    from pyglet.window import key as _key
    win, app = cube_win
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    sel.clear()
    sel.add({_first_edge(app)})
    win.on_key_press(_key.I, 0)  # Loop Insert -> closed loop, valid for Loop Slide
    loop_edges = set(sel.edges)
    assert len(loop_edges) >= 2

    win.on_key_press(_key.G, 0)
    assert win._loop_slide_tool is not None
    win._loop_slide_tool.update(dx=25.0, dy=0.0, width=800, height=600)
    win.on_key_release(_key.G, 0)  # commit -> _rebuild_vbo()

    assert win._loop_slide_tool is None
    assert app.scene.selection.edges == loop_edges
    expected = build_selection_edge_data(app.scene.mesh, loop_edges)
    assert win._vlist_sel_edges is not None
    assert win._vlist_sel_edges.count == len(expected) // 3
    assert win._vlist_selection is None
    assert win._vlist_sel_verts is None
