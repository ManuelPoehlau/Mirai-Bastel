"""Soft Selection on the Production app path (WP-SOFT-01 S2a, AD-020) - `PROVISIONAL`.

Headless: the influence map, the sticky settings and the three weighted transform
operations (Move/Rotate/Scale). Soft Selection is not a selection mode: the influence
never enters `Selection`; one gesture is one History entry. Off by default; the host
(`Application`) owns the settings, the tools compute the influence at `begin()`.

SS2 (AD-SYM-04) adds `symmetric`: the field and step categories of symmetric Soft, the caller
side of the Core's weighted transforms (it reads `mirai.symmetry` for the correspondence).

S2b adds the window look: `bands` (weights -> band -> positions, headless) and `gl_bands`
(the `GLPointOverlay` subclass `Application` pushes the bands into). S2d (S2c verdict):
geodesic/smooth defaults, the curve set (+ a `custom` curve with an adjustable shape), radius
steps up to 200 %, and a switch for the bands.

2026-10-22 adds the second display mode: `shading` (weights -> per-corner colours, headless) and
`gl_shading` (the triangle-overlay sink); exactly one of bands / face shading is shown
(`SoftSettings.view_mode`), and a hover with no selection is the preview target. Also 2026-10-22:
`flow` - the Loop / Ring balance, a topology-oriented anisotropic geodesic field (AD-020).

This package imports nothing from `mirai.interaction` or `mirai.application` (the tools
import it), and no Core private member (AD-020 §3, §9).
"""

from .bands import BAND_COUNT, EMPTY_BANDS, SoftBands, band_index
from .gl_bands import BAND_LAYERS, GLSoftBandOverlay
from .gl_shading import GLSoftShadingOverlay
from .flow import flow_families, has_flow_direction
from .influence import CURVES, METRICS, compute_influence, custom_curve, primary_pivot
from .ops import SoftMoveOperation, SoftRotateOperation, SoftScaleOperation
from .symmetric import SoftSymmetryRefusal, SymmetricInfluence, symmetric_influence
from .shading import shading_color
from .settings import (
    CUSTOM_SHAPE_STEPS,
    DEFAULT_CUSTOM_SHAPE_STEP,
    DEFAULT_FLOW_STEP,
    DEFAULT_RADIUS_STEP,
    FLOW_STEPS,
    LOOKS,
    RADIUS_STEPS_PERCENT,
    VIEW_MODES,
    SoftSettings,
    world_radius_for,
)

__all__ = [
    "BAND_COUNT",
    "BAND_LAYERS",
    "CURVES",
    "CUSTOM_SHAPE_STEPS",
    "DEFAULT_CUSTOM_SHAPE_STEP",
    "DEFAULT_FLOW_STEP",
    "DEFAULT_RADIUS_STEP",
    "FLOW_STEPS",
    "LOOKS",
    "EMPTY_BANDS",
    "GLSoftBandOverlay",
    "GLSoftShadingOverlay",
    "METRICS",
    "RADIUS_STEPS_PERCENT",
    "SoftBands",
    "SoftMoveOperation",
    "SoftRotateOperation",
    "SoftScaleOperation",
    "SoftSettings",
    "SoftSymmetryRefusal",
    "SymmetricInfluence",
    "VIEW_MODES",
    "band_index",
    "compute_influence",
    "custom_curve",
    "flow_families",
    "has_flow_direction",
    "primary_pivot",
    "shading_color",
    "symmetric_influence",
    "world_radius_for",
]
