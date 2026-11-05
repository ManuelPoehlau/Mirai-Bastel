"""sys.path bootstrap for the GoZ probe (pattern of `experiments/drag_cost/_paths.py`, not imported from it).

The scripts are run as `python -I experiments/goz_probe/<script>.py`. In isolated mode (`-I`) Python puts neither the
script's folder nor PYTHONPATH on sys.path, so every script adds `experiments/` itself before importing this module.
Order at the front of sys.path: repo `src/` (read-only use of `core`, `mirai.scene_factory`, `mirai.obj_export`),
`examples/` (the shared OBJ loader), `experiments/` (this package).
"""

from __future__ import annotations

import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = EXPERIMENT_DIR.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
REPO_SRC_DIR = REPO_ROOT / "src"
EXAMPLES_DIR = REPO_ROOT / "examples"

_ORDERED_PATHS = (REPO_SRC_DIR, EXAMPLES_DIR, EXPERIMENTS_DIR)


def ensure_paths() -> None:
    wanted = [str(p) for p in _ORDERED_PATHS]
    sys.path[:] = wanted + [p for p in sys.path if p not in wanted]
