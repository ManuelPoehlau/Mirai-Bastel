"""Skinning evaluation (AD-028 §5): the pose model, linear blend skinning and the skin stage of the
viewport's surface chain (morph -> skin -> SubD). Names `PROVISIONAL`.

**Pose model** (§5.1). The pose is view state (§6): per bone a local similarity `L_b` (`BonePose`:
rotation, translation, uniform scale > 0) in the bone's rest frame `B_b = (R_b, h_b)` (`core.rig.rest_frame`);
identity = rest. The world skin transform runs down the hierarchy, `S_root = B·L·B⁻¹`,
`S_child = S_parent · (B_c·L_c·B_c⁻¹)`. **Exact identity short-circuit:** a bone whose own and every
ancestor's `L` is identity has no transform at all (`skin_transforms` leaves it out) - no product is
formed, so the rest pose is bit-exact; a bone with an identity `L` under a posed parent takes the
parent's transform as it is. **Placement conjugation:** the mesh lives in object space, so the
transforms are conjugated by the object's placement `T` (a similarity, AD-021 §4.3): `A_b = T⁻¹·S_b·T`;
an identity placement skips it.

**LBS** for a vertex with input position `p` (the morph mix, or the rest position) and weights
`((k, w_k), ...)`: `p' = c·p + Σ w_k·A_k·p` over the keys with a transform, in ascending key order, the
first term as it is (not added to 0.0, as in `morph_mix`), `c = 1 − Σ` of those weights (`math.fsum`) =
the object's share plus the weights of unposed or dead keys; `c == 0` drops the `c·p` term. A vertex
without a posed key is exactly `p`. Dead keys (no such bone) count as the object's share. Morph first,
skin second: an expression sculpted at rest rides the pose (F-15, audit §E). Normals stay the viewport's.

**`evaluate`** is the definition (the oracle, the SubD reference). **`SkinSurface`** shows it for one
bound mesh: a `SurfacePositions` (O1, 2026-11-11: a position table over the base's topology, a read-only
view with the `Mesh` queries - no longer a `core.Mesh` copy), patched in place like `morph_mix.MixSurface`
- candidates are the input's journal keys (positions, topology: SubD's pattern of following its input),
the base's weights-layer keys, and on a rig / pose / placement change the points with a key of a bone
whose transform changed (a bone -> points index kept in step with the weights journal). Every candidate
is recomputed from its inputs (the drift guard): the shown surface is a pure function of (input positions,
weights, rig, pose, placement), bit-identical whatever the order of pose steps, weight writes and edits.
Since O3 stage 2 (2026-11-13, AD-032 §11) it computes on arrays: its table mirrors the mix's slots (or keeps its own
over the base, with a cache of the base positions), the bone -> points index gives slot arrays, the posed terms of
every slot are padded arrays (width `WEIGHTS_WIDTH`) rebuilt only when a point's weights or the set of posed keys
change, and LBS runs column by column in the rule's order - bit-identical to `evaluate`.

**The stage** (`SkinSurfaceProvider`, `SkinDisplay`, §5.2): wanted only while the rig is posed and the edit
mesh (or the morph base beside its editing view, H7-E) has a weights layer; at rest the chain is
today's. While a later stage (SubD) is wanted it keeps the edit object's surface at rest too
(`keep_edit_surface`, as the morph stage does), so a rest <-> pose toggle patches positions instead of
switching SubD's input (a rebuild). Picking, selection, hover and every tool stay on the rest cage while
posed, also with a morph dialled in (MODELING_ON_DEFORMED_SURFACES §15 (b): the morph-mix picking stops in a
pose); the wire follows the surface. Only the edit object and the morph base beside its view show the pose
(§5.3, F-16).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Optional, Union

from core import Mesh, ObjectTransform
from core.layer_storage import WEIGHTS_WIDTH
from core.mesh import LayerKind
from core.rig import Rig, rest_frame
from core.scene import IDENTITY_TRANSFORM

from viewport.packed_geometry import np  # NumPy behind its pinned-version check (AD-032 §2)

from .morph_mix import topology_touched
from .surface_positions import MovedVertices, SurfacePositions, _grown

Vec3 = tuple[float, float, float]
Mat3 = tuple[Vec3, Vec3, Vec3]
#: x -> M·x + c (M as rows)
Affine = tuple[Mat3, Vec3]

_I3: Mat3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
_ZERO: Vec3 = (0.0, 0.0, 0.0)


# -- pose model --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class BonePose:
    """A bone's local similarity in its rest frame (§5.1): `x -> scale·rotation·x + translation`.
    Validated like `ObjectTransform` (rotation orthonormal with det +1, scale finite and > 0)."""

    rotation: Mat3 = _I3
    translation: Vec3 = _ZERO
    scale: float = 1.0

    def __post_init__(self) -> None:
        checked = ObjectTransform(translation=self.translation, rotation=self.rotation, scale=self.scale)
        object.__setattr__(self, "rotation", checked.rotation)
        object.__setattr__(self, "translation", checked.translation)
        object.__setattr__(self, "scale", checked.scale)

    @property
    def is_identity(self) -> bool:
        return self.rotation == _I3 and self.translation == _ZERO and self.scale == 1.0


REST = BonePose()

#: A pose: BoneId -> BonePose; absent and identity entries are rest.
Pose = Mapping
#: An object's placement: (transform, pivot), or None for the identity.
Placement = Optional[tuple]


def _matmul(a: Mat3, b: Mat3) -> Mat3:
    return tuple(  # type: ignore[return-value]
        tuple(a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j] for j in range(3)) for i in range(3)
    )


def _transpose(a: Mat3) -> Mat3:
    return ((a[0][0], a[1][0], a[2][0]), (a[0][1], a[1][1], a[2][1]), (a[0][2], a[1][2], a[2][2]))


def _apply(m: Mat3, v: Vec3) -> Vec3:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def _bone_world(local: BonePose, frame: tuple[Mat3, Vec3]) -> Affine:
    """`B·L·B⁻¹` as x -> M·x + c: M = s·R_b·R·R_bᵀ, c = R_b·t + h − M·h."""
    rb, h = frame
    m = _matmul(_matmul(rb, local.rotation), _transpose(rb))
    s = local.scale
    if s != 1.0:
        m = tuple(tuple(s * x for x in row) for row in m)  # type: ignore[assignment]
    rt = _apply(rb, local.translation)
    mh = _apply(m, h)
    return m, (rt[0] + h[0] - mh[0], rt[1] + h[1] - mh[1], rt[2] + h[2] - mh[2])


def _compose(outer: Affine, inner: Affine) -> Affine:
    """outer ∘ inner."""
    mo, co = outer
    mi, ci = inner
    c = _apply(mo, ci)
    return _matmul(mo, mi), (c[0] + co[0], c[1] + co[1], c[2] + co[2])


def skin_transforms(rig: Optional[Rig], pose: Pose) -> dict:
    """The world skin transform of every bone that moves: `{BoneId: Affine}`. A bone whose own and every
    ancestor's pose is identity is absent (exactly the rest); pose entries of bones the rig does not
    have are ignored."""
    out: dict = {}
    if rig is None or not pose:
        return out
    for bid in rig.topological_order():
        bone = rig.bone(bid)
        parent = out.get(bone.parent) if bone.parent is not None else None
        local = pose.get(bid)
        if local is None or local.is_identity:
            if parent is not None:
                out[bid] = parent  # the parent's transform as it is (no product with an identity)
            continue
        own = _bone_world(local, rest_frame(bone))
        out[bid] = own if parent is None else _compose(parent, own)
    return out


def placement_of(obj) -> Placement:
    """An object's placement for the conjugation (None = identity, skipped)."""
    if obj.transform == IDENTITY_TRANSFORM:
        return None
    return obj.transform, tuple(obj.pivot)


