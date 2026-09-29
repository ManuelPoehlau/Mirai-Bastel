"""Knife Face Cut Lab — headless tests (no GL, no window).

Covers the automatic checks from the handoff (§6): the four shapes (FC1,
FC2, FC3/notch, FC4) plus the closed shape on a 4x4 grid (invariants,
face-size histogram, ID monotonicity), drop-tail behaviour, Esc restore,
history step count, in-session undo of a pending point. Both variants (B —
Immediate, D — Collected) are exercised independently (AD-017 §1.10 decision
#1: no shared "Cut Engine" logic to test once).
"""

from __future__ import annotations

import collections
import math
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"), str(_REPO_ROOT / "examples"),
           str(_REPO_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from core import Mesh, Scene  # noqa: E402
from core.selection import SelectionMode  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402

from playground.experiments.knife_face.engine import (  # noqa: E402
    EDGE_MARGIN_PX,
    KnifeFaceCollected,
    KnifeFaceImmediate,
    close_loop_with_bridges,
    face_interior_hit,
    knife_face_pick,
    loop_matches_winding,
    min_edge_distance_px,
    select_bridge,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _grid(n: int = 4):
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh, p


def _scene_with_grid(n: int = 4):
    scene = Scene()
    scene.mesh, p = _grid(n)
    return scene, p


def _edge(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _sizes(mesh):
    return dict(sorted(collections.Counter(len(mesh.face_vertices(f)) for f in mesh.all_face_ids()).items()))


def _face_with(mesh, *vs):
    return next(f for f in sorted(mesh.all_face_ids(), key=int)
                if all(v in mesh.face_vertices(f) for v in vs))


def _begin(cls, scene):
    engine = cls()
    engine.activate()
    engine.begin(mesh=scene.mesh, scene=scene, selection=scene.selection)
    return engine


def _face_target(fid, position, distance_px=20.0):
    return {"kind": "face", "face_id": fid, "position": position, "distance_px": distance_px}


def _vertex_target(vid):
    return {"kind": "vertex", "vertex_id": vid}


def _edge_target(eid, t):
    return {"kind": "edge", "edge_id": eid, "t": t}


def _hist_depth(scene):
    return len(scene.history._undo_stack)


# ---------------------------------------------------------------------------
# FC1 — edge -> 1 interior point -> edge (both variants)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", [KnifeFaceImmediate, KnifeFaceCollected])
def test_fc1_edge_interior_edge(cls):
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])
    e2 = _edge(mesh, p[(1, 2)], p[(2, 2)])
    knife = _begin(cls, scene)

    assert knife.click(_edge_target(e1, 0.5))
    assert knife.click(_face_target(fid, (1.5, 1.3, 0.0)))
    assert knife.click(_edge_target(e2, 0.5))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert_mesh_invariants(mesh, context=f"{cls.__name__} FC1")
    assert len(scene.history) == 1


# ---------------------------------------------------------------------------
# FC2 — edge -> 2 interior points -> edge
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", [KnifeFaceImmediate, KnifeFaceCollected])
def test_fc2_edge_two_interior_edge(cls):
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])
    e2 = _edge(mesh, p[(1, 2)], p[(2, 2)])
    knife = _begin(cls, scene)

    assert knife.click(_edge_target(e1, 0.5))
    assert knife.click(_face_target(fid, (1.3, 1.2, 0.0)))
    assert knife.click(_face_target(fid, (1.7, 1.8, 0.0)))
    assert knife.click(_edge_target(e2, 0.5))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert_mesh_invariants(mesh, context=f"{cls.__name__} FC2")
    assert len(scene.history) == 1


# ---------------------------------------------------------------------------
# FC3 — notch: in and out through the same edge (adjacent ends)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", [KnifeFaceImmediate, KnifeFaceCollected])
def test_fc3_notch_same_edge(cls):
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    edge = _edge(mesh, p[(1, 1)], p[(1, 2)])
    va, vb = mesh.edge_vertices(edge)
    t_a, t_b = (0.3, 0.7) if va == p[(1, 1)] else (0.7, 0.3)
    knife = _begin(cls, scene)

    assert knife.click(_edge_target(edge, t_a))
    assert knife.click(_face_target(fid, (1.5, 1.4, 0.0)))
    if cls is KnifeFaceImmediate:
        # B mutates immediately: the first click already split `edge`, so the
        # second endpoint is a fresh edge/t on the remaining piece — the sub-
        # edge between the new start vertex and p[(1, 2)] (pending points
        # relax the "not incident to start" rule, which is what makes the
        # notch reachable at all).
        eid2 = _edge(mesh, knife.start, p[(1, 2)])
        assert knife.click(_edge_target(eid2, 0.5))
    else:
        # D defers everything: both endpoints reference the *same* original
        # (still-unsplit) edge, at their original t — the engine's
        # `_resolve_shared_edge_pair` handles this at commit time.
        assert knife.click(_edge_target(edge, t_b))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert_mesh_invariants(mesh, context=f"{cls.__name__} FC3")
    sizes = _sizes(mesh)
    assert 3 in sizes  # the notch carves off a triangle
    assert len(scene.history) == 1


