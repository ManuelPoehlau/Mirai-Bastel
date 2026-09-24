"""Symmetry Lab — Einstiegspunkt.

Verwendung (vom Repo-Root, Windows und Linux gleich):
    python experiments/symmetry_lab/run.py                 # subd_cube (Default)
    python experiments/symmetry_lab/run.py head_basemesh
    python experiments/symmetry_lab/run.py man_with_shoes_basemesh

Gültige Namen = `loaders.assets.asset_names()` (examples/loaders/assets.py).
Ein unbekannter Name bricht mit Exit-Code 2 und der Liste der gültigen Namen
ab, bevor ein Fenster geöffnet wird.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path-Bootstrap Stufe 0 (Skriptstart) — nachgebaut nach playground/run.py.
# Bei `python experiments/symmetry_lab/run.py` liegt nur dieser Ordner auf
# sys.path[0]; ohne `experiments/` scheitert der nächste Import mit
# ModuleNotFoundError: No module named 'symmetry_lab'.
# ---------------------------------------------------------------------------
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

# Stufe 1: src/, Repo-Root, examples/, experiments/ — siehe symmetry_lab/_paths.py.
from symmetry_lab._paths import ensure_paths  # noqa: E402

ensure_paths()

from mirai.application import Application  # noqa: E402

from symmetry_lab.lab_bindings import (  # noqa: E402
    LAB_OVERRIDES,
    SYMMETRY_LAB_CONTEXT,
    apply_lab_bindings,
)
from symmetry_lab.lab_scene import (  # noqa: E402
    DEFAULT_ASSET,
    UnknownAssetError,
    resolve_asset_name,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirai-Bastel Symmetry Lab")
    parser.add_argument("asset", nargs="?", default=DEFAULT_ASSET,
                        help=f"Registry-Name des Start-Assets (Default: {DEFAULT_ASSET})")
    args = parser.parse_args(argv)
    try:
        asset_name = resolve_asset_name(args.asset)
    except UnknownAssetError as exc:
        print(exc, file=sys.stderr)
        return 2

    app = Application()
    apply_lab_bindings(app.bindings)
    print(f"Lab-Overrides (Kontext {SYMMETRY_LAB_CONTEXT!r}):")
    for override in LAB_OVERRIDES:
        print(f"  {override.describe()}")

    # pyglet erst hier: Namensprüfung und --help brauchen kein Fenstersystem.
    import pyglet

    from symmetry_lab.lab_window import SymmetryLabWindow

    SymmetryLabWindow(app, asset_name)
    pyglet.app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
