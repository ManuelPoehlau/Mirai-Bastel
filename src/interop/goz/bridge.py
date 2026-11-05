"""Send (object -> `.GoZ` + manifest) and the return plan (AD-029 §3, §5, §6). Pure: nothing here mutates a scene.

Rules (E1 README §11, audit §7):

- **Axis:** GoZ = Mirai rotated 180 deg about X; points are written as `(x, -y, -z)` of the world position and read
  back with the same map (self-inverse, det +1: winding stays; sign flips are exact in float32).
- **Placement:** the world position (`to_world`) is sent, as the OBJ export does; a return goes back through `to_object`.
  The manifest fingerprint makes sure the placement is still the one used at send time.
- **Untouched points** (audit §7.3): a returned point whose float32 bits equal what was sent keeps its float64 value;
  only differing points are written, so the Undo delta holds just the moved points.
- **Mirror pairs** (Manu 2026-11-05): ZBrush's Smooth with X symmetry is not exactly symmetric (measured: 76 of 145
  head pairs off by up to 0.0102 = 0.2 % of the head, 13 of 36 seam points off the plane; Move stays bit-exact). While
  the object's Mirai symmetry is on, every pair / seam point the return touched whose deviation is at most
  `SYMMETRY_TOLERANCE` (1 % of the object's size) is made exact in the same Undo step: a pair gets the mean of its two
  sides, a seam point goes onto the plane. Larger deviations stay and are reported. Mirai's own Re-Symmetrize keeps its
  no-tolerance rule; this applies only to a ZBrush return.
- **Last ZBrush state:** after an applied return the manifest keeps ZBrush's points, so a point ZBrush did not move
  since then keeps Mirai's value (incl. a mirrored mean) instead of reading as moved again.
- **Topology** must be exactly the sent one (counts, every face's corner list incl. rotation); otherwise the return can
  only become a new object. N-gons are refused at the send (D4 proposal: GoZ carries triangles and quads only).
- **Subdivided SubTool** (D13, Manu 2026-11-05; E1 T7/T7b/T7c): a return whose every interior point equals the
  one-step Catmull-Clark vertex point of the sent cage is held (`SUBDIVIDED`), not applied: ZBrush returns a smoothed
  cage after a Divide with SMT on and the file says nothing about it. A Divide without SMT returns the cage bit-identical
  (T7b). After a Divide with SMT, the lowest level and **Cage**, every point comes back moved by a tiny amount (T7c: max
  4.1e-4 at extent 5.2): such a return stays appliable, with a warning in the status line (`cage_like`).
- **Polygroups (P2a, docs/WP_GOZ_P2_PLAN.md §3):** every send carries a GROUPS block: region `k` (region order) is id
  `k + 1`, a face in several regions takes the first (the others are recorded), faces in no region take `REST_GROUP`.
  ZBrush keeps these ids per face and gives a group made in ZBrush a new id (E2, 2026-11-05: 101-104 back unchanged, a
  regrouped patch came back as 3225). A same-topology return compares ZBrush's ids with the last known ones; changed
  faces leave every region and join the one their id names (a new id -> a new `Group N`, `REST_GROUP` -> none). The
  new `FaceRegions` goes into the same Undo step as the points. A return whose faces all carry one id Mirai never sent
  keeps the groups untouched (positions only).
"""

from __future__ import annotations

import enum
import math
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from core.ids import FaceId, ObjectId, VertexId
from core.mesh import FaceRegion, FaceRegions, LayerKind, Mesh
from core.scene import Scene, SceneObject

from .format import GozMesh, as_float32, encode_goz
from .manifest import Manifest, float32_hash, fingerprint, fingerprint_differences

Position = tuple[float, float, float]
Placement = Callable[[SceneObject, Position], Position]