# ---------------------------------------------------------------------------
# FC4 — vertex -> interior -> adjacent vertex
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", [KnifeFaceImmediate, KnifeFaceCollected])
def test_fc4_vertex_interior_adjacent_vertex(cls):
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    a, b = p[(1, 1)], p[(1, 2)]
    fid = _face_with(mesh, a, b, p[(2, 2)])
    knife = _begin(cls, scene)

    assert knife.click(_vertex_target(a))
    assert knife.click(_face_target(fid, (1.5, 1.5, 0.0)))
    assert knife.click(_vertex_target(b))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert_mesh_invariants(mesh, context=f"{cls.__name__} FC4")
    sizes = _sizes(mesh)
    assert 3 in sizes
    assert len(scene.history) == 1


# ---------------------------------------------------------------------------
# A5 (Manu, 2026-09-28): a neighbour face right after a completed
# interior-involving cut stays invalid (no line) — cleared only by an
# explicit plain (no-interior) boundary-to-boundary click. Cross-face
# cutting (Blender-like) is a separate, deferred capability (Q5).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", [KnifeFaceImmediate, KnifeFaceCollected])
def test_a5_neighbour_face_locked_right_after_a_cut(cls):
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    f1 = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    f2 = _face_with(mesh, p[(1, 2)], p[(2, 3)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])           # f1's own edge
    e_shared = _edge(mesh, p[(1, 2)], p[(2, 2)])     # shared boundary of f1 and f2

    knife = _begin(cls, scene)
    assert knife.click(_edge_target(e1, 0.5))
    assert knife.click(_face_target(f1, (1.5, 1.3, 0.0)))
    assert knife.click(_edge_target(e_shared, 0.5))  # completes the f1 cut

    # The exit vertex sits on the boundary shared with f2 — but f2 must
    # still be rejected until an explicit plain boundary click intervenes.
    neighbour_click = _face_target(f2, (2.5, 1.5, 0.0))
    assert knife.accepts(neighbour_click) is False
    assert knife.click(neighbour_click) is False
    if hasattr(knife, "path"):  # D: nothing mutates anyway, path unaffected
        assert len(knife.path) == 3
    assert mesh.is_valid_face(f2)

    # A plain (no-interior) boundary hop clears the lock — through one of
    # the split face's *own* remnants (p[(1, 1)] is on the exit vertex's
    # other incident face, not f2), so f2 itself stays untouched by this
    # clearing click. `start`/the path's anchor moves away from f2's
    # boundary with this click (same as any plain Knife click always
    # moves the anchor) — the lock itself is what's under test here, not
    # whether f2 specifically is reachable *from the new anchor*.
    assert knife.click(_vertex_target(p[(1, 1)]))
    assert mesh.is_valid_face(f2)
    assert knife._face_cut_lock is False


# ---------------------------------------------------------------------------
# B: interior start rejected
# ---------------------------------------------------------------------------

def test_b_interior_start_rejected():
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    knife = _begin(KnifeFaceImmediate, scene)
    before = mesh.export_state()

    target = _face_target(fid, (1.5, 1.5, 0.0))
    assert knife.accepts(target) is False
    assert knife.click(target) is False
    assert mesh.export_state() == before


# ---------------------------------------------------------------------------
# D: interior start allowed
# ---------------------------------------------------------------------------

def test_d_interior_start_allowed():
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    knife = _begin(KnifeFaceCollected, scene)

    target = _face_target(fid, (1.5, 1.5, 0.0))
    assert knife.accepts(target) is True
    assert knife.click(target) is True
    assert mesh.export_state() == knife._session_before  # still nothing mutated (D)


# ---------------------------------------------------------------------------
# D: 2 interior clicks + Enter -> mesh unchanged; 3 -> closed shape
# ---------------------------------------------------------------------------

def test_d_two_interior_points_then_commit_is_noop():
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    knife = _begin(KnifeFaceCollected, scene)
    before = mesh.export_state()

    assert knife.click(_face_target(fid, (1.3, 1.3, 0.0)))
    assert knife.click(_face_target(fid, (1.7, 1.3, 0.0)))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is None
    assert mesh.export_state() == before
    assert len(scene.history) == 0
    assert "dropped" in knife.last_message


