"""Regression: die dokumentierten Skript-Einstiegspunkte müssen startbar sein.

Beobachteter Fehler (2026-09-22): `python playground/run.py grid` brach ab mit

    ModuleNotFoundError: No module named 'playground'

Ursache: Bei Skriptstart legt CPython das Verzeichnis des Skripts
(`playground/`) auf sys.path[0], nicht das Repo-Root. Der sys.path-Bootstrap
in `playground/_paths.py` kann sich in diesem Moment nicht selbst importieren.
Die Einstiegspunkte hängen deshalb zuerst das Repo-Root ein („Stufe 0",
siehe `playground/run.py`).

Dieser Test fährt genau diese sys.path-Situation in einem Subprozess nach und
führt den Top-Level-Teil der Einstiegspunkte aus — ohne Fenster, ohne GL:
`__name__ != "__main__"` verhindert den Aufruf von `main()`.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLAYGROUND_DIR = _REPO_ROOT / "playground"

# Wird im Subprozess als `python -c` ausgeführt. Baut exakt die sys.path-Situation
# von `python playground/<script>.py` nach: Skript-Verzeichnis auf Position 0,
# Repo-Root und CWD NICHT auf sys.path. Danach wird das Skript als Modul
# ausgeführt (nicht als `__main__`), damit kein Fenster geöffnet wird.
_DRIVER = """
import os, sys

playground_dir, repo_root, target = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path[:] = [playground_dir] + [
    p for p in sys.path
    if p not in ("", repo_root, playground_dir, os.getcwd(), os.path.abspath(os.getcwd()))
]

with open(target, encoding="utf-8") as fh:
    source = fh.read()

exec(compile(source, target, "exec"),
     {"__name__": "playground_entry_point_check", "__file__": target})
print("ENTRY-POINT-IMPORTS-OK")
"""


@pytest.mark.parametrize("script", ["run.py", "_diag_screenshot.py"])
def test_script_entry_point_bootstrap(script: str) -> None:
    """Skriptstart aus dem Repo-Root darf nicht am Bootstrap scheitern."""
    target = _PLAYGROUND_DIR / script
    assert target.is_file(), f"{script} fehlt"

    # PYTHONPATH entfernen, damit ein äußerer Eintrag das Ergebnis nicht maskiert.
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _DRIVER,
            str(_PLAYGROUND_DIR),
            str(_REPO_ROOT),
            str(target),
        ],
        cwd=str(_REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert result.returncode == 0, (
        f"`python playground/{script}` startet nicht (Simulation ohne Fenster).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "ENTRY-POINT-IMPORTS-OK" in result.stdout
