"""WP-KNIFE-01 S2 — the parity rows as the executable spec of the Production `KnifeTool`.

Rows P01–P15, S1–S5 of `docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md` §1.2, plus the R3 / R5
chord cases (F2) and edge rings on the head (P15), driven through `tests/knife_parity_driver.py`.
Every literal below was recorded from the tool *before* S2 (commit "Tests: parity rows ...") — the
real-cut `KnifeTool` — and S2 (virtual path, resolved at commit) must reproduce it unchanged.

Intended changes (decided: AQ1 = Q5 behaviour, Manu 2026-10-01; and the stated assumption "a session
that cuts nothing leaves mesh and History untouched") are written with their *new* expected value
and marked `xfail(strict=True)` while the pre-S2 tool runs; S2 flips them and drops the mark. P10 (edge -> edge across faces that share
nothing) stays refused until slice S4 (planner).

Asserted per row: which clicks are accepted, `accepts() == click()` on every click, the mesh
(position-canonical face hash + V/E/F), History length, the selection residue (selected edges as
position pairs, Edge mode), History Undo / Redo of the committed entry, a clean geometry check.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from tests.knife_parity_driver import (
    HEAD_ASSET,
    HEAD_RINGS,
    R3_CLICKS,
    R5_CLICKS,
    REFERENCES,
    ROWS,
    SESSION_BASE,
    SESSIONS,
    e,
    head_mesh,
    r3_mesh,
    ring_walk,
    run,
    untouched_hash,
)

GRID_UNTOUCHED = "e2120bc843ae026c"
R3_SETUP_FACES = "db59b359966b0398"


def _committed(r, faces, vef_, residue, accepted):
    assert r.accepted == accepted
    assert r.consistent, "accepts() != click()"
    assert r.faces == faces and r.vef == vef_
    assert r.history == 1 and r.mode == "EDGE"
    assert r.residue == residue
    assert r.undo_restores is True and r.redo_restores is True
    assert r.broken == []


def _nothing(r, accepted, faces=GRID_UNTOUCHED):
    assert r.accepted == accepted
    assert r.consistent, "accepts() != click()"
    assert r.faces == faces
    assert r.history == 0 and r.mode == "-" and r.residue == []
    assert r.content_changed is False
    assert r.broken == []


def test_untouched_fixture_hashes():
    assert untouched_hash("grid") == GRID_UNTOUCHED


# -- same result before and after S2 ---------------------------------------------------------------

def test_p01_edge_to_edge_across_one_quad():
    _committed(run(*ROWS["P01"]), "fcd82c4e071cc3b6", "27/43/17",
               [((0.5, 0.0, 0.0), (0.5, 1.0, 0.0))], "++")


def test_p02_vertex_to_vertex_diagonal():
    _committed(run(*ROWS["P02"]), "14db861c4d80dae4", "25/41/17",
               [((1.0, 1.0, 0.0), (2.0, 2.0, 0.0))], "++")


def test_p03_vertex_edge_edge_vertex_over_three_quads():
    _committed(run(*ROWS["P03"]), "7d3d8ef9d7043cc8", "27/45/19",
               [((0.0, 0.0, 0.0), (1.0, 0.5, 0.0)), ((1.0, 0.5, 0.0), (2.0, 0.5, 0.0)),
                ((2.0, 0.5, 0.0), (3.0, 1.0, 0.0))], "++++")


P04_RESIDUE = [((0.0, 0.3, 0.0), (1.0, 0.6, 0.0)), ((1.0, 0.6, 0.0), (2.0, 0.3, 0.0)),
               ((2.0, 0.3, 0.0), (3.0, 0.6, 0.0))]


def test_p04_zig_zag_edge_chain():
    _committed(run(*ROWS["P04"]), "522319907ecab5d7", "29/47/19", P04_RESIDUE, "++++")


def test_p05_closed_diamond_back_on_the_first_point():
    """The 5th click is the first point again (today a real vertex; S2: the own-point target)."""
    _committed(run(*ROWS["P05"]), "edd72943a07ff45d", "29/48/20",
               [((1.5, 2.0, 0.0), (2.0, 1.5, 0.0)), ((1.5, 2.0, 0.0), (2.0, 2.5, 0.0)),
                ((2.0, 1.5, 0.0), (2.5, 2.0, 0.0)), ((2.0, 2.5, 0.0), (2.5, 2.0, 0.0))], "+++++")


def test_p06_cube_chord_across_the_top_corner():
    _committed(run(*ROWS["P06"]), "552334e4e6a44f80", "10/15/7",
               [((0.0, 1.0, 1.0), (1.0, 1.0, 0.0))], "++")


def test_p07_cube_ring_over_four_sides_closed():
    _committed(run(*ROWS["P07"]), "b84e2c794344c67d", "12/20/10",
               [((0.0, -1.0, -1.0), (0.0, -1.0, 1.0)), ((0.0, -1.0, -1.0), (0.0, 1.0, -1.0)),
                ((0.0, -1.0, 1.0), (0.0, 1.0, 1.0)), ((0.0, 1.0, -1.0), (0.0, 1.0, 1.0))], "+++++")


def test_p10_edge_to_edge_across_faces_that_share_nothing_is_refused_until_s4():
    """Q5 plans across (2 cuts); Production keeps refusing the second click until the planner (S4)."""
    r = run(*ROWS["P10"])
    assert r.accepted == "+-" and r.consistent
    assert r.broken == []


def test_p12_one_vertex_click_then_enter_commits_nothing():
    _nothing(run(*ROWS["P12"]), "+")


def test_p13_same_vertex_twice_is_refused():
    _nothing(run(*ROWS["P13"]), "+-")


def test_s1_undo_redo_then_commit_equals_the_plain_run():
    r = run("grid", SESSION_BASE, ops=SESSIONS["S1"])
    assert r.steps == "u+ r+"
    _committed(r, "522319907ecab5d7", "29/47/19", P04_RESIDUE, "++++")


def test_s2_two_undos_keep_the_first_segment():
    r = run("grid", SESSION_BASE, ops=SESSIONS["S2"])
    assert r.steps == "u+ u+"
    _committed(r, "2ec15b5702aaf8c1", "27/43/17", [((0.0, 0.3, 0.0), (1.0, 0.6, 0.0))], "++++")


def test_s3_a_new_click_clears_the_redo_branch():
    r = run("grid", SESSION_BASE, ops=SESSIONS["S3"])
    assert r.steps == "u+ r-"
    _committed(r, "978b37532c3c21c1", "29/47/19",
               [((0.0, 0.3, 0.0), (1.0, 0.6, 0.0)), ((1.0, 0.6, 0.0), (2.0, 0.3, 0.0)),
                ((2.0, 0.3, 0.0), (2.5, 1.0, 0.0))], "+++++")


def test_s5_undo_of_the_start_and_cancel_restore_exactly():
    r = run("grid", [e((0, 0, 0), (1, 0, 0), .5)],
            ops=["undo", ("click", e((0, 0, 0), (1, 0, 0), .5)), ("click", e((2, 0, 0), (2, 1, 0), .5))],
            finish="cancel")
    assert r.steps == "u+" and r.accepted == "++-"
    _nothing(r, "++-")


def test_r5_chord_out_of_a_concave_face_is_refused_and_clean():
    """F2: the chord (2,1)->(1,2) leaves the L face — refused (Q5 would plan across: slice S4)."""
    _nothing(run("L", R5_CLICKS), "+-", faces=untouched_hash("L"))


HEAD_EXPECTED = {
    (3, 0): "04946028ec325e39", (3, 18): "6770b2261f5cc845", (3, 36): "3130fce8deb7796e",
    (6, 0): "8260b7ac283d2886", (6, 18): "d9c6776868dbf0f2", (6, 36): "d80bc02dbd9711d9",
    (10, 0): "0ee218e8b9a4430a", (10, 18): "c8565289f003bd88", (10, 36): "279b7cf89bdd40b4",
}
HEAD_VEF = {3: "329/653/326", 6: "332/659/329", 10: "336/667/333"}


@pytest.mark.skipif(not HEAD_ASSET.is_file(), reason="head asset not found (examples/meshes/)")
@pytest.mark.parametrize("n,start", HEAD_RINGS)
def test_p15_head_edge_rings(n, start):
    r = run("head", ring_walk(head_mesh(), n, start))
    assert r.accepted == "+" * n and r.consistent
    assert r.faces == HEAD_EXPECTED[(n, start)] and r.vef == HEAD_VEF[n]
    assert r.history == 1 and r.mode == "EDGE" and len(r.residue) == n - 1
    assert r.undo_restores and r.redo_restores
    assert r.broken == []


# -- intended changes (AQ1; "a session that cuts nothing leaves mesh and History untouched") --------

S2_CHANGE = pytest.mark.xfail(strict=True, reason="S2: expected to change (AQ1 / no-cut session), see docstring")


@S2_CHANGE
def test_p08_vertex_to_adjacent_vertex_is_accepted_as_skip():
    """Today: 2nd click refused (`+-`). S2 (AQ1): accepted, nothing cut, nothing committed."""
    _nothing(run(*ROWS["P08"]), "++")


@S2_CHANGE
def test_p08b_the_chain_continues_from_the_neighbour():
    """Today: `+--`, nothing. S2: `+++`, the third click cuts from the neighbour (2,1) to (3,2) —
    the same mesh as that plain cut."""
    ref = run(*REFERENCES["P08b"])
    _committed(run(*ROWS["P08b"]), ref.faces, ref.vef, ref.residue, "+++")


@S2_CHANGE
def test_p09_two_points_on_the_same_edge_commit_nothing():
    """Today: 2nd refused, the 1st split is committed (V+1/E+1, History 1). S2: both accepted
    (skip), no change, no History."""
    _nothing(run(*ROWS["P09"]), "++")


@S2_CHANGE
def test_p09b_the_chain_continues_from_the_second_point_on_the_edge():
    """Today: `+-+`, the cut runs from the *first* point. S2: from the second — the same mesh as
    the plain cut from (1.7, 1) to (1.5, 2)."""
    ref = run(*REFERENCES["P09b"])
    _committed(run(*ROWS["P09b"]), ref.faces, ref.vef, ref.residue, "+++")


@S2_CHANGE
def test_p10_the_refused_session_leaves_no_lone_vertex():
    """Today: the first click's split is committed (V+1/E+1, History 1). S2: nothing committed."""
    _nothing(run(*ROWS["P10"]), "+-")


