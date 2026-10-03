"""Smoke-Test der Drag-Kosten-Probe (WP-SYM-LAB-03 Slice 2, Plan A3).

Läuft auf `subd_cube` mit wenigen Bewegungen und prüft nur, dass Zahlen
herauskommen und der Bericht vollständig ist — die Messung selbst gehört auf den
Referenz-PC (`docs/architecture/REFERENCE_HARDWARE.md` §4), nicht in die Tests.
"""

from __future__ import annotations

import math
import subprocess
import sys

from symmetry_lab import probe_drag_cost as probe
from symmetry_lab._paths import LAB_DIR

from ._app_lab_support import forbid_lab_calls  # noqa: F401


def test_probe_runs_on_subd_cube_and_returns_numbers():
    result = probe.run_probe("subd_cube", moves=6, selection_size=2)
    assert result.asset == "subd_cube"
    assert result.vertex_count == 26
    assert result.selected == 2
    assert result.moved == 4  # zwei gepaarte Vertices + ihre Partner
    assert result.moves == 6
    for stats in (
        result.total,
        result.transform,
        result.lab_overlays,
        result.viewport_rest,
        result.commit_sync,
        result.hover,
    ):
        assert all(math.isfinite(v) and v >= 0.0 for v in (stats.p50, stats.p95, stats.max))
        assert stats.p50 <= stats.p95 <= stats.max
    assert result.total.p95 <= result.total.max


def test_report_names_machine_threshold_and_every_metric():
    result = probe.run_probe("subd_cube", moves=4, selection_size=1)
    text = "\n".join(probe.report_lines([result], 4))
    for needle in ("Plattform:", "CPU:", "Python:", "p95 <= 8 ms", "subd_cube: 26 V",
                   "Bewegung gesamt", "Transform-Schritt", "Lab-Overlays", "Commit-Frame",
                   "Hover-Wechsel"):
        assert needle in text, needle


def test_stats_nearest_rank_p95():
    stats = probe.Stats.of([float(v) for v in range(1, 21)])
    assert (stats.p50, stats.p95, stats.max) == (10.5, 19.0, 20.0)


def test_probe_command_line_runs():
    """Der eine Befehl für den Referenz-PC, hier verkürzt."""
    completed = subprocess.run(
        [sys.executable, str(LAB_DIR / "probe_drag_cost.py"), "--assets", "subd_cube",
         "--moves", "3"],
        capture_output=True, text=True, timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    assert "subd_cube: 26 V" in completed.stdout
