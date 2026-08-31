"""WP-03: Transform-Tools (Rotate/Scale) auf der Transform-Foundation.

Pfad (analog WP-02 MoveTool):

    Command.Rotate / Command.Scale
        ↓
    RotateTool / ScaleTool  (dieses Modul, gemeinsame Basis TransformTool)
        ↓
    RotateOperation / ScaleOperation (mirai_bastel_core, WP-03-Foundation)
        ↓
    Mesh / History

Verantwortlichkeiten (INPUT_COMMAND_TOOL_CONTRACT.md §2):

- Das Tool besitzt temporären Interaktionszustand (betroffene Vertex-IDs,
  feste Rotationsachse bzw. Scale-Achsenmaske, kumulierte Drag-Eingabe) und
  übersetzt Pointer-Deltas in semantische Transform-Schritte. Die persistente
  Domain-Mutation macht ausschließlich die Core-Operation — keine zweite
  Mutationslogik im Tool.
- Der Pivot (Selection Center = Zentroid, oder explizit über
  begin(vertex_ids=..., pivot=...)) wird von der Operation in begin() fix
  gesetzt und während der Interaktion nicht verschoben (V1_SPEC §4).

Eingabe-Interpretation (bewusst minimal, V1-Geste):

- RotateTool: horizontales Ziehen rotiert um eine feste Achse. Default-Achse
  ist die Blickachse der Kamera im begin()-Moment; alternativ Weltachse
  ("x"/"y"/"z") oder ein beliebiger Richtungsvektor. Der Zielwinkel wird aus
  der KUMULIERTEN Pixel-Distanz berechnet und als inkrementeller Schritt an
  die Operation übergeben — das Ergebnis ist damit unabhängig davon, wie das
  Fenster die Drag-Events chunkt.
- ScaleTool: Ziehen (rechts/oben vergrößert) skaliert uniform oder
  achsenbeschränkt ("x"/"y"/"z" → nur diese Achse). Der Zielfaktor wird
  kumuliert bestimmt und als Multiplikator-Schritt übergeben (gleiche
  Chunking-Unabhängigkeit); er wird auf > 0 begrenzt (keine Spiegelung /
  Degeneration durch die Geste).

Achsen-Constraints: Die Foundation (Operationen) unterstützt beliebige
Achsen/Faktor-Tripel; die Tools nehmen eine Achs-Auswahl über begin()
entgegen. Eine interaktive Constraint-Umschaltung per Hotkey
(constraints.py-Modul) ist bewusst NICHT Teil von WP-03 und bleibt eine
offene UX-Entscheidung.
"""

from __future__ import annotations

import math
from typing import Any

from mirai_bastel_core import (
    Mesh,
    OperationContext,
    RotateOperation,
    ScaleOperation,
    VertexId,
)

from . import vecmath as v
from .camera import OrbitCamera
from .tool import Tool

_WORLD_AXES = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


def selection_pivot(mesh: Mesh, vertex_ids) -> v.Vec3:
    """Zentroid der betroffenen Vertices (Selection Pivot / Center, V1_SPEC §4)."""
    positions = [mesh.vertex_position(vid) for vid in vertex_ids]
    if not positions:
        raise ValueError("selection_pivot() benötigt mindestens einen Vertex.")
    count = len(positions)
    return (
        sum(p[0] for p in positions) / count,
        sum(p[1] for p in positions) / count,
        sum(p[2] for p in positions) / count,
    )


class _VertexSelectionView:
    """Minimaler Selection-View für die Transform-Operationen.

    Die Core-Operationen benötigen für V1 lediglich die Menge der zu
    transformierenden Vertex-IDs (analog _MoveSelectionView in move_tool).
    """

    def __init__(self, vertex_ids: set[VertexId]) -> None:
        self.vertices = set(vertex_ids)


def _resolve_axis(axis) -> v.Vec3:
    """Normalisiert die Achs-Angabe: "x"/"y"/"z" oder Richtungsvektor."""
    if isinstance(axis, str):
        try:
            return _WORLD_AXES[axis.lower()]
        except KeyError:
            raise ValueError(
                f"Unbekannte Weltachse {axis!r} — erlaubt: 'x', 'y', 'z'."
            ) from None
    if axis is None:
        raise ValueError("axis=None ist hier nicht gültig.")
    return tuple(axis)


