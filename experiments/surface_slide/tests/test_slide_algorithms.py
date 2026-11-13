"""Regression tests of the candidates: what the report claims, as assertions (thresholds leave a margin over the
measured values; the measured values are in `results/` and the report)."""

from __future__ import annotations

import numpy as np
import pytest

from surface_slide import algorithms as A
from surface_slide import geodesic as geo
from surface_slide import geometries as G
from surface_slide import harness as H
from surface_slide import metrics as M
from surface_slide import scenarios as S
from surface_slide.fields import mirror, mirror_partners

BAD = geo.FLAG_STUCK | geo.FLAG_MAXITER


def by_name(scenarios, name):
    return next(s for s in scenarios if s.name == name)


@pytest.fixture(scope="module")
def u_scenarios():
    return S.u_scenarios()


@pytest.fixture(scope="module")
def cage_scenarios():
    return S.gollum_scenarios("cage")


# --- the tracer is exact on a developable surface -----------------------------------------------------------------------

@pytest.mark.parametrize("make", [lambda: A.GeodesicAbs("project"), lambda: A.GeodesicWalk("project"),
                                  lambda: A.GeodesicPursuit("project")])
def test_geodesics_match_the_unrolled_u_exactly(u_scenarios, make):
    """On the polyhedral U a geodesic is a straight line in the unrolled chart: an exact ground truth."""
    for scn in u_scenarios:
        if scn.truth is None:
            continue
        r = H.run(scn, make())
        assert r.metrics["err_intended"]["max"] < 1e-12, scn.name
        assert not np.any(r.flags & BAD)


def test_geodesic_goes_round_the_bend_and_projection_does_not(u_scenarios):
    scn = by_name(u_scenarios, "C3_u_gap3cells_around_bend")
    an = scn.analytic
    r = H.run(scn, A.GeodesicAbs("project"))
    s_end = an.anchor_sy(scn.ref.V, scn.ref.T, r.tri[-1], r.bary[-1])[:, 0]
    assert np.all(an.wall(s_end) == 2)                      # arrived on wall B, along the surface
    assert r.metrics["continuity"]["region_jumps"] == 0
    r2 = H.run(scn, A.ClosestGlobal())
    s2 = an.anchor_sy(scn.ref.V, scn.ref.T, r2.tri[-1], r2.bary[-1])[:, 0]
    assert np.all(an.wall(s2) == 1)                         # stuck at the bottom of the bend


# --- concave reliability ---------------------------------------------------------------------------------------------------

CONCAVE = ["C1_u_gap3cells_into_gap_30deg", "C1_u_gap3cells_into_gap_60deg", "C1_u_gap3cells_into_gap_80deg",
           "C2_u_gap3cells_along_y_into_gap", "C1_u_gap1cell_into_gap_60deg", "C2_u_gap1cell_along_y_into_gap"]


@pytest.mark.parametrize("name", CONCAVE)
def test_global_projection_switches_wall(u_scenarios, name):
    """The documented failure: every vertex ends on the opposite wall, with a small global distance."""
    scn = by_name(u_scenarios, name)
    for cand in (A.ClosestGlobal(), A.RayNormal()):
        r = H.run(scn, cand)
        assert r.metrics["wrong_region_final"] == scn.setup.n
        assert r.metrics["continuity"]["region_jumps"] == scn.setup.n
        assert r.metrics["dev_tracked"]["max"] < 1e-12       # "on the surface" - of the wrong wall


@pytest.mark.parametrize("name", CONCAVE)
@pytest.mark.parametrize("make", [lambda: A.GeodesicAbs("project"), lambda: A.GeodesicWalk("project"),
                                  lambda: A.GeodesicPursuit("project"), lambda: A.GeodesicInc(),
                                  lambda: A.TangentLocal(), lambda: A.ClosestLocal()])
def test_anchored_candidates_keep_their_wall(u_scenarios, name, make):
    scn = by_name(u_scenarios, name)
    r = H.run(scn, make())
    assert r.metrics["wrong_region_any_frame"] == 0
    assert r.metrics["continuity"]["region_jumps"] == 0


# --- sphere -----------------------------------------------------------------------------------------------------------------

def test_sphere_exponential_map_converges():
    errors = []
    for n in (8, 16, 32):
        geo_ = G.cube_sphere(n)
        ref = H.build_ref(geo_.V, geo_.faces)
        setup = A.SlideSetup.from_vertices(ref, S.sphere_probes(ref, 32))
        delta = np.array([0.3, 0.2, 0.25])
        cand = A.GeodesicAbs("project")
        cand.begin(setup)
        r = cand.update(delta)
        truth = geo_.analytic.exp(setup.p0, geo_.analytic.tangent(setup.p0, np.broadcast_to(delta, setup.p0.shape)))
        errors.append(np.linalg.norm(r.pos - truth, axis=1).max())
        assert geo_.analytic.distance(r.pos).max() <= 0.3 * ref.mean_edge ** 2   # facet sag ~ h^2 / (4 R) at most
    assert errors[0] > errors[1] > errors[2]


