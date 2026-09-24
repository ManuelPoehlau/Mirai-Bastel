"""Registratur der geteilten OBJ-Assets in `examples/meshes/` (AD-007).

Der `obj_loader` ist bewusst rein pfadbasiert: Er kennt keine Assets, sondern
nur `load_obj(pfad)`. Diese Registratur ist die eine Stelle, an der die *Namen*
der vorhandenen Assets auf ihre Pfade abgebildet werden — damit Konsumenten
(Playground, Experimente, Tests) keine eigenen Pfadkonstanten je Asset anlegen
müssen. Genau diese Duplizierung (drei Konstanten für eine Datei) ist der
Grund, aus dem AD-007 die Asset-/Loader-Ownership überhaupt geklärt hat.

Bewusst kein Asset-*System*: keine Discovery, kein Manifest, keine Metadaten
außer Name, Pfad und einer kurzen Beschreibung. Oben in dieser Datei
registrieren, wer ein Asset nutzen will; alles andere läuft über den Loader.

Fehlerverhalten (laut statt still):

- Unbekannter Name → `KeyError` mit Liste der verfügbaren Namen.
- Registrierter, aber fehlender Dateipfad → `ObjLoadError` aus `load_obj`.

Verwendung::

    from loaders.assets import asset_path, load_asset

    data = load_asset("subd_cube")                 # direkt über den Obj-Loader
    scene = build_core_scene_from_obj(asset_path("man_with_shoes_basemesh"))
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .obj_loader import ObjMeshData, load_obj

#: Verzeichnis der geteilten Assets (AD-007: `examples/meshes/`).
ASSETS_DIR = Path(__file__).resolve().parent.parent / "meshes"


@dataclass(frozen=True)
class ObjAsset:
    """Ein benanntes OBJ-Asset in `examples/meshes/`."""

    #: Registry-Name (siehe `ASSETS`), klein und stabil.
    name: str
    #: Absoluter Pfad zur `.obj`-Datei.
    path: Path
    #: Kurzbeschreibung für Menschen (Reports, Doku).
    description: str

    @property
    def filename(self) -> str:
        """Dateiname (z. B. für Debug-Reports/Window-Titel)."""
        return self.path.name

    def load(self) -> ObjMeshData:
        """Parst dieses Asset über den geteilten Loader (`load_obj`)."""
        return load_obj(self.path)


#: Registry: Name → Asset. Reihenfolge = Reihenfolge in `asset_names()`.
ASSETS: dict[str, ObjAsset] = {
    "head_basemesh": ObjAsset(
        name="head_basemesh",
        path=ASSETS_DIR / "head_basemesh.obj",
        description=(
            "Rigging-Kopf-Basemesh (326 V / 324 Quads, geschlossen). "
            "Referenz-Asset für Rigging-Experiment und Playground."
        ),
    ),
    "man_with_shoes_basemesh": ObjAsset(
        name="man_with_shoes_basemesh",
        path=ASSETS_DIR / "Man_With_Shoes_basemesh.obj",
        description=(
            "Charakter-Basemesh „Mann mit Schuhen“ (928 V / 926 Quads, "
            "geschlossen, ca. 1,88 Einheiten hoch)."
        ),
    ),
    "subd_cube": ObjAsset(
        name="subd_cube",
        path=ASSETS_DIR / "SubD_Cube.obj",
        description=(
            "Würfel, dessen sechs Flächen je in vier Quads unterteilt sind "
            "(26 V / 24 Quads, geschlossen). Kompaktes Testasset für SubD-/"
            "Topologie-Arbeit."
        ),
    ),
}


def asset_names() -> tuple[str, ...]:
    """Alle registrierten Asset-Namen in Registry-Reihenfolge."""
    return tuple(ASSETS)


def get_asset(name: str) -> ObjAsset:
    """Asset per Name; unbekannte Namen fliegen laut (`KeyError`)."""
    try:
        return ASSETS[name]
    except KeyError as exc:
        raise KeyError(
            f"Unbekanntes OBJ-Asset {name!r}. "
            f"Registriert: {', '.join(asset_names())}."
        ) from exc


def asset_path(name: str) -> Path:
    """Pfad zur `.obj`-Datei eines registrierten Assets."""
    return get_asset(name).path


def load_asset(name: str) -> ObjMeshData:
    """Registriertes Asset über den geteilten Obj-Loader parsen."""
    return get_asset(name).load()