def test_d_three_interior_points_then_commit_is_closed_shape():
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    knife = _begin(KnifeFaceCollected, scene)
    before_faces = mesh.all_face_ids()

    assert knife.click(_face_target(fid, (1.3, 1.3, 0.0)))
    assert knife.click(_face_target(fid, (1.7, 1.3, 0.0)))
    assert knife.click(_face_target(fid, (1.5, 1.7, 0.0)))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert_mesh_invariants(mesh, context="D closed shape")
    # spec: "3 pieces in a quad" — the original face is replaced by 3 faces.
    assert len(mesh.all_face_ids()) == len(before_faces) + 2
    sizes = _sizes(mesh)
    assert 3 in sizes  # the closed loop itself (a triangle)
    assert len(scene.history) == 1


# ---------------------------------------------------------------------------
# B: pending tail dropped on commit (Enter/click outside)
# ---------------------------------------------------------------------------

def test_b_pending_tail_dropped_history_matches_edge_split_only():
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])
    knife = _begin(KnifeFaceImmediate, scene)

    assert knife.click(_edge_target(e1, 0.5))
    assert knife.click(_face_target(fid, (1.5, 1.3, 0.0)))
    vcount_before_commit = len(list(mesh.all_vertex_ids()))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None  # the first click's split_edge did mutate the mesh
    assert len(list(mesh.all_vertex_ids())) == vcount_before_commit  # pending point dropped, no new vertex
    assert len(scene.history) == 1
    assert_mesh_invariants(mesh, context="B pending tail dropped")


# ---------------------------------------------------------------------------
# Esc restores the pre-session mesh
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", [KnifeFaceImmediate, KnifeFaceCollected])
def test_esc_restores_pre_session_mesh(cls):
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])
    e2 = _edge(mesh, p[(1, 2)], p[(2, 2)])
    before = mesh.export_state()
    knife = _begin(cls, scene)

    knife.click(_edge_target(e1, 0.5))
    knife.click(_face_target(fid, (1.5, 1.3, 0.0)))
    knife.click(_edge_target(e2, 0.5))
    knife.cancel()
    knife.deactivate()

    # AD-001: ID allocator counters legitimately keep advancing (IDs are
    # never reused), so the topology is compared without them — same
    # convention as test_connect_lab.py's `_topology()` / this repo's
    # test_ad017_knife.py `_topo_snapshot()`.
    def _topology(state):
        return {k: v for k, v in state.items() if not k.endswith("_id_counter")}

    assert _topology(mesh.export_state()) == _topology(before)
    assert len(scene.history) == 0


# ---------------------------------------------------------------------------
# Commit = exactly one history step; Undo/Redo after commit round-trips
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", [KnifeFaceImmediate, KnifeFaceCollected])
def test_commit_is_one_history_step_and_roundtrips(cls):
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])
    e2 = _edge(mesh, p[(1, 2)], p[(2, 2)])
    before = {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}
    knife = _begin(cls, scene)

    knife.click(_edge_target(e1, 0.5))
    knife.click(_face_target(fid, (1.5, 1.3, 0.0)))
    knife.click(_edge_target(e2, 0.5))
    knife.commit()
    knife.deactivate()

    after = {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}
    assert len(scene.history) == 1

    scene.history.undo()
    assert {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")} == before

    scene.history.redo()
    assert {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")} == after


# ---------------------------------------------------------------------------
# In-session undo of a pending point
# ---------------------------------------------------------------------------

def test_b_in_session_undo_of_pending_point():
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])
    knife = _begin(KnifeFaceImmediate, scene)

    knife.click(_edge_target(e1, 0.5))
    assert knife.click(_face_target(fid, (1.5, 1.3, 0.0)))
    assert knife.pending_positions == [(1.5, 1.3, 0.0)]

    assert knife.undo_step() is True
    assert knife.pending_positions == []

    knife.cancel()
    knife.deactivate()


def test_d_interior_start_then_single_boundary_point_is_dropped_not_crash():
    """Regression: an interior-started path that touches exactly one
    boundary point before Enter has no second boundary vertex to anchor a
    split on — the leading interior point must be dropped (same class as a
    dangling tail), not raise (found via the window-wiring smoke test:
    `_resolve_path` used to treat the interior point as a boundary anchor
    and crash with KeyError('edge_id'))."""
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])
    before = mesh.export_state()
    knife = _begin(KnifeFaceCollected, scene)

    assert knife.click(_face_target(fid, (1.5, 1.5, 0.0)))
    assert knife.click(_edge_target(e1, 0.5))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is None
    assert mesh.export_state() == before
    assert "leading interior point" in knife.last_message


