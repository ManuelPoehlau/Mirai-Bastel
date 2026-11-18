"""Argument handling and the statistics line of the paint probe (AD-037 Phase 1e) - headless, no window."""

from __future__ import annotations

import pytest

from drag_cost import probe_paint as probe


def test_defaults_and_limits():
    args = probe.parse_args([])
    assert (args.size, args.dabs, args.no_gl) == (2048, probe.DEFAULT_DABS, False)
    assert probe.parse_args(["--size", "1024", "--no-gl"]).size == 1024
    for argv in (["--size", "16"], ["--dabs", "1"], ["--size", "x"]):
        with pytest.raises(SystemExit):
            probe.parse_args(argv)


def test_stats_are_p50_p95_max():
    line = probe.stats([float(v) for v in range(1, 101)])
    assert line.split() == ["50.50", "95.00", "100.00"]
