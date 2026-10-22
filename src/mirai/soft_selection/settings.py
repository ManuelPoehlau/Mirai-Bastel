"""Sticky Soft Selection settings (WP-SOFT-01 S2a, AD-020 Q3 / handoff E3, E4).

One small immutable value, replaced as a whole, owned by `Application`. It has the
semantics of the axis constraint: it survives commit, cancel, re-arm and Undo, and it is
read once per gesture at `begin()` - a gesture that is armed but has not begun takes the
new value, a running gesture keeps the one it began with.

The radius is stored in **world units** (`world_radius`), computed by `Application` when
soft is switched on, when the step changes and on scene load, and read unchanged by the
tool (and, in S2b, the preview): "15 %" cannot drift between them (review F9).

All look-and-feel values here are `PROVISIONAL`: the radius steps and their unit (percent
of the mesh bounding radius), the start step, the custom-curve shape steps and the band
display. S2c verdict (Manu, 2026-10-11, AD-020 §13): geodesic and smooth are the defaults,
the curve set grew (smooth/sphere/root/sharp/linear/custom), the radius list goes up to
200 %, and the influence bands can be switched off.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from .influence import CURVES, METRICS

#: PROVISIONAL (S2d E5): radius steps in percent of the mesh bounding radius. "Up to 50 %
#: is too small" (Manu, S2c), hence the steps beyond it.
RADIUS_STEPS_PERCENT: tuple[int, ...] = (2, 5, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200)
#: PROVISIONAL: the start step is 15 %.
DEFAULT_RADIUS_STEP = RADIUS_STEPS_PERCENT.index(15)
#: S2c verdict (Manu, 2026-10-11): "geodesic würde ich als Standard nehmen"; the curve
#: default is Smooth (the standard bell curve).
DEFAULT_METRIC = "geodesic"
DEFAULT_CURVE = "smooth"
#: PROVISIONAL (S2d E2): the `p` of the `custom` curve `t^p`, rounder (small p) .. sharper
#: (large p). Ctrl+wheel up = one step towards the front of the list.
CUSTOM_SHAPE_STEPS: tuple[float, ...] = (0.25, 0.33, 0.5, 0.67, 1.0, 1.5, 2.0, 3.0, 4.0)
#: PROVISIONAL: the custom curve starts linear (p = 1).
DEFAULT_CUSTOM_SHAPE_STEP = CUSTOM_SHAPE_STEPS.index(1.0)
#: Influence display modes (2026-10-22, `PROVISIONAL`): precise vertex bands or translucent face
#: shading. Exactly one is shown; `bands_visible` hides whichever is active. The first is the default.
VIEW_MODES: tuple[str, ...] = ("bands", "faces")


def world_radius_for(bounding_radius: float, step: int) -> float:
    """World radius of radius step `step` for a mesh of the given bounding radius."""
    return bounding_radius * RADIUS_STEPS_PERCENT[step] / 100.0


def _next_in(names, current: str) -> str:
    order = list(names)
    return order[(order.index(current) + 1) % len(order)]


@dataclass(frozen=True)
class SoftSettings:
    enabled: bool = False
    radius_step: int = DEFAULT_RADIUS_STEP
    world_radius: float = 0.0
    metric: str = DEFAULT_METRIC
    curve: str = DEFAULT_CURVE
    #: Index into `CUSTOM_SHAPE_STEPS`; kept while another curve is active (E3).
    custom_shape_step: int = DEFAULT_CUSTOM_SHAPE_STEP
    #: Display only (S2d E7): False = no influence display at all (bands or faces, whichever is
    #: active). Changes no weight. The field keeps its S2d name.
    bands_visible: bool = True
    #: Display only (2026-10-22): which of `VIEW_MODES` is shown while `bands_visible`.
    view_mode: str = VIEW_MODES[0]

    def __post_init__(self) -> None:
        if not 0 <= self.radius_step < len(RADIUS_STEPS_PERCENT):
            raise ValueError(f"radius_step out of range: {self.radius_step!r}")
        if not 0 <= self.custom_shape_step < len(CUSTOM_SHAPE_STEPS):
            raise ValueError(f"custom_shape_step out of range: {self.custom_shape_step!r}")
        if self.metric not in METRICS:
            raise ValueError(f"Unknown metric {self.metric!r}; expected one of {sorted(METRICS)}.")
        if self.curve not in CURVES:
            raise ValueError(f"Unknown curve {self.curve!r}; expected one of {sorted(CURVES)}.")
        if self.view_mode not in VIEW_MODES:
            raise ValueError(f"Unknown view_mode {self.view_mode!r}; expected one of {VIEW_MODES}.")

    @property
    def radius_percent(self) -> int:
        return RADIUS_STEPS_PERCENT[self.radius_step]

    @property
    def curve_power(self) -> float:
        """The `p` of the custom curve (used only while `curve == "custom"`)."""
        return CUSTOM_SHAPE_STEPS[self.custom_shape_step]

    def toggled(self) -> "SoftSettings":
        return dataclasses.replace(self, enabled=not self.enabled)

    def with_radius_step(self, step: int, bounding_radius: float) -> "SoftSettings":
        """The step clamped to the list (no wrap) with the world radius recomputed."""
        step = max(0, min(step, len(RADIUS_STEPS_PERCENT) - 1))
        return dataclasses.replace(
            self, radius_step=step, world_radius=world_radius_for(bounding_radius, step)
        )

    def with_bounding_radius(self, bounding_radius: float) -> "SoftSettings":
        """The same step on a (new) mesh: only the world radius is recomputed."""
        return dataclasses.replace(
            self, world_radius=world_radius_for(bounding_radius, self.radius_step)
        )

    def with_next_curve(self) -> "SoftSettings":
        return dataclasses.replace(self, curve=_next_in(CURVES, self.curve))

    def with_custom_shape_step(self, delta: int) -> "SoftSettings":
        """Ctrl+wheel: `delta` steps along `CUSTOM_SHAPE_STEPS` (clamped, no wrap) and the
        curve becomes `custom` - any Ctrl+wheel, also at the end of the list (E2)."""
        step = max(0, min(self.custom_shape_step + delta, len(CUSTOM_SHAPE_STEPS) - 1))
        return dataclasses.replace(self, curve="custom", custom_shape_step=step)

    def with_bands_toggled(self) -> "SoftSettings":
        return dataclasses.replace(self, bands_visible=not self.bands_visible)

    def with_next_view_mode(self) -> "SoftSettings":
        return dataclasses.replace(self, view_mode=_next_in(VIEW_MODES, self.view_mode))

    def with_next_metric(self) -> "SoftSettings":
        return dataclasses.replace(self, metric=_next_in(METRICS, self.metric))

    def status_text(self) -> str:
        """Full state for the status line (`PROVISIONAL` until a HUD exists), e.g.
        `Soft: on · 15 % (0.51) · geodesic · custom p=1.5 · bands on` (the display part names the active
        view mode: `bands on`, `faces off`)."""
        curve = f"custom p={self.curve_power:g}" if self.curve == "custom" else self.curve
        return (
            f"Soft: {'on' if self.enabled else 'off'} · {self.radius_percent} % "
            f"({self.world_radius:.2f}) · {self.metric} · {curve} · "
            f"{self.view_mode} {'on' if self.bands_visible else 'off'}"
        )