def test_d_in_session_undo_of_pending_point():
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    knife = _begin(KnifeFaceCollected, scene)

    knife.click(_face_target(fid, (1.5, 1.5, 0.0)))
    assert knife.click(_face_target(fid, (1.6, 1.6, 0.0)))
    assert len(knife.path) == 2

    assert knife.undo_step() is True
    assert len(knife.path) == 1

    knife.cancel()
    knife.deactivate()


# ---------------------------------------------------------------------------
# ID monotonicity (AD-001) after a face-interior cut
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cls", [KnifeFaceImmediate, KnifeFaceCollected])
def test_ids_monotonic_after_cut(cls):
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])
    e2 = _edge(mesh, p[(1, 2)], p[(2, 2)])
    hi_v = max(int(v) for v in mesh.all_vertex_ids())
    hi_e = max(int(e) for e in mesh.all_edge_ids())
    hi_f = max(int(f) for f in mesh.all_face_ids())
    knife = _begin(cls, scene)

    knife.click(_edge_target(e1, 0.5))
    knife.click(_face_target(fid, (1.5, 1.3, 0.0)))
    knife.click(_edge_target(e2, 0.5))
    knife.commit()
    knife.deactivate()

    new_vs = [v for v in mesh.all_vertex_ids() if int(v) > hi_v]
    new_es = [e for e in mesh.all_edge_ids() if int(e) > hi_e]
    new_fs = [f for f in mesh.all_face_ids() if int(f) > hi_f]
    assert new_vs and new_es and new_fs
    assert fid not in mesh.all_face_ids()


# ---------------------------------------------------------------------------
# Face-size histogram on the 4x4 grid (matches discovery §2/probe shape)
# ---------------------------------------------------------------------------

def test_face_size_histogram_fc1_matches_discovery():
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    e1 = _edge(mesh, p[(1, 1)], p[(2, 1)])
    e2 = _edge(mesh, p[(1, 2)], p[(2, 2)])
    knife = _begin(KnifeFaceImmediate, scene)

    knife.click(_edge_target(e1, 0.5))
    knife.click(_face_target(fid, (1.5, 1.3, 0.0)))
    knife.click(_edge_target(e2, 0.5))
    knife.commit()
    knife.deactivate()

    # 16 quads -> 1 removed + 2 added (fid's split) = 17 faces; splitting e1
    # and e2 each also inserts a vertex into the *neighbouring* quad on the
    # other side of that edge, turning 2 more quads into pentagons.
    assert _sizes(mesh) == {4: 13, 5: 4}


# ---------------------------------------------------------------------------
# Face too small on screen — HUD gate (H3, EDGE_MARGIN_PX)
# ---------------------------------------------------------------------------

def test_face_interior_click_rejected_below_edge_margin():
    scene, p = _scene_with_grid()
    mesh = scene.mesh
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])
    knife = _begin(KnifeFaceCollected, scene)

    too_close = _face_target(fid, (1.5, 1.5, 0.0), distance_px=EDGE_MARGIN_PX - 1.0)
    assert knife.accepts(too_close) is False

    far_enough = _face_target(fid, (1.5, 1.5, 0.0), distance_px=EDGE_MARGIN_PX)
    assert knife.accepts(far_enough) is True


# ---------------------------------------------------------------------------
# Picking — face-interior hit position and edge clearance (lab-local, H1/H3)
# ---------------------------------------------------------------------------

def _front_camera():
    """Front-on view (yaw=pitch=0 looks along -Z) — the grid lies in the
    Z=0 plane, varying in X/Y, so this (not a top-down pitch) is what frames
    it face-on, matching how OrbitCamera's `eye()` places the camera relative
    to `world_up=(0,1,0)`."""
    return OrbitCamera(target=(2.0, 2.0, 0.0), distance=6.0, yaw=0.0, pitch=0.0)


def test_knife_face_pick_face_hit_has_position_and_distance():
    mesh, p = _grid()
    camera = _front_camera()
    width = height = 400
    sx, sy = camera.project_to_screen((1.5, 1.5, 0.0), width, height)

    target = knife_face_pick(camera, mesh, sx, sy, width, height)

    assert target["kind"] == "face"
    assert target["distance_px"] is not None and target["distance_px"] > 0.0
    hit = target["position"]
    assert math.isclose(hit[0], 1.5, abs_tol=0.05)
    assert math.isclose(hit[1], 1.5, abs_tol=0.05)


