"""Soft Selection on the Production app path (WP-SOFT-01 S2a, AD-020) - `PROVISIONAL`.

Headless: the influence map, the sticky settings and the three weighted transform
operations (Move/Rotate/Scale). Soft Selection is not a selection mode: the influence
never enters `Selection`; one gesture is one History entry. Off by default; the host
(`Application`) owns the settings, the tools compute the influence at `begin()`.

S2b adds the window look: `bands` (weights -> band -> positions, headless) and `gl_bands`
(the `GLPointOverlay` subclass `Application` pushes the bands into).

This package imports nothing from `mirai.interaction` or `mirai.application` (the tools
import it), and no Core private member (AD-020 §3, §9).
"""

from .bands import BAND_COUNT, EMPTY_BANDS, SoftBands, band_index
from .gl_bands import BAND_LAYERS, GLSoftBandOverlay
from .influence import CURVES, METRICS, compute_influence, primary_pivot
from .ops import SoftMoveOperation, SoftRotateOperation, SoftScaleOperation
from .settings import (
    DEFAULT_RADIUS_STEP,
    RADIUS_STEPS_PERCENT,
    SoftSettings,
    world_radius_for,
)

__all__ = [
    "BAND_COUNT",
    "BAND_LAYERS",
    "CURVES",
    "DEFAULT_RADIUS_STEP",
    "EMPTY_BANDS",
    "GLSoftBandOverlay",
    "METRICS",
    "RADIUS_STEPS_PERCENT",
    "SoftBands",
    "SoftMoveOperation",
    "SoftRotateOperation",
    "SoftScaleOperation",
    "SoftSettings",
    "band_index",
    "compute_influence",
    "primary_pivot",
    "world_radius_for",
]