class TransformTool(Tool):
    """Gemeinsame Basis der interaktiven Rotate-/Scale-Tools (WP-03).

    Lifecycle-Zustellung (Tool-Manager, WP-02-Verträge unverändert):

        activate()  → Tool bereit (keine Interaktion)
        begin(vertex_ids=..., [pivot=...], [achsen/Constraint-Parameter])
                    → Operation.begin() mit fixem Pivot
        update(dx, dy, width, height)* → Operation.update(Schritt)
        commit()    → Operation.commit()  (genau eine History-Grenze)
        cancel()    → Operation.cancel()  (exakter Vorzustand, keine History)
        deactivate()→ Rückkehr nach IDLE, ohne die History zu berühren

    Der Window-Pfad (app.py) ruft begin() ausschließlich mit `vertex_ids`
    auf — Pivot- und Achsen-Parameter sind optionale Erweiterungen für
    direkte Aufrufer (Tests, spätere Tools) und ändern den Window-Pfad nicht.
    """

    def __init__(self, scene, camera: OrbitCamera) -> None:
        super().__init__()
        self._scene = scene
        self._camera = camera
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

    # -- Hooks -----------------------------------------------------------------

    def _on_begin(self, vertex_ids, **params: Any) -> None:
        vertex_ids = set(vertex_ids)
        if not vertex_ids:
            raise ValueError("TransformTool.begin() benötigt mindestens einen Vertex.")
        self._vertex_ids = vertex_ids
        context = OperationContext(
            target=self._scene.mesh,
            selection=_VertexSelectionView(vertex_ids),
            history=self._scene.history,
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
        pass

    # -- Von konkreten Tools zu implementieren ---------------------------------

    def _create_operation(self, context: OperationContext):
        """Erzeugt die konkrete Core-Operation für diese Interaktion."""
        raise NotImplementedError


class RotateTool(TransformTool):
    """Modal-interaktives Rotate-Tool (WP-03).

    begin(vertex_ids=..., axis=None, pivot=None):

        axis=None          → Blickachse der Kamera im begin()-Moment
                             (Screen-Plane-Rotation); während der
                             Interaktion fix.
        axis="x"/"y"/"z"   → Weltachse durch den Pivot (Achsen-Constraint).
        axis=Vec3          → beliebige Richtung durch den Pivot.
    """

    # V1-Geste: Radiant pro Pixel horizontalem Ziehen (~0.45°/px).
    RADIANS_PER_PIXEL = math.pi / 400.0

    def __init__(self, scene, camera: OrbitCamera) -> None:
        super().__init__(scene, camera)
        self._axis: v.Vec3 | None = None
        self._drag_pixels = 0.0
        self._applied_angle = 0.0

    @property
    def axis(self) -> v.Vec3:
        """Feste Rotationsachse dieser Interaktion (seit begin())."""
        return self._axis

    def _create_operation(self, context: OperationContext) -> RotateOperation:
        return RotateOperation(context)

    def _on_begin(self, vertex_ids, axis=None, **params: Any) -> None:
        super()._on_begin(vertex_ids, **params)
        if axis is None:
            # Default: Blickachse im begin()-Moment (Screen-Plane-Rotation).
            forward, _, _ = self._camera.basis()
            self._axis = forward
        else:
            self._axis = _resolve_axis(axis)
        self._drag_pixels = 0.0
        self._applied_angle = 0.0

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        # Zielwinkel aus kumulierter Pixel-Distanz → inkrementeller Schritt.
        # Damit ist das Ergebnis unabhängig vom Event-Chunking des Fensters.
        self._drag_pixels += dx
        target_angle = self.RADIANS_PER_PIXEL * self._drag_pixels
        step = target_angle - self._applied_angle
        if step == 0.0:
            return
        self._operation.update(axis=self._axis, angle=step)
        self._applied_angle = target_angle


class ScaleTool(TransformTool):
    """Modal-interaktives Scale-Tool (WP-03).

    begin(vertex_ids=..., axes=None, pivot=None):

        axes=None          → uniformer Scale (V1_SPEC: Uniform Scale)
        axes="x"/"y"/"z"   → Scale entlang dieser einen Achse
                             (V1_SPEC: Scale entlang X/Y/Z)
    """

    # V1-Geste: Faktor-Zuwachs pro Pixel (rechts/oben vergrößert).
    SCALE_PER_PIXEL = 0.005
    # Untergrenze für den Zielfaktor: Die Geste erzeugt keine Spiegelung
    # (negativer Faktor) und keine Degeneration (Faktor 0).
    MIN_SCALE = 0.01

    def __init__(self, scene, camera: OrbitCamera) -> None:
        super().__init__(scene, camera)
        self._axes_mask: tuple[float, float, float] = (1.0, 1.0, 1.0)
        self._drag_pixels = 0.0
        self._applied_scale = 1.0

    @property
    def axes_mask(self) -> tuple[float, float, float]:
        """Achsenmaske dieser Interaktion (1.0 = skaliert mit)."""
        return self._axes_mask

    def _create_operation(self, context: OperationContext) -> ScaleOperation:
        return ScaleOperation(context)

    def _on_begin(self, vertex_ids, axes=None, **params: Any) -> None:
        super()._on_begin(vertex_ids, **params)
        if axes is None:
            self._axes_mask = (1.0, 1.0, 1.0)
        else:
            try:
                self._axes_mask = _WORLD_AXES[str(axes).lower()]
            except KeyError:
                raise ValueError(
                    f"Unbekannte Scale-Achse {axes!r} — erlaubt: 'x', 'y', 'z'."
                ) from None
        self._drag_pixels = 0.0
        self._applied_scale = 1.0

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        # Zielfaktor aus kumulierter Pixel-Distanz → Multiplikator-Schritt
        # (chunking-unabhängig, siehe Modul-Docstring).
        self._drag_pixels += dx + dy
        target_scale = max(
            self.MIN_SCALE, 1.0 + self.SCALE_PER_PIXEL * self._drag_pixels
        )
        step = target_scale / self._applied_scale
        if step == 1.0:
            return
        # Achsenmaske: nur maskierte Achsen skalieren, die anderen bleiben.
        factor = tuple(step if mask else 1.0 for mask in self._axes_mask)
        self._operation.update(factor=factor)
        self._applied_scale = target_scale

