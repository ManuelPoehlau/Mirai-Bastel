"""Transform-Tools: gemeinsame Basis für RotateTool/ScaleTool.

Pfad (analog MoveTool, production):

    Command.Rotate / Command.Scale
        ↓
    RotateTool / ScaleTool  (dieses Paket)
        ↓
    RotateOperation / ScaleOperation (src/core, per ADR-001 promoviert)
        ↓
    Mesh / History

Verantwortlichkeiten (INPUT_COMMAND_TOOL_CONTRACT.md §2):

- Das Tool besitzt temporären Interaktionszustand (betroffene Vertex-IDs,
  feste Rotationsachse bzw. Scale-Achsenmaske, kumulierte Drag-Eingabe) und
  übersetzt Pointer-Deltas in semantische Transform-Schritte. Die
  persistente Domain-Mutation macht ausschließlich die Core-Operation —
  keine zweite Mutationslogik im Tool.
- Der Pivot (Selection Center = Zentroid, oder explizit über
  begin(vertex_ids=..., pivot=...)) wird von der Operation in begin() fix
  gesetzt und während der Interaktion nicht verschoben (V1_SPEC §4).

Produktions-Tools haben bewusst einen parameterlosen `__init__` (WP-04
Gate-4-Design): `scene`, `camera` und `vertex_ids` kommen über den
Interaktions-Kontext in `_on_begin(scene=..., camera=..., vertex_ids=...)`.
Konkrete Tools implementieren nur `_create_operation()` und ihre
Gesten-Interpretation (Update-Abbildung); die Snapshot-/Commit-/Cancel-
Maschinerie liegt hier.
"""

from __future__ import annotations

from typing import Any

from core import Mesh, OperationContext, Selection, SelectionMode, VertexId

from ..tool import Tool
from .selection_helpers import _VertexSelectionView, selection_normal, selection_pivot

_WORLD_AXES = {
    # Einzelachsen.
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
    # Ebenen (AD-009): als Achsenmaske — beide Komponenten bleiben frei, die
    # jeweils dritte wird gesperrt. Für ScaleTool/MoveTool direkt als Maske
    # verwendbar (komponentenweise, da Weltachsen orthogonale Einheitsvektoren
    # sind). Für RotateTool NICHT direkt verwendbar — dort bedeutet "Ebene"
    # "Rotation um die Flächennormale", eine einzelne Richtung, keine Maske;
    # siehe die eigene Auflösung in rotate.py.
    "xy": (1.0, 1.0, 0.0),
    "yz": (0.0, 1.0, 1.0),
    "xz": (1.0, 0.0, 1.0),
}


def axis_component(axis: str) -> tuple[float, float, float]:
    """Liefert Weltachsenvektor für Achse ("x", "y", "z").

    Wirft ValueError für unbekannte Achsen. "normal" wird hier nicht
    verarbeitet — siehe _resolve_space() für Normal-Auflösung.
    """
    axis_lower = axis.lower()
    if axis_lower in _WORLD_AXES:
        result = _WORLD_AXES[axis_lower]
        # Nur Einzelachsen zurückgeben, keine Ebenen.
        if result.count(1.0) == 1:
            return result
    raise ValueError(f"axis_component(): unbekannte Achse '{axis}' (erwartet 'x', 'y', 'z')")


def plane_component(plane: str) -> tuple[float, float, float]:
    """Liefert Ebenenmaske für Ebene ("xy", "yz", "xz").

    Eine Ebenenmaske hat zwei 1.0-Komponenten (frei) und eine 0.0 (gesperrt).
    Wirft ValueError für unbekannte Ebenen.
    """
    plane_lower = plane.lower()
    if plane_lower in _WORLD_AXES:
        result = _WORLD_AXES[plane_lower]
        # Nur Ebenen zurückgeben, keine Einzelachsen.
        if result.count(1.0) == 2:
            return result
    raise ValueError(f"plane_component(): unbekannte Ebene '{plane}' (erwartet 'xy', 'yz', 'xz')")


