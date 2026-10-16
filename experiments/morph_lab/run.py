"""Morph Lab — entry point on the app path (WP-MORPH-LAB-01).

Usage (from the repo root, same on Windows and Linux):
    python experiments/morph_lab/run.py                          # head_basemesh (default)
    python experiments/morph_lab/run.py man_with_shoes_basemesh
    python experiments/morph_lab/run.py head_basemesh --neu      # start over (old file -> .bak)

First start per asset: writes `scenes/morph_lab/<asset>.mirai.json` (base + an ID-identical target
beside it, `lab_scene`) and opens it. Later starts reopen that file, so Ctrl+S keeps the sculpted
target. Builds the same path as `src/main.py` (`Application` → Viewport → `GLRenderStore`) through
its `create_window` / `install_handlers(save=)` / `run` (H6) and adds only the lab parts: the
replacement surface (AD-013 H7, second user) attached after the load, the weight keys and a HUD
line. All modelling tools, lighting and shading are the app's. An unknown asset name exits with
code 2 before a window opens; an unusable scene file exits with code 1 and names `--neu`.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

# Stage 0 (script start): only this folder is on sys.path[0]; without
# `experiments/` the next import fails with "No module named 'morph_lab'".
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from morph_lab._paths import REPO_SRC_DIR, ensure_paths  # noqa: E402

ensure_paths()

from mirai.application import Application  # noqa: E402
from scene_files import SceneFiles  # noqa: E402

from morph_lab.lab_app import MorphAppLab, install_lab_bindings, startup_listing  # noqa: E402
from morph_lab.lab_scene import (  # noqa: E402
    DEFAULT_ASSET,
    DEFAULT_SCENE_DIR,
    LabSceneError,
    UnknownAssetError,
    resolve_asset_name,
    resolve_pair,
    scene_path,
    write_start_scene,
)

CAPTION = "Mirai — Morph Lab (App-Pfad)"


def load_src_main():
    """`src/main.py` as a module (H6); checked that it really is that file."""
    module = importlib.import_module("main")
    if Path(module.__file__).resolve() != (REPO_SRC_DIR / "main.py").resolve():
        raise ImportError(f"'main' ist nicht src/main.py, sondern {module.__file__}")
    return module


def build_app_lab(
    asset_name: str,
    width: int,
    height: int,
    gl_types: dict | None = None,
    scene_dir: str | Path = DEFAULT_SCENE_DIR,
    new: bool = False,
) -> tuple[Application, MorphAppLab, SceneFiles]:
    """Application + lab from the lab's scene file, without a window (headless: `gl_types=None`,
    TraceStore). One-time set-up before the event loop as `src/main.py` opens a scene file
    (`init_scene` + `SceneFiles.load` → `load_scene`, then `frame_scene`, `set_viewport_size`);
    the provider is attached after the load, which builds a new viewport (review F-5)."""
    path = scene_path(asset_name, scene_dir)
    if new or not path.exists():
        backup = write_start_scene(asset_name, path)
        print(f"Neue Morph-Szene: {path}" + (f" (alte Datei: {backup.name})" if backup else ""))
    app = Application()
    install_lab_bindings(app.bindings)
    gl_types = dict(gl_types or {})
    app.init_scene("cube", **gl_types)
    files = SceneFiles(app, directory=scene_dir, gl_types=gl_types)
    if not files.load(path):
        raise LabSceneError(f"{app.status_message} - mit --neu neu anlegen")
    try:
        base_id, target_id = resolve_pair(app.scene, asset_name)
    except LabSceneError as exc:
        raise LabSceneError(f"{path.name}: {exc} - mit --neu neu anlegen") from exc
    app.frame_scene()
    app.set_viewport_size(width, height)
    lab = MorphAppLab(app, base_id, target_id)
    lab.attach(app.viewport)
    return app, lab, files


def _tolerate_unencodable_output() -> None:
    """German text + arrows must not crash a redirected stdout with a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mirai-Bastel Morph Lab (App-Pfad, WP-MORPH-LAB-01)")
    parser.add_argument("asset", nargs="?", default=DEFAULT_ASSET,
                        help=f"Registry-Name des Basis-Assets (Default: {DEFAULT_ASSET})")
    parser.add_argument("--neu", action="store_true",
                        help="Szene neu anlegen (Basis + unverändertes Ziel); die alte Datei wird .bak")
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
    from morph_lab.lab_app_window import install_lab_window

    window = src_main.create_window(caption=CAPTION)
    try:
        app, lab, files = build_app_lab(
            asset_name, window.width, window.height, gl_types=src_main.GL_TYPES, new=args.neu
        )
    except LabSceneError as exc:
        print(exc, file=sys.stderr)
        window.close()
        return 1
    install_lab_window(window, app, lab, src_main, asset_name, save=files.save)
    src_main.run(window, app)
    return 0


if __name__ == "__main__":
    sys.exit(main())
