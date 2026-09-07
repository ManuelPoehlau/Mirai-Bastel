"""sys.path-Bootstrap für das Integration Lab.

Das Lab lebt als flache, eigenständige Sammlung (wie die übrigen
Experimente): Der Lab-Ordner, das Repository-Root und das Rigging-
Experiment (für den OBJ Loader) werden auf `sys.path` gelegt. Dadurch
funktionieren alle Lab-Imports sowohl als Skript (`python run.py`) als
auch unter pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

_LAB_DIR = Path(__file__).resolve().parent
_EXPERIMENTS_DIR = _LAB_DIR.parent
_REPO_ROOT = _EXPERIMENTS_DIR.parent
_RIGGING_DIR = _EXPERIMENTS_DIR / "rigging-skinning-morphing"


def ensure_paths() -> None:
    """Legt Lab-Ordner, Repo-Root und Rigging-Ordner auf sys.path."""
    for _path in (str(_LAB_DIR), str(_REPO_ROOT), str(_RIGGING_DIR)):
        if _path not in sys.path:
            sys.path.insert(0, _path)


# Repository-relativer Standardpfad zum Head-Basemesh-Asset.
DEFAULT_HEAD_ASSET = _RIGGING_DIR / "meshes" / "head_basemesh.obj"