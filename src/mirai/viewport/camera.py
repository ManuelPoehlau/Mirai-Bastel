"""OrbitCamera: minimale Kamera für den V1-Viewport-Praxistest.

Bewusst NICHT enthalten (Scope-Absprache im Chat vor diesem Milestone):
- Ortho-Modus / Front-Back-Left-Right-Snapping
- Achsen-Constraints oder ein Transform-Gizmo (Verschiebung ist frei
  entlang der Bildebene der Kamera, siehe screen_delta_to_world)
- Kamera-Animation/Interpolation

Architekturentscheidung dieser Datei: Picking (screen_to_ray,
project_to_screen) kommt bewusst OHNE Matrix-Inversion und ohne
Abhängigkeit auf pyglet/moderngl aus - stattdessen direkt über die
Kamera-Basisvektoren (forward/right/up) und das Field-of-View
konstruiert. Das gilt nur für ein symmetrisches Perspektiv-Frustum
(V1 hat keinen Ortho-Modus), ist dafür aber unabhängig von der
konkreten Render-Library testbar (siehe tests/test_camera_picking.py).
Die tatsächlichen Render-Matrizen für die GPU werden separat in
app.py aufgebaut (dort, wo ohnehin schon eine Render-Library-
Abhängigkeit besteht) und müssen mit denselben fov/aspect/basis-Werten
konsistent bleiben, damit Picking und Darstellung zueinander passen.

Gate 5 Ergänzung (VIEWPORT_V02_ARCHITECTURE.md §4.1, §7): `build_view_matrix()`
/ `build_projection_matrix(aspect)` sowie `camera_revision` wurden additiv
ergänzt, damit diese eine Kamera-Instanz sowohl für Tool-Picking (Gate 3/4)
als auch für die GL-Uniform-Erzeugung in `src.viewport.RenderMesh`
(duck-typed, siehe dortiger Paket-Docstring) verwendet werden kann - statt
eine zweite, parallele Kamera-Repräsentation einzuführen. `src.viewport`
importiert diese Klasse NICHT (keine Abhängigkeit auf `src.mirai`); die
Bindung passiert an der Integrationsstelle (`Application`/Entry-Point) über
Duck-Typing.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import vecmath as v
from .vecmath import Vec3


def _intersect_ray_plane(
    origin: Vec3, direction: Vec3, plane_point: Vec3, plane_normal: Vec3
) -> Vec3 | None:
    denom = v.dot(direction, plane_normal)
    if abs(denom) < 1e-9:
        return None
    t = v.dot(v.sub(plane_point, origin), plane_normal) / denom
    return v.add(origin, v.scale(direction, t))


@dataclass
class OrbitCamera:
    target: Vec3 = (0.0, 0.0, 0.0)
    distance: float = 6.0
    yaw: float = math.radians(45)
    pitch: float = math.radians(25)
    fov_degrees: float = 50.0
    near: float = 0.05
    far: float = 200.0

    # Gate 5: monoton wachsende Revision, NUR fürs Reporting/Benchmarking.
    # Wird bei orbit()/dolly()/pan() erhöht. Bewusst KEINE Kopplung an
    # Mesh-/Geometry-Zustand - Camera-Changes duerfen laut V0.2-Architektur
    # NIE eine Geometry-Invalidierung ausloesen (siehe RenderMesh._sync_camera,
    # das ausschliesslich die camera_uniforms-Ressource anfasst).
    camera_revision: int = field(default=0, compare=False)

    def orbit(self, d_yaw: float, d_pitch: float) -> None:
        self.yaw += d_yaw
        max_pitch = math.radians(85)
        self.pitch = max(-max_pitch, min(max_pitch, self.pitch + d_pitch))
        self.camera_revision += 1

    def dolly(self, factor: float) -> None:
        self.distance = max(0.5, min(200.0, self.distance * factor))
        self.camera_revision += 1

    def eye(self) -> Vec3:
        cp = math.cos(self.pitch)
        return (
            self.target[0] + self.distance * cp * math.sin(self.yaw),
            self.target[1] + self.distance * math.sin(self.pitch),
            self.target[2] + self.distance * cp * math.cos(self.yaw),
        )

    def basis(self) -> tuple[Vec3, Vec3, Vec3]:
        """(forward, right, up) - normalisierte Kamera-Basisvektoren."""
        forward = v.normalize(v.sub(self.target, self.eye()))
        world_up = (0.0, 1.0, 0.0)
        right = v.normalize(v.cross(forward, world_up))
        up = v.normalize(v.cross(right, forward))
        return forward, right, up

    # ------------------------------------------------------------------
    # GL-Matrizen (Gate 5: fuer RenderMesh.camera_uniforms, siehe Docstring
    # oben). Spalten-Hauptreihenfolge (GL-Konvention), identisch zur im
    # V0.2-Proof verifizierten Mathematik
    # (experiments/mirai_bastel_viewport_V02/camera.py).
    # ------------------------------------------------------------------

    def build_view_matrix(self) -> list[float]:
        eye = self.eye()
        forward, right, up = self.basis()

        tx = -v.dot(eye, right)
        ty = -v.dot(eye, up)
        tz = -v.dot(eye, forward)
        return [
            right[0], up[0], forward[0], 0.0,
            right[1], up[1], forward[1], 0.0,
            right[2], up[2], forward[2], 0.0,
            tx, ty, tz, 1.0,
        ]

    def build_projection_matrix(self, aspect: float) -> list[float]:
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        half_w = half_h * aspect
        m00 = 1.0 / half_w
        m11 = 1.0 / half_h
        m22 = -(self.far + self.near) / (self.far - self.near)
        m23 = -1.0
        m32 = -(2.0 * self.far * self.near) / (self.far - self.near)
        return [
            m00, 0.0, 0.0, 0.0,
            0.0, m11, 0.0, 0.0,
            0.0, 0.0, m22, m23,
            0.0, 0.0, m32, 0.0,
        ]

    # ------------------------------------------------------------------
    # Picking (siehe Modul-Docstring: bewusst ohne Matrix-Invertierung)
    # ------------------------------------------------------------------

    def screen_to_ray(
        self, sx: float, sy: float, width: int, height: int
    ) -> tuple[Vec3, Vec3]:
        """(origin, direction) eines Welt-Rays durch den Bildschirmpunkt.

        Pixel-Konvention: Ursprung unten links, y wächst nach oben (GL-/
        pyglet-Konvention). Wenn die konkrete Render-Library eine andere
        Konvention verwendet (z. B. Ursprung oben links), muss die
        Umrechnung an der Aufrufstelle in app.py passieren, nicht hier.
        """
        ndc_x = (2.0 * sx / width) - 1.0
        ndc_y = (2.0 * sy / height) - 1.0
        aspect = width / height
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        half_w = half_h * aspect
        forward, right, up = self.basis()
        direction = v.normalize(
            v.add(
                forward,
                v.add(v.scale(right, ndc_x * half_w), v.scale(up, ndc_y * half_h)),
            )
        )
        return self.eye(), direction

    def project_to_screen(
        self, point: Vec3, width: int, height: int
    ) -> tuple[float, float] | None:
        """Pixel-Koordinaten (gleiche Konvention wie screen_to_ray) eines
        Weltpunkts, oder None, wenn der Punkt vor/auf der Nahebene liegt."""
        eye = self.eye()
        forward, right, up = self.basis()
        rel = v.sub(point, eye)
        cam_z = v.dot(rel, forward)
        if cam_z <= self.near:
            return None
        cam_x = v.dot(rel, right)
        cam_y = v.dot(rel, up)
        aspect = width / height
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        half_w = half_h * aspect
        ndc_x = cam_x / (cam_z * half_w)
        ndc_y = cam_y / (cam_z * half_h)
        return (ndc_x + 1.0) * 0.5 * width, (ndc_y + 1.0) * 0.5 * height

    def pan(self, dx_px: float, dy_px: float, width: int, height: int) -> None:
        """Verschiebt das Orbit-Ziel entlang der Kamera-Bildebene (Pan/Track).

        Konvention (siehe WP-01-BUGS_AND_TODOS): Das sichtbare Objekt folgt
        der Mausbewegung wie beim Greifen — konsistent zur Orbit-Richtung
        („Ziehen nach unten dreht das Modell nach unten"). Positives `dy_px`
        bewegt das Ziel deshalb nach UNTEN, nicht nach oben.

        `dx_px`/`dy_px` sind Pixel-Mausbewegungen in der GL-Konvention
        (Ursprung unten links). Das Pan-Tempo ist von der aktuellen Distanz
        und dem FOV abhängig, damit Nah-/Fern-Zoom ähnlich anfühlt.
        """
        if height <= 0:
            return
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        world_per_px = 2.0 * self.distance * half_h / height
        _forward, right, up = self.basis()
        self.target = v.sub(
            self.target,
            v.add(
                v.scale(right, dx_px * world_per_px),
                v.scale(up, dy_px * world_per_px),
            ),
        )
        self.camera_revision += 1

    def screen_delta_to_world(
        self, point: Vec3, dx: float, dy: float, width: int, height: int
    ) -> Vec3:
        """Übersetzt eine Pixel-Mausbewegung (dx, dy) in ein Weltraum-Delta
        für `point`, frei entlang der Bildebene der Kamera (keine
        Achsen-Constraints - siehe Modul-Docstring).
        """
        projected = self.project_to_screen(point, width, height)
        if projected is None:
            return (0.0, 0.0, 0.0)
        sx, sy = projected
        origin_a, dir_a = self.screen_to_ray(sx, sy, width, height)
        origin_b, dir_b = self.screen_to_ray(sx + dx, sy + dy, width, height)
        forward, _, _ = self.basis()
        p_a = _intersect_ray_plane(origin_a, dir_a, point, forward)
        p_b = _intersect_ray_plane(origin_b, dir_b, point, forward)
        if p_a is None or p_b is None:
            return (0.0, 0.0, 0.0)
        return v.sub(p_b, p_a)