#: E1 T7: ZBrush's smoothed cage deviated from the computed vertex points by 5.4e-7 at a head of extent 5.2.
SUBDIV_TOLERANCE = 1e-5
#: Manu 2026-11-05: deviations up to 1 % of the object's size are made symmetric (measured ZBrush Smooth: 0.2 %).
SYMMETRY_TOLERANCE = 0.01
#: E1 T7c: after Cage every point differed from the sent cage by at most 4.1e-4 at extent 5.2 (7.8e-5 relative).
CAGE_TOLERANCE = 2e-4
#: Share of points that must have moved for the Cage warning (T7c: all 326).
CAGE_MOVED_SHARE = 0.95
#: P2a (`PROVISIONAL`): the group id of the faces in no region; ids avoid 0 (an OBJ import's single group, E1 T2).
REST_GROUP = 0xFFFE


def to_goz(p: Sequence[float]) -> Position:
    return (p[0], -p[1], -p[2])


from_goz = to_goz  # the map is its own inverse


@dataclass(frozen=True)
class SymmetryInfo:
    """The object's mirror pairs and seam points as Mirai sees them before the return (`mirai.symmetry`), and its
    mirror map; passed in by the window glue so this module stays core-only."""

    pairs: tuple[tuple[VertexId, VertexId], ...]
    seam: tuple[VertexId, ...]
    mirror: Callable[[Position], Position]


GroupNamer = Callable[[Optional[FaceRegions]], str]


class SendRefused(ValueError):
    """The object cannot travel through GoZ (the message is the status line)."""


def short_name(name: str) -> str:
    """The SubTool name / short identifier ZBrush shows: letters, digits, `_` (GoZMakeObjectPath makes it unique)."""
    return (re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "Mirai")[:40]


def sent_points(obj: SceneObject, to_world: Placement) -> list[Position]:
    mesh = obj.mesh
    return [tuple(as_float32(c) for c in to_goz(to_world(obj, mesh.vertex_position(v)))) for v in mesh.all_vertex_ids()]


def build_send(
    scene: Scene,
    obj: SceneObject,
    *,
    identifier: str,
    transfer_id: str,
    session_id: str,
    scene_path: Optional[str],
    to_world: Placement,
    clock: Callable[[], float] = time.time,
) -> tuple[bytes, Manifest]:
    mesh = obj.mesh
    vertex_ids = mesh.all_vertex_ids()
    face_ids = mesh.all_face_ids()
    if not face_ids:
        raise SendRefused(f"{obj.name!r} has no faces")
    index = {v: i for i, v in enumerate(vertex_ids)}
    faces = [[index[v] for v in mesh.face_vertices(f)] for f in face_ids]
    ngons = sum(1 for f in faces if len(f) > 4)
    if ngons:
        raise SendRefused(f"{obj.name!r} has {ngons} faces with more than 4 corners - GoZ carries triangles and "
                          "quads only (split them first, e.g. Knife / Connect)")
    points = sent_points(obj, to_world)
    groups, names, overlaps = send_groups(mesh, face_ids)
    data = encode_goz(short_name(obj.name), points, faces, groups)
    manifest = Manifest(
        transfer_id=transfer_id, session_id=session_id, identifier=identifier, object_id=int(obj.id),
        object_name=obj.name, scene_path=scene_path, vertex_ids=[int(v) for v in vertex_ids],
        face_ids=[int(f) for f in face_ids], faces=faces, sent_float32=float32_hash(points),
        fingerprint=fingerprint(scene, obj), sent_at=clock(), sent_groups=groups,
        group_names={str(k): v for k, v in names.items()}, rest_group=REST_GROUP, group_overlaps=overlaps,
    )
    return data, manifest


def send_groups(mesh: Mesh, face_ids: Sequence[FaceId]) -> tuple[list[int], dict[int, str], list]:
    """Per sent face its group id, the id -> region name map and the overlaps (see module)."""
    regions = mesh.face_regions.regions if mesh.face_regions is not None else ()
    if len(regions) >= REST_GROUP:
        raise SendRefused(f"{len(regions)} groups - GoZ carries at most {REST_GROUP - 1}")
    ids = {r.name: k + 1 for k, r in enumerate(regions)}
    groups: list[int] = []
    overlaps: list = []
    for index, f in enumerate(face_ids):
        member = [r.name for r in regions if f in r.faces]
        groups.append(ids[member[0]] if member else REST_GROUP)
        if len(member) > 1:
            overlaps.append([index, member[1:]])
    return groups, {k: name for name, k in ids.items()}, overlaps


