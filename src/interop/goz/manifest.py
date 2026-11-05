"""Transfer manifest and return-conflict fingerprint (AD-029 §5; E1 README §8.1, audit §7.1).

A manifest is written beside each sent `.GoZ` (`<identifier>.mirai-goz.json`, atomic) and kept in memory. It holds the
identity of the send, the dense index <-> ID maps and the **fingerprint** of the object at send time. A return is
applied in place only if the current object still has exactly that fingerprint; any difference is a conflict, never
something to compensate silently.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import asdict, dataclass, field
from typing import Optional

from core.ids import FaceId, VertexId
from core.mesh import LayerKind, Mesh
from core.scene import Scene, SceneObject

MANIFEST_VERSION = 1
#: GoZ = Mirai rotated 180 deg about X (E1-Q6): written as (x, -y, -z), read back with the same map.
AXIS_CONVENTION = "x,-y,-z"
REPRESENTATION_BASE = "base"


def _digest(chunks) -> str:
    h = hashlib.sha256()
    for chunk in chunks:
        h.update(chunk)
    return h.hexdigest()


def topology_hash(mesh: Mesh) -> str:
    """Ascending vertex IDs, then every face ID with its boundary as stored (rotation included)."""
    def chunks():
        vids = mesh.all_vertex_ids()
        yield struct.pack(f"<I{len(vids)}q", len(vids), *(int(v) for v in vids))
        for fid in mesh.all_face_ids():
            boundary = mesh.face_vertices(fid)
            yield struct.pack(f"<qI{len(boundary)}q", int(fid), len(boundary), *(int(v) for v in boundary))
    return _digest(chunks())


def positions_hash(mesh: Mesh) -> str:
    """The float64 rest positions in vertex-ID order."""
    return _digest(struct.pack("<3d", *mesh.vertex_position(v)) for v in mesh.all_vertex_ids())


def float32_hash(points) -> str:
    return _digest(struct.pack("<3f", *p) for p in points)


def layers_fingerprint(mesh: Mesh) -> dict:
    """Every point layer's meta (id, name, kind, new-point rule, order) and its values hash: morph targets are
    relative offsets (J-3) and weights hang on vertex IDs, so an edit of either since the send is a conflict too."""
    out = []
    for lid in mesh.point_layer_ids():
        info = mesh.point_layer_info(lid)
        items = mesh.layer_items(lid)
        if info.kind is LayerKind.VECTOR:
            values = _digest(struct.pack("<q3d", int(v), *value) for v, value in items)
        else:
            values = _digest([json.dumps([[int(v), [[int(b), w] for b, w in value]] for v, value in items]).encode()])
        out.append({"id": int(lid), "name": info.name, "kind": info.kind.value, "new_point": info.new_point,
                    "values": values})
    return {"layers": out}


def regions_hash(mesh: Mesh) -> Optional[str]:
    """The stored face regions as saved (names in order, face IDs incl. dead ones); None without regions."""
    regions = mesh.face_regions
    if regions is None:
        return None
    return _digest([json.dumps([[r.name, sorted(int(f) for f in r.faces)] for r in regions.regions]).encode()])


def placement(obj: SceneObject) -> dict:
    t = obj.transform
    return {"translation": list(t.translation), "rotation": [list(r) for r in t.rotation], "scale": t.scale,
            "pivot": list(obj.pivot), "state": obj.state.value}


def rig_hash(scene: Scene) -> Optional[str]:
    return None if scene.rig is None else _digest([json.dumps(scene.rig.to_dict(), sort_keys=True).encode()])


def fingerprint(scene: Scene, obj: SceneObject) -> dict:
    mesh = obj.mesh
    return {
        "topology": topology_hash(mesh),
        "vertex_count": len(mesh.all_vertex_ids()),
        "face_count": len(mesh.all_face_ids()),
        "positions": positions_hash(mesh),
        "placement": placement(obj),
        "layers": layers_fingerprint(mesh),
        "rig": rig_hash(scene),
        "regions": regions_hash(mesh),
    }


def fingerprint_differences(sent: dict, now: dict) -> list[str]:
    """Readable names of the parts that differ (empty = the object is as it was sent). `regions` is compared only when
    the sent fingerprint has it (a P1 manifest on disk predates it)."""
    names = {"topology": "topology", "vertex_count": "topology", "face_count": "topology",
             "positions": "point positions", "placement": "object placement", "layers": "morph targets / weights",
             "rig": "rig", "regions": "groups"}
    out: list[str] = []
    for key, label in names.items():
        if key == "regions" and key not in sent:
            continue
        if sent.get(key) != now.get(key) and label not in out:
            out.append(label)
    return out


@dataclass
class Manifest:
    transfer_id: str
    session_id: str
    identifier: str
    object_id: int
    object_name: str
    scene_path: Optional[str]
    vertex_ids: list[int]
    face_ids: list[int]
    faces: list[list[int]]
    sent_float32: str
    fingerprint: dict
    sent_at: float
    representation: str = REPRESENTATION_BASE
    axis: str = AXIS_CONVENTION
    version: int = MANIFEST_VERSION
    #: ZBrush's points of the last applied return (GoZ frame, float32), None = as sent (bridge.rebase_manifest).
    zbrush_points: Optional[list] = None
    #: P2a polygroups (None = sent without GROUPS, a P1 manifest): the id of every sent face, id -> region name (ids
    #: ZBrush returned for new groups join it after an apply), the id of the faces in no region, and the faces that were
    #: in more than one region (`[face index, [other region names]]`; the id names the first in region order)
    sent_groups: Optional[list[int]] = None
    group_names: dict[str, str] = field(default_factory=dict)
    rest_group: Optional[int] = None
    group_overlaps: list = field(default_factory=list)
    #: ZBrush's group ids of the last applied return, None = as sent (like `zbrush_points`)
    zbrush_groups: Optional[list[int]] = None
    #: P2b: every n-gon split in the file, `[face id, [indices of its pieces in faces]]` (`faces` / `face_ids` hold
    #: one entry per sent piece; a piece repeats its n-gon's face id)
    ngons: list = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "Manifest":
        raw = json.loads(text)
        if raw.get("version") != MANIFEST_VERSION or raw.get("axis") != AXIS_CONVENTION:
            raise ValueError(f"unsupported manifest (version {raw.get('version')!r}, axis {raw.get('axis')!r})")
        return cls(**raw)

    def vertex_id(self, index: int) -> VertexId:
        return VertexId(self.vertex_ids[index])

    def face_id(self, index: int) -> FaceId:
        return FaceId(self.face_ids[index])
