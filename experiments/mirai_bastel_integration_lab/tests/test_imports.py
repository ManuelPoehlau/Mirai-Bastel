"""Import-Smoke-Tests für die interaktive Lab-Viewport-Schicht.

Es wird KEIN Fenster geöffnet — es wird nur geprüft, dass die
pyglet-basierte Integrationsschicht fehlerfrei importierbar ist.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
for _p in (str(_LAB), str(_LAB.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import integration.lab_viewport as lab_viewport  # noqa: E402


def test_viewport_module_imports_and_exposes_window():
    assert hasattr(lab_viewport, "IntegrationLabWindow")


def test_scene_package_re_exports():
    import scene  # noqa: E402

    assert hasattr(scene, "LabScene")
    assert callable(scene.build_lab_scene)