"""Soft Selection experiment (WP-SOFT-01 S1) - headless influence + weighted transforms.

Entry point and purpose: `README.md` in this folder; evidence: `FINDINGS.md`.
Intentionally imports nothing from `playground/` (AD-010 precedent, guarded by
`tests/test_import_boundary.py`).

This package `__init__` stays empty on purpose (no imports, no sys.path changes):
the bootstrap lives in `_paths.py` and is called explicitly by the entry points.
"""
