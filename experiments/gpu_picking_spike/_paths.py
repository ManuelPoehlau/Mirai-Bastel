"""sys.path bootstrap for the GPU picking spike (pattern of `experiments/drag_cost/_paths.py`,
copied, not imported). Puts at the front of sys.path, in this order: repo `src/` (`core`,
`mirai`, `viewport`), the repo root, `examples/` (OBJ loader, asset registry) and
`experiments/` (this package)."""

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
