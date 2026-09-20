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

from .transform import TransformTool, _face_tangent_basis, _resolve_space


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
        self._normal: tuple[float, float, float] | None = None
        self._plane_exclude: tuple[float, float, float] | None = None
        # Tangent basis and per-basis-vector active flags for normal-space scale.
        # _tangent_basis = (tangent_x, tangent_y, normal), all unit vectors.
        # _active_axes[i] = True means basis vector i gets the step factor.
        self._tangent_basis: tuple | None = None
        self._active_axes: tuple[bool, bool, bool] | None = None

    @property
    def axes_mask(self) -> tuple[float, float, float]:
        """Achsenmaske dieser Interaktion (1.0 = skaliert mit)."""
        return self._axes_mask

    def _create_operation(self, context: OperationContext) -> ScaleOperation:
        return ScaleOperation(context)

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, space=None, axes=None, axis=None, derived_geometry=None, **params: Any
    ) -> None:
        super()._on_begin(scene=scene, camera=camera, vertex_ids=vertex_ids, **params)
        self._normal = None
        self._plane_exclude = None

        # WP-03C: axis is now an explicit parameter (separate from space)
        # Backward compatibility: axes → space (old parameter name)
        if space is None and axes is not None:
            space = axes
        # Additional backward compat: if old API passes axis as space parameter
        if space is None and axis is not None and not isinstance(axis, str):
            # axis passed as vector — treat as space
            space = axis
            axis = None
        elif space is None and axis is not None:
            # axis passed as string (old flat API)
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
                # Konvertiere Achse zu Maske: axis (1,0,0) → mask (1,0,0)
                # (für Scale verwendet man die Achse direkt als Maske)
                self._axes_mask = axis_or_mask
            elif space_lower == "normal":
                axis_lower_check = axis.lower() if isinstance(axis, str) else None
                if derived_geometry is None:
                    raise ValueError(
                        "space='normal' erfordert derived_geometry, mesh und selection."
                    )
                # Derive full tangent basis (raises ValueError for invalid selections).
                normal_vec, tx, ty = _face_tangent_basis(
                    self._scene.mesh,
                    self._scene.selection,
                    derived_geometry,
                )
                # Canonical basis order: b0=tangent_x, b1=tangent_y, b2=normal.
                self._tangent_basis = (tx, ty, normal_vec)
                if axis_lower_check in ("xy", "yz", "xz"):
                    # WP-03D: plane constraint — scale in plane, freeze excluded direction.
                    # "xy" = tangent plane → freeze normal (b2)
                    # "yz" = yz plane    → freeze tangent_x (b0)
                    # "xz" = xz plane    → freeze tangent_y (b1)
                    _plane_freeze = {"xy": (True, True, False), "yz": (False, True, True), "xz": (True, False, True)}
                    self._active_axes = _plane_freeze[axis_lower_check]
                    self._plane_exclude = self._tangent_basis[{"xy": 2, "yz": 0, "xz": 1}[axis_lower_check]]
                    self._normal = None
                else:
                    # WP-03C: single-axis — scale along one basis direction.
                    # "x" → tangent_x (b0), "y" → tangent_y (b1), else → normal (b2)
                    _axis_active = {"x": (True, False, False), "y": (False, True, False)}
                    self._active_axes = _axis_active.get(axis_lower_check, (False, False, True))
                    _axis_idx = {"x": 0, "y": 1}
                    self._normal = self._tangent_basis[_axis_idx.get(axis_lower_check, 2)]
                    self._plane_exclude = None
                self._axes_mask = (1.0, 1.0, 1.0)  # unused when _tangent_basis is set
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

        # Skalierungsfaktor anwenden: tangent-basis, oder Weltachsen-Maske.
        if self._tangent_basis is not None:
            factor = tuple(step if active else 1.0 for active in self._active_axes)
            self._operation.update(factor=factor, basis=self._tangent_basis)
        else:
            # Weltachsenmaske (uniform oder x/y/z/xy/yz/xz): diagonal exakt.
            factor = tuple(step if mask else 1.0 for mask in self._axes_mask)
            self._operation.update(factor=factor)
        self._applied_scale = target_scale

    def _on_deactivate(self) -> None:
        super()._on_deactivate()
        self._axes_mask = (1.0, 1.0, 1.0)
        self._normal = None
        self._plane_exclude = None
        self._tangent_basis = None
        self._active_axes = None
        self._drag_pixels = 0.0
        self._applied_scale = 1.0