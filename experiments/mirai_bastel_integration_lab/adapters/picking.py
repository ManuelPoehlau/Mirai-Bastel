"""Screen-Space-Vertex-Picking — seit WP-IL-01 an Production delegiert.

Production-Lieferant: `src/mirai/viewport/picking.py::pick_nearest_vertex`
(pyglet-/GPU-frei, Core-Query-API, Pixel-Distanz, Default-Threshold 14 px).
Das ist funktional identisch zur früheren Lab-eigenen Implementierung
(V1-Adaption), die als Duplikat von Production-Code entfernt wurde
(Audit §C, Zeile „Picking“).

Dieses Modul arbeitet gegen `src.core.Mesh` (Core-IDs) und rein auf
Pixel-Parametern — bewusst pyglet-frei.
"""

from __future__ import annotations

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from core.ids import VertexId  # noqa: E402  (Production-Importpfad)
from core.mesh import Mesh  # noqa: E402

from mirai.viewport.picking import pick_nearest_vertex  # noqa: E402,F401

DEFAULT_PIXEL_THRESHOLD = 14.0


def pick_vertex(
    camera,
    core_mesh: Mesh,
    screen_x: float,
    screen_y: float,
    width: int,
    height: int,
    threshold_px: float = DEFAULT_PIXEL_THRESHOLD,
) -> VertexId | None:
    """Nächsten Core-Vertex unter dem Cursor (Pixel-Distanz) zurückgeben.

    Delegation an `mirai.viewport.picking.pick_nearest_vertex`. Konventionen
    identisch zur bisherigen Lab-Implementierung: y wächst nach oben
    (GL/pyglet-Konvention); die Umrechnung von Fenster-Pixeln passiert an der
    Aufrufstelle (pyglet liefert Ursprung unten links).
    """
    return pick_nearest_vertex(
        camera,
        core_mesh,
        screen_x,
        screen_y,
        width,
        height,
        max_pixel_distance=threshold_px,
    )