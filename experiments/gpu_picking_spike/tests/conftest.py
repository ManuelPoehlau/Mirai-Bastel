"""Test bootstrap: sys.path as at script start (`gpu_picking_spike/_paths.py`). Run from the repo
root: `xvfb-run -a python -m pytest experiments/gpu_picking_spike/tests` (the GL tests need a
display; without one the repo-root `conftest.py` turns them into visible skips)."""

import sys
from pathlib import Path

_EXPERIMENTS = str(Path(__file__).resolve().parents[2])
if _EXPERIMENTS not in sys.path:
    sys.path.insert(0, _EXPERIMENTS)

from gpu_picking_spike._paths import ensure_paths  # noqa: E402

ensure_paths()
