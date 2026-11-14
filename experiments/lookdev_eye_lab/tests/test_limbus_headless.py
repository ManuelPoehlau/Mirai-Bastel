"""P1c model, state, keys and entry point (headless)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from lookdev_gpu_probe import cube_math as cm
from lookdev_eye_lab import cornea_optics as co
from lookdev_eye_lab import eye_geometry as geo
from lookdev_eye_lab import iris_fit
from lookdev_eye_lab import lab_state as ls
from lookdev_eye_lab import limbus_gl as lg
from lookdev_eye_lab import limbus_model as lm

LAB = Path(__file__).resolve().parents[1]
P = lm.LimbusParams()


def _ring_point(phi=0.3):
    return np.array([lm.RING_RADIUS * np.cos(phi), lm.RING_RADIUS * np.sin(phi), geo.LIMBUS_Z])


def test_the_limbus_coordinate_is_zero_on_the_shared_ring_from_both_sides():
    p = _ring_point()
    assert lm.sclera_u(p) == pytest.approx(0.0, abs=1e-12) and lm.cornea_u(p) == pytest.approx(0.0, abs=1e-12)
    assert lm.U0 == pytest.approx((co.GEOMETRY.angle[0] - geo.LIMBUS_RADIUS), abs=1e-12)
    assert -0.35 < lm.U0 / lm.MM < -0.25  # the chamber angle ~0.29 mm inside the ring


def test_band_weights_run_from_the_chamber_angle_to_the_band_edge():
    assert lm.colour_weight(lm.U0, P.band) == 0.0 and lm.colour_weight(P.band, P.band) == 1.0
    assert lm.transmission(lm.U0, P.band, P.falloff) == 1.0 and lm.transmission(P.band, P.band, P.falloff) == 0.0
    u = np.linspace(lm.U0 - 0.01, P.band + 0.01, 500)
    assert np.all(np.diff(lm.colour_weight(u, P.band)) >= 0) and np.all(np.diff(lm.transmission(u, P.band, 4)) <= 0)
    sclera, limbal = np.array([0.7, 0.68, 0.6]), np.array([0.01, 0.01, 0.02])
    assert np.allclose(lm.tint(1.0, limbal, sclera, 1.0), sclera)  # beyond the band: the plain sclera
    assert np.allclose(lm.tint(0.0, limbal, sclera, 0.0), sclera)  # strength 0: no tint


def test_normal_blend_is_halfway_on_the_ring_and_pure_outside():
    p = _ring_point()
    n_c = co.normalize(p - np.array([0.0, 0.0, geo.CORNEA_CENTRE_Z]))
    n_s = co.normalize(p)
    kink = np.degrees(np.arccos(np.dot(n_c, n_s)))
    assert kink == pytest.approx(19.6, abs=0.1)  # the seam's normal kink (handoff)
    mid = lm.normal_blend(n_c, n_s, 0.0, P.normal_w)
    assert np.allclose(mid, co.normalize(n_c + n_s))
    assert np.allclose(lm.normal_blend(n_c, n_s, -P.normal_w, P.normal_w), n_c)
    assert np.allclose(lm.normal_blend(n_c, n_s, P.normal_w, P.normal_w), n_s)


def test_asymmetry_is_zero_when_off_and_largest_at_top_and_bottom():
    pts = np.array([[0.5, 0.0, 0.8], [0.0, 0.5, 0.8], [0.0, -0.5, 0.8], [0.35, 0.35, 0.8]])
    assert np.all(lm.asym_shift(pts, lm.LimbusParams().asym_units) == 0.0)
    on = lm.asym_shift(pts, lm.LimbusParams(asym=True).asym_units) / lm.MM
    assert on == pytest.approx([0.0, lm.ASYM_MM, lm.ASYM_MM, lm.ASYM_MM / 2])
    amount = lm.ASYM_MM * lm.MM
    assert np.all(lm.iris_cover(np.linspace(-0.1, 0.0, 9), 0.0, amount) == 0.0)  # no cover without the shift
    assert np.all(lm.iris_cover(np.linspace(-0.1, 0.0, 9), amount, 0.0) == 0.0)  # switch off
    assert lm.iris_cover(lm.U0, amount, amount) == pytest.approx(1.0)


def test_iris_cover_is_continuous_across_the_horizontal():
    """Regression (Manu, reference PC 2026-11-14): with the asymmetry on, a seam left and right on the limbus - the
    cover jumped from 0 (exactly horizontal) to 1 (any shift > 0) for rays between the chamber angle and the iris edge."""
    amount = lm.ASYM_MM * lm.MM
    phi = np.radians(np.linspace(-20.0, 20.0, 1601))
    p = np.stack([np.cos(phi), np.sin(phi), np.zeros_like(phi)], -1)
    shift = lm.asym_shift(p, amount)
    for u_mm in (-0.28, -0.22, -0.17, -0.05):
        cover = lm.iris_cover(u_mm * lm.MM, shift, amount)
        assert cover[800] == 0.0 and np.max(np.abs(np.diff(cover))) < 0.01, u_mm
    top = np.array([[0.0, 1.0, 0.0]])
    assert lm.iris_cover(lm.U0 - 0.5 * amount, lm.asym_shift(top, amount), amount)[0] == pytest.approx(0.5)


def test_the_sclera_band_sees_the_iris_root_through_the_tissue():
    """A straight-on camera: just outside the ring the refracted ray reaches the iris cone; far out it does not."""
    eye = np.array([0.0, 0.0, 3.0])
    theta = lm.THETA_RING + np.array([0.1, 3.0]) * lm.MM
    p = np.stack([np.sin(theta), np.zeros(2), np.cos(theta)], -1)
    hit, point = lm.sclera_through(p, co.normalize(p - eye), co.normalize(p))
    assert hit[0] and not hit[1]
    assert geo.LIMBUS_RADIUS < np.hypot(*point[0, :2]) <= geo.IRIS_RADIUS


def test_image_limbal_colour_reads_the_outer_ring_only(tmp_path):
    size = 128
    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    y, x = np.meshgrid(c, c, indexing="ij")
    rho = np.hypot(x, y)
    rgb = np.full((size, size, 3), 0.5)
    rgb[(rho >= 0.83) & (rho < 0.88)] = (1.0, 0.0, 0.0)
    path = tmp_path / "x.png"
    cm.write_png(path, rgb)
    before = path.read_bytes()
    colour, note = lm.image_limbal_colour(path, iris_fit.IrisFit(0.2, 0.88, outer=0.88))
    assert colour == pytest.approx((1.0, 0.0, 0.0), abs=0.02) and "0.83-0.88" in note
    colour, _ = lm.image_limbal_colour(path)  # no fit: the lab's limbus share 0.819 -> mostly grey
    assert colour[1] > 0.1
    assert path.read_bytes() == before


def test_limbus_state_defaults():
    s = lg.LimbusState()
    assert s.refraction == "V2" and s.limbus_level == "L0" and s.colour_source == "shader" and not s.asym
    assert s.refraction_active and not s.limbus_active
    assert lg.LimbusState(limbus_level="L2").limbus_active
    assert not lg.LimbusState(limbus_level="L2", technique="T-A").limbus_active
    assert lg.LimbusState(limbus_level="L3", asym=True).variant == "T-C_V2_L3_asym"
    for name, (_text, action) in ls.KEYS.items():  # P1's keys keep the limbus state
        assert isinstance(action(s, False), lg.LimbusState), name


def test_run_limbus_parser_and_keys():
    sys.path.insert(0, str(LAB))
    try:
        import run_limbus
        import run_refraction
    finally:
        sys.path.remove(str(LAB))
    args = run_limbus.build_parser().parse_args([])
    assert args.level == "L0" and args.refraction == "V2"
    taken = set(ls.KEYS) | set(run_refraction.REFRACTION_KEYS) | {"J", "Z", "P", "F1", "ESCAPE"}
    assert not set(run_limbus.LIMBUS_KEYS) & taken
    s = lg.LimbusState()
    for name, (_text, action) in run_limbus.LIMBUS_KEYS.items():
        action(s, False)
        action(s, True)
    run_limbus.LIMBUS_KEYS["Q"][1](s, False)
    run_limbus.LIMBUS_KEYS["A"][1](s, False)
    assert s.limbus_level == "L1" and s.asym
