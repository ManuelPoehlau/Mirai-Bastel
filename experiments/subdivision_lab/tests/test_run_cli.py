"""A12: an unknown mesh name exits with code 2 and lists the valid names —
before any window opens (pyglet is only imported after the name check). Both entries: the app path
(`run.py`, WP-SUBD-LAB-02) and the standalone window (`run_standalone.py`)."""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

from subdivision_lab._paths import LAB_DIR, REPO_ROOT


@pytest.mark.parametrize("entry", ["run.py", "run_standalone.py"])
def test_unknown_asset_exits_2_with_valid_names(entry):
    result = subprocess.run(
        [sys.executable, str(LAB_DIR / entry), "no_such_mesh"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2
    assert "head_basemesh" in result.stderr and "subd_cube" in result.stderr
    assert "man_with_shoes_basemesh" in result.stderr


@pytest.mark.parametrize("entry", ["run", "run_standalone"])
def test_name_check_needs_no_pyglet(entry):
    module = importlib.import_module(f"subdivision_lab.{entry}")

    assert "pyglet" not in module.__dict__
    assert module.main(["no_such_mesh"]) == 2


def test_bench_cli_rejects_unknown_asset_before_opening_a_window():
    from subdivision_lab import bench

    assert bench.main(["--assets", "no_such_mesh"]) == 2
