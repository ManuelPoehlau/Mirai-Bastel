"""The CPU-authoritative pixels of every painted object (AD-037 §4, audit 2026-11-18 §4.2 principles 1, 4, 6; Phase 1d).

The document value is `SceneObject.paint` (`core.scene.PaintStack`: layer names, image paths, opacity, visibility); the
pixels of its layers live here, in NumPy, until a save writes them as PNG (`mirai.paint.files`). The GPU only ever gets
copies (`viewport.live_texture`, Phase 1c), so painting, Undo and saving never read pixels back.

**Keys.** Pixels belong to an object *instance* and a layer name (unique in its stack): the commands that delete and
restore an object keep the instance, so its pixels survive delete / Undo, and a copy (Duplicate, mirror copy, Detach)
takes the source's current pixels (`copy_object`), not the last saved file. `SceneObject` has `__slots__` without a weak
reference, so the store holds the instance (cleared on a scene reset, `clear`). A layer whose pixels were never loaded
is read from its image on first use (`None` image = transparent); a file that cannot be read loads transparent, is
reported once (`missing`) and keeps its path until it is painted.

**Layout.** One `(height, width, 4)` uint8 RGBA array per layer, row 0 = v = 0 (the texel map's and GL's order,
`mirai.paint.texel_map`). Changes are tracked per `TILE` x `TILE` tile: `take_changed` hands the tiles changed since the
last call to whoever shows the composite, `dirty` names the layers a save has to write.

**Strokes.** `begin_stroke` returns a `StrokeRecorder`: it captures a tile's pixels the first time the stroke touches it
(compressed), `commit()` turns that into one `PaintStrokeCommand` (one Undo step per stroke), `cancel()` puts every
touched tile back exactly (Esc). The command keeps only the "before" tiles until its first Undo captures the "after"
ones (audit §8.4 item 5: about 0.2-0.7 MiB raw per stroke, a fraction of that compressed).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field

import numpy as np

from core import PaintStack, SceneObject

#: Tile side in pixels (audit §8.1: a 40-dab stroke at 1-10 % radius touches 11-44 tiles at 2048²).
TILE = 64


class PaintError(ValueError):
    """A paint request that cannot be served (wrong size, unknown layer); the app shows it in the status line."""


def blank(width: int, height: int) -> np.ndarray:
    return np.zeros((height, width, 4), dtype=np.uint8)


@dataclass
class _Layer:
    rgba: np.ndarray
    #: the image file these pixels equal (None = blank, never written); read and set by `mirai.paint.files`
    source: str | None = None
    #: True when the pixels differ from `source` (a save writes them)
    dirty: bool = False


@dataclass
class _ObjectPaint:
    obj: SceneObject
    size: tuple[int, int]
    layers: dict[str, _Layer] = field(default_factory=dict)
    changed: set[tuple[int, int]] = field(default_factory=set)


def tiles_of(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """The tiles a pixel box [x0, x1) x [y0, y1) touches, as (tile x, tile y)."""
    if x1 <= x0 or y1 <= y0:
        return []
    return [(tx, ty) for ty in range(y0 // TILE, (y1 - 1) // TILE + 1) for tx in range(x0 // TILE, (x1 - 1) // TILE + 1)]


def tile_box(tile: tuple[int, int], width: int, height: int) -> tuple[int, int, int, int]:
    tx, ty = tile
    return tx * TILE, ty * TILE, min((tx + 1) * TILE, width), min((ty + 1) * TILE, height)


class PaintStore:
    """Pixels per painted object instance (module docstring). `loader(path) -> (h, w, 4) uint8 RGBA in GL row order`
    reads a layer image (`mirai.paint.files.read_layer`); injected so the store has no file dependency in tests."""

    def __init__(self, loader=None) -> None:
        self._objects: dict[int, _ObjectPaint] = {}
        self._loader = loader
        self.missing: set[str] = set()

    # -- objects -------------------------------------------------------------------------------------------------

    def clear(self) -> None:
        """A scene reset: every object is new."""
        self._objects.clear()
        self.missing.clear()

    def _entry(self, obj: SceneObject) -> _ObjectPaint:
        stack = obj.paint
        if stack is None:
            raise PaintError(f"{obj.name!r} has no paint")
        size = (stack.width, stack.height)
        entry = self._objects.get(id(obj))
        if entry is None or entry.obj is not obj or entry.size != size:
            entry = _ObjectPaint(obj, size)  # a new stack size: its old pixels cannot be reused
            self._objects[id(obj)] = entry
        return entry  # pixels of a layer that left the stack stay: an Undo can bring the layer back

    def _layer(self, obj: SceneObject, name: str) -> _Layer:
        entry = self._entry(obj)
        layer = entry.layers.get(name)
        if layer is None:
            spec = next((layer for layer in obj.paint.layers if layer.name == name), None)
            if spec is None:
                raise PaintError(f"{obj.name!r} has no paint layer {name!r}")
            layer = _Layer(self._load(spec.image, entry.size), spec.image)
            entry.layers[name] = layer
        return layer

    def _load(self, image: str | None, size: tuple[int, int]) -> np.ndarray:
        width, height = size
        if image is None or self._loader is None:
            return blank(width, height)
        try:
            rgba = self._loader(image)
        except (OSError, ValueError):
            self.missing.add(image)
            return blank(width, height)
        if rgba.shape != (height, width, 4):
            raise PaintError(f"paint layer image {image!r} is {rgba.shape[1]} x {rgba.shape[0]},"
                             f" the stack is {width} x {height}")
        return np.ascontiguousarray(rgba, dtype=np.uint8)

    def pixels(self, obj: SceneObject, name: str) -> np.ndarray:
        """The layer's pixels (the array itself: read it, write only through a `StrokeRecorder`)."""
        return self._layer(obj, name).rgba

    def loaded(self, obj: SceneObject, name: str) -> bool:
        """True when the layer's pixels are in memory (else they are its image file)."""
        entry = self._objects.get(id(obj))
        return entry is not None and entry.obj is obj and entry.size == (obj.paint.width, obj.paint.height) \
            and name in entry.layers

    def is_dirty(self, obj: SceneObject, name: str) -> bool:
        return self.loaded(obj, name) and self._layer(obj, name).dirty

    def source(self, obj: SceneObject, name: str) -> str | None:
        """The image file the loaded pixels equal (None = blank, never written)."""
        return self._layer(obj, name).source

    def mark_saved(self, obj: SceneObject, name: str, source: str | None) -> None:
        layer = self._layer(obj, name)
        layer.source, layer.dirty = source, False

    def set_pixels(self, obj: SceneObject, name: str, rgba: np.ndarray, *, dirty: bool = True) -> None:
        """Replaces a layer's pixels as a whole (a new layer from an image, a UV transfer later); no Undo here."""
        entry = self._entry(obj)
        width, height = entry.size
        if rgba.shape != (height, width, 4):
            raise PaintError(f"pixels are {rgba.shape}, the stack is {width} x {height}")
        source = self._layer(obj, name).source
        entry.layers[name] = _Layer(np.ascontiguousarray(rgba, dtype=np.uint8).copy(), source, dirty)
        entry.changed.update(tiles_of(0, 0, width, height))

    def copy_object(self, source: SceneObject, target: SceneObject) -> None:
        """`target` (a copy of `source` with the same stack) starts with `source`'s current pixels."""
        if source.paint is None or target.paint is None:
            return
        src = self._objects.get(id(source))
        if src is None or src.obj is not source:
            return  # nothing loaded: both read the same files
        entry = self._entry(target)
        if entry.size != src.size:
            return
        for name, layer in src.layers.items():
            entry.layers[name] = _Layer(layer.rgba.copy(), layer.source, layer.dirty)
        entry.changed.update(tiles_of(0, 0, *entry.size))

    def same_paint(self, a: SceneObject, b: SceneObject) -> bool:
        """True when `a` and `b` show the same paint: equal stacks and, where either has pixels in memory, equal pixels
        (a part detached and painted on its own has the same stack value and other pixels). Both without paint: True."""
        if a.paint != b.paint:
            return False
        if a.paint is None:
            return True
        for spec in a.paint.layers:
            if self.loaded(a, spec.name) or self.loaded(b, spec.name):
                if not np.array_equal(self.pixels(a, spec.name), self.pixels(b, spec.name)):
                    return False
        return True

    def take_changed(self, obj: SceneObject) -> set[tuple[int, int]]:
        """The tiles whose composite changed since the last call (for the live texture)."""
        entry = self._objects.get(id(obj))
        if entry is None or entry.obj is not obj:
            return set()
        out, entry.changed = entry.changed, set()
        return out

    def _touched(self, obj: SceneObject, name: str, tiles) -> None:
        entry = self._entry(obj)
        entry.layers[name].dirty = True
        entry.changed.update(tiles)

    # -- strokes -------------------------------------------------------------------------------------------------

    def begin_stroke(self, obj: SceneObject, name: str, description: str = "Paint stroke") -> "StrokeRecorder":
        self._layer(obj, name)
        return StrokeRecorder(self, obj, name, description)

    # -- composite -----------------------------------------------------------------------------------------------

    def composite(self, obj: SceneObject, base: np.ndarray, box: tuple[int, int, int, int] | None = None) -> np.ndarray:
        """The visible layers over `base` ((h, w, 4) uint8 at the stack's size, or an RGB colour), Normal blend with
        each layer's opacity, in `box` (x0, y0, x1, y1; default the whole image). Returns uint8 RGBA, alpha 255."""
        stack: PaintStack = obj.paint
        width, height = stack.width, stack.height
        x0, y0, x1, y1 = (0, 0, width, height) if box is None else box
        if isinstance(base, np.ndarray):
            out = base[y0:y1, x0:x1, :3].astype(np.float32)
        else:
            out = np.empty((y1 - y0, x1 - x0, 3), dtype=np.float32)
            out[...] = np.asarray(base, dtype=np.float32)[:3] * 255.0
        for spec in stack.layers:
            if not spec.visible or spec.opacity <= 0.0:
                continue
            rgba = self.pixels(obj, spec.name)[y0:y1, x0:x1]
            covered = rgba[..., 3]
            rows = np.flatnonzero(covered.any(axis=1))
            if rows.size == 0:
                continue  # nothing painted here
            cols = np.flatnonzero(covered[rows[0]:rows[-1] + 1].any(axis=0))
            r0, r1, c0, c1 = rows[0], rows[-1] + 1, cols[0], cols[-1] + 1  # only where the layer has alpha
            part = rgba[r0:r1, c0:c1]
            target = out[r0:r1, c0:c1]
            alpha = part[..., 3:4].astype(np.float32) * (spec.opacity / 255.0)
            target += (part[..., :3].astype(np.float32) - target) * alpha
        result = np.empty((y1 - y0, x1 - x0, 4), dtype=np.uint8)
        result[..., :3] = np.clip(np.rint(out), 0, 255).astype(np.uint8)
        result[..., 3] = 255
        return result


