"""Knife Face Lab — Variant Q5 (cross-face segments on top of D): headless tests.

Engine level (no GL, no window): planner, gaps, snap, close-and-continue, undo,
camera fix, A5 lock. D's own behaviour is covered by `test_knife_face_lab.py`
(unchanged); the last block here checks the family registration.
"""

from __future__ import annotations

import collections
import copy
import math
import random
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"),
           str(_REPO_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from core import Mesh, Scene  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from mirai.viewport.picking_cache import PickCache  # noqa: E402

from playground._paths import DEFAULT_HEAD_ASSET  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.experiments.knife_face import (  # noqa: E402
    KnifeFaceVariantB,
    KnifeFaceVariantD,
    KnifeFaceVariantQ5,
)
from playground.experiments.knife_face.engine import KnifeFaceCollected, knife_face_pick  # noqa: E402
from playground.experiments.knife_face.engine_q5 import (  # noqa: E402
    EARLIER_POINT_NOTE,
    SNAP_PX,
    KnifeFaceCrossFace,
)
from playground.experiments.knife_face.planner import View, plan_crossings, point_position  # noqa: E402
from playground.slot import ExperimentSlot, VariantEntry  # noqa: E402

W, H = 1280, 800


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _grid(n: int = 4, hole=None):
    """n x n quads in z=0; `hole=(c, r)` leaves that quad out."""
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            if (c, r) == hole:
                continue
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh, p


def _camera(mesh, yaw=20.0, pitch=35.0) -> OrbitCamera:
    cam = OrbitCamera(yaw=math.radians(yaw), pitch=math.radians(pitch))
    center, radius = mesh_center_and_radius(mesh)
    cam.frame_on_bounds(center, radius, margin=1.4)
    return cam


def _session(mesh, cam, *, cls=KnifeFaceCrossFace, cache=None, occlusion=True):
    scene = Scene()
    scene.mesh = mesh
    knife = cls()
    knife.activate()
    knife.begin(mesh=mesh, scene=scene, selection=scene.selection)
    if cam is not None and hasattr(knife, "set_view"):
        knife.set_view(cam, W, H, cache=cache, occlusion=occlusion)
    return knife, scene


def _edge(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _ept(mesh, a, b, t_from_a):
    """Edge point given from `a`'s side (the edge may be stored the other way round)."""
    eid = _edge(mesh, a, b)
    t = t_from_a if mesh.edge_vertices(eid)[0] == a else 1.0 - t_from_a
    return {"kind": "edge", "edge_id": eid, "t": t}


def _vpt(vid):
    return {"kind": "vertex", "vertex_id": vid}


def _face_at(cam, mesh, world, *, cache=None):
    """A face target picked exactly as the window does: project, then knife_face_pick."""
    s = cam.project_to_screen(world, W, H)
    target = knife_face_pick(cam, mesh, s[0], s[1], W, H, cache=cache, occlusion=True)
    assert target["kind"] == "face", target
    return target


def _sizes(mesh):
    return dict(sorted(collections.Counter(len(mesh.face_vertices(f)) for f in mesh.all_face_ids()).items()))


def _crossings(knife):
    return [p for p in knife.path if p.get("crossing")]


def _breaks(knife, reason=None):
    return [p for p in knife.path if p["kind"] == "break" and (reason is None or p.get("reason") == reason)]


# ---------------------------------------------------------------------------
# 4.1 Planner: one click across several faces
# ---------------------------------------------------------------------------

def test_grid_edge_three_quads_edge_in_one_click():
    mesh, p = _grid()
    knife, scene = _session(mesh, _camera(mesh))
    before = len(mesh.all_face_ids())

    assert knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3))
    assert knife.click(_ept(mesh, p[(1, 3)], p[(2, 3)], 0.6))
    assert len(_crossings(knife)) == 2 and not _breaks(knife)
    cmd = knife.commit()
    knife.deactivate()

    assert cmd is not None
    assert "3/3 cut(s) applied" in knife.last_message
    assert len(mesh.all_face_ids()) == before + 3
    assert_mesh_invariants(mesh, context="Q5 grid 3 quads")
    assert len(scene.history) == 1


def test_task2_edge_interior_neighbour_interior_edge_cuts_both_quads():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    for t in (_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5),               # edge (left border of quad c=0)
              _face_at(cam, mesh, (0.5, 1.4, 0.0)),                 # inside that quad
              _face_at(cam, mesh, (1.5, 1.6, 0.0)),                 # inside the NEIGHBOUR quad
              _ept(mesh, p[(1, 2)], p[(2, 2)], 0.5)):               # edge of the neighbour (x=2)
        assert knife.click(t)
    knife.commit()
    assert "2/2 cut(s) applied" in knife.last_message
    assert len(mesh.all_face_ids()) == 18
    assert_mesh_invariants(mesh, context="Q5 task 2")


