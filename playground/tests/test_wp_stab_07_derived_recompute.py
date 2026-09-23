"""WP-STAB-07: `derived` (adjacency/normal cache) must never be stale after a
topology-mutating key handler.

Uses a real, GL-backed `PlaygroundWindow` (same pattern as
`test_wp_stab_01_selection_overlay_lifecycle.py` /
`test_wp_stab_02_hover_reset.py`), driven through the actual key dispatch
(`on_key_press`) plus the window's own Tweak/Gizmo-drag helpers — this is the
"headless equivalent" of a live manual check (same production code path, just
driven from pytest instead of a mouse/keyboard); a live GUI check was not
possible in this environment.

Root cause (pre-fix): `_recompute_derived()` (-> `derived.full_recompute`)
was only called from the non-single-vertex branch of `_sync_after_transform()`
and from Undo/Redo. Loop Insert / Split / Collapse / Connect Edges / Vertex
Connect / Loop Slide only called `_rebuild_vbo()`, which rebuilds the static
mesh VBOs but not `derived`. The next single-vertex incremental update
(`_patch_vbo_single_vertex` -> `derived.affected_neighborhood(mesh, {vid})`)
then indexed `derived`'s stale internal structures against a `FaceId` that no
longer existed in `mesh` and raised `KeyError` — before any VBO update, so
stale geometry was shown right up to the crash.

    T1  Loop Insert on a cube edge -> Vertex mode -> Tweak-drag (temp-target,
        no pre-selection) a vertex adjacent to the new topology -> no
        KeyError; patched VBO position matches `mesh.vertex_position()`.
        (This is the exact reported repro: Loop Insert deletes/recreates the
        faces around the edge, so the pre-mutation `vertex_to_faces` entry
        for the surviving endpoint points at deleted FaceIds.)
    T2  Split -> the new vertex's `derived.vertex_normals`/`vertex_to_faces`
        entry must exist (not silently stale/missing) -> a subsequent
        temp-target Tweak-drag on it must not raise.
    T3  Collapse -> the surviving vertex's `derived.vertex_normals` value
        must match a from-scratch recompute of the post-collapse mesh (not
        the stale pre-collapse value) -> a subsequent temp-target Tweak-drag
        on it must not raise.
        (T2/T3 do not reproduce a *KeyError* the way T1 does: `split_edge`/
        `collapse_edge` keep the touched faces' FaceIds for this mesh shape,
        so `affected_neighborhood()` never indexes a deleted id here — the
        bug they characterize is `derived` silently going out of sync with
        `mesh`, the same underlying defect WP-STAB-07 fixes, verified
        directly on `derived` instead of relying on it also crashing.)
    T4  Gizmo-drag / Extrude call site: Loop Insert -> Vertex mode, single
        vertex pre-selected -> gizmo-handle drag (patched hit, same pattern
        as `test_gizmo.py`) also goes through `_sync_after_transform()` and
        must not raise either. NOTE: by inspection, the Gizmo/Q-W-E/Extrude
        call sites never actually reach `_patch_vbo_single_vertex()` — that
        branch is gated on `self._tweak_started`, which only the Tweak
        gesture (`_tweak_begin`) sets; Gizmo/Transform drags always take the
        `_recompute_derived()` + `_rebuild_vbo()` branch already. So T4 is a
        regression-safety test (passes both pre- and post-fix, i.e. this
        call site was not actually susceptible to the reported crash), kept
        per WP scope to cover that call site explicitly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.selection import SelectionMode  # noqa: E402
from pyglet.window import key as _key  # noqa: E402
from pyglet.window import mouse as _mouse  # noqa: E402
from playground.transformer import update_transform  # noqa: E402
from viewport.derived import DerivedGeometry  # noqa: E402


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


def _first_edge(app):
    return next(iter(app.scene.mesh.all_edge_ids()))


def _vlist_position(vlist, mesh, vid):
    """Read back the flat_slot for `vid` in a per-vertex-id VBO (as built by
    `_patch_vbo_single_vertex`'s Vertex-VBO branch: enumerate(all_vertex_ids())
    order) and return the 3 floats stored there.
    """
    for slot, v in enumerate(mesh.all_vertex_ids()):
        if v == vid:
            return tuple(vlist.position[slot * 3: slot * 3 + 3])
    raise AssertionError(f"vertex {vid} not found in mesh")


# ---------------------------------------------------------------------------
# T1 — Loop Insert -> temp-target Tweak-drag near the new topology
# ---------------------------------------------------------------------------

def test_t1_loop_insert_then_tweak_drag_no_keyerror(cube_win):
    win, app = cube_win
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    sel.clear()
    edge_id = _first_edge(app)
    # The ORIGINAL edge's endpoint — it survives Loop Insert (unlike the new
    # mid-loop vertices) but its incident faces are replaced, so `derived`'s
    # pre-mutation vertex_to_faces entry for it points at deleted FaceIds.
    # affected_neighborhood() must not be handed that stale entry.
    va, _vb0 = app.scene.mesh.edge_vertices(edge_id)
    sel.add({edge_id})

    win.on_key_press(_key.I, 0)  # Loop Insert
    assert sel.mode is SelectionMode.EDGE
    assert set(sel.edges)
    assert va in set(app.scene.mesh.all_vertex_ids())

    sel.mode = SelectionMode.VERTEX
    sel.clear()
    sel.add({va})

    ok = win._tweak_begin("move", 640, 400)
    assert ok and win._tweak_started

    mesh = app.scene.mesh
    update_transform(win._tweak_tool, 25.0, 10.0, win.width, win.height)
    win._sync_after_transform()  # must NOT raise KeyError (pre-fix: did)

    expected = mesh.vertex_position(va)
    assert win._vlist_verts is not None
    got = _vlist_position(win._vlist_verts, mesh, va)
    assert got == pytest.approx(expected, abs=1e-5)

    win._tweak_commit()


# ---------------------------------------------------------------------------
# T2 — Split -> new vertex's derived normal must not be stale/missing,
#      then a temp-target Tweak-drag on it must not raise.
#
# NOTE: unlike Loop Insert, `Mesh.split_edge` keeps the touched faces' IDs
# (it only grows their boundary) — so `affected_neighborhood()` cannot hit a
# deleted FaceId here and this particular drag never raised KeyError even
# pre-fix. What IS stale pre-fix is `derived.vertex_normals`/`vertex_to_faces`
# for the brand-new vertex: it didn't exist at the last full_recompute, so
# `vertex_to_faces.get(new_vid, ())` silently returns nothing and the new
# vertex's normal is never populated at all (falls back to the (0,1,0)
# hard-coded default in `build_face_data`/`build_vertex_data` forever, not
# just for one frame) until *something* forces a full_recompute. That is the
# same class of bug WP-STAB-07 fixes (derived not reflecting current
# topology) — this test characterizes it directly instead of relying on it
# also happening to crash.
# ---------------------------------------------------------------------------

def test_t2_split_new_vertex_derived_not_stale(cube_win):
    win, app = cube_win
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    sel.clear()
    edge_id = _first_edge(app)
    sel.add({edge_id})

    win.on_key_press(_key.S, 0)  # S: Split Edge (sel is cleared afterwards)
    mesh = app.scene.mesh
    derived = app.viewport.render_mesh.derived
    new_vid = max(mesh.all_vertex_ids())  # the vertex split_edge() just created

    # Pre-fix: derived was never recomputed after the mutation, so the new
    # vertex has no entry at all. Post-fix: _recompute_derived() ran as part
    # of the S handler, so it does.
    assert new_vid in derived.vertex_normals
    assert new_vid in derived.vertex_to_faces

    # Same shape as T1: temp-target Tweak-drag the mutation's vertex.
    sel.mode = SelectionMode.VERTEX
    sel.clear()
    sel.add({new_vid})

    ok = win._tweak_begin("move", 640, 400)
    assert ok and win._tweak_started

    update_transform(win._tweak_tool, -15.0, 20.0, win.width, win.height)
    win._sync_after_transform()  # must NOT raise

    expected = mesh.vertex_position(new_vid)
    got = _vlist_position(win._vlist_verts, mesh, new_vid)
    assert got == pytest.approx(expected, abs=1e-5)

    win._tweak_commit()


# ---------------------------------------------------------------------------
# T3 — Collapse -> the surviving vertex's derived normal must reflect the
#      post-merge geometry, then a temp-target Tweak-drag on it must not raise.
#
# NOTE: like Split, `Mesh.collapse_edge` keeps the touched faces' IDs for a
# simple quad-mesh collapse (no face degenerates below 3 unique vertices), so
# this drag does not raise KeyError pre-fix either. What IS stale pre-fix is
# the VALUE of `derived.vertex_normals[survivor]`: the merge moves `survivor`
# to the collapsed edge's midpoint and reshapes its incident faces, but
# without a recompute the cached normal is still the pre-collapse one.
# ---------------------------------------------------------------------------

def test_t3_collapse_survivor_derived_not_stale(cube_win):
    win, app = cube_win
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    sel.clear()
    edge_id = _first_edge(app)
    va_before, vb_before = app.scene.mesh.edge_vertices(edge_id)
    sel.add({edge_id})

    win.on_key_press(_key.C, _key.MOD_SHIFT)  # Shift+C: Collapse Edge

    mesh = app.scene.mesh
    derived = app.viewport.render_mesh.derived
    remaining_ids = set(mesh.all_vertex_ids())
    survivor = va_before if va_before in remaining_ids else vb_before
    assert survivor in remaining_ids

    # Reference: a from-scratch recompute against the post-collapse mesh —
    # what `derived.vertex_normals[survivor]` must match after the fix.
    fresh = DerivedGeometry(mesh)
    assert derived.vertex_normals[survivor] == pytest.approx(
        fresh.vertex_normals[survivor], abs=1e-6
    )

    sel.mode = SelectionMode.VERTEX
    sel.clear()
    sel.add({survivor})

    ok = win._tweak_begin("move", 640, 400)
    assert ok and win._tweak_started

    update_transform(win._tweak_tool, 12.0, -8.0, win.width, win.height)
    win._sync_after_transform()  # must NOT raise

    expected = mesh.vertex_position(survivor)
    got = _vlist_position(win._vlist_verts, mesh, survivor)
    assert got == pytest.approx(expected, abs=1e-5)

    win._tweak_commit()


# ---------------------------------------------------------------------------
# T4 — Gizmo-drag / Extrude call site: same _sync_after_transform() path
# ---------------------------------------------------------------------------

def test_t4_loop_insert_then_gizmo_drag_no_keyerror(cube_win):
    win, app = cube_win
    sel = app.scene.selection
    sel.mode = SelectionMode.EDGE
    sel.clear()
    edge_id = _first_edge(app)
    # Original endpoint — see T1 docstring for why this (not the new
    # mid-loop vertex) is what exercises the stale-derived-cache bug.
    va, _vb0 = app.scene.mesh.edge_vertices(edge_id)
    sel.add({edge_id})

    win.on_key_press(_key.I, 0)  # Loop Insert
    assert va in set(app.scene.mesh.all_vertex_ids())

    sel.mode = SelectionMode.VERTEX
    sel.clear()
    sel.add({va})

    with patch("playground.window.pick_gizmo_handle", return_value="x"):
        win.on_mouse_press(640, 400, _mouse.LEFT, 0)
    assert win._gizmo_drag_armed is True

    win.on_mouse_drag(680, 400, 40, 0, _mouse.LEFT, 0)  # must NOT raise KeyError
    assert win._gizmo_drag_started is True

    win.on_mouse_release(680, 400, _mouse.LEFT, 0)

    mesh = app.scene.mesh
    expected = mesh.vertex_position(va)
    got = _vlist_position(win._vlist_verts, mesh, va)
    assert got == pytest.approx(expected, abs=1e-5)
