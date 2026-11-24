"""Test bootstrap: repo `src/`, `experiments/`, `experiments/lookdev_diffuse_area` and this experiment on sys.path, as
its scripts do at start. Run from the repo root: `python -m pytest experiments/lookdev_pcss/tests -q` (headless; not
part of the default run, AGENTS.md §8a)."""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
for _p in (_HERE.parents[1] / "src", _HERE.parents[0], _HERE.parents[0] / "lookdev_diffuse_area", _HERE):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
