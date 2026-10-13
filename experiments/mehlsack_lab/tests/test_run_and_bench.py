"""`run.py --help` needs no window; the bench runs end to end on a small box (GL, skips without)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from mehlsack_lab._paths import LAB_DIR, REPO_ROOT

from ._pyglet_headless import import_pyglet


def test_run_help_needs_no_window():
    result = subprocess.run([sys.executable, str(LAB_DIR / "run.py"), "--help"],
                            capture_output=True, text=True, cwd=REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "Mehlsack" in result.stdout


def test_bench_runs_on_a_small_box():
    import_pyglet()
    from mehlsack_lab import bench

    try:
        report = bench.run_bench("test", runs=1, width=480, height=360,
                                 box=dict(height=2.0, width=1.5, depth=1.5, h=4, n=3))
    except Exception as exc:  # no GL / no display in this environment
        if "display" in str(exc).lower() or "EGL" in str(exc):
            pytest.skip(f"no GL context available: {exc}")
        raise
    assert "| 15 % |" in report and "| 200 % |" in report and "host: test" in report
