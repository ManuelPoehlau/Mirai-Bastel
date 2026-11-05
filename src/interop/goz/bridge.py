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
  only become a new object.
- **N-gons (P2b, docs/WP_GOZ_P2_PLAN.md §4; Manu 2026-11-05: "Möglichst Vierecke"):** GoZ carries triangles and quads
  only, so a face with more than 4 corners is split **in the file only** (`split_ngon`): the ear-clipping triangulation
  (handed in by the glue, `viewport.derived`), then adjacent triangles merged into quads wherever their union is a
  non-reflex quad, without new points. Deterministic (boundary + positions at send time). The manifest's `faces` are
  the sent pieces, `face_ids` repeat the n-gon's `FaceId` per piece, `ngons` lists them. A return with exactly the sent
  pieces maps back by point index as in P1 (Mirai's n-gons stay n-gons); any other topology is a new object. An
  n-gon whose pieces come back with different group ids takes the id with the largest area share.
- **Mirror-symmetric split (Manu 2026-11-05):** while the object's Mirai symmetry is on (`SymmetryInfo`, from the glue),
  of two mirrored n-gons only the one with the lower `FaceId` is split as above and the other gets the mirror image
  of that split; an n-gon the mirror maps onto itself gets a split that is its own mirror image: cut along the plane
  between its two corners on it and split one half (mirrored onto the other), or a ladder of symmetric quads between
  mirrored corners (a triangle where it meets a corner on the plane) - whichever valid one has fewer triangles (valid:
  every piece keeps the face's winding without a reflex corner and the pieces cover the face exactly once); if none is
  valid, and for n-gons with an unpaired corner, the plain split. A mirrored pair needs no check: Mirai pairs points
  only at exactly mirrored positions, so the image is the same split. Measured before (head, 8 mirrored
  6-gon pairs): 0 of 8 pairs split alike. ZBrush's Smooth and Poseable Symmetry use the edges, so both halves should
  carry the same ones.
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
#: the glue's ear clipping (`viewport.derived.triangulate_face`): boundary + positions -> triangles of boundary vertices
Triangulate = Callable[[Sequence[VertexId], dict], list]


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
    triangulate: Optional[Triangulate] = None,
    symmetry: Optional[SymmetryInfo] = None,
    clock: Callable[[], float] = time.time,
) -> tuple[bytes, Manifest]:
    mesh = obj.mesh
    vertex_ids = mesh.all_vertex_ids()
    mesh_faces = mesh.all_face_ids()
    if not mesh_faces:
        raise SendRefused(f"{obj.name!r} has no faces")
    index = {v: i for i, v in enumerate(vertex_ids)}
    faces: list[list[int]] = []
    face_ids: list[FaceId] = []
    ngons: list = []
    big = [f for f in mesh_faces if len(mesh.face_vertices(f)) > 4]
    if big and triangulate is None:
        raise SendRefused(f"{obj.name!r} has faces with more than 4 corners and no triangulation was given")
    splits, stats = split_ngons(mesh, big, triangulate, symmetry) if big else ({}, {})
    for f in mesh_faces:
        if f in splits:
            pieces = splits[f]
            ngons.append([int(f), list(range(len(faces), len(faces) + len(pieces)))])
        else:
            pieces = [mesh.face_vertices(f)]
        for piece in pieces:
            faces.append([index[v] for v in piece])
            face_ids.append(f)
    points = sent_points(obj, to_world)
    groups, names, overlaps = send_groups(mesh, face_ids)
    data = encode_goz(short_name(obj.name), points, faces, groups)
    manifest = Manifest(
        transfer_id=transfer_id, session_id=session_id, identifier=identifier, object_id=int(obj.id),
        object_name=obj.name, scene_path=scene_path, vertex_ids=[int(v) for v in vertex_ids],
        face_ids=[int(f) for f in face_ids], faces=faces, sent_float32=float32_hash(points),
        fingerprint=fingerprint(scene, obj), sent_at=clock(), sent_groups=groups,
        group_names={str(k): v for k, v in names.items()}, rest_group=REST_GROUP, group_overlaps=overlaps,
        ngons=ngons, extra={"ngon_split": stats} if stats else {},
    )
    return data, manifest


# -- n-gons (P2b) -------------------------------------------------------------------------------------------------------


def _sub(a: Sequence[float], b: Sequence[float]) -> Position:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Sequence[float], b: Sequence[float]) -> Position:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def newell(points: Sequence[Sequence[float]]) -> Position:
    """The Newell normal of a polygon (length = twice its area; exact for planar polygons)."""
    n = len(points)
    return tuple(math.fsum((points[i][(c + 1) % 3] - points[(i + 1) % n][(c + 1) % 3])
                           * (points[i][(c + 2) % 3] + points[(i + 1) % n][(c + 2) % 3]) for i in range(n))
                 for c in range(3))


