"""`KnifeTool` across faces and points in space (WP-KNIFE-01 S4, PROVISIONAL) — headless, with a camera view.

Production counterparts of the Lab's Q5 cross-face tests (`playground/tests/test_knife_face_q5.py`, the
spec: the planner moves to `src`, *what* is cut stays Q5's) and the absolute spec of the points in space
(Manu, 2026-10-02: a click outside the mesh inside a session is a point and cuts — Blender; there is no Lab
oracle for them). The tool gets its camera through `set_view` (Application: the live camera at hover and
click time); without a view a segment across faces stays refused (S2 of the handoff). Defaults S1–S5 /
S4a–d: decision.md "WP-KNIFE-01 S4".
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, Scene
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.scene_factory import create_cube
from mirai.topology.knife import CROSS_FACE, KnifeTool
from mirai.topology.knife_pick import knife_pick
from mirai.topology.knife_preview import target_position
from mirai.viewport.camera import OrbitCamera
from tests.mesh_invariants import assert_mesh_invariants

W, H = 1280, 800
XFAIL = pytest.mark.xfail(strict=True, reason="WP-KNIFE-01 S4: not built yet")


# -- fixtures -------------------------------------------------------------------------------------------


def _grid(n: int = 4, hole=None, occluder: bool = False):
    """n x n quads in z = 0, quad (c, r) = [c, c+1] x [r, r+1]; `hole` leaves a quad out; `occluder` adds a
    small quad in front hiding the x = 2 crossing of a y = 1.5 line seen from the front."""
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            if (c, r) != hole:
                mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    if occluder:
        mesh.add_face([mesh.add_vertex(q) for q in ((1.6, 1.2, 0.6), (2.4, 1.2, 0.6), (2.4, 1.8, 0.6), (1.6, 1.8, 0.6))])
    return mesh, p


def _camera(mesh, yaw=20.0, pitch=35.0) -> OrbitCamera:
    cam = OrbitCamera(yaw=math.radians(yaw), pitch=math.radians(pitch))
    center, radius = mesh_center_and_radius(mesh)
    cam.frame_on_bounds(center, radius, margin=1.4)
    return cam


def _session(mesh, cam, *, occlusion=True, cache=None):
    scene = Scene()
    scene.mesh = mesh
    knife = KnifeTool()
    knife.activate()
    knife.begin(mesh=mesh, scene=scene, selection=scene.selection)
    if cam is not None:
        knife.set_view(cam, W, H, cache=cache, occlusion=occlusion)
    return knife, scene


def _edge(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


def _ept(mesh, a, b, t_from_a):
    eid = _edge(mesh, a, b)
    t = t_from_a if mesh.edge_vertices(eid)[0] == a else 1.0 - t_from_a
    return {"kind": "edge", "edge_id": eid, "t": t}


def _vpt(vid):
    return {"kind": "vertex", "vertex_id": vid}


def _face_at(cam, mesh, world):
    s = cam.project_to_screen(world, W, H)
    target = knife_pick(cam, mesh, s[0], s[1], W, H, occlusion=True)
    assert target["kind"] == "face", target
    return target


def _crossings(knife):
    return [p for p in knife.path if p.get("crossing")]


def _breaks(knife, reason=None):
    return [p for p in knife.path if p["kind"] == "break" and (reason is None or p.get("reason") == reason)]


def _vef(mesh):
    return (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids()))


def _faces(mesh):
    """Position-canonical faces (id-free)."""
    out = []
    for f in mesh.all_face_ids():
        cyc = [tuple(round(c, 9) + 0.0 for c in mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
        k = cyc.index(min(cyc))
        out.append(tuple(cyc[k:] + cyc[:k]))
    return sorted(out)


def _content(state):
    return {k: v for k, v in state.items() if not k.endswith("_counter")}


def _vertices_at(mesh, pos, tol=1e-6):
    return [v for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), pos) < tol]


def _space(cam, sx, sy):
    from mirai.topology.knife_pick import space_point

    return {"kind": "space", "position": space_point(cam, sx, sy, W, H)}


def _screen(cam, world):
    return cam.project_to_screen(world, W, H)


def _beyond(cam, a_world, b_world, factor):
    """A screen position on the screen line a -> b, `factor` times as far from a as b is."""
    a, b = _screen(cam, a_world), _screen(cam, b_world)
    return (a[0] + factor * (b[0] - a[0]), a[1] + factor * (b[1] - a[1]))


# =========================================================================================================
# Ported Q5 cross-face tests (Production counterparts)
# =========================================================================================================


@XFAIL
def test_far_click_crosses_any_number_of_faces():
    mesh, p = _grid(n=6)
    knife, scene = _session(mesh, _camera(mesh))
    assert knife.click(_ept(mesh, p[(3, 0)], p[(4, 0)], 0.5))
    assert knife.click(_ept(mesh, p[(3, 6)], p[(4, 6)], 0.5))
    assert len(_crossings(knife)) == 5 and not _breaks(knife)
    assert knife.commit() is not None
    res = knife.last_resolution
    assert (res.applied, res.runs) == (6, 6)
    assert len(scene.history) == 1
    assert_mesh_invariants(mesh, context="S4 6 quads")


@XFAIL
def test_hole_visible_pieces_cut_gap_skipped_hud_note():
    mesh, p = _grid(hole=(2, 1))
    knife, scene = _session(mesh, _camera(mesh))
    faces_before = len(mesh.all_face_ids())
    assert knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5))
    assert knife.click(_ept(mesh, p[(1, 4)], p[(2, 4)], 0.5))   # accepted: the target itself is valid
    assert knife.last_plan.skipped == ["gap"]
    assert len(_breaks(knife, "gap")) == 1
    knife.commit()
    res = knife.last_resolution
    assert (res.applied, res.runs, res.gaps) == (3, 3, 1)
    assert len(mesh.all_face_ids()) == faces_before + 3
    assert_mesh_invariants(mesh, context="S4 hole")
    assert len(scene.history) == 1


@XFAIL
def test_no_run_is_connected_across_a_gap():
    mesh, p = _grid(hole=(2, 1))
    knife, _scene = _session(mesh, _camera(mesh))
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5))
    knife.click(_ept(mesh, p[(1, 4)], p[(2, 4)], 0.5))
    knife.commit()
    left, right = _vertices_at(mesh, (2.0, 1.5, 0.0), 1e-3), _vertices_at(mesh, (3.0, 1.5, 0.0), 1e-3)
    assert len(left) == len(right) == 1
    assert not any(set(mesh.edge_vertices(e)) == {left[0], right[0]} for e in mesh.all_edge_ids())
    assert_mesh_invariants(mesh, context="S4 gap")


@XFAIL
def test_one_hit_face_at_a_piece_end_is_not_cut_and_the_hidden_crossing_is_counted():
    mesh, p = _grid(occluder=True)
    knife, _scene = _session(mesh, _camera(mesh, 0.0, 0.0))
    faces_before = len(mesh.all_face_ids())
    assert knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5))
    assert knife.click(_ept(mesh, p[(1, 4)], p[(2, 4)], 0.5))
    assert len(_crossings(knife)) == 4
    assert knife.last_plan.hidden == 1
    assert len(_breaks(knife, "gap")) == 2
    knife.commit()
    assert (knife.last_resolution.applied, knife.last_resolution.runs) == (3, 3)
    assert len(mesh.all_face_ids()) == faces_before + 3
    assert_mesh_invariants(mesh, context="S4 one-hit faces")


@XFAIL
def test_without_occlusion_nothing_is_hidden_and_nothing_skipped():
    mesh, p = _grid(occluder=True)
    knife, _scene = _session(mesh, _camera(mesh, 0.0, 0.0), occlusion=False)
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5))
    knife.click(_ept(mesh, p[(1, 4)], p[(2, 4)], 0.5))
    assert len(_crossings(knife)) == 3 and not _breaks(knife)
    assert knife.last_plan.hidden == 0


@XFAIL
def test_crossing_dots_and_lines_in_hover_plan():
    mesh, p = _grid()
    knife, _scene = _session(mesh, _camera(mesh))
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3))
    plan = knife.plan(_ept(mesh, p[(1, 3)], p[(2, 3)], 0.6))
    assert plan.ok and len(plan.crossings) == 2
    assert [style for _a, _b, style in plan.lines] == ["cut"] * 3
    assert plan.method == "walk"
    assert len(knife.path) == 1                                    # planning never mutates the session


def test_cross_face_target_without_a_view_is_rejected():
    mesh, p = _grid()
    knife, _scene = _session(mesh, None)
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3))
    assert not knife.click(_ept(mesh, p[(1, 3)], p[(2, 3)], 0.6))
    assert knife.last_plan.reason == CROSS_FACE


@XFAIL
def test_boundary_start_loop_across_faces_closes_fully():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    start = _ept(mesh, p[(1, 2)], p[(2, 2)], 0.2)
    for t in (start, _face_at(cam, mesh, (1.4, 1.5, 0.0)), _ept(mesh, p[(1, 2)], p[(2, 2)], 0.8),
              _face_at(cam, mesh, (2.6, 1.5, 0.0))):
        assert knife.click(t)
    assert knife.click({"kind": "point", "pid": knife.path[0]["pid"]})
    assert knife.path[-2]["reason"] == "closed" and knife.path[-2]["cyclic"]
    knife.commit()
    assert (knife.last_resolution.applied, knife.last_resolution.runs) == (2, 2)
    assert_mesh_invariants(mesh, context="S4 boundary-start loop")


def _loop4(cam, mesh):
    return [_face_at(cam, mesh, w) for w in ((1.5, 1.5, 0.0), (2.5, 1.5, 0.0), (2.5, 2.5, 0.0), (1.5, 2.5, 0.0))]


@XFAIL
def test_interior_start_loop_over_four_quads_closes_without_bridges():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, scene = _session(mesh, cam)
    old_vertices = set(mesh.all_vertex_ids())
    for t in _loop4(cam, mesh):
        assert knife.click(t)
    assert len(_crossings(knife)) == 3
    assert knife.click({"kind": "point", "pid": knife.path[0]["pid"]})
    assert knife.path[-2] == {"kind": "break", "reason": "closed", "cyclic": True}
    assert len(scene.history) == 0
    assert knife.commit() is not None
    assert (knife.last_resolution.applied, knife.last_resolution.runs) == (4, 4)
    cut = [e for e in knife.path_edges if mesh.is_valid_edge(e)]
    assert len(cut) == 8 and not [e for e in cut if set(mesh.edge_vertices(e)) & old_vertices]   # 0 bridges
    assert_mesh_invariants(mesh, context="S4 loop4")


@XFAIL
def test_continuing_from_the_seed_does_not_connect_across_the_closed_loop():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    for t in _loop4(cam, mesh):
        knife.click(t)
    assert knife.click({"kind": "point", "pid": knife.path[0]["pid"]})
    n_closed = len(knife.path)
    assert knife.click(_ept(mesh, p[(0, 3)], p[(0, 4)], 0.5))
    assert [q["kind"] for q in knife.path[n_closed - 2:n_closed]] == ["break", "face"]
    knife.commit()
    assert (knife.last_resolution.applied, knife.last_resolution.runs) == (8, 8)
    assert len([e for e in knife.path_edges if mesh.is_valid_edge(e)]) == 12


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


def _pid_of(knife, target):
    return next(q["pid"] for q in knife.path if q["kind"] == target["kind"] and not q.get("crossing")
                and q.get("edge_id") == target.get("edge_id") and q.get("vertex_id") == target.get("vertex_id"))


@XFAIL
def test_earlier_point_click_is_one_undo_step_with_its_crossings():
    mesh, p, cam, knife, scene, pts = _earlier_edge_scene()
    for name in "ABCD":
        assert knife.click(pts[name])
    before = knife.path
    assert knife.click({"kind": "point", "pid": _pid_of(knife, pts["B"])})
    after = knife.path
    assert len(after) > len(before) + 1 and any(q.get("crossing") for q in after[len(before):])
    assert knife.undo_step() and knife.path == before
    assert knife.redo_step() and knife.path == after
    assert knife.last_point["pid"] == _pid_of(knife, pts["B"])


@XFAIL
def test_click_on_an_earlier_edge_point_across_faces_connects_and_continues():
    mesh, p, cam, knife, scene, pts = _earlier_edge_scene()
    for name in "ABCD":
        assert knife.click(pts[name])
    assert knife.click({"kind": "point", "pid": _pid_of(knife, pts["B"])})
    assert knife.last_plan.earlier and not knife.last_plan.closing
    assert knife.click(pts["E"])
    assert knife.commit() is not None and len(scene.history) == 1
    res = knife.last_resolution
    assert res.applied == res.runs
    v = _vertices_at(mesh, (2.0, 1.5, 0.0))
    assert len(v) == 1 and len(mesh.vertex_edges(v[0])) == 6
    assert_mesh_invariants(mesh, context="S4 earlier edge point")


@XFAIL
def test_the_last_point_and_planner_crossings_are_not_earlier_points():
    mesh, p, cam, knife, scene, pts = _earlier_edge_scene()
    for name in "AB":
        knife.click(pts[name])
    assert not knife.plan({"kind": "point", "pid": _pid_of(knife, pts["B"])}).ok      # the last point
    crossing = _crossings(knife)[0]
    assert crossing["pid"] not in {q["pid"] for q in knife.snap_points}                # never a snap target
    assert not knife.plan({"kind": "point", "pid": crossing["pid"]}).ok               # nor an own-point target
    if crossing["kind"] == "vertex":
        assert knife.plan(_vpt(crossing["vertex_id"])).ok                              # the mesh vertex: a new click


@XFAIL
def test_one_click_with_k_crossings_undoes_as_one_step():
    mesh, p = _grid()
    knife, _scene = _session(mesh, _camera(mesh))
    knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3))
    one = knife.path
    knife.click(_ept(mesh, p[(1, 3)], p[(2, 3)], 0.6))
    two = knife.path
    assert len(two) == 4                                           # target + 2 crossings
    assert knife.undo_step() and knife.path == one
    assert knife.redo_step() and knife.path == two
    assert knife.undo_step() and knife.undo_step()
    assert knife.path == [] and not knife.undo_step()


@XFAIL
def test_plane_planner_reports_a_vertex_hit_not_an_edge_end():
    from mirai.topology.knife_planner import View, plan_crossings

    mesh, p = _grid()
    cam = _camera(mesh, 0.0, 0.0)
    a, b = _vpt(p[(3, 3)]), _ept(mesh, p[(3, 1)], p[(3, 2)], 0.514)
    res = plan_crossings(View(cam, W, H, None, True), mesh, a, b)
    assert all(c["kind"] == "vertex" or 1e-9 < c["t"] < 1 - 1e-9 for c in res.crossings)
    assert {"kind": "vertex", "vertex_id": p[(3, 2)]} in res.crossings
    before = _faces(mesh)
    knife, _scene = _session(mesh, cam)
    assert knife.click(a) and knife.click(b)
    knife.commit()
    assert _faces(mesh) == before                                  # all along existing edges: nothing cut


@XFAIL
def test_straight_line_out_of_a_concave_face_is_planned_across_faces():
    mesh, _p = _grid()
    cam = _camera(mesh, 0.0, 0.0)

    def edge_at(a, b, t):
        pos = tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
        for eid in mesh.all_edge_ids():
            p0, p1 = (mesh.vertex_position(x) for x in mesh.edge_vertices(eid))
            d = [p1[k] - p0[k] for k in range(3)]
            u = sum((pos[k] - p0[k]) * d[k] for k in range(3)) / sum(c * c for c in d)
            if 1e-9 < u < 1 - 1e-9 and math.dist(pos, tuple(p0[k] + u * d[k] for k in range(3))) < 1e-9:
                return {"kind": "edge", "edge_id": eid, "t": u}
        raise LookupError(pos)

    knife, _scene = _session(mesh, cam)
    for t in (edge_at((0, 0, 0), (1, 0, 0), 0.5), _face_at(cam, mesh, (0.5, 0.5, 0.0)), edge_at((0, 0, 0), (0, 1, 0), 0.5)):
        assert knife.click(t)
    assert knife.commit() is not None
    knife, _scene = _session(mesh, cam)
    assert knife.click(edge_at((0.5, 0, 0), (1, 0, 0), 0.6))
    assert knife.click(edge_at((0, 0.5, 0), (0, 1, 0), 0.6))
    assert knife.commit() is not None
    assert (knife.last_resolution.applied, knife.last_resolution.runs) == (3, 3)
    assert_mesh_invariants(mesh, context="S4 concave (R5)")


@XFAIL
def test_planner_with_pick_cache_gives_the_same_crossings_as_without():
    from mirai.topology.knife_planner import View, plan_crossings
    from mirai.viewport.picking_cache import PickCache

    mesh = create_cube()
    cam = _camera(mesh, 35.0, 30.0)
    rnd = random.Random(5)
    for _ in range(40):
        pts = []
        while len(pts) < 2:
            s = (rnd.uniform(0, W), rnd.uniform(0, H))
            t = knife_pick(cam, mesh, *s, W, H, occlusion=True)
            if t["kind"] in ("vertex", "edge"):
                pts.append(t)
            elif t["kind"] == "face":
                pts.append({"kind": "face", "face_id": t["face_id"], "position": t["position"]})
        plain = plan_crossings(View(cam, W, H, None, True), mesh, *pts)
        cached = plan_crossings(View(cam, W, H, PickCache(), True), mesh, *pts)
        assert plain.crossings == cached.crossings and plain.method == cached.method


# =========================================================================================================
# Points in space (Manu, 2026-10-02) — absolute spec, no Lab oracle
# =========================================================================================================

CUBE_VIEW = (35.0, 30.0)


def _cube_session(occlusion=True, view=CUBE_VIEW):
    mesh = create_cube()
    cam = _camera(mesh, *view)
    knife, scene = _session(mesh, cam, occlusion=occlusion)
    return mesh, cam, knife, scene


def _cube_edge(mesh, a, b, t):
    va = next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) == a)
    vb = next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) == b)
    return _ept(mesh, va, vb, t)


TOP_RIGHT = ((1.0, 1.0, -1.0), (1.0, 1.0, 1.0))
FRONT_LEFT = ((-1.0, -1.0, 1.0), (-1.0, 1.0, 1.0))


def _mesh_twin(knife_clicks, view=CUBE_VIEW):
    """The same cut made by mesh clicks only (on a fresh cube): V/E/F and the faces after commit."""
    mesh = create_cube()
    cam = _camera(mesh, *view)
    knife, scene = _session(mesh, cam)
    for make in knife_clicks:
        assert knife.click(make(mesh))
    assert knife.commit() is not None
    return _vef(mesh), _faces(mesh)


@XFAIL
def test_space_point_lies_on_the_click_ray_and_on_the_camera_target_plane():
    from mirai.topology.knife_pick import space_point

    mesh = create_cube()
    for yaw, pitch, (sx, sy) in ((35.0, 30.0, (40.0, 60.0)), (200.0, -20.0, (1200.0, 700.0)), (90.0, 70.0, (640.0, 5.0))):
        cam = _camera(mesh, yaw, pitch)
        cam.pan(37.0, -12.0, W, H)                          # the target need not be the mesh centre
        pos = space_point(cam, sx, sy, W, H)
        eye, target = cam.eye(), cam.target
        view_dir = [target[k] - eye[k] for k in range(3)]
        assert abs(sum((pos[k] - target[k]) * view_dir[k] for k in range(3))) < 1e-9 * sum(c * c for c in view_dir)
        back = cam.project_to_screen(pos, W, H)
        assert back[0] == pytest.approx(sx, abs=1e-6) and back[1] == pytest.approx(sy, abs=1e-6)


@XFAIL
def test_mesh_start_then_a_click_in_space_cuts_the_visible_faces_up_to_the_last_crossing():
    mesh, cam, knife, scene = _cube_session()
    before = mesh.export_state()
    a = _cube_edge(mesh, *TOP_RIGHT, 0.5)
    assert knife.click(a)
    sx, sy = _beyond(cam, (1.0, 1.0, 0.0), (-1.0, 0.0, 1.0), 1.6)        # past the front / left edge
    assert knife.click(_space(cam, sx, sy))
    rec = knife.path[-1]
    assert rec["kind"] == "space" and "pid" in rec
    assert [q["kind"] for q in _crossings(knife)] == ["edge", "edge"]
    assert knife.path[-2] == {"kind": "break", "reason": "space"}
    assert knife.last_point is rec                                         # the chain continues from it
    assert knife.commit() is not None and len(scene.history) == 1
    twin = _mesh_twin([lambda m: _cube_edge(m, *TOP_RIGHT, 0.5),
                       lambda m: _cube_edge(m, *FRONT_LEFT, _crossing_t(mesh_before=before))])
    assert (_vef(mesh), _faces(mesh)) == twin
    scene.history.undo()
    assert _content(mesh.export_state()) == _content(before)


def _crossing_t(mesh_before):
    """t (from the bottom) of the planner's crossing on the front / left edge in the space test above."""
    mesh = Mesh.from_state(mesh_before)
    cam = _camera(mesh, *CUBE_VIEW)
    knife, _scene = _session(mesh, cam)
    knife.click(_cube_edge(mesh, *TOP_RIGHT, 0.5))
    knife.click(_space(cam, *_beyond(cam, (1.0, 1.0, 0.0), (-1.0, 0.0, 1.0), 1.6)))
    c = _crossings(knife)[-1]
    pos = target_position(mesh, c)
    return (pos[1] + 1.0) / 2.0