def test_min_edge_distance_px_shrinks_towards_boundary():
    mesh, p = _grid()
    camera = _front_camera()
    width = height = 400
    fid = _face_with(mesh, p[(1, 1)], p[(2, 2)])

    sx_c, sy_c = camera.project_to_screen((1.5, 1.5, 0.0), width, height)
    d_center = min_edge_distance_px(camera, mesh, fid, sx_c, sy_c, width, height)

    sx_e, sy_e = camera.project_to_screen((1.05, 1.5, 0.0), width, height)
    d_near_edge = min_edge_distance_px(camera, mesh, fid, sx_e, sy_e, width, height)

    assert d_near_edge < d_center


# ---------------------------------------------------------------------------
# D — multi-run commit: shared joint points resolved once (KeyError regression)
# ---------------------------------------------------------------------------

def _ngon_scene(n: int):
    scene = Scene()
    mesh = scene.mesh
    vs = [mesh.add_vertex((math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n), 0.0))
          for k in range(n)]
    fid = mesh.add_face(vs)
    return scene, fid


def _state_no_counters(mesh):
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}


def test_d_three_boundary_points_on_three_edges_commit_without_crash():
    """Handoff repro: interior click + 3 boundary clicks on 3 edges of one quad
    used to raise KeyError(EdgeId) in split_edge (joint point split twice)."""
    scene, fid = _ngon_scene(4)
    mesh = scene.mesh
    edges = mesh.face_edges(fid)
    before = _state_no_counters(mesh)
    knife = _begin(KnifeFaceCollected, scene)

    assert knife.click(_face_target(fid, (0.0, 0.0, 0.0)))
    assert knife.click(_edge_target(edges[0], 0.3))
    assert knife.click(_edge_target(edges[1], 0.5))
    assert knife.click(_edge_target(edges[2], 0.5))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert "2/2 cut(s) applied" in knife.last_message
    assert len(mesh.all_face_ids()) == 3
    assert_mesh_invariants(mesh, context="D 3 boundary points")
    assert len(scene.history) == 1
    scene.history.undo()
    assert _state_no_counters(mesh) == before


@pytest.mark.parametrize("n_edges", [4, 5])
def test_d_boundary_chain_on_n_edges_of_a_polygon(n_edges):
    scene, fid = _ngon_scene(6)
    mesh = scene.mesh
    edges = mesh.face_edges(fid)
    knife = _begin(KnifeFaceCollected, scene)

    for e in edges[:n_edges]:
        assert knife.click(_edge_target(e, 0.5))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert f"{n_edges - 1}/{n_edges - 1} cut(s) applied" in knife.last_message
    assert_mesh_invariants(mesh, context=f"D {n_edges}-point chain")
    assert len(mesh.all_face_ids()) == n_edges
    assert len(scene.history) == 1


def test_d_mixed_interior_run_and_plain_runs_share_joints():
    """interior, B1, B2, interior, B3, B4 -> leading interior dropped; runs
    [B1, B2], [B2, i, B3], [B3, B4] with two shared joints. The interior-bearing
    run must keep its interior position while each joint is resolved once.
    (The handoff's literal `i, B, i, B, B` is not clickable: A5 locks out a face
    click right after a boundary that closes a lead-interior run.)"""
    scene, fid = _ngon_scene(6)
    mesh = scene.mesh
    edges = mesh.face_edges(fid)
    knife = _begin(KnifeFaceCollected, scene)

    assert knife.click(_face_target(fid, (0.0, 0.1, 0.0)))
    assert knife.click(_edge_target(edges[0], 0.5))
    assert knife.click(_edge_target(edges[1], 0.5))
    assert knife.click(_face_target(fid, (-0.2, 0.0, 0.0)))
    assert knife.click(_edge_target(edges[3], 0.5))
    assert knife.click(_edge_target(edges[4], 0.5))
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert "3/3 cut(s) applied" in knife.last_message
    assert "leading interior" in knife.last_message
    assert_mesh_invariants(mesh, context="D mixed interior + shared joints")
    assert len(mesh.all_face_ids()) == 4
    assert any(
        math.isclose(mesh.vertex_position(v)[0], -0.2) and math.isclose(mesh.vertex_position(v)[1], 0.0)
        for v in mesh.all_vertex_ids()
    )
    assert len(scene.history) == 1


