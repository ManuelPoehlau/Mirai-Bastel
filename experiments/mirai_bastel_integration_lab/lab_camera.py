"""Lab-Kamera: V0.2 `OrbitCamera` + Picking-/World-Delta-Ergänzungen.

Wiederverwendung:
- Basiszustand, Orbit/Dolly und View-/Projektions-Matrizen kommen direkt von
  der V0.2-Kamera (`experiments/mirai_bastel_viewport_V02/camera.py`).
- Die Picking-/Welt-Delta-Mathematik (`project_to_screen`, `screen_to_ray`,
  `screen_delta_to_world`, Basis-Vektoren) ist aus der V1-Viewport-Kamera
  adaptiert (`experiments/mirai_bastel_viewport_V1/viewport/camera.py`) —
  dort getestet und pyglet-frei. Beide Kameras verwenden dieselbe
  eye/target/yaw/pitch-Konvention, sodass Rendering und Picking konsistent
  bleiben und Eye-Punkte/Basisvektoren übereinstimmen.

Integration-Lücke (im README dokumentiert):
  Die V0.2-Demonstrator-Kamera ruft `camera.project_to_screen(...)` auf,
  das die V0.2-Kamera selbst gar nicht anbietet. Das Lab behebt das additiv
  hier (Subklasse), ohne die V0.2-Kamera zu verändern.

Rendering-Fix (im README dokumentiert):
  Die V0.2-View-Matrix schreibt +forward in die dritte Matrix-Zeile
  (Links-Hand-Konvention: Front-Punkte auf positivem Camera-Z), die
  V0.2-Projektion ist aber Standard-GL (clip.w = -view.z). Front-Geometrie
  landet damit bei clip.w < 0 und wird vollständig geclippt -> schwarzer
  Viewport (Ursprung bei yaw=45°/pitch=25°/dist=8: view.z=+8, clip.w=-8).
  Diese Klasse überschreibt `build_view_matrix` mit der gluLookAt-Konvention
  (-forward in Zeile 3). Das Picking (`project_to_screen`/`screen_to_ray`)
  definiert cam_z = dot(rel, forward) > 0 als "vor der Kamera" und bleibt
  unverändert — mit der korrigierten View-Matrix gilt exakt
  NDC.xy = cam.xy / (cam_z * half_w bzw. half_h), d. h. Render-Pipeline und
  Picking verwenden dieselbe Kamera-Konvention. V0.2 bleibt unberührt.
"""

from __future__ import annotations

import math

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from experiments.mirai_bastel_viewport_V02.camera import OrbitCamera, _cross, _dot, _normalize, _sub  # noqa: E402

Vec3 = tuple[float, float, float]


class LabOrbitCamera(OrbitCamera):
    """V0.2-Orbit-Kamera plus Projektion/Ray/World-Delta (siehe Modul-Doc)."""

    # -- Basis-Vektoren (identische Konvention wie V1 camera.py) -------------
    def basis(self) -> tuple[Vec3, Vec3, Vec3]:
        """(forward, right, up) — normalisierte Kamera-Basisvektoren."""
        forward = _normalize(_sub(self.target, self.eye()))
        world_up = (0.0, 1.0, 0.0)
        right = _normalize(_cross(forward, world_up))
        up = _normalize(_cross(right, forward))
        return forward, right, up

    # -- View-Matrix (GL-korrigiert, siehe Modul-Doc) ------------------------
    def build_view_matrix(self) -> list[float]:
        """View-Matrix in Standard-GL/gluLookAt-Konvention (Zeile 3 = -forward).

        Override der V0.2-Matrix (+forward), deren Front-Geometrie bei der
        GL-Projektion (clip.w = -view.z) negatives clip.w erhält und daher
        komplett geclippt wird (schwarzer Viewport). Spalten-Hauptreihenfolge,
        identisches Uniform-Layout wie die V0.2-Matrix.
        """
        eye = self.eye()
        forward, right, up = self.basis()
        tx = -_dot(eye, right)
        ty = -_dot(eye, up)
        tz = _dot(eye, forward)
        return [
            right[0], up[0], -forward[0], 0.0,
            right[1], up[1], -forward[1], 0.0,
            right[2], up[2], -forward[2], 0.0,
            tx, ty, tz, 1.0,
        ]

    # -- Projektion ----------------------------------------------------------
    def project_to_screen(
        self, point: Vec3, width: int, height: int
    ) -> tuple[float, float] | None:
        """Pixel-Koordinaten (Ursprung unten links) oder None hinter Nahebene."""
        eye = self.eye()
        forward, right, up = self.basis()
        rel = _sub(point, eye)
        cam_z = _dot(rel, forward)
        if cam_z <= self.near:
            return None
        cam_x = _dot(rel, right)
        cam_y = _dot(rel, up)
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        half_w = half_h * (width / height)
        ndc_x = cam_x / (cam_z * half_w)
        ndc_y = cam_y / (cam_z * half_h)
        return (ndc_x + 1.0) * 0.5 * width, (ndc_y + 1.0) * 0.5 * height

    def screen_to_ray(
        self, screen_x: float, screen_y: float, width: int, height: int
    ) -> tuple[Vec3, Vec3]:
        """(origin, direction) eines Welt-Rays durch den Bildschirmpunkt."""
        ndc_x = (2.0 * screen_x / width) - 1.0
        ndc_y = (2.0 * screen_y / height) - 1.0
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        half_w = half_h * (width / height)
        forward, right, up = self.basis()
        offset = (
            right[0] * ndc_x * half_w + up[0] * ndc_y * half_h,
            right[1] * ndc_x * half_w + up[1] * ndc_y * half_h,
            right[2] * ndc_x * half_w + up[2] * ndc_y * half_h,
        )
        direction = _normalize(
            (forward[0] + offset[0], forward[1] + offset[1], forward[2] + offset[2])
        )
        return self.eye(), direction

    # -- Welt-Delta für Drags (V1-`screen_delta_to_world`-Semantik) ----------
    def screen_delta_to_world(
        self, point: Vec3, dx: float, dy: float, width: int, height: int
    ) -> Vec3:
        """Pixel-Delta (dx, dy) → Welt-Delta an der Tiefe von `point`."""

        def _intersect_ray_plane(
            origin: Vec3, direction: Vec3, plane_point: Vec3, plane_normal: Vec3
        ) -> Vec3 | None:
            denom = _dot(direction, plane_normal)
            if abs(denom) < 1e-9:
                return None
            t = _dot(_sub(plane_point, origin), plane_normal) / denom
            return (
                origin[0] + direction[0] * t,
                origin[1] + direction[1] * t,
                origin[2] + direction[2] * t,
            )

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
        return _sub(p_b, p_a)

    # -- Pan (Pixel-Semantik wie V1-`camera.pan`) ----------------------------
    def pan_px(self, dx_px: float, dy_px: float, width: int, height: int) -> None:
        """Verschiebt das Orbit-Ziel entlang der Kamera-Bildebene."""
        if height <= 0:
            return
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        world_per_px = 2.0 * self.distance * half_h / height
        _forward, right, up = self.basis()
        self.target = _sub(
            self.target,
            (
                right[0] * dx_px * world_per_px + up[0] * dy_px * world_per_px,
                right[1] * dx_px * world_per_px + up[1] * dy_px * world_per_px,
                right[2] * dx_px * world_per_px + up[2] * dy_px * world_per_px,
            ),
        )