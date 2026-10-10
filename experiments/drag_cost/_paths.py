"""sys.path bootstrap for the drag-cost probe.

Pattern copied (not imported) from `experiments/soft_selection/_paths.py`. Puts these at
the front of sys.path, in this order:

1. repo `src/`      - Production packages `core`, `mirai`, `viewport`, and `src/main.py` (`GL_TYPES`)
2. repo root        - after `src/`, so a top-level `viewport` always resolves to `src/viewport`
3. `examples/`      - shared OBJ loader + asset registry (`loaders`, AD-007)
4. `experiments/`   - so the package `drag_cost` itself is importable

Stage 0 (script start): with `python experiments/drag_cost/probe_drag_gl.py` only
`experiments/drag_cost/` is on sys.path[0]; the probe therefore adds `experiments/`
before importing this module.
"""

from __future__ import annotations

import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = EXPERIMENT_DIR.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
REPO_SRC_DIR = REPO_ROOT / "src"
EXAMPLES_DIR = REPO_ROOT / "examples"

_ORDERED_PATHS = (REPO_SRC_DIR, REPO_ROOT, EXAMPLES_DIR, EXPERIMENTS_DIR)


def ensure_paths() -> None:
    """Establishes the order from the module docstring at the front of sys.path."""
    wanted = [str(p) for p in _ORDERED_PATHS]
    sys.path[:] = wanted + [p for p in sys.path if p not in wanted]
