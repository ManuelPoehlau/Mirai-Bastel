"""sys.path-Bootstrap für das Artist Playground.

Legt Repo-Root, Repo-`src/` (für Production-Pakete `core`/`viewport`/`mirai`),
`examples/` (für den geteilten OBJ-Loader und den Head-Basemesh-Asset, AD-007),
das Rigging-Experiment (für `deformation.Transform`, gebraucht vom
Articulation-Experiment, `playground/experiments/articulation/articulation.py`
— unabhängig vom OBJ-Loader, der seit AD-007 in `examples/` liegt) und das
Integration Lab (für die Framing-/Mesh-Adapter `adapters.obj_to_core`) auf
sys.path.

Dadurch funktionieren alle Playground-Imports sowohl als Skript
(`python playground/run.py`) als auch unter pytest aus dem Repo-Root.

Wiederverwendung statt Duplikation (WP-Grundsatz): Das Framing kommt aus dem
Integration Lab (`frame_camera_on_bounds`, `build_core_scene_from_obj`) — der
Playground nutzt damit exakt denselben Startpfad wie das Lab. Dafür muss der
Lab-Ordner auf sys.path liegen (top-level Pakete `adapters`/`scene`/`_paths`).

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
_LAB_DIR = _REPO_ROOT / "experiments" / "mirai_bastel_integration_lab"


def ensure_paths() -> None:
    """Legt Integration Lab, Repo-Root, Repo-`src/`, `examples/` und Rigging auf sys.path."""
    for _path in (
        str(_LAB_DIR),
        str(_REPO_SRC_DIR),
        str(_REPO_ROOT),
        str(_EXAMPLES_DIR),
        str(_RIGGING_DIR),
    ):
        if _path not in sys.path:
            sys.path.insert(0, _path)


# Repository-relativer Standardpfad zum Head-Basemesh-Asset (AD-007: examples/, geteilt).
DEFAULT_HEAD_ASSET = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"
