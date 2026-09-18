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
    axis="xy"/"yz"/"xz" → Rotation in dieser Ebene (AD-009) = Rotation um die
                         Flächennormale (Ebene XY → Achse Z, usw.). Anders als
                         bei Move/Scale ist das KEINE Maske, sondern weiterhin
                         eine einzelne Richtung — eine Rotation hat immer genau
                         eine Achse, auch wenn sie als "Ebene" benannt wird.
    axis=Vec3          → beliebige Richtung durch den Pivot.

Geste (V1): horizontales Ziehen rotiert; der Zielwinkel wird aus der
KUMULIERTEN Pixel-Distanz berechnet und als inkrementeller Schritt an die
Operation übergeben — das Ergebnis ist unabhängig davon, wie das Fenster
die Drag-Events chunkt.
"""

from __future__ import annotations

import math
from typing import Any

from core import OperationContext, RotateOperation, Selection, SelectionMode

from .selection_helpers import selection_normal
from .transform import TransformTool, _WORLD_AXES

VEC3 = tuple[float, float, float]

# AD-009: Ebenen-Constraint für Rotate = Rotation um die Flächennormale.
# Bewusst getrennt von _WORLD_AXES (dort sind "xy"/"yz"/"xz" Masken für
# Scale/Move, hier ist es die eine Achse senkrecht zur genannten Ebene).
_PLANE_ROTATION_AXES: dict[str, VEC3] = {
    "xy": (0.0, 0.0, 1.0),  # Rotation in der XY-Ebene → um Z
    "yz": (1.0, 0.0, 0.0),  # Rotation in der YZ-Ebene → um X
    "xz": (0.0, 1.0, 0.0),  # Rotation in der XZ-Ebene → um Y
}


def _resolve_axis(axis, derived_geometry=None, mesh=None, selection: Selection | None = None) -> VEC3:
    """Resolve axis specification: "x"/"y"/"z", "xy"/"yz"/"xz", "normal", or vector.

    axis="normal" requires derived_geometry, mesh, and selection to compute
    the normal from the current component selection.
    """
    if isinstance(axis, str):
        key = axis.lower()
        if key == "normal":
            if derived_geometry is None or mesh is None or selection is None:
                raise ValueError(
                    "axis='normal' requires derived_geometry, mesh, and selection."
                )
            mode = selection.mode
            if mode is None:
                raise ValueError("Selection has no active mode.")
            result = selection_normal(derived_geometry, mesh, selection, mode)
            length = (result[0] ** 2 + result[1] ** 2 + result[2] ** 2) ** 0.5
            if length < 1e-12:
                raise ValueError(
                    "Normal derived from selection is zero (degenerate case, e.g., "
                    "opposing vertex normals). Unable to rotate around null axis."
                )
            return result
        if key in _PLANE_ROTATION_AXES:
            return _PLANE_ROTATION_AXES[key]
        try:
            return _WORLD_AXES[key]
        except KeyError:
            raise ValueError(
                f"Unbekannte Achse/Ebene {axis!r} — erlaubt: "
                "'x', 'y', 'z', 'xy', 'yz', 'xz', 'normal'."
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
        self, scene=None, camera=None, vertex_ids=None, axis=None, derived_geometry=None, **params: Any
    ) -> None:
        super()._on_begin(scene=scene, camera=camera, vertex_ids=vertex_ids, **params)
        if axis is None:
            # Default: Blickachse im begin()-Moment (Screen-Plane-Rotation).
            forward, _, _ = self._camera.basis()
            self._axis = forward
        else:
            self._axis = _resolve_axis(
                axis,
                derived_geometry=derived_geometry,
                mesh=self._scene.mesh if self._scene else None,
                selection=self._scene.selection if self._scene else None,
            )
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