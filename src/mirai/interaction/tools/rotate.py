"""RotateTool: modal-interaktives Rotate-Tool auf RotateOperation (src/core).

Pfad:

    Command.Rotate
        ↓
    RotateTool
        ↓
    RotateOperation (src/core, per ADR-001 promoviert)
        ↓
    Mesh / History

begin(vertex_ids=..., space=None, pivot=None):

    space=None         → Blickachse der Kamera im begin()-Moment
                         (Screen-Plane-Rotation); während der Interaktion fix.
    space="x"/"y"/"z"  → Weltachse durch den Pivot (Achsen-Constraint).
    space="xy"/"yz"/"xz" → Rotation in dieser Ebene (AD-009) = Rotation um die
                         Flächennormale (Ebene XY → Achse Z, usw.). Anders als
                         bei Move/Scale ist das KEINE Maske, sondern weiterhin
                         eine einzelne Richtung — eine Rotation hat immer genau
                         eine Achse, auch wenn sie als "Ebene" benannt wird.
    space="normal"     → Rotation um die aus der Selection abgeleitete Normal.
    space=Vec3         → beliebige Richtung durch den Pivot.

Geste (V1): horizontales Ziehen rotiert; der Zielwinkel wird aus der
KUMULIERTEN Pixel-Distanz berechnet und als inkrementeller Schritt an die
Operation übergeben — das Ergebnis ist unabhängig davon, wie das Fenster
die Drag-Events chunkt.
"""

from __future__ import annotations

import math
from typing import Any

from core import OperationContext, RotateOperation

from .transform import TransformTool, _resolve_space

VEC3 = tuple[float, float, float]


def _resolve_axis(axis, derived_geometry=None, mesh=None, selection=None):
    """Backward compatibility wrapper for _resolve_space (axis → space parameter).

    Deprecated: Use _resolve_space() directly.
    """
    if axis is None:
        raise ValueError("axis=None ist hier nicht gültig.")
    if not isinstance(axis, str):
        # Vector passed directly
        return tuple(axis)
    return _resolve_space(
        axis,
        derived_geometry=derived_geometry,
        mesh=mesh,
        selection=selection,
        for_rotation=True,
    )


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
        self, scene=None, camera=None, vertex_ids=None, space=None, axis=None, derived_geometry=None, **params: Any
    ) -> None:
        super()._on_begin(scene=scene, camera=camera, vertex_ids=vertex_ids, **params)
        # WP-03C: axis is now an explicit parameter (separate from space)
        # Backward compatibility: if only 'axis' is passed (old API), treat it as 'space'
        if space is None and axis is not None and not isinstance(axis, str):
            # axis passed as vector (old API) — treat as space
            space = axis
            axis = None
        elif space is None and axis is not None:
            # axis passed as string (could be old flat API like axis="normal"
            # or new axis="x" from space="normal", axis="x")
            # Let _resolve_space figure it out
            space = axis
            axis = None

        if space is None:
            # Default: Blickachse im begin()-Moment (Screen-Plane-Rotation).
            forward, _, _ = self._camera.basis()
            self._axis = forward
        elif isinstance(space, str):
            self._axis = _resolve_space(
                space,
                derived_geometry=derived_geometry,
                mesh=self._scene.mesh if self._scene else None,
                selection=self._scene.selection if self._scene else None,
                axis=axis,  # Pass through new axis parameter (WP-03C)
                for_rotation=True,
            )
        else:
            # space als Vektor übergeben
            self._axis = tuple(space)
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