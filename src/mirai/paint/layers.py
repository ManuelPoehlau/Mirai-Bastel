"""Layer operations on a painted object (AD-037 §11, Phase 3: "several layers"; audit 2026-11-18 §7).

Each function checks the request against the object's stack and returns the Undo step that makes it - nothing is changed
until the caller runs the step's `redo()` and pushes it (`PaintRoomController.layer_command`). A request that cannot be
served raises `PaintError` with the text for the status line.

- `add` a transparent layer above another (the first free "Ebene N"), at most `MAX_LAYERS`;
- `delete` (not the only layer: "Leeren" clears it), `rename` (unique, non-empty), `move` one place up / down;
- `set_values`: opacity, visibility, blend (`PAINT_BLEND_MODES`: Normal, Multiply - P-12, Manu 2026-11-19);
- `merge_down`: the layer into the one beneath it - both visible, the same blend; the result has opacity 1 with both
  opacities baked in, so the composite stays the same (up to 8-bit rounding, `store.merge_pixels`);
- `clear`: the layer transparent.

Pixel changes are `PaintLayersCommand`s (the pixels leave the store into the step), value changes `PaintStackCommand`s.
"""

from __future__ import annotations

import dataclasses

from core import PaintLayer, PaintStack, SceneObject
from core.scene import PAINT_BLEND_MODES

from .store import (LayerSnapshot, PaintError, PaintLayersCommand, PaintStackCommand, PaintStore, blank,
                    merge_pixels)

#: Layers per object at most (`PROVISIONAL`; audit §4.2: "1-8 layers"; each is 16 MiB in memory at 2048²).
MAX_LAYERS = 8
#: The name stem of a new layer ("Ebene 1" is the first stroke's, `controllers.paint_room.FIRST_LAYER`).
NAME_STEM = "Ebene"
#: German labels of the blend modes (the panel).
BLEND_LABELS = {"normal": "Normal", "multiply": "Multiplizieren"}


def _stack(obj: SceneObject) -> PaintStack:
    if obj.paint is None:
        raise PaintError(f"{obj.name!r} has no paint yet - the first stroke makes its first layer")
    return obj.paint


def index_of(stack: PaintStack, name: str) -> int:
    for i, layer in enumerate(stack.layers):
        if layer.name == name:
            return i
    raise PaintError(f"no paint layer {name!r}")


def free_name(stack: PaintStack) -> str:
    taken = {layer.name for layer in stack.layers}
    n = len(stack.layers) + 1
    while f"{NAME_STEM} {n}" in taken:
        n += 1
    return f"{NAME_STEM} {n}"


def _with_layers(stack: PaintStack, layers) -> PaintStack:
    return dataclasses.replace(stack, layers=tuple(layers))


def add(store: PaintStore, obj: SceneObject, above: str | None = None) -> tuple[PaintLayersCommand, str]:
    """A transparent layer above `above` (default: the top); returns the step and the new layer's name."""
    stack = _stack(obj)
    if len(stack.layers) >= MAX_LAYERS:
        raise PaintError(f"at most {MAX_LAYERS} paint layers")
    name = free_name(stack)
    at = len(stack.layers) if above is None else index_of(stack, above) + 1
    layers = list(stack.layers)
    layers.insert(at, PaintLayer(name, None))
    # the new name may still have pixels in the store (a layer of that name deleted earlier, whose step was dropped):
    # the step sets none, so the new layer is transparent
    return (PaintLayersCommand(store, obj, stack, _with_layers(stack, layers), {name: store.snapshot(obj, name)},
                               {name: None}, f"New paint layer {name!r}"), name)


def delete(store: PaintStore, obj: SceneObject, name: str) -> PaintLayersCommand:
    stack = _stack(obj)
    i = index_of(stack, name)
    if len(stack.layers) == 1:
        raise PaintError("the only paint layer cannot be deleted - clear it instead")
    layers = list(stack.layers)
    del layers[i]
    return PaintLayersCommand(store, obj, stack, _with_layers(stack, layers), {name: store.snapshot(obj, name)},
                              {name: None}, f"Delete paint layer {name!r}")