# -- subdivision signature ----------------------------------------------------------------------------------------------


def catmull_clark_vertex_points(points: Sequence[Position], faces: Sequence[Sequence[int]]) -> list[Optional[Position]]:
    """One Catmull-Clark step's new position of every original point: `(F + 2R + (n - 3) P) / n` (F = mean of the
    adjacent face points, R = mean of the incident edge midpoints, n = valence). None for a point on an open border or
    a non-manifold edge: ZBrush's border rule was not measured (the E1 head is closed)."""
    n = len(points)
    face_points = [tuple(math.fsum(points[i][c] for i in f) / len(f) for c in range(3)) for f in faces]
    faces_of: list[list[int]] = [[] for _ in range(n)]
    edge_faces: dict[tuple[int, int], int] = {}
    for fi, f in enumerate(faces):
        for k, a in enumerate(f):
            b = f[(k + 1) % len(f)]
            faces_of[a].append(fi)
            key = (a, b) if a < b else (b, a)
            edge_faces[key] = edge_faces.get(key, 0) + 1
    neighbours: list[list[int]] = [[] for _ in range(n)]
    open_point = [False] * n
    for (a, b), count in edge_faces.items():
        neighbours[a].append(b)
        neighbours[b].append(a)
        if count != 2:
            open_point[a] = open_point[b] = True
    out: list[Optional[Position]] = []
    for i, p in enumerate(points):
        valence = len(neighbours[i])
        if open_point[i] or valence < 3 or len(faces_of[i]) != valence:
            out.append(None)
            continue
        out.append(tuple(
            (math.fsum(face_points[f][c] for f in faces_of[i]) / valence
             + math.fsum(p[c] + points[j][c] for j in neighbours[i]) / valence
             + (valence - 3) * p[c]) / valence
            for c in range(3)
        ))
    return out


def _extent(points: Sequence[Position]) -> float:
    return max(max(max(p[c] for p in points) - min(p[c] for p in points) for c in range(3)), 1e-9)


def looks_subdivided(sent: Sequence[Position], returned: Sequence[Position], faces: Sequence[Sequence[int]]) -> bool:
    """True if every interior point of the return is the one-step vertex point of the sent cage (within float32
    noise) and that map actually moves some point (a flat grid's interior is its own vertex point)."""
    predicted = catmull_clark_vertex_points(sent, faces)
    tol = SUBDIV_TOLERANCE * _extent(sent)
    checked = moved = 0
    for q, r, s in zip(predicted, returned, sent):
        if q is None:
            continue
        checked += 1
        if max(abs(a - b) for a, b in zip(q, r)) > tol:
            return False
        if max(abs(a - b) for a, b in zip(q, s)) > tol:
            moved += 1
    return checked > 0 and moved > 0


# -- the return plan ----------------------------------------------------------------------------------------------------


class ReturnKind(enum.Enum):
    IN_PLACE = "in_place"  # points and / or groups into the object, one Undo step
    UNCHANGED = "unchanged"  # nothing moved, no group changed
    CONFLICT = "conflict"  # the Mirai object changed since the send -> new object only (D3 proposal)
    TOPOLOGY_CHANGED = "topology_changed"  # -> new object only
    UNKNOWN_OBJECT = "unknown_object"  # no manifest / other session / object gone -> new object only
    SUBDIVIDED = "subdivided"  # held (D13 open)
    INVALID = "invalid"  # incomplete or malformed file -> nothing


NEW_OBJECT_KINDS = frozenset({ReturnKind.CONFLICT, ReturnKind.TOPOLOGY_CHANGED, ReturnKind.UNKNOWN_OBJECT})


