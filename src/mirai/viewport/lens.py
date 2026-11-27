"""Lens math of the likeness camera (AD-042 §3): focal length, sensor and fit -> the one camera's FOV.

Pure: stdlib only, no camera, no `src/viewport`, no pyglet / NumPy. It never touches a camera; the application
writes `view_fov_degrees(...)` into `camera.fov_degrees` (the camera's FOV stays its only lens value).

Pinhole model, millimetres for focal length and sensor, aspects are width / height. The view keeps a margin
around the gate (`overscan` >= 1); the invariant (AD-042 §3.2, tested): a point at camera coordinates
(x, y, z) lands at gate-relative (ndc_x / half_w, ndc_y / half_h) = (x / (z tw), y / (z th)), whatever the
window aspect and the overscan, so a resize never moves the model relative to the gate.

No clamping here (a test can probe any value); the application's setters clamp to the ranges.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

#: key -> (label, width mm, height mm, default fit). "custom" takes width / height from the Lens itself.
SENSORS: dict[str, tuple[str, float, float, str]] = {
    "equiv35": ("Kleinbild-Äquivalent", 36.0, 24.0, "diagonal"),  # LC-D5 default
    "full_frame": ("Vollformat", 36.0, 24.0, "auto"),
    "aps_c": ("APS-C", 23.5, 15.6, "auto"),
}
CUSTOM = "custom"
SENSOR_KEYS = (*SENSORS, CUSTOM)
FITS = ("auto", "width", "height", "diagonal")
FOCAL_RANGE_MM = (10.0, 600.0)
OVERSCAN_RANGE = (1.0, 1.5)
OVERSCAN_DEFAULT = 1.15


@dataclass(frozen=True)
class Lens:
    focal_mm: float = 50.0
    sensor: str = "equiv35"  # a SENSORS key or "custom"
    sensor_w_mm: float = 36.0
    sensor_h_mm: float = 24.0
    fit: str = "diagonal"


def _positive(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and > 0, got {value!r}")
    return value


def _check_lens(lens: Lens) -> None:
    _positive("focal length", lens.focal_mm)
    _positive("sensor width", lens.sensor_w_mm)
    _positive("sensor height", lens.sensor_h_mm)
    if lens.sensor not in SENSOR_KEYS:
        raise ValueError(f"unknown sensor {lens.sensor!r}")
    if lens.fit not in FITS:
        raise ValueError(f"unknown fit {lens.fit!r}")


def _check_overscan(overscan: float) -> float:
    overscan = float(overscan)
    if not math.isfinite(overscan) or overscan < 1.0:
        raise ValueError(f"overscan must be finite and >= 1, got {overscan!r}")
    return overscan


def with_sensor(lens: Lens, key: str) -> Lens:
    """The lens with a preset's width, height and default fit; "custom" keeps width, height and fit."""
    if key == CUSTOM:
        return replace(lens, sensor=CUSTOM)
    if key not in SENSORS:
        raise ValueError(f"unknown sensor {key!r}")
    _label, w, h, fit = SENSORS[key]
    return replace(lens, sensor=key, sensor_w_mm=w, sensor_h_mm=h, fit=fit)


def frame_aspect(lens: Lens, photo_size: tuple[int, int] | None) -> float:
    """The frame's width / height: the photo's when there is one, else the sensor's."""
    if photo_size is not None:
        w, h = photo_size
        return _positive("photo width", w) / _positive("photo height", h)
    return _positive("sensor width", lens.sensor_w_mm) / _positive("sensor height", lens.sensor_h_mm)


def effective_sensor(sensor_w_mm: float, sensor_h_mm: float, fit: str, frame_aspect: float) -> tuple[float, float]:
    """(W, H) in mm of the sensor area that records a frame of `frame_aspect`, by the fit (AD-042 §3.2.2)."""
    sw = _positive("sensor width", sensor_w_mm)
    sh = _positive("sensor height", sensor_h_mm)
    a = _positive("frame aspect", frame_aspect)
    if fit == "width":
        return sw, sw / a
    if fit == "height":
        return sh * a, sh
    if fit == "auto":  # Blender's: the longer sensor side goes along the frame's longer side
        side = max(sw, sh)
        return (side, side / a) if a >= 1.0 else (side * a, side)
    if fit == "diagonal":
        d = math.hypot(sw, sh)
        r = math.sqrt(1.0 + a * a)
        return d * a / r, d / r
    raise ValueError(f"unknown fit {fit!r}")


def gate_tan_half(lens: Lens, frame_aspect: float) -> tuple[float, float]:
    """(tw, th): tan of the gate's horizontal and vertical half-angles."""
    _check_lens(lens)
    w, h = effective_sensor(lens.sensor_w_mm, lens.sensor_h_mm, lens.fit, frame_aspect)
    return (w / 2.0) / lens.focal_mm, (h / 2.0) / lens.focal_mm


def view_tan_half_v(lens: Lens, frame_aspect: float, window_aspect: float, overscan: float) -> float:
    """tan(fov/2) of the view that shows the gate with the margin `overscan` in a window of `window_aspect`."""
    a = _positive("frame aspect", frame_aspect)
    a_w = _positive("window aspect", window_aspect)
    o = _check_overscan(overscan)
    tw, th = gate_tan_half(lens, a)
    if a_w >= a:
        return th * o
    return (tw * o) / a_w


def view_fov_degrees(lens: Lens, frame_aspect: float, window_aspect: float, overscan: float) -> float:
    return 2.0 * math.degrees(math.atan(view_tan_half_v(lens, frame_aspect, window_aspect, overscan)))


def gate_rect_ndc(frame_aspect: float, window_aspect: float, overscan: float) -> tuple[float, float]:
    """(half_w, half_h) of the centred gate in NDC."""
    a = _positive("frame aspect", frame_aspect)
    a_w = _positive("window aspect", window_aspect)
    o = _check_overscan(overscan)
    if a_w >= a:
        return (a / a_w) / o, 1.0 / o
    return 1.0 / o, (a_w / a) / o


def focal_from_fov(
    fov_degrees: float, lens: Lens, frame_aspect: float, window_aspect: float, overscan: float
) -> float:
    """The focal length (mm) whose view has `fov_degrees` (the inverse of `view_fov_degrees`)."""
    fov = float(fov_degrees)
    if not math.isfinite(fov) or not 0.0 < fov < 180.0:
        raise ValueError(f"fov must be in (0, 180), got {fov!r}")
    a = _positive("frame aspect", frame_aspect)
    a_w = _positive("window aspect", window_aspect)
    o = _check_overscan(overscan)
    _check_lens(lens)
    w, h = effective_sensor(lens.sensor_w_mm, lens.sensor_h_mm, lens.fit, a)
    t = math.tan(math.radians(fov) / 2.0)
    if a_w >= a:
        return (h / 2.0) * o / t
    return (w / 2.0) * o / (t * a_w)


def gate_angles_degrees(lens: Lens, frame_aspect: float) -> tuple[float, float]:
    """(horizontal, vertical) full angles of the gate in degrees."""
    tw, th = gate_tan_half(lens, frame_aspect)
    return 2.0 * math.degrees(math.atan(tw)), 2.0 * math.degrees(math.atan(th))
