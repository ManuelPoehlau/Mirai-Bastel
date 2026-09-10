"""Playground-Kamera: Production-`OrbitCamera` + GL-View-Matrix-Korrektur.

Dokumentierter Befund (Integration-Lab-Reconciliation-Audit §A.1,
`docs/research/viewport/production_camera_gl_convention.md`):

  Die Production-View-Matrix (`src/mirai/viewport/camera.py::OrbitCamera.
  build_view_matrix`) schreibt +forward in die dritte Matrix-Zeile
  (Links-Hand-Konvention: Front-Punkte auf positivem Camera-Z). Die
  Production-Projektion ist dagegen Standard-OpenGL (`clip.w = -view.z`,
  erwartet Front-Punkte auf NEGATIVEM Camera-Z). Folge in einem echten
  GL-Draw-Pfad: clip.w < 0 für alles vor der Kamera → komplettes Clipping
  → schwarzer Viewport.

Diese Klasse überschreibt NUR `build_view_matrix()` mit der gluLookAt-
Konvention (-forward in Zeile 3) — exakt der im Integration Lab bewährte,
dokumentierte Fix (`experiments/mirai_bastel_integration_lab/lab_camera.py`).

Bewusst OHNE Eingriff in die Production:

- `OrbitCamera` (src/mirai) wird NICHT verändert (Architecture Map: 🟢 REUSE).
- Alle Kamera-/Picking-Mathematik (`eye`, `basis`, `orbit`, `dolly`, `pan`,
  `screen_to_ray`, `project_to_screen`, `screen_delta_to_world`) bleibt vom
  Production-Code geerbt und wird hier NICHT überschrieben.
- Nur der für GL bestimmte Matrix-Ausgang wird an der Playground-GL-Grenze
  adaptiert. Der Playground-Draw liest weiterhin von derselben Kamera-
  Instanz (kein Zustands-Splitting, kanonischer Pfad wie im Lab).
"""

from __future__ import annotations

from playground._paths import ensure_paths

ensure_paths()

from mirai.viewport import vecmath as v  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402


class PlaygroundCamera(OrbitCamera):
    """Production-`OrbitCamera` plus GL-View-Matrix-Korrektur (siehe Modul-Doc)."""

    # -- View-Matrix (GL-korrigiert, siehe Modul-Doc) ------------------------
    def build_view_matrix(self) -> list[float]:
        """View-Matrix in Standard-GL/gluLookAt-Konvention (Zeile 3 = -forward).

        Override der Production-Matrix (+forward), deren Front-Geometrie bei
        der GL-Projektion (`clip.w = -view.z`) negatives clip.w erhält und
        damit komplett geclippt würde (schwarzer Viewport). Identisch zur
        im Integration Lab dokumentierten Korrektur. Spalten-Hauptreihenfolge,
        identisches Uniform-Layout wie die Production-Matrix.
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