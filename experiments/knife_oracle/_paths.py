"""sys.path-Bootstrap für das Knife-Oracle (Muster: `symmetry_lab/_paths.py`).

Reihenfolge: Repo-`src/` (core, mirai, viewport), Repo-Root (`tests.knife_kept_replay`, `tests.mesh_invariants`),
`examples/` (OBJ-Loader für den Head, AD-007), `experiments/` (damit `knife_oracle` importierbar ist).
"""

from __future__ import annotations

import sys
from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = ORACLE_DIR.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
REPO_SRC_DIR = REPO_ROOT / "src"
EXAMPLES_DIR = REPO_ROOT / "examples"

#: The head asset some golden sessions run on (AD-007: `examples/` is shared).
DEFAULT_HEAD_ASSET = EXAMPLES_DIR / "meshes" / "head_basemesh.obj"

_ORDERED_PATHS = (REPO_SRC_DIR, REPO_ROOT, EXAMPLES_DIR, EXPERIMENTS_DIR)


def ensure_paths() -> None:
    """Puts the paths above at the front of sys.path, in that order."""
    wanted = [str(p) for p in _ORDERED_PATHS]
    sys.path[:] = wanted + [p for p in sys.path if p not in wanted]