def test_phong_evaluation_removes_the_facet_sag():
    geo_ = G.cube_sphere(16)
    ref = H.build_ref(geo_.V, geo_.faces)
    setup = A.SlideSetup.from_vertices(ref, S.sphere_probes(ref, 32))
    delta = np.array([0.3, 0.2, 0.25])
    flat, phong = A.GeodesicAbs("project"), A.GeodesicAbs("project", evaluator="phong", alpha=0.5)
    flat.begin(setup)
    phong.begin(setup)
    d_flat = geo_.analytic.distance(flat.update(delta).pos).max()
    d_phong = geo_.analytic.distance(phong.update(delta).pos).max()
    assert d_phong < d_flat / 50.0


def test_transport_moves_a_rigid_patch_without_stretching_it_on_a_cylinder():
    scn = by_name(S.cylinder_scenarios(), "B5_cylinder_rigid_circ")
    decal = H.run(scn, A.GeodesicAbs("transport")).metrics["edges_rigid"]
    proj = H.run(scn, A.GeodesicAbs("project")).metrics["edges_rigid"]
    closest = H.run(scn, A.ClosestGlobal()).metrics["edges_rigid"]
    assert decal["max_abs_rel"] < 0.01
    assert proj["max_abs_rel"] > 3 * decal["max_abs_rel"]
    assert closest["max_abs_rel"] > 10 * decal["max_abs_rel"]


# --- stability: absolute, incremental, pursuit -------------------------------------------------------------------------------

def test_absolute_geodesic_is_a_function_of_the_drag_alone(cage_scenarios):
    scn = by_name(cage_scenarios, "D_cage_cheek_to_eye")
    delta = scn.path[-1]
    one = A.GeodesicAbs("transport")
    one.begin(scn.setup)
    direct = one.update(delta).pos
    two = A.GeodesicAbs("transport")
    two.begin(scn.setup)
    for d in H.polyline_path([delta * [1, 0, 0], delta * [1.5, -0.5, 0], delta], 7):
        via = two.update(d).pos
    assert np.array_equal(direct, via)
    assert np.array_equal(two.update(np.zeros(3)).pos, scn.setup.p0)      # zero drag: the start, to the bit


@pytest.mark.parametrize("feature", ["cheek", "brow", "nose_side"])
def test_pursuit_is_speed_limited_and_closes_the_loop(cage_scenarios, feature):
    scn = by_name(cage_scenarios, f"D_cage_{feature}_loop")
    r = H.run(scn, A.GeodesicPursuit("transport", gain=1.0))
    c = r.metrics["continuity"]
    assert c["max_step_ratio"] <= 2.0 + 1e-6
    assert c["region_jumps"] == 0
    assert r.metrics["closure"]["max"] == 0.0
    assert r.metrics["dev_tracked_max_over_frames"] < 1e-12
    assert not np.any(r.flags & BAD)


def test_plain_absolute_geodesic_pops_on_the_coarse_cage(cage_scenarios):
    """Why the limiter exists: turning the drag on the coarse cage moves some vertex several times faster than it."""
    scn = by_name(cage_scenarios, "D_cage_nose_side_loop")
    r = H.run(scn, A.GeodesicAbs("transport"))
    assert r.metrics["continuity"]["max_step_ratio"] > 3.0
    assert r.metrics["closure"]["max"] == 0.0


def test_incremental_candidates_do_not_close_the_loop(cage_scenarios):
    scn = by_name(cage_scenarios, "D_cage_nose_side_loop")
    h = scn.ref.mean_edge
    for cand in (A.GeodesicInc(), A.TangentLocal()):
        assert H.run(scn, cand).metrics["closure"]["max"] > 0.5 * h
    walk = H.run(scn, A.GeodesicWalk("transport")).metrics
    assert walk["continuity"]["max_step_ratio"] <= 1.0 + 1e-6
    assert 0.0 < walk["closure"]["max"] < H.run(scn, A.GeodesicInc()).metrics["closure"]["max"]


def test_no_candidate_of_the_geodesic_family_leaves_the_surface_on_gollum(cage_scenarios):
    for scn in cage_scenarios:
        for cand in (A.GeodesicPursuit("transport"), A.GeodesicWalk("transport")):
            r = H.run(scn, cand)
            assert r.metrics["dev_tracked_max_over_frames"] < 1e-9 * scn.ref.bbox_diag, scn.name
            assert r.metrics["continuity"]["region_jumps"] == 0, scn.name
            assert not np.any(r.flags & BAD), scn.name


def test_global_projection_jumps_between_the_lips(cage_scenarios):
    scn = by_name(cage_scenarios, "D_cage_lip_down")
    assert H.run(scn, A.ClosestGlobal()).metrics["continuity"]["region_jumps"] > 0
    assert H.run(scn, A.GeodesicPursuit("transport")).metrics["continuity"]["region_jumps"] == 0


# --- soft selection ----------------------------------------------------------------------------------------------------------