# Plane-to-axis mapping für RotateTool: in Ebene XY rotieren = um Z-Achse rotieren.
_PLANE_ROTATION_AXES: dict[str, tuple[float, float, float]] = {
    "xy": (0.0, 0.0, 1.0),  # Rotation in der XY-Ebene → um Z
    "yz": (1.0, 0.0, 0.0),  # Rotation in der YZ-Ebene → um X
    "xz": (0.0, 1.0, 0.0),  # Rotation in der XZ-Ebene → um Y
}


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    """Normalize a vector."""
    x, y, z = v
    length = (x * x + y * y + z * z) ** 0.5
    if length < 1e-12:
        return (0.0, 0.0, 0.0)
    return (x / length, y / length, z / length)


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    """Cross product a × b."""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _face_tangent_basis(
    mesh: Mesh, selection: Selection, derived_geometry
) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    """Derive orthonormal basis (normal, tangent_x, tangent_y) for single-face selection.

    Requires:
    - selection.mode == SelectionMode.FACE
    - exactly one face in selection.faces

    Tangent basis is right-handed:
    - tangent_x: normalized direction of first edge of the face (winding-order-deterministic)
    - tangent_y: normal × tangent_x
    - normal: face normal (from selection_normal)

    Returns (normal, tangent_x, tangent_y) — all unit vectors, orthonormal.
    Raises ValueError if selection is not a single face or if normal is degenerate.
    """
    if selection.mode != SelectionMode.FACE:
        raise ValueError(
            f"_face_tangent_basis() requires FACE mode, got {selection.mode}."
        )
    if len(selection.faces) != 1:
        raise ValueError(
            f"_face_tangent_basis() requires exactly one face, got {len(selection.faces)}."
        )

    # Get the face
    face_id = list(selection.faces)[0]
    face_verts = mesh.face_vertices(face_id)
    if len(face_verts) < 2:
        raise ValueError(f"Face {face_id} has fewer than 2 vertices (degenerate).")

    # Get the normal
    normal = selection_normal(derived_geometry, mesh, selection, SelectionMode.FACE)
    normal_length = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
    if normal_length < 1e-12:
        raise ValueError(
            "Normal for single face is zero (degenerate). Cannot derive tangent basis."
        )

    # Get the first edge (from first vertex to second vertex)
    v0 = mesh.vertex_position(face_verts[0])
    v1 = mesh.vertex_position(face_verts[1])
    edge = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
    tangent_x = _normalize(edge)

    if (tangent_x[0] ** 2 + tangent_x[1] ** 2 + tangent_x[2] ** 2) < 1e-12:
        raise ValueError(
            f"First edge of face {face_id} is degenerate (zero length)."
        )

    # Compute tangent_y = normal × tangent_x (right-handed)
    tangent_y = _cross(normal, tangent_x)
    tangent_y = _normalize(tangent_y)

    return (normal, tangent_x, tangent_y)


def _resolve_space(
    space: str | None,
    derived_geometry=None,
    mesh: Mesh | None = None,
    selection: Selection | None = None,
    axis: str | None = None,
    for_rotation: bool = False,
) -> tuple[float, float, float]:
    """Auflösen von Raum-Parametern mit optionalem Achsen-Modifier (WP-03C).

    Flache Strings (backward compat):
        "x", "y", "z", "xy", "yz", "xz", "normal" → wie bisher

    Orthogonale (space, axis)-Parameter (WP-03C):
        space="world", axis="x"/...   → Weltachse
        space="normal", axis=None/"z" → Single-direction normal (existing)
        space="normal", axis="x"/"y"  → Tangent basis (single-face only)

    Backward compat: flache Strings werden automatisch zu (space, axis) übersetzt.
    """
    if space is None:
        raise ValueError("_resolve_space(): space=None wird vom Aufrufer explizit behandelt.")

    key = space.lower()

    # Backward compat: translate flat strings to (space, axis) form
    # "x"/"y"/"z" → space="world", axis="x"/"y"/"z"
    # "xy"/"yz"/"xz" → space="world", axis="xy"/"yz"/"xz"
    # "normal" → space="normal", axis="z" (default)
    if axis is None:
        if key in ("x", "y", "z", "xy", "yz", "xz"):
            space = "world"
            axis = key
        elif key == "normal":
            axis = "z"  # default: single-direction normal
        else:
            # Unknown string, let it fail below
            space = key
            axis = None

    # Now process (space, axis) form
    space_lower = space.lower()
    axis_lower = axis.lower() if axis else None

    # World space
    if space_lower == "world":
        if axis_lower in ("x", "y", "z"):
            return axis_component(axis_lower)
        elif axis_lower in ("xy", "yz", "xz"):
            if for_rotation:
                return _PLANE_ROTATION_AXES[axis_lower]
            else:
                return plane_component(axis_lower)
        else:
            raise ValueError(
                f"_resolve_space(space='world', axis='{axis}'): "
                f"axis muss 'x'/'y'/'z' oder 'xy'/'yz'/'xz' sein."
            )

    # Normal space
    if space_lower == "normal":
        if derived_geometry is None or mesh is None or selection is None:
            raise ValueError(
                "space='normal' erfordert derived_geometry, mesh und selection."
            )

        # Single-direction normal (axis="z" or None)
        if axis_lower in (None, "z"):
            mode = selection.mode
            if mode is None:
                raise ValueError("Selection hat keinen aktiven Mode für Normal-Berechnung.")
            result = selection_normal(derived_geometry, mesh, selection, mode)
            length = (result[0] ** 2 + result[1] ** 2 + result[2] ** 2) ** 0.5
            if length < 1e-12:
                raise ValueError(
                    "Normal aus Selection ist Null. Kann nicht "
                    "um Null-Achse rotieren/verschieben/skalieren."
                )
            return result

        # Tangent basis (axis="x" or "y")
        if axis_lower in ("x", "y"):
            normal, tangent_x, tangent_y = _face_tangent_basis(mesh, selection, derived_geometry)
            return tangent_x if axis_lower == "x" else tangent_y

        raise ValueError(
            f"_resolve_space(space='normal', axis='{axis}'): "
            f"axis muss None/'z' (single-normal) oder 'x'/'y' (tangent) sein."
        )

    raise ValueError(
        f"_resolve_space(): unbekannter space='{space}' "
        f"(erlaubt: 'world', 'normal' mit axis='x'/'y'/'z')."
    )


