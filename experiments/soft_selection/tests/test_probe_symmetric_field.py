"""probe_symmetric_field.py (AD-SYM-04 SS0): smoke on subd_cube with a few radii, plus the
two facts the report rests on (exact comparison, the R-6 counterexample)."""

from __future__ import annotations

import pytest

from soft_selection import probe_symmetric_field as probe


def test_probe_smoke_subd_cube(capsys):
    code = probe.main(["--assets", "subd_cube", "--radii", "5", "50", "200", "--skip-cost"])
    out = capsys.readouterr().out
    assert code == 0 and "STOP" not in out
    assert out.isascii()
    assert "subd_cube axis X (valid" in out and "D-1: HOLDS" in out
    # Y has no pair on this asset: symmetric Soft would refuse, nothing to judge.
    assert "subd_cube axis Y (partial, pairs 0)" in out and "n.a." in out
    assert "cases where the influence reaches the seam:" in out


def test_probe_leaves_the_mesh_without_definition_and_unmoved():
    mesh = probe.load_mesh("subd_cube")
    before = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    result = probe.probe_asset_axis("subd_cube", mesh, "X", 1.0, (5, 100))
    assert mesh.symmetry_definition is None
    assert before == {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    assert result.geometry.straddling == 0 and result.geometry.precondition


def test_cost_probe_runs_on_subd_cube():
    _, seeds, vertices, rows = probe.probe_cost("subd_cube", "X", repeat=1)
    assert vertices == 26 and seeds >= 1
    assert len(rows) == len(probe.COST_FRACTIONS) * len(probe.METRIC_NAMES)
    assert all(r.influenced_sym >= r.influenced_today for r in rows)


def test_comparison_is_exact_and_reports_ulp():
    diff = probe.Diff()
    diff.add("same", 0.5, 0.5)
    diff.add("one ulp", 1.0, 1.0 + 2.0**-52)
    assert (diff.checked, diff.bad, diff.max_ulp) == (2, 1, 1)
    assert probe.ulp_distance(1.0, 1.0) == 0


def test_straddling_quad_is_valid_and_breaks_only_the_own_side_claim():
    """R-6: a valid mesh with edges across the plane and no end point on it. The pair stays
    equal (the graph is symmetric); 'union field == own side's field' fails for geodesic only."""
    mesh = probe.straddling_quad()
    probe.set_symmetry_axis(mesh, "X")
    corr = probe.vertex_correspondence(mesh)
    geometry = probe.analyse_geometry("straddling_quad", mesh, "X", corr)
    assert geometry.state is probe.SymmetryState.VALID
    assert geometry.straddling == 4 and not geometry.precondition
    seeds = {mesh.all_vertex_ids()[0]}
    euclid = probe.evaluate_case(mesh, "X", corr, seeds, 2.0, "euclidean")
    geo = probe.evaluate_case(mesh, "X", corr, seeds, 2.0, "geodesic")
    assert euclid.own_w.bad == 0 and euclid.cross_wins == 0
    assert geo.pair_w.bad == 0 and geo.pair_d.bad == 0
    assert geo.own_w.bad > 0 and geo.cross_wins > 0


def test_unknown_asset_is_rejected():
    with pytest.raises(SystemExit) as exc:
        probe.main(["--assets", "no_such_asset"])
    assert exc.value.code == 2
