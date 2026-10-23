"""Serialisierung: Scene-Hülle statt reinem Mesh-Dateiformat.

Bezug: V1_SPEC.md §12, AD-021 §5.3.

Architekturvertrag: das Format hat von Anfang an benannte Plätze für
morph_targets/rig/animation, auch wenn diese in V1 immer `null` sind.
Künftige Subsysteme erweitern das Format um einen benannten Platz.
Keine Versions-Migrations-Engine, kein Plugin-Serialisierungsframework
(§12) - absichtlich nicht Teil dieser Datei.

Version 2 (AD-021 M0) ist die erste und einzige Migration: die Geometrie
liegt nicht mehr unter `"mesh"`, sondern pro Objekt unter
`"objects"[i]["mesh"]` (unverändertes `Mesh.export_state()`-Format inkl.
`"symmetry"`). Version 1 wird weiter gelesen - als ein normales Objekt mit
Identitäts-Transform, das Edit-Objekt ist; geschrieben wird nur Version 2.
Das ist ein einzelner Lese-Zweig, keine Migrations-Engine.

Version 3 (Spiegelpaare, OBJECT_MIRROR_SYMMETRY_PROPOSAL §5.1, CORE_V1_FREEZE §7.1) ist
additiv: ein benannter Platz `"mirror_pairs"` (`a`/`b` = ObjectIds der Datei, `normal`,
`offset`) neben den reservierten Plätzen. Version 2 liest sich als Version 3 ohne Paare;
geschrieben wird nur Version 3. Ein Paar auf ein fehlendes Objekt macht die Datei ungültig.

Selection und History werden bewusst NICHT mitgespeichert - beides ist
transienter UI-/Session-Zustand, kein persistenter Scene-Inhalt. Das
Edit-Objekt dagegen ist Scene-Zustand und wird gespeichert (AD-021 §2).
"""

from __future__ import annotations

import json

from .ids import ObjectId
from .mesh import Mesh
from .scene import MirrorPair, ObjectState, ObjectTransform, Scene, SceneObject

FORMAT_VERSION = 3


def scene_to_dict(scene: Scene) -> dict:
    return {
        "version": FORMAT_VERSION,
        "object_id_counter": scene.object_id_counter,
        "edit_object": int(scene.edit_object_id),
        "objects": [_object_to_dict(obj) for obj in scene.objects.values()],
        "mirror_pairs": [_pair_to_dict(pair) for pair in scene.mirror_pairs],
        # Reservierte, aktuell leere Plätze für künftige Subsysteme (§12):
        "morph_targets": scene.morph_targets,
        "rig": scene.rig,
        "animation": scene.animation,
    }


def scene_from_dict(data: dict) -> Scene:
    version = data.get("version")
    if version in (2, FORMAT_VERSION):
        scene = Scene.from_objects(
            (_object_from_dict(raw) for raw in data["objects"]),
            edit_object_id=ObjectId(data["edit_object"]),
            object_id_counter=int(data["object_id_counter"]),
            mirror_pairs=(
                [_pair_from_dict(raw) for raw in data.get("mirror_pairs") or ()]
                if version == FORMAT_VERSION
                else ()
            ),
        )
    elif version == 1:
        scene = Scene()
        scene.mesh = Mesh.from_state(data["mesh"])
    else:
        raise ValueError(f"Unbekannte/nicht unterstützte Scene-Version: {version!r}")
    scene.morph_targets = data.get("morph_targets")
    scene.rig = data.get("rig")
    scene.animation = data.get("animation")
    return scene


def _object_to_dict(obj: SceneObject) -> dict:
    return {
        "id": int(obj.id),
        "name": obj.name,
        "state": obj.state.value,
        "transform": {
            "translation": list(obj.transform.translation),
            "rotation": [list(row) for row in obj.transform.rotation],
            "scale": obj.transform.scale,
        },
        "pivot": list(obj.pivot),
        "mesh": obj.mesh.export_state(),
    }


def _object_from_dict(raw: dict) -> SceneObject:
    transform = raw["transform"]
    return SceneObject(
        ObjectId(raw["id"]),
        Mesh.from_state(raw["mesh"]),
        name=raw["name"],
        transform=ObjectTransform(
            translation=transform["translation"],
            rotation=transform["rotation"],
            scale=transform["scale"],
        ),
        pivot=raw["pivot"],
        state=ObjectState(raw["state"]),
    )


def _pair_to_dict(pair: MirrorPair) -> dict:
    return {"a": int(pair.a), "b": int(pair.b), "normal": list(pair.normal), "offset": pair.offset}


def _pair_from_dict(raw: dict) -> MirrorPair:
    return MirrorPair(ObjectId(raw["a"]), ObjectId(raw["b"]), normal=raw["normal"], offset=raw["offset"])


def scene_to_json(scene: Scene, *, indent: int | None = 2) -> str:
    return json.dumps(scene_to_dict(scene), indent=indent)


def scene_from_json(text: str) -> Scene:
    return scene_from_dict(json.loads(text))
