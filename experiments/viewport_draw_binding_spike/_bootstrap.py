"""Import-Hilfe: reine Pfad-Injektion, kein Verhalten.

Fügt `src/` (für `core`, `viewport`, `mirai`) und `examples/` (für
`loaders.obj_loader`, benötigt von `mirai.scene_factory.build_core_scene_from_obj`)
auf `sys.path`, analog `tests/_bootstrap.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _REPO_ROOT / "src"
_EXAMPLES = _REPO_ROOT / "examples"

for _path in (str(_SRC), str(_EXAMPLES), str(_REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