def polygon_area(points: Sequence[Sequence[float]]) -> float:
    return 0.5 * math.sqrt(_dot(*(newell(points),) * 2))


def _quad_ok(quad: Sequence[Position], normal: Position, tol: float) -> bool:
    """No reflex corner (a straight one, e.g. a Knife point on an edge, is fine) and a real area."""
    for k in range(4):
        a, b, c = quad[k - 1], quad[k], quad[(k + 1) % 4]
        if _dot(_cross(_sub(b, a), _sub(c, b)), normal) < -tol:
            return False
    return _dot(newell(quad), normal) > tol


def split_ngon(boundary: Sequence[VertexId], position: Callable[[VertexId], Position],
               triangulate: Triangulate) -> list[tuple[int, ...]]:
    """The pieces of an n-gon as corner positions in `boundary` (see module): quads where two adjacent triangles of
    the triangulation form a non-reflex quad, triangles elsewhere; every piece in the boundary's winding, the pieces
    ordered by their corners. A convex n-gon (fan) gives n/2 - 1 quads and, for odd n, one triangle."""
    at = {v: k for k, v in enumerate(boundary)}
    pts = [position(v) for v in boundary]
    normal = newell(pts)
    size = max(max(p[c] for p in pts) - min(p[c] for p in pts) for c in range(3)) or 1.0
    length = math.sqrt(_dot(normal, normal)) or 1.0
    unit = tuple(c / length for c in normal)
    tol = 1e-9 * size * size
    # a sub-polygon of a simple polygon keeps the polygon's winding when its corners follow the boundary order
    tris = sorted(tuple(sorted(at[v] for v in tri)) for tri in triangulate(list(boundary), dict(zip(boundary, pts))))
    used = [False] * len(tris)
    pieces: list[tuple[int, ...]] = []
    for i, t in enumerate(tris):
        if used[i]:
            continue
        used[i] = True
        for j in range(i + 1, len(tris)):
            u = tris[j]
            if used[j] or len(set(t) & set(u)) != 2:
                continue
            quad = tuple(sorted(set(t) | set(u)))
            if _quad_ok([pts[k] for k in quad], unit, tol):
                used[j] = True
                pieces.append(quad)
                break
        else:
            pieces.append(t)
    return sorted(pieces)


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
    groups = plan_groups(goz.groups, manifest, mesh, new_group_name, returned)
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


def _piece_ok(piece: Sequence[Position], unit: Position, tol: float) -> bool:
    if len(piece) == 4:
        return _quad_ok(piece, unit, tol)
    return _dot(newell(piece), unit) > tol


def valid_split(boundary: Sequence[VertexId], pieces: Sequence[Sequence[VertexId]],
                position: Callable[[VertexId], Position]) -> bool:
    """Every piece a triangle or quad in the face's winding without a reflex corner, and together the face exactly once
    (Newell vectors add up over a decomposition; overlaps or gaps change the sum)."""
    pts = [position(v) for v in boundary]
    normal = newell(pts)
    length = math.sqrt(_dot(normal, normal))
    if length == 0.0:
        return False
    unit = tuple(c / length for c in normal)
    size = max(max(p[c] for p in pts) - min(p[c] for p in pts) for c in range(3)) or 1.0
    tol = 1e-9 * size * size
    total = 0.0
    for piece in pieces:
        corners = [position(v) for v in piece]
        if len(piece) not in (3, 4) or len(set(piece)) != len(piece) or not _piece_ok(corners, unit, tol):
            return False
        total += _dot(newell(corners), unit)
    return abs(total - length) <= 1e-6 * length + tol


def _in_order(boundary: Sequence[VertexId], vertices) -> list[VertexId]:
    at = {v: k for k, v in enumerate(boundary)}
    return sorted(vertices, key=at.__getitem__)


