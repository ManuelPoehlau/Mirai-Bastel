"""Test-Bootstrap: sys.path wie im Lab-Muster (`knife_oracle/_paths.py`).

Aufruf vom Repo-Root: `xvfb-run -a python -m pytest experiments/knife_oracle/tests`. pytest legt `experiments/`
auf sys.path (erstes Verzeichnis ohne `__init__.py` oberhalb der Tests), sodass `knife_oracle` importierbar ist.
"""

from knife_oracle._paths import ensure_paths

ensure_paths()