def test_d_two_runs_on_same_original_edge_do_not_crash():
    """Different runs whose ends land on one original edge: splitting for the
    first must not invalidate the second's edge id."""
    scene, fid = _ngon_scene(6)
    mesh = scene.mesh
    edges = mesh.face_edges(fid)
    knife = _begin(KnifeFaceCollected, scene)

    assert knife.click(_edge_target(edges[0], 0.2))
    assert knife.click(_edge_target(edges[2], 0.5))
    assert knife.click(_edge_target(edges[4], 0.5))
    assert knife.click(_edge_target(edges[0], 0.8))
    knife.commit()
    knife.deactivate()

    assert_mesh_invariants(mesh, context="D shared original edge across runs")


def test_d_run_failure_is_dropped_and_rest_stays_one_undoable_step(monkeypatch):
    """Safety net: an exception from Core inside one run drops only that run
    (HUD N/M), the commit still reaches the History push for the rest."""
    import playground.experiments.knife_face.engine as eng

    scene, fid = _ngon_scene(6)
    mesh = scene.mesh
    edges = mesh.face_edges(fid)
    before = _state_no_counters(mesh)
    knife = _begin(KnifeFaceCollected, scene)
    for e in edges[:3]:
        assert knife.click(_edge_target(e, 0.5))

    real, calls = eng.connect_in_shared_face, []

    def flaky(mesh_, a, b):
        calls.append((a, b))
        if len(calls) == 1:
            raise KeyError("forced")
        return real(mesh_, a, b)

    monkeypatch.setattr(eng, "connect_in_shared_face", flaky)
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert "1/2 cut(s) applied" in knife.last_message
    assert len(scene.history) == 1
    assert_mesh_invariants(mesh, context="D dropped run")
    scene.history.undo()
    assert _state_no_counters(mesh) == before
    scene.history.redo()
    assert len(mesh.all_face_ids()) == 2


def test_d_lone_boundary_point_leaves_mesh_untouched():
    scene, fid = _ngon_scene(4)
    mesh = scene.mesh
    before = mesh.export_state()
    knife = _begin(KnifeFaceCollected, scene)
    assert knife.click(_edge_target(mesh.face_edges(fid)[0], 0.5))
    assert knife.commit() is None
    knife.deactivate()
    assert mesh.export_state() == before


# ---------------------------------------------------------------------------
# Closed shape: bridges independent of click order and direction (Task A, 2026-09-29)
# Reference: FACE_HOLES_DISCOVERY.md §6 (winding defect) — probe:
# experiments/topology/knife_bridge_order_probe.py
# ---------------------------------------------------------------------------

def _rnd(p):
    return tuple(round(c, 6) + 0.0 for c in p)


def _dot3(a, b):
    return sum(x * y for x, y in zip(a, b))


def _bilinear(corners, u, v):
    a, b, c, d = corners
    return tuple((1 - u) * (1 - v) * a[i] + u * (1 - v) * b[i] + u * v * c[i] + (1 - u) * v * d[i]
                 for i in range(3))


def _loop_points(corners, k, shape):
    """k loop points, counter-clockwise in the quad's (u, v) parameter square."""
    pts = []
    for i in range(k):
        if shape == "tie":  # k == 4: the square whose distances to all four corners are exactly equal
            u, v = ((0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75))[i]
        else:
            a = 2 * math.pi * i / k
            if shape == "sym":
                u, v = 0.5 + 0.25 * math.cos(a), 0.5 + 0.25 * math.sin(a)
            else:  # "skew": off-centre, unequal radii
                r = 0.16 + 0.10 * ((i * 7) % 5) / 4.0
                u, v = 0.44 + r * math.cos(a), 0.58 + r * math.sin(a)
        pts.append(_bilinear(corners, u, v))
    return pts


def _rotations_both_ways(pts):
    k = len(pts)
    for seq in (pts, list(reversed(pts))):
        for s in range(k):
            yield seq[s:] + seq[:s]


def _lowest_first(seq):
    i = min(range(len(seq)), key=lambda j: seq[j])
    return tuple(seq[i:] + seq[:i])


