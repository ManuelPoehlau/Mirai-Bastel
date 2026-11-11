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

import os
import subprocess
import sys
import tempfile
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


def _git(*args: str, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
                          env=env).stdout.strip()


def source_state() -> str:
    """Commit and working-tree state of the checkout the probe imports (`git` absent = 'unknown'). A modified tree also
    names the git tree id of its `src/` as it is on disk (a scratch index, the real one untouched): after the change is
    committed, `git rev-parse <commit>:src` gives the same id when the measured code is the committed code."""
    try:
        head = _git("rev-parse", "--short=10", "HEAD")
        dirty = _git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.CalledProcessError):
        return "commit unknown (no git)"
    if not dirty:
        return f"commit {head}, working tree clean"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
            _git("read-tree", "HEAD", env=env)
            _git("add", "-A", "--", "src", env=env)
            tree = _git("write-tree", "--prefix=src/", env=env)
    except (OSError, subprocess.CalledProcessError):
        tree = "unknown"
    return f"commit {head}, working tree MODIFIED, src/ tree {tree[:10]}"
