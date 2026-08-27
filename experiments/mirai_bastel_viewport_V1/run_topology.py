"""Einstiegspunkt für den Topology-Lab-Viewport."""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent / "mirai_bastel_core_V1"))

from viewport.topology_app import main  # noqa: E402

if __name__ == "__main__":
    main()
