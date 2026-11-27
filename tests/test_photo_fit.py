"""The photo fit (AD-042 §18.3, proposal §2.4 / §9 M2), pure: offset == lens shift and rotation == camera roll against
an independent off-axis / rolled reference camera; identity, mirror, crop scale, clamping, aspect safety."""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from mirai.viewport import lens as L
from mirai.viewport import photo_fit as F
from viewport.backdrop import gate_corners

LENS = L.Lens(focal_mm=85.0)
CASES = [  # (frame aspect, window aspect, overscan): window wider and narrower than the photo
    (1.5, 1.6, 1.15),
    (2 / 3, 1.6, 1.15),
    (1.5, 0.75, 1.3),
    (4 / 3, 4 / 3, 1.0),
]


def _setup(a, a_w, o):
    gate = L.gate_rect_ndc(a, a_w, o)
    tw, th = L.gate_tan_half(LENS, a)
    return gate, tw, th


def _points(seed: int, n: int = 40):
    rng = random.Random(seed)
    return [(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3), rng.uniform(1.0, 5.0)) for _ in range(n)]


def _symmetric_ndc(p, gate, tw, th):
    """The likeness camera (symmetric frustum, AD-042 §3.2's invariant): where the point lands on screen."""
    x, y, z = p
    return (x / (z * tw)) * gate[0], (y / (z * th)) * gate[1]


def _uv_off_axis(p, tw, th, cx, cy):
    """A real camera with its principal point moved by (cx, cy) (tan units, an off-axis frustum, written out
    independently of `photo_fit`): the point's place in the photo, u right, v down."""
    x, y, z = p
    left, right = -tw + cx, tw + cx
    bottom, top = -th + cy, th + cy
    return (x / z - left) / (right - left), (top - y / z) / (top - bottom)


def _uv_rolled(p, tw, th, phi):
    """A real camera rolled by `phi` (counter-clockwise about its optical axis): the point's place in its photo."""
    x, y, z = p
    xr = math.cos(phi) * x + math.sin(phi) * y
    yr = -math.sin(phi) * x + math.cos(phi) * y
    return (xr / (z * tw) + 1.0) / 2.0, (1.0 - yr / (z * th)) / 2.0


@pytest.mark.parametrize("a, a_w, o", CASES)
def test_the_identity_fit_is_the_gate(a, a_w, o):
    gate, _tw, _th = _setup(a, a_w, o)
    assert F.photo_corners(gate, a_w, F.PhotoFit()) == gate_corners(gate)
    assert F.PhotoFit().is_identity and F.PhotoFit(scale=2.0).is_identity  # the scale needs the cropped mode


@pytest.mark.parametrize("a, a_w, o", CASES)
def test_offset_is_a_lens_shift(a, a_w, o):
    gate, tw, th = _setup(a, a_w, o)
    rng = random.Random(7)
    for _ in range(6):
        cx, cy = rng.uniform(-0.6, 0.6) * tw, rng.uniform(-0.6, 0.6) * th
        # the window moved right records the point further left: the photo moves right by the shift (gate heights)
        fit = F.PhotoFit(offset_x=cx / (2.0 * th), offset_y=cy / (2.0 * th))
        corners = F.photo_corners(gate, a_w, fit)
        for p in _points(int(cx * 1e6)):
            got = F.photo_point_ndc(corners, *_uv_off_axis(p, tw, th, cx, cy))
            want = _symmetric_ndc(p, gate, tw, th)
            assert got == pytest.approx(want, abs=1e-12)


@pytest.mark.parametrize("a, a_w, o", CASES)
def test_rotation_is_a_camera_roll(a, a_w, o):
    gate, tw, th = _setup(a, a_w, o)
    for deg in (-37.0, -3.5, 0.25, 12.0, 90.0, 179.0):
        corners = F.photo_corners(gate, a_w, F.PhotoFit(rotation_deg=deg))
        for p in _points(int(deg * 100)):
            got = F.photo_point_ndc(corners, *_uv_rolled(p, tw, th, math.radians(deg)))
            assert got == pytest.approx(_symmetric_ndc(p, gate, tw, th), abs=1e-12)


@pytest.mark.parametrize("a, a_w, o", CASES)
def test_roll_and_shift_together(a, a_w, o):
    """A rolled camera whose principal point is shifted too: rotation plus the shift turned into screen axes."""
    gate, tw, th = _setup(a, a_w, o)
    phi, cx, cy = math.radians(8.0), 0.2 * tw, -0.1 * th
    sx, sy = cx / (2 * th), cy / (2 * th)  # the shift in the rolled camera's axes, gate heights
    ox = math.cos(phi) * sx - math.sin(phi) * sy
    oy = math.sin(phi) * sx + math.cos(phi) * sy
    corners = F.photo_corners(gate, a_w, F.PhotoFit(rotation_deg=8.0, offset_x=ox, offset_y=oy))
    for p in _points(3):
        x, y, z = p
        xr = math.cos(phi) * x + math.sin(phi) * y
        yr = -math.sin(phi) * x + math.cos(phi) * y
        uv = _uv_off_axis((xr, yr, z), tw, th, cx, cy)
        assert F.photo_point_ndc(corners, *uv) == pytest.approx(_symmetric_ndc(p, gate, tw, th), abs=1e-12)


def test_a_rotation_keeps_the_photo_shape_in_any_window():
    gate = L.gate_rect_ndc(1.5, 0.6, 1.15)
    corners = F.photo_corners(gate, 0.6, F.PhotoFit(rotation_deg=30.0))
    iso = [(x * 0.6, y) for x, y in corners]  # back to isotropic units
    width = math.dist(iso[0], iso[1])
    height = math.dist(iso[0], iso[3])
    assert width / height == pytest.approx(1.5, abs=1e-12)
    assert width == pytest.approx(2 * gate[0] * 0.6, abs=1e-12)


def test_mirror_and_crop_scale():
    gate, a_w = (0.6, 0.8), 1.25
    plain = F.photo_corners(gate, a_w, F.PhotoFit())
    mirrored = F.photo_corners(gate, a_w, F.PhotoFit(mirror=True))
    for u, v in ((0.0, 0.0), (0.2, 0.7), (1.0, 0.5)):
        assert F.photo_point_ndc(mirrored, u, v) == pytest.approx(F.photo_point_ndc(plain, 1.0 - u, v), abs=1e-15)
    scaled = F.photo_corners(gate, a_w, F.PhotoFit(cropped=True, scale=0.5))
    for u, v in ((0.0, 0.0), (0.3, 0.9)):
        x, y = F.photo_point_ndc(plain, u, v)
        assert F.photo_point_ndc(scaled, u, v) == pytest.approx((0.5 * x, 0.5 * y), abs=1e-15)
    assert F.photo_corners(gate, a_w, F.PhotoFit(scale=0.5)) == plain  # not cropped: the scale waits


def test_clamping():
    fit = F.clamped(F.PhotoFit(rotation_deg=190.0, offset_x=5.0, offset_y=-5.0, scale=100.0))
    assert fit.rotation_deg == pytest.approx(-170.0) and (fit.offset_x, fit.offset_y) == (1.0, -1.0)
    assert fit.scale == F.SCALE_RANGE[1]
    assert F.clamped(F.PhotoFit(rotation_deg=-180.0)).rotation_deg == -180.0
    with pytest.raises(ValueError):
        F.clamped(F.PhotoFit(rotation_deg=float("nan")))
    with pytest.raises(ValueError):
        F.photo_corners((0.5, 0.5), 0.0, F.PhotoFit(rotation_deg=1.0))
