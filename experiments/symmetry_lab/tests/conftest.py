"""Test-Bootstrap: sys.path wie beim Lab-Start (`symmetry_lab/_paths.py`).

Aufruf vom Repo-Root: `python -m pytest experiments/symmetry_lab/tests`.
pytest legt dabei `experiments/` auf sys.path (erstes Verzeichnis ohne
`__init__.py` oberhalb der Tests), sodass `symmetry_lab` importierbar ist.
"""

from symmetry_lab._paths import ensure_paths

ensure_paths()
