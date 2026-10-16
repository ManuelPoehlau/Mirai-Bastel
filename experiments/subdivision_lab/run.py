"""SubD Lab — entry point on the app path (WP-SUBD-LAB-02).

Usage (from the repo root, same on Windows and Linux):
    python experiments/subdivision_lab/run.py                 # head_basemesh (default)
    python experiments/subdivision_lab/run.py subd_cube
    python experiments/subdivision_lab/run.py man_with_shoes_basemesh

Builds the same path as `src/main.py` (`Application` → Viewport V02 → `GLRenderStore`) through its
`create_window` / `install_handlers` / `run` (H6) and adds only the lab parts: the replacement
surface (AD-013 H7), the cage/isoline overlay (H1), the lab keys and a HUD line (`lab_app`,
`lab_app_window`). All modelling tools, lighting and shading are the app's. Valid names =
`loaders.assets.asset_names()`; an unknown name exits with code 2 before a window opens. The
standalone window of WP-SUBD-LAB-01 (and its F9 bench) is `run_standalone.py`.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

# Stage 0 (script start): only this folder is on sys.path[0]; without
# `experiments/` the next import fails with "No module named 'subdivision_lab'".
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from subdivision_lab._paths import REPO_SRC_DIR, ensure_paths  # noqa: E402

ensure_paths()

from loaders.assets import asset_path  # noqa: E402
from mirai.application import Application  # noqa: E402

from subdivision_lab.lab_app import SubdAppLab, start_lab, startup_listing  # noqa: E402
from subdivision_lab.lab_scene import DEFAULT_ASSET, UnknownAssetError, resolve_asset_name  # noqa: E402

CAPTION = "Mirai — SubD Lab (App-Pfad)"


def load_src_main():
    """`src/main.py` as a module (H6); checked that it really is that file."""
    module = importlib.import_module("main")
    if Path(module.__file__).resolve() != (REPO_SRC_DIR / "main.py").resolve():
        raise ImportError(f"'main' ist nicht src/main.py, sondern {module.__file__}")
    return module


def build_app_lab(
    asset_name: str, width: int, height: int, gl_types: dict | None = None, line_sink=None
) -> tuple[Application, SubdAppLab]:
    """Application + lab + scene, without a window (headless: `gl_types=None`, TraceStore). One-time
    set-up before the event loop as in `src/main.py` (`init_scene`, `frame_scene`,
    `set_viewport_size`)."""
    app = Application()
    lab = start_lab(app, line_sink=line_sink)
    app.init_scene("obj", obj_path=asset_path(asset_name), **(gl_types or {}))
    app.frame_scene()
    app.set_viewport_size(width, height)
    lab.attach(app.viewport)
    return app, lab


def _tolerate_unencodable_output() -> None:
    """German text + arrows must not crash a redirected stdout with a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirai-Bastel SubD Lab (App-Pfad, WP-SUBD-LAB-02)")
    parser.add_argument("asset", nargs="?", default=DEFAULT_ASSET,
                        help=f"Registry-Name des Start-Assets (Default: {DEFAULT_ASSET})")
    _tolerate_unencodable_output()
    args = parser.parse_args(argv)
    try:
        asset_name = resolve_asset_name(args.asset)
    except UnknownAssetError as exc:
        print(exc, file=sys.stderr)
        return 2

    for line in startup_listing():
        print(line)

    # pyglet (through src/main.py) only here: name check and --help need no window system.
    src_main = load_src_main()
    from subdivision_lab.lab_app_window import install_lab_window
    from subdivision_lab.lab_lines import LabLineOverlay

    window = src_main.create_window(caption=CAPTION)
    app, lab = build_app_lab(
        asset_name, window.width, window.height, gl_types=src_main.GL_TYPES, line_sink=LabLineOverlay()
    )
    install_lab_window(window, app, lab, src_main, asset_name)
    src_main.run(window, app)
    return 0


if __name__ == "__main__":
    sys.exit(main())
