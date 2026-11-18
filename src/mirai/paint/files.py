"""Paint layers on disk (AD-037 §3.3; audit 2026-11-18 P-4, Phase 1d). Stdlib + NumPy (the PNG codec of
`mirai.iris_import`), the file rules of `mirai.texture_files`.

**Where.** Every layer image and the flattened image live in the scene's `<stem>_textures/` folder under their content
name (`texture_files.hashed_name`; the same pixels = the same file, nothing is overwritten or deleted). A scene file
stores them scene-relative like `SceneObject.texture` (`texture_files.to_file` / `resolve`); in memory a layer path is
absolute. A layer image outside that folder (after "Save as" elsewhere) is copied into it.

**What a save writes** (`prepare_save`, then `PaintSave.apply` once the scene file is written):
- a layer whose pixels are in memory and differ from their file (`PaintStore.is_dirty`): a new PNG - unless the layer is
  fully transparent, which needs no file (`image = None`);
- a loaded, unchanged layer: the file its pixels came from (`PaintStore.source`) - so a stack value an Undo brought back
  with an older path is written with the right one;
- a layer never loaded: its path as it is (the pixels are that file);
- per painted object one **flattened** PNG (P-4): the base texture (or the base colour) with every visible layer
  composited, RGB, for OBJ / GoZ / any other tool. Written when a layer was written or no flat image exists yet; the
  status line names it. The Core does not store it (derived data).

**Pixels.** PNG rows are top first, the store's rows are v = 0 first (`mirai.paint.texel_map`): one flip on each read and
write. 8 bit RGBA for layers; the base is read as the viewport reads it (`iris_import.read_rgba`) and resampled nearest
to the stack size when it differs.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from core import PaintStack, SceneObject
from viewport.gl_render_store import DEFAULT_BASE_COLOR

from .. import texture_files
from ..iris_import import decode_png, encode_png, read_rgba
from ..scene_objects import object_base_color
from .store import PaintStore


#: zlib level of the paint PNGs (reference PC 2026-11-18, P-F 7.4 / 9.4 s): level 1 encodes a textured 2048² image in
#: about a quarter of level 6's time for ~1.6x the bytes - a save is frequent, the files are local.
PNG_LEVEL = 1


#: Decoded images by (path, modification time, size): the reference PC read the 2048² ZBrush texture in 6.35 s
#: (2026-11-18, P-F "read base"; the container 0.04 s), so the room, the save's flattened image and the eyedropper read it
#: once per session. A changed file has another stamp; at most `_CACHE_SIZE` images are kept.
_CACHE: dict[tuple, np.ndarray] = {}
_CACHE_SIZE = 4
#: how the last uncached `read_image` went: path, decoder ("own" / "system"), seconds for the file read and the decode
last_read: dict = {}


def clear_image_cache() -> None:
    _CACHE.clear()


def read_image(path: str) -> np.ndarray:
    """(h, w, 4) uint8 RGBA, top row first, read-only (cached, see `_CACHE`): a PNG through the own decoder (pyglet's
    pure-Python PNG path took 1.8 s for the 2048² ZBrush texture in the container, the own one 0.13 s), anything else
    through `iris_import.read_rgba`."""
    import time

    stat = os.stat(path)
    key = (os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    started = time.perf_counter()
    data = Path(path).read_bytes()
    read = time.perf_counter() - started
    try:
        rgba, decoder = decode_png(data, slow=False), "own"
    except ValueError as exc:
        # not a PNG the own decoder reads fast (AD-037 §10.8c: Paeth rows 6.5 s on the reference PC): the system's decoder
        # (pyglet: WIC on Windows), which itself falls back to the own one when it cannot
        rgba, decoder = read_rgba(path), f"system ({exc})"
    last_read.clear()
    last_read.update(path=str(path), bytes=len(data), decoder=decoder, read_s=read,
                     decode_s=time.perf_counter() - started - read)
    rgba.setflags(write=False)
    while len(_CACHE) >= _CACHE_SIZE:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = rgba
    return rgba


def read_layer(path: str) -> np.ndarray:
    """A layer image as (h, w, 4) uint8 RGBA, row 0 = v = 0. `OSError` / `ValueError`."""
    return np.ascontiguousarray(read_image(path)[::-1])


def encode_layer(rgba: np.ndarray) -> bytes:
    return encode_png(rgba[::-1], PNG_LEVEL)


def read_base(obj: SceneObject, width: int, height: int) -> np.ndarray | tuple[float, float, float]:
    """The base under the layers (P-4): the object's texture at the stack size (row 0 = v = 0), or its base colour when
    it has none or it cannot be read."""
    if obj.texture is not None:
        try:
            rgba = read_image(obj.texture)[::-1]
        except (OSError, ValueError):
            rgba = None
        if rgba is not None:
            h, w = rgba.shape[:2]
            if (w, h) != (width, height):
                ys = (np.arange(height) * h) // height
                xs = (np.arange(width) * w) // width
                rgba = rgba[ys][:, xs]
            return np.ascontiguousarray(rgba)
    return object_base_color(obj) or DEFAULT_BASE_COLOR


def flatten(store: PaintStore, obj: SceneObject) -> np.ndarray:
    """The object's composite (base + visible layers), (h, w, 4) uint8, row 0 = v = 0."""
    stack = obj.paint
    return store.composite(obj, read_base(obj, stack.width, stack.height))