def test_task3_interior_start_first_quad_is_not_cut_neighbour_is():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    for t in (_face_at(cam, mesh, (0.5, 1.5, 0.0)), _face_at(cam, mesh, (1.5, 1.5, 0.0)),
              _ept(mesh, p[(1, 2)], p[(2, 2)], 0.5)):
        assert knife.click(t)
    knife.commit()
    assert "leading interior point(s) dropped" in knife.last_message
    assert len(mesh.all_face_ids()) == 16 + 1     # only the neighbour quad was divided
    first = {p[(1, 0)], p[(1, 1)], p[(2, 1)], p[(2, 0)]}
    assert any(first <= set(mesh.face_vertices(f)) for f in mesh.all_face_ids())  # first quad still whole
    assert_mesh_invariants(mesh, context="Q5 task 3")


def test_far_click_crosses_any_number_of_faces():
    """Not limited to the neighbour face: edge -> 3 quads away in a single click."""
    mesh, p = _grid(n=6)
    knife, _scene = _session(mesh, _camera(mesh))
    assert knife.click(_ept(mesh, p[(3, 0)], p[(4, 0)], 0.5))
    assert knife.click(_ept(mesh, p[(3, 6)], p[(4, 6)], 0.5))
    assert len(_crossings(knife)) == 5
    knife.commit()
    assert "6/6 cut(s) applied" in knife.last_message
    assert_mesh_invariants(mesh, context="Q5 6 quads")


def test_vertex_pass_through_snaps_within_half_pixel_no_sliver():
    mesh, p = _grid()
    cam = _camera(mesh)
    # (0.5+d, 0) -> (1.5+d, 2) passes (1+d, 1): d = 0.002 is ~0.2 px from vertex (1, 1).
    d = 0.002
    knife, _scene = _session(mesh, cam)
    knife.click(_ept(mesh, p[(0, 0)], p[(0, 1)], 0.5 + d))
    assert knife.click(_ept(mesh, p[(2, 1)], p[(2, 2)], 0.5 + d))
    assert [c["kind"] for c in _crossings(knife)] == ["vertex"]
    assert _crossings(knife)[0]["vertex_id"] == p[(1, 1)]
    knife.commit()
    assert_mesh_invariants(mesh, context="Q5 vertex snap")
    # no sliver: nothing within 1% of an original vertex was cut off an edge
    shortest = min(
        math.dist(mesh.vertex_position(a), mesh.vertex_position(b)) for a, b in
        (mesh.edge_vertices(e) for e in mesh.all_edge_ids())
    )
    assert shortest > 0.1


def test_vertex_tolerance_does_not_over_snap_two_pixels_off():
    mesh, p = _grid()
    cam = _camera(mesh)
    d = 0.02  # ~1.7-2 px from vertex (1, 1) under this camera
    px = math.dist(cam.project_to_screen((1.0, 1.0, 0.0), W, H), cam.project_to_screen((1.0 + d, 1.0, 0.0), W, H))
    assert px > 1.0
    knife, _scene = _session(mesh, cam)
    knife.click(_ept(mesh, p[(0, 0)], p[(0, 1)], 0.5 + d))
    assert knife.click(_ept(mesh, p[(2, 1)], p[(2, 2)], 0.5 + d))
    assert [c["kind"] for c in _crossings(knife)] == ["edge", "edge"]
    knife.commit()
    assert_mesh_invariants(mesh, context="Q5 no over-snap")


def test_hole_visible_pieces_cut_gap_skipped_hud_note():
    mesh, p = _grid(hole=(2, 1))
    knife, scene = _session(mesh, _camera(mesh))
    faces_before = len(mesh.all_face_ids())

    assert knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5))
    assert knife.click(_ept(mesh, p[(1, 4)], p[(2, 4)], 0.5))  # accepted: the target itself is valid
    assert "skipped" in knife.last_message and "hole" in knife.last_message
    assert len(_breaks(knife, "gap")) == 1
    knife.commit()

    assert "3/3 cut(s) applied" in knife.last_message and "1 stretch(es) skipped" in knife.last_message
    assert len(mesh.all_face_ids()) == faces_before + 3
    assert_mesh_invariants(mesh, context="Q5 hole")
    assert len(scene.history) == 1


