"""Szene laden: Registry-Asset → `app.scene.mesh` + Kamera-Framing.

Muster aus `PlaygroundApp.load_asset` / `_frame_camera` (Stand `47f821b`),
ohne `Viewport`/`PygletStore` (Handoff Slice 2 §2.3: beides zeichnet nichts).
GL-frei — der Aufrufer (Fenster) ruft `load_asset_into` erst auf, nachdem
der GL-Kontext existiert (AD-010-Befund).
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
