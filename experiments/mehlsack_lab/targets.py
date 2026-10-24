"""Hover targets: the Loop or Ring of a hovered edge and its seed vertices (handoff E3).

The traversal itself is Production's `mirai.topology.loop_ring` — imported read-only, its
conservative rules unchanged (until 2026-10-24 through the Playground's re-export
`playground.topology_tools.loop_ring`, removed with the Playground).

`loop_ring` is duck-typed over the mesh query API (`is_valid_edge`, `edge_vertices`,
`edge_faces`, `face_edges`, `vertex_edges`). Core V1's `Mesh.vertex_edges()` is an O(E)
scan, so a loop of 128 edges on the 32 × 32 box costs ~1.5 M edge checks per hover.
`TopologyIndex` answers the same five queries from tables built once through the
public Core API. It is valid as long as the topology does not change — true for the
whole edit phase (Slice 1 is Move only); a new box builds a new index. Same lists in
the same order as the Core (pinned by `tests/test_targets.py`: every loop and ring
equals the traversal on the raw mesh), so the rules stay `loop_ring`'s.

Rim override (Slice 2a E15, Manu O4: "Ja, macht in diesem Experiment Sinn"): the cap
corners have valence 3, where `loop_ring` stops. `TargetFinder` may be given the box's
rims (closed vertex cycles from `box.box_rims`); a Loop hover on a rim edge then yields
the **closed** rim loop (`4n` edges, around the corners). This is an explicit lab
override in front of `loop_ring` — `loop_ring.py` and `TopologyIndex` stay untouched, every
other Loop and every Ring is `loop_ring`'s (pinned by `tests/test_targets.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from core import EdgeId, FaceId, Mesh, VertexId
from mirai.topology.loop_ring import edge_loop, edge_ring

MODE_LOOP = "loop"
MODE_RING = "ring"
MODES = (MODE_LOOP, MODE_RING)
MODE_LABELS = {MODE_LOOP: "Loop", MODE_RING: "Ring"}


class TopologyIndex:
    """Read-only topology tables of one mesh (see module docstring)."""

    def __init__(self, mesh: Mesh) -> None:
        self.mesh = mesh
        self.edges: list[EdgeId] = mesh.all_edge_ids()
        self.edge_ends: dict[EdgeId, tuple[VertexId, VertexId]] = {}
        self.edges_of_vertex: dict[VertexId, list[EdgeId]] = {v: [] for v in mesh.all_vertex_ids()}
        for eid in self.edges:
            a, b = mesh.edge_vertices(eid)
            self.edge_ends[eid] = (a, b)
            # Core order: `vertex_edges` lists edges in `all_edge_ids()` order.
            self.edges_of_vertex[a].append(eid)
            self.edges_of_vertex[b].append(eid)
        self.faces_of_edge: dict[EdgeId, list[FaceId]] = {e: mesh.edge_faces(e) for e in self.edges}
        self.edges_of_face: dict[FaceId, list[EdgeId]] = {
            f: mesh.face_edges(f) for f in mesh.all_face_ids()
        }

    # -- the query surface `loop_ring` uses ------------------------------------------

    def is_valid_edge(self, edge_id) -> bool:
        return edge_id in self.edge_ends

    def edge_vertices(self, edge_id):
        return self.edge_ends[edge_id]

    def edge_faces(self, edge_id):
        return list(self.faces_of_edge[edge_id])

    def face_edges(self, face_id):
        return list(self.edges_of_face[face_id])

    def vertex_edges(self, vertex_id):
        return list(self.edges_of_vertex[vertex_id])


@dataclass(frozen=True)
class Target:
    """What a hover on `edge` in `mode` grabs: the traversed edges and their vertices
    (the seeds, `w = 1`)."""

    mode: str
    edge: EdgeId
    edges: tuple[EdgeId, ...]
    closed: bool
    seeds: frozenset
    #: A seed (first end of the hovered edge): its live position turns a screen delta into a
    #: world delta, like the anchor vertex of the app's `MoveTool`. It moves by the full delta.
    anchor: VertexId


class TargetFinder:
    """Loop/Ring targets of one fixed topology, cached per `(mode, edge)`."""

    def __init__(self, mesh: Mesh, rims: Sequence[Sequence[VertexId]] = ()) -> None:
        self.index = TopologyIndex(mesh)
        self._cache: dict[tuple[str, EdgeId], Target] = {}
        #: rim edge -> its closed rim loop, in cycle order (see module docstring)
        self.rim_of_edge: dict[EdgeId, tuple[EdgeId, ...]] = {}
        edge_of_pair = {frozenset(ends): eid for eid, ends in self.index.edge_ends.items()}
        for cycle in rims:
            pairs = [frozenset((cycle[t], cycle[(t + 1) % len(cycle)])) for t in range(len(cycle))]
            if any(pair not in edge_of_pair for pair in pairs):
                raise ValueError("rim cycle is not a closed chain of mesh edges")
            loop = tuple(edge_of_pair[pair] for pair in pairs)
            for eid in loop:
                self.rim_of_edge[eid] = loop

    def clear(self) -> None:
        """Forgets the cached targets (bench: measure a cold hover change)."""
        self._cache.clear()

    def target(self, edge: EdgeId, mode: str) -> Target:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
        key = (mode, edge)
        found = self._cache.get(key)
        if found is None:
            rim = self.rim_of_edge.get(edge) if mode == MODE_LOOP else None
            if rim is not None:
                start = rim.index(edge)  # hovered edge first, like a closed `loop_ring` traversal
                edges, closed = rim[start:] + rim[:start], True
            else:
                traverse = edge_loop if mode == MODE_LOOP else edge_ring
                traversal = traverse(self.index, edge)
                edges, closed = tuple(traversal.edges), traversal.closed
            seeds = frozenset(v for e in edges for v in self.index.edge_ends[e])
            found = Target(mode, edge, edges, closed, seeds, self.index.edge_ends[edge][0])
            self._cache[key] = found
        return found
