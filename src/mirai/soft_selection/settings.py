"""Sticky Soft Selection settings (WP-SOFT-01 S2a, AD-020 Q3 / handoff E3, E4).

One small immutable value, replaced as a whole, owned by `Application`. It has the
semantics of the axis constraint: it survives commit, cancel, re-arm and Undo, and it is
read once per gesture at `begin()` - a gesture that is armed but has not begun takes the
new value, a running gesture keeps the one it began with.

The radius is stored in **world units** (`world_radius`), computed by `Application` when
soft is switched on, when the step changes and on scene load, and read unchanged by the
tool (and, in S2b, the preview): "15 %" cannot drift between them (review F9).

All look-and-feel values here are `PROVISIONAL` test settings for the Artist comparison
test (S2c): the radius steps and their unit (percent of the mesh bounding radius), the
start step, and the start metric/curve. None of them is a default decision.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from .influence import CURVES, METRICS

#: PROVISIONAL (handoff E4): radius steps in percent of the mesh bounding radius.
RADIUS_STEPS_PERCENT: tuple[int, ...] = (2, 5, 10, 15, 20, 30, 40, 50)
#: PROVISIONAL: the start step is 15 %.
DEFAULT_RADIUS_STEP = RADIUS_STEPS_PERCENT.index(15)
#: PROVISIONAL start values for the comparison test, not defaults (Artist, S2c).
DEFAULT_METRIC = "euclidean"
DEFAULT_CURVE = "smooth"


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

    def __post_init__(self) -> None:
        if not 0 <= self.radius_step < len(RADIUS_STEPS_PERCENT):
            raise ValueError(f"radius_step out of range: {self.radius_step!r}")
        if self.metric not in METRICS:
            raise ValueError(f"Unknown metric {self.metric!r}; expected one of {sorted(METRICS)}.")
        if self.curve not in CURVES:
            raise ValueError(f"Unknown curve {self.curve!r}; expected one of {sorted(CURVES)}.")

    @property
    def radius_percent(self) -> int:
        return RADIUS_STEPS_PERCENT[self.radius_step]

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

    def with_next_metric(self) -> "SoftSettings":
        return dataclasses.replace(self, metric=_next_in(METRICS, self.metric))

    def status_text(self) -> str:
        """Full state for the status line (`PROVISIONAL` until a HUD exists), e.g.
        `Soft: on · 15 % (0.51) · euclidean · smooth`."""
        return (
            f"Soft: {'on' if self.enabled else 'off'} · {self.radius_percent} % "
            f"({self.world_radius:.2f}) · {self.metric} · {self.curve}"
        )
