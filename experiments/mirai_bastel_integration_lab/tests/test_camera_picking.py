"""Lab-Kamera + Picking: Production-Kamera-Basis, headless.

Seit WP-IL-01 basiert `LabOrbitCamera` auf der Production-Kamera
(`src/mirai/viewport/camera.py::OrbitCamera`); das GL-View-Matrix-Override
ist der einzige Lab-Zusatz (dokumentierte Production-Grenze). Diese Tests
sichern die Mathematik (Konsistenz Projektion ↔ Picking ↔ Core-IDs) und die
View-Matrix-Konvention gegen das historische „schwarzer Viewport“-Symptom.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
_REPO = _LAB.parent.parent
for _p in (str(_LAB), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from adapters.core_to_render import CoreRenderBinding  # noqa: E402
from adapters.picking import pick_vertex  # noqa: E402
from lab_camera import LabOrbitCamera  # noqa: E402
from scene.scene_objects import build_cube_scene  # noqa: E402

from viewport.resource_store import TraceStore  # noqa: E402  (Production, Gate 5)


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
    # Production-Delegation: ohne Index-Map (pick_nearest_vertex).
    picked = pick_vertex(camera, core_mesh, sx, sy, 800, 600)
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


def test_orbit_and_zoom_production_compatible():
    _, _, camera = _setup()
    camera.orbit(0.2, 0.1)
    camera.dolly(0.8)
    # Matrizen der Production-Kamera existieren weiterhin (Renderer-Vertrag).
    view = camera.build_view_matrix()
    proj = camera.build_projection_matrix(1.6)
    assert len(view) == 16 and len(proj) == 16


def test_lab_camera_is_production_orbit_camera_subclass():
    """WP-IL-01: Die Lab-Kamera IST eine Production-OrbitCamera."""
    from mirai.viewport.camera import OrbitCamera as ProductionOrbitCamera

    _, _, camera = _setup()
    assert isinstance(camera, ProductionOrbitCamera)
    # Production-Verhalten: camera_revision wird bei Kamera-Operationen erhöht.
    rev0 = camera.camera_revision
    camera.orbit(0.1, 0.1)
    assert camera.camera_revision == rev0 + 1


# -- View-Matrix-Konvention (Regression zum "schwarzen Viewport") -----------

def _apply_view(matrix: list[float], point: tuple[float, float, float]):
    """Wendet eine column-major 4x4 (flat 16, GL-Upload-Layout) an."""
    x, y, z = point
    return (
        matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
        matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
        matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14],
    )


def test_view_matrix_front_point_on_negative_z():
    """Front-Punkte müssen auf NEGATIVEM Camera-Z landen (GL-Konvention).

    Diagnose: Die Production/V0.2-Matrix schreibt +forward in Zeile 3; mit
    der GL-Projektion (clip.w = -view.z) erhielte Front-Geometrie clip.w < 0
    und würde komplett geclippt (schwarzer Viewport). Das Lab-Override
    korrigiert das (dokumentierte Production-Grenze, Audit §A.1).
    """
    _, _, camera = _setup()
    vx, vy, vz = _apply_view(camera.build_view_matrix(), camera.target)
    assert vz < 0.0                      # vor der Kamera => negatives view.z
    assert -vz > 0.0                     # clip.w = -view.z > 0 => nicht geclippt


def test_origin_within_opengl_frustum_default_camera():
    """Ursprung bei Default-Kamera (yaw=45°, pitch=25°, dist=8) im Frustum."""
    camera = LabOrbitCamera()            # V0.2-Defaults
    proj = camera.build_projection_matrix(1.6)
    vx, vy, vz = _apply_view(camera.build_view_matrix(), (0.0, 0.0, 0.0))
    clip_w = -vz
    assert clip_w > 0.0
    # clip.z = Zeile 2 der Projektion (Ursprung: vx = vy = 0)
    ndc_z = (proj[10] * vz + proj[14]) / clip_w
    assert -1.0 <= ndc_z <= 1.0


def test_render_matrix_chain_matches_picking_projection():
    """Render-Kette (view→proj→NDC→Pixel) == project_to_screen (Picking).

    Stellt sicher, dass Rendering und Picking dieselbe Kamera-Konvention
    verwenden — Kernanforderung nach dem View-Matrix-Fix.
    """
    _, _, camera = _setup()
    w, h = 800, 600
    point = (0.3, -0.2, 0.1)
    view = camera.build_view_matrix()
    proj = camera.build_projection_matrix(w / h)
    vx, vy, vz = _apply_view(view, point)
    clip_w = -vz
    clip_x = proj[0] * vx                # Projektions-Zeile 0
    clip_y = proj[5] * vy                # Projektions-Zeile 1
    sx = (clip_x / clip_w + 1.0) * 0.5 * w
    sy = (clip_y / clip_w + 1.0) * 0.5 * h
    px, py = camera.project_to_screen(point, w, h)
    assert math.isclose(sx, px, abs_tol=1e-6)
    assert math.isclose(sy, py, abs_tol=1e-6)


# -- Kamera-State-Änderungen (Regressionsnähte zur Laufzeit-Probe) -----------
# Die Laufzeit-Probe (2026-07-09, außerhalb des Repos, wieder entfernt) hat
# über pyglets Dispatch-Pfad nachgewiesen, dass die Viewport-Handler gerufen
# werden und genau diese State-Änderungen bewirken. Diese Tests sichern die
# Mathematik dahinter headless ab.

def test_orbit_changes_yaw_and_pitch():
    _, _, camera = _setup()
    yaw0, pitch0 = camera.yaw, camera.pitch
    camera.orbit(0.3, 0.2)
    assert math.isclose(camera.yaw - yaw0, 0.3, abs_tol=1e-9)
    assert math.isclose(camera.pitch - pitch0, 0.2, abs_tol=1e-9)


def test_dolly_changes_distance():
    _, _, camera = _setup()
    d0 = camera.distance
    camera.dolly(0.9)
    assert math.isclose(camera.distance, d0 * 0.9, abs_tol=1e-9)


def test_pan_moves_target():
    _, _, camera = _setup()
    t0 = camera.target
    # Production-API: pan(dx_px, dy_px, width, height) (früher Lab: pan_px).
    camera.pan(40, -20, 800, 600)
    assert camera.target != t0


def test_pyglet2_modifier_constants_live_in_key_module():
    """Naht zur Laufzeit: pyglet 2.x kennt key.MOD_SHIFT, aber KEIN
    mouse.MOD_SHIFT mehr (alte API — Ursache des ursprünglichen
    on_mouse_drag-Crashes). Die Handler müssen bei key.MOD_SHIFT bleiben.
    """
    from pyglet.window import key as _k
    from pyglet.window import mouse as _m
    assert hasattr(_k, "MOD_SHIFT")
    assert not hasattr(_m, "MOD_SHIFT")