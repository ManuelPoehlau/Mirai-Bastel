"""Mehlsack Lab — visible window for Manu.

Usage (from the repo root, same on Windows and Linux; needs `pyglet`):
    python experiments/mehlsack_lab/run.py

Controls: `LAB_OVERRIDES` in `lab_bindings.py` (printed at start) and the README. At start
the window prints `GL_VERSION` / `GL_RENDERER`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Stage 0 (script start): only this folder is on sys.path[0]; without `experiments/` the
# next import fails with "No module named 'mehlsack_lab'".
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

# Stage 1: src/, repo root, experiments/ — see mehlsack_lab/_paths.py.
from mehlsack_lab._paths import ensure_paths  # noqa: E402

ensure_paths()

from mehlsack_lab.lab_bindings import overrides_table  # noqa: E402


def _tolerate_unencodable_output() -> None:
    """German text + arrows must not crash a redirected stdout with a legacy code page
    (Windows `> file`): replace what cannot be encoded."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirai-Bastel Mehlsack Lab (Slice 2a: Move)")
    _tolerate_unencodable_output()
    parser.parse_args(argv)

    print("Mehlsack Lab — Eingaben (LAB_OVERRIDES):")
    for line in overrides_table():
        print(f"  {line}")

    # pyglet only here: --help needs no window system.
    import pyglet

    from mehlsack_lab.lab_window import MehlsackLabWindow

    MehlsackLabWindow()
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
