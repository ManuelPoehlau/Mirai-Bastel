"""Test bootstrap: sys.path as at lab start (`morph_lab/_paths.py`).

Run from the repo root: `python -m pytest experiments/morph_lab/tests` (the app-path tests are
headless with `TraceStore` and need no display; the import-boundary test loads pyglet and skips
cleanly without it). pytest puts `experiments/` on sys.path (first directory without `__init__.py`
above the tests), so `morph_lab` is importable.
"""

from morph_lab._paths import ensure_paths

ensure_paths()