@XFAIL
def test_both_ends_in_space_cut_every_visible_face_in_between():
    mesh, cam, knife, scene = _cube_session()
    left = _beyond(cam, (1.0, 0.0, -0.2), (-1.0, 0.0, 0.8), 1.8)
    right = _beyond(cam, (-1.0, 0.0, 0.8), (1.0, 0.0, -0.2), 1.8)
    assert knife.click(_space(cam, *left)) and knife.last_plan.start
    assert knife.click(_space(cam, *right))
    kinds = [q["kind"] for q in _crossings(knife)]
    assert len(kinds) >= 3                                                  # left silhouette, front/right, right silhouette
    assert _breaks(knife, "space") and len(_breaks(knife, "space")) == 2
    crossings = [target_position(mesh, q) for q in _crossings(knife)]
    assert knife.commit() is not None and len(scene.history) == 1
    for pos in crossings:
        assert len(_vertices_at(mesh, pos)) == 1
    assert _vef(mesh)[2] == 6 + len(crossings) - 1                         # each face between two crossings split
    assert_mesh_invariants(mesh, context="S4 space to space")


@XFAIL
def test_a_space_segment_that_crosses_nothing_is_accepted_and_commits_nothing():
    mesh, cam, knife, scene = _cube_session()
    before = mesh.export_state()
    assert knife.click(_space(cam, 20.0, 20.0))
    assert knife.click(_space(cam, 40.0, 700.0))                          # down the left margin: no face
    assert not _crossings(knife) and knife.last_plan.ok
    assert knife.commit() is None
    assert len(scene.history) == 0 and _content(mesh.export_state()) == _content(before)