def _self_mirror_splits(boundary: Sequence[VertexId], partner: dict, position, triangulate) -> list[list[list[VertexId]]]:
    """The candidate splits of an n-gon the mirror maps onto itself, each its own mirror image (see module); [] when
    the mirror is not a reflection of the corner cycle."""
    n = len(boundary)
    at = {v: k for k, v in enumerate(boundary)}
    c = at.get(partner.get(boundary[0]))
    if c is None or any(partner.get(boundary[i]) != boundary[(c - i) % n] for i in range(n)):
        return []
    seam = [i for i in range(n) if (2 * i - c) % n == 0]
    out: list[list[list[VertexId]]] = []
    if len(seam) == 2 and (seam[1] - seam[0]) % n not in (1, n - 1):  # cut along the plane, split one half
        a, b = seam
        half = [boundary[i % n] for i in range(a, b + 1)]
        pieces = [[half[k] for k in piece] for piece in split_ngon(half, position, triangulate)]
        mirrored = [_in_order(boundary, (partner[v] for v in piece)) for piece in pieces]
        out.append([_in_order(boundary, p) for p in pieces] + mirrored)
    # the ladder: symmetric quads between mirrored corners, a triangle at a corner on the plane
    if seam:
        l = r = seam[0]
    else:
        j = next(j for j in range(n) if (c - j) % n == (j + 1) % n)  # the edge the plane crosses
        l, r = j, (j + 1) % n
    ladder: list[list[VertexId]] = []
    while True:
        gap = (l - r) % n or n
        if gap == 1:
            break
        if gap == 2:
            ladder.append(_in_order(boundary, {boundary[r], boundary[(r + 1) % n], boundary[l]}))
            break
        ladder.append(_in_order(boundary, {boundary[(l - 1) % n], boundary[l], boundary[r], boundary[(r + 1) % n]}))
        l, r = (l - 1) % n, (r + 1) % n
    out.append(ladder)
    return out


def split_ngons(mesh: Mesh, faces: Sequence[FaceId], triangulate: Triangulate,
                symmetry: Optional[SymmetryInfo] = None) -> tuple[dict[FaceId, list[list[VertexId]]], dict]:
    """The pieces of every n-gon in `faces` (vertex IDs, each in its face's winding) and the counts for the status:
    `split`, and with symmetry `mirrored` (pairs split alike + self-mirror n-gons split symmetrically) and
    `asymmetric` (left to the plain split)."""
    position = mesh.vertex_position

    def plain(f: FaceId) -> list[list[VertexId]]:
        boundary = mesh.face_vertices(f)
        return [[boundary[k] for k in piece] for piece in split_ngon(boundary, position, triangulate)]

    out: dict[FaceId, list[list[VertexId]]] = {}
    stats = {"split": len(faces)}
    if symmetry is None:
        return {f: plain(f) for f in faces}, stats
    partner: dict[VertexId, VertexId] = {v: v for v in symmetry.seam}
    for a, b in symmetry.pairs:
        partner[a], partner[b] = b, a
    for f in faces:  # a corner exactly on the plane is its own image even when no seam edge declares it (a dissolved
        for v in mesh.face_vertices(f):  # or knifed seam edge leaves such corners undeclared)
            if v not in partner and symmetry.mirror(position(v)) == position(v):
                partner[v] = v
    by_corners = {frozenset(mesh.face_vertices(f)): f for f in faces}
    mirrored = asymmetric = 0
    for f in sorted(faces, key=int):
        if f in out:
            continue
        boundary = mesh.face_vertices(f)
        if not all(v in partner for v in boundary):
            out[f] = plain(f)
            asymmetric += 1
            continue
        g = by_corners.get(frozenset(partner[v] for v in boundary))
        if g is None:
            out[f] = plain(f)
            asymmetric += 1
        elif g == f:
            candidates = [p for p in _self_mirror_splits(boundary, partner, position, triangulate)
                          if valid_split(boundary, p, position)]
            if candidates:
                out[f] = min(candidates, key=lambda p: (sum(len(x) == 3 for x in p), len(p)))
                mirrored += 1
            else:
                out[f] = plain(f)
                asymmetric += 1
        else:
            # the partners are exact mirror images (Mirai's pairing rule), so the image is the same split of `g`;
            # its corners in `g`'s boundary order keep `g`'s winding
            pieces = plain(f)
            other = mesh.face_vertices(g)
            out[f] = pieces
            out[g] = [_in_order(other, (partner[v] for v in piece)) for piece in pieces]
            mirrored += 2
    stats.update(mirrored=mirrored, asymmetric=asymmetric)
    return out, stats