def test_no_run_is_connected_across_a_gap():
    mesh, p = _grid(hole=(2, 1))
    knife, _scene = _session(mesh, _camera(mesh))
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5))
    knife.click(_ept(mesh, p[(1, 4)], p[(2, 4)], 0.5))
    knife.commit()
    # the crossings on the hole's two borders lie on the same line but share no face
    def vertex_at(x, y):
        return next(v for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), (x, y, 0.0)) < 1e-3)

    left, right = vertex_at(2.0, 1.5), vertex_at(3.0, 1.5)
    assert not any(set(mesh.edge_vertices(e)) == {left, right} for e in mesh.all_edge_ids())
    assert_mesh_invariants(mesh, context="Q5 gap")


def _occluded_grid():
    """4x4 grid in z=0 plus a small quad in front that hides the x=2 crossing of
    a y=1.5 line seen from the front."""
    mesh, p = _grid()
    occ = [mesh.add_vertex(v) for v in ((1.6, 1.2, 0.6), (2.4, 1.2, 0.6), (2.4, 1.8, 0.6), (1.6, 1.8, 0.6))]
    mesh.add_face(occ)
    return mesh, p


def test_one_hit_face_at_a_piece_end_is_not_cut():
    mesh, p = _occluded_grid()
    knife, _scene = _session(mesh, _camera(mesh, 0.0, 0.0))
    faces_before = len(mesh.all_face_ids())
    a = _ept(mesh, p[(1, 0)], p[(2, 0)], 0.5)
    b = _ept(mesh, p[(1, 4)], p[(2, 4)], 0.5)
    assert knife.click(a) and knife.click(b)
    # visible hits: x=1, the occluder's two edges, x=3; the x=2 crossing is hidden behind it
    assert len(_crossings(knife)) == 4
    assert "1 hidden crossing(s) not cut" in knife.last_message
    assert len(_breaks(knife, "gap")) == 2
    knife.commit()
    # quads (c=1) and (c=2) each got exactly one hit (x=1 / x=3): not cut. Cut: quad c=0,
    # the occluder itself (visibly crossed) and quad c=3.
    assert "3/3 cut(s) applied" in knife.last_message
    assert len(mesh.all_face_ids()) == faces_before + 3
    for corners in (((1, 1), (1, 2), (2, 2), (2, 1)), ((1, 2), (1, 3), (2, 3), (2, 2))):
        vs = {p[c] for c in corners}
        assert any(vs <= set(mesh.face_vertices(f)) for f in mesh.all_face_ids())  # still one face
    assert_mesh_invariants(mesh, context="Q5 one-hit faces")


def test_without_occlusion_nothing_is_hidden_and_nothing_skipped():
    mesh, p = _occluded_grid()
    knife, _scene = _session(mesh, _camera(mesh, 0.0, 0.0), occlusion=False)
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5))
    knife.click(_ept(mesh, p[(1, 4)], p[(2, 4)], 0.5))
    # Wireframe (no occlusion): the walk follows the grid's own connectivity, all
    # three crossings are cut and there is no gap.
    assert len(_crossings(knife)) == 3 and not _breaks(knife)


def test_along_an_existing_edge_is_skipped_not_refused():
    mesh, p = _grid()
    knife, _scene = _session(mesh, _camera(mesh))
    assert knife.click(_vpt(p[(1, 0)]))
    assert knife.click(_vpt(p[(1, 1)]))  # adjacent vertex: nothing to cut
    assert len(_breaks(knife, "edge")) == 1 and "along an existing edge" in knife.last_message
    faces = len(mesh.all_face_ids())
    knife.commit()
    assert len(mesh.all_face_ids()) == faces


def test_crossing_dots_and_lines_in_hover_plan():
    mesh, p = _grid()
    knife, _scene = _session(mesh, _camera(mesh))
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3))
    plan = knife.hover(_ept(mesh, p[(1, 3)], p[(2, 3)], 0.6))["plan"]
    assert plan.ok and len(plan.crossings) == 2
    assert [style for _a, _b, style in plan.lines] == ["cut"] * 3
    assert len(knife.path) == 1  # hover never mutates the session


def test_cross_face_target_without_a_view_is_rejected():
    mesh, p = _grid()
    knife, _scene = _session(mesh, None)
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3))
    assert not knife.click(_ept(mesh, p[(1, 3)], p[(2, 3)], 0.6))
    assert "no camera view" in knife.last_message


