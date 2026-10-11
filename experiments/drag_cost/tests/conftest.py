"""Test bootstrap: sys.path as at script start (`drag_cost/_paths.py`).

Run from the repo root: `python -m pytest experiments/drag_cost/tests`. These tests are
headless: they never import pyglet or `src/main.py` (the probe imports both lazily).
"""

from drag_cost._paths import ensure_paths

ensure_paths()