@S2_CHANGE
def test_p11_one_edge_click_then_enter_commits_nothing():
    """Today: the lone split is committed (V+1/E+1, History 1, empty residue). S2: nothing."""
    _nothing(run(*ROWS["P11"]), "+")


@S2_CHANGE
def test_p14_edge_click_then_click_outside_commits_nothing():
    """Engine level: the outside click is refused, the commit (Application: the outside click
    itself) commits nothing. Today: the lone split, History 1."""
    _nothing(run(*ROWS["P14"]), "+-")


@S2_CHANGE
def test_s4_undo_everything_then_commit_pushes_nothing():
    """Today: History 1 with unchanged content (an empty Undo step). S2: History 0."""
    r = run("grid", SESSION_BASE, ops=SESSIONS["S4"])
    assert r.steps == "u+ u+ u+ u+"
    _nothing(r, "++++")


@S2_CHANGE
def test_r3_chord_along_a_straight_run_of_boundary_edges_is_a_skip():
    """R3 (HD2): from (1,1) to (1.75,1), along the straight bottom line a first session left (vertex at
    (1.5,1)). Today: refused by F2, and the rolled-back split still pushes an empty History entry
    (the S4 defect). S2: along existing edges = a skip (Q5's rule, AQ1 = Q5 behaviour — open point
    S2-a in decision.md), nothing cut, no History."""
    _nothing(run("grid", R3_CLICKS, mesh=r3_mesh()), "++", faces=R3_SETUP_FACES)


def test_r3_stays_clean():
    r = run("grid", R3_CLICKS, mesh=r3_mesh())
    assert r.consistent and r.content_changed is False and r.broken == []
    assert r.faces == R3_SETUP_FACES


@S2_CHANGE
def test_g3_the_mesh_is_not_changed_during_a_session():
    """S2 (M1, model B): clicks change the path, not the mesh — the mesh changes at commit."""
    r = run(*ROWS["P04"])
    assert r.session_mutations == [False, False, False, False]