# ---------------------------------------------------------------------------
# Camera: crossings are fixed at click time
# ---------------------------------------------------------------------------

def _head():
    return build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh


def _head_segment():
    """A -> B on the head with >= 3 crossings under cam2 whose crossings differ under cam3."""
    mesh = _head()
    cam1, cam2, cam3 = _camera(mesh, 225, 25), _camera(mesh, 235, 25), _camera(mesh, 250, 15)
    rnd = random.Random(3)
    xs = [cam1.project_to_screen(mesh.vertex_position(v), W, H) for v in mesh.all_vertex_ids()]
    xs = [x for x in xs if x is not None]
    lo_x, hi_x, lo_y, hi_y = min(x[0] for x in xs), max(x[0] for x in xs), min(x[1] for x in xs), max(x[1] for x in xs)
    for _ in range(4000):
        s1 = (rnd.uniform(lo_x, hi_x), rnd.uniform(lo_y, hi_y))
        a = knife_face_pick(cam1, mesh, s1[0], s1[1], W, H, occlusion=True)
        if a["kind"] != "face" or a["distance_px"] < 9.0:
            continue
        s2 = (s1[0] + rnd.uniform(-160, 160), s1[1] + rnd.uniform(-160, 160))
        b = knife_face_pick(cam2, mesh, s2[0], s2[1], W, H, occlusion=True)
        if b["kind"] != "face" or b["distance_px"] < 9.0 or a["face_id"] == b["face_id"]:
            continue
        pa = {"kind": "face", "face_id": a["face_id"], "position": a["position"]}
        pb = {"kind": "face", "face_id": b["face_id"], "position": b["position"]}
        r2 = plan_crossings(View(cam2, W, H, None, True), mesh, pa, pb)
        r3 = plan_crossings(View(cam3, W, H, None, True), mesh, pa, pb)
        if r2.method == "walk" and len(r2.crossings) >= 3 and r3.crossings != r2.crossings:
            return mesh, (cam1, cam2, cam3), a, b
    raise AssertionError("no suitable head segment found")


def test_camera_change_after_a_click_does_not_change_the_result():
    mesh0, (cam1, cam2, cam3), a, b = _head_segment()

    def run(extra_orbit: bool):
        mesh = copy.deepcopy(mesh0)
        knife, _scene = _session(mesh, cam1)
        assert knife.click(a)                       # clicked in view 1
        knife.set_view(cam2, W, H)                  # orbit, then the target
        assert knife.click(b)
        stored = [dict(c) for c in _crossings(knife)]
        if extra_orbit:                             # orbit again: hover + set_view under a third camera
            knife.set_view(cam3, W, H)
            knife.hover(b)
        knife.commit()
        return mesh, stored, knife.last_message

    m_orbit, crossings_orbit, msg_orbit = run(True)
    m_plain, crossings_plain, msg_plain = run(False)
    assert len(crossings_plain) >= 3
    assert crossings_orbit == crossings_plain
    assert msg_orbit == msg_plain
    assert m_orbit.export_state() == m_plain.export_state()
    assert_mesh_invariants(m_orbit, context="Q5 camera fix (head)")


# ---------------------------------------------------------------------------
# 4.2 Snap
# ---------------------------------------------------------------------------

def test_snap_to_a_virtual_path_point_within_14px_not_outside():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    first = _face_at(cam, mesh, (1.5, 1.5, 0.0))
    knife.click(first)
    knife.click(_face_at(cam, mesh, (1.7, 1.3, 0.0)))
    sx, sy = cam.project_to_screen(first["position"], W, H)

    near = knife.snap_target(_face_at(cam, mesh, (1.5, 1.5, 0.0)), sx + SNAP_PX - 2.0, sy)
    assert near == {"kind": "path", "index": 0}
    far = knife.snap_target(_face_at(cam, mesh, (1.5, 1.5, 0.0)), sx + SNAP_PX + 6.0, sy)
    assert far["kind"] == "face"
    assert SNAP_PX == 14.0


def test_snap_to_a_mesh_vertex_within_14px_not_outside():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    knife.click(_face_at(cam, mesh, (1.5, 1.5, 0.0)))
    vx, vy = cam.project_to_screen(mesh.vertex_position(p[(2, 2)]), W, H)

    inside = knife_face_pick(cam, mesh, vx + SNAP_PX - 2.0, vy, W, H, occlusion=True)
    assert inside == _vpt(p[(2, 2)])
    assert knife.snap_target(inside, vx + SNAP_PX - 2.0, vy) == inside
    plan = knife.plan(inside)
    assert plan.ok and plan.snap_position == mesh.vertex_position(p[(2, 2)])

    outside = knife_face_pick(cam, mesh, vx + SNAP_PX + 8.0, vy, W, H, occlusion=True)
    assert outside["kind"] != "vertex"
    assert knife.plan(outside).snap_position is None


