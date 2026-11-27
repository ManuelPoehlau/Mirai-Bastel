"""The backdrop seam (AD-042 §7): a photo behind the meshes, a gate and a passepartout over them.

`src/viewport` receives a gate, an image, four corners, an opacity and a placement - never a lens, a camera record
or anything of `src/mirai` (VIEWPORT_V02 §2). All lens and fit math stays in `mirai.viewport.lens`; M1 sends the
gate rectangle as the corners, M2's photo rotation / offset / crop / mirror are other corners, no viewport change.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

BEHIND, FRONT = "behind", "front"
PLACEMENTS = (BEHIND, FRONT)


@dataclass(frozen=True)
class Backdrop:
    gate: tuple[float, float]  # (half_w, half_h) of the centred gate in NDC, each in (0, 1]
    passepartout: float = 0.5  # darkening outside the gate (0 = none)
    image: Any = None  # (h, w, 4) uint8 RGBA, top row first; None = gate only
    image_serial: int = 0  # a new serial = a new image (the pass uploads once per serial)
    corners: tuple[tuple[float, float], ...] = ()  # the image's NDC corners: top-left, top-right, bottom-right, bottom-left
    opacity: float = 1.0
    placement: str = BEHIND  # FRONT is accepted and drawn from M2 (AD-042 §7.6)

    def __post_init__(self) -> None:
        if len(self.gate) != 2 or not all(math.isfinite(g) and 0.0 < g <= 1.0 for g in self.gate):
            raise ValueError(f"gate half sizes must be in (0, 1], got {self.gate!r}")
        if not 0.0 <= self.passepartout <= 1.0:
            raise ValueError(f"passepartout must be in [0, 1], got {self.passepartout!r}")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError(f"opacity must be in [0, 1], got {self.opacity!r}")
        if self.placement not in PLACEMENTS:
            raise ValueError(f"unknown placement {self.placement!r}")
        if self.image is not None:
            shape = getattr(self.image, "shape", None)
            if shape is None or len(shape) != 3 or shape[2] != 4:
                raise ValueError("the backdrop image must be an (h, w, 4) RGBA array")
            if len(self.corners) != 4 or not all(len(c) == 2 for c in self.corners):
                raise ValueError("an image needs four NDC corners")


def gate_corners(gate: tuple[float, float]) -> tuple[tuple[float, float], ...]:
    """The gate rectangle as the four corners (top-left, top-right, bottom-right, bottom-left) - M1's photo quad."""
    w, h = gate
    return ((-w, h), (w, h), (w, -h), (-w, -h))
