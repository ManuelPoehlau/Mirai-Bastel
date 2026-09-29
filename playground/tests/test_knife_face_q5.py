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
from mirai.scene_factory import build_core_scene_from_obj, create_cube  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from mirai.viewport.picking_cache import PickCache  # noqa: E402

from playground._paths import DEFAULT_HEAD_ASSET  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.experiments.knife_face import (  # noqa: E402
    KnifeFaceVariantB,
    KnifeFaceVariantD,
    KnifeFaceVariantQ5,
)
from playground.experiments.knife_face.engine import (  # noqa: E402
    FaceFrame,
    KnifeFaceCollected,
    KnifeFaceImmediate,
    face_problem,
    knife_face_pick,
    segment_in_face,
    split_face_path,
)
from playground.experiments.knife_face.engine_q5 import (  # noqa: E402
    EARLIER_INTERIOR_NOTE,
    SNAP_PX,
    KnifeFaceCrossFace,
)
from playground.experiments.knife_face.planner import View, plan_crossings, point_position  # noqa: E402
from playground.slot import ExperimentSlot, VariantEntry  # noqa: E402
from viewport.derived import triangulate_mesh_face  # noqa: E402

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
    assert knife.path[-2] == {"kind": "break", "reason": "closed", "cyclic": True}  # [-1] is the seed
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
    assert knife.path[-2]["reason"] == "closed" and knife.path[-2]["cyclic"]
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
    assert knife.path[-2]["reason"] == "closed"
    knife.commit()
    assert_mesh_invariants(mesh, context="Q5 vertex-start loop")


def _vertices_at(mesh, pos, tol=1e-6):
    return [v for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), pos) < tol]


def _assert_no_duplicates(mesh):
    """No two vertices at one location, no zero-length edge."""
    ids = list(mesh.all_vertex_ids())
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            assert math.dist(mesh.vertex_position(a), mesh.vertex_position(b)) > 1e-6, (a, b)
    for e in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(e)
        assert math.dist(mesh.vertex_position(va), mesh.vertex_position(vb)) > 1e-6, e


def test_close_seeds_the_next_chain_with_the_closing_vertex_behind_the_break():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    pts = _loop4(cam, mesh)
    for t in pts:
        knife.click(t)
    assert _close_by_click(knife, cam, mesh, pts[0])
    assert knife.path[-2] == {"kind": "break", "reason": "closed", "cyclic": True}
    assert knife.path[-1] is knife.path[0]                  # the very same dict: one point, not a copy
    assert knife.chain == [knife.path[0]]                   # the new chain consists of the seed
    n_closed = len(knife.path)

    # the next click draws a segment that starts at the closing vertex (planner, like any last point)
    far = _ept(mesh, p[(0, 3)], p[(0, 4)], 0.5)
    plan = knife.plan(far)
    assert plan.ok and plan.lines[0][0] == point_position(mesh, pts[0])
    assert knife.click(far)
    assert len(scene.history) == 0                          # still no commit: only Enter ends the session
    assert knife.path[n_closed - 1] is knife.path[0] and len(knife.path) > n_closed + 1
    assert _crossings(knife)                                # the segment crosses faces on its way to the edge

    seed_pos = pts[0]["position"]
    ids_before = set(mesh.all_vertex_ids())
    knife.commit()
    assert "8/8 cut(s) applied" in knife.last_message       # 4 loop cuts + 4 from the seed to the edge
    assert "dropped" not in knife.last_message
    v = _vertices_at(mesh, seed_pos)
    assert len(v) == 1                                      # closing vertex = ONE vertex, loop and continuation share it
    assert len(mesh.vertex_edges(v[0])) == 3                # its two loop edges + the continuation edge
    _assert_no_duplicates(mesh)
    assert_mesh_invariants(mesh, context="Q5 close then continue (interior start)")
    cut = [e for e in knife.path_edges if mesh.is_valid_edge(e)]
    assert len(cut) == 12
    assert not [e for e in cut if set(mesh.edge_vertices(e)) & ids_before]  # still no bridge to an original vertex
    assert len(scene.history) == 1


def test_close_then_commit_at_once_is_unchanged_by_the_seed():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    pts = _loop4(cam, mesh)
    for t in pts:
        knife.click(t)
    assert _close_by_click(knife, cam, mesh, pts[0])
    knife.commit()
    assert knife.last_message == "4/4 cut(s) applied"       # a seed alone is neither a cut nor a note
    assert _sizes(mesh) == {4: 16, 6: 4}
    assert len(_vertices_at(mesh, pts[0]["position"])) == 1
    assert_mesh_invariants(mesh, context="Q5 close, commit at once")


def test_edge_start_close_then_continue_merges_into_one_vertex():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    start = _ept(mesh, p[(1, 2)], p[(2, 2)], 0.2)           # on the edge x=2 between two quads
    for t in (start, _face_at(cam, mesh, (1.4, 1.5, 0.0)),
              _ept(mesh, p[(1, 2)], p[(2, 2)], 0.8), _face_at(cam, mesh, (2.6, 1.5, 0.0))):
        assert knife.click(t)
    px = cam.project_to_screen(point_position(mesh, start), W, H)
    target = knife.snap_target(knife_face_pick(cam, mesh, px[0] + 3.0, px[1], W, H, occlusion=True), px[0] + 3.0, px[1])
    assert knife.click(target) and knife.path[-1] is knife.path[0]
    assert knife.click(_ept(mesh, p[(0, 3)], p[(0, 4)], 0.5))
    start_pos = point_position(mesh, start)
    ids_before = set(mesh.all_vertex_ids())
    knife.commit()
    assert "dropped" not in knife.last_message
    v = _vertices_at(mesh, start_pos)
    assert len(v) == 1 and v[0] not in ids_before           # the edge is split once, not once per occurrence
    assert len(mesh.vertex_edges(v[0])) == 5                # 2 along the split edge + 2 loop + 1 continuation
    _assert_no_duplicates(mesh)
    assert_mesh_invariants(mesh, context="Q5 close then continue (edge start)")
    assert len(scene.history) == 1


