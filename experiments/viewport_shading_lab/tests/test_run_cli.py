"""E16: an unknown mesh name exits with code 2 and lists the valid names —
before any window opens (pyglet is only imported after the name check)."""

from __future__ import annotations

import subprocess
import sys

from viewport_shading_lab._paths import LAB_DIR, REPO_ROOT


def test_unknown_asset_exits_2_with_valid_names():
    result = subprocess.run(
        [sys.executable, str(LAB_DIR / "run.py"), "no_such_mesh"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 2
    assert "head_basemesh" in result.stderr and "subd_cube" in result.stderr


def test_name_check_needs_no_pyglet():
    from viewport_shading_lab import run

    assert "pyglet" not in run.__dict__
    assert run.main(["no_such_mesh"]) == 2
