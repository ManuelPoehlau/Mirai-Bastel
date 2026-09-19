"""MoveTool: Referenz-Tool der Produktions-Application.

Pfad:

    Command.Move
        ↓
    MoveTool
        ↓
    Core-MoveOperation (src/core)
        ↓
    Mesh / History

Verantwortlichkeiten (INPUT_COMMAND_TOOL_CONTRACT.md §2):

- MoveTool besitzt temporären Interaktionszustand (Anchor-Vertex, laufende
  MoveOperation, Menge der betroffenen Vertex-IDs, optionale Achsen-/
  Ebenen-Maske, optional normal für "space='normal'"-Constraint).
- Die eigentliche persistente Domain-Mutation macht die bestehende
  `MoveOperation` aus `src.core` — es wird bewusst KEINE zweite
  Move-Mutationslogik gebaut.
- Selection ist kein Tool: Sie bleibt Core-Domain-State. Die Auflösung
  Selection → betroffene Vertex-IDs übernimmt die reine Hilfsfunktion
  `resolve_selection_vertices()`.

begin(vertex_ids=..., space=None, pivot=None, derived_geometry=None) (AD-009, analog Rotate/Scale):

    space=None          → frei auf der Bildebene der Kamera (bisheriges Verhalten).
    space="x"/"y"/"z"   → Bewegung nur entlang dieser Weltachse.
    space="xy"/"yz"/"xz" → Bewegung in dieser Weltebene (die jeweils dritte
                          Komponente bleibt gesperrt).
    space="normal"      → Bewegung entlang der aus der Selection abgeleiteten Normal.

Constraint-Mechanik: Das ohnehin über die Bildebene berechnete Welt-Delta
wird komponentenweise mit der Achsen-/Ebenenmaske multipliziert (identisches
Prinzip wie bei `ScaleTool.axes_mask` — siehe `transform.py::_WORLD_AXES`),
statt eine zweite, unabhängige Constraint-Mathematik einzuführen.

Produktions-Design (WP-04): parameterloser `__init__`; `scene`, `camera`
und `vertex_ids` kommen über den Interaktions-Kontext in
`_on_begin(scene=..., camera=..., vertex_ids=...)` (Pattern A/B).

Bewusst pyglet-frei und ohne physische Key-/Button-Konstanten: Pointer-
Bewegung wird als semantisches Pixel-Delta übergeben und erst hier mit der
Kamera-Hilfsfunktion in ein Welt-Delta übersetzt.
"""

from __future__ import annotations

from typing import Any

from core import (
    MoveOperation,
    OperationContext,
    VertexId,
)

from ..tool import Tool
from .selection_helpers import _VertexSelectionView
from .transform import _resolve_space


