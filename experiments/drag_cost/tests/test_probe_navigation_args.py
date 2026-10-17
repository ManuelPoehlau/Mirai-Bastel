"""Argument handling, row budget, report format and import boundary of the navigation probe
(WP-VIEW-PERF-01) - headless: no pyglet, no window (the probe imports `src/main.py` and pyglet
lazily)."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import textwrap

import pytest

from drag_cost import probe_navigation_gl as probe
from drag_cost._paths import EXPERIMENTS_DIR, REPO_ROOT


def test_defaults():
    args = probe.parse_args([])
    assert args.assets == list(probe.DEFAULT_ASSETS)
    assert args.scenarios == list(probe.SCENARIO_NAMES)
    assert args.steps == probe.DEFAULT_STEPS and args.min_steps == probe.DEFAULT_MIN_STEPS
    assert args.row_seconds == probe.DEFAULT_ROW_SECONDS
    assert args.profile_top == probe.DEFAULT_PROFILE_TOP


def test_default_dense_asset_is_gollum_20k_and_gollum_stays_selectable():
    assert probe.DEFAULT_ASSETS[-1] == probe.GOLLUM_20K
    label, path = probe.resolve_asset(probe.GOLLUM_20K)
    assert label == "gollum_20k" and path == (REPO_ROOT / probe.GOLLUM_20K).resolve()
    assert probe.parse_args(["--assets", probe.GOLLUM]).assets == [probe.GOLLUM]
    assert "direct" in probe.parse_args(["--scenarios", "direct"]).scenarios


def test_registry_name_and_obj_path_both_resolve():
    label, path = probe.resolve_asset("head_basemesh")
    assert label == "head_basemesh" and path.name == "head_basemesh.obj"
    label, path = probe.resolve_asset(probe.GOLLUM)
    assert label == "gollum" and path == (REPO_ROOT / probe.GOLLUM).resolve()
    label, path = probe.resolve_asset(str(REPO_ROOT / probe.GOLLUM))
    assert label == "gollum"


@pytest.mark.parametrize("spec", ["no_such_asset", "examples/meshes/missing.obj", "README.md"])
def test_unknown_asset_raises(spec):
    with pytest.raises(ValueError):
        probe.resolve_asset(spec)


@pytest.mark.parametrize(
    "argv",
    [
        ["--steps", "0"],
        ["--steps", "x"],
        ["--min-steps", "0"],
        ["--steps", "5", "--min-steps", "10"],
        ["--warmup", "-1"],
        ["--drag-moves", "0"],
        ["--profile-top", "-1"],
        ["--row-seconds", "0"],
        ["--row-seconds", "nan"],
        ["--assets", "no_such_asset"],
        ["--assets", "README.md"],
        ["--scenarios", "no_such_scenario"],
    ],
)
def test_invalid_arguments_exit_with_status_2(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        probe.parse_args(argv)
    assert exc.value.code == 2
    assert capsys.readouterr().err


def test_zero_warmup_and_no_profile_are_allowed():
    args = probe.parse_args(["--warmup", "0", "--profile-top", "0"])
    assert args.warmup == 0 and args.profile_top == 0


def test_list_prints_scenarios_and_assets_without_a_window(capsys):
    assert probe.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "orbit" in out and "first_hover" in out and "head_basemesh" in out
    assert probe.GOLLUM in out


def test_budget_caps_steps_and_keeps_min_steps_past_the_time_budget():
    budget = probe._Budget(steps=10, min_steps=3, seconds=0.0)
    assert budget.more(0) and budget.more(2)
    assert not budget.more(3)  # the time budget (0 s) is spent
    roomy = probe._Budget(steps=4, min_steps=1, seconds=1e9)
    assert roomy.more(3) and not roomy.more(4)


def _sample(**kw):
    values = dict(event=10.0, pick=9.0, cache=4.0, cache_rebuilds=1, occl=5.0, occl_tests=6,
                  sync=0.5, draw=2.0, gpu=float("nan"), upload_bytes=2048)
    values.update(kw)
    return probe.NavSample(**values)


def test_nav_report_lines():
    result = probe.NavResult("zoom", "head_basemesh", (_sample(), _sample(event=30.0)), note="x")
    assert result.samples[0].frame == pytest.approx(12.5)
    lines = probe.nav_lines(result)
    text = "\n".join(lines)
    assert lines[0].lstrip().startswith("zoom") and "n=  2" in lines[0]
    assert "(1/2 over 16.7 ms)" in lines[0]
    assert "1.0 rebuilds/event" in text and "6.0 tests/event" in text
    assert "gpu    n/a" in text and "2.0 KB/frame" in text
    assert lines[-1].strip() == "x"
    assert all(line.isascii() for line in lines)


def test_direct_report_line():
    r = probe.DirectResult("box 60 px vertex", "gollum_20k", (4.0, 2.0), (3, 1), note="12 vertices selected")
    (line,) = probe.direct_lines(r)
    assert "box 60 px vertex" in line and "n=  2" in line and "2.0 occl tests/call" in line
    assert line.isascii()


def test_loop_report_line():
    r = probe.LoopResult("gollum", "zoom", 2.0, 4, 30, 30, 500.0, 3.0, 1200.0)
    (line,) = probe.loop_lines(r)
    assert "4 events" in line and "30 on_draw" in line and "without a frame   1200.0 ms" in line
    assert not math.isnan(r.event_ms_mean)


def test_no_pyglet_playground_or_foreign_experiment_imports():
    script = textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {str(EXPERIMENTS_DIR)!r})
        from drag_cost._paths import ensure_paths
        ensure_paths()
        import drag_cost.probe_navigation_gl as probe
        probe.parse_args([])
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