@XFAIL
def test_a_chain_never_touching_the_mesh_commits_nothing():
    mesh, cam, knife, scene = _cube_session()
    before = mesh.export_state()
    assert knife.click(_space(cam, 20.0, 20.0))
    assert knife.lift()
    assert knife.commit() is None and len(scene.history) == 0
    assert _content(mesh.export_state()) == _content(before)


@XFAIL
def test_start_in_space_then_a_mesh_point():
    mesh, cam, knife, scene = _cube_session()
    b = _cube_edge(mesh, *TOP_RIGHT, 0.5)
    start = _beyond(cam, (1.0, 1.0, 0.0), (-1.0, 0.0, 1.0), 1.6)
    assert knife.click(_space(cam, *start)) and knife.path[0]["kind"] == "space"
    assert knife.click(b)
    assert knife.path[1] == {"kind": "break", "reason": "space"}
    assert len(_crossings(knife)) == 2
    assert knife.commit() is not None
    assert (knife.last_resolution.applied, knife.last_resolution.runs) == (2, 2)
    assert_mesh_invariants(mesh, context="S4 space start")


@XFAIL
def test_orbiting_between_clicks_keeps_the_space_points_world_position():
    mesh, cam, knife, _scene = _cube_session()
    assert knife.click(_cube_edge(mesh, *TOP_RIGHT, 0.5))
    space = _space(cam, *_beyond(cam, (1.0, 1.0, 0.0), (-1.0, 0.0, 1.0), 1.6))
    assert knife.click(space)
    stored = tuple(knife.path[-1]["position"])
    path = knife.path
    cam.orbit(math.radians(40.0), math.radians(-10.0))                     # the live camera moves
    knife.set_view(cam, W, H)
    assert knife.path == path and tuple(knife.path[-1]["position"]) == stored
    assert knife.click(_cube_edge(mesh, (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), 0.5))   # planned with the new camera
    assert knife.path[: len(path)] == path


