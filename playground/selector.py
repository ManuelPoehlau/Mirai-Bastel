"""PlaygroundSelector — headless Click-to-Selection-Bridge für AP-03.

Phase 1: handle_face_click (Replace)
Phase 2: SelectMode-Enum + handle_face_click_modifier (A) + handle_face_click_toggle (B)
         + dispatch_face_click (zentraler Einstiegspunkt für das Window)

Kein GL, kein pyglet, vollständig headless testbar.
Konvention: sx/sy in pyglet-Koordinaten (y=0 unten).
"""

from __future__ import annotations

from enum import Enum, auto

from playground._paths import ensure_paths

ensure_paths()

from core.selection import SelectionMode  # noqa: E402
from mirai.viewport.picking import pick_face  # noqa: E402

CLICK_THRESHOLD: float = 5.0  # Pixel (Manhattan-Summe aus on_mouse_drag)


class SelectMode(Enum):
    """Welche Klick-Philosophie gerade aktiv ist."""
    REPLACE  = auto()   # Klick = Replace (Phase 1 Baseline)
    MODIFIER = auto()   # Shift=Add, Ctrl=Remove, Alt=Toggle (Variante A)
    TOGGLE   = auto()   # Jeder Klick togglet (Variante B)
    BOX      = auto()   # LMB-Drag = Box-Select (Variante C)


# ---------------------------------------------------------------------------
# Phase 1 — Replace
# ---------------------------------------------------------------------------

def handle_face_click(
    camera,
    mesh,
    selection,
    sx: float,
    sy: float,
    width: int,
    height: int,
) -> bool:
    """Single Face Select (Replace).

    Hit  → selection.set({fid}), True.
    Miss → selection.clear() falls nicht leer, sonst False.
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


# ---------------------------------------------------------------------------
# Phase 2 — Variante A: Modifier-basiert (Shift/Ctrl/Alt)
# ---------------------------------------------------------------------------

def handle_face_click_modifier(
    camera,
    mesh,
    selection,
    sx: float,
    sy: float,
    width: int,
    height: int,
    modifiers: int,
    input_map,
) -> bool:
    """Variante A: Shift=Add, Ctrl=Remove, Alt=Toggle, bare click=Replace.

    Miss mit Modifier → Selection unverändert (False).
    Miss ohne Modifier → selection.clear() falls nicht leer (wie Phase 1).
    """
    fid = pick_face(camera, mesh, sx, sy, width, height)

    has_add    = bool(modifiers & input_map.add_modifier)
    has_remove = bool(modifiers & input_map.remove_modifier)
    has_toggle = bool(modifiers & input_map.toggle_modifier)
    has_modifier = has_add or has_remove or has_toggle

    if fid is None:
        # Nur bare-miss leert die Selektion
        if not has_modifier and not selection.is_empty():
            selection.clear()
            return True
        return False

    selection.mode = SelectionMode.FACE
    if has_add:
        selection.add({fid})
    elif has_remove:
        selection.remove({fid})
    elif has_toggle:
        selection.toggle(fid)
    else:
        selection.set({fid})
    return True


# ---------------------------------------------------------------------------
# Phase 2 — Variante B: Toggle (jeder Klick togglet)
# ---------------------------------------------------------------------------

def handle_face_click_toggle(
    camera,
    mesh,
    selection,
    sx: float,
    sy: float,
    width: int,
    height: int,
) -> bool:
    """Variante B: Jeder Klick togglet die getroffene Face (Max-ähnlich).

    Hit  → selection.toggle(fid), True.
    Miss → Selection unverändert, False.
    """
    fid = pick_face(camera, mesh, sx, sy, width, height)
    if fid is None:
        return False
    selection.mode = SelectionMode.FACE
    selection.toggle(fid)
    return True


# ---------------------------------------------------------------------------
# Zentraler Dispatch
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Phase 3 — Variante C: Box-Select (LMB-Drag)
# ---------------------------------------------------------------------------

def pick_faces_in_rect(
    camera,
    mesh,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: int,
    height: int,
) -> set:
    """Alle Faces bei denen ALLE Vertices im Bildschirm-Rechteck liegen.

    Koordinaten in pyglet-Screen-Space (y=0 unten). x1/y1 und x2/y2 können
    beliebige Ecken sein (kein Vorzeichen-Requirement).
    Ein Vertex hinter der Kamera (project_to_screen → None) disqualifiziert das Face.
    """
    xmin, xmax = min(x1, x2), max(x1, x2)
    ymin, ymax = min(y1, y2), max(y1, y2)
    result = set()
    for fid in mesh.all_face_ids():
        verts = mesh.face_vertices(fid)
        if not verts:
            continue
        all_inside = True
        for vid in verts:
            projected = camera.project_to_screen(mesh.vertex_position(vid), width, height)
            if projected is None:
                all_inside = False
                break
            px, py = projected
            if not (xmin <= px <= xmax and ymin <= py <= ymax):
                all_inside = False
                break
        if all_inside:
            result.add(fid)
    return result


def handle_box_select(
    camera,
    mesh,
    selection,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: int,
    height: int,
) -> bool:
    """Box-Select: Alle Faces im Rechteck ersetzen die Selektion.

    Gibt True zurück wenn sich die Selektion geändert hat.
    Hit  → selection.set(faces), True.
    Miss → selection.clear() falls nicht leer, sonst False.
    """
    faces = pick_faces_in_rect(camera, mesh, x1, y1, x2, y2, width, height)
    old_faces = set(selection.faces)
    if faces:
        selection.mode = SelectionMode.FACE
        selection.set(faces)
        return faces != old_faces
    if not selection.is_empty():
        selection.clear()
        return True
    return False


def dispatch_face_click(
    camera,
    mesh,
    selection,
    sx: float,
    sy: float,
    width: int,
    height: int,
    modifiers: int,
    input_map,
    mode: SelectMode,
) -> bool:
    """Routed den Click zum richtigen Handler basierend auf SelectMode."""
    if mode is SelectMode.REPLACE:
        return handle_face_click(camera, mesh, selection, sx, sy, width, height)
    if mode is SelectMode.MODIFIER:
        return handle_face_click_modifier(
            camera, mesh, selection, sx, sy, width, height, modifiers, input_map
        )
    if mode is SelectMode.TOGGLE:
        return handle_face_click_toggle(camera, mesh, selection, sx, sy, width, height)
    if mode is SelectMode.BOX:
        # Click in BOX mode = Replace-Fallback (kein Drag gestartet)
        return handle_face_click(camera, mesh, selection, sx, sy, width, height)
    return False
