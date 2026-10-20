"""sys.path bootstrap: `src/`, repo root, `examples/`, `experiments/` (same order as `drag_cost/_paths.py`)."""

from __future__ import annotations

import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = EXPERIMENT_DIR.parent
REPO_ROOT = EXPERIMENTS_DIR.parent

_ORDERED_PATHS = (REPO_ROOT / "src", REPO_ROOT, REPO_ROOT / "examples", EXPERIMENTS_DIR)


def ensure_paths() -> None:
    wanted = [str(p) for p in _ORDERED_PATHS]
    sys.path[:] = wanted + [p for p in sys.path if p not in wanted]
