"""Symmetry Lab auf dem App-Pfad — Einstiegspunkt (WP-SYM-LAB-03 Slice 1b).

Verwendung (vom Repo-Root, Windows und Linux gleich):
    python experiments/symmetry_lab/run_app.py                 # subd_cube (Default)
    python experiments/symmetry_lab/run_app.py head_basemesh
    python experiments/symmetry_lab/run_app.py man_with_shoes_basemesh

Baut denselben Pfad wie `src/main.py` (`Application` → `Viewport` V02 →
`GLRenderStore`) über dessen `create_window` / `install_handlers` / `run` (H6)
und ergänzt nur die Lab-Teile (`lab_app`, `lab_overlays`, `lab_app_window`).
Gültige Namen = `loaders.assets.asset_names()`; ein unbekannter Name bricht mit
Exit-Code 2 ab, bevor ein Fenster geöffnet wird. Der alte Einstieg `run.py`
bleibt bis Slice 5 unverändert.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

# Stufe 0 (Skriptstart), wie run.py: experiments/ auf sys.path, damit
# `symmetry_lab` importierbar ist.
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from symmetry_lab._paths import REPO_SRC_DIR, ensure_paths  # noqa: E402

ensure_paths()

from loaders.assets import asset_path  # noqa: E402
from mirai.application import Application  # noqa: E402

from symmetry_lab.lab_app import SymmetryAppLab, start_lab, startup_listing  # noqa: E402
from symmetry_lab.lab_overlays import build_lab_overlays  # noqa: E402
from symmetry_lab.lab_scene import (  # noqa: E402
    DEFAULT_ASSET,
    UnknownAssetError,
    resolve_asset_name,
)

CAPTION = "Mirai — Symmetry Lab (App-Pfad)"


def load_src_main():
    """`src/main.py` als Modul (H6). `ensure_paths()` legt `src/` an den Anfang
    von sys.path; geprüft wird trotzdem, dass wirklich diese Datei geladen wurde."""
    module = importlib.import_module("main")
    if Path(module.__file__).resolve() != (REPO_SRC_DIR / "main.py").resolve():
        raise ImportError(f"'main' ist nicht src/main.py, sondern {module.__file__}")
    return module


def build_lab(window, asset_name: str, src_main, gl_types: dict | None = None):
    """Application + Lab + Szene + Overlays + Handler an `window`.

    `gl_types` = `src_main.GL_TYPES` im echten Fenster; `None` = headless
    (TraceStore, keine GL-Overlays des Viewports), für Tests mit einem
    Stellvertreter-Fenster."""
    from symmetry_lab.lab_app_window import install_lab_window

    app = Application()
    lab: SymmetryAppLab = start_lab(app)
    app.init_scene("obj", obj_path=asset_path(asset_name), **(gl_types or {}))
    app.frame_scene()
    # Erste Größe/Aspect wie main.py, damit der erste Frame nicht verzerrt ist.
    app.set_viewport_size(window.width, window.height)
    lab.attach_overlays(app.viewport, build_lab_overlays())
    hud = install_lab_window(window, app, lab, src_main)
    return app, lab, hud


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mirai-Bastel Symmetry Lab auf dem App-Pfad (WP-SYM-LAB-03)"
    )
    parser.add_argument("asset", nargs="?", default=DEFAULT_ASSET,
                        help=f"Registry-Name des Start-Assets (Default: {DEFAULT_ASSET})")
    args = parser.parse_args(argv)
    try:
        asset_name = resolve_asset_name(args.asset)
    except UnknownAssetError as exc:
        print(exc, file=sys.stderr)
        return 2

    for line in startup_listing():
        print(line)

    # pyglet (über src/main.py) erst hier: Namensprüfung und --help brauchen
    # kein Fenstersystem.
    src_main = load_src_main()
    window = src_main.create_window(caption=CAPTION)
    app, _lab, _hud = build_lab(window, asset_name, src_main, gl_types=src_main.GL_TYPES)
    src_main.run(window, app)
    return 0


if __name__ == "__main__":
    sys.exit(main())
