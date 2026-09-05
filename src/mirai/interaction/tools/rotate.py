"""RotateTool: modal-interaktives Rotate-Tool auf RotateOperation (src/core).

Pfad:

    Command.Rotate
        ↓
    RotateTool
        ↓
    RotateOperation (src/core, per ADR-001 promoviert)
        ↓
    Mesh / History

begin(vertex_ids=..., axis=None, pivot=None):

    axis=None          → Blickachse der Kamera im begin()-Moment
                         (Screen-Plane-Rotation); während der Interaktion fix.
    axis="x"/"y"/"z"   → Weltachse durch den Pivot (Achsen-Constraint).
    axis=Vec3          → beliebige Richtung durch den Pivot.

Geste (V1): horizontales Ziehen rotiert; der Zielwinkel wird aus der
KUMULIERTEN Pixel-Distanz berechnet und als inkrementeller Schritt an die
Operation übergeben — das Ergebnis ist unabhängig davon, wie das Fenster
die Drag-Events chunkt.
"""

from __future__ import annotations

import math
from typing import Any

from core import OperationContext, RotateOperation

from .transform import TransformTool, _WORLD_AXES

VEC3 = tuple[float, float, float]


def _resolve_axis(axis) -> VEC3:
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


class RotateTool(TransformTool):
    """Modal-interaktives Rotate-Tool (Basis: TransformTool)."""

    # V1-Geste: Radiant pro Pixel horizontales Ziehen (~0.45°/px).
    RADIANS_PER_PIXEL = math.pi / 400.0

    def __init__(self) -> None:
        super().__init__()
        self._axis: VEC3 | None = None
        self._drag_pixels = 0.0
        self._applied_angle = 0.0

    @property
    def axis(self) -> VEC3:
        """Feste Rotationsachse dieser Interaktion (seit begin())."""
        return self._axis

    def _create_operation(self, context: OperationContext) -> RotateOperation:
        return RotateOperation(context)

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, axis=None, **params: Any
    ) -> None:
        super()._on_begin(scene=scene, camera=camera, vertex_ids=vertex_ids, **params)
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