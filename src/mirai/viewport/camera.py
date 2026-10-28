"""OrbitCamera: die eine Kamera von Viewport, Picking und GL-Uniforms.

Ortho (WP Ortho / Views, Manu V-1..V-3 2026-10-28; Vertrag: VIEWPORT_V02_ARCHITECTURE §4.1
"Addendum Ortho"): `ortho` ist ein Modus derselben Kamera, keine zweite Kamera. Halbe Bildhöhe in
Weltmaß = `distance * tan(fov/2)` (gleiche Größe am Target beim Umschalten; Dolly = Ortho-Zoom).
Ortho-Strahlen sind parallel (Richtung = `forward`), ihre Ursprünge liegen `ortho_back` hinter der
Augenebene, damit Geometrie vor/hinter dem Orbit-Auge nicht abgeschnitten wird; `project_to_screen`,
`screen_projector` und `build_projection_matrix` benutzen dieselbe Tiefe. Wer einen Strahl zu
einem Punkt braucht, nimmt `ray_origin_toward(point)` statt `eye()`; wer eine bildschirmkonstante
Größe braucht, `view_scale_at(point)`. Standardansichten: `nearest_standard_view`.

Bewusst NICHT enthalten:
- Achsen-Constraints oder ein Transform-Gizmo (Verschiebung ist frei
  entlang der Bildebene der Kamera, siehe screen_delta_to_world)
- Kamera-Animation/Interpolation

Architekturentscheidung dieser Datei: Picking (screen_to_ray,
project_to_screen) kommt bewusst OHNE Matrix-Inversion und ohne
Abhängigkeit auf pyglet/moderngl aus - stattdessen direkt über die
Kamera-Basisvektoren (forward/right/up) und das Field-of-View
konstruiert (symmetrisches Perspektiv-Frustum bzw. symmetrisches Ortho-Volumen),
ist dafür aber unabhängig von der
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


def ray_plane_point(origin: Vec3, direction: Vec3, plane_point: Vec3, plane_normal: Vec3) -> Vec3 | None:
    """Where the ray meets the plane (None when parallel); `OrbitCamera.screen_to_ray` gives the ray."""
    return _intersect_ray_plane(origin, direction, plane_point, plane_normal)


#: |cos pitch| below this = the camera looks straight down/up (Top / Bottom): `basis()` takes `right`
#: from the yaw instead of `cross(forward, world_up)`, which degenerates there. Free orbit stays within
#: ±85° (`OrbitCamera.orbit`), so only a snapped view reaches it.
POLE_EPS = 1e-6

_QUARTER = math.pi / 2.0
#: Standard views by the quarter turn of the yaw (eye on +Z = Front; Y-up, the model faces +Z).
_SIDE_VIEWS = ("Front", "Right", "Back", "Left")


def nearest_standard_view(yaw: float, pitch: float) -> tuple[str, float, float]:
    """(name, yaw, pitch) of the standard view nearest to the view (yaw, pitch) (V-1): the dominant
    axis of the view direction decides Front / Back / Left / Right / Top / Bottom. The yaw is the
    nearest multiple of 90° to `yaw` itself (not wrapped), so leaving the snap returns to angles close
    by; for Top / Bottom too, so "up" on screen is a world axis."""
    k = round(yaw / _QUARTER)
    snapped_yaw = k * _QUARTER
    cp = math.cos(pitch)
    horizontal = abs(cp) * max(abs(math.sin(yaw)), abs(math.cos(yaw)))
    if abs(math.sin(pitch)) > horizontal:
        return ("Top", snapped_yaw, _QUARTER) if pitch > 0 else ("Bottom", snapped_yaw, -_QUARTER)
    return _SIDE_VIEWS[k % 4], snapped_yaw, 0.0


@dataclass
class OrbitCamera:
    target: Vec3 = (0.0, 0.0, 0.0)
    distance: float = 6.0
    yaw: float = math.radians(45)
    pitch: float = math.radians(25)
    fov_degrees: float = 50.0
    near: float = 0.05
    far: float = 200.0
    #: Orthographic projection (V-2); toggled by `set_ortho`, set by a snapped view (`set_view`).
    ortho: bool = False

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

    def frame_on_bounds(self, center: Vec3, radius: float, margin: float = 1.25) -> None:
        """Richtet die Kamera auf einen Bounds-Mittelpunkt/-Radius aus ("Zoom to Object").

        AD-008: Portiert aus `experiments/mirai_bastel_integration_lab/adapters/
        obj_to_core.py::frame_camera_on_bounds` (dort duck-typed gegen `target`/
        `distance`; hier direkt als Methode, weil `OrbitCamera` bereits die
        konkrete Klasse ist). Nimmt bewusst Center/Radius statt eines Mesh
        entgegen — Geometrie-Abfragen (`mirai.mesh_geometry.mesh_center_and_radius`)
        bleiben von der reinen Kamera-Mathematik getrennt (diese Datei hat sonst
        keine `core`-Abhängigkeit, siehe Moduldocstring).

        Reiner View-Effekt: Setzt nur `target`/`distance`, verändert kein Mesh.
        Schon als Idee vorgemerkt in `docs/future_ideas/VIEWPORT_NAVIGATION.md`
        ("Zoom to Object").
        """
        fov_degrees = self.fov_degrees
        half_height = math.tan(math.radians(fov_degrees / 2.0))
        if half_height <= 0.0:
            distance = max(radius * 2.0, 0.5)
        else:
            distance = max((radius / half_height) * margin, 0.5)
        self.target = center
        self.distance = distance
        self.camera_revision += 1

    def set_view(self, yaw: float, pitch: float, ortho: bool | None = None) -> None:
        """Sets the orbit angles directly (a snapped standard view may use pitch ±90°, which
        `orbit()` never reaches) and optionally the projection; one revision bump."""
        self.yaw = yaw
        self.pitch = pitch
        if ortho is not None:
            self.ortho = bool(ortho)
        self.camera_revision += 1

    def set_ortho(self, ortho: bool) -> bool:
        """Ortho on/off (V-2 toggle). True = changed (revision bumped)."""
        ortho = bool(ortho)
        if ortho == self.ortho:
            return False
        self.ortho = ortho
        self.camera_revision += 1
        return True

    @property
    def ortho_back(self) -> float:
        """How far behind the eye plane the ortho rays start (and the ortho depth range begins), so
        geometry between or behind the orbit eye is neither cut nor unpickable."""
        return self.far / 2.0

    def _half_height(self) -> float:
        """Half the view height: tan(fov/2) per unit depth (persp) or in world units (ortho)."""
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        return half_h * self.distance if self.ortho else half_h

    def ray_origin_toward(self, point: Vec3) -> Vec3:
        """Where the view ray through `point` starts: the eye (persp); in ortho the point moved
        back along the view direction to the ortho ray-origin plane."""
        eye = self.eye()
        if not self.ortho:
            return eye
        forward = self.basis()[0]
        depth = v.dot(v.sub(point, eye), forward) + self.ortho_back
        return v.sub(point, v.scale(forward, depth))

    def view_scale_at(self, point: Vec3) -> float:
        """The length a screen-constant size scales with at `point`: its distance to the eye (persp,
        what the gizmo always used) or, in ortho, `distance` everywhere (the eye distance at the
        target, so toggling keeps the size there)."""
        if self.ortho:
            return self.distance
        eye = self.eye()
        return math.sqrt((point[0] - eye[0]) ** 2 + (point[1] - eye[1]) ** 2 + (point[2] - eye[2]) ** 2)

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
        if abs(math.cos(self.pitch)) < POLE_EPS:
            # Top / Bottom: cross(forward, world_up) degenerates; this is its limit from either side.
            right = (math.cos(self.yaw), 0.0, -math.sin(self.yaw))
        else:
            world_up = (0.0, 1.0, 0.0)
            right = v.normalize(v.cross(forward, world_up))
        up = v.normalize(v.cross(right, forward))
        return forward, right, up

    # ------------------------------------------------------------------
    # GL-Matrizen (Gate 5: fuer RenderMesh.camera_uniforms, siehe Docstring
    # oben). Spalten-Hauptreihenfolge in Standard-OpenGL-Konvention:
    # Punkte vor der Kamera liegen auf negativem Camera-Z, damit die
    # Projection-Matrix clip.w = -view.z > 0 erzeugt.
    # ------------------------------------------------------------------

    def build_view_matrix(self) -> list[float]:
        eye = self.eye()
        forward, right, up = self.basis()

        tx = -v.dot(eye, right)
        ty = -v.dot(eye, up)
        tz = v.dot(eye, forward)
        return [
            right[0], up[0], -forward[0], 0.0,
            right[1], up[1], -forward[1], 0.0,
            right[2], up[2], -forward[2], 0.0,
            tx, ty, tz, 1.0,
        ]

    def build_projection_matrix(self, aspect: float) -> list[float]:
        if self.ortho:
            half_h = self._half_height()
            half_w = half_h * aspect
            near, far = -self.ortho_back, self.far
            return [
                1.0 / half_w, 0.0, 0.0, 0.0,
                0.0, 1.0 / half_h, 0.0, 0.0,
                0.0, 0.0, -2.0 / (far - near), 0.0,
                0.0, 0.0, -(far + near) / (far - near), 1.0,
            ]
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
        if self.ortho:
            # Parallel rays: the screen point on the eye plane, pulled back by `ortho_back`.
            half_h *= self.distance
            half_w *= self.distance
            origin = v.add(
                self.eye(),
                v.add(
                    v.add(v.scale(right, ndc_x * half_w), v.scale(up, ndc_y * half_h)),
                    v.scale(forward, -self.ortho_back),
                ),
            )
            return origin, forward
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
        Weltpunkts, oder None, wenn der Punkt vor/auf der Nahebene liegt
        (Ortho: vor/auf der Ebene der Strahlursprünge, `ortho_back` hinter dem Auge)."""
        eye = self.eye()
        forward, right, up = self.basis()
        rel = v.sub(point, eye)
        cam_z = v.dot(rel, forward)
        if self.ortho:
            if cam_z <= -self.ortho_back:
                return None
            cam_x = v.dot(rel, right)
            cam_y = v.dot(rel, up)
            half_h = self._half_height()
            half_w = half_h * (width / height)
            ndc_x = cam_x / half_w
            ndc_y = cam_y / half_h
            return (ndc_x + 1.0) * 0.5 * width, (ndc_y + 1.0) * 0.5 * height
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

    def screen_projector(self, width: int, height: int):
        """`project_to_screen` as a function of the point alone, with eye, basis and
        frustum computed once (WP-VIEW-PERF-01: `PickCache.refresh` projects every vertex;
        per call they cost ~5x the projection itself). The same operations in the same
        order, so every result is bit-identical to `project_to_screen` - keep the two in
        step (tests/test_camera.py)."""
        ex, ey, ez = self.eye()
        (fx, fy, fz), (rx, ry, rz), (ux, uy, uz) = self.basis()
        if self.ortho:
            back = -self.ortho_back
            oh = self._half_height()
            ow = oh * (width / height)

            def project_ortho(point: Vec3) -> tuple[float, float] | None:
                px = point[0] - ex
                py = point[1] - ey
                pz = point[2] - ez
                cam_z = px * fx + py * fy + pz * fz
                if cam_z <= back:
                    return None
                cam_x = px * rx + py * ry + pz * rz
                cam_y = px * ux + py * uy + pz * uz
                ndc_x = cam_x / ow
                ndc_y = cam_y / oh
                return (ndc_x + 1.0) * 0.5 * width, (ndc_y + 1.0) * 0.5 * height

            return project_ortho
        near = self.near
        aspect = width / height
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        half_w = half_h * aspect

        def project(point: Vec3) -> tuple[float, float] | None:
            px = point[0] - ex
            py = point[1] - ey
            pz = point[2] - ez
            cam_z = px * fx + py * fy + pz * fz
            if cam_z <= near:
                return None
            cam_x = px * rx + py * ry + pz * rz
            cam_y = px * ux + py * uy + pz * uz
            ndc_x = cam_x / (cam_z * half_w)
            ndc_y = cam_y / (cam_z * half_h)
            return (ndc_x + 1.0) * 0.5 * width, (ndc_y + 1.0) * 0.5 * height

        return project

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
