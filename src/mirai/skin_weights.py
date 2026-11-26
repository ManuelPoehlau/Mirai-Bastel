"""The weight write rule in the app (AD-028 §3.4, the handoff's remainder rule). Names `PROVISIONAL`.

The Core stores weights (`LayerKind.WEIGHTS`, canonical form W1-W4) and combines them for new points; it
never needs the hierarchy. Writing a bone's weight - what the weight gestures (slice 3) and bone
deletion do - is this module's rule, applied per vertex and written through `Mesh.set_layer_value`
(journaled, so Undo restores the exact old split):

Setting bone `b` to `x ∈ [0, 1]` at a vertex with value `W` and object share `r = 1 − Σw`:

- `old = W[b]` (0 when absent), `Δ = x − old`; `Δ = 0` changes nothing.
- **Raise** (`Δ > 0`): every other share - the other bones and `r` - is scaled by `(1 − x) / (1 − old)`;
  `b` gets `x`.
- **Lower** (`Δ < 0`): `b` gets `x`; the freed `−Δ` goes to `parent(b)`, or to the object's share for a
  root (P-3: lowering a jaw share falls back to what the jaw hangs on).
- **More than four keys** after a write: `b` and the three largest other bones stay (ties: the smaller key
  stays); the dropped shares go to the remaining others proportionally (`r` included); `b` stays `x`.
- Then the Core's canonical form (W4).
- **Soft** (Manu 2026-11-02): the target is `x(v) = old_b(v) + s(v)·(x − old_b(v))` (`soft_target`).
- **Deleting a bone** = lowering it to 0 everywhere: its share goes to its parent (or the object); never
  more than four keys (the parent replaces the bone).
- **Path dependent across gestures** (DEVCHAT-001, accepted): raising and lowering back in a second gesture
  does not restore the old split - `{jaw 0.4, cheek 0.6}` (parent head): jaw -> 0.7 gives
  `{jaw 0.7, cheek 0.3}`, jaw back -> 0.4 gives `{head 0.3, jaw 0.4, cheek 0.3}`. Within one gesture the
  result is deterministic: `WeightStroke` computes every step from the values at the press (§8.4).
- **Clean** ("Aufräumen", AD-041 §3.3 / W-9, `clean_weights`): every share `0 < w < threshold` is lowered to 0 by this
  rule (to the parent, or the object for a root), repeated until no share of the vertex is below the threshold - a
  parent can receive a small share and pass it on; the hierarchy is finite, so this ends. The brush is
  `mirai.weight_paint` (AD-041 §3.1-§3.2).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from typing import Optional

from core import Mesh
from core.rig import Rig

#: influences per point (W1)
MAX_INFLUENCES = 4


def set_bone_weight(value, bone: int, x: float, parent_of: Callable[[int], Optional[int]]) -> tuple:
    """The rule of the module docstring on one vertex value (pure). Returns the new value as pairs in
    ascending key order (the Core canonicalizes it when written)."""
    if not (math.isfinite(x) and 0.0 <= x <= 1.0):
        raise ValueError(f"a weight lies in [0, 1]: {x!r}")
    bone = int(bone)
    shares = {int(k): float(w) for k, w in value}
    old = shares.get(bone, 0.0)
    delta = x - old
    if delta == 0.0:
        return tuple(sorted(shares.items()))
    rest = max(0.0, 1.0 - math.fsum(shares.values()))  # the object's share r
    if delta > 0.0:
        scale = (1.0 - x) / (1.0 - old)
        shares = {k: w * scale for k, w in shares.items() if k != bone}
        rest *= scale
    else:
        shares.pop(bone, None)
        parent = parent_of(bone)
        if parent is None:
            rest += -delta
        else:
            parent = int(parent)
            shares[parent] = shares.get(parent, 0.0) + (-delta)
    shares = {k: w for k, w in shares.items() if w > 0.0}
    if len(shares) + (1 if x > 0.0 else 0) > MAX_INFLUENCES:
        keep = MAX_INFLUENCES - (1 if x > 0.0 else 0)
        ranked = sorted(shares.items(), key=lambda kw: (-kw[1], kw[0]))
        kept, dropped = dict(ranked[:keep]), ranked[keep:]
        mass = math.fsum(w for _, w in dropped)
        remaining = math.fsum(kept.values()) + rest
        if remaining > 0.0:
            grow = (remaining + mass) / remaining
            kept = {k: w * grow for k, w in kept.items()}
        shares = kept
    if x > 0.0:
        shares[bone] = x
    return tuple(sorted(shares.items()))


def soft_target(old: float, x: float, s: float) -> float:
    """The Soft target (§3.4): `old + s·(x − old)`, `s` the Soft field at the vertex (1 on the selection)."""
    return old + s * (x - old)


def bone_share(value, bone: int) -> float:
    for k, w in value:
        if k == bone:
            return w
    return 0.0


def parent_function(rig: Optional[Rig]) -> Callable[[int], Optional[int]]:
    """`bone -> parent` of the rig (None for a root, an unknown bone or no rig)."""
    parents = {} if rig is None else {int(b.id): b.parent for b in rig.bones}
    return lambda bone: parents.get(int(bone))


class WeightStroke:
    """One weight write gesture's arithmetic (§8.4): the values at the press of every vertex the stroke
    may touch are kept; each step writes `set_bone_weight(press value, bone, target)` - a pure function of
    the press values and the step's targets, never of the previous step. Runs inside the caller's open
    recording (`Mesh.begin_change`): release = `end_change` (one entry), Esc = `rollback_change`."""

    def __init__(self, mesh: Mesh, layer, bone: int, rig: Optional[Rig], vertices: Iterable) -> None:
        self.mesh = mesh
        self.layer = layer
        self.bone = int(bone)
        self._parent_of = parent_function(rig)
        self.press = {v: mesh.layer_value(layer, v) for v in vertices}

    def press_share(self, v) -> float:
        return bone_share(self.press[v], self.bone)

    def step(self, targets: Mapping) -> None:
        """Sets the bone to `targets[v]` at every pressed vertex named; a pressed vertex not named goes
        back to its press value (a narrowed field leaves no trace of a wider one)."""
        mesh, layer = self.mesh, self.layer
        for v, value in self.press.items():
            x = targets.get(v)
            new = value if x is None else set_bone_weight(value, self.bone, x, self._parent_of)
            if mesh.layer_value(layer, v) != new:
                mesh.set_layer_value(layer, v, new)


def delete_bone_weights(mesh: Mesh, layer, bone: int, rig: Rig) -> int:
    """Lowers `bone` to 0 at every vertex that has it (its share to its parent or the object, §3.4),
    through `set_layer_value` (journaled). Returns the number of vertices rewritten. The caller removes the
    bone from the rig after this (it needs the bone's parent here)."""
    parent_of = parent_function(rig)
    bone = int(bone)
    count = 0
    for v, value in mesh.layer_items(layer):
        if any(k == bone for k, _ in value):
            mesh.set_layer_value(layer, v, set_bone_weight(value, bone, 0.0, parent_of))
            count += 1
    return count


#: AD-041 W-9 `PROVISIONAL`: shares below this are cleaned
CLEAN_THRESHOLD = 0.01


def clean_value(value, threshold: float, parent_of: Callable[[int], Optional[int]]) -> tuple:
    """The value with every share below `threshold` lowered to 0 by the write rule (module docstring; pure)."""
    while True:
        small = [(w, k) for k, w in value if 0.0 < w < threshold]
        if not small:
            return tuple(value)
        _, bone = min(small)  # the smallest first (ties: the smaller key)
        value = set_bone_weight(value, bone, 0.0, parent_of)


def clean_weights(mesh: Mesh, layer, rig: Optional[Rig], threshold: float = CLEAN_THRESHOLD,
                  mask: Optional[Mapping] = None) -> int:
    """Aufräumen ("clean", AD-041 §3.3) over the whole mesh and every bone, through `set_layer_value` inside the caller's one
    recording (one Undo step). `mask`: vertex -> protection; a masked vertex (any `m > 0`, `PROVISIONAL`: a threshold
    cut has no partial form) keeps its value. Returns the number of vertices rewritten."""
    if not 0.0 < threshold <= 1.0:
        raise ValueError(f"a clean threshold lies in (0, 1]: {threshold!r}")
    parent_of = parent_function(rig)
    mask = mask or {}
    count = 0
    for v, value in mesh.layer_items(layer):
        if mask.get(v, 0.0) > 0.0 or not any(w < threshold for _, w in value):
            continue
        new = clean_value(value, threshold, parent_of)
        if new != value:
            mesh.set_layer_value(layer, v, new)
            count += 1
    return count
