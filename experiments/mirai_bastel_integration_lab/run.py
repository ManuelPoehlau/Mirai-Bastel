"""Integration Lab — interaktiver Start.

    python experiments/mirai_bastel_integration_lab/run.py

Startet die erste Zielszene (Cube + Head Basemesh) im Integrations-Viewport.
Dokumentation siehe README.md im Lab-Ordner.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
for _p in (str(_THIS_DIR), str(_THIS_DIR.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from integration.lab_viewport import main  # noqa: E402

if __name__ == "__main__":
    main()