"""The eye lab as the oracle of the production eye (AD-033 §8, Manu 2026-11-15: "Q-E1 ja"): the promoted NumPy twins in
`src/viewport/eye_optics.py` must give the lab's numbers for the lab's eye (`mirai.eye_object.DEFAULT_EYE` = the lab's
`eye_geometry` constants). Headless. The lab is frozen: change it only to keep it running, never to follow production.

The production GLSL is checked against `eye_optics` on the GPU by `tests/test_gl_eye_pass.py`; together the chain is
lab -> eye_optics -> production GLSL."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from lookdev_eye_lab import cornea_optics as co
from lookdev_eye_lab import eye_geometry as geo
from lookdev_eye_lab import iris_fit
from lookdev_eye_lab import limbus_model as lm
from lookdev_eye_lab import studio_env as se
from mirai.eye_object import DEFAULT_EYE
from viewport import eye_optics as eo

G = eo.EyeGeometry.from_values(DEFAULT_EYE)
N = 4000


def test_geometry_is_the_labs():
    lab = co.GEOMETRY
    assert G.limbus_z == pytest.approx(lab.limbus_z, abs=1e-15)
    assert G.anterior_centre_z == pytest.approx(lab.anterior_centre_z, abs=1e-15)
    assert G.posterior_centre_z == pytest.approx(lab.posterior_centre_z, abs=1e-15)
    assert G.iris_radius == pytest.approx(geo.IRIS_RADIUS, abs=1e-15)
    assert (G.iris_a, G.iris_b) == pytest.approx((lab.iris_a, lab.iris_b), abs=1e-15)
    assert G.angle == pytest.approx(lab.angle, abs=1e-12)


@pytest.mark.parametrize("variant", ["V2", "V3"])
def test_trace_is_the_labs(variant):
    rng = np.random.default_rng(1)
    az, off, dist = rng.uniform(0, 2 * np.pi, N), np.radians(rng.uniform(0, 85, N)), rng.uniform(1.5, 5, N)
    eye = np.stack([dist * np.sin(off) * np.cos(az), dist * np.sin(off) * np.sin(az), dist * np.cos(off)], -1)
    r = G.limbus_radius * 1.05 * np.sqrt(rng.uniform(0, 1, N))
    phi = rng.uniform(0, 2 * np.pi, N)
    d = eo.normalize(np.stack([r * np.cos(phi), r * np.sin(phi), G.anterior_z(np.minimum(r, G.limbus_radius))], -1)
                     - eye)
    ours, lab = eo.trace(eye, d, variant, G), co.trace(eye, d, variant)
    assert np.array_equal(ours.kind, lab.kind)
    assert np.abs(ours.hit - lab.hit).max() < 1e-12 and np.abs(ours.entry - lab.entry).max() < 1e-12
    assert np.abs(ours.transmit_inner - lab.transmit_inner).max() < 1e-12


@pytest.mark.parametrize("hold", [False, True])
def test_iris_fit_is_the_labs(hold):
    spec = dataclasses.replace(DEFAULT_EYE, fit_pupil=0.22, fit_limbus=0.88, hold_outer_color=hold)
    lab_fit = iris_fit.IrisFit(0.22, 0.88, outer=0.88 if hold else 1.0)
    rng = np.random.default_rng(2)
    xy = rng.uniform(-geo.IRIS_RADIUS * 1.2, geo.IRIS_RADIUS * 1.2, (N, 2))
    assert np.abs(eo.iris_uv(xy, G, eo.fit_knots(spec, G)) - iris_fit.uv(xy, lab_fit)).max() < 1e-12
    assert np.abs(eo.iris_uv(xy, G) - np.array([geo.iris_uv(x, y) for x, y in xy])).max() < 1e-12


def test_limbus_functions_are_the_labs():
    rng = np.random.default_rng(3)
    params = lm.LimbusParams(band_mm=1.2, strength=0.8, normal_mm=0.6, falloff=3.0, asym=True, overlap_mm=0.2)
    u0 = eo.limbus_u0(G)
    assert u0 == pytest.approx(lm.U0, abs=1e-15)
    theta = np.radians(rng.uniform(15, 50, N))
    phi = rng.uniform(0, 2 * np.pi, N)
    p = np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], -1)
    assert np.abs(eo.sclera_u(p, G) - lm.sclera_u(p)).max() < 1e-12
    assert np.abs(eo.cornea_u(p, G) - lm.cornea_u(p)).max() < 1e-15
    shift = eo.asym_shift(p, eo.ASYM_MM * eo.MM, 0.2 * eo.MM)
    assert np.abs(shift - lm.asym_shift(p, params.asym_units, params.overlap_units)).max() < 1e-15
    u = rng.uniform(-0.08, 0.15, N)
    assert np.abs(eo.colour_weight(u, params.band, u0) - lm.colour_weight(u, params.band)).max() < 1e-15
    assert np.abs(eo.transmission(u, params.band, 3.0, u0) - lm.transmission(u, params.band, 3.0)).max() < 1e-15
    assert np.abs(eo.iris_cover(u, shift, params.cover_max, u0) - lm.iris_cover(u, shift, params.cover_max)).max() \
        < 1e-15
    nc = eo.normalize(p - np.array([0.0, 0.0, G.anterior_centre_z]))
    assert np.abs(eo.normal_blend(nc, p, u, params.normal_w) - lm.normal_blend(nc, p, u, params.normal_w)).max() < 1e-15
    eye = np.array([0.3, -0.2, 3.0])
    d = eo.normalize(p - eye)
    ours, lab = eo.sclera_through(p, d, p, G), lm.sclera_through(p, d, p)
    assert np.array_equal(ours[0], lab[0]) and np.abs(ours[1] - lab[1]).max() < 1e-12


def test_studio_and_procedural_iris_are_the_labs():
    rng = np.random.default_rng(4)
    d = eo.normalize(rng.normal(size=(N, 3)))
    for roughness in (0.04, 0.3, 0.7):
        assert np.abs(eo.td_env(d, roughness) - se.td_radiance(d, roughness)).max() < 1e-12
    assert np.array_equal(eo.procedural_iris(G, 128), geo.iris_image(128))
