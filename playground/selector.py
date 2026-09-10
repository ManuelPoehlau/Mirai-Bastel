"""PlaygroundSelector — headless Click-to-Selection-Bridge für AP-03 Phase 1.

Verbindet Screen-Koordinaten mit core.Selection über die Production-Picking-API.
Kein GL, kein pyglet, vollständig headless testbar.

Phase 1: Single Select (Replace). Add/Remove/Toggle kommen in Phase 2.

Konvention: sx/sy in pyglet-Koordinaten (y=0 unten).
"""

from __future__ import annotations

from playground._paths import ensure_paths

ensure_paths()

from core.selection import SelectionMode  # noqa: E402
from mirai.viewport.picking import pick_face  # noqa: E402

CLICK_THRESHOLD: float = 5.0  # Pixel (Manhattan-Summe aus on_mouse_drag)


def handle_face_click(
    camera,
    mesh,
    selection,
    sx: float,
    sy: float,
    width: int,
    height: int,
) -> bool:
    """Single Face Select (Replace-Modus).

    Picked Face → selection.set({fid}).
    Miss → selection.clear() falls nicht schon leer.
    Gibt True zurück wenn sich selection geändert hat.
    """
    fid = pick_face(camera, mesh, sx, sy, width, height)
    if fid is not None:
        selection.mode = SelectionMode.FACE
        selection.set({fid})
        return True
    if not selection.is_empty():
        selection.clear()
        return True
    return False
