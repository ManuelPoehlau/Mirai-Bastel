"""AD-017: Knife session state machine — headless tests (no GL, no window).

Covers §1.7 and §4 of WP-AP-CUT_PLAN.md.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"),
           str(_REPO_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import Scene  # noqa: E402
from core.operations.topology import MeshStateCommand  # noqa: E402
from core.selection import Selection, SelectionMode  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.topology_tools.knife import KnifeTool  # noqa: E402


def _topo_snapshot(mesh):
    """Capture topology as (vertex_ids, edge_endpoints_frozenset, face_boundaries).
    Ignores allocator counters — used for restoration comparisons."""
    verts = frozenset(mesh.all_vertex_ids())
    edges = frozenset(frozenset(mesh.edge_vertices(e)) for e in mesh.all_edge_ids())
    faces = frozenset(tuple(mesh.face_vertices(f)) for f in mesh.all_face_ids())
    positions = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    return (verts, edges, faces, positions)


def _hist_depth(app):
    """Number of undo operations available in the global history."""
    return len(app.scene.history._undo_stack)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _two_quad_app():
    """Two quads sharing edge v1-v2.

    Layout:
      v0(0,1) - v1(1,1) - v4(2,1)
      |   f1    |   f2    |
      v3(0,0) - v2(1,0) - v5(2,0)
    """
    app = PlaygroundApp()
    mesh = app.scene.mesh
    v0 = mesh.add_vertex((0.0, 1.0, 0.0))
    v1 = mesh.add_vertex((1.0, 1.0, 0.0))
    v2 = mesh.add_vertex((1.0, 0.0, 0.0))
    v3 = mesh.add_vertex((0.0, 0.0, 0.0))
    v4 = mesh.add_vertex((2.0, 1.0, 0.0))
    v5 = mesh.add_vertex((2.0, 0.0, 0.0))
    f1 = mesh.add_face([v0, v1, v2, v3])
    f2 = mesh.add_face([v1, v4, v5, v2])
    return app, (v0, v1, v2, v3, v4, v5), (f1, f2)


def _three_quad_app():
    """Three quads in a row sharing edges v1-v2 and v4-v5.

    v0 - v1 - v4 - v6
    | f1  | f2  | f3  |
    v3 - v2 - v5 - v7
    """
    app = PlaygroundApp()
    mesh = app.scene.mesh
    v0 = mesh.add_vertex((0.0, 1.0, 0.0))
    v1 = mesh.add_vertex((1.0, 1.0, 0.0))
    v2 = mesh.add_vertex((1.0, 0.0, 0.0))
    v3 = mesh.add_vertex((0.0, 0.0, 0.0))
    v4 = mesh.add_vertex((2.0, 1.0, 0.0))
    v5 = mesh.add_vertex((2.0, 0.0, 0.0))
    v6 = mesh.add_vertex((3.0, 1.0, 0.0))
    v7 = mesh.add_vertex((3.0, 0.0, 0.0))
    f1 = mesh.add_face([v0, v1, v2, v3])
    f2 = mesh.add_face([v1, v4, v5, v2])
    f3 = mesh.add_face([v4, v6, v7, v5])
    return app, (v0, v1, v2, v3, v4, v5, v6, v7), (f1, f2, f3)


def _begin_knife(app):
    """Create, activate, and begin a KnifeTool."""
    mesh = app.scene.mesh
    sel = app.scene.selection
    tool = KnifeTool()
    tool.activate()
    tool.begin(mesh=mesh, scene=app.scene, selection=sel)
    return tool


# ---------------------------------------------------------------------------
# 1. First click on vertex sets start, no mesh mutation
# ---------------------------------------------------------------------------

def test_first_click_vertex_sets_start():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    before = mesh.export_state()
    knife = _begin_knife(app)
    accepted = knife.click({"kind": "vertex", "vertex_id": v0})
    assert accepted
    assert mesh.export_state() == before  # no mutation
    assert knife._start == v0


# ---------------------------------------------------------------------------
# 2. First click on edge splits at t, sets start
# ---------------------------------------------------------------------------

def test_first_click_edge_splits():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    eid = mesh._get_or_create_edge(v0, v1)
    knife = _begin_knife(app)
    before_vert_count = len(list(mesh.all_vertex_ids()))
    accepted = knife.click({"kind": "edge", "edge_id": eid, "t": 0.3})
    assert accepted
    assert len(list(mesh.all_vertex_ids())) == before_vert_count + 1
    assert knife._start is not None
    assert_mesh_invariants(mesh, context="knife first click edge")


# ---------------------------------------------------------------------------
# 3. vertex → vertex creates connecting edge
# ---------------------------------------------------------------------------

def test_vertex_to_vertex_connection():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    knife = _begin_knife(app)
    # Start at v0
    knife.click({"kind": "vertex", "vertex_id": v0})
    # Connect to v2 (non-adjacent diagonal of f1)
    accepted = knife.click({"kind": "vertex", "vertex_id": v2})
    assert accepted
    assert len(knife._path_edges) == 1
    assert mesh.is_valid_edge(knife._path_edges[0])
    assert_mesh_invariants(mesh, context="knife vertex-vertex")


# ---------------------------------------------------------------------------
# 4. vertex → edge@t creates split + connection
# ---------------------------------------------------------------------------

def test_vertex_to_edge():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v3})
    # Edge v1-v2 is shared between f1 and f2, and f1 contains v3
    shared_edge = mesh._get_or_create_edge(v1, v2)
    accepted = knife.click({"kind": "edge", "edge_id": shared_edge, "t": 0.5})
    assert accepted
    assert len(knife._path_edges) == 1
    assert_mesh_invariants(mesh, context="knife vertex-edge")


# ---------------------------------------------------------------------------
# 5. Chain over 3 faces with arbitrary t
# ---------------------------------------------------------------------------

def test_chain_over_three_faces():
    app, (v0, v1, v2, v3, v4, v5, v6, v7), (f1, f2, f3) = _three_quad_app()
    mesh = app.scene.mesh
    knife = _begin_knife(app)
    # Start at v3 (corner of f1)
    knife.click({"kind": "vertex", "vertex_id": v3})
    # Step to shared edge v1-v2 (between f1 and f2) at t=0.5 → connects v3 to new midpoint
    shared_12 = mesh._get_or_create_edge(v1, v2)
    assert knife.click({"kind": "edge", "edge_id": shared_12, "t": 0.5})
    assert len(knife._path_edges) == 1
    # From the midpoint, step to shared edge v4-v5 (between f2 and f3) at t=0.5
    shared_45 = mesh._get_or_create_edge(v4, v5)
    assert knife.click({"kind": "edge", "edge_id": shared_45, "t": 0.5})
    assert len(knife._path_edges) == 2
    assert_mesh_invariants(mesh, context="knife chain three faces")


# ---------------------------------------------------------------------------
# 6. Invalid targets are no-ops
# ---------------------------------------------------------------------------

def test_edge_incident_to_start_rejected():
    """An edge incident to the current start vertex is invalid."""
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    # Edge v0-v1 is incident to start v0 → rejected
    incident_edge = mesh._get_or_create_edge(v0, v1)
    accepted = knife.click({"kind": "edge", "edge_id": incident_edge, "t": 0.5})
    assert not accepted
    assert len(knife._path_edges) == 0


def test_no_shared_face_rejected():
    """Vertex with no shared face with the start is rejected."""
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    knife = _begin_knife(app)
    # Start at v3; v4 and v5 are on f2 only, not sharing a face with v3 (f1 only)
    knife.click({"kind": "vertex", "vertex_id": v3})
    # v5 is in f2 only; v3 is in f1 only → no shared face
    accepted = knife.click({"kind": "vertex", "vertex_id": v5})
    assert not accepted
    assert len(knife._path_edges) == 0


def test_face_target_rejected():
    app, _, _ = _two_quad_app()
    mesh = app.scene.mesh
    knife = _begin_knife(app)
    # Face target is not valid for knife
    accepted = knife.click({"kind": "face", "face_id": next(iter(mesh.all_face_ids()))})
    assert not accepted


def test_outside_target_rejected():
    app, _, _ = _two_quad_app()
    knife = _begin_knife(app)
    accepted = knife.click({"kind": "outside"})
    assert not accepted


# ---------------------------------------------------------------------------
# 7. undo_step sequence: A→B→C→D, undo, undo
# ---------------------------------------------------------------------------

def test_undo_step_sequence():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    knife = _begin_knife(app)
    # Step A: set start at v0 (push step before setting start)
    knife.click({"kind": "vertex", "vertex_id": v0})
    topo_A = _topo_snapshot(mesh)   # no mutation at step A
    start_A = knife._start
    path_A = list(knife._path_edges)

    # Step B: connect to v2 (diagonal of f1) — mutations the mesh
    knife.click({"kind": "vertex", "vertex_id": v2})
    assert len(knife._path_edges) == 1
    topo_B = _topo_snapshot(mesh)
    assert topo_B != topo_A  # mesh changed

    # Undo step B — restores state from just before step B
    undone = knife.undo_step()
    assert undone
    assert _topo_snapshot(mesh) == topo_A  # topology back to step A state
    assert knife._start == start_A
    assert knife._path_edges == path_A

    # Undo step A — restores to before step A
    if knife._step_stack:
        knife.undo_step()
    assert knife._start is None  # start reset to None
    assert knife._path_edges == []


def test_empty_stack_undo_no_op():
    app, _, _ = _two_quad_app()
    knife = _begin_knife(app)
    result = knife.undo_step()
    assert not result  # empty stack → False


# ---------------------------------------------------------------------------
# 8. cancel restores session_before exactly
# ---------------------------------------------------------------------------

def test_cancel_restores_pre_session_state():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    topo_before = _topo_snapshot(mesh)
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    assert _topo_snapshot(mesh) != topo_before  # mesh changed during session
    knife.cancel()
    # Topology restored (allocator counter may be higher — that's by design)
    assert _topo_snapshot(mesh) == topo_before
    assert_mesh_invariants(mesh, context="knife cancel")


def test_cancel_pushes_nothing_to_history():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    before_hist = _hist_depth(app)
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    knife.cancel()
    assert _hist_depth(app) == before_hist


# ---------------------------------------------------------------------------
# 9. commit → one history entry
# ---------------------------------------------------------------------------

def test_commit_pushes_one_history_entry():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    before_hist = _hist_depth(app)
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    cmd = knife.commit()
    knife.deactivate()
    assert cmd is not None
    assert _hist_depth(app) == before_hist + 1


def test_commit_without_changes_pushes_no_history():
    app, _, _ = _two_quad_app()
    before_hist = _hist_depth(app)
    knife = _begin_knife(app)
    # No clicks — no mesh mutation
    cmd = knife.commit()
    knife.deactivate()
    assert cmd is None
    assert _hist_depth(app) == before_hist


# ---------------------------------------------------------------------------
# 10. global undo after commit removes the whole session
# ---------------------------------------------------------------------------

def test_global_undo_after_commit_removes_whole_session():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    topo_before = _topo_snapshot(mesh)
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    knife.commit()
    knife.deactivate()
    # Mesh changed from session
    assert _topo_snapshot(mesh) != topo_before
    # Global undo removes the whole session
    app.undo()
    assert _topo_snapshot(mesh) == topo_before
    assert_mesh_invariants(mesh, context="knife global undo")


# ---------------------------------------------------------------------------
# 11. commit residue: Edge mode, selection == path_edges
# ---------------------------------------------------------------------------

def test_commit_residue():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    sel = app.scene.selection
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    path_edges = list(knife._path_edges)
    knife.commit()
    knife.deactivate()
    # Residue: Edge mode, path_edges selected
    assert sel.mode is SelectionMode.EDGE
    assert sel.edges == set(path_edges)
    # All selected edges must be valid
    assert all(mesh.is_valid_edge(e) for e in sel.edges)


# ---------------------------------------------------------------------------
# 12. in-session redo (contract extension, DECIDED 2026-09-22)
# ---------------------------------------------------------------------------

def test_redo_restores_full_session_state():
    """A->B->C / Undo -> A->B / Redo -> A->B->C (mesh, start, path_edges)."""
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    knife = _begin_knife(app)
    # A: start at v0 (no mutation); B: connect v2 (diagonal f1); C: connect v4 (diagonal f2)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    knife.click({"kind": "vertex", "vertex_id": v4})
    topo_ABC = _topo_snapshot(mesh)
    start_ABC, path_ABC = knife._start, list(knife._path_edges)
    assert len(path_ABC) == 2

    assert knife.undo_step()
    assert _topo_snapshot(mesh) != topo_ABC
    assert knife._start == v2 and len(knife._path_edges) == 1

    assert knife.redo_step()
    assert _topo_snapshot(mesh) == topo_ABC
    assert knife._start == start_ABC
    assert knife._path_edges == path_ABC
    assert_mesh_invariants(mesh, context="knife redo")


def test_redo_empty_branch_no_op():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    before = _topo_snapshot(mesh)
    knife = _begin_knife(app)
    assert not knife.redo_step()          # nothing undone yet
    knife.click({"kind": "vertex", "vertex_id": v0})
    assert not knife.redo_step()          # still nothing undone
    assert _topo_snapshot(mesh) == before
    assert knife._start == v0


def test_undo_redo_round_trips_are_state_identical():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    knife.click({"kind": "vertex", "vertex_id": v4})
    topo_ABC = _topo_snapshot(mesh)
    start_ABC, path_ABC = knife._start, list(knife._path_edges)

    for _ in range(2):                     # undo/redo x2 stays exact
        assert knife.undo_step()
        assert knife.redo_step()
        assert _topo_snapshot(mesh) == topo_ABC
        assert knife._start == start_ABC
        assert knife._path_edges == path_ABC
    assert len(knife._step_stack) == 3 and len(knife._redo_stack) == 0


def test_accepted_click_after_undo_clears_redo_branch():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})      # B accepted
    assert knife.undo_step()                              # back to start=v0
    assert len(knife._redo_stack) == 1
    # New accepted cut replaces the undone one -> redo branch is gone
    # (v2 is the f1 diagonal of start v0 — a valid new cut after the undo)
    assert knife.click({"kind": "vertex", "vertex_id": v2})
    assert knife._redo_stack == []
    assert not knife.redo_step()


def test_rejected_click_keeps_redo_branch():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    assert knife.undo_step()
    assert len(knife._redo_stack) == 1
    # v5 shares no face with start v0 -> rejected, must NOT clear the redo branch
    assert not knife.click({"kind": "vertex", "vertex_id": v5})
    assert len(knife._redo_stack) == 1
    assert knife.redo_step()


def test_cancel_with_redo_entries_restores_session_before():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    topo_before = _topo_snapshot(mesh)
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    assert knife.undo_step()
    assert len(knife._redo_stack) == 1
    knife.cancel()
    assert _topo_snapshot(mesh) == topo_before
    assert knife._start is None and knife._path_edges == []
    assert knife._step_stack == [] and knife._redo_stack == []


def test_commit_after_redo_pushes_one_history_entry():
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    topo_before = _topo_snapshot(mesh)
    before_hist = _hist_depth(app)
    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    knife.click({"kind": "vertex", "vertex_id": v4})
    assert knife.undo_step()
    assert knife.redo_step()
    cmd = knife.commit()
    knife.deactivate()
    assert cmd is not None
    assert _hist_depth(app) == before_hist + 1
    # Global undo removes the whole (redone) session
    app.undo()
    assert _topo_snapshot(mesh) == topo_before


# ---------------------------------------------------------------------------
# 13. history isolation: in-session undo/redo never touch global history
# ---------------------------------------------------------------------------

def _depths(app):
    """(global undo depth, global redo depth)."""
    h = app.scene.history
    return (len(h._undo_stack), len(h._redo_stack))


def _push_history_split_then_undo(app, edge_id):
    """Create a real global history entry (edge split) and immediately undo it,
    leaving a non-empty global redo branch — the diagnosed corruption setup."""
    mesh = app.scene.mesh
    before = mesh.export_state()
    mesh.split_edge(edge_id, 0.5)
    app.scene.history.push(MeshStateCommand(
        mesh=mesh,
        before_state=before,
        after_state=mesh.export_state(),
        description="pre-session",
    ))
    app.undo()  # mesh back to the pre-split state; redo branch = 1


def test_session_undo_redo_never_touch_global_history():
    """Central invariant: while a session is active, undo/redo operate
    exclusively on the session's own step history."""
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    topo_initial = _topo_snapshot(mesh)
    eid = mesh._get_or_create_edge(v1, v2)  # existing shared edge — no mutation
    _push_history_split_then_undo(app, eid)
    assert _topo_snapshot(mesh) == topo_initial
    depths = _depths(app)
    assert depths == (0, 1)               # one global undo entry, one pending redo

    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    knife.click({"kind": "vertex", "vertex_id": v4})
    topo_ABC = _topo_snapshot(mesh)
    assert topo_ABC != topo_initial

    # Full in-session undo/redo cycles — global stacks must never change.
    for _ in range(2):
        while knife.undo_step():
            assert _depths(app) == depths
        while knife.redo_step():
            assert _depths(app) == depths
    assert _topo_snapshot(mesh) == topo_ABC
    assert _depths(app) == depths

    # The pre-session global redo entry was not consumed: after cancelling the
    # session it is still pending and still functional.
    knife.cancel()
    assert _topo_snapshot(mesh) == topo_initial
    assert _depths(app) == depths
    app.redo()
    assert _depths(app) == (1, 0)
    assert _topo_snapshot(mesh) != topo_initial