def object_transforms(world: dict, placement: Placement) -> dict:
    """`A_b = T⁻¹·S_b·T` per bone (§5.1); `placement` None returns `world` as it is."""
    if placement is None or not world:
        return world
    transform, pivot = placement
    rt, s = transform.rotation, transform.scale
    rp = _apply(rt, pivot)
    ct = tuple(transform.translation[i] + pivot[i] - s * rp[i] for i in range(3))  # T(p) = s·R_T·p + c_T
    rtt = _transpose(rt)
    out = {}
    for bid, (m, c) in world.items():
        ma = _matmul(_matmul(rtt, m), rt)
        mc = _apply(m, ct)
        d = _apply(rtt, (mc[0] + c[0] - ct[0], mc[1] + c[1] - ct[1], mc[2] + c[2] - ct[2]))
        out[bid] = (ma, (d[0] / s, d[1] / s, d[2] / s))
    return out


def _flat(transforms: dict) -> dict:
    """{key: (m00, m01, m02, c0, m10, ..., c2)} for the hot loop."""
    return {
        int(k): (m[0][0], m[0][1], m[0][2], c[0], m[1][0], m[1][1], m[1][2], c[1], m[2][0], m[2][1], m[2][2], c[2])
        for k, (m, c) in transforms.items()
    }