def test_vertex_start_close_then_continue_uses_the_existing_vertex():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    v = p[(2, 2)]
    for t in (_vpt(v), _face_at(cam, mesh, (1.5, 1.5, 0.0)), _face_at(cam, mesh, (2.5, 1.5, 0.0)),
              _face_at(cam, mesh, (2.5, 2.5, 0.0))):
        assert knife.click(t)
    assert knife.click(_vpt(v)) and knife.path[-1] is knife.path[0]
    assert knife.click(_ept(mesh, p[(3, 0)], p[(3, 1)], 0.5))
    n_vertices = len(list(mesh.all_vertex_ids()))
    deg = len(mesh.vertex_edges(v))
    knife.commit()
    assert "dropped" not in knife.last_message
    assert _vertices_at(mesh, mesh.vertex_position(v)) == [v]   # no second vertex on the existing one
    assert len(mesh.vertex_edges(v)) == deg + 3                 # loop in/out + the continuation
    assert len(list(mesh.all_vertex_ids())) > n_vertices
    _assert_no_duplicates(mesh)
    assert_mesh_invariants(mesh, context="Q5 close then continue (vertex start)")


def test_close_with_a_skipped_stretch_is_no_loop_and_seeds_from_the_last_point():
    mesh, p = _grid(hole=(1, 2))
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    start = _ept(mesh, p[(1, 1)], p[(2, 1)], 0.5)
    for t in (start, _face_at(cam, mesh, (0.5, 1.5, 0.0)), _face_at(cam, mesh, (0.5, 3.5, 0.0)),
              _face_at(cam, mesh, (2.5, 3.5, 0.0))):
        assert knife.click(t)
    px = cam.project_to_screen(point_position(mesh, start), W, H)
    target = knife.snap_target(knife_face_pick(cam, mesh, px[0] + 3.0, px[1], W, H, occlusion=True), px[0] + 3.0, px[1])
    assert knife.click(target)
    assert knife.path[-2] == {"kind": "break", "reason": "closed", "cyclic": False}   # skipped stretch: no cyclic loop
    assert _breaks(knife, "gap")
    assert knife.path[-1] is knife.path[0]                  # the chain's last point IS the closing vertex here
    assert knife.click(_ept(mesh, p[(3, 3)], p[(3, 4)], 0.5))
    start_pos = point_position(mesh, start)
    knife.commit()
    assert "skipped" in knife.last_message and "dropped" not in knife.last_message
    assert len(_vertices_at(mesh, start_pos)) == 1
    _assert_no_duplicates(mesh)
    assert_mesh_invariants(mesh, context="Q5 open close then continue")
    assert len(scene.history) == 1


def test_continuing_from_the_seed_does_not_connect_across_the_closed_loop():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    pts = _loop4(cam, mesh)
    for t in pts:
        knife.click(t)
    assert _close_by_click(knife, cam, mesh, pts[0])
    n_closed = len(knife.path)
    assert knife.click(_ept(mesh, p[(0, 3)], p[(0, 4)], 0.5))
    # the continuation is its own chain (seed first); the closed chain's entries are untouched
    assert [q["kind"] for q in knife.path[n_closed - 2:n_closed]] == ["break", "face"]
    chains = knife._chains()
    assert [(closed, cyclic, seeded) for _e, closed, cyclic, seeded in chains] == [(True, True, False), (False, False, True)]
    assert chains[1][0][0] is chains[0][0][0]
    knife.commit()
    # 4 loop cuts (cyclic, no edge from the last click to the seed but the closing one) + the continuation only
    assert "8/8 cut(s) applied" in knife.last_message
    assert len([e for e in knife.path_edges if mesh.is_valid_edge(e)]) == 12


def test_random_close_and_continue_sessions_never_duplicate_the_closing_vertex():
    """Grid sessions with closes and continuations (deterministic): invariants hold and the seeded
    start point is never doubled. (Other vertex doublings are a planner matter, not covered here.)"""
    closes = 0
    for seed in range(60):
        rnd = random.Random(seed)
        mesh, p = _grid(5)
        cam = _camera(mesh, yaw=rnd.choice([0, 20, 40]), pitch=rnd.choice([35, 60]))
        knife, _scene = _session(mesh, cam)
        for _ in range(rnd.randint(4, 8)):
            if rnd.random() < 0.5:
                try:
                    t = _face_at(cam, mesh, (rnd.uniform(0.6, 4.4), rnd.uniform(0.6, 4.4), 0.0))
                except AssertionError:
                    continue
            else:
                r, c = rnd.randrange(5), rnd.randrange(4)
                a, b = (p[(r, c)], p[(r, c + 1)]) if rnd.random() < 0.5 else (p[(c, r)], p[(c + 1, r)])
                t = _ept(mesh, a, b, rnd.uniform(0.2, 0.8))
            knife.click(t)
            clicked = knife._clicked()
            if len(clicked) >= 3 and rnd.random() < 0.5:
                sx, sy = cam.project_to_screen(point_position(mesh, clicked[0]), W, H)
                snapped = knife.snap_target(knife_face_pick(cam, mesh, sx + 2, sy + 2, W, H, occlusion=True), sx + 2, sy + 2)
                closes += bool(snapped.get("kind") == "path" and knife.click(snapped))
        starts = [point_position(mesh, next(q for q in entries if q["kind"] != "break"))
                  for entries, _closed, _cyclic, seeded in knife._chains() if seeded]
        knife.commit()
        assert_mesh_invariants(mesh, context=f"Q5 random close/continue {seed}")
        for pos in starts:
            assert len(_vertices_at(mesh, pos)) <= 1, (seed, pos)
    assert closes > 20  # the sessions really do close and continue


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
    assert closed[-1] is closed[0]                   # the seed is part of the closing step
    assert knife.undo_step()
    assert knife.path == before_close                # the whole closing click (crossings + break + seed) is gone
    assert not [q for q in knife.path if q["kind"] == "break"]
    assert knife.redo_step()
    assert knife.path == closed
    assert knife.path[-1] is knife.path[0] and knife.path[-2]["reason"] == "closed"  # redo restores close and seed

    # a click after the close is its own step: undoing it leaves close + seed, the next undo removes both
    assert knife.click(_ept(mesh, p[(0, 3)], p[(0, 4)], 0.5))
    assert knife.undo_step()
    assert knife.path == closed
    assert knife.undo_step()
    assert knife.path == before_close


def test_click_on_a_snapped_earlier_interior_point_is_still_rejected_with_a_note():
    """Task B keeps this sub-case: an interior point has no vertex before commit, and a second run
    through it needs a graph, not a polyline (decision.md, "Task B")."""
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    pts = _loop4(cam, mesh)
    for t in pts:
        knife.click(t)
    n = len(knife.path)
    plan = knife.plan({"kind": "path", "index": 2})   # an interior point that is not the chain start
    assert not plan.ok and plan.reason == EARLIER_INTERIOR_NOTE and plan.snap_position is not None
    assert not knife.click({"kind": "path", "index": 2})
    assert knife.last_message == f"rejected: {EARLIER_INTERIOR_NOTE}"
    assert len(knife.path) == n

    assert _close_by_click(knife, cam, mesh, pts[0])
    assert not knife.click({"kind": "path", "index": 0})   # the closed chain's start is now the seed: the last point
    assert knife.last_message == "rejected: already the last point"