def test_global_redo_state_not_replayed_mid_session():
    """The diagnosed corruption must be impossible: the global pre-session
    state is never re-applied over in-session cuts."""
    app, (v0, v1, v2, v3, v4, v5), _ = _two_quad_app()
    mesh = app.scene.mesh
    topo_initial = _topo_snapshot(mesh)
    eid = mesh._get_or_create_edge(v1, v2)  # existing shared edge — no mutation
    _push_history_split_then_undo(app, eid)
    assert _topo_snapshot(mesh) == topo_initial

    knife = _begin_knife(app)
    knife.click({"kind": "vertex", "vertex_id": v0})
    knife.click({"kind": "vertex", "vertex_id": v2})
    topo_session = _topo_snapshot(mesh)
    assert topo_session != topo_initial
    assert len(knife._step_stack) == 2

    # In-session redo restores session state, never the pre-session entry.
    assert knife.undo_step()
    assert knife.redo_step()
    assert _topo_snapshot(mesh) == topo_session
    assert _topo_snapshot(mesh) != topo_initial
    assert len(knife._step_stack) == 2
    assert _depths(app) == (0, 1)

    # Cancel restores exactly the pre-session state; the global entry survives.
    knife.cancel()
    assert _topo_snapshot(mesh) == topo_initial
    assert _depths(app) == (0, 1)
    app.redo()
    assert _depths(app) == (1, 0)
    assert _topo_snapshot(mesh) != topo_initial

