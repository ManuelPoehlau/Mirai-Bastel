"""The evaluated mix of several morph targets (AD-025 Phase 4, the §11 "multi-target evaluation rules").

**Rule** (decided with Phase 4, `PROVISIONAL` where marked in AD-025 §17): the additive mix

    p(v) = b(v) + Σᵢ (wᵢ / 100) · dᵢ(v)

over the targets with a weight above 0, wᵢ in whole percent 0..100 (no clamping beyond that range, no
normalization, no correctives). The sum runs in ascending `LayerId` order — fixed for the life of a
layer, unlike the display order — with the first term taken as it is (not added to 0.0). So one target
gives exactly the Phase 3 values (`b + d` at 100 %, `b + w·d` below), and a point with no offset in any
active target is exactly its rest position.

**Drift guard by construction:** a point is never updated incrementally (`p += Δw·d`). Every point whose
inputs may have changed — the points of a target whose weight changed (sparse: only that target's
points), the points the base's journal names (moved, new, offsets written), the points of a target
rewritten as a whole — is recomputed from `b`, the weights and the offsets. The shown surface is
therefore a pure function of the current inputs: bit-identical whatever the order or number of weight
steps, edits, Undo / Redo (tested against the definition, `tests/test_morph_mix.py`).

`MixSurface` owns the evaluated surface of one base mesh, patched in place from the base's change journal
(`Mesh.watch()`, keys only): a weight step costs O(points of that target × active targets at a point), an
edit O(touched points), a topology edit the changed elements (AD-025 §16.1), a build O(V) only the first
time. Since O1 (2026-11-11, audit 2026-11-10 §G.3) the surface is a `SurfacePositions`: the mix as a
position table over the base's own topology (a read-only view with the `Mesh` queries; no layers), not a
`core.Mesh` copy with the base's topology replayed into it. Since O3 stage 2 (2026-11-13, AD-032 §11) it
computes on arrays on the table's slots: the offsets of each shown target as `present` / `D` arrays, the base
positions as `B`, the candidates as slot arrays; the sum keeps the rule's order column by column (the first term as
it is, then `+=` in ascending `LayerId` order), so the result is bit-identical to `evaluate`.
"""

from __future__ import annotations

from typing import Optional

from core import Mesh

from viewport.packed_geometry import np  # NumPy behind its pinned-version check (AD-032 §2)

from .surface_positions import MovedVertices, SurfacePositions, _grown

_ZERO = (0.0, 0.0, 0.0)


def rest_state(mesh: Mesh) -> dict:
    """The mesh's state without its point layers (the morph editing view's copy, `morph_targets.view_state`; tests)."""
    state = mesh.export_state()
    state["point_layers"] = None
    return state


def topology_touched(change, mesh: Mesh) -> bool:
    if change.edges or change.faces or change.face_uvs:
        return True
    return any(before is None or not mesh.is_valid_vertex(vid) for vid, before in change.vertices.items())


def offset_keys(change, lid) -> Optional[set]:
    """The vertices whose offset in `lid` may have changed (None = the whole layer)."""
    if lid in change.layer_whole:
        return None
    return set(change.layer_values.get(lid, ()))


def mix_position(b, terms) -> tuple:
    """`b + Σ f·d` over `terms` = [(f, d), ...] in their order, the first term as it is (module rule)."""
    if not terms:
        return tuple(b)
    f, d = terms[0]
    sx, sy, sz = f * d[0], f * d[1], f * d[2]
    for f, d in terms[1:]:
        sx += f * d[0]
        sy += f * d[1]
        sz += f * d[2]
    return (b[0] + sx, b[1] + sy, b[2] + sz)


def factor(weight: int) -> float:
    """Whole percent -> the multiplier (exactly 1.0 at 100 %)."""
    return 1.0 if weight >= 100 else weight / 100.0


def evaluate(base: Mesh, weights: dict) -> dict:
    """The definition, for every vertex (the oracle and the reference for SubD of the mixed cage)."""
    order = sorted((lid for lid, w in weights.items() if w > 0), key=int)
    out = {}
    for v in base.all_vertex_ids():
        terms = []
        for lid in order:
            d = base.layer_value(lid, v)
            if d != _ZERO:
                terms.append((factor(weights[lid]), d))
        out[v] = mix_position(base.vertex_position(v), terms)
    return out


