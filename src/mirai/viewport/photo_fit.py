"""Photo fit of the likeness camera (AD-042 §18, M2): rotation, offset, crop scale and mirror -> the photo's NDC corners.

Pure: stdlib only, no camera, no `src/viewport`. The application sends the corners to the backdrop seam
(`viewport.backdrop.Backdrop.corners`); `src/viewport` never sees these values.

Three pinhole equivalences (proposal §2.4) make camera changes unnecessary:

- **offset** of the photo in the gate == a lens shift (principal-point offset) of the camera;
- **rotation** of the photo about the gate centre == a camera roll (LC-D4: the photo turns, the model stays upright);
- **scale** == a focal-length change at a fixed pose, so it exists only in the cropped mode: an uncropped photo fills
  the gate (scale 1) and the lens is the variable.

Both equivalences are tested against an asymmetric / rolled reference camera (`tests/test_photo_fit.py`).

Units: the rotation in degrees, counter-clockwise on screen; the offset in gate heights (+x right, +y up), so a value
means the same in every window shape; the scale relative to the gate. All maths runs in isotropic screen units
(NDC x times the window aspect), so a rotation keeps the photo's shape in any window.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

ROTATION_RANGE = (-180.0, 180.0)
OFFSET_RANGE = (-1.0, 1.0)  # gate heights
SCALE_RANGE = (0.1, 4.0)


@dataclass(frozen=True)
class PhotoFit:
    rotation_deg: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    cropped: bool = False  # „beschnittenes Foto“: the scale applies
    scale: float = 1.0  # kept while not cropped, applied only when cropped
    mirror: bool = False  # left / right

    @property
    def effective_scale(self) -> float:
        return self.scale if self.cropped else 1.0

    @property
    def is_identity(self) -> bool:
        return (self.rotation_deg == 0.0 and self.offset_x == 0.0 and self.offset_y == 0.0
                and self.effective_scale == 1.0 and not self.mirror)


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return value


def clamped(fit: PhotoFit) -> PhotoFit:
    """The fit with every value in its range (the setters and the file reader use it); `ValueError` on NaN / inf."""
    rot = _finite("rotation", fit.rotation_deg)
    rot = math.remainder(rot, 360.0) if abs(rot) > 180.0 else rot  # 190° -> -170°: one turn is the same picture
    lo, hi = OFFSET_RANGE
    ox = max(lo, min(hi, _finite("offset x", fit.offset_x)))
    oy = max(lo, min(hi, _finite("offset y", fit.offset_y)))
    s_lo, s_hi = SCALE_RANGE
    scale = max(s_lo, min(s_hi, _finite("scale", fit.scale)))
    return PhotoFit(rot, ox, oy, bool(fit.cropped), scale, bool(fit.mirror))


def photo_corners(
    gate: tuple[float, float], window_aspect: float, fit: PhotoFit
) -> tuple[tuple[float, float], ...]:
    """The photo's NDC corners (top-left, top-right, bottom-right, bottom-left of the *image*) for a centred gate of
    half size `gate` in NDC. The identity fit gives exactly `viewport.backdrop.gate_corners(gate)`."""
    hw, hh = float(gate[0]), float(gate[1])
    a_w = float(window_aspect)
    if not (math.isfinite(a_w) and a_w > 0.0):
        raise ValueError(f"window aspect must be finite and > 0, got {window_aspect!r}")
    if fit.is_identity:
        return ((-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh))
    s = fit.effective_scale
    half_x, half_y = hw * a_w * s, hh * s  # isotropic units: NDC x times the window aspect
    left, right = (half_x, -half_x) if fit.mirror else (-half_x, half_x)  # mirrored: the image's left lands right
    local = ((left, half_y), (right, half_y), (right, -half_y), (left, -half_y))
    theta = math.radians(fit.rotation_deg)
    c, sn = math.cos(theta), math.sin(theta)
    gate_h = 2.0 * hh  # the offset unit, in isotropic units
    dx, dy = fit.offset_x * gate_h, fit.offset_y * gate_h
    out = []
    for x, y in local:
        rx, ry = c * x - sn * y + dx, sn * x + c * y + dy
        out.append((rx / a_w, ry))
    return tuple(out)


def photo_point_ndc(corners, u: float, v: float) -> tuple[float, float]:
    """Where the image point (u, v) - 0..1, u to the right, v down from the image's top - lands in NDC (the quad is a
    parallelogram, so the two triangles map it affinely); the tests use it."""
    (tlx, tly), (trx, try_), _br, (blx, bly) = corners
    return (tlx + u * (trx - tlx) + v * (blx - tlx), tly + u * (try_ - tly) + v * (bly - tly))