# ---------------------------------------------------------------------------
# Task B (2026-09-29): a click on an earlier cut point connects and continues
# ---------------------------------------------------------------------------

def _index_of(knife, target):
    """Path index of the clicked entry a (vertex / edge) target created."""
    return next(i for i, q in enumerate(knife.path)
                if q["kind"] == target["kind"] and not q.get("crossing")
                and q.get("edge_id") == target.get("edge_id") and q.get("vertex_id") == target.get("vertex_id"))


def _applied(knife):
    import re
    m = re.search(r"(\d+)/(\d+) cut\(s\) applied", knife.last_message)
    assert m, knife.last_message
    return int(m.group(1)), int(m.group(2))


def _earlier_edge_scene():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    pts = {
        "A": _ept(mesh, p[(1, 0)], p[(2, 0)], 0.5),   # (0, 1.5)
        "B": _ept(mesh, p[(1, 2)], p[(2, 2)], 0.5),   # (2, 1.5)
        "C": _ept(mesh, p[(3, 2)], p[(3, 3)], 0.5),   # (2.5, 3)
        "D": _ept(mesh, p[(1, 2)], p[(1, 3)], 0.5),   # (2.5, 1)
        "E": _ept(mesh, p[(0, 2)], p[(0, 3)], 0.5),   # (2.5, 0)
    }
    return mesh, p, cam, knife, scene, pts


def test_click_on_an_earlier_edge_point_connects_and_the_chain_continues_from_it():
    mesh, p, cam, knife, scene, pts = _earlier_edge_scene()
    for name in "ABCD":
        assert knife.click(pts[name])
    b = knife.path[_index_of(knife, pts["B"])]
    n = len(knife.path)

    target = {"kind": "path", "index": _index_of(knife, pts["B"])}
    plan = knife.plan(target)
    assert plan.ok and not plan.closing and "connects to an earlier cut point" in plan.message
    assert plan.lines[0][0] == point_position(mesh, pts["D"]) and plan.lines[-1][1] == point_position(mesh, pts["B"])
    assert knife.click(target)
    assert len(scene.history) == 0                        # still a session step, not a commit
    assert knife.path[-1] is b and len(knife.path) > n    # the very same dict again: one point, not a copy
    assert knife.chain[-1] is b                           # ...and the chain continues from it

    assert knife.click(pts["E"])                          # the next segment starts at B
    assert point_position(mesh, knife.path[-1]) == (2.5, 0.0, 0.0)
    cmd = knife.commit()
    assert cmd is not None and len(scene.history) == 1
    done, total = _applied(knife)
    assert done == total and "dropped" not in knife.last_message and "repeated" not in knife.last_message

    v = _vertices_at(mesh, (2.0, 1.5, 0.0))
    assert len(v) == 1                                    # one merged vertex at the earlier point
    assert len(mesh.vertex_edges(v[0])) == 6              # 2 halves of its split edge + cuts to A-side, C, D, E
    _assert_no_duplicates(mesh)
    assert_mesh_invariants(mesh, context="Q5 earlier edge point")


def test_click_on_an_earlier_existing_vertex_point_connects_and_continues():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    v1 = p[(1, 1)]
    for t in (_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5), _vpt(v1), _ept(mesh, p[(1, 3)], p[(2, 3)], 0.5),
              _ept(mesh, p[(3, 2)], p[(3, 3)], 0.5)):
        assert knife.click(t)
    n_vertices = len(mesh.all_vertex_ids())
    assert knife.plan(_vpt(v1)).ok                        # a picked mesh vertex that is an earlier point of the chain
    assert knife.click(_vpt(v1))
    assert knife.chain[-1] == _vpt(v1)
    assert knife.click(_ept(mesh, p[(0, 3)], p[(0, 4)], 0.5))
    knife.commit()
    done, total = _applied(knife)
    assert done == total
    assert len(_vertices_at(mesh, mesh.vertex_position(v1))) == 1     # no second vertex on the existing one
    assert mesh.is_valid_vertex(v1)
    _assert_no_duplicates(mesh)
    assert_mesh_invariants(mesh, context="Q5 earlier vertex point")
    assert len(mesh.all_vertex_ids()) > n_vertices        # the edge points did become vertices


def test_earlier_point_click_is_one_undo_step_with_its_crossings():
    mesh, p, cam, knife, scene, pts = _earlier_edge_scene()
    for name in "ABCD":
        knife.click(pts[name])
    before = knife.path
    assert knife.click({"kind": "path", "index": _index_of(knife, pts["B"])})
    after = knife.path
    assert len(after) > len(before)
    assert knife.undo_step() and knife.path == before     # the segment with its crossings and the point: one step
    assert knife.redo_step() and knife.path == after
    assert knife.chain[-1] is knife.path[_index_of(knife, pts["B"])]


def test_retracing_a_segment_merges_instead_of_splitting_twice():
    """B -> C, then back to B: same edge crossing again. No double split, no zero-length edge."""
    mesh, p, cam, knife, scene, pts = _earlier_edge_scene()
    for name in "ABC":
        assert knife.click(pts[name])
    assert knife.click({"kind": "path", "index": _index_of(knife, pts["B"])})
    assert knife.click(pts["E"])
    knife.commit()
    assert "repeated segment(s) merged" in knife.last_message
    done, total = _applied(knife)
    assert done == total
    _assert_no_duplicates(mesh)
    assert_mesh_invariants(mesh, context="Q5 retraced segment")


def _diamond(mesh, p):
    return [_ept(mesh, p[(1, 1)], p[(1, 2)], 0.5),        # (1.5, 1)
            _ept(mesh, p[(1, 2)], p[(2, 2)], 0.5),        # (2, 1.5)
            _ept(mesh, p[(2, 1)], p[(2, 2)], 0.5),        # (1.5, 2)
            _ept(mesh, p[(1, 1)], p[(2, 1)], 0.5)]        # (1, 1.5)


