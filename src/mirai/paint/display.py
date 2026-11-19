"""What a painted object shows (AD-037 §6, §8 Phase 2: the live texture wired to `PaintStore.take_changed`).

One `PaintDisplay` per app. For every painted object it keeps the **composite** - the base (the object's own texture at
the stack size, or its base colour; P-4) with the visible layers over it (`PaintStore.composite`) - as a `(h, w, 4)`
uint8 array and a `viewport.live_texture.LiveTexture` over it, which the viewport draws in place of the texture path
(`ObjectsController._shown_texture`). Each frame `update()` re-composites only the tiles the store reports as changed
(`take_changed`) and marks them on the live texture, which uploads only those boxes; a changed stack value (a layer's
opacity or visibility, a stack added by Undo / Redo) re-composites the tiles the old or the new stack has paint in
(Phase 3: layer changes over a large image), another base or size the whole image.

An object without paint shows its texture path exactly as before (P-E: nothing is allocated until an object is painted),
except the Paint Room's object while the room is open (`prepare`): its composite (= the base) is read and shown when the
room opens, so the first dab only re-composites its tiles (Manu 2026-11-18: "Erster Tupfer dauert ca 7 Sekunden").

**Mipmaps** per frame (`MIPMAPS` "frame"; Manu 2026-11-18: with "deferred" the stroke showed less the steeper the surface
was seen - the minified levels were the old image until the release). Only frames that uploaded a box regenerate them.
Data flows store -> composite -> GPU only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core import SceneObject
from viewport.live_texture import LiveTexture

from . import files
from .store import TILE, PaintStore, occupied, tile_box, tiles_in

#: The live texture's mip policy (`viewport.live_texture.MIP_POLICIES`; see the module docstring). P-B on the reference PC:
#: "frame" 4.7 ms against "deferred" 4.0 ms per frame at 3 % (2048²).
MIPMAPS = "frame"


def base_composite(base, width: int, height: int) -> np.ndarray:
    """`PaintStore.composite` of a stack without paint: the base as uint8 RGBA, alpha 255 (the same arithmetic)."""
    out = np.empty((height, width, 4), dtype=np.uint8)
    if isinstance(base, np.ndarray):
        out[..., :3] = np.clip(np.rint(base[..., :3].astype(np.float32)), 0, 255).astype(np.uint8)
    else:
        out[..., :3] = np.clip(np.rint(np.asarray(base, dtype=np.float32)[:3] * 255.0), 0, 255).astype(np.uint8)
    out[..., 3] = 255
    return out


@dataclass
class _Entry:
    obj: SceneObject
    key: tuple
    base: object
    composite: np.ndarray
    live: LiveTexture
    #: (tiles down, across) bool: where the composite may differ from the base (a superset) - a change of the layers'
    #: values or order re-composites only these and the tiles the new stack has paint in
    nonbase: np.ndarray | None = None


def _grid(height: int, width: int) -> np.ndarray:
    return np.zeros((-(-height // TILE), -(-width // TILE)), dtype=bool)


class PaintDisplay:
    def __init__(self, store: PaintStore, read_base=files.read_base) -> None:
        self.store = store
        self._read_base = read_base
        self._entries: dict[int, _Entry] = {}
        #: objects shown through their composite although they have no paint yet (the Paint Room's object)
        self._prepared: dict[int, SceneObject] = {}
        #: whole-image composites made (tests, the probe)
        self.full_composites = 0
        #: seconds the last `prepare` took to read the base image and to make the composite (the room's status line)
        self.last_prepare: tuple[float, float] | None = None

    def _painted(self, obj: SceneObject) -> np.ndarray:
        """The tiles the visible layers of `obj`'s stack have paint in."""
        stack = obj.paint
        grid = _grid(stack.height, stack.width)
        for spec in stack.layers:
            if spec.visible and spec.opacity > 0.0:
                grid |= occupied(self.store.pixels(obj, spec.name))
        return grid

    def _recomposite(self, entry: _Entry, grid: np.ndarray) -> int:
        obj, stack = entry.obj, entry.obj.paint
        tiles = tiles_in(grid)
        for tile in tiles:
            x0, y0, x1, y1 = tile_box(tile, stack.width, stack.height)
            entry.composite[y0:y1, x0:x1] = self.store.composite(obj, entry.base, (x0, y0, x1, y1))
            entry.live.mark(x0, y0, x1, y1)
        return len(tiles)

    def prepare(self, obj: SceneObject, width: int, height: int) -> None:
        """Show `obj` through a composite of `width` x `height` from now on, painted or not (the Paint Room opens)."""
        import time

        self._prepared[id(obj)] = obj
        entry = self._entries.get(id(obj))
        if entry is not None and entry.obj is obj and entry.composite.shape[:2] == (height, width):
            self.last_prepare = (0.0, 0.0)
            return
        started = time.perf_counter()
        base = self._read_base(obj, width, height)
        read = time.perf_counter() - started
        composite = base_composite(base, width, height) if obj.paint is None else \
            np.ascontiguousarray(self.store.composite(obj, base))
        if obj.paint is not None:
            self.store.take_changed(obj)
        if entry is not None:
            _release(entry.live)
        nonbase = _grid(height, width) if obj.paint is None else self._painted(obj)
        self._entries[id(obj)] = _Entry(obj, self._key(obj), base, composite, LiveTexture(composite, mipmaps=MIPMAPS),
                                        nonbase)
        self.full_composites += 1
        self.last_prepare = (read, time.perf_counter() - started - read)

    def unprepare(self, obj: SceneObject) -> None:
        """The room closed: an object without paint shows its texture path again."""
        self._prepared.pop(id(obj), None)
        entry = self._entries.get(id(obj))
        if entry is not None and entry.obj is obj and obj.paint is None:
            _release(entry.live)
            del self._entries[id(obj)]

    def shows(self, obj: SceneObject) -> bool:
        """True when `obj` is drawn through its composite (it is painted, or the Paint Room is open on it)."""
        return obj.paint is not None or self._prepared.get(id(obj)) is obj

    @staticmethod
    def _key(obj: SceneObject) -> tuple:
        return (obj.paint, obj.texture, obj.material)

    def texture(self, obj: SceneObject) -> LiveTexture | None:
        """The live texture `obj` shows (None when it shows none: no paint and not prepared)."""
        if not self.shows(obj):
            return None
        entry = self._entries.get(id(obj))
        key = self._key(obj)
        if entry is not None and entry.obj is obj and entry.key == key:
            return entry.live
        if obj.paint is None:  # prepared, the paint went (an Undo of the first stroke): the base again
            if entry is None or entry.obj is not obj:
                return None
            entry.composite[...] = base_composite(entry.base, entry.composite.shape[1], entry.composite.shape[0])
            entry.key = key
            entry.nonbase = _grid(*entry.composite.shape[:2])
            entry.live.mark_all()
            return entry.live
        stack = obj.paint
        if (entry is not None and entry.obj is obj and entry.key[0] is None and entry.key[1:] == key[1:]
                and entry.composite.shape[:2] == (stack.height, stack.width)):
            # the stack came (the first stroke, its Redo): the composite is the base, and every pixel written since is in
            # a tile the store reports as changed - `update` composites those
            entry.key = key
            return entry.live
        if (entry is not None and entry.obj is obj and entry.key[0] is not None and entry.key[1:] == key[1:]
                and entry.composite.shape[:2] == (stack.height, stack.width) and entry.nonbase is not None):
            # another stack of the same size over the same base (a layer's opacity, visibility, blend, order; a layer
            # added, deleted, merged): every tile outside the old and the new paint is the base on both sides
            entry.key = key
            painted = self._painted(obj)
            changed = _grid(stack.height, stack.width)
            for tx, ty in self.store.take_changed(obj):
                changed[ty, tx] = True
            self._recomposite(entry, entry.nonbase | painted | changed)
            entry.nonbase = painted | changed
            return entry.live
        base = entry.base if (entry is not None and entry.obj is obj and entry.key[1:] == key[1:]
                              and entry.composite.shape[:2] == (stack.height, stack.width)) else None
        if base is None:
            base = self._read_base(obj, stack.width, stack.height)
        composite = np.ascontiguousarray(self.store.composite(obj, base))
        self.full_composites += 1
        self.store.take_changed(obj)  # the whole image is new
        painted = self._painted(obj)
        if entry is not None and entry.obj is obj and entry.composite.shape == composite.shape:
            entry.composite[...] = composite  # the same array: the viewport keeps its texture, everything is re-sent
            entry.key, entry.base, entry.nonbase = key, base, painted
            entry.live.mark_all()
            return entry.live
        if entry is not None:
            _release(entry.live)  # another size: a new texture (the viewport takes it with the next view sync)
        live = LiveTexture(composite, mipmaps=MIPMAPS)
        self._entries[id(obj)] = _Entry(obj, key, base, composite, live, painted)
        return live

    def update(self) -> int:
        """Re-composites the changed tiles of every shown painted object; returns how many tiles."""
        done = 0
        for oid, entry in list(self._entries.items()):
            obj = entry.obj
            if obj.paint is None:
                continue  # kept: an Undo can bring the stack back with these pixels
            if self._key(obj) != entry.key:
                self.texture(obj)
                continue
            tiles = self.store.take_changed(obj)
            if not tiles:
                continue
            grid = _grid(obj.paint.height, obj.paint.width)
            for tx, ty in tiles:
                grid[ty, tx] = True
            done += self._recomposite(entry, grid)
            if entry.nonbase is not None:
                entry.nonbase |= grid
        return done

    def finish(self, obj: SceneObject) -> None:
        """A stroke ended on `obj`: its mipmaps follow (policy "deferred", AD-037 §7 P-B)."""
        entry = self._entries.get(id(obj))
        if entry is not None and entry.obj is obj:
            entry.live.finish()

    def colour_at(self, obj: SceneObject, texel: int) -> tuple[float, float, float] | None:
        """The composite's colour (0-1) at a flat texel index (the eyedropper: the albedo, not the lit frame colour)."""
        if obj.paint is None:
            return None
        self.texture(obj)
        self.update()
        entry = self._entries[id(obj)]
        pixel = entry.composite.reshape(-1, 4)[int(texel)]
        return tuple(float(c) / 255.0 for c in pixel[:3])

    def clear(self) -> None:
        """A scene reset: every live texture goes (its GL name with it when a context is current)."""
        for entry in self._entries.values():
            _release(entry.live)
        self._entries.clear()


def _release(live: LiveTexture) -> None:
    try:
        live.release()
    except Exception:  # noqa: BLE001 - no GL context (headless, shutdown): nothing to free
        pass
