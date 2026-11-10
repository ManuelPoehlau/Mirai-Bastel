"""The assembly kernel of AD-031 (P1): copy whole meshes into another object's mesh (Attach) and faces out into a new
mesh (Detach, Separate by Islands). Names `PROVISIONAL`.

Pure data operations over the public `core.Mesh` API — no `Application`, no history, no viewport. The commands of P2/P3
wrap them in `Application._mesh_transaction` (one recording, one Undo step) and own every artist-facing policy that
AD-031 §10 still leaves open (O-1, O-2, O-5, O-7, …); this module decides none of them.

- `append_objects(dst, sources)` (AD-031 §2.1, §3): every source's vertices, faces (with their corner UVs), loose
  edges, point layers and regions become new elements of `dst.mesh`, placed so the world shape is unchanged. The
  destination's own elements, layers, regions and symmetry definition are not touched. Atomic: all checks run before
  the first write, the writes run inside a nested change recording (the `core.operations.collapse_elements` pattern)
  that is rolled back exactly on any failure — standalone or inside a caller's `_mesh_transaction`. The one check that
  needs the result (symmetry, D4) runs inside that recording; a refusal there leaves only the id counters forward
  (AD-001).
- `extract_faces(mesh, faces)` (AD-031 §2.2): a new, independent mesh of those faces in the same object space
  (positions bit-identical), with every point layer, the corner UVs and the regions restricted to them. `mesh` is only
  read. Loose edges are not carried (Detach works on faces).
- `look_differences(dst, sources)` (§3.1), `incoming_unweighted(sources)` (§3.2, O-5), `check_append(dst, sources)`
  and `derived_symmetry(mesh, axis)` (§3.5) are the read-only plans the commands consult.
- `linked_faces(mesh, seeds)` (P3): the face-connected part ("island") of `seeds` - faces joined across a shared
  edge, the face components `symmetry_topology.topological_sides` counts (without a seam). Select Linked selects it
  for Detach; Separate by Islands (P7) splits by the same definition.

Data rules (AD-031 §3; never merged by name, never dropped silently):

- **Positions:** `object_space.to_object(dst, to_world(src, p))`; verbatim when transform and pivot are equal.
- **Morph targets (`VECTOR` layers):** always a new layer named `"<source object> · <target>"` (`" 2"`, `" 3"` … while
  taken), `kind` and `new_point` copied, values mapped by the placements' linear part (`delta_to_object(dst,
  delta_to_world(src, v))`, the frame-change rule of AD-025 §4.3); destination targets get the default for the new
  points. More than `MAX_TARGETS` targets afterwards → refused.
- **Skin weights (`WEIGHTS`):** merged into the destination's one weights layer (created as `"Skin"` if absent),
  values unchanged — keys are the scene rig's `BoneId`s and skinning is placement-invariant (AD-028 §3.2). A mesh with
  more than one weights layer → refused. New points of a source without weights stay unbound; the count is reported
  (`AppendResult.unweighted`); whether that is acceptable is the command's decision (O-5: refused for a bound
  destination unless the artist overrides it).
- **Regions:** every source region is carried with its live faces, in source order; a free name stays, a taken
  `Group N` is renumbered with `regions.new_group_name`, any other taken name becomes `"<source object> · <name>"`
  (then `" 2"` …). The tint follows the name (`regions.slot_index`), so a renamed region changes colour (§3.3). Dead
  ids are not carried; a region without live faces is carried empty, so no name is lost. With `ungrouped_region`
  (O-7, the command's choice) a source's live faces in none of its regions become one more region named after the
  source object, by the same naming rule, after that source's regions.
- **Symmetry:** the destination's definition is never edited; source definitions are dropped. With a definition set,
  the append is refused (and rolled back) when it introduces or worsens an AMBIGUOUS correspondence (D4: a vertex
  AMBIGUOUS afterwards that was not before, or an already AMBIGUOUS vertex with more candidates than before - an
  ambiguous correspondence silently switches mirroring off for those points); an unrelated pre-existing AMBIGUOUS
  vertex is no reason to refuse; PARTIAL is reported, not refused.
- **Order:** sources in `ObjectId` order, elements in ascending id order — the result is deterministic.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from core import FaceId, FaceRegion, FaceRegions, LayerId, Mesh, ObjectId, SceneObject, SymmetryDefinition, VertexId
from core.mesh import LayerKind, PointLayerInfo

from . import object_space
from .morph_targets import MAX_TARGETS
from .regions import new_group_name
from .symmetry import CorrespondenceState, SymmetryState, mirror_position, symmetry_state, vertex_correspondence
from .symmetry_axis import definition_for_axis

#: Joins a source object's name and a carried target / region name (AD-031 D2, D2b).
NAME_SEPARATOR = " · "
#: The name a destination's weights layer gets when a source brings the first one (AD-028 §3.3).
SKIN_LAYER_NAME = "Skin"
#: An automatic group name (`regions.new_group_name`'s pattern): renumbered on a collision instead of prefixed.
_GROUP_NAME = re.compile(r"Group (\d+)$")


class AssemblyRefused(ValueError):
    """The operation would lose or corrupt data, or its input is invalid; nothing was changed. `str(exc)` says why."""


@dataclass(frozen=True)
class AppendResult:
    """What `append_objects` did, per source `ObjectId`: the vertex, face and point-layer id maps (source -> destination)
    and the region names (source name -> name in the destination); `ungrouped_regions`: source -> the name of the
    region made for its ungrouped faces (only with `ungrouped_region`, only for a source that has such faces).
    `unweighted`: appended points without a weight (the empty value `()`) in a destination that has a weights layer
    afterwards (0 without one; the destination's own points are never counted). `symmetry_before` / `_after`: the
    destination's state (`SymmetryState.OFF` without a definition)."""

    vertex_maps: Mapping[ObjectId, Mapping[VertexId, VertexId]]
    face_maps: Mapping[ObjectId, Mapping[FaceId, FaceId]]
    layer_maps: Mapping[ObjectId, Mapping[LayerId, LayerId]]
    region_names: Mapping[ObjectId, Mapping[str, str]]
    unweighted: int
    symmetry_before: SymmetryState
    symmetry_after: SymmetryState
    ungrouped_regions: Mapping[ObjectId, str]


@dataclass(frozen=True)
class ExtractResult:
    """The new mesh and the id maps from the source mesh (`vertex_map`, `face_map`)."""

    mesh: Mesh
    vertex_map: Mapping[VertexId, VertexId]
    face_map: Mapping[FaceId, FaceId]


# -- read-only plans ------------------------------------------------------------------------------------------------


def look_of(obj: SceneObject) -> tuple:
    """An object's look (AD-031 §3.1): `(material, texture)`; `None` is the app's default for either."""
    return (obj.material, obj.texture)


def look_differences(dst: SceneObject, sources: Iterable[SceneObject]) -> tuple[SceneObject, ...]:
    """The sources whose look differs from the destination's, in `ObjectId` order (empty = Attach may run; otherwise
    only the explicit "take destination look" variant may, D1)."""
    look = look_of(dst)
    return tuple(sorted((s for s in sources if look_of(s) != look), key=lambda s: int(s.id)))


def incoming_unweighted(sources: Iterable[SceneObject]) -> int:
    """How many points of `sources` would arrive without a skin weight (AD-031 §3.2, O-5): all points of a source
    without a weights layer, else its points with the empty value `()` (the Core stores an all-zero value as `()`, so
    missing and zero weights are one case; a partial value counts as weighted). Read-only; for a destination that
    has a weights layer it equals `AppendResult.unweighted` of the append."""
    count = 0
    for src in sources:
        mesh = src.mesh
        layers = _weights_layers(mesh)
        if not layers:
            count += len(mesh.all_vertex_ids())
        else:
            count += sum(1 for v in mesh.all_vertex_ids() if not mesh.layer_value(layers[0], v))
    return count


def derived_symmetry(mesh: Mesh, axis: str | None) -> SymmetryDefinition | None:
    """The definition a detached mesh gets (AD-031 §3.5, D5): Shift+S's own rule for `axis`
    (`symmetry_axis.definition_for_axis`, seam = the edges exactly on the plane) when the mesh is VALID under it,
    else None. `mesh` is left as it was (its definition is restored); meant for a fresh mesh without a recording."""
    definition = definition_for_axis(mesh, axis)
    if definition is None:
        return None
    previous = mesh.symmetry_definition
    mesh.symmetry_definition = definition
    try:
        valid = symmetry_state(mesh) is SymmetryState.VALID
    finally:
        mesh.symmetry_definition = previous
    return definition if valid else None


def linked_faces(mesh: Mesh, seeds: Iterable[FaceId]) -> frozenset[FaceId]:
    """The faces connected to `seeds` across shared edges (AD-031 P3, the island definition of Detach and Separate by
    Islands): a face that touches the part only at a vertex is another island. Read-only; invalid seeds are
    ignored, so no valid seed gives the empty set."""
    found = {f for f in seeds if mesh.is_valid_face(f)}
    todo = list(found)
    while todo:
        for edge in mesh.face_edges(todo.pop()):
            for other in mesh.edge_faces(edge):
                if other not in found:
                    found.add(other)
                    todo.append(other)
    return frozenset(found)


# -- append -----------------------------------------------------------------------------------------------------------


def append_objects(
    dst: SceneObject, sources: Sequence[SceneObject], *, ungrouped_region: bool = False
) -> AppendResult:
    """Appends every source's mesh to `dst.mesh` (module docstring). Sources are only read. `ungrouped_region`: a
    source's faces in none of its regions join a new region named after the source (O-7). Raises `AssemblyRefused`
    with `dst.mesh` unchanged; any other failure during the writes is rolled back exactly and re-raised."""
    ordered = _checked_sources(dst, sources)
    mesh = dst.mesh
    layer_plan = _plan_layers(mesh, ordered)
    region_plan, ungrouped_plan = _plan_regions(mesh, ordered, ungrouped_region)
    has_definition = mesh.symmetry_definition is not None
    before = symmetry_state(mesh)
    ambiguity_before = _ambiguity(mesh) if has_definition else {}

    change = mesh.begin_change()
    try:
        result = _append(dst, ordered, layer_plan, region_plan, ungrouped_plan)
        after = symmetry_state(mesh)
        if has_definition:
            ambiguity = _ambiguity(mesh)
            newly = [v for v in ambiguity if v not in ambiguity_before]
            worse = [v for v, n in ambiguity.items() if v in ambiguity_before and n > ambiguity_before[v]]
            if newly or worse:
                raise AssemblyRefused(
                    f"{len(newly) + len(worse)} point(s) would make the symmetry ambiguous (coincident points) - "
                    "move the part or switch symmetry off (Shift+S)"
                )
    except BaseException:
        mesh.rollback_change(change)
        raise
    mesh.release_change(change)
    vertex_maps, face_maps, layer_maps, unweighted = result
    return AppendResult(
        vertex_maps=vertex_maps,
        face_maps=face_maps,
        layer_maps=layer_maps,
        region_names={oid: dict(names) for oid, names in region_plan.items()},
        unweighted=unweighted,
        symmetry_before=before,
        symmetry_after=after,
        ungrouped_regions={oid: name for oid, (name, _) in ungrouped_plan.items()},
    )


def check_append(dst: SceneObject, sources: Sequence[SceneObject]) -> None:
    """Raises the `AssemblyRefused` that `append_objects(dst, sources)` would raise before its first write (input,
    weights layers, `MAX_TARGETS`, layer kinds); read-only. The symmetry check (D4) needs the result and is not here."""
    _plan_layers(dst.mesh, _checked_sources(dst, sources))


def _checked_sources(dst: SceneObject, sources: Sequence[SceneObject]) -> list[SceneObject]:
    ordered = sorted(sources, key=lambda s: int(s.id))
    if not ordered:
        raise AssemblyRefused("no source object")
    ids = [s.id for s in ordered]
    if len(set(ids)) != len(ids):
        raise AssemblyRefused("a source object is named twice")
    if dst.id in ids:
        raise AssemblyRefused(f"{dst.name!r} cannot be attached to itself")
    meshes = [dst.mesh] + [s.mesh for s in ordered]
    if len({id(m) for m in meshes}) != len(meshes):
        raise AssemblyRefused("two of the objects share one mesh")
    return ordered


def _free(name: str, taken: set[str]) -> str:
    if name not in taken:
        return name
    n = 2
    while f"{name} {n}" in taken:
        n += 1
    return f"{name} {n}"


def _weights_layers(mesh: Mesh) -> list[LayerId]:
    return [lid for lid in mesh.point_layer_ids() if mesh.point_layer_info(lid).kind is LayerKind.WEIGHTS]


@dataclass(frozen=True)
class _LayerPlan:
    #: the destination's weights layer, or the info of the one to create (exactly one of them, or neither)
    skin: LayerId | None
    new_skin: PointLayerInfo | None
    #: per source: [(source layer, info of the new vector layer | None = goes into the skin layer)]
    per_source: Mapping[ObjectId, list[tuple[LayerId, PointLayerInfo | None]]]


def _plan_layers(mesh: Mesh, sources: list[SceneObject]) -> _LayerPlan:
    """Names and kinds of every carried layer, decided before the first write (AD-031 §3.2)."""
    dst_weights = _weights_layers(mesh)
    if len(dst_weights) > 1:
        raise AssemblyRefused("the destination has more than one weights layer")
    taken = {mesh.point_layer_info(lid).name for lid in mesh.point_layer_ids()}
    vectors = sum(1 for lid in mesh.point_layer_ids() if mesh.point_layer_info(lid).kind is LayerKind.VECTOR)
    skin = dst_weights[0] if dst_weights else None
    new_skin = None
    per_source: dict[ObjectId, list] = {}
    for src in sources:
        if len(_weights_layers(src.mesh)) > 1:
            raise AssemblyRefused(f"{src.name!r} has more than one weights layer")
        plan = []
        for lid in src.mesh.point_layer_ids():
            info = src.mesh.point_layer_info(lid)
            if info.kind is LayerKind.WEIGHTS:
                if skin is None and new_skin is None:
                    new_skin = PointLayerInfo(_free(SKIN_LAYER_NAME, taken), LayerKind.WEIGHTS)
                    taken.add(new_skin.name)
                plan.append((lid, None))
            elif info.kind is LayerKind.VECTOR:
                name = _free(f"{src.name}{NAME_SEPARATOR}{info.name}", taken)
                taken.add(name)
                vectors += 1
                plan.append((lid, PointLayerInfo(name, LayerKind.VECTOR, info.new_point)))
            else:  # a kind this kernel has no rule for: refuse rather than drop it
                raise AssemblyRefused(f"{src.name!r}: layer {info.name!r} has an unsupported kind {info.kind!r}")
        per_source[src.id] = plan
    if vectors > MAX_TARGETS:
        raise AssemblyRefused(f"the result would have {vectors} morph targets (at most {MAX_TARGETS})")
    return _LayerPlan(skin, new_skin, per_source)


def _region_name(name: str, names: list[str], src: SceneObject) -> str:
    """The collision-free name of a carried region (AD-031 §3.3, D2b): a free name stays, a taken `Group N` is
    renumbered, any other taken name becomes `"<source object> · <name>"` (then `" 2"` …)."""
    if name not in names:
        return name
    if _GROUP_NAME.match(name):
        return new_group_name(FaceRegions(tuple(FaceRegion(n) for n in names)))
    return _free(f"{src.name}{NAME_SEPARATOR}{name}", set(names))


def _plan_regions(
    mesh: Mesh, sources: list[SceneObject], ungrouped_region: bool
) -> tuple[dict[ObjectId, dict[str, str]], dict[ObjectId, tuple[str, list[FaceId]]]]:
    """Per source: region name -> its collision-free name in the destination (AD-031 §3.3, D2b); and, with
    `ungrouped_region`, per source with ungrouped live faces: (the new region's name, those faces) (O-7)."""
    names = [r.name for r in mesh.face_regions.regions] if mesh.face_regions is not None else []
    plan: dict[ObjectId, dict[str, str]] = {}
    ungrouped: dict[ObjectId, tuple[str, list[FaceId]]] = {}
    for src in sources:
        renamed: dict[str, str] = {}
        regions = src.mesh.face_regions
        for region in regions.regions if regions is not None else ():
            name = _region_name(region.name, names, src)
            names.append(name)
            renamed[region.name] = name
        plan[src.id] = renamed
        if ungrouped_region:
            grouped = set().union(*(r.faces for r in regions.regions)) if regions is not None else set()
            faces = [f for f in sorted(src.mesh.all_face_ids(), key=int) if f not in grouped]
            if faces:
                name = _region_name(src.name, names, src)
                names.append(name)
                ungrouped[src.id] = (name, faces)
    return plan, ungrouped


def _ambiguity(mesh: Mesh) -> dict[VertexId, int]:
    """The AMBIGUOUS vertices and their candidate counts (`symmetry.vertex_correspondence`'s rule: the other points
    exactly at the mirrored position). A count that grows is a worsened ambiguity (D4)."""
    ambiguous = [v for v, c in vertex_correspondence(mesh).items() if c.state is CorrespondenceState.AMBIGUOUS]
    if not ambiguous:
        return {}
    definition = mesh.symmetry_definition
    at = Counter(mesh.vertex_position(v) for v in mesh.all_vertex_ids())
    out = {}
    for v in ambiguous:
        position = mesh.vertex_position(v)
        mirrored = mirror_position(position, definition.plane_point, definition.plane_normal)
        out[v] = at[mirrored] - (1 if mirrored == position else 0)
    return out


def _point_map(dst: SceneObject, src: SceneObject):
    if dst.transform == src.transform and dst.pivot == src.pivot:
        return tuple
    return lambda p: object_space.to_object(dst, object_space.to_world(src, p))


def _vector_map(dst: SceneObject, src: SceneObject):
    if dst.transform == src.transform:  # the linear part is equal: values stay bit-identical
        return None
    return lambda v: object_space.delta_to_object(dst, object_space.delta_to_world(src, v))


def _append(
    dst: SceneObject, sources: list[SceneObject], layers: _LayerPlan, regions: dict, ungrouped: dict
) -> tuple:
    mesh = dst.mesh
    skin = layers.skin if layers.new_skin is None else mesh.add_point_layer(layers.new_skin)
    layer_maps: dict[ObjectId, dict[LayerId, LayerId]] = {}
    for src in sources:
        layer_maps[src.id] = {
            lid: (skin if info is None else mesh.add_point_layer(info)) for lid, info in layers.per_source[src.id]
        }
    origin = () if mesh.has_point_layers() else None  # every new point starts at the layers' defaults
    vertex_maps: dict[ObjectId, dict[VertexId, VertexId]] = {}
    face_maps: dict[ObjectId, dict[FaceId, FaceId]] = {}
    carried: list[FaceRegion] = []
    for src in sources:
        source = src.mesh
        to_dst = _point_map(dst, src)
        vmap = {v: mesh.add_vertex(to_dst(source.vertex_position(v)), origin=origin) for v in source.all_vertex_ids()}
        fmap = {
            f: mesh.add_face([vmap[v] for v in source.face_vertices(f)], source.face_uvs(f), infer_uvs=False)
            for f in source.all_face_ids()
        }
        for e in source.all_edge_ids():
            if not source.edge_faces(e):  # a loose edge (face edges came with their faces)
                a, b = source.edge_vertices(e)
                mesh.add_edge(vmap[a], vmap[b])
        mapped = _vector_map(dst, src)
        for lid, target in layer_maps[src.id].items():
            vector = source.point_layer_info(lid).kind is LayerKind.VECTOR
            for v, value in source.layer_items(lid):
                mesh.set_layer_value(target, vmap[v], mapped(value) if vector and mapped is not None else value)
        if source.face_regions is not None:
            names = regions[src.id]
            for region in source.face_regions.regions:
                carried.append(FaceRegion(names[region.name], frozenset(fmap[f] for f in region.faces if f in fmap)))
        if src.id in ungrouped:
            name, faces = ungrouped[src.id]
            carried.append(FaceRegion(name, frozenset(fmap[f] for f in faces)))
        vertex_maps[src.id], face_maps[src.id] = vmap, fmap
    if carried:
        own = mesh.face_regions.regions if mesh.face_regions is not None else ()
        mesh.face_regions = FaceRegions(own + tuple(carried))
    unweighted = 0
    if skin is not None:
        unweighted = sum(
            1 for vmap in vertex_maps.values() for v in vmap.values() if not mesh.layer_value(skin, v)
        )
    return vertex_maps, face_maps, layer_maps, unweighted


# -- extract ----------------------------------------------------------------------------------------------------------


def extract_faces(mesh: Mesh, faces: Iterable[FaceId]) -> ExtractResult:
    """A new mesh of `faces` (module docstring): the vertices they use (copied, so the result shares nothing with
    `mesh`), the faces in ascending id order with their corner UVs, every point layer (same info and order, values of
    the copied points), and the regions restricted to the extracted faces (names unchanged; regions without one of
    them are left out — they stay with `mesh`). No symmetry definition (`derived_symmetry` decides it). Built without a
    change recording: the result is a fresh instance. Raises `AssemblyRefused` for no face or an unknown face."""
    chosen = sorted(set(faces), key=int)
    if not chosen:
        raise AssemblyRefused("no face to extract")
    unknown = [f for f in chosen if not mesh.is_valid_face(f)]
    if unknown:
        raise AssemblyRefused(f"{len(unknown)} unknown face(s)")
    out = Mesh()
    layers = [(lid, out.add_point_layer(mesh.point_layer_info(lid))) for lid in mesh.point_layer_ids()]
    origin = () if layers else None
    used = sorted({v for f in chosen for v in mesh.face_vertices(f)}, key=int)
    vmap = {v: out.add_vertex(mesh.vertex_position(v), origin=origin) for v in used}
    fmap = {f: out.add_face([vmap[v] for v in mesh.face_vertices(f)], mesh.face_uvs(f), infer_uvs=False) for f in chosen}
    for lid, new in layers:
        for v, value in mesh.layer_items(lid):
            if v in vmap:
                out.set_layer_value(new, vmap[v], value)
    if mesh.face_regions is not None:
        kept = tuple(
            FaceRegion(r.name, frozenset(fmap[f] for f in r.faces if f in fmap))
            for r in mesh.face_regions.regions
            if any(f in fmap for f in r.faces)
        )
        out.face_regions = FaceRegions(kept) if kept else None
    return ExtractResult(out, vmap, fmap)
