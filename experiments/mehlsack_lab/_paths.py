"""sys.path bootstrap for the Mehlsack Lab (rebuilt after `subdivision_lab/_paths.py`).

Puts, in this order, at the front of sys.path:

1. repo `src/`    — production packages `core`, `viewport`, `mirai`
2. repo root      — after `src/`, so a top-level `viewport` always resolves to
                    `src/viewport`; also what makes `playground.topology_tools.loop_ring`
                    importable (the one allowed `playground` module, handoff E3)
3. `experiments/` — so the package `mehlsack_lab` itself is importable

With `python experiments/mehlsack_lab/run.py` only this folder is on sys.path[0];
`run.py` therefore adds `experiments/` before importing this module.
"""

from __future__ import annotations

import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = LAB_DIR.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
REPO_SRC_DIR = REPO_ROOT / "src"

_ORDERED_PATHS = (REPO_SRC_DIR, REPO_ROOT, EXPERIMENTS_DIR)


def ensure_paths() -> None:
    """Establishes the order from the module docstring at the front of sys.path."""
    wanted = [str(p) for p in _ORDERED_PATHS]
    sys.path[:] = wanted + [p for p in sys.path if p not in wanted]