def test_click_on_a_point_of_an_already_closed_chain_connects_and_continues():
    """Case (ii): the earlier point lies behind the closing break — attempted and additive."""
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    e1, e2, e3, e4 = _diamond(mesh, p)
    for t in (e1, e2, e3, e4):
        assert knife.click(t)
    assert knife.click({"kind": "path", "index": 0})       # close on the start; the seed is E1 again
    assert knife.path[-2]["reason"] == "closed" and knife.path[-1] is knife.path[0]

    i3 = _index_of(knife, e3)
    plan = knife.plan({"kind": "path", "index": i3})       # E3 belongs to the closed chain
    assert plan.ok and plan.lines[0][0] == point_position(mesh, e1)
    assert knife.click({"kind": "path", "index": i3})
    assert knife.chain[-1] is knife.path[i3]
    assert knife.click(_ept(mesh, p[(3, 1)], p[(3, 2)], 0.5))  # (1.5, 3): from E3 into the quad above
    knife.commit()
    done, total = _applied(knife)
    assert done == total and "dropped" not in knife.last_message
    for pos in ((1.5, 1.0, 0.0), (2.0, 1.5, 0.0), (1.5, 2.0, 0.0), (1.0, 1.5, 0.0)):
        assert len(_vertices_at(mesh, pos)) == 1
    assert len(mesh.all_face_ids()) == 16 + 4 + 1 + 1     # 4 corner triangles + diamond, diamond split, quad above split
    _assert_no_duplicates(mesh)
    assert_mesh_invariants(mesh, context="Q5 earlier point behind a closed chain")


def test_click_on_an_earlier_point_of_a_closed_chain_next_to_the_seed_merges_the_loop_edge():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    e1, e2, e3, e4 = _diamond(mesh, p)
    for t in (e1, e2, e3, e4):
        knife.click(t)
    knife.click({"kind": "path", "index": 0})
    assert knife.click({"kind": "path", "index": _index_of(knife, e2)})   # E1 -> E2 is a loop edge already
    knife.commit()
    assert "1 repeated segment(s) merged" in knife.last_message
    assert len(mesh.all_face_ids()) == 16 + 4
    assert_mesh_invariants(mesh, context="Q5 loop edge retraced")


def test_start_of_the_chain_still_closes_after_an_earlier_point_click():
    mesh, p, cam, knife, scene, pts = _earlier_edge_scene()
    for name in "ABCD":
        knife.click(pts[name])
    assert knife.click({"kind": "path", "index": _index_of(knife, pts["B"])})
    plan = knife.plan({"kind": "path", "index": 0})
    assert plan.ok and plan.closing                       # A is the chain start: sealing stays the special case
    assert knife.click({"kind": "path", "index": 0})
    assert knife.path[-2]["reason"] == "closed"
    knife.commit()
    assert_mesh_invariants(mesh, context="Q5 close after an earlier point")
    _assert_no_duplicates(mesh)


def test_the_last_point_and_planner_crossings_are_not_earlier_points():
    mesh, p, cam, knife, scene, pts = _earlier_edge_scene()
    for name in "AB":
        knife.click(pts[name])
    plan = knife.plan({"kind": "path", "index": _index_of(knife, pts["B"])})
    assert not plan.ok and plan.reason == "already the last point"
    crossing_index = next(i for i, q in enumerate(knife.path) if q.get("crossing"))
    # a crossing is never offered as a snap target:
    world = point_position(mesh, knife.path[crossing_index])
    sx, sy = cam.project_to_screen(world, W, H)
    target = knife.snap_target(knife_face_pick(cam, mesh, sx, sy, W, H, occlusion=True), sx, sy)
    assert target.get("kind") != "path"


def test_random_sessions_with_earlier_point_clicks_commit_cleanly():
    """60 random edge-point sessions (3-8 steps, about half of them earlier-point clicks): commit never raises,
    invariants hold and no point that was clicked twice ends up as two vertices."""
    for seed in range(60):
        rnd = random.Random(seed)
        mesh, p = _grid()
        cam = _camera(mesh, yaw=rnd.choice([0.0, 20.0, -30.0]), pitch=rnd.choice([35.0, 60.0]))
        knife, scene = _session(mesh, cam)
        eids = list(mesh.all_edge_ids())
        for step in range(rnd.randint(3, 8)):
            last = knife.chain[-1] if knife.chain else None
            earlier = [i for i, q in enumerate(knife.path)
                       if q["kind"] in ("edge", "vertex") and not q.get("crossing") and q is not last]
            if step >= 2 and earlier and rnd.random() < 0.5:
                knife.click({"kind": "path", "index": rnd.choice(earlier)})
                continue
            for _ in range(20):
                e = rnd.choice(eids)
                if mesh.is_valid_edge(e) and knife.click({"kind": "edge", "edge_id": e, "t": rnd.uniform(0.2, 0.8)}):
                    break
        knife.commit()
        assert_mesh_invariants(mesh, context=f"Q5 earlier-point stress seed {seed}")
        positions = collections.Counter(tuple(round(c, 6) for c in mesh.vertex_position(v)) for v in mesh.all_vertex_ids())
        # A doubled vertex on an *original* grid vertex is the planner's t = 0 case (decision.md, close-and-continue
        # stress) and happens without any earlier-point click; a doubled non-grid position would be this feature.
        assert not [k for k, c in positions.items() if c > 1 and not all(abs(x - round(x)) < 1e-6 for x in k)], seed


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


