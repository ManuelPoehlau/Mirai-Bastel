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


def _resolve_space(
    space: str | None,
    derived_geometry=None,
    mesh: Mesh | None = None,
    selection: Selection | None = None,
    for_rotation: bool = False,
) -> tuple[float, float, float]:
    """Auflösen von Raum-Parametern: "x"/"y"/"z", "xy"/"yz"/"xz", "normal", oder None.

    space=None:
        → Wird vom Aufrufer behandelt (z. B. Kamera-Achse für Rotate,
          freiform für Move, uniform für Scale).
    space="x"/"y"/"z":
        → Weltachse aus _WORLD_AXES.
    space="xy"/"yz"/"xz":
        → Ebenenmaske (zwei 1.0, eine 0.0) für Move/Scale;
        → bei for_rotation=True: Rotationsachse (senkrecht zur Ebene).
    space="normal":
        → Normal aus selection_normal(); erfordert derived_geometry, mesh, selection.
        Wirft ValueError wenn degenerierten Normal oder fehlende Parameter.

    Für Rotate (for_rotation=True): plane "xy" gibt Rotationsachse Z zurück.
    Für Move/Scale (for_rotation=False): plane "xy" gibt Maske (1,1,0) zurück.
    """
    if space is None:
        raise ValueError("_resolve_space(): space=None wird vom Aufrufer explizit behandelt.")

    key = space.lower()

    # Einzelachsen
    if key in ("x", "y", "z"):
        return axis_component(key)

    # Ebenen
    if key in _WORLD_AXES and _WORLD_AXES[key].count(1.0) == 2:
        if for_rotation:
            # Für Rotate: gebe die Rotationsachse zurück (senkrecht zur Ebene).
            return _PLANE_ROTATION_AXES[key]
        else:
            # Für Move/Scale: gebe die Ebenenmaske zurück.
            return plane_component(key)

    # Normal
    if key == "normal":
        if derived_geometry is None or mesh is None or selection is None:
            raise ValueError(
                "space='normal' erfordert derived_geometry, mesh und selection "
                "(aktuell: mindestens einer ist None)."
            )
        mode = selection.mode
        if mode is None:
            raise ValueError("Selection hat keinen aktiven Mode für Normal-Berechnung.")
        result = selection_normal(derived_geometry, mesh, selection, mode)
        length = (result[0] ** 2 + result[1] ** 2 + result[2] ** 2) ** 0.5
        if length < 1e-12:
            raise ValueError(
                "Normal aus Selection ist Null (Degeneration, z. B. "
                "entgegengesetzte Vertex-Normalen heben sich auf). Kann nicht "
                "um Null-Achse rotieren/verschieben/skalieren."
            )
        return result

    raise ValueError(
        f"_resolve_space(): unbekannter Space '{space}' — erlaubt: "
        "'x', 'y', 'z', 'xy', 'yz', 'xz', 'normal'."
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