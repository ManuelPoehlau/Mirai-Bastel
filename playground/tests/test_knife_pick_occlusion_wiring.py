"""WP-06 B8 wiring: Playground Knife picks through the shared cache + occlusion.

Scene (camera straight down -Z): an occluder quad at z=2 hides a back vertex/
edge at z=0; a front vertex/edge at z=3 sits almost on the same view ray.
Opt-in default must stay the exact pre-B8 behaviour for callers that pass
neither `cache` nor `occlusion`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import Mesh  # noqa: E402
from mirai.topology.knife_pick import knife_pick  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from mirai.viewport.picking_cache import PickCache  # noqa: E402
from playground.experiments.knife_face.engine import knife_face_pick  # noqa: E402

W, H = 800, 600


def _camera() -> OrbitCamera:
    return OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.0, yaw=0.0, pitch=0.0)


def _scene():
    mesh = Mesh()
    back_a = mesh.add_vertex((0.0, 0.0, 0.0))
    back_b = mesh.add_vertex((0.0, 1.0, 0.0))
    back_edge = mesh.add_edge(back_a, back_b)
    front_a = mesh.add_vertex((0.0, 0.0, 3.0))
    # Front edge on the same view rays as the back edge's midpoint (y=0.5 at
    # z=0 <-> y=0.2 at z=3, from the eye at z=5), well clear of the vertices.
    fe_b = mesh.add_vertex((0.0, 0.4, 3.0))
    front_edge = mesh.add_edge(front_a, fe_b)
    quad = [mesh.add_vertex(p) for p in
            ((-1.0, -1.0, 2.0), (1.0, -1.0, 2.0), (1.0, 1.0, 2.0), (-1.0, 1.0, 2.0))]
    mesh.add_face(quad)
    return mesh, back_a, front_a, back_edge, front_edge


def test_vertex_front_wins_with_occlusion_default_unchanged():
    mesh, back_a, front_a, _be, _fe = _scene()
    cam = _camera()
    sx, sy = cam.project_to_screen((0.0, 0.0, 0.0), W, H)

    old = knife_pick(cam, mesh, sx, sy, W, H)
    assert old == {"kind": "vertex", "vertex_id": back_a}

    new = knife_pick(cam, mesh, sx, sy, W, H, cache=PickCache(), occlusion=True)
    assert new == {"kind": "vertex", "vertex_id": front_a}


def test_edge_front_wins_with_occlusion_default_unchanged():
    mesh, _a, _fa, back_edge, front_edge = _scene()
    cam = _camera()
    sx, sy = cam.project_to_screen((0.0, 0.5, 0.0), W, H)

    old = knife_pick(cam, mesh, sx, sy, W, H)
    assert old["kind"] == "edge" and old["edge_id"] == back_edge

    new = knife_pick(cam, mesh, sx, sy, W, H, cache=PickCache(), occlusion=True)
    assert new["kind"] == "edge" and new["edge_id"] == front_edge


def test_knife_face_pick_passes_cache_and_occlusion_through():
    mesh, back_a, front_a, _be, _fe = _scene()
    cam = _camera()
    sx, sy = cam.project_to_screen((0.0, 0.0, 0.0), W, H)

    assert knife_face_pick(cam, mesh, sx, sy, W, H)["vertex_id"] == back_a
    hit = knife_face_pick(cam, mesh, sx, sy, W, H, cache=PickCache(), occlusion=True)
    assert hit["vertex_id"] == front_a


def test_playground_app_shares_the_applications_pick_cache():
    from playground.app import PlaygroundApp

    app = PlaygroundApp()
    assert app.pick_cache is app._app._pick_cache
