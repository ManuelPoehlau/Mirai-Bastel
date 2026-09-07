"""HUD-Vertrag des Lab-Viewports (headless, ohne Fenster).

Der Kommentar in `integration/lab_viewport.py` verweist auf diese Datei —
sie existierte bisher nicht (dangling reference, repariert 2026-07-09).

Hintergrund: Nach dem Befund „Aenderungen kamen am Endgeraet scheinbar
nicht an" traegt der Viewport jetzt einen Versionstag (Fenstertitel, HUD,
Konsolen-Banner). Diese Tests sichern den HUD-Vertrag ohne GPU:

- Versionstag gesetzt (identifiziert den laufenden Code-Stand),
- HUD-Texte nicht leer (Status-Titel, Hinweistext).
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB = Path(__file__).resolve().parents[1]
for _p in (str(_LAB), str(_LAB.parent.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import integration.lab_viewport as lv  # noqa: E402


def test_version_tag_is_set():
    assert isinstance(lv.LAB_VERSION, str)
    assert lv.LAB_VERSION.strip()
    assert lv.LAB_VERSION.startswith("v")


def test_hud_texts_are_present():
    assert lv._STATUS_TITLE.strip()
    assert "INTEGRATION LAB" in lv._STATUS_TITLE
    assert lv._HINT_TEXT.strip()
    # Die im Task geforderten Interaktionen sind dokumentiert:
    for token in ("Orbit", "Pan", "Zoom", "Vertex", "Move"):
        assert token in lv._HINT_TEXT, token