class _Offsets:
    """One shown target's offsets on the table's slots (AD-032 §11.2): `present` (the vertex at the slot has an entry -
    exactly the keys of the dict cache this replaces) and `D` (its offset). A freed slot is cleared; a new vertex
    starts absent."""

    __slots__ = ("present", "D", "_slots")

    def __init__(self, capacity: int) -> None:
        self.present = np.zeros(capacity, dtype=bool)
        self.D = np.zeros((capacity, 3))
        self._slots = None

    def fit(self, capacity: int) -> None:
        if len(self.present) < capacity:
            self.present = _grown(self.present, capacity, False)
            self.D = _grown(self.D, capacity, 0.0)

    def slots(self):
        """The present slots, ascending (cached until the next change)."""
        if self._slots is None:
            self._slots = np.flatnonzero(self.present)
        return self._slots

    def changed(self) -> None:
        self._slots = None


class MixSurface:
    """The evaluated surface of one base mesh (module docstring)."""

    def __init__(self, base: Mesh) -> None:
        self.base = base
        self._watch = base.watch()
        #: the shown mix: a `SurfacePositions` over the base's topology (None until the first `update`)
        self.mesh: Optional[SurfacePositions] = None
        #: the weights the surface shows: LayerId -> whole percent (> 0 only)
        self.weights: dict = {}
        #: True right after an `update` that patched the topology of `mesh` in place (H7)
        self.topology_changed = False
        # LayerId -> `_Offsets` of every shown target (a cache of the base's layer on the table's slots, kept in step
        # through the journal); dropped when the target's weight goes to 0 (memory bounded by the mix)
        self._offsets: dict = {}
        # [(factor, _Offsets)] in ascending LayerId order - the summation order
        self._terms: list = []
        # the base positions on the table's slots (refreshed for the vertices the base's journal names)
        self._B = None

    def close(self) -> None:
        self._watch.close()

    def pending(self) -> bool:
        return not self._watch.peek().is_empty()

    def _load(self, lid) -> _Offsets:
        """The target's stored offsets on the table's slots (every stored vertex is held: new ones get slots first)."""
        surface = self.mesh
        out = _Offsets(surface.capacity)
        items = self.base.layer_items(lid)
        if items:
            n = len(items)
            slots = surface.table_slots([v for v, _ in items])
            out.D[slots] = np.fromiter((c for _, d in items for c in d), dtype=np.float64, count=3 * n).reshape(n, 3)
            out.present[slots] = True
        return out

    def _set_terms(self) -> None:
        self._terms = [(factor(self.weights[lid]), self._offsets[lid]) for lid in sorted(self.weights, key=int)]

    def _fit(self) -> None:
        """Per-slot arrays as large as the table (it grows when vertices enter)."""
        capacity = self.mesh.capacity
        if len(self._B) < capacity:
            self._B = _grown(self._B, capacity, 0.0)
            for offsets in self._offsets.values():
                offsets.fit(capacity)

    def update(self, weights: dict) -> tuple[bool, set]:
        """Shows `weights` (LayerId -> whole percent; 0 and unknown layers are ignored). Returns
        (rebuilt = a new `mesh` object, changed vertices of the kept one)."""
        base = self.base
        alive = set(base.point_layer_ids())
        weights = {lid: int(w) for lid, w in weights.items() if w > 0 and lid in alive}
        change = self._watch.take()
        self.topology_changed = False
        if self.mesh is None:
            surface = self.mesh = SurfacePositions(base)
            self._B = surface.P.copy()
            self.weights = weights
            self._offsets = {lid: self._load(lid) for lid in weights}
            self._set_terms()
            if self._offsets:
                slots = np.unique(np.concatenate([o.slots() for o in self._offsets.values()]))
                surface._owner_set_slots(slots, self._mix(slots))
            return True, set()
        surface = self.mesh
        index = surface._index
        valid = base.is_valid_vertex
        candidates: list = []  # slot arrays
        named = change.vertices
        if topology_touched(change, base):
            # AD-025 §16.1: the surface reads the base's topology; it drops the vertices that went and tells its
            # watches which elements changed (new vertices get a slot here and their mix below)
            freed = surface._owner_follow_topology(change)
            for offsets in self._offsets.values():
                offsets.present[freed] = False
                offsets.changed()
            self.topology_changed = True
        new = [v for v in named if v not in index and valid(v)]
        if new:
            rows = [base.vertex_position(v) for v in new]
            new_slots = np.fromiter((surface._owner_add(v, p) for v, p in zip(new, rows)), dtype=np.intp,
                                    count=len(new))
            surface._owner_record(dict.fromkeys(new))
            self._fit()
            self._B[new_slots] = rows
        else:
            new_slots = None
        moved = [v for v in named if v in index and valid(v)]
        if moved:  # the base positions the journal names (moved, new)
            slots = surface.table_slots(moved)
            self._B[slots] = [base.vertex_position(v) for v in moved]
            candidates.append(np.unique(slots))
        offsets = self._offsets
        for lid in list(offsets):  # keep the shown targets' caches in step with the base's journal
            cache = offsets[lid]
            if lid not in alive:
                candidates.append(offsets.pop(lid).slots())
                continue
            keys = offset_keys(change, lid)
            if keys is None:
                fresh = self._load(lid)
                candidates += [cache.slots(), fresh.slots()]
                offsets[lid] = fresh
                continue
            held = [v for v in keys if v in index]  # a vertex that went left with its slot
            if not held:
                continue
            for v in held:
                s = index[v]
                d = base.layer_value(lid, v) if valid(v) else _ZERO
                if d == _ZERO:
                    cache.present[s] = False
                else:
                    cache.present[s] = True
                    cache.D[s] = d
            cache.changed()
            candidates.append(np.unique(surface.table_slots(held)))
        if weights != self.weights:
            for lid in set(weights) | set(self.weights):
                old, new_weight = self.weights.get(lid), weights.get(lid)
                if old == new_weight:
                    continue
                if new_weight is None:  # weight 0: its points go back to the other targets' mix
                    cache = offsets.pop(lid, None)
                    if cache is not None:
                        candidates.append(cache.slots())
                    continue
                if lid not in offsets:
                    offsets[lid] = self._load(lid)
                candidates.append(offsets[lid].slots())
            self.weights = weights
        self._set_terms()
        if new_slots is not None:
            candidates.append(new_slots)
        return False, self._recompute(candidates, new_slots)

    def _mix(self, slots) -> "np.ndarray":
        """The rule for held `slots`, column by column: per target in ascending LayerId order, the first present term
        `f * d` as it is, then `+= f * d`; `b + sum`, or `b` as stored without a term (`mix_position`, bit for bit)."""
        out = self._B[slots]
        acc = started = None
        for f, offsets in self._terms:
            has = offsets.present[slots]
            if not has.any():
                continue
            if acc is None:
                acc = np.zeros((len(slots), 3))
                started = np.zeros(len(slots), dtype=bool)
                first = has
            else:
                first = has & ~started
                rest = has & started
                if rest.any():
                    acc[rest] += f * offsets.D[slots[rest]]
            if first.any():
                acc[first] = f * offsets.D[slots[first]]
            started |= has
        if acc is not None:
            out[started] = out[started] + acc[started]
        return out

    def _recompute(self, candidates: list, new_slots=None) -> MovedVertices:
        """The rule for every candidate slot (`_mix`), written into the table where it differs and recorded as one
        chunk; new vertices are written as they are (recorded by id). Returns the changed vertices (new ones
        included)."""
        surface = self.mesh
        if not candidates:
            return surface._owner_moved(np.zeros(0, dtype=np.intp))
        slots = np.unique(np.concatenate(candidates)) if len(candidates) > 1 else candidates[0]
        slots = slots[surface._held[slots]]
        always = None
        if new_slots is not None:
            always = np.zeros(len(slots), dtype=bool)
            always[np.searchsorted(slots, new_slots)] = True
        changed = surface._owner_write_slots(slots, self._mix(slots), always)
        if new_slots is not None:
            changed = np.union1d(changed, new_slots)
        return surface._owner_moved(changed)