@dataclass
class ReturnPlan:
    kind: ReturnKind
    identifier: str
    label: str  # the object's name, or the SubTool's
    reason: str
    goz: Optional[GozMesh] = None
    manifest: Optional[Manifest] = None
    object_id: Optional[ObjectId] = None
    positions: dict[VertexId, Position] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    cage_like: bool = False
    #: P2a: the new regions value to write (`regions_changed`; None is "no regions"), ZBrush's ids of this return
    #: when the plan read them (the manifest's next baseline) and the id -> name map incl. new groups
    regions_changed: bool = False
    regions: Optional[FaceRegions] = None
    zbrush_groups: Optional[tuple[int, ...]] = None
    group_names: dict[int, str] = field(default_factory=dict)

    @property
    def in_place(self) -> bool:
        return self.kind is ReturnKind.IN_PLACE

    @property
    def new_object(self) -> bool:
        return self.kind in NEW_OBJECT_KINDS

    def summary(self) -> str:
        text = f"ZBrush {self.label!r}: {self.reason}"
        return text + (" (" + "; ".join(self.notes) + ")" if self.notes else "")


def invalid_plan(identifier: str, reason: str) -> ReturnPlan:
    return ReturnPlan(ReturnKind.INVALID, identifier, identifier.replace("\\", "/").rsplit("/", 1)[-1], reason)


def plan_return(
    goz: GozMesh,
    manifest: Optional[Manifest],
    scene: Scene,
    *,
    identifier: str,
    session_id: str,
    scene_path: Optional[str],
    to_world: Placement,
    to_object: Placement,
    symmetry: Optional[SymmetryInfo] = None,
    new_group_name: Optional[GroupNamer] = None,
) -> ReturnPlan:
    subtool = goz.name[len("GoZMesh_"):] if goz.name.startswith("GoZMesh_") else goz.name
    if manifest is None:
        return ReturnPlan(ReturnKind.UNKNOWN_OBJECT, identifier, subtool or identifier,
                          "not sent from Mirai - can be added as a new object", goz)
    label = manifest.object_name

    def plan(kind: ReturnKind, reason: str, **kw) -> ReturnPlan:
        return ReturnPlan(kind, identifier, label, reason, goz, manifest, **kw)

    same_scene = manifest.session_id == session_id or (scene_path is not None and manifest.scene_path == scene_path)
    obj = scene.objects.get(ObjectId(manifest.object_id)) if same_scene else None
    if obj is None:
        why = "its object is gone" if same_scene else "sent from another Mirai session or scene"
        return plan(ReturnKind.UNKNOWN_OBJECT, f"{why} - can be added as a new object")
    if len(goz.points) != len(manifest.vertex_ids) or [list(f) for f in goz.faces] != manifest.faces:
        return plan(ReturnKind.TOPOLOGY_CHANGED,
                    f"topology changed in ZBrush ({len(goz.points)} points / {len(goz.faces)} faces, sent "
                    f"{len(manifest.vertex_ids)} / {len(manifest.faces)}) - only as a new object", object_id=obj.id)
    differences = fingerprint_differences(manifest.fingerprint, fingerprint(scene, obj))
    sent = sent_points(obj, to_world) if not differences else []
    if not differences and float32_hash(sent) != manifest.sent_float32:
        differences = ["sent points"]
    if differences:
        return plan(ReturnKind.CONFLICT, f"{obj.name!r} changed in Mirai since the send ({', '.join(differences)}) - "
                    "only as a new object", object_id=obj.id)
    returned = goz.points
    last = [tuple(p) for p in manifest.zbrush_points] if manifest.zbrush_points is not None else sent
    if looks_subdivided(last, returned, manifest.faces):
        return plan(ReturnKind.SUBDIVIDED, "looks divided in ZBrush with SMT on (every point smoothed by one "
                    "subdivision step) - held, nothing applied; in ZBrush: lowest level > Cage, or Divide with SMT off, "
                    "then GoZ again", object_id=obj.id)
    positions: dict[VertexId, Position] = {}
    largest = 0.0
    for i, (r, s) in enumerate(zip(returned, last)):
        if r != s:
            positions[manifest.vertex_id(i)] = to_object(obj, from_goz(r))
            largest = max(largest, max(abs(a - b) for a, b in zip(r, s)))
    mesh = obj.mesh
    groups = plan_groups(goz.groups, manifest, mesh, new_group_name)
    notes = list(groups.notes)
    group_kw = dict(zbrush_groups=groups.read, group_names=groups.names, regions_changed=groups.changed,
                    regions=groups.regions)
    if not positions and not groups.changed:
        return plan(ReturnKind.UNCHANGED, "no point moved" + (", no group changed" if groups.read else ""),
                    object_id=obj.id, notes=notes, **group_kw)
    moved_by_zbrush = len(positions)
    cage_like = len(positions) >= CAGE_MOVED_SHARE * len(sent) and largest <= CAGE_TOLERANCE * _extent(sent)
    if cage_like:
        notes.append(f"looks like ZBrush's Cage reconstruction, not a sculpt: every point moved by at most {largest:.2g}"
                     " - exact symmetry pairs may break (Re-Symmetrize)")
    if symmetry is not None and positions:
        notes.extend(symmetrize_positions(positions, mesh, symmetry))
    targets = sum(1 for lid in mesh.point_layer_ids() if mesh.point_layer_info(lid).kind is LayerKind.VECTOR)
    if targets:
        notes.append(f"{targets} morph target{'s' if targets != 1 else ''} follow the new base")
    reason = f"{moved_by_zbrush} of {len(sent)} points moved" if positions else "no point moved, groups changed"
    return plan(ReturnKind.IN_PLACE, reason, object_id=obj.id, positions=positions, notes=notes, cage_like=cage_like,
                **group_kw)


