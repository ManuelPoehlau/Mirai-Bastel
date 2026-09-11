"""PlaygroundSelector — headless Click-to-Selection-Bridge für AP-03.

Phase 1: handle_face_click (Replace)
Phase 2: SelectMode-Enum + handle_face_click_modifier (A) + handle_face_click_toggle (B)
         + dispatch_face_click (zentraler Einstiegspunkt für das Window)
Phase 3: pick_faces_in_rect + handle_box_select (SelectMethod.BOX)
Phase 5: pick_component + dispatch_click (Component-Mode-aware: Vertex/Edge/Face)

Zwei orthogonale Systeme:
  SelectMode   — WAS der Klick tut      (REPLACE / MODIFIER / TOGGLE), M-Taste
  SelectMethod — WIE du auswählst       (PICK / BOX / LASSO / PAINT),  Q-Taste

Kein GL, kein pyglet, vollständig headless testbar.
Konvention: sx/sy in pyglet-Koordinaten (y=0 unten).
"""

from __future__ import annotations

from enum import Enum, auto

from playground._paths import ensure_paths

ensure_paths()

from core.selection import SelectionMode  # noqa: E402
from mirai.viewport.picking import pick_face, pick_nearest_edge, pick_nearest_vertex  # noqa: E402

CLICK_THRESHOLD: float = 5.0  # Pixel (Manhattan-Summe aus on_mouse_drag)


class SelectMode(Enum):
    """WAS der Klick tut (Selection Behaviour)."""
    REPLACE  = auto()   # Klick = Replace (Phase 1 Baseline)
    MODIFIER = auto()   # Shift=Add, Ctrl=Remove, Alt=Toggle (Variante A)
    TOGGLE   = auto()   # Jeder Klick togglet (Variante B)


class SelectMethod(Enum):
    """WIE die Auswahl gezeichnet wird (Selection Method).

    PICK  — Einzelklick
    BOX   — LMB-Drag = Rechteck
    LASSO — Freihand-Polygon (Stub, noch nicht implementiert)
    PAINT — Pinsel-Selektion (Stub, noch nicht implementiert)
    """
    PICK  = auto()
    BOX   = auto()
    LASSO = auto()
    PAINT = auto()


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
# Phase 3 — SelectMethod.BOX: Rechteck-Auswahl
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
    modifiers: int = 0,
    input_map=None,
) -> bool:
    """Box-Select: Shift=Add, Ctrl=Remove, kein Modifier=Replace.

    Gibt True zurück wenn sich die Selektion geändert hat.
    Miss ohne Modifier → selection.clear() falls nicht leer.
    """
    faces = pick_faces_in_rect(camera, mesh, x1, y1, x2, y2, width, height)

    has_add    = input_map is not None and bool(modifiers & input_map.add_modifier)
    has_remove = input_map is not None and bool(modifiers & input_map.remove_modifier)

    before = frozenset(selection.faces)

    if not faces:
        if not has_add and not has_remove and not selection.is_empty():
            selection.clear()
            return True
        return False

    selection.mode = SelectionMode.FACE
    if has_add:
        selection.add(faces)
    elif has_remove:
        selection.remove(faces)
    else:
        selection.set(faces)
    return frozenset(selection.faces) != before


# ---------------------------------------------------------------------------
# Phase 5 — Component Mode (Vertex / Edge / Face)
# ---------------------------------------------------------------------------

def pick_component(camera, mesh, selection, sx: float, sy: float, width: int, height: int):
    """Picked das nächste Element je nach selection.mode (Vertex/Edge/Face)."""
    if selection.mode is SelectionMode.VERTEX:
        return pick_nearest_vertex(camera, mesh, sx, sy, width, height)
    if selection.mode is SelectionMode.EDGE:
        return pick_nearest_edge(camera, mesh, sx, sy, width, height)
    return pick_face(camera, mesh, sx, sy, width, height)


def dispatch_click(
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
    method: SelectMethod = SelectMethod.PICK,
) -> bool:
    """Component-aware Dispatch: kombiniert SelectMode (Behaviour) + SelectMethod.

    SelectMethod.LASSO / PAINT sind noch nicht implementiert → False.
    SelectMethod.PICK / BOX-Click-Fallback verwenden SelectMode für Behaviour.
    """
    if method is SelectMethod.LASSO or method is SelectMethod.PAINT:
        return False

    hit = pick_component(camera, mesh, selection, sx, sy, width, height)

    if mode is SelectMode.REPLACE:
        if hit is not None:
            selection.set({hit})
            return True
        if not selection.is_empty():
            selection.clear()
            return True
        return False

    if mode is SelectMode.TOGGLE:
        if hit is None:
            return False
        selection.toggle(hit)
        return True

    if mode is SelectMode.MODIFIER:
        has_add    = bool(modifiers & input_map.add_modifier)
        has_remove = bool(modifiers & input_map.remove_modifier)
        has_toggle = bool(modifiers & input_map.toggle_modifier)
        has_modifier = has_add or has_remove or has_toggle
        if hit is None:
            if not has_modifier and not selection.is_empty():
                selection.clear()
                return True
            return False
        if has_add:
            selection.add({hit})
        elif has_remove:
            selection.remove({hit})
        elif has_toggle:
            selection.toggle(hit)
        else:
            selection.set({hit})
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
    """Face-only Dispatch (ohne Component-Mode). Für Tests und Experimente."""
    if mode is SelectMode.REPLACE:
        return handle_face_click(camera, mesh, selection, sx, sy, width, height)
    if mode is SelectMode.MODIFIER:
        return handle_face_click_modifier(
            camera, mesh, selection, sx, sy, width, height, modifiers, input_map
        )
    if mode is SelectMode.TOGGLE:
        return handle_face_click_toggle(camera, mesh, selection, sx, sy, width, height)
    return False
