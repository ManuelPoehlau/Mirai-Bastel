"""sys.path-Bootstrap für das Artist Playground.

Legt Repo-Root, Repo-`src/` (für Production-Pakete `core`/`viewport`/`mirai`),
`examples/` (für den geteilten OBJ-Loader und den Head-Basemesh-Asset, AD-007)
und das Rigging-Experiment (für `deformation.Transform`, gebraucht vom
Articulation-Experiment, `playground/experiments/articulation/articulation.py`
— unabhängig vom OBJ-Loader, der seit AD-007 in `examples/` liegt) auf
sys.path.

Dadurch funktionieren alle Playground-Imports, sobald `ensure_paths()`
gelaufen ist — unter pytest aus dem Repo-Root, unter `python -m
playground.run` und als Skript (`python playground/run.py`).

Wichtig (beobachteter Fehlerfall): `ensure_paths()` kann diesen Bootstrap
nicht selbst leisten, wenn die Datei per Skriptaufruf startet. Bei
`python playground/run.py` legt CPython `playground/` auf sys.path[0] und
nicht das Repo-Root; `from playground._paths import ensure_paths` scheitert
dann mit `ModuleNotFoundError: No module named 'playground'`. Skript-
Einstiegspunkte in `playground/` (aktuell `run.py`, `_diag_screenshot.py`)
hängen deshalb VOR diesem Import das Repo-Root ein („Stufe 0", siehe
Kommentar in `playground/run.py`).

Hinweis: `src/` liegt VOR dem Repo-Root — das Top-Level-`viewport` löst
dadurch auf `src/viewport` (Production) auf, nicht auf das stray-Verzeichnis
`viewport/` im Repo-Root.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PLAYGROUND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PLAYGROUND_DIR.parent
_REPO_SRC_DIR = _REPO_ROOT / "src"
_EXAMPLES_DIR = _REPO_ROOT / "examples"
_RIGGING_DIR = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"


def ensure_paths() -> None:
    """Legt Repo-Root, Repo-`src/`, `examples/` und Rigging auf sys.path."""
    for _path in (
        str(_REPO_SRC_DIR),
        str(_REPO_ROOT),
        str(_EXAMPLES_DIR),
        str(_RIGGING_DIR),
    ):
        if _path not in sys.path:
            sys.path.insert(0, _path)


# Repository-relativer Standardpfad zum Head-Basemesh-Asset (AD-007: examples/, geteilt).
DEFAULT_HEAD_ASSET = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"
