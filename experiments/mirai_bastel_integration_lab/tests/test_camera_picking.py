"""Lab-Kamera + Picking: legacy-gap-sicher und headless.

Die V0.2-Kamera besitzt KEIN `project_to_screen` (der V0.2-Demonstrator
ruft es dennoch auf — Integrationslücke). Die Lab-Kamera ergänzt die
Projektion/Ray/Deltas additiv; diese Tests sichern die Mathematik
(Konsistenz Projektion ↔ Picking ↔ Core-IDs).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
for _p in (str(_LAB), str(_LAB.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.core_to_render import CoreRenderBinding  # noqa: E402
from adapters.picking import pick_vertex  # noqa: E402
from lab_camera import LabOrbitCamera  # noqa: E402
from scene.scene_objects import build_cube_scene  # noqa: E402

from experiments.mirai_bastel_viewport_V02.renderer import TraceStore  # noqa: E402


def _setup():
    core_mesh = build_cube_scene().mesh
    binding = CoreRenderBinding(core_mesh, store_type=TraceStore)
    camera = LabOrbitCamera(
        distance=8.0, yaw=math.radians(0.0), pitch=math.radians(0.0)
    )
    camera.target = (0.0, 0.0, 0.0)
    return core_mesh, binding, camera


def test_projection_of_front_vertex_is_screen_center():
    _, _, camera = _setup()
    # Kamera blickt entlang -z (yaw=0, pitch=0) von (0,0,8) aus.
    # (1,0,-1) liegt dadurch rechts der Bildmitte, senkrecht mittig.
    sx, sy = camera.project_to_screen((1.0, 0.0, -1.0), 800, 600)
    assert sx is not None and sy is not None
    assert abs(sx - 471.5) < 5.0 and abs(sy - 300.0) < 5.0


def test_pick_vertex_returns_core_vertex_at_projected_point():
    core_mesh, binding, camera = _setup()
    vid = core_mesh.all_vertex_ids()[0]          # (-1,-1,-1)
    sx, sy = camera.project_to_screen(core_mesh.vertex_position(vid), 800, 600)
    assert sx is not None
    picked = pick_vertex(
        camera, core_mesh, binding.index_map, sx, sy, 800, 600
    )
    assert picked == vid


def test_pick_vertex_none_when_point_behind_camera():
    core_mesh, binding, camera = _setup()
    # Eye liegt bei (0,0,8) und blickt in -z: ein Punkt bei z=9 liegt
    # HINTER der Kamera (cam_z < near) => keine Projektion.
    result = camera.project_to_screen((0.0, 0.0, 9.0), 800, 600)
    assert result is None


def test_screen_ray_and_projection_are_consistent():
    _, _, camera = _setup()
    origin, direction = camera.screen_to_ray(400, 300, 800, 600)
    assert origin == camera.eye()
    assert math.isclose(math.sqrt(sum(d * d for d in direction)), 1.0, abs_tol=1e-6)


def test_orbit_and_zoom_still_v02_compatible():
    _, _, camera = _setup()
    camera.orbit(0.2, 0.1)
    camera.dolly(0.8)
    # Matrizen der V0.2-Kamera existieren weiterhin (Renderer-Vertrag).
    view = camera.build_view_matrix()
    proj = camera.build_projection_matrix(1.6)
    assert len(view) == 16 and len(proj) == 16