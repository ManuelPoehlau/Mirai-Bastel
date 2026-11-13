"""Test bootstrap: `experiments/` on sys.path, as the probes do at script start.

Run from the repo root: `python -m pytest experiments/lookdev_gpu_probe/tests -q` (headless tests need NumPy only;
`test_gl_probe.py` needs pyglet and a display - `xvfb-run -a` in a container - and is skipped without them by the
repo-root conftest).
"""

import sys
from pathlib import Path

_EXPERIMENTS_DIR = str(Path(__file__).resolve().parents[2])
if _EXPERIMENTS_DIR not in sys.path:
    sys.path.insert(0, _EXPERIMENTS_DIR)