def _stem(obj: SceneObject, layer: str) -> str:
    return texture_files.clean_stem(f"{obj.name}_{layer}")


@dataclass
class PaintSave:
    """What a save will change: {object: its stack with the written paths}, the store's new sources, the flat images."""

    stacks: dict[int, tuple[SceneObject, PaintStack]] = field(default_factory=dict)
    sources: list[tuple[SceneObject, str, str | None]] = field(default_factory=list)
    flats: dict[int, str] = field(default_factory=dict)
    written: int = 0

    def apply(self, store: PaintStore) -> None:
        """After the scene file is written: the objects point at the written files (no Undo step: the same pixels)."""
        for obj, stack in self.stacks.values():
            obj.paint = stack
        for obj, name, source in self.sources:
            store.mark_saved(obj, name, source)

    def file_stack(self, obj_id: int, scene_dir: Path) -> dict | None:
        """The stack's dict for the scene file: paths scene-relative where they lie below the scene folder."""
        entry = self.stacks.get(obj_id)
        if entry is None:
            return None
        data = entry[1].to_dict()
        for layer in data["layers"]:
            if layer["image"] is not None:
                layer["image"] = texture_files.to_file(layer["image"], scene_dir)
        return data


def prepare_save(objects, store: PaintStore, scene_path: str | Path) -> PaintSave:
    """Writes the PNG files a save of `objects` (a scene's objects, `document_scene()`) needs into the scene's
    `<stem>_textures/` and returns the `PaintSave` (module docstring). `OSError` when a file cannot be written: nothing
    in memory has changed then."""
    directory = texture_files.scene_texture_dir(scene_path)
    plan = PaintSave()
    for obj in objects:
        stack = obj.paint
        if stack is None:
            continue
        layers, wrote = [], False
        for spec in stack.layers:
            image = spec.image
            if store.loaded(obj, spec.name):
                if store.is_dirty(obj, spec.name):
                    rgba = store.pixels(obj, spec.name)
                    if not rgba[..., 3].any():
                        image = None  # transparent: no file needed
                    else:
                        data = encode_layer(rgba)
                        image = str(texture_files.store(data, directory, texture_files.hashed_name(
                            _stem(obj, spec.name), data, ".png")))
                        plan.written += 1
                        wrote = True
                else:
                    image = store.source(obj, spec.name)
            if image is not None and not texture_files.inside(image, directory) and os.path.isfile(image):
                image = str(texture_files.copy_into(image, directory))  # "Save as" elsewhere: the folder stays whole
            if store.loaded(obj, spec.name):
                plan.sources.append((obj, spec.name, image))
            layers.append(dataclasses.replace(spec, image=image))
        plan.stacks[int(obj.id)] = (obj, dataclasses.replace(stack, layers=tuple(layers)))
        flat_name = texture_files.clean_stem(f"{obj.name}_paint_flat")
        has_flat = directory.is_dir() and any(p.name.startswith(flat_name + "_") for p in directory.iterdir())
        if wrote or not has_flat:
            data = encode_png(flatten(store, obj)[::-1], PNG_LEVEL)
            plan.flats[int(obj.id)] = str(texture_files.store(data, directory, texture_files.hashed_name(
                flat_name, data, ".png")))
    return plan


def resolve_stack(stack: PaintStack, scene_dir: str | Path) -> PaintStack:
    """A stack as read from a scene file in `scene_dir`: every layer path absolute (`texture_files.resolve`)."""
    return dataclasses.replace(stack, layers=tuple(
        layer if layer.image is None else dataclasses.replace(layer, image=texture_files.resolve(layer.image, scene_dir))
        for layer in stack.layers))
