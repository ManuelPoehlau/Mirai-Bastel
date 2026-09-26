"""Test bootstrap: sys.path as at lab start (`viewport_shading_lab/_paths.py`).

Run from the repo root: `python -m pytest experiments/viewport_shading_lab/tests`.
pytest puts `experiments/` on sys.path (first directory without `__init__.py`
above the tests), so `viewport_shading_lab` is importable.
"""

from viewport_shading_lab._paths import ensure_paths

ensure_paths()