def skin_point(p, value, flat: dict) -> Vec3:
    """LBS of one point (module rule); `flat` from `_flat(object_transforms(...))`."""
    first = True
    posed = []
    for k, w in value:
        a = flat.get(k)
        if a is None:
            continue
        posed.append(w)
        x, y, z = p
        tx = w * (a[0] * x + a[1] * y + a[2] * z + a[3])
        ty = w * (a[4] * x + a[5] * y + a[6] * z + a[7])
        tz = w * (a[8] * x + a[9] * y + a[10] * z + a[11])
        if first:
            sx, sy, sz = tx, ty, tz
            first = False
        else:
            sx += tx
            sy += ty
            sz += tz
    if first:
        return tuple(p)  # type: ignore[return-value]
    c = 1.0 - math.fsum(posed)
    if c == 0.0:
        return (sx, sy, sz)
    return (c * p[0] + sx, c * p[1] + sy, c * p[2] + sz)


def skin_layer(mesh: Mesh):
    """The mesh's skin layer: its first WEIGHTS layer in display order (the app binds one), or None."""
    for lid in mesh.point_layer_ids():
        if mesh.point_layer_info(lid).kind is LayerKind.WEIGHTS:
            return lid
    return None


def is_posed(rig: Optional[Rig], pose: Pose) -> bool:
    """Some bone of the rig has a non-identity pose (AD-028 §7.1 "posed")."""
    return rig is not None and any(not p.is_identity and rig.has_bone(b) for b, p in pose.items())


def evaluate(
    base: Mesh,
    input_positions: Union[Mesh, SurfacePositions, Mapping, None],
    rig: Optional[Rig],
    pose: Pose,
    placement: Placement = None,
    layer=None,
) -> dict:
    """The definition (§5.1) for every vertex of `base`: `{VertexId: position}`. `input_positions` is a
    mesh or a `SurfacePositions` with the base's IDs (the morph mix) or a mapping; None = the base's rest
    positions. `layer` defaults to `skin_layer(base)`; without a weights layer every point is its input."""
    if input_positions is None:
        position = base.vertex_position
    elif isinstance(input_positions, Mapping):
        position = input_positions.__getitem__
    else:
        position = input_positions.vertex_position
    lid = skin_layer(base) if layer is None else layer
    flat = _flat(object_transforms(skin_transforms(rig, pose), placement))
    out = {}
    for v in base.all_vertex_ids():
        p = position(v)
        out[v] = skin_point(p, base.layer_value(lid, v), flat) if lid is not None and flat else tuple(p)
    return out


# -- the evaluated surface of one bound mesh ------------------------------------------------------------


