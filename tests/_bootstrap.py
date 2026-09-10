"""Import-Hilfe: Tests laufen gegen den Produktionspfad `src/core/` und den Repo-Root."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"

# Füge src/ VOR dem Repo-Root ein, damit viewport → src/viewport aufgelöst wird
for _path in (str(_SRC), str(_REPO_ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
