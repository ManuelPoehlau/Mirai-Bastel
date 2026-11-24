"""The organic LookDev material's presets and value rules (AD-038 §7, §18).

Since LD-2 (2026-11-21) the value itself is the Core type `core.LookMaterial` on `SceneObject.look` (saved with the
scene, format v15; changed by `ObjectLookCommand`, one Undo step). This module keeps what is `src/mirai`'s: the presets,
the Neutral fallback, F0 from the level and the "angepasst" rule (`with_values`). Since AD-039 S7 (2026-11-24) a
material may carry image maps (`core.LookMaps`, `LookMaterial.maps`; format v16): `with_map` sets or removes one, the
normal map's values go through `with_values` (`MAP_VALUES`, never "angepasst": the maps are not preset values), and a
preset pick keeps the maps (`keep_maps`), like an eye preset keeps its images. Since AD-039 S6 (2026-11-24) an object
may carry region materials (`core.RegionLook`, `SceneObject.look_regions`; format v17): `with_region` sets, adds or
removes one (at most `LOOK_REGIONS_MAX`, a new one last: the later entry wins on overlap), `moved_region` changes the
order, `renamed_region` carries an entry with its region's rename; a region's material carries no maps (the maps are the
object's, one UV layout: `region_material`).

`LookMaterial` is one value bundle of the one organic shading model (`viewport.lookdev_pass`, proposal §4): an sRGB
artist colour, where the albedo comes from (`texture`: the object's shown texture or paint composite; `color`: the
colour), perceptual roughness (alpha = r²), the specular *level* (F0 = 0.08 x level; 0.5 -> 0.04), the diffuse wrap
(softness; the preset fixes its per-channel tint) and the backscatter with its colour.

Six presets (`PRESETS`, values `PROVISIONAL`, tuned in the M1 practical test). An object without a look (`SceneObject.look is None`) is drawn
**Neutral** (Manu 2026-11-19, AD-038 §15 Q3): nothing is guessed from object names. Its albedo is then the shown texture
or paint composite when it has UVs and one, else `ObjectMaterial.base_color` read as a colour only, else the Worklight's
`DEFAULT_BASE_COLOR`; `glossiness` is never read as roughness, nor `specular` as F0 (proposal §4.3).
"""

from __future__ import annotations

import dataclasses

from core import LookMaps, LookMaterial, RegionLook
from core.scene import LOOK_ALBEDO_SOURCES as ALBEDO_SOURCES
from core.scene import LOOK_MAP_FIELDS, LOOK_REGIONS_MAX

#: AD-039 §10: the map values `with_values` takes (they change `LookMaterial.maps`, and only when it has maps).
MAP_VALUES = ("normal_strength", "normal_green_down")


def f0(material: LookMaterial) -> float:
    """The specular level as F0 (0.5 -> 0.04)."""
    return 0.08 * material.specular


def wrap_rgb(material: LookMaterial) -> tuple[float, float, float]:
    return tuple(material.wrap * t for t in material.wrap_tint)


def with_values(material: LookMaterial, **changes) -> LookMaterial:
    """A copy with `changes`; a value change marks it "angepasst" (the preset name stays). `MAP_VALUES` change the
    maps (a material without maps keeps none) and do not mark it."""
    map_changes = {k: changes.pop(k) for k in MAP_VALUES if k in changes}
    if map_changes and material.maps is not None:
        material = dataclasses.replace(material, maps=dataclasses.replace(material.maps, **map_changes))
    values = {k: v for k, v in changes.items() if k not in ("preset", "adjusted")}
    for name in ("base_color", "wrap_tint", "backscatter_color"):
        if name in values:
            values[name] = tuple(float(c) for c in values[name])
    adjusted = material.adjusted or any(getattr(material, k) != v for k, v in values.items())
    adjusted = changes.get("adjusted", adjusted)
    if "preset" in changes:
        values["preset"] = changes["preset"]
    return dataclasses.replace(material, **values, adjusted=adjusted)


def with_map(material: LookMaterial, kind: str, path: str | None) -> LookMaterial:
    """A copy whose `kind` map ("roughness" / "normal" / "translucency") is `path` (None removes it; without any map
    left `maps` is None again, the v15 material)."""
    if kind not in LOOK_MAP_FIELDS:
        raise ValueError(f"LookDev map: one of {', '.join(LOOK_MAP_FIELDS)}, not {kind!r}")
    maps = material.maps
    if maps is None:
        if path is None:
            return material
        return dataclasses.replace(material, maps=LookMaps(**{kind: path}))
    paths = {name: getattr(maps, name) for name in LOOK_MAP_FIELDS} | {kind: path}
    if all(value is None for value in paths.values()):
        return dataclasses.replace(material, maps=None)
    return dataclasses.replace(material, maps=dataclasses.replace(maps, **{kind: path}))