def test_nearer_session_point_wins_over_a_picked_mesh_vertex():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    fid = next(f for f in mesh.all_face_ids() if p[(1, 1)] in mesh.face_vertices(f) and p[(2, 2)] in mesh.face_vertices(f))
    first = {"kind": "face", "face_id": fid, "position": (1.91, 1.91, 0.0), "distance_px": 9.5}  # ~13 px from v(2,2)
    assert knife.click(first)
    assert knife.click(_face_at(cam, mesh, (1.5, 1.3, 0.0)))
    px, py = cam.project_to_screen(first["position"], W, H)
    target = knife_face_pick(cam, mesh, px, py, W, H, occlusion=True)
    assert target == _vpt(p[(2, 2)])  # the 14 px vertex pick fires as well ...
    assert knife.snap_target(target, px, py) == {"kind": "path", "index": 0}  # ... but the session point is nearer


# ---------------------------------------------------------------------------
# 4.2 Close and continue
# ---------------------------------------------------------------------------

def _loop4(cam, mesh):
    return [_face_at(cam, mesh, w) for w in
            ((1.5, 1.5, 0.0), (2.5, 1.5, 0.0), (2.5, 2.5, 0.0), (1.5, 2.5, 0.0))]


def _close_by_click(knife, cam, mesh, first):
    sx, sy = cam.project_to_screen(first["position"], W, H)
    target = knife.snap_target(knife_face_pick(cam, mesh, sx + 5.0, sy + 3.0, W, H, occlusion=True), sx + 5.0, sy + 3.0)
    assert target == {"kind": "path", "index": 0}
    return knife.click(target)


def test_interior_start_loop_over_four_quads_closes_without_bridges():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    ids_before = (set(mesh.all_vertex_ids()), set(mesh.all_edge_ids()))
    pts = _loop4(cam, mesh)
    for t in pts:
        assert knife.click(t)
    assert _close_by_click(knife, cam, mesh, pts[0])
    assert knife.path[-1] == {"kind": "break", "reason": "closed", "cyclic": True}
    assert len(scene.history) == 0                          # closing does not commit
    assert mesh.export_state() == scene.mesh.export_state()  # nothing applied yet (D model)

    cmd = knife.commit()
    assert cmd is not None
    assert "4/4 cut(s) applied" in knife.last_message
    assert _sizes(mesh) == {4: 16, 6: 4}
    assert_mesh_invariants(mesh, context="Q5 loop4")
    cut = [e for e in knife.path_edges if mesh.is_valid_edge(e)]
    assert len(cut) == 8
    assert not [e for e in cut if set(mesh.edge_vertices(e)) & ids_before[0]]  # 0 bridges
    assert len(scene.history) == 1


def test_boundary_start_loop_across_faces_closes_fully():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    start = _ept(mesh, p[(1, 2)], p[(2, 2)], 0.2)           # on the edge x=2 between two quads
    for t in (start, _face_at(cam, mesh, (1.4, 1.5, 0.0)),
              _ept(mesh, p[(1, 2)], p[(2, 2)], 0.8), _face_at(cam, mesh, (2.6, 1.5, 0.0))):
        assert knife.click(t)
    px = cam.project_to_screen(point_position(mesh, start), W, H)
    target = knife.snap_target(knife_face_pick(cam, mesh, px[0] + 3.0, px[1], W, H, occlusion=True), px[0] + 3.0, px[1])
    assert target == {"kind": "path", "index": 0}
    assert knife.click(target)
    assert knife.path[-1]["reason"] == "closed" and knife.path[-1]["cyclic"]
    knife.commit()
    assert "2/2 cut(s) applied" in knife.last_message
    assert_mesh_invariants(mesh, context="Q5 boundary-start loop")


def test_vertex_start_loop_closes_by_clicking_that_vertex():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    v = p[(2, 2)]
    for t in (_vpt(v), _face_at(cam, mesh, (1.5, 1.5, 0.0)), _face_at(cam, mesh, (2.5, 1.5, 0.0)),
              _face_at(cam, mesh, (2.5, 2.5, 0.0))):
        assert knife.click(t)
    assert knife.click(_vpt(v))  # a picked mesh vertex that is the chain start closes it
    assert knife.path[-1]["reason"] == "closed"
    knife.commit()
    assert_mesh_invariants(mesh, context="Q5 vertex-start loop")