class SkinSurface:
    """The skinned surface of one base mesh (module docstring). `input` is what is skinned: the base itself,
    or the morph mix of it (a `SurfacePositions` over the same base: same IDs and topology)."""

    def __init__(self, base: Mesh, input_mesh: Union[Mesh, SurfacePositions]) -> None:
        self.base = base
        self.input = input_mesh
        self._input_watch = input_mesh.watch()
        self._base_watch = None if input_mesh is base else base.watch()
        #: the shown surface: a `SurfacePositions` over the base's topology (None until the first `update`)
        self.mesh: Optional[SurfacePositions] = None
        #: True right after an `update` that patched the topology of `mesh` in place (H7)
        self.topology_changed = False
        self.layer = None
        self._flat: dict = {}
        # VertexId -> its weights value: a cache of the layer kept in step through the journal (as the
        # mix caches its offsets) and the bone index's inverse
        self._values: dict = {}
        self._points_of: dict = {}  # key -> set of VertexIds
        # -- on the table's slots (AD-032 §11.2) --
        #: the input is a table whose slots this one mirrors (the mix); else the input is the base
        self._table_input = isinstance(input_mesh, SurfacePositions)
        #: the input positions when the input is the base (refreshed for what its journal names); None = `input.P`
        self._X = None
        self._key_slots: dict = {}  # key -> its points' slots (ascending), rebuilt when its set or the slots change
        self._key_row: dict = {}  # key -> row of `_T`
        self._T = np.zeros((0, 12))  # per key row: the flat transform (m00, m01, m02, c0, m10, ..., c2)
        # the posed terms of every slot, in the value's order: transform row, weight; their count; c and c == 0
        self._tn = np.zeros(0, dtype=np.intp)
        self._tk = np.zeros((0, WEIGHTS_WIDTH), dtype=np.intp)
        self._tw = np.zeros((0, WEIGHTS_WIDTH))
        self._tc = np.zeros(0)
        self._tcz = np.zeros(0, dtype=bool)

    def close(self) -> None:
        self._input_watch.close()
        if self._base_watch is not None:
            self._base_watch.close()

    def pending(self) -> bool:
        if not self._input_watch.peek().is_empty():
            return True
        return self._base_watch is not None and not self._base_watch.peek().is_empty()

    # -- the bone -> points index ----------------------------------------------------------------

    def _index_all(self) -> set:
        """Rebuilds the index from the layer; returns every point it names before and after."""
        before = set(self._values)
        self._values, self._points_of = {}, {}
        self._key_slots.clear()
        if self.layer is not None:
            for v, value in self.base.layer_items(self.layer):
                self._index(v, value)
        return before | set(self._values)

    def _index(self, v, value) -> None:
        old = self._values.pop(v, ())
        key_slots = self._key_slots
        for k, _ in old:
            points = self._points_of.get(k)
            if points is not None:
                points.discard(v)
                key_slots.pop(k, None)
                if not points:
                    del self._points_of[k]
        if value:
            self._values[v] = value
            for k, _ in value:
                self._points_of.setdefault(k, set()).add(v)
                key_slots.pop(k, None)

    def _slots_of_key(self, k):
        """The slots of the points with key `k` (ascending; points the table does not hold are skipped)."""
        got = self._key_slots.get(k)
        if got is None:
            index = self.mesh._index
            points = [index[v] for v in self._points_of.get(k, ()) if v in index]
            got = self._key_slots[k] = np.sort(np.asarray(points, dtype=np.intp))
        return got

    # -- the posed terms (AD-032 §11.2) -------------------------------------------------------------

    def _fit(self) -> None:
        capacity = self.mesh.capacity
        if len(self._tn) < capacity:
            self._tn = _grown(self._tn, capacity, 0)
            self._tk = _grown(self._tk, capacity, 0)
            self._tw = _grown(self._tw, capacity, 0.0)
            self._tc = _grown(self._tc, capacity, 0.0)
            self._tcz = _grown(self._tcz, capacity, False)
            if self._X is not None:
                self._X = _grown(self._X, capacity, 0.0)

    def _set_transforms(self) -> None:
        """`_T` rows of the keys with a transform now (a key keeps its row for the stage's life)."""
        rows = self._key_row
        for k in self._flat:
            if k not in rows:
                rows[k] = len(rows)
        if len(self._T) < len(rows):
            self._T = _grown(self._T, len(rows), 0.0)
        for k, a in self._flat.items():
            self._T[rows[k]] = a

    def _rebuild_terms(self, vertex_ids) -> None:
        """The posed terms of the held `vertex_ids` under `_flat`: per key with a transform, in the value's order, its
        `_T` row and weight; `c = 1.0 - math.fsum(...)` of those weights (as `skin_point`)."""
        index, values, flat, rows = self.mesh._index, self._values, self._flat, self._key_row
        slots, counts, keys, weights, cs = [], [], [], [], []
        pad_k, pad_w = [0] * WEIGHTS_WIDTH, [0.0] * WEIGHTS_WIDTH
        for v in vertex_ids:
            s = index.get(v)
            if s is None:
                continue
            value = values.get(v)
            posed = [(rows[k], w) for k, w in value if k in flat] if value and flat else ()
            n = len(posed)
            slots.append(s)
            counts.append(n)
            keys.append([k for k, _ in posed] + pad_k[n:])
            ws = [w for _, w in posed]
            weights.append(ws + pad_w[n:])
            cs.append(1.0 - math.fsum(ws) if n else 1.0)
        if not slots:
            return
        slots = np.asarray(slots, dtype=np.intp)
        self._tn[slots] = counts
        self._tk[slots] = keys
        self._tw[slots] = weights
        c = np.asarray(cs)
        self._tc[slots] = c
        self._tcz[slots] = c == 0.0

    def _inputs(self):
        return self._X if self._X is not None else self.input.position_array()

    def _skin(self, slots, X) -> "np.ndarray":
        """LBS of held `slots` (`skin_point`, bit for bit): per term column j, `w * (((a0*x + a1*y) + a2*z) + a3)` per
        component, the first term as it is, then `+=`; `c*p + sum`, or the sum where c == 0.0; a point without a
        posed term is its input as it is."""
        out = X[slots]
        counts = self._tn[slots]
        posed = np.flatnonzero(counts)
        if not len(posed):
            return out
        sl, n = slots[posed], counts[posed]
        nmin, nmax = int(n.min()), int(n.max())
        if nmin != nmax:  # most terms first: the slots that still have a term j are a prefix
            order = np.argsort(-n, kind="stable")
            posed, sl, n = posed[order], sl[order], n[order]
        p = out[posed]
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        neg = -n
        T, tk, tw = self._T, self._tk, self._tw
        acc = np.empty((len(sl), 3))
        for j in range(nmax):
            m = len(sl) if j < nmin else int(np.searchsorted(neg, -j, side="left"))
            a = T[tk[sl[:m], j]]
            w = tw[sl[:m], j]
            xm, ym, zm = x[:m], y[:m], z[:m]
            for axis in range(3):
                r = 4 * axis
                t = a[:, r] * xm
                t += a[:, r + 1] * ym
                t += a[:, r + 2] * zm
                t += a[:, r + 3]
                t *= w
                if j == 0:
                    acc[:, axis] = t
                else:
                    acc[:m, axis] += t
        rest = ~self._tcz[sl]
        if rest.any():
            acc[rest] = self._tc[sl[rest], None] * p[rest] + acc[rest]
        out[posed] = acc
        return out

    # -- update ----------------------------------------------------------------------------------

    def update(self, rig: Optional[Rig], pose: Pose, placement: Placement) -> tuple[bool, set]:
        """Shows the inputs now. Returns (rebuilt = a new `mesh` object, changed vertices of the kept one)."""
        base = self.base
        flat = _flat(object_transforms(skin_transforms(rig, pose), placement))
        change = self._input_watch.take()
        base_change = change if self._base_watch is None else self._base_watch.take()
        self.topology_changed = False
        layer = skin_layer(base)
        if self.mesh is None:
            self.layer = layer
            self._index_all()
            self._flat = flat
            layout = self.input if self._table_input else None
            surface = self.mesh = SurfacePositions(base, None if layout is not None else self.input.vertex_position,
                                                   layout=layout)
            if layout is None:
                self._X = surface.P.copy()
            self._fit()
            self._set_transforms()
            self._rebuild_terms(self._values)
            if self._values:
                slots = np.unique(surface.table_slots(list(self._values)))
                surface._owner_write_slots(slots, self._skin(slots, self._inputs()))  # nobody watches yet
            return True, set()
        surface = self.mesh
        index = surface._index
        candidates: list = []  # slot arrays
        named: set = set()  # VertexIds
        dirty: set = set()  # VertexIds whose posed terms are rebuilt
        new_slots = None
        moves = change.slot_moves() if self._table_input else None
        if moves is not None:
            candidates.append(moves)
        else:
            vertices = change.vertices
            if topology_touched(change, self.input):
                surface._owner_follow_topology(change)
                self._key_slots.clear()
                self.topology_changed = True
            valid = self.input.is_valid_vertex
            new = [v for v in vertices if v not in index and valid(v)]
            if new:  # a slot each (the mix's, mirrored); the row is written below, the base's cache with `held`
                new_slots = np.fromiter((surface._owner_add(v, (0.0, 0.0, 0.0)) for v in new), dtype=np.intp,
                                        count=len(new))
                surface._owner_record(dict.fromkeys(new))
                self._key_slots.clear()
                self._fit()
                dirty.update(new)
            held = [v for v in vertices if v in index and valid(v)]
            if held and self._X is not None:  # the base's positions the journal names
                self._X[surface.table_slots(held)] = [base.vertex_position(v) for v in held]
            named.update(held)
        # the weights: a layer that came, went or was written whole re-indexes; else per key
        if layer != self.layer or layer in base_change.layer_whole:
            self.layer = layer
            touched = self._index_all()
            named |= touched
            dirty |= touched
        elif layer is not None and layer in base_change.layer_values:
            for v in base_change.layer_values[layer]:
                value = base.layer_value(layer, v) if base.is_valid_vertex(v) else ()
                self._index(v, value)
                named.add(v)
                dirty.add(v)
        # rig, pose, placement: the points of every bone whose transform changed
        if flat != self._flat:
            old = self._flat
            for k in set(flat) | set(old):
                if flat.get(k) != old.get(k):
                    candidates.append(self._slots_of_key(k))
                    if (k in flat) != (k in old):  # posed <-> not: the terms of its points change
                        dirty |= self._points_of.get(k, set())
            self._flat = flat
            self._set_transforms()
        if dirty:
            self._rebuild_terms(dirty)
        if named:
            held = [v for v in named if v in index]
            if held:
                candidates.append(np.unique(surface.table_slots(held)))
        if new_slots is not None:
            candidates.append(new_slots)
        return False, self._recompute(candidates, new_slots)

    def _recompute(self, candidates: list, new_slots=None) -> MovedVertices:
        """LBS for every candidate slot (`_skin`), written into the table where it differs and recorded as one chunk;
        new vertices are written as they are (recorded by id). Returns the changed vertices (new ones included)."""
        surface = self.mesh
        if not candidates:
            return surface._owner_moved(np.zeros(0, dtype=np.intp))
        slots = np.unique(np.concatenate(candidates)) if len(candidates) > 1 else candidates[0]
        slots = slots[surface._held[slots]]
        always = None
        if new_slots is not None:
            always = np.zeros(len(slots), dtype=bool)
            always[np.searchsorted(slots, new_slots)] = True
        changed = surface._owner_write_slots(slots, self._skin(slots, self._inputs()), always)
        if new_slots is not None:
            changed = np.union1d(changed, new_slots)
        return surface._owner_moved(changed)


