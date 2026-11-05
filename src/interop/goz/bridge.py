"""Send (object -> `.GoZ` + manifest) and the return plan (AD-029 §3, §5, §6). Pure: nothing here mutates a scene.

Rules (E1 README §11, audit §7):

- **Axis:** GoZ = Mirai rotated 180 deg about X; points are written as `(x, -y, -z)` of the world position and read
  back with the same map (self-inverse, det +1: winding stays; sign flips are exact in float32).
- **Placement:** the world position (`to_world`) is sent, as the OBJ export does; a return goes back through `to_object`.
  The manifest fingerprint makes sure the placement is still the one used at send time.
- **Untouched points** (audit §7.3): a returned point whose float32 bits equal what was sent keeps its float64 value;
  only differing points are written, so the Undo delta holds just the moved points.
- **Topology** must be exactly the sent one (counts, every face's corner list incl. rotation); otherwise the return can
  only become a new object. N-gons are refused at the send (D4 proposal: GoZ carries triangles and quads only).
- **Subdivided SubTool** (D13, Manu 2026-11-05; E1 T7/T7b/T7c): a return whose every interior point equals the
  one-step Catmull-Clark vertex point of the sent cage is held (`SUBDIVIDED`), not applied: ZBrush returns a smoothed
  cage after a Divide with SMT on and the file says nothing about it. A Divide without SMT returns the cage bit-identical
  (T7b). After a Divide with SMT, the lowest level and **Cage**, every point comes back moved by a tiny amount (T7c: max
  4.1e-4 at extent 5.2): such a return stays appliable, with a warning in the status line (`cage_like`).
"""

from __future__ import annotations

import enum
import math
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from core.ids import ObjectId, VertexId
from core.mesh import LayerKind, Mesh
from core.scene import Scene, SceneObject

from .format import GozMesh, as_float32, encode_goz
from .manifest import Manifest, float32_hash, fingerprint, fingerprint_differences

Position = tuple[float, float, float]
Placement = Callable[[SceneObject, Position], Position]

#: E1 T7: ZBrush's smoothed cage deviated from the computed vertex points by 5.4e-7 at a head of extent 5.2.
SUBDIV_TOLERANCE = 1e-5
#: E1 T7c: after Cage every point differed from the sent cage by at most 4.1e-4 at extent 5.2 (7.8e-5 relative).
CAGE_TOLERANCE = 2e-4
#: Share of points that must have moved for the Cage warning (T7c: all 326).
CAGE_MOVED_SHARE = 0.95


def to_goz(p: Sequence[float]) -> Position:
    return (p[0], -p[1], -p[2])


from_goz = to_goz  # the map is its own inverse


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
    data = encode_goz(short_name(obj.name), points, faces)
    manifest = Manifest(
        transfer_id=transfer_id, session_id=session_id, identifier=identifier, object_id=int(obj.id),
        object_name=obj.name, scene_path=scene_path, vertex_ids=[int(v) for v in vertex_ids],
        face_ids=[int(f) for f in face_ids], faces=faces, sent_float32=float32_hash(points),
        fingerprint=fingerprint(scene, obj), sent_at=clock(),
    )
    return data, manifest


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
    POSITIONS = "positions"  # in place, one Undo step
    UNCHANGED = "unchanged"  # nothing moved
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

    @property
    def in_place(self) -> bool:
        return self.kind is ReturnKind.POSITIONS

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
    if looks_subdivided(sent, returned, manifest.faces):
        return plan(ReturnKind.SUBDIVIDED, "looks divided in ZBrush with SMT on (every point smoothed by one "
                    "subdivision step) - held, nothing applied; in ZBrush: lowest level > Cage, or Divide with SMT off, "
                    "then GoZ again", object_id=obj.id)
    positions: dict[VertexId, Position] = {}
    largest = 0.0
    for i, (r, s) in enumerate(zip(returned, sent)):
        if r != s:
            positions[manifest.vertex_id(i)] = to_object(obj, from_goz(r))
            largest = max(largest, max(abs(a - b) for a, b in zip(r, s)))
    if not positions:
        return plan(ReturnKind.UNCHANGED, "no point moved", object_id=obj.id)
    notes = []
    cage_like = len(positions) >= CAGE_MOVED_SHARE * len(sent) and largest <= CAGE_TOLERANCE * _extent(sent)
    if cage_like:
        notes.append(f"looks like ZBrush's Cage reconstruction, not a sculpt: every point moved by at most {largest:.2g}"
                     " - exact symmetry pairs may break (Re-Symmetrize)")
    mesh = obj.mesh
    targets = sum(1 for lid in mesh.point_layer_ids() if mesh.point_layer_info(lid).kind is LayerKind.VECTOR)
    if targets:
        notes.append(f"{targets} morph target{'s' if targets != 1 else ''} follow the new base")
    return plan(ReturnKind.POSITIONS, f"{len(positions)} of {len(sent)} points moved", object_id=obj.id,
                positions=positions, notes=notes, cage_like=cage_like)


def mesh_from_goz(goz: GozMesh) -> Mesh:
    """A new mesh in Mirai's world frame (the new-object path: identity placement, fresh IDs)."""
    mesh = Mesh()
    ids = [mesh.add_vertex(from_goz(p)) for p in goz.points]
    for face in goz.faces:
        mesh.add_face([ids[i] for i in face])
    return mesh


def rebase_manifest(manifest: Manifest, scene: Scene, obj: SceneObject, to_world: Placement) -> Manifest:
    """After an applied return Mirai and ZBrush hold the same shape: the manifest takes the object's new fingerprint,
    so the next GoZ of the same SubTool (more sculpting, no resend) plans against it instead of reading as a conflict.
    An Undo of the apply makes Mirai differ again - that next return is then a conflict (fail-closed)."""
    from dataclasses import replace

    return replace(manifest, fingerprint=fingerprint(scene, obj), sent_float32=float32_hash(sent_points(obj, to_world)))