@XFAIL
def test_undo_redo_lift_esc_with_space_points():
    mesh, cam, knife, scene = _cube_session()
    assert knife.click(_cube_edge(mesh, *TOP_RIGHT, 0.5))
    one = knife.path
    assert knife.click(_space(cam, *_beyond(cam, (1.0, 1.0, 0.0), (-1.0, 0.0, 1.0), 1.6)))
    two = knife.path
    assert len(two) == len(one) + 4                                        # 2 crossings, the break, the point
    assert knife.undo_step() and knife.path == one                         # one click = one step
    assert knife.redo_step() and knife.path == two
    assert knife.lift() and knife.last_point is None                       # E / RMB after a space point
    assert knife.undo_step() and knife.path == two
    knife.cancel()
    assert len(scene.history) == 0


@XFAIL
def test_space_points_are_no_snap_targets_and_no_earlier_points():
    mesh, cam, knife, _scene = _cube_session()
    assert knife.click(_space(cam, 20.0, 20.0))
    assert knife.click(_cube_edge(mesh, *TOP_RIGHT, 0.5))
    space = knife.path[0]
    assert space["pid"] not in {q["pid"] for q in knife.snap_points}
    assert not knife.plan({"kind": "point", "pid": space["pid"]}).ok
    again = _space(cam, 21.0, 21.0)                                        # next to it: a new space point
    plan = knife.plan(again)
    assert plan.ok and plan.entries[-1] is not space and not plan.closing and not plan.earlier