# -- the stage ------------------------------------------------------------------------------------------


def _has_weights(mesh) -> bool:
    return mesh is not None and skin_layer(mesh) is not None


class SkinSurfaceProvider:
    """H7 provider of the skin stage (`sync(mesh, selection) -> moved`, `surface_mesh`, `dirty`, H7-E
    `entry_surfaces` / `entry_moved`). `mesh` in `sync` is the stage's input (the edit mesh, or the morph
    mix of it); the base is the edit object's mesh. Never writes a scene mesh."""

    def __init__(
        self,
        scene_of: Callable,
        upstream_entries: Callable[[], dict] = dict,
        beside: Callable[[], tuple] = tuple,
    ) -> None:
        self._scene_of = scene_of
        #: the morph stage's entry surfaces while that stage runs (the input of a base beside its view)
        self._upstream_entries = upstream_entries
        #: ObjectIds shown beside the edit object (the morph base beside its editing view, §5.2 H7-E)
        self._beside = beside
        #: the pose, view state (§6): BoneId -> BonePose; set through `set_pose` (slice 3: the SkeletonController)
        self.pose: dict = {}
        #: the edit object's posed surface (a `SurfacePositions`, O1), None = not shown
        self.surface_mesh: Optional[SurfacePositions] = None
        self.entry_surfaces: dict = {}
        self.entry_moved: dict = {}
        self.surface_topology_changed = False
        self.entry_topology_changed: set = set()
        #: the wire is drawn at the posed surface (as for the mix); picking stays on the rest cage
        self.wire_follows_surface = True
        #: show the edit object's surface at rest too while a later stage (SubD) reads it (§5.2)
        self.keep_edit_surface = False
        self._surfaces: dict = {}
        self._dirty = False
        self._seen: tuple = ()

    def reset(self) -> None:
        """A new scene: the pose is not saved (a load starts at rest, §6)."""
        for surface in self._surfaces.values():
            surface.close()
        self._surfaces.clear()
        self.pose = {}
        self.surface_mesh = None
        self.entry_surfaces, self.entry_moved = {}, {}
        self._dirty = True

    def set_pose(self, pose: Mapping) -> None:
        """Replaces the pose (identity entries dropped). View state: no History, not saved."""
        self.pose = {b: p for b, p in pose.items() if not p.is_identity}
        self._dirty = True

    def posed(self) -> bool:
        return is_posed(self._scene_of().rig, self.pose)

    def shown(self) -> dict:
        """ObjectId -> object of what the stage shows now: the edit object while posed (or kept, see
        `keep_edit_surface`) and the bases beside it while posed - each only with a weights layer."""
        scene = self._scene_of()
        if scene.rig is None:
            return {}
        posed = self.posed()
        out = {}
        edit = scene.edit_object
        if (posed or self.keep_edit_surface) and _has_weights(edit.mesh):
            out[edit.id] = edit
        if posed:
            for oid in self._beside():
                obj = scene.objects.get(oid)
                if obj is not None and oid != edit.id and _has_weights(obj.mesh):
                    out[oid] = obj
        return out

    def wants_surface(self) -> bool:
        return bool(self.shown())

    def _inputs_key(self) -> tuple:
        scene = self._scene_of()
        return (
            scene.rig,
            tuple((oid, obj.transform, obj.pivot) for oid, obj in scene.objects.items() if oid in self._surfaces),
        )

    @property
    def dirty(self) -> bool:
        if self._dirty or any(s.pending() for s in self._surfaces.values()):
            return True
        return bool(self._surfaces) and self._inputs_key() != self._seen

    @dirty.setter
    def dirty(self, value: bool) -> None:
        self._dirty = bool(value)

    def sync(self, mesh, selection) -> set:
        self._dirty = False
        scene = self._scene_of()
        shown = self.shown()
        upstream = self._upstream_entries() or {}
        edit_id = scene.edit_object_id
        for oid, surface in list(self._surfaces.items()):
            obj = shown.get(oid)
            wanted_input = None if obj is None else (mesh if oid == edit_id else upstream.get(oid, obj.mesh))
            if obj is None or obj.mesh is not surface.base or surface.input is not wanted_input:
                self._surfaces.pop(oid).close()
        self.surface_mesh = None
        self.entry_surfaces, self.entry_moved = {}, {}
        self.surface_topology_changed, self.entry_topology_changed = False, set()
        moved_edit: set = set()
        for oid, obj in shown.items():
            surface = self._surfaces.get(oid)
            if surface is None:
                source = mesh if oid == edit_id else upstream.get(oid, obj.mesh)
                surface = self._surfaces[oid] = SkinSurface(obj.mesh, source)
            rebuilt, changed = surface.update(scene.rig, self.pose, placement_of(obj))
            if oid == edit_id:
                self.surface_mesh = surface.mesh
                moved_edit = set() if rebuilt else changed
                self.surface_topology_changed = surface.topology_changed
            else:
                self.entry_surfaces[oid] = surface.mesh
                self.entry_moved[oid] = set() if rebuilt else changed
                if surface.topology_changed:
                    self.entry_topology_changed.add(oid)
        self._seen = self._inputs_key()
        return moved_edit


class SkinDisplay:
    """The skin provider and its stage in the app's surface chain (as `MorphDisplay`): wanted while the
    provider has something to show; keeps the edit object's surface at rest while a later stage reads it."""

    def __init__(self, scene_of: Callable, upstream_entries: Callable[[], dict] = dict, beside: Callable[[], tuple] = tuple) -> None:
        self.provider = SkinSurfaceProvider(scene_of, upstream_entries, beside)
        self.viewport = None
        self.chain = None

    def attach(self, viewport) -> None:
        self.viewport = viewport
        self.provider.reset()

    def owns_slot(self) -> bool:
        if self.viewport is None or self.chain is None:
            return False
        return self.chain.holds(self.provider)

    def refresh(self) -> None:
        if self.viewport is None or self.chain is None:
            return
        provider = self.provider
        provider.keep_edit_surface = self.chain.later_stage_wanted(provider)
        self.chain.want(provider, provider.wants_surface())
