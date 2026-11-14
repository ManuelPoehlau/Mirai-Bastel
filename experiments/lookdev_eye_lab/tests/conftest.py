"""Test bootstrap: repo `src/` and `experiments/` on sys.path, as the lab's scripts do at start.

Run from the repo root: `python -m pytest experiments/lookdev_eye_lab/tests -q`. The headless tests need NumPy only;
`test_gl_*.py` need pyglet and a display (`xvfb-run -a` in a container) and are skipped without them by the
repo-root conftest.
"""

import sys
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parents[2]
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from lookdev_eye_lab._paths import ensure_paths  # noqa: E402

ensure_paths()