def _closed_shape_signature(mesh, scene_faces_before, loop, parent_normal, parent_poly2d, project):
    """Everything an order-independent result must agree on, plus the per-run quality checks."""
    orig = set(scene_faces_before["vertices"])
    seqs, inner = set(), None
    for f in mesh.all_face_ids():
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(f)]
        assert _dot3(_newell(pts), parent_normal) > 0, "face normal disagrees with the parent's"
        seqs.add(_lowest_first([_rnd(p) for p in pts]))
        if {_rnd(p) for p in pts} == {_rnd(p) for p in loop}:
            inner = f
    bridges = frozenset(
        frozenset(_rnd(mesh.vertex_position(v)) for v in mesh.edge_vertices(e))
        for e in mesh.all_edge_ids()
        if len(set(mesh.edge_vertices(e)) & orig) == 1 and len(set(mesh.edge_vertices(e)) - orig) == 1
    )
    assert inner is not None and len(bridges) == 2 and len(seqs) == 3

    # no overlap: every sample of the parent (projected) lies in exactly one face
    polys = [[project(mesh.vertex_position(v)) for v in mesh.face_vertices(f)] for f in mesh.all_face_ids()]
    xs, ys = [q[0] for q in parent_poly2d], [q[1] for q in parent_poly2d]
    n = 23
    for i in range(n):
        for j in range(n):
            pt = (min(xs) + (max(xs) - min(xs)) * (i + 0.3183) / n, min(ys) + (max(ys) - min(ys)) * (j + 0.2718) / n)
            if _in_poly2d(pt, parent_poly2d):
                assert sum(1 for pl in polys if _in_poly2d(pt, pl)) == 1, f"overlap/gap at {pt}"
    return bridges, frozenset(seqs), inner


def _newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return tuple(n)


def _in_poly2d(pt, poly):
    x, y = pt
    inside = False
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _projector(parent_pts, normal):
    """Projection onto the plane through the parent's centroid (non-planar quads: the projected measure)."""
    cen = tuple(sum(p[i] for p in parent_pts) / len(parent_pts) for i in range(3))
    L = math.sqrt(_dot3(normal, normal))
    n = tuple(c / L for c in normal)
    ref = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = (n[1] * ref[2] - n[2] * ref[1], n[2] * ref[0] - n[0] * ref[2], n[0] * ref[1] - n[1] * ref[0])
    L = math.sqrt(_dot3(u, u))
    u = tuple(c / L for c in u)
    v = (n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2], n[0] * u[1] - n[1] * u[0])
    return lambda p: (_dot3(tuple(p[i] - cen[i] for i in range(3)), u), _dot3(tuple(p[i] - cen[i] for i in range(3)), v))


def _one_face_scene(corners, orientation=1):
    scene = Scene()
    vs = [scene.mesh.add_vertex(c) for c in (corners if orientation == 1 else list(reversed(corners)))]
    fid = scene.mesh.add_face(vs)
    return scene, fid


def _click_loop_and_commit(cls, scene, fid, loop):
    knife = _begin(cls, scene)
    for p in loop:
        assert knife.click(_face_target(fid, p))
    cmd = knife.commit()
    knife.deactivate()
    assert cmd is not None
    return cmd


def _permutation_matrix(corners, ks, shapes, orientation=1):
    for shape in shapes:
        for k in ks:
            if shape == "tie" and k != 4:
                continue
            loop = _loop_points(corners, k, shape)
            results = set()
            for clicks in _rotations_both_ways(loop):
                scene, fid = _one_face_scene(corners, orientation)
                mesh = scene.mesh
                parent = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
                normal = _newell(parent)
                before = {"vertices": list(mesh.all_vertex_ids())}
                project = _projector(parent, normal)
                _click_loop_and_commit(KnifeFaceCollected, scene, fid, clicks)
                assert_mesh_invariants(mesh, context=f"D closed shape {shape} k={k}")
                assert _winding_mismatches(mesh) == 0
                bridges, partition, inner = _closed_shape_signature(
                    mesh, before, loop, normal, [project(p) for p in parent], project)
                results.add((bridges, partition))
            assert len(results) == 1, f"{shape} k={k}: click order/direction changed the result ({len(results)} variants)"


def _winding_mismatches(mesh):
    """Interior edges traversed in the same direction by both of their faces."""
    directed = collections.defaultdict(list)
    for f in mesh.all_face_ids():
        b = mesh.face_vertices(f)
        for i in range(len(b)):
            directed[frozenset((b[i], b[(i + 1) % len(b)]))].append((b[i], b[(i + 1) % len(b)]))
    return sum(1 for uses in directed.values() if len(uses) == 2 and uses[0] == uses[1])


_UNIT_QUAD = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]


def test_closed_shape_grid_quad_is_independent_of_click_order_and_direction():
    _permutation_matrix(_UNIT_QUAD, range(3, 9), ("sym", "skew", "tie"))


def test_closed_shape_clockwise_parent_face_is_independent_too():
    """The canonical winding is the *parent's*, not "counter-clockwise": a face stored the other way round."""
    _permutation_matrix(_UNIT_QUAD, (3, 4, 6), ("sym", "skew", "tie"), orientation=-1)