def test_loop_inside_one_face_is_independent_of_click_order_and_direction():
    """Task A (2026-09-29): same bridges, same faces, parent's winding — for every start and direction,
    closed by clicking the start (Q5 subclasses D's resolver)."""
    k = 5
    centre = (1.5, 1.5)
    loop = [(centre[0] + 0.25 * math.cos(2 * math.pi * i / k), centre[1] + 0.25 * math.sin(2 * math.pi * i / k), 0.0)
            for i in range(k)]
    results = set()
    for seq in (loop, loop[::-1]):
        for s in range(k):
            clicks = seq[s:] + seq[:s]
            mesh, p = _grid()
            cam = _camera(mesh, yaw=0.0, pitch=0.0)
            knife, scene = _session(mesh, cam)
            orig = set(mesh.all_vertex_ids())
            targets = [_face_at(cam, mesh, w) for w in clicks]
            for t in targets:
                assert knife.click(t)
            assert _close_by_click(knife, cam, mesh, targets[0])
            assert knife.commit() is not None
            assert "2 bridges" in knife.last_message
            assert_mesh_invariants(mesh, context="Q5 in-face loop order")
            assert len(mesh.all_face_ids()) == 16 + 2

            for f in mesh.all_face_ids():
                pts = [mesh.vertex_position(v) for v in mesh.face_vertices(f)]
                assert sum((a[0] * b[1] - b[0] * a[1]) for a, b in zip(pts, pts[1:] + pts[:1])) > 0  # CCW like the grid
            seqs = set()
            for f in mesh.all_face_ids():
                pts = [tuple(round(c, 4) + 0.0 for c in mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
                i = min(range(len(pts)), key=lambda j: pts[j])
                seqs.add(tuple(pts[i:] + pts[:i]))
            results.add(frozenset(seqs))
    assert len(results) == 1


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
# Geometric integrity (decision.md "Q5 integrity findings (2026-09-29)"; probe:
# experiments/topology/knife_integrity_probe.py). Minimal reproductions of every defect
# class, the commit safety net, and seeded random sessions on grid and cube.
# ---------------------------------------------------------------------------

GRID_PLANES = [(2, 0.0, 1.0, 16.0)]
CUBE_PLANES = [(a, s, s, 4.0) for a in range(3) for s in (-1.0, 1.0)]


def _newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def _tri_area(a, b, c):
    u = [b[k] - a[k] for k in range(3)]
    v = [c[k] - a[k] for k in range(3)]
    return 0.5 * math.sqrt((u[1] * v[2] - u[2] * v[1]) ** 2 + (u[2] * v[0] - u[0] * v[2]) ** 2
                           + (u[0] * v[1] - u[1] * v[0]) ** 2)


def assert_geometric_integrity(mesh, planes=None, *, context=""):
    """What `assert_mesh_invariants` does not see: every face a simple polygon with area whose
    triangulation covers exactly its area (overlapping triangles = the Artist's "hatching"), no
    edge without a face, every edge walked in opposite directions by its two faces; on planar
    reference surfaces (`planes`: (axis, value, outward sign, area)) every face lies in one
    plane, faces outward, and the faces of each plane add up to its area (no overlap, no gap)."""
    assert_mesh_invariants(mesh, context=context)
    directed = collections.Counter()
    sums = [0.0] * len(planes or [])
    for fid in mesh.all_face_ids():
        problem = face_problem(mesh, fid)
        assert problem is None, f"{context}: face {fid!r} would {problem}"
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        area = 0.5 * math.sqrt(sum(c * c for c in _newell(pts)))
        tri = sum(_tri_area(*(mesh.vertex_position(v) for v in t)) for t in triangulate_mesh_face(mesh, fid))
        assert abs(tri - area) <= 1e-6 * max(1.0, area), f"{context}: face {fid!r} triangles {tri} != area {area}"
        b = mesh.face_vertices(fid)
        for i in range(len(b)):
            directed[(b[i], b[(i + 1) % len(b)])] += 1
        if planes:
            k = next((k for k, (ax, val, _s, _a) in enumerate(planes)
                      if all(abs(p[ax] - val) <= 1e-6 for p in pts)), None)
            assert k is not None, f"{context}: face {fid!r} lies in no reference plane"
            ax, _val, sign, _area = planes[k]
            signed = 0.5 * _newell(pts)[ax] * sign
            assert signed > 0.0, f"{context}: face {fid!r} is flipped"
            sums[k] += signed
    assert max(directed.values(), default=1) == 1, f"{context}: inconsistent winding"
    assert all(mesh.edge_faces(e) for e in mesh.all_edge_ids()), f"{context}: edge without a face"
    for k, total in enumerate(sums):
        assert abs(total - planes[k][3]) <= 1e-6, f"{context}: plane {planes[k][:3]} covered {total}"


def _vid_at(mesh, pos):
    return next(v for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), pos) < 1e-9)


def _spec(mesh, spec):
    """("v", pos) vertex, ("e", pos_a, pos_b, t) the point a + t (b - a) on whichever current edge
    holds it, ("f", pos) the face interior holding pos (a face-interior click)."""
    kind = spec[0]
    if kind == "v":
        return _vpt(_vid_at(mesh, spec[1]))
    if kind == "e":
        a, b, t = spec[1], spec[2], spec[3]
        pos = tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
        for eid in mesh.all_edge_ids():
            p0, p1 = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
            d = [p1[k] - p0[k] for k in range(3)]
            u = sum((pos[k] - p0[k]) * d[k] for k in range(3)) / sum(c * c for c in d)
            if 1e-9 < u < 1 - 1e-9 and math.dist(pos, tuple(p0[k] + u * d[k] for k in range(3))) < 1e-9:
                return {"kind": "edge", "edge_id": eid, "t": u}
        raise LookupError(pos)
    pos = spec[1]
    for fid in mesh.all_face_ids():
        fr = FaceFrame(mesh, fid)
        if fr.height(pos) > 1e-9:
            continue
        if segment_in_face(mesh, fid, pos, pos) == "inside":
            return {"kind": "face", "face_id": fid, "position": tuple(pos), "distance_px": 20.0}
    raise LookupError(pos)


def _play(cls, mesh, specs, cam=None):
    knife, scene = _session(mesh, cam, cls=cls)
    accepted = [knife.click(_spec(mesh, sp)) for sp in specs]
    cmd = knife.commit()
    knife.deactivate()
    return knife, scene, cmd, accepted


def _vertices_at(mesh, pos):
    return [v for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), pos) < 1e-9]


def _seg_x(p, q, r, s):
    """Intersection of the 2D lines pq and rs (x, y)."""
    d = (q[0] - p[0]) * (s[1] - r[1]) - (q[1] - p[1]) * (s[0] - r[0])
    t = ((r[0] - p[0]) * (s[1] - r[1]) - (r[1] - p[1]) * (s[0] - r[0])) / d
    return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), 0.0)


# HB1: the last chord crosses the notch's first segment inside quad (0,0).
HB1 = [("e", (0, 0, 0), (1, 0, 0), 0.2), ("f", (0.8, 0.5, 0)), ("e", (0, 0, 0), (1, 0, 0), 0.6),
       ("e", (0, 1, 0), (1, 1, 0), 0.5)]
HB1_X = _seg_x((0.2, 0.0), (0.8, 0.5), (0.6, 0.0), (0.5, 1.0))


@pytest.mark.parametrize("cls", [KnifeFaceCrossFace, KnifeFaceCollected])
def test_crossing_cut_gets_one_intersection_vertex_and_both_cuts_apply(cls):
    """H-b / Artist decision 2026-09-29 ("like Blender"): the crossing is one vertex of both cuts."""
    mesh, _p = _grid()
    before = mesh.export_state()
    knife, scene, cmd, accepted = _play(cls, mesh, HB1)
    assert all(accepted) and cmd is not None
    assert "2/2 cut(s) applied" in knife.last_message
    assert_geometric_integrity(mesh, GRID_PLANES, context=f"{cls.__name__} HB1")
    xs = _vertices_at(mesh, HB1_X)
    assert len(xs) == 1                                     # one vertex, no duplicate
    assert len(mesh.vertex_edges(xs[0])) == 4               # on both cuts: four cut edges meet there
    assert len(scene.history) == 1
    scene.history.undo()
    assert mesh.export_state()["faces"] == before["faces"]


