"""Serialisierung: Scene-Hülle statt reinem Mesh-Dateiformat.

Bezug: V1_SPEC.md §12.

Architekturvertrag: das Format hat von Anfang an benannte Plätze für
morph_targets/rig/animation, auch wenn diese in V1 immer `null` sind.
Damit muss das Format beim Hinzufügen künftiger Subsysteme erweitert,
nicht migriert werden. Keine Versions-Migrations-Engine, kein Plugin-
Serialisierungsframework (§12) - absichtlich nicht Teil dieser Datei.

Selection und History werden bewusst NICHT mitgespeichert - beides ist
transienter UI-/Session-Zustand, kein persistenter Scene-Inhalt.
"""

from __future__ import annotations

import json

from .mesh import Mesh
from .scene import Scene

FORMAT_VERSION = 1


def scene_to_dict(scene: Scene) -> dict:
    return {
        "version": FORMAT_VERSION,
        "mesh": scene.mesh.export_state(),
        # Reservierte, aktuell leere Plätze für künftige Subsysteme (§12):
        "morph_targets": scene.morph_targets,
        "rig": scene.rig,
        "animation": scene.animation,
    }


def scene_from_dict(data: dict) -> Scene:
    if data.get("version") != FORMAT_VERSION:
        raise ValueError(f"Unbekannte/nicht unterstützte Scene-Version: {data.get('version')!r}")
    scene = Scene()
    scene.mesh = Mesh.from_state(data["mesh"])
    scene.morph_targets = data.get("morph_targets")
    scene.rig = data.get("rig")
    scene.animation = data.get("animation")
    return scene


def scene_to_json(scene: Scene, *, indent: int | None = 2) -> str:
    return json.dumps(scene_to_dict(scene), indent=indent)


def scene_from_json(text: str) -> Scene:
    return scene_from_dict(json.loads(text))
