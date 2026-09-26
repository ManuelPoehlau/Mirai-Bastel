"""Viewport Shading Lab — visible window for Manu (handoff E17).

Usage (from the repo root, same on Windows and Linux):
    python experiments/viewport_shading_lab/run.py                  # head_basemesh (default)
    python experiments/viewport_shading_lab/run.py subd_cube

Valid names = `loaders.assets.asset_names()` (examples/loaders/assets.py). An
unknown name exits with code 2 and the list of valid names before any window
opens. Controls: `LAB_OVERRIDES` in `lab_bindings.py` (printed at start) and
the README.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Stage 0 (script start): only this folder is on sys.path[0]; without
# `experiments/` the next import fails with "No module named 'viewport_shading_lab'".
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

# Stage 1: src/, repo root, examples/, experiments/ — see viewport_shading_lab/_paths.py.
from viewport_shading_lab._paths import ensure_paths  # noqa: E402

ensure_paths()

from viewport_shading_lab.lab_bindings import overrides_table  # noqa: E402
from viewport_shading_lab.lab_scene import (  # noqa: E402
    DEFAULT_ASSET,
    UnknownAssetError,
    resolve_asset_name,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirai-Bastel Viewport Shading Lab (Slice 1)")
    parser.add_argument("asset", nargs="?", default=DEFAULT_ASSET,
                        help=f"Registry-Name des Meshes (Default: {DEFAULT_ASSET})")
    args = parser.parse_args(argv)
    try:
        asset_name = resolve_asset_name(args.asset)
    except UnknownAssetError as exc:
        print(exc, file=sys.stderr)
        return 2

    print("Viewport Shading Lab — Eingaben (LAB_OVERRIDES):")
    for line in overrides_table():
        print(f"  {line}")

    # pyglet only here: name check and --help need no window system.
    import pyglet

    from viewport_shading_lab.lab_window import ShadingLabWindow

    ShadingLabWindow(asset_name)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
