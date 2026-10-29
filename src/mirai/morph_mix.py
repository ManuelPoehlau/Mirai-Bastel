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

`MixSurface` owns the evaluated `core.Mesh` of one base mesh (same IDs and topology, positions = the
mix; no layers), patched in place from the base's change journal (`Mesh.watch()`, keys only): a weight
step costs O(points of that target × active targets at a point), an edit O(touched points), a topology
edit the changed elements (AD-025 §16.1), a rebuild O(V) only the first time.
"""

from __future__ import annotations

from typing import Optional

from core import Mesh
from core.mesh import MeshDelta

_ZERO = (0.0, 0.0, 0.0)


def rest_state(mesh: Mesh) -> dict:
    """The mesh's state without its point layers (a derived mesh carries none)."""
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


class MixSurface:
    """The evaluated surface of one base mesh (module docstring)."""

    def __init__(self, base: Mesh) -> None:
        self.base = base
        self._watch = base.watch()
        self.mesh: Optional[Mesh] = None
        #: the weights the surface shows: LayerId -> whole percent (> 0 only)
        self.weights: dict = {}
        #: True right after an `update` that patched the topology of `mesh` in place (H7)
        self.topology_changed = False
        # LayerId -> {VertexId: offset} of every shown target (a cache of the base's layer, kept in step
        # through the journal); dropped when the target's weight goes to 0 (memory bounded by the mix)
        self._offsets: dict = {}
        # [(factor, offsets dict)] in ascending LayerId order - the summation order
        self._terms: list = []

    def close(self) -> None:
        self._watch.close()

    def pending(self) -> bool:
        return not self._watch.peek().is_empty()

    def _load(self, lid) -> dict:
        return dict(self.base.layer_items(lid))

    def _point(self, v) -> tuple:
        b = self.base.vertex_position(v)
        terms = []
        for f, offsets in self._terms:
            d = offsets.get(v)
            if d is not None:
                terms.append((f, d))
        return mix_position(b, terms)

    def _set_terms(self) -> None:
        self._terms = [(factor(self.weights[lid]), self._offsets[lid]) for lid in sorted(self.weights, key=int)]

    def update(self, weights: dict) -> tuple[bool, set]:
        """Shows `weights` (LayerId -> whole percent; 0 and unknown layers are ignored). Returns
        (rebuilt = a new `mesh` object, changed vertices of the kept one)."""
        base = self.base
        alive = set(base.point_layer_ids())
        weights = {lid: int(w) for lid, w in weights.items() if w > 0 and lid in alive}
        change = self._watch.take()
        self.topology_changed = False
        if self.mesh is None:
            self.weights = weights
            self._offsets = {lid: self._load(lid) for lid in weights}
            self._set_terms()
            state = rest_state(base)
            vertices = state["vertices"]
            for v in set().union(*self._offsets.values()) if self._offsets else ():
                vertices[int(v)] = list(self._point(v))
            self.mesh = Mesh.from_state(state)
            return True, set()
        candidates = set(change.vertices)
        if topology_touched(change, base):
            # AD-025 §16.1: the base's changed elements, applied in place (positions follow below)
            self.mesh.apply_delta(_topology_delta(change, base, self.mesh))
            self.topology_changed = True
        offsets = self._offsets
        for lid in list(offsets):  # keep the shown targets' caches in step with the base's journal
            if lid not in alive:
                candidates |= set(offsets.pop(lid))
                continue
            keys = offset_keys(change, lid)
            cache = offsets[lid]
            if keys is None:
                fresh = self._load(lid)
                candidates |= set(cache) | set(fresh)
                offsets[lid] = fresh
                continue
            for v in keys:
                d = base.layer_value(lid, v) if base.is_valid_vertex(v) else _ZERO
                if d == _ZERO:
                    cache.pop(v, None)
                else:
                    cache[v] = d
            candidates |= keys
        if weights != self.weights:
            for lid in set(weights) | set(self.weights):
                old, new = self.weights.get(lid), weights.get(lid)
                if old == new:
                    continue
                if new is None:  # weight 0: its points go back to the other targets' mix
                    candidates |= set(offsets.pop(lid, ()))
                    continue
                if lid not in offsets:
                    offsets[lid] = self._load(lid)
                candidates |= set(offsets[lid])
            self.weights = weights
        self._set_terms()
        return False, self._recompute(candidates)

    def _recompute(self, candidates) -> set:
        """`mix_position` for every candidate, inlined (the weight-step hot loop; same arithmetic, same
        order: the first term as it is, then += in ascending LayerId order)."""
        base, surface, terms = self.base, self.mesh, self._terms
        valid, rest = base.is_valid_vertex, base.vertex_position
        shown, put = surface.vertex_position, surface.set_vertex_position
        changed = set()
        for v in candidates:
            if not valid(v):
                continue
            b = rest(v)
            first = True
            for f, offsets in terms:
                d = offsets.get(v)
                if d is None:
                    continue
                if first:
                    sx, sy, sz = f * d[0], f * d[1], f * d[2]
                    first = False
                else:
                    sx += f * d[0]
                    sy += f * d[1]
                    sz += f * d[2]
            p = tuple(b) if first else (b[0] + sx, b[1] + sy, b[2] + sz)
            if shown(v) != p:
                put(v, p)
                changed.add(v)
        return changed


def _topology_delta(change, base: Mesh, surface: Mesh) -> MeshDelta:
    """The surface's records of the elements `change` names (before) against the base's (after), read
    through the public queries. Vertices only where one appears or goes (a new one at the base's rest
    position): the positions of kept vertices are the caller's (they carry the mix)."""
    def vertex(mesh, v):
        if not mesh.is_valid_vertex(v):
            return None
        return tuple(surface.vertex_position(v)) if mesh is base and surface.is_valid_vertex(v) else tuple(mesh.vertex_position(v))

    def edge(mesh, e):
        return (*mesh.edge_vertices(e), tuple(mesh.edge_faces(e))) if mesh.is_valid_edge(e) else None

    def face(mesh, f):
        return tuple(mesh.face_vertices(f)) if mesh.is_valid_face(f) else None

    def uvs(mesh, f):
        return mesh.face_uvs(f) if mesh.is_valid_face(f) else None

    pairs = []
    for keys, read in ((change.vertices, vertex), (change.edges, edge), (change.faces, face)):
        pairs.append({k: (read(surface, k), read(base, k)) for k in keys if read(surface, k) != read(base, k)})
    uv_keys = set(change.faces) | set(change.face_uvs)
    face_uvs = {f: (uvs(surface, f), uvs(base, f)) for f in uv_keys if uvs(surface, f) != uvs(base, f)}
    return MeshDelta(*pairs, face_uvs=face_uvs)