@XFAIL
def test_a_mesh_started_chain_with_a_space_point_closes_but_not_cyclically():
    mesh, cam, knife, _scene = _cube_session()
    start = _cube_edge(mesh, *TOP_RIGHT, 0.5)
    assert knife.click(start)
    assert knife.click(_space(cam, *_beyond(cam, (1.0, 1.0, 0.0), (-1.0, 0.0, 1.0), 1.6)))
    assert knife.click(_face_at(cam, mesh, (0.3, 0.2, 1.0)))
    assert knife.click({"kind": "point", "pid": knife.path[0]["pid"]})    # back on the start: closes
    assert knife.last_plan.closing and not knife.last_plan.cyclic
    assert knife.commit() is not None
    assert_mesh_invariants(mesh, context="S4 close with a space point")


@XFAIL
def test_a_chain_started_in_space_cannot_close_the_double_click_only_lifts():
    mesh, cam, knife, _scene = _cube_session()
    assert knife.click(_space(cam, 20.0, 20.0))
    assert knife.click(_cube_edge(mesh, *TOP_RIGHT, 0.5))
    assert knife.click(_face_at(cam, mesh, (0.3, 0.2, 1.0)))
    assert knife.click(_face_at(cam, mesh, (0.3, 1.0, 0.3)))
    plan = knife.plan_lift(close=True)
    assert plan.ok and plan.lift and not plan.closing
    assert "space" in plan.reason
    assert knife.finish_chain() and knife.path[-1] == {"kind": "break", "reason": "lift"}


