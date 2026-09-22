"""Artist Playground — Einstiegspunkt.

Verwendung:
    python playground/run.py          # Cube (default)
    python playground/run.py cube     # explizit Cube
    python playground/run.py head     # Head-Basemesh
    python playground/run.py grid     # flaches 8x8-Quad-Raster (Connect Lab)

Oder als Modul vom Repo-Root:
    python -m playground.run
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# !!! NICHT ENTFERNEN — sys.path-Bootstrap Stufe 0 (Skriptstart) !!!
# ---------------------------------------------------------------------------
# Bei `python playground/run.py` legt CPython das Verzeichnis des Skripts
# (also `playground/`) auf sys.path[0] und NICHT das Repo-Root. Ohne die drei
# Zeilen unten scheitert die nächste Zeile mit
#     ModuleNotFoundError: No module named 'playground'
# weil `playground/_paths.py` sich in diesem Moment nicht selbst importieren
# kann (beobachtet am 2026-09-22, danach durch ein Zurückschreiben einer alten
# Dateifassung erneut).
# Absicherung: playground/tests/test_entry_point_bootstrap.py
#     python -m pytest playground/tests/test_entry_point_bootstrap.py -q
# Unter `python -m playground.run` vom Repo-Root und unter pytest ist das ein
# No-op (identisches Muster wie in `playground/tests/input_characterization.py`).
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# sys.path-Bootstrap Stufe 1: Repo-Root, Repo-`src/`, `examples/` und
# Rigging-Experiment — Details und Reihenfolge in `playground/_paths.py`.
from playground._paths import ensure_paths  # noqa: E402

import pyglet  # noqa: E402

from playground.app import PlaygroundApp  # noqa: E402
from playground.window import PlaygroundWindow  # noqa: E402


def main() -> None:
    mesh = sys.argv[1] if len(sys.argv) > 1 else "cube"
    app = PlaygroundApp()
    # AD-010: Szene-Load passiert in PlaygroundWindow selbst, NACH
    # GL-Kontext-Erzeugung (PlaygroundPygletStore braucht einen aktiven
    # Kontext) — hier nur noch die gewünschte Szene auswählen.
    win = PlaygroundWindow(app, initial_mesh=mesh)
    pyglet.app.run()


if __name__ == "__main__":
    main()
