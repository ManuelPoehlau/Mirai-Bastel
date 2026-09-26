"""Viewport Shading Lab (WP-SHADE-LAB-01) — standalone research window.

Entry point and controls: `README.md` in this folder. The lab deliberately
imports nothing from `playground/` or any other `experiments/` folder
(handoff E1, guarded by `tests/test_import_boundary.py`).

This package `__init__` stays empty on purpose (no imports, no sys.path
changes): the bootstrap lives in `_paths.py` and is called explicitly by the
entry points.
"""
