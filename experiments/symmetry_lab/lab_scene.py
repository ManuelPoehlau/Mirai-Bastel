"""Asset-Namen der Registry prüfen; Mesh ohne Viewport laden (GL-frei).

`run.py` nutzt `DEFAULT_ASSET`, `resolve_asset_name` und `UnknownAssetError`
(Exit-Code 2 vor dem Fenster); geladen wird dort über `Application.init_scene`
(H2-R4 (f)). `load_asset_into` setzt `app.scene.mesh` direkt, ohne Viewport — seit
WP-SYM-LAB-03 Slice 5 nur noch für die Forschungs-Tests (`test_lab_topology`,
`test_lab_knife`, `test_lab_resymmetrize`, `test_lab_symmetry`, `test_lab_scene`),
nicht für den Lab-Pfad. Muster aus `PlaygroundApp.load_asset` / `_frame_camera`
(Stand `47f821b`).
"""

from __future__ import annotations

from core.selection import SelectionMode
from loaders.assets import asset_names, asset_path
from mirai.application import Application
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.scene_factory import build_core_scene_from_obj

DEFAULT_ASSET = "subd_cube"
#: Gleicher Wert wie `PlaygroundApp._frame_camera`.
FRAME_MARGIN = 1.4


class UnknownAssetError(LookupError):
    """Asset-Name ist nicht in `loaders.assets.asset_names()` registriert."""


def resolve_asset_name(name: str) -> str:
    """Gibt `name` zurück oder wirft `UnknownAssetError` mit allen gültigen Namen."""
    valid = asset_names()
    if name not in valid:
        raise UnknownAssetError(
            f"Unbekanntes Asset {name!r}. Gültige Namen: {', '.join(valid)}"
        )
    return name


def load_asset_into(app: Application, name: str) -> None:
    """Lädt das Asset in `app.scene`, leert die Auswahl (Vertex-Modus) und rahmt die Kamera."""
    resolve_asset_name(name)
    app.scene.mesh = build_core_scene_from_obj(asset_path(name)).mesh
    selection = app.scene.selection
    selection.clear()
    selection.mode = SelectionMode.VERTEX
    center, radius = mesh_center_and_radius(app.scene.mesh)
    app.camera.frame_on_bounds(center, radius, margin=FRAME_MARGIN)