@XFAIL
def test_wireframe_space_line_cuts_everything_under_it():
    mesh, cam, knife, _scene = _cube_session(occlusion=False)
    left = _beyond(cam, (1.0, 0.0, -0.2), (-1.0, 0.0, 0.8), 1.8)
    right = _beyond(cam, (-1.0, 0.0, 0.8), (1.0, 0.0, -0.2), 1.8)
    assert knife.click(_space(cam, *left)) and knife.click(_space(cam, *right))
    assert knife.last_plan.hidden == 0
    seen = _crossings(knife)
    mesh2, cam2, knife2, _s2 = _cube_session(occlusion=True)
    knife2.click(_space(cam2, *left))
    knife2.click(_space(cam2, *right))
    assert len(seen) > len(_crossings(knife2))                            # the back faces too
    assert knife.commit() is not None
    assert_mesh_invariants(mesh, context="S4 wireframe space")


@XFAIL
def test_space_records_never_reach_the_resolver(monkeypatch):
    from mirai.topology import knife as knife_module

    seen = []
    original = knife_module.resolve_cross_face

    def recording(mesh, path, before):
        seen.append(list(path))
        return original(mesh, path, before)

    monkeypatch.setattr(knife_module, "resolve_cross_face", recording)
    mesh, cam, knife, _scene = _cube_session()
    knife.click(_space(cam, 20.0, 20.0))
    knife.click(_cube_edge(mesh, *TOP_RIGHT, 0.5))
    knife.click(_space(cam, *_beyond(cam, (1.0, 1.0, 0.0), (-1.0, 0.0, 1.0), 1.6)))
    knife.commit()
    assert seen and all(p["kind"] != "space" for p in seen[0])
    assert any(p.get("reason") == "space" for p in seen[0])               # the break markers stay


