"""Argument handling and import boundary of the drag-cost probe - headless: no
pyglet, no window (the probe imports `src/main.py` and pyglet lazily)."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from drag_cost import probe_drag_gl as probe
from drag_cost._paths import EXPERIMENTS_DIR


def test_defaults():
    args = probe.parse_args([])
    assert args.assets == list(probe.DEFAULT_ASSETS)
    assert args.sizes is None and args.moves == probe.DEFAULT_MOVES
    assert args.scenarios == ["plain_w"]


def test_default_sizes_are_the_findings_counts():
    assert probe.sizes_for("head_basemesh", None) == (9, 36, 68)
    assert probe.sizes_for("man_with_shoes_basemesh", None) == (18, 76, 112)
    assert probe.sizes_for("head_basemesh", [5, 7]) == (5, 7)
    assert probe.sizes_for("subd_cube", None) == probe.FALLBACK_SIZES


@pytest.mark.parametrize(
    "argv",
    [
        ["--moves", "0"],
        ["--moves", "x"],
        ["--sizes", "0"],
        ["--sizes", "9", "-3"],
        ["--warmup", "-1"],
        ["--assets", "no_such_asset"],
        ["--scenarios", "no_such_scenario"],
    ],
)
def test_invalid_arguments_exit_with_status_2(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        probe.parse_args(argv)
    assert exc.value.code == 2
    assert capsys.readouterr().err


def test_zero_warmup_is_allowed():
    assert probe.parse_args(["--warmup", "0"]).warmup == 0


def test_list_prints_scenarios_and_assets_without_a_window(capsys):
    assert probe.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "plain_w" in out and "head_basemesh" in out


def test_stats_nearest_rank():
    stats = probe.Stats.of([float(i) for i in range(1, 101)])
    assert stats.p50 == 50.5 and stats.p95 == 95.0 and stats.max == 100.0


def test_no_pyglet_playground_or_foreign_experiment_imports():
    script = textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {str(EXPERIMENTS_DIR)!r})
        from drag_cost._paths import ensure_paths
        ensure_paths()
        import drag_cost.probe_drag_gl
        print(json.dumps(sorted(sys.modules)))
        """
    )
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    loaded = set(json.loads(out.stdout))
    assert not {m for m in loaded if m == "pyglet" or m.startswith("pyglet.")}
    assert "main" not in loaded
    assert not {m for m in loaded if m == "playground" or m.startswith("playground.")}
    foreign = {
        m for m in loaded
        if m.split(".")[0] in {"symmetry_lab", "soft_selection", "topology", "subdivision_lab"}
    }
    assert not foreign
