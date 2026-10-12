"""Test bootstrap: sys.path as at lab start (`mehlsack_lab/_paths.py`).

Run from the repo root: `python -m pytest experiments/mehlsack_lab/tests` (GL tests: under
Xvfb, `xvfb-run -a python -m pytest ...`; they skip cleanly when no GL is available).
pytest puts `experiments/` on sys.path (first directory without `__init__.py` above the
tests), so `mehlsack_lab` is importable. Not part of `pytest.ini` testpaths — run by path.
"""

from mehlsack_lab._paths import ensure_paths

ensure_paths()
