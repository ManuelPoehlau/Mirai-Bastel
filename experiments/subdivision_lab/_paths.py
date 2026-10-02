"""sys.path bootstrap for the Subdivision Mini-Lab.

Rebuilt (not imported) after `experiments/viewport_shading_lab/_paths.py`.
Puts, in this order, at the front of sys.path:

1. repo `src/`    — production packages `core`, `viewport`, `mirai`
2. repo root      — after `src/`, so a top-level `viewport` always resolves
                    to `src/viewport`
3. `examples/`    — shared OBJ loader + asset registry (`loaders`, AD-007)
4. `experiments/` — so the package `subdivision_lab` itself is importable

With `python experiments/subdivision_lab/run.py` only this folder is on
sys.path[0]; `run.py`/`bench.py` therefore add `experiments/` before
importing this module.
"""

from __future__ import annotations

import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = LAB_DIR.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
REPO_SRC_DIR = REPO_ROOT / "src"
EXAMPLES_DIR = REPO_ROOT / "examples"

_ORDERED_PATHS = (REPO_SRC_DIR, REPO_ROOT, EXAMPLES_DIR, EXPERIMENTS_DIR)


def ensure_paths() -> None:
    """Establishes the order from the module docstring at the front of sys.path."""
    wanted = [str(p) for p in _ORDERED_PATHS]
    sys.path[:] = wanted + [p for p in sys.path if p not in wanted]