def keep_maps(material: LookMaterial, before: LookMaterial | None) -> LookMaterial:
    """A picked preset with the maps the object had (a preset has none)."""
    maps = before.maps if before is not None else None
    return material if maps is None else dataclasses.replace(material, maps=maps)


def region_material(material: LookMaterial) -> LookMaterial:
    """A material as a region's (AD-039 §9): without maps - the maps are the object's (one UV layout), the region
    draws the object's maps with its own values."""
    return material if material.maps is None else dataclasses.replace(material, maps=None)


def with_region(regions: tuple, name: str, material: LookMaterial | None) -> tuple:
    """`regions` (`SceneObject.look_regions`) with region `name`'s material set (in its place), added (last: it wins
    on overlap) or removed (`material` None). ValueError when a fifth one would be added."""
    entries = list(regions)
    index = next((i for i, entry in enumerate(entries) if entry.region == name), None)
    if material is None:
        return tuple(entries) if index is None else tuple(entries[:index] + entries[index + 1:])
    entry = RegionLook(name, region_material(material))
    if index is not None:
        entries[index] = entry
    elif len(entries) >= LOOK_REGIONS_MAX:
        raise ValueError(f"LookDev: höchstens {LOOK_REGIONS_MAX} Region-Materialien je Objekt")
    else:
        entries.append(entry)
    return tuple(entries)


def moved_region(regions: tuple, name: str, step: int) -> tuple:
    """`regions` with `name`'s entry moved `step` places (-1 = up: drawn under the next ones, +1 = down: over them);
    clamped at the ends, unchanged when `name` has no entry."""
    entries = list(regions)
    index = next((i for i, entry in enumerate(entries) if entry.region == name), None)
    if index is None:
        return tuple(entries)
    target = max(0, min(len(entries) - 1, index + int(step)))
    entries.insert(target, entries.pop(index))
    return tuple(entries)


def renamed_region(regions: tuple, old: str, new: str) -> tuple:
    """`regions` after region `old` became `new` (AD-039 §9: a rename carries its entry). An entry already under `new`
    (the name was free in the mesh, so it was a missing region's) gives way to the carried one."""
    if not any(entry.region == old for entry in regions):
        return tuple(regions)
    return tuple(RegionLook(new, entry.look) if entry.region == old else entry
                 for entry in regions if entry.region != new)


NEUTRAL = "Neutral"
#: The six presets (proposal §4.1; `PROVISIONAL`). Creature Skin is the Gollum candidate; Neutral the fallback (clay).
PRESETS: dict[str, LookMaterial] = {
    "Creature Skin": LookMaterial("Creature Skin", (0.62, 0.52, 0.44), "texture", roughness=0.5, specular=0.35,
                                  wrap=0.3, wrap_tint=(1.0, 0.65, 0.5), backscatter=0.15,
                                  backscatter_color=(1.0, 0.45, 0.3)),
    "Wet Skin": LookMaterial("Wet Skin", (0.62, 0.45, 0.42), "texture", roughness=0.25, specular=0.35, wrap=0.3,
                             wrap_tint=(1.0, 0.65, 0.5), backscatter=0.1, backscatter_color=(1.0, 0.45, 0.3)),
    "Zähne": LookMaterial("Zähne", (0.85, 0.80, 0.68), "color", roughness=0.3, specular=0.5, wrap=0.1,
                          wrap_tint=(1.0, 0.9, 0.8), backscatter=0.1, backscatter_color=(1.0, 0.8, 0.6)),
    "Mundinneres": LookMaterial("Mundinneres", (0.55, 0.22, 0.22), "texture", roughness=0.3, specular=0.35, wrap=0.5,
                                wrap_tint=(1.0, 0.5, 0.45), backscatter=0.3, backscatter_color=(1.0, 0.3, 0.25)),
    "Organisch": LookMaterial("Organisch", (0.6, 0.55, 0.5), "texture", roughness=0.55, specular=0.5, wrap=0.1),
    NEUTRAL: LookMaterial(NEUTRAL, (0.5, 0.5, 0.5), "texture", roughness=0.6, specular=0.5),
}
PRESET_NAMES = tuple(PRESETS)


def preset(name: str) -> LookMaterial:
    try:
        return PRESETS[name]
    except KeyError:
        raise ValueError(f"LookDev material: no preset {name!r} ({', '.join(PRESET_NAMES)})") from None


def fallback(base_color: tuple[float, float, float] | None, default: tuple[float, float, float]) -> LookMaterial:
    """Neutral for an object without a look: its `ObjectMaterial.base_color` as the colour (else `default`)."""
    colour = tuple(float(c) for c in (base_color if base_color is not None else default))
    return dataclasses.replace(PRESETS[NEUTRAL], base_color=colour)
