"""P1b: the CPU ray model of the cornea (headless). The GLSL twins are compared in `test_gl_refraction.py`."""

from __future__ import annotations

import math

import numpy as np
import pytest

from lookdev_eye_lab import cornea_optics as co

G = co.GEOMETRY
MM = 1.0 / co.MM


# -- refraction ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("eta", [1.0 / 1.376, 1.0 / 1.3375, 1.376 / 1.336])
@pytest.mark.parametrize("angle", [0.0, 10.0, 45.0, 70.0, 89.0])
def test_refract_obeys_snell_and_stays_in_the_plane_of_incidence(eta, angle):
    n = np.array([0.0, 0.0, 1.0])
    a = math.radians(angle)
    i = np.array([math.sin(a), 0.0, -math.cos(a)])
    t = co.refract(i, n, eta)
    if eta * math.sin(a) > 1.0:
        assert np.all(t == 0.0)
        return
    assert np.linalg.norm(t) == pytest.approx(1.0, abs=1e-12)
    assert t[1] == pytest.approx(0.0, abs=1e-15) and t[2] < 0.0  # same plane, continues into the surface
    assert math.hypot(t[0], t[1]) == pytest.approx(eta * math.sin(a), abs=1e-12)  # sin(t) = eta sin(i)


def test_refract_identity_and_total_internal_reflection():
    n = np.array([0.0, 0.0, 1.0])
    i = co.normalize(np.array([0.3, 0.2, -0.9]))
    assert np.allclose(co.refract(i, n, 1.0), i)
    grazing = co.normalize(np.array([1.0, 0.0, -0.1]))
    assert np.all(co.refract(grazing, n, 1.376 / 1.0) == 0.0)  # cornea -> air beyond the critical angle
    # Cornea -> aqueous: critical angle asin(1.336 / 1.376) = 76.1 degrees.
    critical = math.degrees(math.asin(co.N_AQUEOUS / co.N_CORNEA))
    for angle, tir in ((critical - 0.2, False), (critical + 0.2, True)):
        a = math.radians(angle)
        t = co.refract(np.array([math.sin(a), 0.0, -math.cos(a)]), n, co.N_CORNEA / co.N_AQUEOUS)
        assert bool(np.all(t == 0.0)) is tir


def test_light_bends_toward_the_normal_entering_the_cornea():
    n = np.array([0.0, 0.0, 1.0])
    i = co.normalize(np.array([0.6, 0.0, -0.8]))
    v2 = co.refract(i, n, 1.0 / co.N_EFFECTIVE)
    v3 = co.refract(i, n, 1.0 / co.N_CORNEA)
    assert -v3[2] > -v2[2] > -i[2]  # the denser medium bends more


# -- intersections ---------------------------------------------------------------------------------------------------


def test_sphere_entry_hit_miss_tangent_and_inside():
    c, r = np.zeros(3), 1.0
    hit, t = co.sphere_entry(np.array([0.0, 0.0, 5.0]), np.array([0.0, 0.0, -1.0]), c, r)
    assert hit and t == pytest.approx(4.0)
    hit, _ = co.sphere_entry(np.array([2.0, 0.0, 5.0]), np.array([0.0, 0.0, -1.0]), c, r)
    assert not hit
    hit, t = co.sphere_entry(np.array([1.0, 0.0, 5.0]), np.array([0.0, 0.0, -1.0]), c, r)
    assert hit and t == pytest.approx(5.0)  # tangent
    hit, t = co.sphere_entry(np.zeros(3), np.array([0.0, 0.0, 1.0]), c, r)
    assert hit and t == pytest.approx(1.0)  # from inside: the far wall
    hit, _ = co.sphere_entry(np.array([0.0, 0.0, 5.0]), np.array([0.0, 0.0, 1.0]), c, r)
    assert not hit  # sphere behind the origin


@pytest.mark.parametrize("r", [0.0, 0.1, G.pupil_radius, 0.3, G.iris_radius])
def test_iris_cone_hit_on_a_vertical_ray(r):
    hit, t, rr = co.iris_cone_hit(np.array([r, 0.0, 2.0]), np.array([0.0, 0.0, -1.0]))
    assert hit and rr == pytest.approx(r, abs=1e-12)
    assert 2.0 - t == pytest.approx(float(G.iris_z(r)), abs=1e-12)


def test_iris_cone_hit_oblique_and_upward_rays():
    d = co.normalize(np.array([0.5, 0.2, -1.0]))
    o = np.array([-0.2, 0.0, 1.2])
    hit, t, r = co.iris_cone_hit(o, d)
    p = o + t * d
    assert hit and p[2] == pytest.approx(G.iris_a + G.iris_b * r, abs=1e-12)
    hit, _, _ = co.iris_cone_hit(np.array([0.0, 0.0, 1.0]), np.array([0.0, 0.0, 1.0]))
    assert not hit  # going away from the iris


