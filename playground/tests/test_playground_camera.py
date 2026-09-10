"""Headless-Tests für `PlaygroundCamera` (Playground-GL-Grenze, WP-AP-01).

Sichert den Kamera/GL-Befund-Fix ab, OHNE Production zu verändern:

1. `PlaygroundCamera` ist eine `OrbitCamera` (alle Defaults identisch).
2. Die Picking-/Kamera-Mathematik wird NICHT überschrieben (dieselben
   Funktionsobjekte wie in der Production-Basisklasse).
3. Die GL-View-Matrix folgt der gluLookAt-Konvention: Front-Punkte auf
   negativem Camera-Z → `clip.w > 0` → sichtbar im GL-Pfad.
4. Orbit/Pan/Zoom verhalten sich exakt wie die Production-Kamera.
5. Der PlaygroundApp-Draw-Pfad (u_view/u_proj nach load_cube) clippt den
   Cube nicht mehr.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# sys.path-Bootstrap (identisch zu den übrigen Playground-Tests).
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
_RIGGING = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"
_LAB = _REPO_ROOT / "experiments" / "mirai_bastel_integration_lab"
for _p in (str(_LAB), str(_REPO_SRC), str(_REPO_ROOT), str(_RIGGING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


from mirai.viewport.camera import OrbitCamera  # noqa: E402

from playground.app import PlaygroundApp  # noqa: E402
from playground.camera import PlaygroundCamera  # noqa: E402


# ---------------------------------------------------------------------------
# Matrix-Helfer (Spalten-Hauptreihenfolge, wie build_view_matrix/…)
# ---------------------------------------------------------------------------

def _apply(m: list[float], vec) -> tuple[float, float, float, float]:
    """Spalten-Hauptreihenfolge: m * (x, y, z, w)."""
    x, y, z, w = vec
    return (
        m[0] * x + m[4] * y + m[8] * z + m[12] * w,
        m[1] * x + m[5] * y + m[9] * z + m[13] * w,
        m[2] * x + m[6] * y + m[10] * z + m[14] * w,
        m[3] * x + m[7] * y + m[11] * z + m[15] * w,
    )


def _clip(camera, point, aspect: float) -> tuple[float, float, float, float]:
    view = camera.build_view_matrix()
    proj = camera.build_projection_matrix(aspect)
    vc = _apply(view, (*point, 1.0))
    return _apply(proj, vc)


# ---------------------------------------------------------------------------
# 1. Klasse + Defaults
# ---------------------------------------------------------------------------

def test_playground_camera_is_orbit_camera_subclass():
    assert issubclass(PlaygroundCamera, OrbitCamera)


def test_playground_camera_defaults_match_production():
    cam = PlaygroundCamera()
    prod = OrbitCamera()
    assert cam.target == prod.target
    assert cam.distance == prod.distance
    assert cam.yaw == prod.yaw
    assert cam.pitch == prod.pitch
    assert cam.fov_degrees == prod.fov_degrees
    assert cam.near == prod.near
    assert cam.far == prod.far


# ---------------------------------------------------------------------------
# 2. Picking-/Kamera-Mathematik bleibt unverändert (nicht überschrieben)
# ---------------------------------------------------------------------------

def test_picking_and_navigation_math_is_inherited_unchanged():
    """Nur build_view_matrix darf überschrieben sein — alles andere erbt Production."""
    overridden = {
        name
        for name in (
            "eye", "basis", "orbit", "dolly", "pan",
            "screen_to_ray", "project_to_screen", "screen_delta_to_world",
        )
        if getattr(PlaygroundCamera, name) is not getattr(OrbitCamera, name)
    }
    assert overridden == set(), f"Kamera-/Picking-Mathematik wurde überschrieben: {overridden}"


def test_picking_projection_matches_production_camera():
    """screen_to_ray/project_to_screen liefern identische Ergebnisse wie Production."""
    cam = PlaygroundCamera(target=(1.0, 2.0, 3.0), distance=8.0, yaw=0.7, pitch=0.3)
    prod = OrbitCamera(target=(1.0, 2.0, 3.0), distance=8.0, yaw=0.7, pitch=0.3)
    for sx, sy in ((0.0, 0.0), (400.0, 300.0), (640.0, 512.0)):
        a = cam.screen_to_ray(sx, sy, 1280, 800)
        b = prod.screen_to_ray(sx, sy, 1280, 800)
        assert a == b
        pa = cam.project_to_screen((0.5, -0.25, 1.0), 1280, 800)
        pb = prod.project_to_screen((0.5, -0.25, 1.0), 1280, 800)
        assert pa == pb


# ---------------------------------------------------------------------------
# 3. GL-Konvention: Front-Punkte auf negativem Camera-Z, clip.w > 0
# ---------------------------------------------------------------------------

def test_view_matrix_front_point_on_negative_z():
    cam = PlaygroundCamera(target=(0.0, 0.0, 0.0), distance=6.0)
    vx, vy, vz, vw = _apply(cam.build_view_matrix(), (0.0, 0.0, 0.0, 1.0))
    assert vz < 0.0, f"Target (Front) muss auf negativem Camera-Z liegen, vz={vz:.3f}"
    assert vw == 1.0


def test_clip_w_positive_for_visible_cube_corner():
    cam = PlaygroundCamera(target=(0.0, 0.0, 0.0), distance=5.2002)
    for point in ((1.0, 1.0, 1.0), (-1.0, -1.0, -1.0), (0.0, 0.0, 0.0)):
        cx, cy, cz, cw = _clip(cam, point, 1280.0 / 800.0)
        assert cw > 0.0, f"Punkt {point} wird geclippt (clip.w={cw:.3f})"
        assert -abs(cw) <= cz <= abs(cw), f"Punkt {point} außerhalb Clip-Z"


# ---------------------------------------------------------------------------
# 4. Orbit / Pan / Zoom verhalten sich wie Production
# ---------------------------------------------------------------------------

def test_orbit_pan_dolly_behavior_matches_production():
    cam = PlaygroundCamera()
    prod = OrbitCamera()
    # Orbit
    cam.orbit(0.13, -0.07)
    prod.orbit(0.13, -0.07)
    assert math.isclose(cam.yaw, prod.yaw) and math.isclose(cam.pitch, prod.pitch)
    # Dolly
    cam.dolly(0.9)
    prod.dolly(0.9)
    assert math.isclose(cam.distance, prod.distance)
    # Pan
    cam.pan(12.0, -5.0, 1280, 800)
    prod.pan(12.0, -5.0, 1280, 800)
    assert cam.target == prod.target
    # Eye/Basis bleiben konsistent
    assert cam.eye() == prod.eye()
    assert cam.basis() == prod.basis()


def test_camera_revision_increments_on_navigation():
    cam = PlaygroundCamera()
    r0 = cam.camera_revision
    cam.orbit(0.1, 0.0)
    assert cam.camera_revision == r0 + 1
    cam.dolly(1.1)
    assert cam.camera_revision == r0 + 2
    cam.pan(1.0, 1.0, 640, 480)
    assert cam.camera_revision == r0 + 3


# ---------------------------------------------------------------------------
# 5. PlaygroundApp-Pfad: Kameratyp + GL-Kette nach load_cube
# ---------------------------------------------------------------------------

def test_app_uses_playground_camera():
    app = PlaygroundApp()
    assert isinstance(app.camera, PlaygroundCamera)


def test_app_cube_draw_chain_clips_nothing():
    """PlaygroundApp-Draw-Kette (u_view/u_proj) clippt den Cube nicht mehr."""
    app = PlaygroundApp()
    app.load_cube()
    cam = app.camera
    aspect = 1280.0 / 800.0  # identisch zu PlaygroundWindow
    for vid in app.scene.mesh.all_vertex_ids():
        point = app.scene.mesh.vertex_position(vid)
        cx, cy, cz, cw = _clip(cam, point, aspect)
        assert cw > 0.0, f"Vertex {vid} {point} wird geclippt (clip.w={cw:.3f})"
        assert -abs(cw) <= cz <= abs(cw)
    # Framing-Wert unverändert (bestehende Übernahme aus dem Lab):
    assert math.isclose(cam.distance, 5.2002, abs_tol=1e-3)


def test_app_camera_uniforms_match_draw_chain():
    """Production-Viewport-Ressource camera_uniforms liefert dieselbe GL-Kette."""
    app = PlaygroundApp()
    app.load_cube()
    app.update(0.016)  # viewport.sync()
    uniforms = app.viewport.render_mesh.store.data("camera_uniforms")
    expected_view = list(app.camera.build_view_matrix())
    expected_proj = list(app.camera.build_projection_matrix(app.viewport.render_mesh.aspect))
    assert len(uniforms) == 32
    assert uniforms[:16] == expected_view
    assert uniforms[16:] == expected_proj