def rename(store: PaintStore, obj: SceneObject, name: str, new: str) -> PaintLayersCommand:
    stack = _stack(obj)
    i = index_of(stack, name)
    new = new.strip()
    if new == name:
        raise PaintError("the layer already has that name")
    if any(layer.name == new for layer in stack.layers):
        raise PaintError(f"a paint layer {new!r} exists")
    layers = list(stack.layers)
    try:
        layers[i] = dataclasses.replace(layers[i], name=new)
    except ValueError as exc:
        raise PaintError(f"layer name: {exc}") from exc
    pixels = store.snapshot(obj, name)
    return PaintLayersCommand(store, obj, stack, _with_layers(stack, layers),
                              {name: pixels, new: store.snapshot(obj, new)}, {name: None, new: pixels},
                              f"Rename paint layer {name!r} to {new!r}")


def move(obj: SceneObject, name: str, step: int) -> PaintStackCommand:
    """One place up (`step` +1, towards the top) or down (-1)."""
    stack = _stack(obj)
    i = index_of(stack, name)
    j = i + (1 if step > 0 else -1)
    if not 0 <= j < len(stack.layers):
        raise PaintError(f"{name!r} is already the {'top' if step > 0 else 'bottom'} layer")
    layers = list(stack.layers)
    layers[i], layers[j] = layers[j], layers[i]
    return PaintStackCommand(obj, stack, _with_layers(stack, layers),
                             f"Move paint layer {name!r} {'up' if step > 0 else 'down'}")


def with_values(stack: PaintStack, name: str, **values) -> PaintStack:
    """`stack` with layer `name`'s opacity / visible / blend changed (`PaintError` for an invalid value)."""
    unknown = set(values) - {"opacity", "visible", "blend"}
    if unknown:
        raise TypeError(f"paint layer values: {sorted(unknown)}")
    if "blend" in values and values["blend"] not in PAINT_BLEND_MODES:
        raise PaintError(f"blend one of {PAINT_BLEND_MODES}")
    i = index_of(stack, name)
    layers = list(stack.layers)
    try:
        layers[i] = dataclasses.replace(layers[i], **values)
    except ValueError as exc:
        raise PaintError(str(exc)) from exc
    return _with_layers(stack, layers)


def set_values(obj: SceneObject, name: str, before: PaintStack | None = None, **values) -> PaintStackCommand | None:
    """The step from `before` (default: the stack now; a held slider's start) to the stack with the values; None when
    nothing changes."""
    before = _stack(obj) if before is None else before
    after = with_values(before, name, **values)
    if after == before:
        return None
    what = ", ".join(f"{k} {_value_text(k, v)}" for k, v in values.items())
    return PaintStackCommand(obj, before, after, f"Paint layer {name!r}: {what}")


def _value_text(key: str, value) -> str:
    if key == "opacity":
        return f"{round(float(value) * 100)} %"
    if key == "visible":
        return "shown" if value else "hidden"
    return str(value)


def merge_down(store: PaintStore, obj: SceneObject, name: str) -> PaintLayersCommand:
    stack = _stack(obj)
    i = index_of(stack, name)
    if i == 0:
        raise PaintError(f"{name!r} is the bottom layer - nothing to merge into")
    upper, lower = stack.layers[i], stack.layers[i - 1]
    if not (upper.visible and lower.visible):
        raise PaintError("merge down: show both layers first")
    if upper.blend != lower.blend:
        raise PaintError(f"merge down: {upper.blend} into {lower.blend} cannot be one layer"
                         " - give both the same blend")
    up_pixels, low_pixels = store.load(obj, upper.name), store.load(obj, lower.name)
    merged = merge_pixels(up_pixels, upper.opacity, low_pixels, lower.opacity, upper.blend)
    layers = list(stack.layers)
    layers[i - 1] = dataclasses.replace(lower, opacity=1.0)
    del layers[i]
    return PaintLayersCommand(
        store, obj, stack, _with_layers(stack, layers),
        {upper.name: store.snapshot(obj, upper.name), lower.name: store.snapshot(obj, lower.name)},
        {upper.name: None, lower.name: LayerSnapshot.of(merged, store.source(obj, lower.name), True)},
        f"Merge paint layer {upper.name!r} down into {lower.name!r}")


def clear(store: PaintStore, obj: SceneObject, name: str) -> PaintLayersCommand:
    stack = _stack(obj)
    index_of(stack, name)
    pixels = store.load(obj, name)
    if not pixels[..., 3].any():
        raise PaintError(f"{name!r} is already empty")
    return PaintLayersCommand(store, obj, stack, stack, {name: store.snapshot(obj, name)},
                              {name: LayerSnapshot.of(blank(stack.width, stack.height), store.source(obj, name), True)},
                              f"Clear paint layer {name!r}")
