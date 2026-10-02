"""Subdivision Mini-Lab — visible window for Manu.

Usage (from the repo root, same on Windows and Linux):
    python experiments/subdivision_lab/run.py                      # head_basemesh (default)
    python experiments/subdivision_lab/run.py subd_cube
    python experiments/subdivision_lab/run.py head_basemesh --host "Manu-PC"

Valid names = `loaders.assets.asset_names()` (examples/loaders/assets.py). An
unknown name exits with code 2 and the list of valid names before any window
opens. `--host` is the label printed above every F9 bench table (where it was
measured). Controls: `LAB_OVERRIDES` in `lab_bindings.py` (printed at start) and
the README. At start the window prints `GL_VERSION` / `GL_RENDERER`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Stage 0 (script start): only this folder is on sys.path[0]; without
# `experiments/` the next import fails with "No module named 'subdivision_lab'".
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

# Stage 1: src/, repo root, examples/, experiments/ — see subdivision_lab/_paths.py.
from subdivision_lab._paths import ensure_paths  # noqa: E402

ensure_paths()

from subdivision_lab.lab_bindings import overrides_table  # noqa: E402
from subdivision_lab.lab_scene import (  # noqa: E402
    DEFAULT_ASSET,
    UnknownAssetError,
    resolve_asset_name,
)


def _tolerate_unencodable_output() -> None:
    """German text + arrows must not crash a redirected stdout with a legacy
    code page (Windows `> file`): replace what cannot be encoded."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirai-Bastel Subdivision-Mini-Lab (Slice 1)")
    parser.add_argument("asset", nargs="?", default=DEFAULT_ASSET,
                        help=f"Registry-Name des Meshes (Default: {DEFAULT_ASSET})")
    parser.add_argument("--host", default="unlabeled",
                        help="Host-Label für Messungen (steht über jeder Bench-Tabelle)")
    _tolerate_unencodable_output()
    args = parser.parse_args(argv)
    try:
        asset_name = resolve_asset_name(args.asset)
    except UnknownAssetError as exc:
        print(exc, file=sys.stderr)
        return 2

    print("Subdivision-Mini-Lab — Eingaben (LAB_OVERRIDES):")
    for line in overrides_table():
        print(f"  {line}")

    # pyglet only here: name check and --help need no window system.
    import pyglet

    from subdivision_lab.lab_window import SubdLabWindow

    SubdLabWindow(asset_name, host_label=args.host)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