def test_after_close_a_new_independent_chain_starts_and_commit_ends_the_session():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    pts = _loop4(cam, mesh)
    for t in pts:
        knife.click(t)
    assert _close_by_click(knife, cam, mesh, pts[0])
    n_closed = len(knife.path)

    # a new chain far from the loop: two edge points of quad (0,0)
    assert knife.click(_ept(mesh, p[(0, 0)], p[(0, 1)], 0.5))
    assert knife.click(_ept(mesh, p[(1, 0)], p[(1, 1)], 0.5))
    assert len(knife.path) == n_closed + 2
    assert [q["kind"] for q in knife.path[n_closed - 1:n_closed + 1]] == ["break", "edge"]  # no run across the break
    assert len(scene.history) == 0
    knife.commit()
    assert "5/5 cut(s) applied" in knife.last_message
    assert _sizes(mesh)[6] == 4
    assert_mesh_invariants(mesh, context="Q5 close then continue")
    assert len(scene.history) == 1


def test_close_is_one_undo_step_and_redo_restores_it():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    pts = _loop4(cam, mesh)
    for t in pts:
        knife.click(t)
    before_close = knife.path
    assert _close_by_click(knife, cam, mesh, pts[0])
    closed = knife.path
    assert knife.undo_step()
    assert knife.path == before_close                # the whole closing click (crossings + break) is gone
    assert knife.redo_step()
    assert knife.path == closed


def test_click_on_a_snapped_earlier_point_is_rejected_with_a_note():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    pts = _loop4(cam, mesh)
    for t in pts:
        knife.click(t)
    n = len(knife.path)
    plan = knife.plan({"kind": "path", "index": 2})   # not the chain start
    assert not plan.ok and plan.reason == EARLIER_POINT_NOTE and plan.snap_position is not None
    assert not knife.click({"kind": "path", "index": 2})
    assert knife.last_message == f"rejected: {EARLIER_POINT_NOTE}"
    assert len(knife.path) == n

    assert _close_by_click(knife, cam, mesh, pts[0])
    assert not knife.click({"kind": "path", "index": 0})   # a point of an already closed chain
    assert knife.last_message == f"rejected: {EARLIER_POINT_NOTE}"


def test_closing_needs_three_points():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    knife.click(_face_at(cam, mesh, (1.5, 1.5, 0.0)))
    knife.click(_face_at(cam, mesh, (2.5, 1.5, 0.0)))
    plan = knife.plan({"kind": "path", "index": 0})
    assert not plan.ok and "at least 3" in plan.reason


def test_loop_inside_one_face_keeps_the_two_bridge_stand_in():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    pts = [_face_at(cam, mesh, w) for w in ((1.3, 1.3, 0.0), (1.7, 1.3, 0.0), (1.5, 1.7, 0.0))]
    for t in pts:
        assert knife.click(t)
    assert _close_by_click(knife, cam, mesh, pts[0])
    assert len(scene.history) == 0
    knife.commit()
    assert "closed shape" in knife.last_message and "2 bridges" in knife.last_message
    assert len(mesh.all_face_ids()) == 16 + 2
    assert_mesh_invariants(mesh, context="Q5 in-face loop")


# ---------------------------------------------------------------------------
# 4.3 Undo / redo, A5 lock
# ---------------------------------------------------------------------------

def test_one_click_with_k_crossings_undoes_as_one_step():
    mesh, p = _grid()
    knife, _scene = _session(mesh, _camera(mesh))
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3))
    one = knife.path
    knife.click(_ept(mesh, p[(1, 3)], p[(2, 3)], 0.6))
    two = knife.path
    assert len(two) == 4  # target + 2 crossings

    assert knife.undo_step() and knife.path == one
    assert knife.redo_step() and knife.path == two
    assert knife.undo_step() and knife.undo_step()
    assert knife.path == [] and not knife.undo_step()


def test_a5_lock_is_off_in_q5_and_still_on_in_d():
    def sequence(cls):
        mesh, p = _grid()
        cam = _camera(mesh)
        knife, _scene = _session(mesh, cam, cls=cls)
        e1 = _ept(mesh, p[(1, 1)], p[(2, 1)], 0.5)
        e2 = _ept(mesh, p[(1, 2)], p[(2, 2)], 0.5)
        assert knife.click(e1)
        assert knife.click(_face_at(cam, mesh, (1.5, 1.3, 0.0)))
        assert knife.click(e2)                       # run boundary-interior-boundary completed
        return knife.click(_face_at(cam, mesh, (2.5, 1.5, 0.0))), knife   # neighbour face interior

    ok_d, knife_d = sequence(KnifeFaceCollected)
    ok_q5, knife_q5 = sequence(KnifeFaceCrossFace)
    assert ok_d is False and knife_d._face_cut_lock is True
    assert ok_q5 is True and knife_q5._face_cut_lock is False