# -- polygroups (P2a) ---------------------------------------------------------------------------------------------------


@dataclass
class GroupPlan:
    read: Optional[tuple[int, ...]] = None  # ZBrush's ids, when they were taken into account
    names: dict[int, str] = field(default_factory=dict)
    changed: bool = False
    regions: Optional[FaceRegions] = None
    notes: list[str] = field(default_factory=list)


def plan_groups(returned: Optional[Sequence[int]], manifest: Manifest, mesh: Mesh,
                new_group_name: Optional[GroupNamer] = None) -> GroupPlan:
    """The regions after ZBrush's group ids `returned` (see module). Needs the sent topology (checked by the caller)."""
    names = {int(k): v for k, v in manifest.group_names.items()}
    if returned is None or manifest.sent_groups is None:
        return GroupPlan(names=names)
    returned = tuple(int(g) for g in returned)
    baseline = manifest.zbrush_groups if manifest.zbrush_groups is not None else manifest.sent_groups
    rest = manifest.rest_group
    if len(set(returned)) == 1 and returned[0] not in set(names) | {rest} | set(baseline):
        return GroupPlan(names=names, notes=[f"ZBrush gave every face one group Mirai never sent ({returned[0]}) - "
                                             "groups left as they are"])
    changed_at = [i for i, (r, b) in enumerate(zip(returned, baseline)) if r != b]
    if not changed_at:
        return GroupPlan(read=returned, names=names)
    regions = mesh.face_regions
    before = {r.name: r.faces for r in regions.regions} if regions is not None else {}
    order = list(before)
    for i in changed_at:
        gid = returned[i]
        if gid == rest or gid in names:
            continue
        taken = FaceRegions(tuple(FaceRegion(n, frozenset()) for n in dict.fromkeys([*order, *names.values()])))
        names[gid] = new_group_name(taken) if new_group_name is not None else f"ZBrush {gid}"
    moved = {manifest.face_id(i) for i in changed_at}
    sets = {name: set(faces) - moved for name, faces in before.items()}
    for i in changed_at:
        gid = returned[i]
        if gid == rest:
            continue
        name = names[gid]
        if name not in sets:
            sets[name] = set()
            order.append(name)
        sets[name].add(manifest.face_id(i))
    kept = tuple(FaceRegion(n, frozenset(sets[n])) for n in order if sets[n])
    value = FaceRegions(kept) if kept else None
    if value == regions:
        return GroupPlan(read=returned, names=names)
    after = {r.name: r.faces for r in kept}
    changed = sum(1 for n, faces in before.items() if after.get(n) != faces)
    new = sum(1 for n in after if n not in before)
    note = f"groups: {changed} changed, {new} new ({len(changed_at)} faces regrouped)"
    return GroupPlan(read=returned, names=names, changed=True, regions=value, notes=[note])