# -- geometry --------------------------------------------------------------------------------------------------------


def test_thickness_profile_is_plausible_and_grows_toward_the_limbus():
    r = np.linspace(0.0, G.limbus_radius, 50)
    t = G.thickness_at(r) * MM
    assert t[0] == pytest.approx(0.55, abs=1e-9)
    assert np.all(np.diff(t) > 0.0)
    assert 0.65 < t[-1] < 0.85  # peripheral corneal thickness, Gullstrand-like
    assert np.all(G.posterior_z(r[r < G.posterior_radius]) < G.anterior_z(r[r < G.posterior_radius]))


def test_anterior_rim_is_the_sclera_limbus_and_the_chamber_closes_at_the_iris():
    assert float(G.anterior_z(G.limbus_radius)) == pytest.approx(G.limbus_z, abs=1e-12)
    r_angle, z_angle = G.angle
    assert G.pupil_radius < r_angle < G.limbus_radius < G.iris_radius
    assert float(G.posterior_z(r_angle)) == pytest.approx(z_angle, abs=1e-9)
    assert float(G.iris_z(r_angle)) == pytest.approx(z_angle, abs=1e-9)
    assert 5.0 < r_angle * MM < 6.0


def test_limbus_weight_blends_from_the_angle_to_the_rim():
    assert co.limbus_weight(G.angle[0]) == 0.0 and co.limbus_weight(G.limbus_radius) == 1.0
    assert 0.0 < co.limbus_weight(0.5 * (G.angle[0] + G.limbus_radius)) < 1.0


# -- traces ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("variant", co.VARIANTS)
def test_on_axis_ray_reaches_the_pupil_centre(variant):
    tr = co.trace(np.array([0.0, 0.0, 5.0]), np.array([[0.0, 0.0, -1.0]]), variant)
    assert tr.kind[0] == co.PUPIL
    assert np.allclose(tr.hit[0, :2], 0.0, atol=1e-12)
    expected = 1.0 if variant != "V3" else 1.0 - co.f0_between(co.N_CORNEA, co.N_AQUEOUS)
    assert tr.transmit_inner[0] == pytest.approx(expected, abs=1e-12)


def test_rays_missing_the_cap_and_rays_into_the_limbal_tissue():
    eye = np.array([0.0, 0.0, 5.0])
    miss = co.normalize(np.array([[0.9, 0.0, -5.0]]))  # passes beside the cornea
    assert co.trace(eye, miss, "V2").kind[0] == co.MISS
    rim = co.normalize(np.array([[G.limbus_radius - 0.005, 0.0, G.limbus_z]]) - eye)
    for variant in ("V2", "V3"):
        assert co.trace(eye, rim, variant).kind[0] == co.LIMBUS  # just inside the rim: below the chamber angle
    assert co.trace(eye, rim, "V1").kind[0] == co.IRIS  # P1 has no limbal tissue


@pytest.mark.parametrize("variant", ["V2", "V3"])
def test_front_view_magnification_matches_optics(variant):
    """The pupil seen through the cornea: traced magnification within 1.5 % of the paraxial one, in the range of the
    human entrance pupil (~1.13), and the virtual pupil lies in front of the real one."""
    paraxial, paraxial_depth = co.paraxial_entrance_pupil(variant)
    r, z = co.virtual_pupil(variant)
    traced = r / G.pupil_radius
    assert 1.10 < traced < 1.18
    assert traced == pytest.approx(paraxial, rel=0.015)
    real_depth = G.apex_z - float(G.iris_z(G.pupil_radius))
    assert G.apex_z - z == pytest.approx(paraxial_depth, rel=0.03)
    assert G.apex_z - z < real_depth - 0.5 * co.MM  # appears more than half a millimetre closer


def test_v2_and_v3_virtual_pupils_agree_closely_on_axis():
    r2, z2 = co.virtual_pupil("V2")
    r3, z3 = co.virtual_pupil("V3")
    assert abs(r2 - r3) * MM < 0.01 and abs(z2 - z3) * MM < 0.02  # mm


def test_refraction_widens_the_angle_the_pupil_stays_visible():
    v1 = co.visibility_limit("V1", co.PUPIL)
    v2 = co.visibility_limit("V2", co.PUPIL)
    assert v2 > v1 + 5.0 and 85.0 < v2 < 100.0


def test_view_metrics_small_frame():
    from mirai.viewport.camera import OrbitCamera

    from lookdev_eye_lab import eye_geometry as geo

    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=2.5)
    camera.set_view(0.0, 0.0)
    m = co.view_metrics(camera, 128, 96, geo.iris_image(64))
    assert m["V2"]["pupil_px"] > 1.2 * m["V1"]["pupil_px"]
    assert m["V1-V2"]["disp_px_median"] > m["V2-V3"]["disp_px_median"]
