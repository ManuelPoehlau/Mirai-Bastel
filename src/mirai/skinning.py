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
from core.mesh import LayerKind
from core.rig import Rig, rest_frame
from core.scene import IDENTITY_TRANSFORM

from .morph_mix import topology_touched
from .surface_positions import SurfacePositions

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
        if self.layer is not None:
            for v, value in self.base.layer_items(self.layer):
                self._index(v, value)
        return before | set(self._values)

    def _index(self, v, value) -> None:
        old = self._values.pop(v, ())
        for k, _ in old:
            points = self._points_of.get(k)
            if points is not None:
                points.discard(v)
                if not points:
                    del self._points_of[k]
        if value:
            self._values[v] = value
            for k, _ in value:
                self._points_of.setdefault(k, set()).add(v)

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
            surface = SurfacePositions(base, self.input.vertex_position)
            for v in self._values:
                p = self._point(v)
                if p != self.input.vertex_position(v):
                    surface._owner_set(v, p)
            self.mesh = surface
            return True, set()
        candidates = set(change.vertices)
        if topology_touched(change, self.input):
            self.mesh._owner_follow_topology(change)
            self.topology_changed = True
        # the weights: a layer that came, went or was written whole re-indexes; else per key
        if layer != self.layer or layer in base_change.layer_whole:
            self.layer = layer
            candidates |= self._index_all()
        elif layer is not None and layer in base_change.layer_values:
            for v in base_change.layer_values[layer]:
                value = base.layer_value(layer, v) if base.is_valid_vertex(v) else ()
                self._index(v, value)
                candidates.add(v)
        # rig, pose, placement: the points of every bone whose transform changed
        if flat != self._flat:
            points_of = self._points_of
            for k in set(flat) | set(self._flat):
                if flat.get(k) != self._flat.get(k):
                    candidates |= points_of.get(k, set())
            self._flat = flat
        return False, self._recompute(candidates)

    def _point(self, v) -> Vec3:
        p = self.input.vertex_position(v)
        value = self._values.get(v)
        if value is None or not self._flat:
            return tuple(p)  # type: ignore[return-value]
        return skin_point(p, value, self._flat)

    def _recompute(self, candidates) -> set:
        """`_point` for every candidate, inlined (the pose-step hot loop; same arithmetic), written into the
        table where it differs (`SurfacePositions._owner_write`, inlined)."""
        valid, position = self.input.is_valid_vertex, self.input.vertex_position
        surface = self.mesh
        index, pos = surface._index, surface._pos
        values, flat = self._values, self._flat
        moved: dict = {}
        for v in candidates:
            if not valid(v):
                continue
            p = position(v)
            value = values.get(v)
            p = tuple(p) if value is None or not flat else skin_point(p, value, flat)
            s = index.get(v)
            if s is None:  # new in the base since the last update
                surface._owner_add(v, p)
                moved[v] = None
                continue
            old = pos[s]
            if old != p:
                moved[v] = old
                pos[s] = p
        surface._owner_record(moved)
        return set(moved)


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