def test_weights_scale_the_travel_and_zero_weight_does_not_move():
    from surface_slide.studies import _banded_setup

    geo_ = S.sphere_geo(16)
    ref = S.ref_of(geo_)
    setup, _ = _banded_setup(ref, S.nearest_vertex(ref, (0, 0, 1.0)))
    n0 = setup.n0[setup.pivot]
    delta = 2.5 * ref.mean_edge * np.cross(n0, [0.0, 1.0, 0.3]) / np.linalg.norm(np.cross(n0, [0.0, 1.0, 0.3]))
    cand = A.GeodesicPursuit("transport")
    cand.begin(setup)
    r = cand.update(delta)
    travel = np.linalg.norm(r.pos - setup.p0, axis=1)
    full = travel[setup.weights == 1.0].mean()
    assert np.array_equal(r.pos[setup.weights == 0.0], setup.p0[setup.weights == 0.0])
    for w in (0.25, 0.5):
        assert travel[setup.weights == w].mean() / full == pytest.approx(w, rel=0.02)
    assert M.tracked_deviation(ref, r.pos, r.tri).max() < 1e-12            # every weight exactly on the surface
    # the linear blend between start and full result is a chord point: off the surface
    lerp = A.Lerp(A.GeodesicAbs("transport"))
    lerp.begin(setup)
    off = geo_.analytic.distance(lerp.update(delta).pos)
    on = geo_.analytic.distance(r.pos)
    assert off[setup.weights == 0.5].max() > 5.0 * on[setup.weights == 0.5].max()


# --- symmetry ----------------------------------------------------------------------------------------------------------------

def test_cube_sphere_is_exactly_mirror_symmetric():
    geo_ = G.cube_sphere(8)
    partner = mirror_partners(geo_.V)
    assert np.all(partner >= 0)
    assert np.array_equal(geo_.V[partner], mirror(geo_.V))


def test_gollum_cage_carries_its_symmetry_and_mirroring_is_exact():
    mesh, ref = S.gollum_cage_ref()
    assert mesh.plane == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    partner = mirror_partners(ref.V)
    assert np.all(partner >= 0)
    v = S.front_vertex(ref, *S.CAGE_FEATURES["nose_side"])
    setup = S.soft_setup(ref, [v], 0.09, v)
    cand = A.GeodesicPursuit("transport")
    cand.begin(setup)
    r = cand.update(np.array([0.05, 0.02, 0.0]))
    mirrored = mirror(r.pos)
    assert np.array_equal(mirror(mirrored), r.pos)          # the mirror image is exact, so pairs stay exact pairs
    # and the mirror image lies on the mirrored half of the same reference (the cage is symmetric)
    _, _, d = ref.closest_point(mirrored)
    assert d.max() < 1e-9 * ref.bbox_diag


# --- a reference that is not the moving mesh ----------------------------------------------------------------------------------

def test_points_of_another_mesh_slide_on_the_reference():
    """A coarse sphere's vertices anchored on a fine sphere (closest point), then moved: they stay on the fine one."""
    coarse, fine = G.cube_sphere(6), G.cube_sphere(24)
    ref = H.build_ref(fine.V, fine.faces)
    setup = A.SlideSetup.from_points(ref, coarse.V[::5])
    assert np.all(setup.verts == -1)
    cand = A.GeodesicPursuit("project")
    cand.begin(setup)
    r = cand.update(np.array([0.25, -0.1, 0.15]))
    assert M.tracked_deviation(ref, r.pos, r.tri).max() < 1e-12
    assert fine.analytic.distance(r.pos).max() < 0.3 * ref.mean_edge ** 2
    assert np.linalg.norm(r.pos - setup.p0, axis=1).max() > 0.1
    assert np.array_equal(cand.update(np.zeros(3)).pos, setup.p0)


def test_mirrored_triangulation_puts_the_mirror_image_on_the_reference():
    mesh, plain = S.gollum_cage_ref(False)
    _, mirrored = S.gollum_cage_ref(True)
    partner = mirror_partners(plain.V)

    def unmatched(ref):
        tris = {tuple(sorted(t)) for t in ref.T.tolist()}
        return sum(1 for t in ref.T.tolist() if tuple(sorted(int(partner[v]) for v in t)) not in tris)

    assert unmatched(plain) > 0 and unmatched(mirrored) == 0
    assert mirrored.n_boundary_edges == plain.n_boundary_edges and mirrored.n_nonmanifold_edges == 0


def test_seam_vertices_slide_on_the_seam():
    from surface_slide.seam import SeamCurve

    mesh, ref = S.gollum_cage_ref()
    curve = SeamCurve(ref, mesh.seam_edges)
    for v in mesh.seam_vertices.tolist()[::3]:
        tri, bary, pos, _ = curve.slide(v, np.array([0.02, 0.06, -0.03]))
        assert pos[0] == 0.0
        assert np.array_equal(ref.point(np.array([tri]), bary[None])[0], pos) or \
            np.linalg.norm(ref.point(np.array([tri]), bary[None])[0] - pos) < 1e-15