def _pack(block: np.ndarray) -> bytes:
    return zlib.compress(np.ascontiguousarray(block).tobytes(), 1)


def _unpack(data: bytes, shape) -> np.ndarray:
    return np.frombuffer(zlib.decompress(data), dtype=np.uint8).reshape(shape)


class StrokeRecorder:
    """One stroke on one layer (module docstring). Write pixels through `write_box` / `write_texels`; `commit()` or
    `cancel()` ends it."""

    def __init__(self, store: PaintStore, obj: SceneObject, name: str, description: str) -> None:
        self.store, self.obj, self.name, self.description = store, obj, name, description
        self._before: dict[tuple[int, int], bytes] = {}
        self._open = True

    @property
    def tiles(self) -> frozenset[tuple[int, int]]:
        return frozenset(self._before)

    def _capture(self, tiles) -> np.ndarray:
        if not self._open:
            raise PaintError("the stroke has ended")
        rgba = self.store.pixels(self.obj, self.name)
        height, width = rgba.shape[:2]
        for tile in tiles:
            if tile not in self._before:
                x0, y0, x1, y1 = tile_box(tile, width, height)
                self._before[tile] = _pack(rgba[y0:y1, x0:x1])
        return rgba

    def write_box(self, x0: int, y0: int, block: np.ndarray) -> None:
        """Writes `block` ((h, w, 4) uint8) with its lower-left texel at (x0, y0)."""
        h, w = block.shape[:2]
        tiles = tiles_of(x0, y0, x0 + w, y0 + h)
        rgba = self._capture(tiles)
        rgba[y0:y0 + h, x0:x0 + w] = block
        self.store._touched(self.obj, self.name, tiles)

    def write_texels(self, texels: np.ndarray, values: np.ndarray) -> None:
        """Writes `values` ((n, 4) uint8) at flat texel indices (`y * width + x`, the texel map's)."""
        texels = np.asarray(texels, dtype=np.int64)
        rgba = self.store.pixels(self.obj, self.name)
        width = rgba.shape[1]
        across = -(-width // TILE)
        keys = np.unique(texels // width // TILE * across + texels % width // TILE)  # one pass, not one per texel
        tiles = {(int(k % across), int(k // across)) for k in keys}
        self._capture(tiles)
        rgba.reshape(-1, 4)[texels] = values
        self.store._touched(self.obj, self.name, tiles)

    def cancel(self) -> None:
        """Every touched tile back as it was (Esc): exact."""
        if not self._open:
            return
        rgba = self.store.pixels(self.obj, self.name)
        height, width = rgba.shape[:2]
        for tile, data in self._before.items():
            x0, y0, x1, y1 = tile_box(tile, width, height)
            rgba[y0:y1, x0:x1] = _unpack(data, (y1 - y0, x1 - x0, 4))
        if self._before:
            self.store._touched(self.obj, self.name, self._before)
        self._open = False

    def commit(self) -> "PaintStrokeCommand | None":
        """The stroke as one Undo step (None when it touched nothing)."""
        if not self._open:
            raise PaintError("the stroke has ended")
        self._open = False
        if not self._before:
            return None
        return PaintStrokeCommand(self.store, self.obj, self.name, self._before, self.description)


class PaintStrokeCommand:
    """The pixels of one stroke as an Undo step (the Core `Command` protocol; `layer_declarations`: no mesh data). Holds
    the touched tiles' "before" pixels; the first Undo captures their "after" pixels for Redo."""

    def __init__(self, store: PaintStore, obj: SceneObject, name: str, before: dict, description: str) -> None:
        self.store, self.obj, self.name = store, obj, name
        self.before = dict(before)
        self.after: dict | None = None
        self.description = description

    def _swap(self, write: dict) -> dict:
        rgba = self.store.pixels(self.obj, self.name)
        height, width = rgba.shape[:2]
        current = {}
        for tile, data in write.items():
            x0, y0, x1, y1 = tile_box(tile, width, height)
            current[tile] = _pack(rgba[y0:y1, x0:x1])
            rgba[y0:y1, x0:x1] = _unpack(data, (y1 - y0, x1 - x0, 4))
        self.store._touched(self.obj, self.name, write)
        return current

    def undo(self) -> None:
        after = self._swap(self.before)
        if self.after is None:
            self.after = after

    def redo(self) -> None:
        self._swap(self.after or {})

    def stored_bytes(self) -> int:
        """Compressed bytes this step holds (the P-11 budget's measure)."""
        return sum(map(len, self.before.values())) + sum(map(len, (self.after or {}).values()))


class PaintStackCommand:
    """`SceneObject.paint` from one value to another as an Undo step (a stack added or removed, a layer's opacity,
    visibility, name or order) - shaped like `ObjectTextureCommand`. Pixels are not part of it: the store keeps a
    layer's pixels while the layer is out of the stack, so an Undo that brings it back finds them."""

    def __init__(self, obj: SceneObject, before: PaintStack | None, after: PaintStack | None, description: str) -> None:
        self.obj, self.before, self.after = obj, before, after
        self.description = description

    def undo(self) -> None:
        self.obj.paint = self.before

    def redo(self) -> None:
        self.obj.paint = self.after
