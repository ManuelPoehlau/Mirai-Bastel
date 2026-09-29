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
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"),
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
    face_interior_hit,
    knife_face_pick,
    min_edge_distance_px,
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
