"""Screen-Space-Vertrex-Picking für das Integration Lab (CPU, headless).

Laufzeit-Fundament ist die Projektions-/Ray-Mathematik der V1-Viewport-
Kamera (`experiments/mirai_bastel_viewport_V1/viewport/camera.py`:
`project_to_screen`, `screen_to_ray`, `screen_delta_to_world`), die dort
bereits durch `tests/test_camera_picking.py` abgesichert ist. Die V0.2-Kamera
besitzt diese Methoden NICHT (Integration-Lücke, im README dokumentiert) —
die Lab-Kamera `lab_camera.LabOrbitCamera` ergänzt sie additiv.

Dieses Modul arbeitet gegen `src.core.Mesh` (Core-IDs) + Index-Map und rein
auf Pixel-Parametern — bewusst pyglet-frei.
"""

from __future__ import annotations

import math

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from src.core.ids import VertexId  # noqa: E402
from src.core.mesh import Mesh  # noqa: E402

from adapters.core_to_render import CoreVertexIndexMap  # noqa: E402

DEFAULT_PIXEL_THRESHOLD = 14.0


def pick_vertex(
    camera,
    core_mesh: Mesh,
    index_map: CoreVertexIndexMap,
    screen_x: float,
    screen_y: float,
    width: int,
    height: int,
    threshold_px: float = DEFAULT_PIXEL_THRESHOLD,
) -> VertexId | None:
    """Nächsten Core-Vertex unter dem Cursor (Pixel-Distanz) zurückgeben.

    Konventionen identisch zur V1-Kamera/v0.2-Demonstrator: y wächst nach
    oben (GL/pyglet-Konvention); die Umrechnung von Fenster-Pixeln passiert
    an der Aufrufstelle (pyglet liefert Ursprung unten links).
    """
    best: VertexId | None = None
    best_dist = threshold_px
    for vid in core_mesh.all_vertex_ids():
        projected = camera.project_to_screen(
            core_mesh.vertex_position(vid), width, height
        )
        if projected is None:
            continue
        px, py = projected
        dist = math.hypot(px - screen_x, py - screen_y)
        if dist < best_dist:
            best_dist = dist
            best = vid
    return best