def test_bent_runs_crossing_each_other_both_apply():
    """H-b with interior points on both runs (Q5 only: D/B refuse the click by their A5 lock)."""
    mesh, _p = _grid()
    specs = [("e", (0, 0, 0), (0, 1, 0), 0.5), ("f", (0.5, 0.8, 0)), ("e", (1, 0, 0), (1, 1, 0), 0.5),
             ("f", (0.2, 0.9, 0)), ("e", (0, 1, 0), (1, 1, 0), 0.2)]
    knife, _scene, cmd, accepted = _play(KnifeFaceCrossFace, mesh, specs, _camera(mesh, 0.0, 0.0))
    assert all(accepted) and cmd is not None and "2/2 cut(s) applied" in knife.last_message
    assert_geometric_integrity(mesh, GRID_PLANES, context="HB2")
    assert len(_vertices_at(mesh, _seg_x((1.0, 0.5), (0.2, 0.9), (0.0, 0.5), (0.5, 0.8)))) == 1


@pytest.mark.parametrize("cls", [KnifeFaceCrossFace, KnifeFaceCollected])
def test_notch_on_a_shared_edge_stays_in_its_split_quad(cls):
    """H-a (R2): the notch's quad is split by earlier runs of the same commit; both notch ends
    also lie on the quad below. Before: the notch was built into the quad below (flipped)."""
    mesh, p = _grid()
    below = next(f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) == {p[(0, 1)], p[(0, 2)], p[(1, 2)], p[(1, 1)]})
    specs = [("e", (1, 1, 0), (1, 2, 0), 0.5), ("e", (2, 1, 0), (2, 2, 0), 0.5), ("e", (1, 1, 0), (2, 1, 0), 0.7),
             ("f", (1.5, 1.3, 0)), ("e", (1, 1, 0), (2, 1, 0), 0.3)]
    knife, _scene, cmd, accepted = _play(cls, mesh, specs)
    assert all(accepted) and cmd is not None and "3/3 cut(s) applied" in knife.last_message
    assert_geometric_integrity(mesh, GRID_PLANES, context=f"{cls.__name__} HA1")
    (inner,) = _vertices_at(mesh, (1.5, 1.3, 0.0))
    faces = {f for e in mesh.vertex_edges(inner) for f in mesh.edge_faces(e)}
    assert all(min(mesh.vertex_position(v)[1] for v in mesh.face_vertices(f)) >= 1.0 - 1e-9 for f in faces)
    assert all(mesh.vertex_position(v)[1] <= 1.0 + 1e-9 for v in mesh.face_vertices(below))


def test_cube_notch_on_a_fold_edge_stays_on_the_top_side():
    """H-a at a fold (what the Artist saw on the cube): both notch ends on the top/right edge."""
    mesh = create_cube()
    specs = [("e", (-1, 1, 1), (1, 1, 1), 0.6), ("e", (1, 1, 1), (1, 1, -1), 0.4), ("f", (0.6, 1, -0.3)),
             ("e", (1, 1, 1), (1, 1, -1), 0.75)]
    knife, _scene, cmd, accepted = _play(KnifeFaceCrossFace, mesh, specs, _camera(mesh, 35.0, 30.0))
    assert all(accepted) and cmd is not None and "2/2 cut(s) applied" in knife.last_message
    assert_geometric_integrity(mesh, CUBE_PLANES, context="HA2")


def test_straight_segment_along_a_split_boundary_line_is_skipped():
    """R3: v(1,1) -> a point on the far piece of the same (already split) edge runs along the
    boundary — nothing to cut, like an existing edge. Before: a zero-area face."""
    mesh, _p = _grid()
    _play(KnifeFaceCrossFace, mesh, [("e", (1, 1, 0), (2, 1, 0), 0.5), ("e", (1, 2, 0), (2, 2, 0), 0.5)])
    before = mesh.export_state()["faces"]
    knife, scene = _session(mesh, _camera(mesh))
    assert knife.click(_spec(mesh, ("v", (1, 1, 0))))
    assert knife.click(_spec(mesh, ("e", (1.5, 1, 0), (2, 1, 0), 0.5)))
    assert _breaks(knife, "edge")
    knife.commit()
    knife.deactivate()
    assert mesh.export_state()["faces"] == before and len(scene.history) == 0
    assert_geometric_integrity(mesh, GRID_PLANES, context="R3 Q5")
    # D (no planner) walks along the boundary at commit: nothing is cut either.
    knife, scene, _cmd, _acc = _play(KnifeFaceCollected, mesh, [("v", (1, 1, 0)), ("e", (1.5, 1, 0), (2, 1, 0), 0.5)])
    assert_geometric_integrity(mesh, GRID_PLANES, context="R3 D")


def test_plane_planner_reports_a_vertex_hit_not_an_edge_end():
    """R4 (the open "t = 0" point): a line along a grid row through (2,3); PLANE used to report
    an edge hit at t ~ 1e-15 there, which became a second vertex on top of (2,3)."""
    mesh, p = _grid()
    cam = _camera(mesh, 0.0, 0.0)
    a, b = _vpt(p[(3, 3)]), _ept(mesh, p[(3, 1)], p[(3, 2)], 0.514)
    res = plan_crossings(View(cam, W, H, None, True), mesh, a, b)
    assert all(c["kind"] == "vertex" or 1e-9 < c["t"] < 1 - 1e-9 for c in res.crossings)
    assert {"kind": "vertex", "vertex_id": p[(3, 2)]} in res.crossings
    before = mesh.export_state()["faces"]
    knife, _scene, _cmd, _acc = _play(KnifeFaceCrossFace, mesh, [("v", (3, 3, 0)), ("e", (1, 3, 0), (2, 3, 0), 0.514)], cam)
    assert mesh.export_state()["faces"] == before              # all along existing edges: nothing cut
    assert_geometric_integrity(mesh, GRID_PLANES, context="R4")


def test_straight_line_out_of_a_concave_face_is_planned_across_faces():
    """R5: after an L cut the big piece is concave; a straight line between two of its points
    leaves it. Q5 plans it like any cross-face segment (both faces cut) instead of one chord."""
    mesh, _p = _grid()
    cam = _camera(mesh, 0.0, 0.0)
    _play(KnifeFaceCrossFace, mesh, [("e", (0, 0, 0), (1, 0, 0), 0.5), ("f", (0.5, 0.5, 0)),
                                     ("e", (0, 0, 0), (0, 1, 0), 0.5)], cam)
    knife, _scene, cmd, accepted = _play(KnifeFaceCrossFace, mesh, [("e", (0.5, 0, 0), (1, 0, 0), 0.6),
                                                                    ("e", (0, 0.5, 0), (0, 1, 0), 0.6)], cam)
    assert all(accepted) and cmd is not None
    assert "3/3 cut(s) applied" in knife.last_message
    assert_geometric_integrity(mesh, GRID_PLANES, context="R5")


