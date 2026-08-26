"""Reine Mathe-/Logik-Tests für Kamera und Picking.

Laufen bewusst OHNE Fenster/GPU, weil camera.py und picking.py
unabhängig von pyglet/moderngl gehalten sind (siehe viewport/camera.py
Modul-Docstring). Das ist der Teil dieses Milestones, der in dieser
Sandbox tatsächlich automatisiert geprüft werden konnte - die
Fenster-/Render-/Input-Schicht (app.py) braucht einen echten Lauf auf
einer Maschine mit Display/GPU.

Ausführen mit: python -m tests.test_camera_picking  (aus diesem Ordner)
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from mirai_bastel_core import Mesh  # noqa: E402

from viewport import vecmath as v  # noqa: E402
from viewport.camera import OrbitCamera  # noqa: E402
from viewport.picking import pick_nearest_vertex  # noqa: E402

_failures = 0


def check(label: str, condition: bool) -> None:
    global _failures
    status = "PASS" if condition else "FAIL"
    if not condition:
        _failures += 1
    print(f"[{status}] {label}")


def approx(a: float, b: float, eps: float = 1e-4) -> bool:
    return abs(a - b) < eps


def _closest_point_on_ray_to_plane_point(origin, direction, plane_point, plane_normal):
    denom = v.dot(direction, plane_normal)
    t = v.dot(v.sub(plane_point, origin), plane_normal) / denom
    return v.add(origin, v.scale(direction, t))


def test_eye_distance_matches_configured_distance() -> None:
    print("\n--- Kamera: eye() hat die konfigurierte Distanz zum target ---")
    cam = OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.0)
    d = v.distance(cam.eye(), cam.target)
    check("Distanz Kamera<->Target entspricht cam.distance", approx(d, 5.0))


def test_target_projects_to_screen_center() -> None:
    print("\n--- Projektion: das Kamera-Ziel landet auf der Bildschirmmitte ---")
    cam = OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.0)
    w, h = 800, 600
    projected = cam.project_to_screen(cam.target, w, h)
    check("Ziel-Projektion existiert (liegt vor der Kamera)", projected is not None)
    if projected is not None:
        sx, sy = projected
        check("x liegt auf der Bildschirmmitte", approx(sx, w / 2, eps=1e-2))
        check("y liegt auf der Bildschirmmitte", approx(sy, h / 2, eps=1e-2))


def test_screen_to_ray_center_points_toward_target() -> None:
    print("\n--- Ray-Casting: Bildschirmmitte zeigt zum target ---")
    cam = OrbitCamera(target=(1.0, 2.0, 3.0), distance=6.0)
    w, h = 800, 600
    _origin, direction = cam.screen_to_ray(w / 2, h / 2, w, h)
    forward, _right, _up = cam.basis()
    check(
        "Ray-Richtung durch die Bildschirmmitte entspricht der Blickrichtung",
        approx(v.dot(direction, forward), 1.0, eps=1e-3),
    )


def test_project_and_unproject_roundtrip() -> None:
    print("\n--- Roundtrip: projizierter Punkt + zurückgeworfener Ray treffen sich wieder ---")
    cam = OrbitCamera(
        target=(0.0, 0.0, 0.0), distance=8.0, yaw=math.radians(30), pitch=math.radians(15)
    )
    w, h = 1024, 768
    point = (0.7, -0.4, 0.2)
    projected = cam.project_to_screen(point, w, h)
    check("Punkt ist projizierbar", projected is not None)
    if projected is not None:
        sx, sy = projected
        origin, direction = cam.screen_to_ray(sx, sy, w, h)
        forward, _right, _up = cam.basis()
        hit = _closest_point_on_ray_to_plane_point(origin, direction, point, forward)
        check(
            "der zurückgeworfene Ray trifft (nahezu) den ursprünglichen Punkt",
            v.distance(hit, point) < 1e-3,
        )


def test_pick_nearest_vertex_hits_correct_vertex() -> None:
    print("\n--- Picking: nächster Vertex wird innerhalb der Toleranz gefunden ---")
    mesh = Mesh()
    v_center = mesh.add_vertex((0.0, 0.0, 0.0))
    v_far = mesh.add_vertex((5.0, 5.0, 5.0))
    mesh.add_vertex((-5.0, -5.0, -5.0))
    cam = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0)
    w, h = 800, 600
    projected = cam.project_to_screen((0.0, 0.0, 0.0), w, h)
    assert projected is not None
    sx, sy = projected

    hit = pick_nearest_vertex(cam, mesh, sx, sy, w, h, max_pixel_distance=14.0)
    check("Klick nahe (0,0,0) trifft genau diesen Vertex", hit == v_center)

    hit_far = pick_nearest_vertex(cam, mesh, sx + 300, sy + 300, w, h, max_pixel_distance=14.0)
    check("Klick weit weg von allen Vertices trifft keinen (oder nicht den falschen)",
          hit_far is None or hit_far != v_far)


def test_screen_delta_to_world_moves_along_view_plane() -> None:
    print("\n--- Drag-Delta: Mausbewegung wird in ein Weltraum-Delta übersetzt ---")
    cam = OrbitCamera(target=(0.0, 0.0, 0.0), distance=6.0)
    w, h = 800, 600
    point = (0.0, 0.0, 0.0)
    delta = cam.screen_delta_to_world(point, dx=40, dy=0, width=w, height=h)
    check("horizontales Maus-Delta erzeugt ein nicht-triviales Weltraum-Delta", v.length(delta) > 1e-3)
    zero_delta = cam.screen_delta_to_world(point, dx=0, dy=0, width=w, height=h)
    check("kein Maus-Delta erzeugt (nahezu) kein Weltraum-Delta", v.length(zero_delta) < 1e-6)


def run_all() -> None:
    tests = [
        test_eye_distance_matches_configured_distance,
        test_target_projects_to_screen_center,
        test_screen_to_ray_center_points_toward_target,
        test_project_and_unproject_roundtrip,
        test_pick_nearest_vertex_hits_correct_vertex,
        test_screen_delta_to_world_moves_along_view_plane,
    ]
    for t in tests:
        t()
    print()
    if _failures:
        print(f"{_failures} Check(s) fehlgeschlagen.")
        sys.exit(1)
    print("Alle Kamera-/Picking-Checks validiert.")


if __name__ == "__main__":
    run_all()