# -- polygroups (P2a) ---------------------------------------------------------------------------------------------------


@dataclass
class GroupPlan:
    read: Optional[tuple[int, ...]] = None  # ZBrush's ids, when they were taken into account
    names: dict[int, str] = field(default_factory=dict)
    changed: bool = False
    regions: Optional[FaceRegions] = None
    notes: list[str] = field(default_factory=list)


def face_groups(groups: Sequence[int], manifest: Manifest,
                points: Optional[Sequence[Position]]) -> tuple[dict[FaceId, int], int]:
    """Per Mirai face its group id: a sent piece's id, or for an n-gon whose pieces differ the id with the largest area
    share of its pieces (Manu 2026-11-05; areas from `points`, ties -> the earlier piece). Also how many n-gons had
    differing pieces."""
    out: dict[FaceId, int] = {}
    for i, g in enumerate(groups):
        out.setdefault(manifest.face_id(i), g)
    mixed = 0
    for fid, pieces in manifest.ngons:
        ids = [groups[i] for i in pieces]
        if len(set(ids)) == 1:
            continue
        mixed += 1
        share: dict[int, float] = {}
        for i, g in zip(pieces, ids):
            area = polygon_area([points[k] for k in manifest.faces[i]]) if points is not None else 1.0
            share[g] = share.get(g, 0.0) + area
        out[FaceId(fid)] = max(share, key=lambda g: (share[g], -ids.index(g)))
    return out, mixed


def plan_groups(returned: Optional[Sequence[int]], manifest: Manifest, mesh: Mesh,
                new_group_name: Optional[GroupNamer] = None,
                points: Optional[Sequence[Position]] = None) -> GroupPlan:
    """The regions after ZBrush's group ids `returned` (see module). Needs the sent topology (checked by the caller);
    `points` are the returned points (an n-gon's area shares)."""
    names = {int(k): v for k, v in manifest.group_names.items()}
    if returned is None or manifest.sent_groups is None:
        return GroupPlan(names=names)
    returned = tuple(int(g) for g in returned)
    baseline = manifest.zbrush_groups if manifest.zbrush_groups is not None else manifest.sent_groups
    rest = manifest.rest_group
    if len(set(returned)) == 1 and returned[0] not in set(names) | {rest} | set(baseline):
        return GroupPlan(names=names, notes=[f"ZBrush gave every face one group Mirai never sent ({returned[0]}) - "
                                             "groups left as they are"])
    if returned == tuple(baseline):
        return GroupPlan(read=returned, names=names)
    now, mixed = face_groups(returned, manifest, points)
    was, _ = face_groups(baseline, manifest, points)
    changed_at = [f for f in now if now[f] != was[f]]
    mixed_note = ([f"{mixed} n-gon{'s' if mixed != 1 else ''} split across groups in ZBrush took the group with the "
                   "largest area"] if mixed else [])
    if not changed_at:
        return GroupPlan(read=returned, names=names, notes=mixed_note)
    regions = mesh.face_regions
    before = {r.name: r.faces for r in regions.regions} if regions is not None else {}
    order = list(before)
    for f in changed_at:
        gid = now[f]
        if gid == rest or gid in names:
            continue
        taken = FaceRegions(tuple(FaceRegion(n, frozenset()) for n in dict.fromkeys([*order, *names.values()])))
        names[gid] = new_group_name(taken) if new_group_name is not None else f"ZBrush {gid}"
    moved = set(changed_at)
    sets = {name: set(faces) - moved for name, faces in before.items()}
    for f in changed_at:
        gid = now[f]
        if gid == rest:
            continue
        name = names[gid]
        if name not in sets:
            sets[name] = set()
            order.append(name)
        sets[name].add(f)
    kept = tuple(FaceRegion(n, frozenset(sets[n])) for n in order if sets[n])
    value = FaceRegions(kept) if kept else None
    if value == regions:
        return GroupPlan(read=returned, names=names, notes=mixed_note)
    after = {r.name: r.faces for r in kept}
    changed = sum(1 for n, faces in before.items() if after.get(n) != faces)
    new = sum(1 for n in after if n not in before)
    note = f"groups: {changed} changed, {new} new ({len(changed_at)} faces regrouped)"
    return GroupPlan(read=returned, names=names, changed=True, regions=value, notes=[note, *mixed_note])


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