def _mid(a: Position, b: Position) -> Position:
    return tuple((x + y) * 0.5 for x, y in zip(a, b))


def _gap(a: Position, b: Position) -> float:
    return max(abs(x - y) for x, y in zip(a, b))


def symmetrize_positions(positions: dict[VertexId, Position], mesh: Mesh, symmetry: SymmetryInfo) -> list[str]:
    """Makes the pairs and seam points this return touched exact again, within `SYMMETRY_TOLERANCE` of the object's
    size (see module). Changes `positions` in place (a partner ZBrush left alone is added); returns the status notes."""
    current = mesh.vertex_position
    tol = SYMMETRY_TOLERANCE * _extent([current(v) for v in mesh.all_vertex_ids()])
    mirror = symmetry.mirror
    fixed_pairs = fixed_seam = 0
    largest = 0.0
    left_pairs = left_seam = 0
    for a, b in symmetry.pairs:
        if a not in positions and b not in positions:
            continue
        pa, pb = positions.get(a, current(a)), positions.get(b, current(b))
        target = mirror(pb)
        gap = _gap(pa, target)
        if gap == 0.0:
            continue
        if gap > tol:
            left_pairs += 1
            continue
        new_a = _mid(pa, target)
        positions[a], positions[b] = new_a, mirror(new_a)
        fixed_pairs += 1
        largest = max(largest, gap)
    for v in symmetry.seam:
        if v not in positions:
            continue
        p = positions[v]
        on_plane = _mid(p, mirror(p))
        gap = _gap(p, on_plane)
        if gap == 0.0:
            continue
        if gap > tol:
            left_seam += 1
            continue
        positions[v] = on_plane
        fixed_seam += 1
        largest = max(largest, gap)
    notes = []
    if fixed_pairs or fixed_seam:
        notes.append(f"symmetry made exact: {fixed_pairs} mirror pairs, {fixed_seam} seam points "
                     f"(ZBrush deviation up to {largest:.2g})")
    if left_pairs or left_seam:
        notes.append(f"{left_pairs} pairs / {left_seam} seam points stay asymmetric (more than 1 % of the size) - "
                     "Re-Symmetrize")
    return notes


def mesh_from_goz(goz: GozMesh) -> Mesh:
    """A new mesh in Mirai's world frame (the new-object path: identity placement, fresh IDs)."""
    mesh = Mesh()
    ids = [mesh.add_vertex(from_goz(p)) for p in goz.points]
    for face in goz.faces:
        mesh.add_face([ids[i] for i in face])
    return mesh


def rebase_manifest(manifest: Manifest, scene: Scene, obj: SceneObject, to_world: Placement,
                    zbrush_points: Optional[Sequence[Position]] = None, plan: Optional[ReturnPlan] = None) -> Manifest:
    """After an applied return Mirai and ZBrush hold the same shape: the manifest takes the object's new fingerprint,
    so the next GoZ of the same SubTool (more sculpting, no resend) plans against it instead of reading as a conflict.
    An Undo of the apply makes Mirai differ again - that next return is then a conflict (fail-closed)."""
    from dataclasses import replace

    groups = {}
    if plan is not None and plan.zbrush_groups is not None:  # ZBrush's ids become the baseline, new ids keep their name
        groups = dict(zbrush_groups=list(plan.zbrush_groups),
                      group_names={str(k): v for k, v in plan.group_names.items()})
    return replace(manifest, fingerprint=fingerprint(scene, obj), sent_float32=float32_hash(sent_points(obj, to_world)),
                   zbrush_points=None if zbrush_points is None else [list(p) for p in zbrush_points], **groups)
