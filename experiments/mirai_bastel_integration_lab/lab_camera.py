"""Lab-Kamera: Production-`OrbitCamera` + GL-View-Matrix-Override (WP-IL-01).

Wiederverwendung seit WP-IL-01 (2026-09-08):

- Basiszustand, Orbit/Dolly/Pan (Pixel-Semantik), Basisvektoren, Picking-
  Mathematik (`project_to_screen`, `screen_to_ray`, `screen_delta_to_world`)
  und `build_projection_matrix` kommen unverändert aus der Production-Kamera
  (`src/mirai/viewport/camera.py::OrbitCamera`). Die früher hier gepflegten
  V1-Adaptionen sind inzwischen Production-Standard und wurden entfernt.
- Die Kamera ist DIE eine Kamera-Instanz pro Lab-Objekt-Kette; sie wird an
  den Production-Viewport über `bind_camera` gebunden (Duck-Typing, Gate 7).

Einziges Override (dokumentierte Production-Grenze, Audit §A.1):

  Die Production-View-Matrix schreibt +forward in die dritte Matrix-Zeile
  (Links-Hand-Konvention: Front-Punkte auf positivem Camera-Z), die
  Production-Projektion ist aber Standard-GL (clip.w = -view.z). Folge:
  clip.w < 0 für alles vor der Kamera → komplettes Clipping → schwarzer
  Viewport. Diese Klasse überschreibt `build_view_matrix` mit der
  gluLookAt-Konvention (-forward in Zeile 3). Picking und Uniforms lesen
  dieselbe Instanz und bleiben konsistent (NDC.xy = cam.xy/(cam_z·half)).
  Eine Korrektur in der Production ist eine eigene Architektur-
  entscheidung (Out of Scope von WP-IL-01; Regression-Tests in
  `tests/test_camera_picking.py`).
"""

from __future__ import annotations

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from mirai.viewport import vecmath as v  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402


class LabOrbitCamera(OrbitCamera):
    """Production-OrbitCamera plus GL-View-Matrix-Korrektur (siehe Modul-Doc)."""

    # -- View-Matrix (GL-korrigiert, siehe Modul-Doc) ------------------------
    def build_view_matrix(self) -> list[float]:
        """View-Matrix in Standard-GL/gluLookAt-Konvention (Zeile 3 = -forward).

        Override der Production-Matrix (+forward), deren Front-Geometrie bei
        der GL-Projektion (clip.w = -view.z) negatives clip.w erhält und
        daher komplett geclippt wird (schwarzer Viewport).
        Spalten-Hauptreihenfolge, identisches Uniform-Layout wie die
        Production-Matrix.
        """
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
