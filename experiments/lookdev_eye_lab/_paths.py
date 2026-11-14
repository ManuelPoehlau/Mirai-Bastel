"""sys.path bootstrap for the Eye Proof lab (pattern of `experiments/drag_cost/_paths.py`): repo `src/` first (the
production packages `core`, `viewport`, `mirai`), then `experiments/` (this package and `lookdev_gpu_probe`).

A script started as `python experiments/lookdev_eye_lab/run.py` has only its own folder on sys.path; it adds
`experiments/` before importing this module."""

from __future__ import annotations

import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = LAB_DIR.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
OUT_DIR = LAB_DIR / "out"
CACHE_DIR = OUT_DIR / "cache"


def ensure_paths() -> None:
    wanted = [str(REPO_ROOT / "src"), str(EXPERIMENTS_DIR)]
    sys.path[:] = wanted + [p for p in sys.path if p not in wanted]