def test_closed_shape_nonplanar_head_quads_are_independent_of_click_order_and_direction():
    from mirai.scene_factory import build_core_scene_from_obj
    from playground._paths import DEFAULT_HEAD_ASSET

    head = build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh
    quads = [f for f in sorted(head.all_face_ids(), key=int) if len(head.face_vertices(f)) == 4]
    for f in quads[:: max(1, len(quads) // 4)][:4]:
        corners = [head.vertex_position(v) for v in head.face_vertices(f)]
        _permutation_matrix(corners, (3, 5, 8), ("sym", "skew"))


def test_close_loop_with_bridges_orients_the_loop_like_the_parent():
    """Direct call, both click directions: inner face has the parent's normal, ring faces do not overlap it."""
    for loop in ([(0.3, 0.3, 0.0), (0.7, 0.3, 0.0), (0.5, 0.7, 0.0)],
                 [(0.3, 0.3, 0.0), (0.5, 0.7, 0.0), (0.7, 0.3, 0.0)]):
        scene, fid = _one_face_scene(_UNIT_QUAD)
        mesh = scene.mesh
        boundary = mesh.face_vertices(fid)
        i1, bv1, i2, bv2 = select_bridge(mesh, boundary, loop)
        loop_vs, f_inner, f_a, f_b, loop_edges = close_loop_with_bridges(mesh, fid, loop, i1, bv1, i2, bv2)
        assert [mesh.vertex_position(v) for v in loop_vs] == loop   # caller's order kept
        assert len(loop_edges) == 3 and all(mesh.is_valid_edge(e) for e in loop_edges)
        assert _newell([mesh.vertex_position(v) for v in mesh.face_vertices(f_inner)])[2] > 0
        assert _winding_mismatches(mesh) == 0
        assert_mesh_invariants(mesh, context="close_loop_with_bridges")
        areas = [abs(_newell([mesh.vertex_position(v) for v in mesh.face_vertices(f)])[2]) / 2 for f in (f_inner, f_a, f_b)]
        assert math.isclose(sum(areas), 1.0, abs_tol=1e-9)


def test_loop_matches_winding():
    boundary = list(_UNIT_QUAD)
    ccw = [(0.3, 0.3, 0.0), (0.7, 0.3, 0.0), (0.5, 0.7, 0.0)]
    assert loop_matches_winding(ccw, boundary)
    assert not loop_matches_winding(list(reversed(ccw)), boundary)
    assert loop_matches_winding(list(reversed(ccw)), list(reversed(boundary)))
    assert loop_matches_winding([(0.3, 0.3, 0.0), (0.6, 0.3, 0.0), (0.9, 0.3, 0.0)], boundary)  # no area: as clicked


def test_closed_shape_island_is_an_ordinary_face_select_and_delete():
    """The inner face ("island") can be selected and deleted with existing Core API; the ring keeps consistent winding."""
    for direction in (1, -1):
        loop = _loop_points(_UNIT_QUAD, 5, "skew")[::direction]
        scene, fid = _one_face_scene(_UNIT_QUAD)
        mesh = scene.mesh
        _click_loop_and_commit(KnifeFaceCollected, scene, fid, loop)
        inner = next(f for f in mesh.all_face_ids() if {_rnd(mesh.vertex_position(v)) for v in mesh.face_vertices(f)}
                     == {_rnd(p) for p in loop})

        scene.selection.mode = SelectionMode.FACE
        scene.selection.clear()
        scene.selection.add({inner})
        assert inner in scene.selection.faces
        mesh.remove_face(inner)

        assert len(mesh.all_face_ids()) == 2
        assert not mesh.is_valid_face(inner)
        assert_mesh_invariants(mesh, context="island deleted")
        assert _winding_mismatches(mesh) == 0
        # the two ring faces still wind like the original quad
        for f in mesh.all_face_ids():
            assert _newell([mesh.vertex_position(v) for v in mesh.face_vertices(f)])[2] > 0


def test_select_bridge_does_not_depend_on_loop_order_on_exact_ties():
    """A square loop in a square face: every loop point is exactly as far from its corner as any other."""
    scene, fid = _one_face_scene(_UNIT_QUAD)
    mesh = scene.mesh
    boundary = mesh.face_vertices(fid)
    loop = _loop_points(_UNIT_QUAD, 4, "tie")
    chosen = set()
    for clicks in _rotations_both_ways(loop):
        i1, bv1, i2, bv2 = select_bridge(mesh, boundary, clicks)
        chosen.add(frozenset({(_rnd(clicks[i1]), _rnd(mesh.vertex_position(bv1))),
                              (_rnd(clicks[i2]), _rnd(mesh.vertex_position(bv2)))}))
    assert len(chosen) == 1
