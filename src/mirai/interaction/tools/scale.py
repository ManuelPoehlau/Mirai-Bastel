"""ScaleTool: modal-interaktives Scale-Tool auf ScaleOperation (src/core).

Pfad:

    Command.Scale
        ↓
    ScaleTool
        ↓
    ScaleOperation (src/core, per ADR-001 promoviert)
        ↓
    Mesh / History

begin(vertex_ids=..., space=None, pivot=None, derived_geometry=None):

    space=None         → uniformer Scale (V1_SPEC: Uniform Scale)
    space="x"/"y"/"z"  → Scale entlang dieser einen Achse
                         (V1_SPEC: Scale entlang X/Y/Z)
    space="xy"/"yz"/"xz" → Scale in dieser Ebene (AD-009): beide Achsen frei,
                         die jeweils dritte gesperrt.
    space="normal"     → Scale entlang der aus der Selection abgeleiteten Normal.

Geste (V1): Ziehen (rechts/oben vergrößert) skaliert; der Zielfaktor wird
kumuliert bestimmt und als Multiplikator-Schritt übergeben (Chunking-
Unabhängigkeit) und auf > 0 begrenzt (keine Spiegelung/Degeneration).
"""

from __future__ import annotations

from typing import Any

from core import OperationContext, ScaleOperation

from .transform import TransformTool, _resolve_space


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
        self._normal: tuple[float, float, float] | None = None  # Für space="normal"

    @property
    def axes_mask(self) -> tuple[float, float, float]:
        """Achsenmaske dieser Interaktion (1.0 = skaliert mit)."""
        return self._axes_mask

    def _create_operation(self, context: OperationContext) -> ScaleOperation:
        return ScaleOperation(context)

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, space=None, axes=None, derived_geometry=None, **params: Any
    ) -> None:
        super()._on_begin(scene=scene, camera=camera, vertex_ids=vertex_ids, **params)
        self._normal = None

        # Backward compatibility: axes → space (axes wird nicht mehr verwendet, space ist neu)
        if space is None and axes is not None:
            space = axes

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
                    for_rotation=False,
                )
                # Konvertiere Achse zu Maske: axis (1,0,0) → mask (1,0,0)
                # (für Scale verwendet man die Achse direkt als Maske)
                self._axes_mask = axis_or_mask
            elif space_lower == "normal":
                # Normal auflösen und speichern
                self._normal = _resolve_space(
                    space,
                    derived_geometry=derived_geometry,
                    mesh=self._scene.mesh if self._scene else None,
                    selection=self._scene.selection if self._scene else None,
                    for_rotation=False,
                )
                self._axes_mask = (1.0, 1.0, 1.0)  # Dummy-Maske, wird nicht verwendet
            else:
                raise ValueError(
                    f"Unbekannter Scale-Space {space!r} — erlaubt: "
                    "'x', 'y', 'z', 'xy', 'yz', 'xz', 'normal'."
                ) from None
        else:
            raise ValueError(f"ScaleTool.begin(): space-Parameter muss String oder None sein, nicht {type(space).__name__}.")

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

        # Skalierungsfaktor anwenden: entweder Normal-basiert oder Achsen-Maske.
        if self._normal is not None:
            # Skalierung entlang der Normal-Richtung: interpoliere zwischen
            # 1.0 und step basierend auf der Normal-Komponente.
            # Für eine nicht-axiale Normal (z.B. (0.7, 0.7, 0)), skaliere
            # Achsen proportional zu ihrer Normalkomponente.
            factor = tuple(
                1.0 + (step - 1.0) * abs(comp)
                for comp in self._normal
            )
        else:
            # Achsenmaske: nur maskierte Achsen skalieren, die anderen bleiben.
            factor = tuple(step if mask else 1.0 for mask in self._axes_mask)

        self._operation.update(factor=factor)
        self._applied_scale = target_scale

    def _on_deactivate(self) -> None:
        super()._on_deactivate()
        self._axes_mask = (1.0, 1.0, 1.0)
        self._normal = None
        self._drag_pixels = 0.0
        self._applied_scale = 1.0