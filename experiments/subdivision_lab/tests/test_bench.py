"""Bench smoke: the report has every measurement ID, the host label and the mode
(handoff §6), and the simulated drag shows 0 structural rebuilds."""

from __future__ import annotations

import pytest

from ._pyglet_headless import import_pyglet

import_pyglet()

from subdivision_lab import bench  # noqa: E402


@pytest.fixture(scope="module")
def report():
    try:
        window = bench.open_bench_window(visible=False, width=320, height=240)
    except Exception as exc:
        pytest.skip(f"no GL context available: {exc}")
    try:
        result = bench.run_bench(
            "pytest-host", runs=3, plan=(("subd_cube", (1, 2)), ("man_with_shoes_basemesh", (3,))),
            width=320, height=240, log=lambda _text: None,
        )
    finally:
        window.close()
    return result


def test_report_names_host_mode_and_gl(report):
    text = report.format()
    assert "pytest-host" in text
    assert bench.MODE_HIDDEN in text
    assert report.gl_version and report.gl_renderer
    assert "GL_VERSION" in text and "GL_RENDERER" in text
    assert "ersetzen keine Messung auf dem Referenz-PC" in text


def test_report_has_all_measurement_ids(report):
    ids = {row[0] for sec in report.sections for row in sec["rows"]}
    assert {"M1", "M2", "M3", "M4", "M5", "M5w", "M6", "M6w", "M7", "M8", "M8i", "M8c", "D1", "D2"} <= ids
    for sec in report.sections:
        for _rid, _label, samples, _expected in sec["rows"]:
            assert samples and all(s >= 0.0 for s in samples)


def test_drag_simulation_shows_no_structural_rebuild(report):
    notes = [n for sec in report.sections for n in sec["notes"] if "benchmark_counters-Delta" in n]
    assert notes
    for note in notes:
        assert "'structural_rebuilds': 0" in note and "'topology_updates': 0" in note
        assert "unverändert" in note and "glGetError = 0" in note


def test_refused_level_is_reported_not_measured(report):
    man = [s for s in report.sections if s["asset"] == "man_with_shoes_basemesh"]
    assert man and man[0]["rows"] == []
    assert any("abgelehnt" in n for n in man[0]["notes"])


def test_stats_helper():
    assert bench.stats_ms([3.0, 1.0, 2.0]) == (1.0, 2.0, 3.0)


def test_time_budget_cuts_rows_and_says_so():
    window = bench.open_bench_window(visible=False, width=320, height=240)
    try:
        result = bench.run_bench(
            "pytest-budget", runs=6, plan=(("subd_cube", (1,)),), width=320, height=240,
            budget_s=1e-9, log=lambda _text: None,
        )
    finally:
        window.close()
    rows = [row for sec in result.sections for row in sec["rows"]]
    assert rows and all(len(samples) == bench.MIN_BUDGET_RUNS for _r, _l, samples, _e in rows)
    text = result.format()
    assert "von 6 (Budget)" in text and "von 100 (Budget)" in text
    assert "Zeitbudget" in text


def test_timed_respects_budget_but_not_below_minimum():
    assert len(bench.timed(lambda: None, 10)) == 10
    assert len(bench.timed(lambda: None, 10, budget_s=1e-12)) == bench.MIN_BUDGET_RUNS