class MoveTool(Tool):
    """Modal-interaktives Move-Tool auf Basis der bestehenden MoveOperation.

    Lifecycle-Zustellung (ToolManager):

        activate()  → Tool bereit (keine Interaktion)
        begin(scene=..., camera=..., vertex_ids=...) → MoveOperation.begin()
        update(dx, dy, width, height)* → MoveOperation.update(delta=…)
        commit()    → MoveOperation.commit()  (genau eine History-Grenze)
        cancel()    → MoveOperation.cancel()  (exakter Vorzustand, keine History)
        deactivate()→ Rückkehr nach IDLE, ohne die History zu berühren
    """

    def __init__(self) -> None:
        super().__init__()
        self._scene = None
        self._camera = None
        self._operation: MoveOperation | None = None
        self._vertex_ids: set[VertexId] = set()
        self._anchor_vertex: VertexId | None = None
        self._axes_mask: tuple[float, float, float] = (1.0, 1.0, 1.0)
        self._normal: tuple[float, float, float] | None = None  # Für space="normal"

    # -- Beobachtbarkeit für Tests/Integration ------------------------------

    @property
    def operation(self) -> MoveOperation | None:
        return self._operation

    @property
    def moves(self) -> set[VertexId]:
        """Von dieser Interaktion betroffene Vertex-IDs (Live-Daten)."""
        return set(self._vertex_ids)

    @property
    def axes_mask(self) -> tuple[float, float, float]:
        """Achsen-/Ebenenmaske dieser Interaktion (1.0 = frei, AD-009)."""
        return self._axes_mask

    # -- Hooks -----------------------------------------------------------------

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, space=None, axis=None, derived_geometry=None, **params: Any
    ) -> None:
        vertex_ids = set(vertex_ids or ())
        if not vertex_ids:
            raise ValueError("MoveTool.begin() benötigt mindestens einen Vertex.")
        self._scene = scene
        self._camera = camera
        self._vertex_ids = vertex_ids
        self._anchor_vertex = min(vertex_ids)
        self._normal = None

        # WP-03C: axis is now an explicit parameter (separate from space)
        # Backward compatibility: if old API passes axis as space parameter
        if space is None and axis is not None and not isinstance(axis, str):
            # axis passed as vector — treat as space
            space = axis
            axis = None
        elif space is None and axis is not None:
            # axis passed as string (old flat API like axis="normal")
            # Let _resolve_space figure it out
            space = axis
            axis = None

        if space is None:
            self._axes_mask = (1.0, 1.0, 1.0)
        elif isinstance(space, str):
            space_lower = space.lower()
            # Achsen und Ebenen via _resolve_space (for_rotation=False → gibt Maske zurück)
            if space_lower in ("x", "y", "z", "xy", "yz", "xz"):
                axis_or_mask = _resolve_space(
                    space,
                    derived_geometry=derived_geometry,
                    mesh=self._scene.mesh if self._scene else None,
                    selection=self._scene.selection if self._scene else None,
                    axis=axis,  # Pass through new axis parameter (WP-03C)
                    for_rotation=False,
                )
                # Verwende die Maske direkt (axis/plane aus _WORLD_AXES)
                self._axes_mask = axis_or_mask
            elif space_lower == "normal":
                # Normal auflösen und speichern (WP-03C: axis kann tangent sein)
                self._normal = _resolve_space(
                    space,
                    derived_geometry=derived_geometry,
                    mesh=self._scene.mesh if self._scene else None,
                    selection=self._scene.selection if self._scene else None,
                    axis=axis,  # Pass through axis ("x"/"y"/"z")
                    for_rotation=False,
                )
                self._axes_mask = (1.0, 1.0, 1.0)  # Dummy-Maske, wird nicht verwendet
            else:
                raise ValueError(
                    f"Unbekannter Move-Space {space!r} — erlaubt: "
                    "'x', 'y', 'z', 'xy', 'yz', 'xz', 'normal'."
                ) from None
        else:
            raise ValueError(f"MoveTool.begin(): space-Parameter muss String oder None sein, nicht {type(space).__name__}.")

        context = OperationContext(
            target=self._scene.mesh,
            selection=_VertexSelectionView(vertex_ids),
            history=self._scene.history,
        )
        operation = MoveOperation(context)
        operation.begin()
        self._operation = operation

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        # Anchor ist ein Referenz-Punkt der bewegten Auswahl: Das Pixel-Delta
        # wird auf der Bildebene der Kamera durch diesen Punkt in ein Welt-Delta
        # übersetzt.
        anchor_pos = self._scene.mesh.vertex_position(self._anchor_vertex)
        world_delta = self._camera.screen_delta_to_world(
            anchor_pos, dx, dy, width, height
        )

        # Constraint anwenden: entweder Normal-Projektion oder Achsen-Maske.
        if self._normal is not None:
            # Projekt world_delta auf die Normal-Richtung: (delta · normal) * normal
            dot = (
                world_delta[0] * self._normal[0] +
                world_delta[1] * self._normal[1] +
                world_delta[2] * self._normal[2]
            )
            world_delta = (
                dot * self._normal[0],
                dot * self._normal[1],
                dot * self._normal[2],
            )
        elif self._axes_mask != (1.0, 1.0, 1.0):
            # AD-009: Achsen-/Ebenen-Constraint — komponentenweise Maske auf das
            # ohnehin berechnete Bildebenen-Delta (kein zweiter Mechanismus).
            world_delta = tuple(
                component * mask
                for component, mask in zip(world_delta, self._axes_mask)
            )

        self._operation.update(delta=world_delta)

    def _on_commit(self) -> Any:
        command = self._operation.commit()
        self._operation = None
        return command

    def _on_cancel(self) -> None:
        self._operation.cancel()
        self._operation = None

    def _on_deactivate(self) -> None:
        self._anchor_vertex = None
        self._scene = None
        self._camera = None
        self._axes_mask = (1.0, 1.0, 1.0)
        self._normal = None