"""Likeness cameras in the scene file (Manu 2026-11-27: Q-LC-3, LC-D2 „C jetzt, A später“, LC-D9 „Kopie in
<Szene>_photos/“; AD-042 §17.7).

The cameras ride in the view section (`view.likeness`, `mirai.view_state`): no Core field, no format version. A file
without the section has no cameras; every scene replacement empties the session first. An older build reads the file
and drops the section when it saves (the `view.lookdev` rule). No Undo (view state). Later (M3, LC-D2 A) they become
camera objects in the Core; this section is then read once more and converted.

Photos (LC-D9): on save the photo's source file is copied byte for byte into `<scene stem>_photos/` beside the scene
under its content name (`texture_files.copy_into`; never overwrites, never deletes) - a folder `.gitignore` excludes
(`scenes/**/*_photos/`), so photos of real people never reach the public repository. The file stores the copy
scene-relative plus the quarter turns („90° drehen“); the source is read again on load (and capped). A source that is
gone by the time of the save is written from memory as a PNG (the capped, turned pixels; 0 turns). A photo missing on
load keeps its path (`LikenessCamera.photo_missing`) and is written again on the next save.

pyglet-free except through `paint.library.read_image_rgba` (pyglet only for a non-PNG file).
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path
from typing import Any

import numpy as np

from . import texture_files
from .likeness import LikenessCamera, LikenessPhoto
from .viewport import lens as lens_math

SECTION = "likeness"
FORMAT = 1
PHOTO_MAX_PX = 4096  # the photo's longer side after the cap (an integer box factor, AD-042 E4)
PHOTO_MIN_PX = 16
NAME_LIMIT = 40
CLIP_RANGE = (0.001, 100_000.0)
SENSOR_SIDE_MM = (1.0, 100.0)


def photo_dir(scene_path: str | Path) -> Path:
    """`<scene stem>_photos/` beside the scene file (git-ignored, LC-D9)."""
    scene = Path(scene_path)
    return scene.parent / f"{texture_files.scene_stem(scene)}_photos"


def read_photo(path: str | Path, turns: int, serial: int) -> LikenessPhoto:
    """Read, cap and turn a photo file. `OSError` / `ValueError` (and pyglet's decoder errors) when it cannot."""
    from .paint.library import read_image_rgba, reduce_rgba

    path = Path(path)
    rgba = read_image_rgba(path)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("kein RGBA-Bild")
    source = (int(rgba.shape[1]), int(rgba.shape[0]))
    if min(source) < PHOTO_MIN_PX:
        raise ValueError(f"kleiner als {PHOTO_MIN_PX} px")
    rgba = np.ascontiguousarray(reduce_rgba(rgba, PHOTO_MAX_PX), dtype=np.uint8)
    turns %= 4
    if turns:
        rgba = np.ascontiguousarray(np.rot90(rgba, k=-turns))
        if turns % 2:
            source = (source[1], source[0])
    return LikenessPhoto(path=path, rgba=rgba, source_size=source, serial=serial, turns=turns)


# -- save --------------------------------------------------------------------------------------------------------

def prepare_save(session, scene_path: Path) -> tuple[dict, dict[int, Path]]:
    """The file section for `session` and {camera index: the photo's copy}. The copies are written here (before the
    scene file; `OSError` = the caller writes nothing). The caller points each photo at its copy after the file is
    written."""
    directory = photo_dir(scene_path)
    scene_dir = Path(scene_path).parent
    copies: dict[int, Path] = {}
    cameras = []
    for index, cam in enumerate(session.cameras):
        photo = None
        if cam.photo is not None:
            source = cam.photo.path
            turns = cam.photo.turns
            if texture_files.inside(source, directory) and source.is_file():
                copy = source
            elif source.is_file():
                copy = texture_files.copy_into(source, directory)
            else:  # the source is gone: the pixels in memory (capped, already turned)
                from .iris_import import encode_png

                data = encode_png(cam.photo.rgba)
                copy = texture_files.store(data, directory, texture_files.hashed_name(source.stem, data, ".png"))
                turns = 0
            copies[index] = copy
            photo = {"file": texture_files.to_file(str(copy), scene_dir), "turns": turns}
        elif cam.photo_missing is not None:
            missing, turns = cam.photo_missing
            photo = {"file": texture_files.to_file(missing, scene_dir), "turns": turns}
        lens = cam.lens
        cameras.append({
            "name": cam.name,
            "target": list(cam.target), "distance": cam.distance, "yaw": cam.yaw, "pitch": cam.pitch,
            "lens": {"focal_mm": lens.focal_mm, "sensor": lens.sensor, "sensor_w_mm": lens.sensor_w_mm,
                     "sensor_h_mm": lens.sensor_h_mm, "fit": lens.fit},
            "clip_near": cam.clip_near, "clip_far": cam.clip_far, "fixed": bool(cam.fixed),
            "photo": photo,
        })
    section = {"format": FORMAT, "cameras": cameras, "active": session.active, "overscan": session.overscan,
               "photo_opacity": session.photo_opacity, "photo_shown": bool(session.photo_shown)}
    return section, copies


# -- load --------------------------------------------------------------------------------------------------------

def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"not a number: {value!r}")
    return float(value)


