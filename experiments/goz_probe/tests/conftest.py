"""Test bootstrap: sys.path as at script start (`goz_probe/_paths.py`).

Run from the repo root: `python -m pytest experiments/goz_probe/tests -q` (not part of the default run, AGENTS.md §8a).
Headless and OS-independent: every test works on a fake GoZ root in a temporary folder and never starts a program.
"""

from goz_probe._paths import ensure_paths

ensure_paths()
