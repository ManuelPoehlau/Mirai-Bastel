"""Einstiegspunkt für die Zylinder-Testszene im Topology Lab."""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parent / "mirai_bastel_core_V1"))

from viewport.topology_app import TopologyWindow  # noqa: E402
from viewport.topology_scene_cylinder import build_cylinder_scene  # noqa: E402


def main() -> None:
    """Startet den Topology-Viewport mit der offenen Zylinder-Testszene."""
    window = TopologyWindow(build_cylinder_scene())
    window.run()


if __name__ == "__main__":
    main()