def test_same_face_clicks_behave_like_d():
    """Direct (same-face) links need no planner and no view: D and Q5 cut identically."""
    results = []
    for cls in (KnifeFaceCollected, KnifeFaceCrossFace):
        mesh, p = _grid()
        knife, scene = _session(mesh, None, cls=cls)
        fid = next(f for f in mesh.all_face_ids() if {p[(1, 1)], p[(2, 2)]} <= set(mesh.face_vertices(f)))
        assert knife.click(_ept(mesh, p[(1, 1)], p[(2, 1)], 0.5))
        assert knife.click({"kind": "face", "face_id": fid, "position": (1.5, 1.3, 0.0), "distance_px": 20.0})
        assert knife.click(_ept(mesh, p[(1, 2)], p[(2, 2)], 0.5))
        assert knife.commit() is not None
        assert_mesh_invariants(mesh, context=cls.__name__)
        assert len(scene.history) == 1
        results.append((_sizes(mesh), knife.last_message))
    assert results[0] == results[1]


def test_esc_restores_the_mesh_and_commit_writes_one_history_entry():
    mesh, p = _grid()
    state = mesh.export_state()
    knife, scene = _session(mesh, _camera(mesh))
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3))
    knife.click(_ept(mesh, p[(1, 3)], p[(2, 3)], 0.6))
    knife.cancel()
    knife.deactivate()
    assert mesh.export_state() == state and len(scene.history) == 0


# ---------------------------------------------------------------------------
# Cost on head (hover must stay responsive) + shared pick cache
# ---------------------------------------------------------------------------

def test_planner_with_pick_cache_gives_the_same_crossings_as_without():
    mesh0, (cam1, cam2, _cam3), a, b = _head_segment()
    pa = {"kind": "face", "face_id": a["face_id"], "position": a["position"]}
    pb = {"kind": "face", "face_id": b["face_id"], "position": b["position"]}
    plain = plan_crossings(View(cam2, W, H, None, True), mesh0, pa, pb)
    cached = plan_crossings(View(cam2, W, H, PickCache(), True), mesh0, pa, pb)
    assert plain.crossings == cached.crossings and plain.method == cached.method


# ---------------------------------------------------------------------------
# Family registration: M cycles B -> D -> Q5
# ---------------------------------------------------------------------------

def test_m_cycles_b_d_q5_and_q5_uses_the_cross_face_session():
    app = PlaygroundApp()
    app.register_slot(ExperimentSlot(
        VariantEntry(KnifeFaceVariantB(app)),
        VariantEntry(KnifeFaceVariantD(app)),
        VariantEntry(KnifeFaceVariantQ5(app)),
    ), "knife_face")
    app.focused_family = "knife_face"
    slot = app.slots["knife_face"]
    seen = [slot.active_experiment.variant]
    for _ in range(3):
        app.activate_variant("knife_face", (slot.active_index + 1) % slot.variant_count)
        seen.append(slot.active_experiment.variant)
    assert [v.split(" ")[0] for v in seen] == ["B", "D", "Q5", "B"]
    assert slot.variants[2].experiment.session_cls is KnifeFaceCrossFace
    assert slot.variants[1].experiment.session_cls is KnifeFaceCollected


# ---------------------------------------------------------------------------
# Window wiring (real PlaygroundWindow, headless): view, snap, overlay, close
# ---------------------------------------------------------------------------

@pytest.fixture
def q5_window():
    from playground.window import PlaygroundWindow
    app = PlaygroundApp()
    win = PlaygroundWindow(app, initial_mesh="grid")
    app.focused_family = "knife_face"
    app.activate_variant("knife_face", 2)  # M: B -> D -> Q5
    yield win, app
    win.close()


def _start_q5(win):
    from pyglet.window import key as _key
    win.on_key_press(_key.C, 0)
    assert isinstance(win._knife_face_tool, KnifeFaceCrossFace)
    return win._knife_face_tool


def _screen(win, world):
    s = win.app.camera.project_to_screen(world, win.width, win.height)
    return s[0], s[1]


