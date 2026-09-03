"""Einstiegspunkt für den All-Tools-Playground (experimentell).

Ausführen mit: python run_all_tools.py   (aus diesem Ordner)

Ein Fenster, alle aktuell vorhandenen Werkzeuge des viewport_V1-Experiments:
Selection (V/E/F), Topology-Tools (S/K/C/L/R) und die modalen Transform-Tools
(M Move, Shift+R Rotate, Shift+S Scale) inklusive Achsen-Vorwahl über X/Y/Z.

Reines Praxistest-Tool — keine Production-UX, kein WP-04-Baustein.
Siehe viewport/all_tools_app.py und README.md für Details.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent / "mirai_bastel_core_V1"))

from viewport.all_tools_app import main  # noqa: E402

if __name__ == "__main__":
    main()
