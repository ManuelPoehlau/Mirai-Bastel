"""The backdrop seam (AD-042 §7, §18): a photo behind or in front of the meshes, a gate and a passepartout.

`src/viewport` receives a gate, an image, four corners, an opacity, a placement and a wipe line - never a lens, a
camera record or anything of `src/mirai` (VIEWPORT_V02 §2). All lens and fit math stays in `mirai.viewport.lens` and
`mirai.viewport.photo_fit`: the photo's rotation / offset / crop / mirror arrive here as other corners.

- `BEHIND` (M1): drawn before the meshes, depth off; the opaque model covers it.
- `FRONT` (M2): drawn over the meshes in the overlay slot, under the passepartout, the gate line, the wire, the
  highlights and the points (they stay readable), alpha-blended at `opacity`, depth off.
- `wipe` (M2): an NDC x; the photo is drawn only left of it and a 1 px line marks it inside the gate. None = no wipe.
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
    placement: str = BEHIND
    wipe: float | None = None  # NDC x of the wipe line (the photo left of it), None = the whole photo

    def __post_init__(self) -> None:
        if len(self.gate) != 2 or not all(math.isfinite(g) and 0.0 < g <= 1.0 for g in self.gate):
            raise ValueError(f"gate half sizes must be in (0, 1], got {self.gate!r}")
        if not 0.0 <= self.passepartout <= 1.0:
            raise ValueError(f"passepartout must be in [0, 1], got {self.passepartout!r}")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError(f"opacity must be in [0, 1], got {self.opacity!r}")
        if self.placement not in PLACEMENTS:
            raise ValueError(f"unknown placement {self.placement!r}")
        if self.wipe is not None and not (math.isfinite(self.wipe) and -1.0 <= self.wipe <= 1.0):
            raise ValueError(f"wipe must be an NDC x in [-1, 1], got {self.wipe!r}")
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