# =========================================================================================================
# Production-only cases
# =========================================================================================================


@XFAIL
def test_orbit_between_clicks_does_not_change_a_placed_cut():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    assert knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3))
    assert knife.click(_ept(mesh, p[(1, 3)], p[(2, 3)], 0.6))
    placed = knife.path
    for yaw, pitch in ((60.0, 50.0), (-30.0, 60.0)):
        knife.set_view(_camera(mesh, yaw, pitch), W, H)
        knife.plan(_ept(mesh, p[(3, 0)], p[(4, 0)], 0.5))                 # a hover under another camera
        assert knife.path == placed


@XFAIL
def test_a_pen_lift_between_cross_face_chains_commits_both_as_one_entry():
    mesh, p = _grid()
    knife, scene = _session(mesh, _camera(mesh))
    assert knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.3)) and knife.click(_ept(mesh, p[(1, 4)], p[(2, 4)], 0.3))
    assert knife.lift()
    assert knife.click(_ept(mesh, p[(3, 0)], p[(4, 0)], 0.5)) and knife.click(_ept(mesh, p[(3, 4)], p[(4, 4)], 0.5))
    assert len(_crossings(knife)) == 6
    assert knife.commit() is not None and len(scene.history) == 1
    assert (knife.last_resolution.applied, knife.last_resolution.runs) == (8, 8)
    assert_mesh_invariants(mesh, context="S4 two lifted chains")


