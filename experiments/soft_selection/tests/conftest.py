"""Test bootstrap: sys.path as at script start (`soft_selection/_paths.py`).

Run from the repo root: `python -m pytest experiments/soft_selection/tests`.
pytest puts `experiments/` on sys.path (first directory above the tests without an
`__init__.py`), so `soft_selection` is importable. The repo's `tests/` directory is
appended (not prepended) for `mesh_invariants` only - same route as the
`experiments/topology` probes.
"""

import sys

from soft_selection._paths import REPO_ROOT, ensure_paths

ensure_paths()
_REPO_TESTS = str(REPO_ROOT / "tests")
if _REPO_TESTS not in sys.path:
    sys.path.append(_REPO_TESTS)