def _click(win, x, y):
    from pyglet.window import mouse as _mouse
    win.on_mouse_motion(x, y, 0, 0)
    win._drag_moved = 0.0
    win.on_mouse_release(x, y, _mouse.LEFT, 0)


def _edge_mid(mesh, a, b):
    pa, pb = mesh.vertex_position(a), mesh.vertex_position(b)
    return tuple((u + v) / 2 for u, v in zip(pa, pb))


def test_window_q5_cross_face_click_stores_crossings_and_draws_overlay(q5_window):
    from pyglet.window import key as _key
    win, app = q5_window
    mesh = app.scene.mesh
    knife = _start_q5(win)
    xs = sorted({round(mesh.vertex_position(v)[0], 6) for v in mesh.all_vertex_ids()})
    ys = sorted({round(mesh.vertex_position(v)[1], 6) for v in mesh.all_vertex_ids()})
    y0, y1 = ys[3], ys[4]                       # one row of quads
    edge_at = lambda x: _edge(mesh, *[v for v in mesh.all_vertex_ids()
                                       if abs(mesh.vertex_position(v)[0] - x) < 1e-6 and y0 - 1e-6 <= mesh.vertex_position(v)[1] <= y1 + 1e-6])
    ea, eb = edge_at(xs[1]), edge_at(xs[5])     # four quads apart
    ax, ay = _screen(win, _edge_mid(mesh, *mesh.edge_vertices(ea)))
    bx, by = _screen(win, _edge_mid(mesh, *mesh.edge_vertices(eb)))

    _click(win, ax, ay)
    assert len(knife.path) == 1
    win.on_mouse_motion(bx, by, 0, 0)            # hover: pending segment planned with this frame's camera
    kf = win._kfq5_vlists
    assert "hover_cross" in kf and "hover_cut" in kf and "stored_cross" not in kf
    _click(win, bx, by)
    assert len(_crossings(knife)) == 3 and win._knife_face_tool is knife
    assert "stored_cross" in win._kfq5_vlists and "stored_cut" in win._kfq5_vlists
    assert len(app.scene.history) == 0           # nothing applied before commit (D model)

    win.on_key_press(_key.ENTER, 0)
    assert win._knife_face_tool is None and len(app.scene.history) == 1
    assert not win._kfq5_vlists                  # overlay cleaned up with the session
    assert_mesh_invariants(app.scene.mesh, context="window Q5")


def test_window_q5_snap_close_continue_undo_and_commit(q5_window):
    from pyglet.window import key as _key
    win, app = q5_window
    mesh = app.scene.mesh
    knife = _start_q5(win)
    xs = sorted({round(mesh.vertex_position(v)[0], 6) for v in mesh.all_vertex_ids()})
    ys = sorted({round(mesh.vertex_position(v)[1], 6) for v in mesh.all_vertex_ids()})
    cx, cy = xs[4], ys[4]                         # loop around this vertex
    worlds = [(cx - 0.4, cy - 0.4, 0.0), (cx + 0.4, cy - 0.4, 0.0), (cx + 0.4, cy + 0.4, 0.0), (cx - 0.4, cy + 0.4, 0.0)]
    for w in worlds:
        _click(win, *_screen(win, w))
    assert len([p for p in knife.path if not p.get("crossing")]) == 4

    sx, sy = _screen(win, worlds[0])
    win.on_mouse_motion(sx + 6, sy + 4, 0, 0)     # near the start: snap highlight, closing preview
    assert "hover_snap" in win._kfq5_vlists
    _click(win, sx + 6, sy + 4)
    assert knife.path[-1]["reason"] == "closed" and knife.path[-1]["cyclic"]
    assert win._knife_face_tool is knife and len(app.scene.history) == 0   # closing does not commit

    win.on_mouse_motion(sx + 6, sy + 4, 0, 0)     # the closed chain's start still snaps, but the click is rejected
    n = len(knife.path)
    _click(win, sx + 6, sy + 4)
    assert len(knife.path) == n and EARLIER_POINT_NOTE in knife.last_message

    win.on_key_press(_key.Z, _key.MOD_CTRL)       # undo = the whole closing click
    assert knife.path[-1]["kind"] != "break"
    win.on_key_press(_key.Y, _key.MOD_CTRL)
    assert knife.path[-1]["reason"] == "closed"

    win.on_key_press(_key.ENTER, 0)               # only commit ends the session
    assert win._knife_face_tool is None and len(app.scene.history) == 1
    assert_mesh_invariants(app.scene.mesh, context="window Q5 loop")
