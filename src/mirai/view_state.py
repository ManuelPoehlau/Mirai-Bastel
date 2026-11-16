"""Ansichts-Zustand einer Szene speichern und laden (Manu 2026-11-07).

Shading, Wireframe, Region-Farben, Symmetrie-Anzeige, Worklight, Glanz, Kamera (Ansicht, Fokus, Ortho),
Referenz-Ghost, Texturen, die SubD-Vorschau und die Morph-Regler (Gewichte und aktuelles Ziel je Objekt, Manu
2026-11-16) sollen beim Öffnen einer gespeicherten Szene nicht neu
eingestellt werden müssen. Der Zustand reist in der Szenendatei unter dem optionalen Schlüssel `"view"`
(neben `objects`, `rig`, ...): `core.serialization` ignoriert unbekannte Schlüssel, das Core-Format
(Version, Vertrag) bleibt unverändert, und ältere Builds lesen die Datei weiter (sie verlieren nur die Ansicht).

Reiner Ansichts-Zustand: kein History-Eintrag, keine Mesh-Änderung. Nicht gespeichert werden Auswahl,
Hover, Gizmo-Größe, Maske/Hide (gehören zum Mesh der Sitzung) und die Look-Zeile der Pfeiltasten.
Eine Datei ohne `"view"` (oder mit einem kaputten Abschnitt) lässt die jeweilige Ansicht stehen -
jeder Abschnitt wird einzeln und defensiv gelesen, ein Fehler darin verhindert nie das Laden der Szene.

pyglet-frei; `capture(app)` liefert ein JSON-fähiges dict, `apply(app, view)` setzt es zurück.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

from viewport.light_rig import PRESETS, SPACE_CAMERA, SPACE_WORLD, LightRig
from viewport.material import SurfaceFinish

from core import LayerId

from .morph_targets import MAX_WEIGHT, MIN_WEIGHT, morph_target_ids
from .subdivision.preview import LEVELS, VIEW_ORDER
from .viewport.display import DisplayMode

#: Schlüssel in der Szenendatei.
VIEW_KEY = "view"
VIEW_VERSION = 1


# -- capture ------------------------------------------------------------------------------------


def capture(app) -> dict:
    """Der aktuelle Ansichts-Zustand von `app` als JSON-fähiges dict."""
    display = app.display
    camera = app.camera
    sym = app.symmetry_display
    subd = app.subdivision
    return {
        "version": VIEW_VERSION,
        "display": {
            "mode": display.mode.name,
            "wireframe_overlay": display.wireframe_overlay,
            "region_tint": display.region_tint,
            "show_texture": display.show_texture,
        },
        "light": {
            "preset": display.light_preset,
            "space": display.light_space,
            "edit": None if display.light_edit is None else display.light_edit.to_dict(),
        },
        "surface_finish": dataclasses.asdict(display.surface_finish),
        "symmetry_display": None if sym is None else bool(sym.visible),
        "reference_ghost": bool(app._objects.reference_ghost),
        "camera": {
            "target": list(camera.target),
            "distance": camera.distance,
            "yaw": camera.yaw,
            "pitch": camera.pitch,
            "fov_degrees": camera.fov_degrees,
            "ortho": bool(camera.ortho),
        },
        "subd": {
            "view": subd.view,
            "level": subd.level,
            "cage_depth_test": bool(subd.cage_depth_test),
            "secondary_strength": subd.secondary_strength,
            "lines_shown": bool(subd.lines_shown),
        },
        "morph": _capture_morph(app),
    }


def _capture_morph(app) -> dict:
    """The morph sliders: [object index, layer id, weight] of every existing target other than 0 % and [object index,
    layer id] of each object's current target. The object is its position in the file's `objects` list (a load gives
    the objects new ObjectIds in that order, `scene_objects.replace_scene`); LayerIds survive with the mesh."""
    provider = app.morph.provider
    objects = app._morph.document_scene().objects
    weights, current = [], []
    for index, (oid, obj) in enumerate(objects.items()):
        for lid, weight in sorted(provider.object_weights(oid).items(), key=lambda item: int(item[0])):
            weights.append([index, int(lid), int(weight)])
        if morph_target_ids(obj.mesh):
            lid = provider.current_target(oid)
            if lid is not None:
                current.append([index, int(lid)])
    return {"weights": weights, "current": current}


# -- apply --------------------------------------------------------------------------------------


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"not a finite number: {value!r}")
    return float(value)


def _flag(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"not a bool: {value!r}")
    return value


def apply(app, view: Any) -> list[str]:
    """Setzt den gespeicherten Ansichts-Zustand auf `app`. Gibt die Namen der Abschnitte zurück, die
    nicht gelesen werden konnten (leer = alles übernommen); `view` ohne dict-Form = nichts zu tun."""
    if not isinstance(view, dict):
        return []
    skipped: list[str] = []
    for name, section in (
        ("display", _apply_display),
        ("light", _apply_light),
        ("surface_finish", _apply_finish),
        ("camera", _apply_camera),
        ("subd", _apply_subd),
        ("symmetry_display", _apply_symmetry),
        ("reference_ghost", _apply_ghost),
        ("morph", _apply_morph),
    ):
        if name not in view:
            continue
        try:
            section(app, view[name])
        except (ValueError, TypeError, KeyError, AttributeError):
            skipped.append(name)
    app._apply_display()  # one push of mode, tint, light and finish to the viewport
    return skipped


def _apply_display(app, raw: dict) -> None:
    display = app.display
    mode = DisplayMode[raw["mode"]]
    wire = _flag(raw["wireframe_overlay"])
    tint = _flag(raw["region_tint"])
    texture = _flag(raw["show_texture"])
    display.set_mode(mode)
    display.set_wireframe_overlay(wire)
    display.region_tint = tint
    display.show_texture = texture
    app._objects.sync_views()  # the texture switch is read by the objects' views


def _apply_light(app, raw: dict) -> None:
    preset = raw["preset"]
    if preset not in PRESETS:
        raise ValueError(f"unknown light preset {preset!r}")
    space = raw["space"]
    if space not in (None, SPACE_CAMERA, SPACE_WORLD):
        raise ValueError(f"unknown light space {space!r}")
    edit = raw["edit"]
    rig = None
    if edit is not None:
        known = {f.name for f in dataclasses.fields(LightRig)}
        rig = LightRig(**{key: value for key, value in edit.items() if key in known})
    display = app.display
    display.light_preset = preset
    display.light_space = space
    display.light_edit = rig


def _apply_finish(app, raw: dict) -> None:
    known = {f.name for f in dataclasses.fields(SurfaceFinish)}
    values = {key: _number(raw[key]) for key in known if key in raw}
    app.display.surface_finish = SurfaceFinish(**values)


def _apply_camera(app, raw: dict) -> None:
    target = raw["target"]
    if not isinstance(target, (list, tuple)) or len(target) != 3:
        raise ValueError("camera target needs three numbers")
    target = tuple(_number(v) for v in target)
    distance = _number(raw["distance"])
    yaw = _number(raw["yaw"])
    pitch = _number(raw["pitch"])
    fov = _number(raw["fov_degrees"])
    ortho = _flag(raw["ortho"])
    if distance <= 0.0 or not 1.0 <= fov < 180.0:
        raise ValueError("camera distance / fov out of range")
    camera = app.camera
    camera.target = target
    camera.distance = max(0.5, min(200.0, distance))  # the range `OrbitCamera.dolly` keeps
    camera.yaw = yaw
    camera.pitch = pitch
    camera.fov_degrees = fov
    camera.ortho = ortho
    camera.camera_revision += 1
    app.restore_camera_state()


def _apply_subd(app, raw: dict) -> None:
    view = raw["view"]
    level = raw["level"]
    if view not in VIEW_ORDER:
        raise ValueError(f"unknown SubD view {view!r}")
    if isinstance(level, bool) or level not in LEVELS:
        raise ValueError(f"unknown SubD level {level!r}")
    depth = _flag(raw["cage_depth_test"])
    strength = _number(raw["secondary_strength"])
    lines = _flag(raw["lines_shown"])
    subd = app.subdivision
    subd.provider.set_level(level)  # a refused level (face limit) keeps the current one
    subd.cage_depth_test = depth
    subd.secondary_strength = max(0.0, min(1.0, strength))
    subd.lines.configure(lines_shown=lines)
    subd.set_view(view)


def _apply_symmetry(app, raw: Any) -> None:
    display = app.symmetry_display
    if raw is None or display is None:
        return
    display.visible = _flag(raw)


def _apply_ghost(app, raw: Any) -> None:
    controller = app._objects
    controller.reference_ghost = _flag(raw)
    controller.sync_views()


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"not an int: {value!r}")
    return value


def _apply_morph(app, raw: dict) -> None:
    """Puts the saved sliders back. Entries for an object or target the scene does not have are left out; a malformed
    entry makes the whole section skipped (nothing set)."""
    objects = list(app.scene.objects.values())  # the file's order (`replace_scene`)
    weights, current = [], []
    for entry in raw.get("weights", []):
        index, lid, weight = (_int(v) for v in entry)
        weights.append((index, LayerId(lid), max(MIN_WEIGHT, min(MAX_WEIGHT, weight))))
    for entry in raw.get("current", []):
        index, lid = (_int(v) for v in entry)
        current.append((index, LayerId(lid)))

    def alive(index, lid):
        """The object at `index` when it has the target `lid`, else None."""
        if not 0 <= index < len(objects):
            return None
        obj = objects[index]
        return obj.id if lid in morph_target_ids(obj.mesh) else None

    provider = app.morph.provider
    for index, lid, weight in weights:
        oid = alive(index, lid)
        if oid is not None:
            provider.set_weight(oid, weight, lid)
    for index, lid in current:
        oid = alive(index, lid)
        if oid is not None:
            provider.set_current(oid, lid)
    app.morph.refresh()
