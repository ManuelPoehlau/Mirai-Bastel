"""What a painted object shows (AD-037 §6, §8 Phase 2: the live texture wired to `PaintStore.take_changed`).

One `PaintDisplay` per app. For every painted object it keeps the **composite** - the base (the object's own texture at
the stack size, or its base colour; P-4) with the visible layers over it (`PaintStore.composite`) - as a `(h, w, 4)`
uint8 array and a `viewport.live_texture.LiveTexture` over it, which the viewport draws in place of the texture path
(`ObjectsController._shown_texture`). Each frame `update()` re-composites only the tiles the store reports as changed
(`take_changed`) and marks them on the live texture, which uploads only those boxes; a changed stack value (a layer's
opacity or visibility, a stack added by Undo / Redo) or another base re-composites the whole image.

An object without paint shows its texture path exactly as before (P-E: nothing is allocated until an object is painted).
Data flows store -> composite -> GPU only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core import SceneObject
from viewport.live_texture import LiveTexture

from . import files
from .store import PaintStore, tile_box


@dataclass
class _Entry:
    obj: SceneObject
    key: tuple
    base: object
    composite: np.ndarray
    live: LiveTexture


class PaintDisplay:
    def __init__(self, store: PaintStore, read_base=files.read_base) -> None:
        self.store = store
        self._read_base = read_base
        self._entries: dict[int, _Entry] = {}
        #: whole-image composites made (tests, the probe)
        self.full_composites = 0

    @staticmethod
    def _key(obj: SceneObject) -> tuple:
        return (obj.paint, obj.texture, obj.material)

    def texture(self, obj: SceneObject) -> LiveTexture | None:
        """The live texture `obj` shows (None without paint)."""
        if obj.paint is None:
            return None
        entry = self._entries.get(id(obj))
        key = self._key(obj)
        if entry is not None and entry.obj is obj and entry.key == key:
            return entry.live
        stack = obj.paint
        base = entry.base if (entry is not None and entry.obj is obj and entry.key[1:] == key[1:]
                              and entry.composite.shape[:2] == (stack.height, stack.width)) else None
        if base is None:
            base = self._read_base(obj, stack.width, stack.height)
        composite = np.ascontiguousarray(self.store.composite(obj, base))
        self.full_composites += 1
        self.store.take_changed(obj)  # the whole image is new
        if entry is not None and entry.obj is obj and entry.composite.shape == composite.shape:
            entry.composite[...] = composite  # the same array: the viewport keeps its texture, everything is re-sent
            entry.key, entry.base = key, base
            entry.live.mark_all()
            return entry.live
        if entry is not None:
            _release(entry.live)  # another size: a new texture (the viewport takes it with the next view sync)
        live = LiveTexture(composite)
        self._entries[id(obj)] = _Entry(obj, key, base, composite, live)
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
            stack = obj.paint
            for tile in tiles:
                x0, y0, x1, y1 = tile_box(tile, stack.width, stack.height)
                entry.composite[y0:y1, x0:x1] = self.store.composite(obj, entry.base, (x0, y0, x1, y1))
                entry.live.mark(x0, y0, x1, y1)
            done += len(tiles)
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