@pytest.mark.parametrize("cls", [KnifeFaceCrossFace, KnifeFaceCollected])
def test_a_run_crossing_itself_is_dropped_with_a_note_and_the_rest_applies(cls):
    """A run that crosses itself inside one face would enclose a loop touching the rest at one
    vertex only — not representable yet (open point): that run is dropped, named in the HUD."""
    mesh, _p = _grid()
    specs = [("e", (1, 0, 0), (1, 1, 0), 0.3), ("f", (0.3, 0.4, 0)), ("f", (0.5, 0.8, 0)), ("f", (0.5, 0.1, 0)),
             ("e", (0, 0, 0), (1, 0, 0), 0.7), ("e", (0, 0, 0), (0, 1, 0), 0.5)]
    knife, _scene, cmd, accepted = _play(cls, mesh, specs)
    assert all(accepted) and cmd is not None
    assert "1/2 cut(s) applied" in knife.last_message
    assert "1 cut(s) closing a loop at a single point dropped" in knife.last_message
    assert_geometric_integrity(mesh, GRID_PLANES, context=f"{cls.__name__} self-crossing")


def test_commit_rolls_back_broken_geometry_and_names_the_reason():
    """Safety net: B cuts at every click through `connect_in_shared_face` (lowest face id, no
    geometric check) — HB1 there leaves a face crossing itself. The whole session is taken back,
    History gets nothing, the HUD says why."""
    mesh, _p = _grid()
    before = mesh.export_state()
    knife, scene, cmd, accepted = _play(KnifeFaceImmediate, mesh, HB1)
    assert all(accepted) and cmd is None and len(scene.history) == 0
    assert knife.last_message == "commit rolled back — a face would cross itself; mesh unchanged"
    assert mesh.export_state()["faces"] == before["faces"]
    assert_geometric_integrity(mesh, GRID_PLANES, context="rollback")


def test_commit_check_catches_a_face_flipped_against_its_neighbour():
    """The pre-fix R2 result, built by hand: the notch inside the quad *below* its own. It passes
    the invariant catalogue; the commit check refuses it."""
    mesh, p = _grid()
    knife, scene = _session(mesh, None, cls=KnifeFaceCollected)
    below = next(f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) == {p[(0, 1)], p[(0, 2)], p[(1, 2)], p[(1, 1)]})
    e = _edge(mesh, p[(1, 1)], p[(1, 2)])
    v1, _ea, eb = mesh.split_edge(e, 0.3 if mesh.edge_vertices(e)[0] == p[(1, 1)] else 0.7)
    v2 = mesh.split_edge(eb, 0.5)[0]
    split_face_path(mesh, below, v1, v2, [(1.5, 1.3, 0.0)])
    assert_mesh_invariants(mesh, context="hand-built flipped notch")
    assert knife.commit() is None and len(scene.history) == 0
    assert knife.last_message.startswith("commit rolled back — a face would")
    assert_geometric_integrity(mesh, GRID_PLANES, context="flipped rolled back")


def test_hover_and_stored_preview_show_the_intersection_with_an_earlier_cut():
    mesh, _p = _grid()
    knife, _scene = _session(mesh, _camera(mesh))
    for sp in HB1[:3]:
        assert knife.click(_spec(mesh, sp))
    plan = knife.plan(_spec(mesh, HB1[3]))
    assert plan.ok and "1 intersection(s) with earlier cuts" in plan.message
    assert any(math.dist(c, HB1_X) < 1e-9 for c in plan.crossings)
    assert knife.click(_spec(mesh, HB1[3]))
    assert any(math.dist(c, HB1_X) < 1e-9 for c in knife.preview_stored()["crossings"])
    assert knife.undo_step() and not any(math.dist(c, HB1_X) < 1e-9 for c in knife.preview_stored()["crossings"])
    assert knife.redo_step()
    assert knife.commit() is not None
    knife.deactivate()
    assert len(_vertices_at(mesh, HB1_X)) == 1


def _random_sessions(scene_name, cls, runs, seed0=0):
    """Seeded random sessions like the probe's (smaller): screen positions aimed at face interiors,
    vertices and edge points of the current mesh, picked and snapped as the window does."""
    from mirai.scene_factory import create_cube as _cube
    failures = []
    for seed in range(seed0, seed0 + runs):
        rnd = random.Random(seed)
        mesh = _grid()[0] if scene_name == "grid" else _cube()
        planes = GRID_PLANES if scene_name == "grid" else CUBE_PLANES
        cams = [_camera(mesh, y, pt) for y, pt in (((20, 35), (0, 0), (-30, 60), (45, 25)) if scene_name == "grid"
                                                   else ((35, 30), (-40, 25), (130, -30), (60, 55)))]
        for _session_no in range(rnd.randint(1, 3)):
            knife, _scene = _session(mesh, None, cls=cls)
            for _ in range(rnd.randint(2, 9)):
                cam = rnd.choice(cams)
                r = rnd.random()
                if r < 0.45:
                    fid = rnd.choice(mesh.all_face_ids())
                    tri = rnd.choice(triangulate_mesh_face(mesh, fid))
                    u, v = rnd.random(), rnd.random()
                    if u + v > 1:
                        u, v = 1 - u, 1 - v
                    a, b, c = (mesh.vertex_position(x) for x in tri)
                    world = tuple(a[k] + u * (b[k] - a[k]) + v * (c[k] - a[k]) for k in range(3))
                elif r < 0.6:
                    world = mesh.vertex_position(rnd.choice(mesh.all_vertex_ids()))
                else:
                    va, vb = mesh.edge_vertices(rnd.choice(mesh.all_edge_ids()))
                    t = rnd.uniform(0.1, 0.9)
                    pa, pb = mesh.vertex_position(va), mesh.vertex_position(vb)
                    world = tuple(pa[k] + t * (pb[k] - pa[k]) for k in range(3))
                sp = cam.project_to_screen(world, W, H)
                if sp is None:
                    continue
                sx, sy = sp[0] + rnd.uniform(-2, 2) * (r >= 0.45), sp[1] + rnd.uniform(-2, 2) * (r >= 0.45)
                target = knife_face_pick(cam, mesh, sx, sy, W, H, occlusion=True)
                if hasattr(knife, "set_view"):
                    knife.set_view(cam, W, H, occlusion=True)
                    target = knife.snap_target(target, sx, sy)
                knife.click(target)
            knife.commit()
            knife.deactivate()
            try:
                assert_geometric_integrity(mesh, planes, context=f"{scene_name} seed {seed}")
            except AssertionError as exc:
                failures.append(str(exc))
                break
            if "rolled back" in knife.last_message:
                failures.append(f"{scene_name} seed {seed}: {knife.last_message}")
    return failures


