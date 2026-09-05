"""ScaleTool: modal-interaktives Scale-Tool auf ScaleOperation (src/core).

Pfad:

    Command.Scale
        ↓
    ScaleTool
        ↓
    ScaleOperation (src/core, per ADR-001 promoviert)
        ↓
    Mesh / History

begin(vertex_ids=..., axes=None, pivot=None):

    axes=None          → uniformer Scale (V1_SPEC: Uniform Scale)
    axes="x"/"y"/"z"   → Scale entlang dieser einen Achse
                         (V1_SPEC: Scale entlang X/Y/Z)

Geste (V1): Ziehen (rechts/oben vergrößert) skaliert; der Zielfaktor wird
kumuliert bestimmt und als Multiplikator-Schritt übergeben (Chunking-
Unabhängigkeit) und auf > 0 begrenzt (keine Spiegelung/Degeneration).
"""

from __future__ import annotations

from typing import Any

from core import OperationContext, ScaleOperation

from .transform import TransformTool, _WORLD_AXES


class ScaleTool(TransformTool):
    """Modal-interaktives Scale-Tool (Basis: TransformTool)."""

    # V1-Geste: Faktor-Zuwachs pro Pixel (rechts/oben vergrößert).
    SCALE_PER_PIXEL = 0.005
    # Untergrenze für den Zielfaktor: Die Geste erzeugt keine Spiegelung
    # (negativer Faktor) und keine Degeneration (Faktor 0).
    MIN_SCALE = 0.01

    def __init__(self) -> None:
        super().__init__()
        self._axes_mask: tuple[float, float, float] = (1.0, 1.0, 1.0)
        self._drag_pixels = 0.0
        self._applied_scale = 1.0

    @property
    def axes_mask(self) -> tuple[float, float, float]:
        """Achsenmaske dieser Interaktion (1.0 = skaliert mit)."""
        return self._axes_mask

    def _create_operation(self, context: OperationContext) -> ScaleOperation:
        return ScaleOperation(context)

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, axes=None, **params: Any
    ) -> None:
        super()._on_begin(scene=scene, camera=camera, vertex_ids=vertex_ids, **params)
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