"""probe_cost.py prints the table for the requested assets (handoff §9)."""

from __future__ import annotations

import pytest

from soft_selection import probe_cost


def test_probe_prints_one_row_per_radius_and_metric(capsys):
    assert probe_cost.main(["--assets", "head_basemesh", "--steps", "2", "--repeat", "1"]) == 0
    out = capsys.readouterr().out
    assert "CPU:" in out and "Asset head_basemesh: 326 vertices" in out
    rows = [line for line in out.splitlines() if line.strip().endswith(tuple("0123456789"))
            and ("euclidean" in line or "geodesic" in line)]
    assert len(rows) == len(probe_cost.RADIUS_FRACTIONS) * len(probe_cost.METRICS)
    assert out.isascii()


def test_probe_leaves_the_asset_unchanged():
    result = probe_cost.probe_asset("head_basemesh", steps=2, repeat=1)
    assert [r.influenced for r in result.rows] == [
        r.influenced for r in probe_cost.probe_asset("head_basemesh", steps=2, repeat=1).rows
    ]
    assert all(r.influenced >= result.seeds for r in result.rows)


def test_probe_rejects_unknown_asset():
    with pytest.raises(SystemExit) as exc:
        probe_cost.main(["--assets", "no_such_asset"])
    assert exc.value.code == 2
