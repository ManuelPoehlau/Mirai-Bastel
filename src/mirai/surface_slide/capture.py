"""Capture: the drawn triangles of a face set of a `core.Mesh` as a `SlideReference` (audit B1, B2, §13.2).

Phase 2. Reads the mesh through the Core's query API only; never writes it.

- **Drawn triangles (B1).** Every captured polygon is cut by `viewport.derived.triangulate_face` (the rule behind
  `triangulate_mesh_face`, "der eine Ort"): no second triangulation rule. The positions come from the press snapshot
  (`MeshHalf.position`), so a capture that grows while the gesture already wrote vertices still sees the press state.
- **Half (symmetry).** Under a symmetry definition only the driven half is captured: polygons with no corner on the
  passive side. Polygons with corners strictly on both sides (*straddling*) and hidden polygons are never captured.
  The declared seam edges and every edge to a polygon that is not captured *because it may not be* (passive, hidden,
  straddling) are barriers (`BARRIER_EDGE`): a trace stops short of them (E3).
- **Region (B2).** `margin` limits the capture to the polygons around the vertices within that distance of the driven
  vertices (Dijkstra over the polygons' corners, straight-line steps); the edges to eligible polygons left out are
  `CAPTURE_EDGE`. A chain a driven vertex walks (the seam, an open boundary, E5) is captured whole, so a chain walk
  never ends at the region border. `margin=None` captures every eligible polygon (the full capture of gate G2).
- **Canonical order.** Polygons by ascending `FaceId`, triangles in `triangulate_face` order, rows by ascending
  `VertexId`. A region capture is then a sub-array of the full capture in the same relative order, so every
  order-dependent sum and tie-break (angle-weighted normals, the transport's shortest paths) comes out the same: as
  long as no trace reaches the region border, a region slide equals the full slide bit for bit (gate G2).
- **Seam normals.** A seam vertex's captured ring is half its ring. Its normal is the angle-weighted normal of the
  half with the plane component removed: exactly the normal of the half plus its mirror image (direction).
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Iterable, Mapping

from core import EdgeId, FaceId, Mesh, VertexId
from viewport.derived import triangulate_face
from viewport.packed_geometry import np  # NumPy behind its pinned-version check (AD-032 §2)

from .curves import EdgeChain
from .reference import CAPTURE_EDGE, SlideReference, unit

_I = np.intp
Position = tuple[float, float, float]


class MeshHalf:
    """The part of `mesh` a slide may capture, at the press state (module docstring).

    `positions`: press positions of the vertices the gesture writes (read instead of the mesh, which the gesture
    changes). `plane`: `(point, normal)` of an exact axis plane or None; `side`: +1 / -1, the driven half.
    `hidden_faces`: polygons never captured. `seam_edges`: the declared seam (barriers, the seam chain)."""

    def __init__(self, mesh: Mesh, *, positions: Mapping[VertexId, Position] | None = None,
                 plane: tuple[Position, Position] | None = None, side: int = 0,
                 hidden_faces: Iterable[FaceId] = (), seam_edges: Iterable[EdgeId] = ()) -> None:
        self.mesh = mesh
        self._fixed = dict(positions or {})
        self.plane = plane
        self.side = int(side) if plane is not None else 0
        self.hidden_faces = frozenset(f for f in hidden_faces if mesh.is_valid_face(f))
        self.seam_edges = frozenset(e for e in seam_edges if mesh.is_valid_edge(e))
        self.seam_vertices = frozenset(v for e in self.seam_edges for v in mesh.edge_vertices(e))
        self._faces_around: dict[VertexId, list[FaceId]] = {}
        self._side: dict[VertexId, int] = {}
        self._eligible: dict[FaceId, bool] = {}
        self._straddles: dict[FaceId, bool] = {}

    def position(self, v: VertexId) -> Position:
        p = self._fixed.get(v)
        return self.mesh.vertex_position(v) if p is None else p

    def side_of(self, v: VertexId) -> int:
        """-1 / 0 / +1: the side of the plane `v` is on (0 without a plane)."""
        s = self._side.get(v)
        if s is None:
            if self.plane is None:
                s = 0
            else:
                point, normal = self.plane
                d = sum((p - o) * n for p, o, n in zip(self.position(v), point, normal))
                s = (d > 0.0) - (d < 0.0)
            self._side[v] = s
        return s

    def faces_around(self, v: VertexId) -> list[FaceId]:
        """The polygons with corner `v`, ascending."""
        out = self._faces_around.get(v)
        if out is None:
            mesh = self.mesh
            out = sorted({f for e in mesh.vertex_edges(v) for f in mesh.edge_faces(e)})
            self._faces_around[v] = out
        return out

    def straddles(self, f: FaceId) -> bool:
        """A polygon with corners strictly on both sides of the plane."""
        s = self._straddles.get(f)
        if s is None:
            sides = {self.side_of(v) for v in self.mesh.face_vertices(f)}
            s = 1 in sides and -1 in sides
            self._straddles[f] = s
        return s

    def eligible(self, f: FaceId) -> bool:
        """May `f` be captured: not hidden, not straddling, no corner on the passive side."""
        e = self._eligible.get(f)
        if e is None:
            e = f not in self.hidden_faces
            if e and self.plane is not None:
                e = all(self.side_of(v) != -self.side for v in self.mesh.face_vertices(f))
            self._eligible[f] = e
        return e

    def chain_edges(self, v: VertexId, *, seam: bool) -> list[tuple[EdgeId, VertexId]]:
        """The chain edges at `v` with their other end: the declared seam edges (`seam`), or the open boundary edges
        (one polygon, an eligible one; not seam)."""
        mesh = self.mesh
        out = []
        for e in mesh.vertex_edges(v):
            if seam:
                if e not in self.seam_edges:
                    continue
            else:
                faces = mesh.edge_faces(e)
                if e in self.seam_edges or len(faces) != 1 or not self.eligible(faces[0]):
                    continue
            a, b = mesh.edge_vertices(e)
            out.append((e, b if a == v else a))
        return out


@dataclass(frozen=True)
class SlideCapture:
    """One captured reference. `vertex_ids[row]` is the vertex of reference row `row` (ascending), `row_of` the
    inverse; `face_ids` the captured polygons (ascending); `triangle_face[t]` the polygon triangle `t` belongs to;
    `chains` the seam chain and the open-boundary chain (that order; either may be absent). `margin` None = full
    capture; `complete` = no capture border left (the capture can no longer grow)."""

    reference: SlideReference
    vertex_ids: tuple[VertexId, ...]
    row_of: dict[VertexId, int]
    face_ids: tuple[FaceId, ...]
    triangle_face: tuple[FaceId, ...]
    chains: tuple[EdgeChain, ...]
    seam_rows: tuple[int, ...]
    margin: float | None
    complete: bool


def region_faces(half: MeshHalf, driven: Iterable[VertexId], margin: float) -> set[FaceId]:
    """The eligible polygons around every vertex within `margin` of `driven` (Dijkstra over the corners of eligible
    polygons, straight-line steps), plus every eligible polygon along a chain a driven vertex is on."""
    dist: dict[VertexId, float] = {}
    heap: list[tuple[float, VertexId]] = []
    for v in sorted(set(driven)):
        dist[v] = 0.0
        heap.append((0.0, v))
    heapq.heapify(heap)
    done: set[VertexId] = set()
    faces: set[FaceId] = set()
    mesh = half.mesh
    while heap:
        d, v = heapq.heappop(heap)
        if v in done:
            continue
        done.add(v)
        p = half.position(v)
        for f in half.faces_around(v):
            if not half.eligible(f):
                continue
            faces.add(f)
            for o in mesh.face_vertices(f):
                if o in done:
                    continue
                q = half.position(o)
                nd = d + math.sqrt((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2)
                if nd <= margin and nd < dist.get(o, math.inf):
                    dist[o] = nd
                    heapq.heappush(heap, (nd, o))
    faces |= chain_faces(half, driven)
    return faces


def chain_faces(half: MeshHalf, driven: Iterable[VertexId]) -> set[FaceId]:
    """The eligible polygons along every chain component (seam, open boundary) a driven vertex is on."""
    mesh = half.mesh
    faces: set[FaceId] = set()
    for seam in (True, False):
        # a vertex walks the first chain it is on: the seam before the boundary
        start = [v for v in driven if (v in half.seam_vertices) == seam]
        seen: set[VertexId] = set(start)
        todo = list(start)
        while todo:
            v = todo.pop()
            for e, o in half.chain_edges(v, seam=seam):
                faces.update(f for f in mesh.edge_faces(e) if half.eligible(f))
                if o not in seen:
                    seen.add(o)
                    todo.append(o)
    return faces


def all_faces(half: MeshHalf) -> set[FaceId]:
    return {f for f in half.mesh.all_face_ids() if half.eligible(f)}


def build_capture(half: MeshHalf, faces: Iterable[FaceId], *, edge_scale: float,
                  margin: float | None) -> SlideCapture:
    """The `SlideReference` of `faces` (module docstring: drawn triangles, edge codes, canonical order)."""
    mesh = half.mesh
    face_ids = tuple(sorted(faces))
    captured = set(face_ids)
    vertex_ids = tuple(sorted({v for f in face_ids for v in mesh.face_vertices(f)}))
    row_of = {v: i for i, v in enumerate(vertex_ids)}
    V = np.array([half.position(v) for v in vertex_ids], dtype=np.float64).reshape(-1, 3)
    tris: list[tuple[int, int, int]] = []
    tri_face: list[FaceId] = []
    barriers: list[tuple[int, int]] = []
    borders: list[tuple[int, int]] = []
    done_edges: set[EdgeId] = set()
    for f in face_ids:
        boundary = mesh.face_vertices(f)
        for a, b, c in triangulate_face(boundary, {v: half.position(v) for v in boundary}):
            tris.append((row_of[a], row_of[b], row_of[c]))
            tri_face.append(f)
        for e in mesh.face_edges(f):
            if e in done_edges:
                continue
            done_edges.add(e)
            a, b = mesh.edge_vertices(e)
            pair = (row_of[a], row_of[b])
            if e in half.seam_edges:
                barriers.append(pair)
                continue
            others = [g for g in mesh.edge_faces(e) if g != f]
            if not others or others[0] in captured:
                continue
            (borders if half.eligible(others[0]) else barriers).append(pair)
    T = np.array(tris, dtype=_I).reshape(-1, 3)
    ref = SlideReference(V, T, barrier_edges=barriers, capture_edges=borders, edge_scale=edge_scale)
    seam_rows = tuple(sorted(row_of[v] for v in half.seam_vertices if v in row_of))
    if half.plane is not None and seam_rows:
        VN = np.array(ref.VN)
        rows = np.array(seam_rows, dtype=_I)
        axis = int(np.argmax(np.abs(np.asarray(half.plane[1], dtype=np.float64))))
        VN[rows, axis] = 0.0
        VN[rows] = unit(VN[rows])
        ref = SlideReference(V, T, barrier_edges=barriers, capture_edges=borders, edge_scale=edge_scale,
                             vertex_normals=VN)

    chains: list[EdgeChain] = []
    seam_pairs = [(row_of[a], row_of[b]) for e in sorted(half.seam_edges)
                  for a, b in (mesh.edge_vertices(e),) if a in row_of and b in row_of]
    if seam_pairs:
        seam_pairs_arr = np.array(seam_pairs, dtype=_I)
        tri, _ = ref.edge_slots(seam_pairs_arr)
        seam_pairs_arr = seam_pairs_arr[tri >= 0]
        if len(seam_pairs_arr):
            ordered = np.unique(np.sort(seam_pairs_arr, axis=1), axis=0)
            chains.append(EdgeChain(ref, ordered, stop_short=EdgeChain(ref, ordered).ends()))
    boundary = EdgeChain.boundary(ref)
    if boundary.n_edges:
        stops = sorted(set(boundary.ends()) | set(seam_rows))
        chains.append(EdgeChain.boundary(ref, stop_short=stops))
    return SlideCapture(ref, vertex_ids, row_of, face_ids, tuple(tri_face), tuple(chains), seam_rows, margin,
                        not bool(np.any(ref.nbr == CAPTURE_EDGE)))
