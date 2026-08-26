"""Einstiegspunkt für den V1-Viewport-Praxistest.

Ausführen mit: python run.py   (aus diesem Ordner, nach `pip install -r requirements.txt`)

Siehe README.md für Scope, Steuerung und bekannte Risiken.
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent / "mirai_bastel_core_V1"))

from viewport.app import main  # noqa: E402

if __name__ == "__main__":
    main()
