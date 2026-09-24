"""Asset-Loader und geteilte Asset-Registratur (AD-007, `examples/`).

Bewusst experimentell: Die Loader sind reine Parser ohne Core-, Viewport-
oder pyglet-Abhängigkeit und damit headless testbar. Die Überführung in das
Core-Mesh passiert im Viewport-Adapter (siehe viewport_adapter.py).

`obj_loader` parst eine beliebige `.obj`-Datei; `assets` bildet die Namen der
geteilten Assets in `examples/meshes/` auf Pfade und Loader ab.
"""

from .assets import (
    ASSETS,
    ASSETS_DIR,
    ObjAsset,
    asset_names,
    asset_path,
    get_asset,
    load_asset,
)
from .obj_loader import ObjLoadError, ObjMeshData, load_obj, parse_obj

__all__ = [
    "ASSETS",
    "ASSETS_DIR",
    "ObjAsset",
    "ObjLoadError",
    "ObjMeshData",
    "asset_names",
    "asset_path",
    "get_asset",
    "load_asset",
    "load_obj",
    "parse_obj",
]
