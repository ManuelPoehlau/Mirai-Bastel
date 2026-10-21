"""AD-023 H1 for Delete: a delta history entry instead of two whole-mesh snapshots.

Capture mechanism (AD-023 §7 asks for it to be stated): **declared neighbourhood + local diff.** Before the
unchanged Core op runs (`apply_removal` -> `Mesh.delete_faces / delete_edges / delete_vertices`), the closure it
can touch is exported locally - the faces to delete, every edge of them (plus the given edges), every endpoint of
those edges (plus the given vertices). After the op, whatever of that closure no longer exists is "removed", and
every surviving edge of it whose face list changed is "changed". No full snapshot, no Core hook, no recording
proxy. The price is a per-op contract: **the op mutates nothing outside its declared neighbourhood.** For Delete
that holds by construction of `Mesh._delete_region` (it removes the faces, edges of those faces and their
now edgeless endpoints, and edits the face lists of the surviving edges of those faces - nothing else); the tests
check it against full snapshots on randomised sequences (`tests/test_delta_equivalence.py`).

What stands in for the Core API: `_reinsert` / `_remove` below reach into `Mesh._vertices / _edges / _faces /
_edge_lookup`. In production this would be a Core method pair (export / apply a partial state), i.e. a
CORE_V1_FREEZE §7 exception with contract tests. Nothing under `src/` is changed here.

Exactness contract (AD-023 §2 H1), as this entry meets it:
1. ID counters: Delete allocates nothing; the entry never touches the allocators (they stay forward).
2. Symmetry definition: Delete does not change it (it rides in the mesh, the entry leaves it alone).
3. Order inside records: boundaries and `edge.faces` are stored as lists and restored as stored.
4. Dict iteration order of `all_*_ids()`: restored exactly. Mesh dicts are in ascending ID order (IDs are
   allocated monotonically and only ever appended; `load_state` keeps the snapshot's order); the capture checks
   that per container and then re-inserts by bisection. If a container is not ascending, the capture records
   the positions instead (slower, still exact). `--order append` skips the restore (measures its price).
5. Rollback: Delete validates every ID before it mutates (MeshError -> mesh unchanged), so no `before` snapshot
   for rollback is needed.
6. "Changed?": the op's own result - anything in the removed sets.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

#: "exact" (default) or "append" (no order restore: measures what exactness costs; NOT exact).
ORDER_MODE = "exact"

_CONTAINERS = ("_vertices", "_edges", "_faces")


@dataclass
class MeshDelta:
    """Records of one Delete (before values) - enough to apply it forward (Redo) and backward (Undo)."""

    vertices: dict = field(default_factory=dict)  # VertexId -> position (removed vertices)
    edges: dict = field(default_factory=dict)  # EdgeId -> (v0, v1, faces list before) (removed edges)
    faces: dict = field(default_factory=dict)  # FaceId -> boundary list (removed faces)
    edge_faces: dict = field(default_factory=dict)  # EdgeId -> (faces before, faces after) (surviving edges)
    #: per container: None = ascending (re-insert by bisection), else [(position before, key)] ascending
    positions: dict = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not (self.vertices or self.edges or self.faces)

    def ring_vertices(self) -> set:
        """Surviving vertices whose incident faces changed (their normals change)."""
        ring: set = set()
        for boundary in self.faces.values():
            ring.update(boundary)
        return ring - self.vertices.keys()


def _neighbourhood(mesh, mode_name: str, ids) -> tuple[set, set, set]:
    """(faces, edges, vertices) the Delete of `ids` in `mode_name` may touch; mirrors `Mesh.delete_*`."""
    vertices: set = set()
    edges: set = set()
    if mode_name == "FACE":
        faces = set(ids)
    elif mode_name == "EDGE":
        edges = set(ids)
        faces = {f for e in edges for f in mesh.edge_faces(e)}
    else:
        vertices = set(ids)
        # Whole-mesh work: the Core has no vertex -> edge index (`vertex_edges` scans every edge); the op itself
        # (`Mesh.delete_vertices`) does the same scan. One pass instead of one scan per vertex.
        if len(vertices) <= 2:
            edges = {e for v in vertices for e in mesh.vertex_edges(v)}
        else:
            edges = {e for e in mesh.all_edge_ids() if not vertices.isdisjoint(mesh.edge_vertices(e))}
        faces = {f for e in edges for f in mesh.edge_faces(e)}
    for f in faces:
        edges.update(mesh.face_edges(f))
    for e in edges:
        vertices.update(mesh.edge_vertices(e))
    return faces, edges, vertices


def _ascending(keys: list) -> bool:
    return keys == sorted(keys)


def capture_removal(mesh, mode, ids, run) -> tuple[MeshDelta, object]:
    """Runs `run()` (the unchanged op) and returns (delta, its result). `mode` is a `SelectionMode`.
    Invalid IDs: `run()` raises before anything changes (the Core validates first), nothing is captured."""
    valid = {"FACE": mesh.is_valid_face, "EDGE": mesh.is_valid_edge, "VERTEX": mesh.is_valid_vertex}[mode.name]
    if not all(valid(i) for i in ids):
        return MeshDelta(), run()
    faces, edges, vertices = _neighbourhood(mesh, mode.name, ids)
    position, face_vertices, edge_vertices, edge_faces = (
        mesh.vertex_position, mesh.face_vertices, mesh.edge_vertices, mesh.edge_faces)
    pos = {v: position(v) for v in vertices}
    erec = {e: (*edge_vertices(e), edge_faces(e)) for e in edges}
    frec = {f: face_vertices(f) for f in faces}
    positions: dict = {}
    if ORDER_MODE == "exact":
        for name, candidates in zip(_CONTAINERS, (vertices, edges, faces)):
            keys = list(getattr(mesh, name))
            if _ascending(keys):
                positions[name] = None
            else:
                positions[name] = [(i, k) for i, k in enumerate(keys) if k in candidates]

    result = run()

    delta = MeshDelta(positions=positions)
    for v in vertices:
        if not mesh.is_valid_vertex(v):
            delta.vertices[v] = pos[v]
    for e in edges:
        if not mesh.is_valid_edge(e):
            delta.edges[e] = erec[e]
        else:
            now = edge_faces(e)
            if now != erec[e][2]:
                delta.edge_faces[e] = (erec[e][2], now)
    for f in faces:
        if not mesh.is_valid_face(f):
            delta.faces[f] = frec[f]
    if ORDER_MODE == "exact":
        for name, removed in zip(_CONTAINERS, (delta.vertices, delta.edges, delta.faces)):
            if positions[name] is not None:
                positions[name] = [(i, k) for i, k in positions[name] if k in removed]
    return delta, result


# -- applying (the stand-in for a Core "apply partial state" API) ------------------------------------


def _reinsert(container: dict, records: dict, positions) -> None:
    """Inserts `records` (key -> value) into `container` at their former places (in place: the Mesh holds the
    dict). `positions` None = the container was ascending: place by bisection."""
    if not records:
        return
    if ORDER_MODE != "exact":
        container.update(records)
        return
    keys = list(container)
    if positions is None:
        if not keys or min(records) > keys[-1]:
            container.update(sorted(records.items()))
            return
        items = list(container.items())
        # Insert from the largest key down so earlier insert points stay valid.
        for k in sorted(records, reverse=True):
            items.insert(bisect.bisect_left(keys, k), (k, records[k]))
    else:
        items = list(container.items())
        for i, k in positions:  # ascending former positions: each insert lands where it was
            items.insert(i, (k, records[k]))
    container.clear()
    container.update(items)


def apply_backward(mesh, delta: MeshDelta) -> None:
    """Undo of a Delete: the mesh is in the after-state; re-insert what was removed, restore edge face lists."""
    from core.mesh import _EdgeData, _FaceData, _VertexData

    _reinsert(mesh._vertices, {v: _VertexData(position=p) for v, p in delta.vertices.items()},
              delta.positions.get("_vertices"))
    _reinsert(mesh._edges, {e: _EdgeData(v0=a, v1=b, faces=list(fs)) for e, (a, b, fs) in delta.edges.items()},
              delta.positions.get("_edges"))
    lookup = mesh._edge_lookup
    for e, (a, b, _fs) in delta.edges.items():
        lookup[frozenset((a, b))] = e
    _reinsert(mesh._faces, {f: _FaceData(boundary=list(b)) for f, b in delta.faces.items()},
              delta.positions.get("_faces"))
    edges = mesh._edges
    for e, (before, _after) in delta.edge_faces.items():
        edges[e].faces = list(before)


def apply_forward(mesh, delta: MeshDelta) -> None:
    """Redo of a Delete: the mesh is in the before-state; remove the records, set the edge face lists."""
    edges, lookup = mesh._edges, mesh._edge_lookup
    for f in delta.faces:
        del mesh._faces[f]
    for e, (a, b, _fs) in delta.edges.items():
        del edges[e]
        del lookup[frozenset((a, b))]
    for v in delta.vertices:
        del mesh._vertices[v]
    for e, (_before, after) in delta.edge_faces.items():
        edges[e].faces = list(after)


class DeltaCommand:
    """`Command` protocol (`core.history`): one Delete as a delta. `on_applied(delta, forward)` is told after
    each undo / redo, so the Application can patch the viewport from the touched set (AD-023 U)."""

    def __init__(self, mesh, delta: MeshDelta, description: str, on_applied=None) -> None:
        self.mesh = mesh
        self.delta = delta
        self.description = description
        self.on_applied = on_applied

    def undo(self) -> None:
        apply_backward(self.mesh, self.delta)
        if self.on_applied is not None:
            self.on_applied(self.delta, False)

    def redo(self) -> None:
        apply_forward(self.mesh, self.delta)
        if self.on_applied is not None:
            self.on_applied(self.delta, True)
