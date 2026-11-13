"""Test bootstrap: `experiments/` on sys.path, as the scripts do at start.

Run from the repo root: `python -m pytest experiments/surface_slide/tests -q` (NumPy only; no display, no pyglet).
Not part of the bare `pytest` run (pytest.ini, AGENTS.md §8a): named explicitly.
"""

import sys
from pathlib import Path

_EXPERIMENTS_DIR = str(Path(__file__).resolve().parents[2])
if _EXPERIMENTS_DIR not in sys.path:
    sys.path.insert(0, _EXPERIMENTS_DIR)