class TransformTool(Tool):
    """Gemeinsame Basis der interaktiven Rotate-/Scale-/Move-Tools.

    Lifecycle-Zustellung (ToolManager, unverändert):

        activate()  → Tool bereit (keine Interaktion)
        begin(scene=..., camera=..., vertex_ids=..., [space=...], [pivot=...],
              [derived_geometry=...]) →
                    Operation.begin() mit fixem Pivot
        update(dx, dy, width, height)* → Operation.update(Schritt)
        commit()    → Operation.commit()  (genau eine History-Grenze)
        cancel()    → Operation.cancel()  (exakter Vorzustand, keine History)
        deactivate()→ Rückkehr nach IDLE, ohne die History zu berühren

    Space-Parameter-Kontrakt (AD-012):
    ------------------------------------
    Alle drei Transform-Tools (Rotate, Move, Scale) akzeptieren einen optionalen
    `space`-Parameter in begin(), der die Transformations-Richtung oder -Einschränkung
    definiert:

    space=None
        → unkonstraniert (Bildebenen-basiert für Move, Kamera-Achse für Rotate,
          uniform für Scale — Vorgabe-Verhalten).
    space="x" | "y" | "z"
        → Einzelachsen-Weltraum-Constraint (Weltachse durch den Pivot).
        Rotate: dreht um diese Achse.
        Move: bewegt nur entlang dieser Achse.
        Scale: skaliert nur entlang dieser Achse.
    space="xy" | "yz" | "xz"
        → Ebenen-Constraint (zwei Achsen frei, eine gesperrt).
        Rotate: dreht um die Senkrechte (xy → z, yz → x, xz → y).
        Move/Scale: arbeitet in dieser Ebene.
    space="normal"
        → Normale der aktuellen Selection (erfordert derived_geometry, mesh, selection).
        Rotate: dreht um die Normal-Richtung.
        Move: bewegt entlang der Normale.
        Scale: skaliert entlang der Normale.
    """

    def __init__(self) -> None:
        super().__init__()
        self._scene = None
        self._camera = None
        self._operation = None
        self._vertex_ids: set[VertexId] = set()

    # -- Beobachtbarkeit für Tests/Integration -------------------------------

    @property
    def operation(self):
        return self._operation

    @property
    def vertex_ids(self) -> set[VertexId]:
        """Von dieser Interaktion betroffene Vertex-IDs (Live-Daten)."""
        return set(self._vertex_ids)

    # -- Hooks ------------------------------------------------------------------

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, **params: Any
    ) -> None:
        vertex_ids = set(vertex_ids or ())
        if not vertex_ids:
            raise ValueError("TransformTool.begin() benötigt mindestens einen Vertex.")
        self._scene = scene
        self._camera = camera
        self._vertex_ids = vertex_ids
        context = OperationContext(
            target=scene.mesh,
            selection=_VertexSelectionView(vertex_ids),
            history=scene.history,
            params={"pivot": params.get("pivot")},
        )
        operation = self._create_operation(context)
        operation.begin()
        self._operation = operation

    def _on_commit(self) -> Any:
        command = self._operation.commit()
        self._operation = None
        return command

    def _on_cancel(self) -> None:
        self._operation.cancel()
        self._operation = None

    def _on_deactivate(self) -> None:
        self._scene = None
        self._camera = None

    # -- Von konkreten Tools zu implementieren ------------------------------------

    def _create_operation(self, context: OperationContext):
        """Erzeugt die konkrete Core-Operation für diese Interaktion."""
        raise NotImplementedError