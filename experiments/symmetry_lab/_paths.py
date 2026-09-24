"""sys.path-Bootstrap für das Symmetry Lab.

Nachgebaut (nicht importiert) nach `playground/_paths.py` / `playground/run.py`
„Stufe 0", Stand `47f821b`. Legt in dieser Reihenfolge auf sys.path:

1. Repo-`src/`       — Production-Pakete `core`, `viewport`, `mirai`
2. Repo-Root         — nach `src/`, damit ein Top-Level-`viewport` immer auf
                       `src/viewport` auflöst
3. `examples/`       — geteilter OBJ-Loader + Asset-Registry (`loaders`, AD-007)
4. `experiments/`    — damit das Paket `symmetry_lab` selbst importierbar ist

Abweichung vom Vorbild: `playground/_paths.py` fügt mit `insert(0, ...)` in
Listenreihenfolge ein und landet dadurch bei „Repo-Root VOR `src/`" (Gegenteil
seines Docstrings; heute folgenlos, weil kein Stray-`viewport/` im Repo-Root
liegt). Hier wird die Zielreihenfolge explizit hergestellt.

Stufe 0 (Skriptstart): Bei `python experiments/symmetry_lab/run.py` liegt nur
`experiments/symmetry_lab/` auf sys.path[0]; `run.py` hängt deshalb vor dem
Import dieses Moduls `experiments/` ein (siehe dortigen Kommentar).
"""

from __future__ import annotations

import sys
from pathlib import Path

LAB_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = LAB_DIR.parent
REPO_ROOT = EXPERIMENTS_DIR.parent
REPO_SRC_DIR = REPO_ROOT / "src"
EXAMPLES_DIR = REPO_ROOT / "examples"

_ORDERED_PATHS = (REPO_SRC_DIR, REPO_ROOT, EXAMPLES_DIR, EXPERIMENTS_DIR)


def ensure_paths() -> None:
    """Stellt die Reihenfolge aus dem Moduldocstring am Anfang von sys.path her."""
    wanted = [str(p) for p in _ORDERED_PATHS]
    sys.path[:] = wanted + [p for p in sys.path if p not in wanted]