def _lens(raw: dict) -> lens_math.Lens:
    sensor = raw["sensor"]
    if sensor not in lens_math.SENSOR_KEYS:
        raise ValueError(f"unknown sensor {sensor!r}")
    if raw["fit"] not in lens_math.FITS:
        raise ValueError(f"unknown fit {raw['fit']!r}")
    lo, hi = lens_math.FOCAL_RANGE_MM
    side = lambda v: max(SENSOR_SIDE_MM[0], min(SENSOR_SIDE_MM[1], _number(v)))  # noqa: E731
    return lens_math.Lens(focal_mm=max(lo, min(hi, _number(raw["focal_mm"]))), sensor=sensor,
                          sensor_w_mm=side(raw["sensor_w_mm"]), sensor_h_mm=side(raw["sensor_h_mm"]), fit=raw["fit"])


def parse(raw: Any, scene_dir: Path) -> tuple[list[tuple[LikenessCamera, tuple[str, int] | None]], dict]:
    """The section as [(camera without photo, (absolute photo path, turns) or None)] and the session values. Raises
    `ValueError` / `TypeError` / `KeyError` on a broken section (the caller then keeps no camera)."""
    if not isinstance(raw, dict) or not isinstance(raw.get("cameras"), list):
        raise ValueError("likeness section needs a camera list")
    out = []
    for item in raw["cameras"]:
        name = str(item["name"]).strip()[:NAME_LIMIT] or "Kamera"
        target = item["target"]
        if not isinstance(target, (list, tuple)) or len(target) != 3:
            raise ValueError("camera target needs three numbers")
        distance = _number(item["distance"])
        if distance <= 0.0:
            raise ValueError("camera distance must be > 0")
        near, far = _number(item["clip_near"]), _number(item["clip_far"])
        if not CLIP_RANGE[0] <= near < far <= CLIP_RANGE[1]:
            raise ValueError("camera clip out of range")
        cam = LikenessCamera(name=name, target=tuple(_number(c) for c in target), distance=distance,
                             yaw=_number(item["yaw"]), pitch=_number(item["pitch"]), lens=_lens(item["lens"]),
                             clip_near=near, clip_far=far, fixed=bool(item.get("fixed", False)))
        photo = item.get("photo")
        wanted = None
        if photo is not None:
            turns = int(_number(photo.get("turns", 0))) % 4
            wanted = (texture_files.resolve(str(photo["file"]), scene_dir), turns)
        out.append((cam, wanted))
    lo, hi = lens_math.OVERSCAN_RANGE
    values = {
        "active": raw.get("active"),
        "overscan": max(lo, min(hi, _number(raw.get("overscan", lens_math.OVERSCAN_DEFAULT)))),
        "photo_opacity": max(0.0, min(1.0, _number(raw.get("photo_opacity", 1.0)))),
        "photo_shown": bool(raw.get("photo_shown", True)),
    }
    active = values["active"]
    if isinstance(active, bool) or not isinstance(active, int) or not 0 <= active < len(out):
        values["active"] = (len(out) - 1) if out else None
    return out, values


def pointed_at(photo: LikenessPhoto, copy: Path) -> LikenessPhoto:
    """The photo read from its copy from now on (the same pixels)."""
    return dataclasses.replace(photo, path=Path(copy))