@pytest.mark.parametrize("scene_name", ["grid", "cube"])
def test_random_q5_sessions_keep_the_geometry_sound(scene_name):
    """80 seeded runs (1-3 sessions of 2-9 clicks each): no integrity failure and no rollback
    (the resolver itself stays sound). The probe runs the same with 400."""
    assert _random_sessions(scene_name, KnifeFaceCrossFace, 80) == []


@pytest.mark.parametrize("scene_name", ["grid", "cube"])
def test_random_d_sessions_keep_the_geometry_sound(scene_name):
    assert _random_sessions(scene_name, KnifeFaceCollected, 60) == []


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
    assert knife.path[-2]["reason"] == "closed" and knife.path[-2]["cyclic"]
    assert win._knife_face_tool is knife and len(app.scene.history) == 0   # closing does not commit

    win.on_mouse_motion(sx + 6, sy + 4, 0, 0)     # the closed chain's start still snaps, but the click is rejected
    n = len(knife.path)
    _click(win, sx + 6, sy + 4)
    assert len(knife.path) == n and "already the last point" in knife.last_message

    win.on_key_press(_key.Z, _key.MOD_CTRL)       # undo = the whole closing click
    assert knife.path[-1]["kind"] != "break"
    win.on_key_press(_key.Y, _key.MOD_CTRL)
    assert knife.path[-2]["reason"] == "closed"

    win.on_key_press(_key.ENTER, 0)               # only commit ends the session
    assert win._knife_face_tool is None and len(app.scene.history) == 1
    assert_mesh_invariants(app.scene.mesh, context="window Q5 loop")


def test_window_q5_click_on_an_earlier_edge_point_connects_and_continues(q5_window):
    from pyglet.window import key as _key
    win, app = q5_window
    mesh = app.scene.mesh
    knife = _start_q5(win)
    xs = sorted({round(mesh.vertex_position(v)[0], 6) for v in mesh.all_vertex_ids()})
    ys = sorted({round(mesh.vertex_position(v)[1], 6) for v in mesh.all_vertex_ids()})
    at = {tuple(round(c, 6) for c in mesh.vertex_position(v)[:2]): v for v in mesh.all_vertex_ids()}

    def mid(c0, r0, c1, r1):
        return _edge_mid(mesh, at[(xs[c0], ys[r0])], at[(xs[c1], ys[r1])])

    a, b = mid(1, 3, 1, 4), mid(3, 3, 3, 4)
    c, d, e = mid(3, 5, 4, 5), mid(3, 3, 4, 3), mid(3, 1, 4, 1)
    for w in (a, b, c, d):
        _click(win, *_screen(win, w))
    assert len([q for q in knife.path if not q.get("crossing")]) == 4
    b_entry = next(q for q in knife.path if q["kind"] == "edge" and not q.get("crossing")
                   and math.dist(point_position(mesh, q), b) < 1e-6)

    bx, by = _screen(win, b)
    win.on_mouse_motion(bx + 4, by + 3, 0, 0)               # near an earlier point: the snap shows
    assert "hover_snap" in win._kfq5_vlists
    n = len(knife.path)
    _click(win, bx + 4, by + 3)
    assert len(knife.path) > n and knife.chain[-1] is b_entry   # accepted; the chain continues from B
    assert "earlier cut point" in knife.last_message and "rejected" not in knife.last_message

    _click(win, *_screen(win, e))                              # the next segment starts at B
    assert point_position(mesh, knife.path[-1]) != point_position(mesh, b_entry)
    win.on_key_press(_key.Z, _key.MOD_CTRL)                    # undo: just the last click
    assert knife.chain[-1] is b_entry
    win.on_key_press(_key.Z, _key.MOD_CTRL)                    # undo: the earlier-point click, crossings included
    assert len(knife.path) == n
    win.on_key_press(_key.Y, _key.MOD_CTRL)
    win.on_key_press(_key.Y, _key.MOD_CTRL)
    win.on_key_press(_key.ENTER, 0)
    assert win._knife_face_tool is None and len(app.scene.history) == 1
    assert len([v for v in app.scene.mesh.all_vertex_ids()
                if math.dist(app.scene.mesh.vertex_position(v), b) < 1e-6]) == 1
    assert_mesh_invariants(app.scene.mesh, context="window Q5 earlier point")


def test_window_q5_after_close_the_preview_and_the_click_start_at_the_closing_vertex(q5_window):
    from pyglet.window import key as _key
    win, app = q5_window
    mesh = app.scene.mesh
    knife = _start_q5(win)
    xs = sorted({round(mesh.vertex_position(v)[0], 6) for v in mesh.all_vertex_ids()})
    ys = sorted({round(mesh.vertex_position(v)[1], 6) for v in mesh.all_vertex_ids()})
    cx, cy = xs[4], ys[4]
    worlds = [(cx - 0.4, cy - 0.4, 0.0), (cx + 0.4, cy - 0.4, 0.0), (cx + 0.4, cy + 0.4, 0.0), (cx - 0.4, cy + 0.4, 0.0)]
    for w in worlds:
        _click(win, *_screen(win, w))
    sx, sy = _screen(win, worlds[0])
    _click(win, sx + 6, sy + 4)                     # snap onto the start: closes, seeds
    assert knife.path[-2]["reason"] == "closed" and knife.path[-1] is knife.path[0]
    assert len(win.app.scene.history) == 0 and win._knife_face_tool is knife

    a, b = (v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) in ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    tx, ty = _screen(win, _edge_mid(mesh, a, b))
    win.on_mouse_motion(tx, ty, 0, 0)               # hover: the pending segment runs from the closing vertex
    plan = knife.last_plan
    assert plan.ok and plan.lines[0][0] == pytest.approx(worlds[0])
    assert "hover_cut" in win._kfq5_vlists
    n = len(knife.path)
    _click(win, tx, ty)
    assert len(knife.path) > n and knife.path[n] is not knife.path[0]

    win.on_key_press(_key.ENTER, 0)
    assert win._knife_face_tool is None and len(app.scene.history) == 1
    assert_mesh_invariants(app.scene.mesh, context="window Q5 close then continue")
