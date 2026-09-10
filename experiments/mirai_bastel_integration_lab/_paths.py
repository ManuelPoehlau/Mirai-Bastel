"""sys.path-Bootstrap für das Integration Lab.

Das Lab lebt als flache, eigenständige Sammlung (wie die übrigen
Experimente): Der Lab-Ordner, das Repository-Root, das Repository-`src/`
(für die Production-Pakete `core`/`viewport`/`mirai`, WP-IL-01) und das
Rigging-Experiment (für den OBJ Loader) werden auf `sys.path` gelegt.
Dadurch funktionieren alle Lab-Imports sowohl als Skript (`python run.py`)
als auch unter pytest.

Hinweis: `src/` liegt VOR dem Repo-Root — das Top-Level-`viewport` löst
dadurch auf `src/viewport` (Production) auf, nicht auf das stray-Verzeichnis
`viewport/` im Repo-Root (Repo-Hygiene-Befund, Audit §H).
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_DIR = _LAB_DIR.parent
_REPO_ROOT = _EXPERIMENTS_DIR.parent
_REPO_SRC_DIR = _REPO_ROOT / "src"
_RIGGING_DIR = _EXPERIMENTS_DIR / "rigging-skinning-morphing"


def ensure_paths() -> None:
    """Legt Lab-Ordner, Repo-Root, Repo-`src/` und Rigging-Ordner auf sys.path."""
    for _path in (
        str(_LAB_DIR),
        str(_REPO_ROOT),
        str(_REPO_SRC_DIR),
        str(_RIGGING_DIR),
    ):
        if _path not in sys.path:
            sys.path.insert(0, _path)


# Repository-relativer Standardpfad zum Head-Basemesh-Asset.
DEFAULT_HEAD_ASSET = _RIGGING_DIR / "meshes" / "head_basemesh.obj"