@XFAIL
def test_finish_chain_closes_across_faces():
    mesh, p = _grid()
    cam = _camera(mesh)
    knife, _scene = _session(mesh, cam)
    for t in _loop4(cam, mesh):
        assert knife.click(t)
    plan = knife.plan_lift(close=True)
    assert plan.ok and plan.closing and plan.cyclic
    assert knife.finish_chain()
    assert knife.path[-1] == {"kind": "break", "reason": "lift"}
    assert any(q.get("crossing") for q in knife.path[-4:])                 # the closing segment's crossing
    assert knife.commit() is not None
    assert (knife.last_resolution.applied, knife.last_resolution.runs) == (4, 4)


@XFAIL
def test_a_midpoint_start_followed_by_a_cross_face_segment():
    mesh, p = _grid()
    knife, _scene = _session(mesh, _camera(mesh))
    assert knife.click(_ept(mesh, p[(1, 0)], p[(2, 0)], 0.5))            # what Shift+click gives
    assert knife.click(_ept(mesh, p[(1, 4)], p[(2, 4)], 0.7))
    assert len(_crossings(knife)) == 3
    knife.commit()
    assert len(_vertices_at(mesh, (0.0, 1.5, 0.0))) == 1
    assert_mesh_invariants(mesh, context="S4 midpoint start")


@XFAIL
def test_a_crossing_on_a_vertex_is_not_found_as_an_earlier_vertex_point():
    mesh, p = _grid()
    knife, _scene = _session(mesh, _camera(mesh))
    knife.click(_ept(mesh, p[(0, 0)], p[(0, 1)], 0.502))
    knife.click(_ept(mesh, p[(2, 1)], p[(2, 2)], 0.502))                 # passes vertex (1, 1): a vertex crossing
    assert [c["kind"] for c in _crossings(knife)] == ["vertex"]
    plan = knife.plan(_vpt(p[(1, 1)]))
    assert plan.ok and not plan.earlier                                    # a fresh click on that vertex (Q5)


# -- integrity: random sessions mixing mesh and space clicks ------------------------------------------------


@XFAIL
@pytest.mark.parametrize("seed", range(12))
def test_random_sessions_mixing_mesh_and_space_clicks_stay_sound(seed):
    rnd = random.Random(f"s4/space/{seed}")
    mesh = create_cube()
    views = [(35.0, 30.0), (-40.0, 25.0), (130.0, -30.0), (60.0, 55.0)]
    for _session_no in range(rnd.randint(1, 2)):
        yaw, pitch = rnd.choice(views)
        cam = _camera(mesh, yaw, pitch)
        knife, scene = _session(mesh, cam, occlusion=rnd.random() < 0.8)
        before = mesh.export_state()
        history = len(scene.history)
        for _ in range(rnd.randint(2, 7)):
            if rnd.random() < 0.2:
                yaw, pitch = rnd.choice(views)
                cam = _camera(mesh, yaw, pitch)
                knife.set_view(cam, W, H)
            sx, sy = rnd.uniform(0, W), rnd.uniform(0, H)
            target = knife_pick(cam, mesh, sx, sy, W, H, occlusion=True)
            if target["kind"] == "outside":
                target = _space(cam, sx, sy)
            acc = knife.accepts(target)
            assert knife.click(target) is acc
            if rnd.random() < 0.1:
                knife.undo_step()
            if rnd.random() < 0.1:
                knife.lift()
        assert _content(mesh.export_state()) == _content(before)            # nothing cut before commit
        cmd = knife.commit()
        assert knife.last_problem is None, knife.last_problem
        assert len(scene.history) == history + (cmd is not None)
        assert_mesh_invariants(mesh, context=f"S4 random space session {seed}")
