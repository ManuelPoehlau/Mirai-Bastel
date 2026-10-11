"""Soft Selection on the Production app path (WP-SOFT-01 S2a, AD-020) - `PROVISIONAL`.

Headless: the influence map, the sticky settings and the three weighted transform
operations (Move/Rotate/Scale). Soft Selection is not a selection mode: the influence
never enters `Selection`; one gesture is one History entry. Off by default; the host
(`Application`) owns the settings, the tools compute the influence at `begin()`.

This package imports nothing from `mirai.interaction` or `mirai.application` (the tools
import it), and no Core private member (AD-020 §3, §9).
"""

from .influence import CURVES, METRICS, compute_influence, primary_pivot
from .ops import SoftMoveOperation, SoftRotateOperation, SoftScaleOperation
from .settings import (
    DEFAULT_RADIUS_STEP,
    RADIUS_STEPS_PERCENT,
    SoftSettings,
    world_radius_for,
)

__all__ = [
    "CURVES",
    "DEFAULT_RADIUS_STEP",
    "METRICS",
    "RADIUS_STEPS_PERCENT",
    "SoftMoveOperation",
    "SoftRotateOperation",
    "SoftScaleOperation",
    "SoftSettings",
    "compute_influence",
    "primary_pivot",
    "world_radius_for",
]
