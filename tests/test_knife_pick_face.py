"""Knife picking of face points (WP-KNIFE-01 S3): the face hit with its position and edge clearance.

Moved from the Knife Face Lab's `knife_face_pick` (H1 of `KNIFE_FACE_CUT_DISCOVERY.md`: `pick_face` returns
only the FaceId — kept so, additively); the 9 px margin (H3); the own-point snap for interior points; the
occlusion helpers made public. Fixture: the framed default cube as in `test_application_knife.py` — faces 1
(z = +1), 3 (x = +1) and 4 (y = +1) face the camera.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.topology import knife_pick as knife_pick_module
from mirai.topology.knife_pick import EDGE_MARGIN_PX, knife_pick, snap_own_point
from mirai.viewport import picking
from mirai.viewport.picking import face_edge_distance_px, face_hit_position, pick_face
from mirai.viewport.picking_cache import PickCache

WIDTH, HEIGHT = 800, 600
SRC = Path(__file__).resolve().parents[1] / "src" / "mirai"


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _v(app, index: int):
    return sorted(app.scene.mesh.all_vertex_ids(), key=int)[index]


def _face_with(app, indices):
    mesh = app.scene.mesh
    want = {_v(app, i) for i in indices}
    return next(f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) == want)


def _centre(app, indices):
    mesh = app.scene.mesh
    pts = [mesh.vertex_position(_v(app, i)) for i in indices]
    return tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))


FRONT = (4, 5, 6, 7)   # z = +1
RIGHT = (2, 6, 5, 1)   # x = +1


def test_a_face_hit_carries_its_position_and_clearance(app):
    mesh, cam = app.scene.mesh, app.camera
    world = _centre(app, FRONT)
    sx, sy = cam.project_to_screen(world, WIDTH, HEIGHT)
    target = knife_pick(cam, mesh, sx, sy, WIDTH, HEIGHT)
    assert target["kind"] == "face" and target["face_id"] == _face_with(app, FRONT)
    assert math.dist(target["position"], world) < 1e-6
    assert target["distance_px"] > EDGE_MARGIN_PX
    assert target["position"] == face_hit_position(cam, mesh, target["face_id"], sx, sy, WIDTH, HEIGHT)
    assert target["distance_px"] == face_edge_distance_px(cam, mesh, target["face_id"], sx, sy, WIDTH, HEIGHT)
    assert pick_face(cam, mesh, sx, sy, WIDTH, HEIGHT) == target["face_id"]  # unchanged signature and result


def test_the_clearance_shrinks_towards_an_edge_and_the_edge_wins_inside_the_margin(app):
    mesh, cam = app.scene.mesh, app.camera
    fid = _face_with(app, FRONT)
    a, b = (mesh.vertex_position(_v(app, i)) for i in (5, 6))   # an edge of the front face
    mid = tuple((a[k] + b[k]) / 2 for k in range(3))
    centre = _centre(app, FRONT)
    # Occlusion on (shaded display): the cube's hidden back edges are no targets.
    far = [knife_pick(cam, mesh, *cam.project_to_screen(tuple(mid[k] + s * (centre[k] - mid[k]) for k in range(3)),
                                                        WIDTH, HEIGHT), WIDTH, HEIGHT, occlusion=True)
           for s in (0.6, 0.3)]
    assert far[0]["kind"] == far[1]["kind"] == "face" and far[0]["distance_px"] > far[1]["distance_px"]
    sx, sy = cam.project_to_screen(mid, WIDTH, HEIGHT)
    near = knife_pick(cam, mesh, sx, sy + 4.0, WIDTH, HEIGHT, occlusion=True)
    assert near["kind"] == "edge"                                 # 4 px off the edge: the edge pick wins
    assert face_edge_distance_px(cam, mesh, fid, sx, sy + 4.0, WIDTH, HEIGHT) < EDGE_MARGIN_PX


def test_the_cache_gives_the_same_face_point(app):
    mesh, cam = app.scene.mesh, app.camera
    cache = PickCache()
    for indices in (FRONT, RIGHT):
        sx, sy = cam.project_to_screen(_centre(app, indices), WIDTH, HEIGHT)
        plain = knife_pick(cam, mesh, sx, sy, WIDTH, HEIGHT)
        cached = knife_pick(cam, mesh, sx, sy, WIDTH, HEIGHT, cache=cache, occlusion=True)
        assert plain == cached


def test_own_interior_points_snap_and_a_nearer_vertex_wins(app):
    mesh, cam = app.scene.mesh, app.camera
    fid = _face_with(app, FRONT)
    world = _centre(app, FRONT)
    own = {"kind": "face", "face_id": fid, "position": world, "pid": 7}
    sx, sy = cam.project_to_screen(world, WIDTH, HEIGHT)
    target = knife_pick(cam, mesh, sx + 5.0, sy, WIDTH, HEIGHT)
    assert snap_own_point(cam, mesh, sx + 5.0, sy, WIDTH, HEIGHT, [own], target) == {"kind": "point", "pid": 7}
    assert snap_own_point(cam, mesh, sx + 20.0, sy, WIDTH, HEIGHT, [own], target) == target   # beyond 14 px
    # An own point right next to a corner: on the corner itself the vertex is nearer and wins.
    corner = mesh.vertex_position(_v(app, 6))
    near_corner = tuple(corner[k] + 0.04 * (world[k] - corner[k]) for k in range(3))
    own_c = dict(own, position=near_corner)
    cx, cy = cam.project_to_screen(corner, WIDTH, HEIGHT)
    vertex = knife_pick(cam, mesh, cx, cy, WIDTH, HEIGHT)
    assert vertex["kind"] == "vertex"
    assert snap_own_point(cam, mesh, cx, cy, WIDTH, HEIGHT, [own_c], vertex) == vertex


def test_a_hidden_own_interior_point_does_not_snap_with_occlusion_on(app):
    mesh, cam = app.scene.mesh, app.camera
    back = _face_with(app, (0, 3, 2, 1))  # z = -1, behind the front face
    world = _centre(app, (0, 3, 2, 1))
    own = {"kind": "face", "face_id": back, "position": world, "pid": 3}
    sx, sy = cam.project_to_screen(world, WIDTH, HEIGHT)
    target = knife_pick(cam, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True)
    assert snap_own_point(cam, mesh, sx, sy, WIDTH, HEIGHT, [own], target) == {"kind": "point", "pid": 3}
    assert snap_own_point(cam, mesh, sx, sy, WIDTH, HEIGHT, [own], target, occlusion=True) == target


def test_occlusion_helpers_are_public_and_the_private_names_still_resolve():
    assert picking._point_occluded is picking.point_occluded
    assert picking._vertex_occluded is picking.vertex_occluded
    assert picking._edge_point_occluded is picking.edge_point_occluded


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            yield node.module or "", [a.name for a in node.names], node.level
        elif isinstance(node, ast.Import):
            for a in node.names:
                yield a.name, [], 0


@pytest.mark.parametrize("name", ["knife.py", "knife_pick.py", "knife_preview.py"])
def test_knife_modules_import_nothing_from_playground_and_no_private_names(name):
    for module, names, _level in _imports(SRC / "topology" / name):
        assert not module.startswith("playground"), (name, module)
        assert not [n for n in names if n.startswith("_")], (name, module, names)


def test_knife_pick_module_uses_the_public_occlusion_helpers():
    assert knife_pick_module.edge_point_occluded is picking.edge_point_occluded
    assert knife_pick_module.point_occluded is picking.point_occluded
