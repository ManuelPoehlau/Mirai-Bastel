"""The Knife's commit-time resolver (WP-KNIFE-01 S1; AD-017 addendum 2026-10-01 "One Knife S1").

Knife-owned (AD-017 decision #1: no universal Cut Engine — Split, Edge Connect and Vertex Connect do
not route through this module). Moved, not copied, from the Knife Face Lab
(`playground/experiments/knife_face/engine.py` / `engine_q5.py`, Variants D and Q5 — the Q5 model is the
Lab's KEEP of 2026-09-30); the Lab sessions keep the click-time part (path, chains, undo/redo snapshots,
accepts/hover/click, planner, picking, HUD text) and call this at commit.

Contract:

- **Camera-free and session-free.** No import of `viewport`, `playground`, `mirai.interaction`, Selection
  or History (`tests/test_knife_resolve.py` checks it). Input: the mesh, the session-start mesh state
  (`export_state()`) and the path as plain, serialisable records. Output: a `KnifeResolution`.
- **Mutations** only through `Mesh.split_face` (AD-017 K1 / B2c), `split_edge`, `connect_vertices`
  (`split_face(..., positions=())` is `connect_vertices`), and `export_state` / `load_state` for the
  rollback of a dropped run or of a whole session (`check_commit`). No `remove_face` / `add_vertex` /
  `add_face`.
- **Deterministic.** Ties are broken by position, never by click order; nothing depends on object
  identity — every point carries an explicit id (`pid`).

Path records (dicts; the resolver never mutates them):

    {"pid": P, "kind": "vertex", "vertex_id": VertexId}
    {"pid": P, "kind": "edge",   "edge_id": EdgeId, "t": float}            # t along the click-time edge
    {"pid": P, "kind": "face",   "face_id": FaceId, "position": (x, y, z)}  # an interior click
      ... optionally "crossing": True (a planner crossing, not clicked)
    {"kind": "break", "reason": "gap" | "edge"}                             # a skipped stretch (Q5)
    {"kind": "break", "reason": "closed", "cyclic": bool}                   # a chain end (Q5)

`pid` is any hashable id unique per point of the session: the same point appearing twice (a closed
chain's seed, a click on an earlier point) carries the same `pid`, two different points never do. The
resolver's own helper points (corner ends of a tail join, the placeholder of an interior seed) get
pids of the form `("resolver", n)`, which no session id can equal.

Two resolutions, one per Lab variant, because their rules differ (D is superseded but still runs):

- `resolve_collected` (Variant D): the path is one chain; an all-interior path of >= 3 points in one face
  is a closed shape (two bridges); leading and trailing interior points are dropped.
- `resolve_cross_face` (Variant Q5): chains separated by "closed" breaks, gap breaks inside a chain,
  cyclic closes, seeded chains, earlier points merged, the last interior click of a stretch joined to the
  nearest corner of its face (Artist decision 2026-09-30).

Behaviour (what is cut, what is dropped and why, every HUD count) is exactly the Lab's at the KEEP state;
the record of each rule lives in `playground/experiments/knife_face/decision.md`. Face constructions now
go through `Mesh.split_face`; a closed shape and a loop at a point are two calls each and burn one
intermediate FaceId (AD-001) — id *values* differ from the Lab's B2b stand-ins, the faces do not
(`playground/tests/test_split_face_equivalence.py`, `playground/tests/test_knife_resolver_golden.py`).
"""

from __future__ import annotations

import collections
import itertools
import math
from dataclasses import dataclass, field
from typing import Any

from core import EdgeId, FaceId, VertexId
from core.mesh import MeshError

from .face_geometry import (
    GEO_EPS,
    FaceFrame,
    Position,
    dist3,
    face_problem,
    loop_matches_winding,
    proper_cross2,
    segment_in_face,
    v_dot,
)

# Directions closer than this (radians) are one direction.
_ANGLE_EPS = 1e-9

# Why a loop closed at a single point could not be built (HUD note; decision.md, 2026-09-30).
LOOP_NO_AREA = "out to one point and straight back — no area"
LOOP_NESTED = "it winds round another loop's point"
LOOP_CROSSED = "the run cuts through its own loop again"
# The loop leaves its face but nothing this run cut crosses it: another loop's bridge or an earlier run's cut
# splits it (S3b, 2026-10-01).
LOOP_OFF_FACE = "the loop does not lie inside one face"
LOOP_NO_BRIDGE = "no bridge fits"

# Distances closer than this are ties (a symmetric shape: the same distance up to float noise).
_TIE_DIGITS = 9


# ---------------------------------------------------------------------------
# Path records
# ---------------------------------------------------------------------------

def is_break(p: dict) -> bool:
    return p["kind"] == "break"


def is_chain_end(p: dict) -> bool:
    return p["kind"] == "break" and p.get("reason") == "closed"


def split_chains(path: list[dict]) -> list[tuple[list[dict], bool, bool, bool]]:
    """[(entries, closed, cyclic, seeded)] — a chain's entries keep its gap breaks.
    `seeded`: the chain starts with the closing point of the chain before it (the same point id).
    A chain holding nothing but its seed has no cut and is left out."""
    out, cur, prev_first = [], [], None
    for p in path:
        if is_chain_end(p):
            first = next((q for q in cur if not is_break(q)), None)
            out.append((cur, True, bool(p.get("cyclic")), first is not None and _same(first, prev_first)))
            prev_first = first
            cur = []
        else:
            cur.append(p)
    points = [q for q in cur if not is_break(q)]
    if points and not (len(points) == 1 and _same(points[0], prev_first)):
        out.append((cur, False, False, _same(points[0], prev_first)))
    return out


def _same(p: dict | None, q: dict | None) -> bool:
    """The same path point (same point id)."""
    return p is not None and q is not None and p["pid"] == q["pid"]


# ---------------------------------------------------------------------------
# Face constructions — each a `Mesh.split_face` composition (AD-017 K1)
# ---------------------------------------------------------------------------

def find_edge(mesh, a: VertexId, b: VertexId) -> EdgeId:
    for eid in mesh.vertex_edges(a):
        if set(mesh.edge_vertices(eid)) == {a, b}:
            return eid
    raise MeshError(f"internal: no edge between {a!r} and {b!r} after split")


def _walks(mesh, face: FaceId, u: VertexId, w: VertexId) -> bool:
    """True if `face`'s boundary steps directly from u to w."""
    b = mesh.face_vertices(face)
    return b[(b.index(u) + 1) % len(b)] == w


def split_face_path(mesh, face_id: FaceId, a: VertexId, b: VertexId, positions: list[Position]):
    """Split `face_id` along a -> positions... -> b, both existing boundary vertices of `face_id`
    (adjacent allowed with >= 1 position — FC3/FC4). One `Mesh.split_face` call.

    Returns (new_vertex_ids, face_1, face_2, path_edge_ids) — `face_1` is the side running a -> b in
    boundary order; `path_edge_ids` are the k+1 new edges a-p0-...-pk-b, in that order."""
    if a == b:
        raise MeshError("split_face_path: a and b must be distinct vertices")
    boundary = mesh.face_vertices(face_id)
    if a not in boundary or b not in boundary:
        raise MeshError("split_face_path: a, b must be boundary vertices of face_id")
    new_vs, path_edges, f1, f2 = mesh.split_face(face_id, a, b, positions)
    if boundary.index(b) < boundary.index(a):
        f1, f2 = f2, f1  # split_face orders by boundary index, not by argument (AD-017 addendum K1)
    return new_vs, f1, f2, path_edges


def select_bridge(mesh, boundary: list[VertexId], loop_positions: list[Position]):
    """LAB DEFAULT rule (spec §2, explicitly "not a UX decision") for closing
    an interior loop: pick two loop points, each nearest to a *distinct*
    boundary vertex, whose loop indices are not themselves loop-adjacent
    (except for a 3-point loop, where every pair is mutually adjacent and the
    constraint is dropped).

    Depends on geometry only, never on click order or direction (Artist decision
    2026-09-29, Task A): ties in distance are broken by position — first the loop point's,
    then the boundary vertex's, lexicographically — and only as a last resort by loop index
    (two loop points at one position). Loop adjacency is symmetric, so rotating or reversing
    the loop cannot change which points are chosen.

    "Nearest" is measured in *world* space (decision.md: the resolver has no camera).

    Returns (loop_index_1, boundary_vertex_1, loop_index_2, boundary_vertex_2).
    """
    k = len(loop_positions)
    candidates = []
    for li, pos in enumerate(loop_positions):
        best = None
        for bv in boundary:
            bpos = mesh.vertex_position(bv)
            key = (round(dist3(pos, bpos), _TIE_DIGITS), tuple(bpos))
            if best is None or key < best[0]:
                best = (key, bv)
        candidates.append((best[0][0], tuple(pos), best[0][1], li, best[1]))
    candidates.sort(key=lambda c: c[:4])

    i1, bv1 = candidates[0][3], candidates[0][4]
    for _dist, _pos, _bpos, li, bv in candidates[1:]:
        if bv == bv1:
            continue
        if k > 3 and (li - i1) % k in (1, k - 1):
            continue
        return i1, bv1, li, bv
    raise MeshError("select_bridge: no valid second bridge point (lab default rule)")


def close_loop_with_bridges(
    mesh, face_id: FaceId, loop_positions: list[Position],
    i1: int, bv1: VertexId, i2: int, bv2: VertexId,
):
    """Close an interior loop (>= 3 points) inside `face_id` by bridging it to the boundary with 2
    edges (spec §2 "closed shape stand-in"): 3 faces — the loop itself (a pure k-gon, wound like the
    parent whichever way it was clicked, Artist decision 2026-09-29, Task A), the wing between
    boundary-arc(bv1 -> bv2) and the loop arc on that side (`f_a`), the wing on the other side (`f_b`).

    Two `Mesh.split_face` calls (`test_split_face_equivalence.py`): bv1 -> loop[i1] .. loop[i2] -> bv2
    along the longer loop arc, then the rest of the loop in the piece that walks that arc in the inner
    face's (= the parent's) direction. Raises MeshError (the mesh possibly changed: the caller
    restores it). Returns (loop_vertices, f_inner, f_a, f_b, loop_edges) — vertices and edges in
    `loop_positions` order (edge i joins point i and point i + 1)."""
    k = len(loop_positions)
    if k < 3:
        raise MeshError("close_loop_with_bridges: needs >= 3 interior points")
    if i1 == i2 or bv1 == bv2:
        raise MeshError("close_loop_with_bridges: bridges must be distinct")
    boundary = mesh.face_vertices(face_id)
    if bv1 not in boundary or bv2 not in boundary:
        raise MeshError("close_loop_with_bridges: bridge vertices must be on face_id's boundary")

    fwd = [(i1 + j) % k for j in range((i2 - i1) % k + 1)]          # i1 .. i2, loop order
    back = [(i2 + j) % k for j in range((i1 - i2) % k + 1)]         # i2 .. i1, loop order
    # Call 1 takes the longer arc, so call 2 never joins two loop points call 1 made adjacent.
    first, second = (fwd, back) if len(fwd) >= len(back) else (back[::-1], fwd[::-1])
    along = (first == fwd) == loop_matches_winding(loop_positions, [mesh.vertex_position(v) for v in boundary])
    vs1, _e1, g1, g2 = mesh.split_face(face_id, bv1, bv2, [loop_positions[i] for i in first])
    host = g1 if _walks(mesh, g1, vs1[0], vs1[1]) == along else g2
    other = g2 if host == g1 else g1
    vs2, _e2, h1, h2 = mesh.split_face(host, vs1[-1], vs1[0], [loop_positions[i] for i in second[1:-1]])

    loop_vs: list[VertexId | None] = [None] * k
    for idx, v in zip(first, vs1):
        loop_vs[idx] = v
    for idx, v in zip(second[1:-1], vs2):
        loop_vs[idx] = v
    loop_set = set(loop_vs)
    f_inner = h1 if set(mesh.face_vertices(h1)) == loop_set else h2
    wing = h2 if f_inner == h1 else h1
    # f_a walks the boundary forward from bv1 (bv1 -> the next parent corner), f_b reaches bv1 from it.
    nxt = boundary[(boundary.index(bv1) + 1) % len(boundary)]
    f_a, f_b = (wing, other) if _walks(mesh, wing, bv1, nxt) else (other, wing)
    loop_edges = [find_edge(mesh, loop_vs[idx], loop_vs[(idx + 1) % k]) for idx in range(k)]
    return loop_vs, f_inner, f_a, f_b, loop_edges


def close_loop_at_vertex(mesh, face_id: FaceId, x: VertexId, loop_positions: list[Position],
                         outside: set[VertexId] | None = None):
    """A loop x -> loop_positions -> x inside `face_id`, touching its boundary at the one vertex `x`
    only (a cut that crosses itself, or leaves a point and comes back to it — Artist decision
    2026-09-30, option (a)): its own face plus **one** bridge from a loop point to another boundary
    vertex, which splits the pinched ring into two simple faces.

    Order- and direction-independent like the closed shape (Task A, 2026-09-29): the loop is wound
    like the parent; the bridge is the shortest one (loop point, boundary vertex other than `x`)
    that leaves every face simple and facing like the parent — ties by position, never by index.
    `outside`: vertices a bridge should go to first — the corners the Artist clicked on, not
    another loop's points (Artist play test 2026-09-30); the rest only if none of those works.

    Each candidate is two `Mesh.split_face` calls (x -> c1 .. cj -> bridge end, then cj -> c(j+1) ..
    -> x in the piece that walks x -> c1 in the parent's direction), taken back with `load_state`
    when it does not fit. Returns (loop_vertices, loop_face, ring_faces, loop_edges) — `loop_edges`
    in `loop_positions` order, x -> first ... last -> x. Raises MeshError when the loop is
    degenerate or no bridge fits (the mesh is then as before the call)."""
    m = len(loop_positions)
    if m < 2:
        raise MeshError("close_loop_at_vertex: a loop needs >= 2 points besides its vertex")
    boundary = mesh.face_vertices(face_id)
    if x not in boundary:
        raise MeshError("close_loop_at_vertex: x must be on face_id's boundary")
    parent_normal = FaceFrame(mesh, face_id).normal
    i = boundary.index(x)
    outer = boundary[i:] + boundary[:i]                          # x, f1 .. f(n-1)
    n = len(outer)
    along = loop_matches_winding([mesh.vertex_position(x)] + list(loop_positions),
                                 [mesh.vertex_position(v) for v in boundary])
    # canon = the loop wound like the parent: click order, or reversed. canon[j] is click point cj(j).
    cj = (lambda j: j) if along else (lambda j: m - 1 - j)
    canon_positions = [loop_positions[cj(j)] for j in range(m)]
    candidates = []
    for j, pc in enumerate(canon_positions):
        for bi in range(1, n):
            pb = mesh.vertex_position(outer[bi])
            first = 0 if outside is None or outer[bi] in outside else 1
            candidates.append((first, round(dist3(pc, pb), _TIE_DIGITS), tuple(pc), tuple(pb), j, bi))
    candidates.sort(key=lambda c: c[:4])
    base = mesh.export_state()
    for *_key, j, bi in candidates:
        jc = cj(j)                                               # the bridge's loop point, click index
        try:
            vs1, _e1, g1, g2 = mesh.split_face(face_id, x, outer[bi], loop_positions[:jc + 1])
            host = g1 if _walks(mesh, g1, x, vs1[0]) == along else g2
            ring_1 = g2 if host == g1 else g1
            vs2, _e2, h1, h2 = mesh.split_face(host, vs1[-1], x, loop_positions[jc + 1:])
            loop_vs = vs1 + vs2
            loop_set = {x, *loop_vs}
            f_loop = h1 if set(mesh.face_vertices(h1)) == loop_set else h2
            ring = [h2 if f_loop == h1 else h1, ring_1]
            ok = all(face_problem(mesh, f) is None and v_dot(FaceFrame(mesh, f).normal, parent_normal) > 0.0
                     for f in (f_loop, *ring))
        except MeshError:
            ok = False
        if ok:
            chain = [x] + loop_vs + [x]
            return loop_vs, f_loop, ring, [find_edge(mesh, u, v) for u, v in zip(chain, chain[1:])]
        mesh.load_state(base)
    raise MeshError("close_loop_at_vertex: no bridge fits")


def cut_in_face(mesh, face_id: FaceId, a: VertexId, b: VertexId, positions: list[Position]):
    """Cut one face from boundary vertex `a` to boundary vertex `b` through `positions`
    (straight when empty). Returns (path_edges, new_face_ids); ([], []) when a and b are
    neighbours on the face (along an existing edge: nothing to cut)."""
    if not positions:
        boundary = mesh.face_vertices(face_id)
        n = len(boundary)
        if (boundary.index(a) - boundary.index(b)) % n in (1, n - 1):
            return [], []
        _vs, edges, f1, f2 = mesh.split_face(face_id, a, b)
        return edges, [f1, f2]
    _new_vs, f1, f2, path_edges = split_face_path(mesh, face_id, a, b, positions)
    return path_edges, [f1, f2]


# ---------------------------------------------------------------------------
# The commit check (integrity findings 2026-09-29) and whole-session rollback
# ---------------------------------------------------------------------------

def mesh_content(state: dict) -> dict:
    """A mesh state without its id allocator counters. `load_state` only ever moves the counters
    forward (AD-001), so a mesh restored after a dropped run equals its old self in everything
    but them — and must still count as unchanged (no History entry, Task B 2026-09-30)."""
    return {k: v for k, v in state.items() if not k.endswith("_counter")}


def integrity_problem(mesh, before_state: dict) -> str | None:
    """The first geometric problem among the faces changed since `before_state` (new, or boundary
    changed), or None. Checks each such face (area, simple polygon) and, across each of its edges,
    the neighbour: at most two faces per edge, walked in opposite directions, and not facing the
    other way where the two lie (nearly) in one plane."""
    m = mesh
    before = before_state["faces"]
    touched = [f for f in m.all_face_ids()
               if before.get(int(f)) != [int(v) for v in m.face_vertices(f)]]
    normals: dict[FaceId, Position] = {}

    def normal(f):
        if f not in normals:
            normals[f] = FaceFrame(m, f).normal
        return normals[f]

    for f in touched:
        problem = face_problem(m, f)
        if problem is not None:
            return f"a face would {problem}"
    for f in touched:
        boundary = m.face_vertices(f)
        k = len(boundary)
        for i, e in enumerate(m.face_edges(f)):
            faces = m.edge_faces(e)
            if len(faces) > 2:
                return "an edge would join more than two faces"
            x, y = boundary[i], boundary[(i + 1) % k]
            for g in faces:
                if g == f:
                    continue
                gb = m.face_vertices(g)
                j = gb.index(x)
                if gb[(j + 1) % len(gb)] == y:
                    return "a face would be wound against its neighbour"
                try:
                    if v_dot(normal(f), normal(g)) < -0.5:
                        return "a face would be flipped against its neighbour"
                except MeshError:
                    return "a face would have no area"
    return None


@dataclass(frozen=True)
class CommitCheck:
    """What `check_commit` found: `after_state` is the state to put into History (None: nothing to
    commit); `problem` is why the session was rolled back (the mesh is then the session-start mesh)."""

    after_state: dict | None
    problem: str | None = None

    @property
    def rolled_back(self) -> bool:
        return self.problem is not None


def check_commit(mesh, before_state: dict) -> CommitCheck:
    """The safety net before History: a session that changed nothing commits nothing; a session
    whose result is geometrically broken is taken back as a whole (`load_state(before_state)`) —
    never half-broken geometry in History."""
    current = mesh.export_state()
    if mesh_content(current) == mesh_content(before_state):
        return CommitCheck(None)
    problem = integrity_problem(mesh, before_state)
    if problem is not None:
        mesh.load_state(before_state)
        return CommitCheck(None, problem)
    return CommitCheck(current)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClosedShape:
    """One closed interior shape (two bridges): built, or why not (`error`: a MeshError's text,
    `problem`: a face_problem of one of its faces)."""

    points: int
    error: str | None = None
    problem: str | None = None

    @property
    def built(self) -> bool:
        return self.error is None and self.problem is None


@dataclass
class KnifeResolution:
    """What a commit resolved — counts and events, no HUD text (the session words it)."""

    path_edges: list[EdgeId] = field(default_factory=list)   # the cut edges, in path order (residue)
    empty: bool = False                     # no points at all
    applied: int = 0                        # runs (and joined tails) that cut something
    runs: int = 0                           # runs (and tails) tried
    joined: int = 0                         # Q5: tails joined to a corner
    dropped_lead: bool = False              # leading interior points without an anchor
    dropped_tail: bool = False              # D: trailing interior points; Q5: a tail no corner worked for
    repeats: int = 0                        # Q5: repeated segments merged
    loops_built: int = 0                    # loops closed at a single point, built
    loops_dropped: collections.Counter = field(default_factory=collections.Counter)   # reason -> count
    closed_shapes: list[ClosedShape] = field(default_factory=list)
    shape_chains: int = 0                   # Q5: all-interior chains taken as closed shapes
    short_shapes: list[int] = field(default_factory=list)   # all-interior chains too short (point counts)
    skipped_shapes: int = 0                 # Q5: closed shapes whose face another run had cut
    lost_continuation: bool = False         # Q5: a seeded chain whose interior start got no vertex
    gaps: int = 0                           # Q5: skipped stretches (gap / along-an-edge breaks)


# ---------------------------------------------------------------------------
# Variant D — one chain, applied run by run
# ---------------------------------------------------------------------------

class KnifeResolver:
    """Variant D's commit-time resolution; one instance per commit (`resolve_collected`).

    The path is grouped into per-face runs (boundary - interior* - boundary). Runs are applied one
    after another, so a run meets the faces the runs before it left behind — never the click-time
    face it was drawn on. It is therefore *walked*: from its first vertex into the face that holds its
    next segment, cutting that face up to the first point where the run meets the face's boundary, and
    on from there. Where it meets a cut of this commit (an edge between two pieces of one click-time
    face) that edge is split — one intersection vertex, part of both cuts (Artist decision 2026-09-29,
    "crossing cuts like Blender"). Where it runs along the boundary nothing is cut. Where it would leave
    its click-time face it cannot be resolved and is dropped (HUD "N-1/N"). Where it crosses itself
    inside one face, or comes back into a vertex it left, the loop becomes its own face with one bridge
    (Artist decision 2026-09-30, option (a)). A dropped run leaves nothing behind, its end splits
    included (Task B, 2026-09-30)."""

    def __init__(self, mesh, before_state: dict):
        self.mesh = mesh
        self.before_state = before_state
        self.path_edges: list[EdgeId] = []
        self.face_root: dict[FaceId, FaceId] = {}
        self.loops_dropped: collections.Counter = collections.Counter()
        self.loops_built = 0
        self._loop_at_point: str | None = None
        self._edge_ends: dict[EdgeId, tuple[VertexId, VertexId]] = {}
        self._edge_splits: dict[EdgeId, list[tuple[float, VertexId]]] = {}
        self._helper_ids = itertools.count()

    def helper_point(self, **fields: Any) -> dict:
        """A point the resolver makes itself (never one of the session's ids)."""
        return {"pid": ("resolver", next(self._helper_ids)), **fields}

    # -- run ends ----------------------------------------------------------------------------

    def _run_end_vertex(self, p: dict, resolved: dict) -> VertexId | None:
        """The vertex of run end `p`, splitting its click-time edge now if no earlier run did.

        Adjacent runs share their joint point (`[A, B]` and `[B, C]` both hold B): it is split
        once and reused (`resolved`, keyed by point id). Several points on one click-time edge
        (notch/FC3, or across runs) are placed on the chain of pieces that edge has become — by
        their t on the original edge, so the order in which runs split it does not matter; a point
        at the same t as an existing split *is* that vertex (never a second vertex on top of it)."""
        m = self.mesh
        if p["kind"] == "vertex" and p["vertex_id"] is not None:
            return p["vertex_id"]  # a vertex point is its vertex, whatever `resolved` holds
        v = resolved.get(p["pid"])
        if v is not None and m.is_valid_vertex(v):
            return v
        if p["kind"] == "vertex":
            v = p["vertex_id"]
        else:
            eid, t = p["edge_id"], p["t"]
            if eid not in self._edge_ends:
                self._edge_ends[eid] = tuple(m.edge_vertices(eid))   # never split before this point
            ends = self._edge_ends[eid]
            splits = self._edge_splits.setdefault(eid, [])
            if t <= GEO_EPS or t >= 1.0 - GEO_EPS:
                # An edge point on the edge's end *is* that vertex — splitting there would put a
                # second vertex on top of it (a zero-area sliver, integrity finding R4).
                v = ends[0 if t <= 0.5 else 1]
            else:
                v = next((sv for st, sv in splits if abs(st - t) <= GEO_EPS), None)
                if v is None:
                    lo = max(((st, sv) for st, sv in splits if st < t), default=(0.0, ends[0]))
                    hi = min(((st, sv) for st, sv in splits if st > t), default=(1.0, ends[1]))
                    piece = find_edge(m, lo[1], hi[1])
                    u = (t - lo[0]) / (hi[0] - lo[0])
                    v, _e1, _e2 = m.split_edge(piece, u if m.edge_vertices(piece)[0] == lo[1] else 1.0 - u)
                    splits.append((t, v))
        if v is not None:
            resolved[p["pid"]] = v
        return v

    # -- walking one run through the current faces (integrity fix, 2026-09-29) ----------------

    def _root(self, face_id: FaceId) -> FaceId:
        """The click-time face a face descends from (itself for an untouched face)."""
        return self.face_root.get(face_id, face_id)

    def _adopt(self, parent: FaceId, children) -> None:
        root = self._root(parent)
        for f in children:
            self.face_root[f] = root

    def _crossable(self, eid: EdgeId) -> bool:
        """A cut of this commit: an edge between two pieces of one click-time face."""
        faces = self.mesh.edge_faces(eid)
        return len(faces) == 2 and self._root(faces[0]) == self._root(faces[1])

    def _step_from(self, p: VertexId, target: Position, root: FaceId | None):
        """Where the run goes from vertex `p` towards `target`: ("face", frame) — into that face
        (its corner at `p` holds the direction) — or ("along", q) — along the boundary edge p-q
        (q not beyond the target). Of several candidates, the face whose plane holds the target
        best wins (a fold edge borders two cube sides; only one holds the target). None: the run
        cannot continue (no face of `root` at `p` holds the direction)."""
        m = self.mesh
        pp = m.vertex_position(p)
        dist = dist3(pp, target)
        if dist <= GEO_EPS:
            return None
        best = None
        faces = {f for e in m.vertex_edges(p) for f in m.edge_faces(e)}
        for f in sorted(faces, key=int):
            if root is not None and self._root(f) != root:
                continue
            try:
                fr = FaceFrame(m, f)
            except MeshError:
                continue
            i = fr.boundary.index(p)
            k = len(fr.boundary)
            p2, t2 = fr.pts2[i], fr.p2(target)
            d2 = (t2[0] - p2[0], t2[1] - p2[1])
            if math.hypot(*d2) <= fr.eps:
                continue
            tilt = fr.height(target) / dist
            nxt, prv = fr.pts2[(i + 1) % k], fr.pts2[i - 1]
            e1 = (nxt[0] - p2[0], nxt[1] - p2[1])
            e2 = (prv[0] - p2[0], prv[1] - p2[1])

            def angle(w):
                return math.atan2(e1[0] * w[1] - e1[1] * w[0], e1[0] * w[0] + e1[1] * w[1]) % (2 * math.pi)

            a_d, a_e2 = angle(d2), angle(e2)
            if a_d < _ANGLE_EPS or a_d > 2 * math.pi - _ANGLE_EPS:
                step = ("along", fr.boundary[(i + 1) % k])
            elif abs(a_d - a_e2) < _ANGLE_EPS:
                step = ("along", fr.boundary[i - 1])
            elif a_d < a_e2:
                step = ("face", fr)
            else:
                continue
            if step[0] == "along" and dist3(pp, m.vertex_position(step[1])) > dist + fr.eps:
                continue  # the target lies on this edge, before its far end: not a vertex to walk to
            if best is None or tilt < best[0] - GEO_EPS:
                best = (tilt, step)
        return None if best is None else best[1]

    @staticmethod
    def _first_hit(fr: FaceFrame, a2, b2, skip_vertex: int | None):
        """First point after `a2` where the segment a2 -> b2 meets the face's boundary, as
        (s, "vertex", boundary index) or (s, "edge", boundary index of the edge's start, lam);
        s in (0, 1] along the segment, lam in (0, 1) along the edge. `skip_vertex`: the boundary
        index the segment starts on (it and its two edges are not hits). A vertex wins over an
        edge at the same point."""
        k = len(fr.pts2)
        dx, dy = b2[0] - a2[0], b2[1] - a2[1]
        length = math.hypot(dx, dy)
        if length <= fr.eps:
            return None
        s_eps = fr.eps / length
        hits = []
        for j, q in enumerate(fr.pts2):
            if j == skip_vertex:
                continue
            s = ((q[0] - a2[0]) * dx + (q[1] - a2[1]) * dy) / (length * length)
            off = abs(dx * (q[1] - a2[1]) - dy * (q[0] - a2[0])) / length
            if off <= fr.eps and s_eps < s <= 1.0 + s_eps:
                hits.append((s, 0, "vertex", j))
        for j in range(k):
            if skip_vertex is not None and skip_vertex in (j, (j + 1) % k):
                continue
            c, d = fr.pts2[j], fr.pts2[(j + 1) % k]
            ex, ey = d[0] - c[0], d[1] - c[1]
            den = dx * ey - dy * ex
            if abs(den) <= 1e-300:
                continue
            cx, cy = c[0] - a2[0], c[1] - a2[1]
            s = (cx * ey - cy * ex) / den
            lam = (cx * dy - cy * dx) / den
            e_len = math.hypot(ex, ey)
            lam_eps = fr.eps / e_len if e_len > 0 else 1.0
            if s_eps < s <= 1.0 + s_eps and lam_eps < lam < 1.0 - lam_eps:
                hits.append((s, 1, "edge", j, lam))
        if not hits:
            return None
        hits.sort(key=lambda h: (h[0], h[1]))
        first = hits[0]
        for h in hits:  # a vertex at (numerically) the same point as an edge hit wins
            if h[0] - first[0] > s_eps:
                break
            if h[2] == "vertex":
                return (h[0],) + h[2:]
        return (first[0],) + first[2:]

    @staticmethod
    def _self_crossing(trail: list, a2, b2, eps: float):
        """First crossing (along a2 -> b2) of the segment a2 -> b2 with a non-adjacent segment of
        `trail`: (trail index j of the crossed segment, parameter along trail[j] -> trail[j+1]),
        or None."""
        best = None
        for j in range(len(trail) - 2):
            c, d = trail[j], trail[j + 1]
            if not proper_cross2(c, d, a2, b2, eps):
                continue
            den = (b2[0] - a2[0]) * (d[1] - c[1]) - (b2[1] - a2[1]) * (d[0] - c[0])
            s = ((c[0] - a2[0]) * (d[1] - c[1]) - (c[1] - a2[1]) * (d[0] - c[0])) / den
            lam = ((c[0] - a2[0]) * (b2[1] - a2[1]) - (c[1] - a2[1]) * (b2[0] - a2[0])) / den
            if best is None or s < best[0]:
                best = (s, j, lam)
        return None if best is None else best[1:]

    def _walk_run(self, a: VertexId, positions: list[Position], b: VertexId, root: FaceId | None):
        """Cut the run a -> positions -> b through the current faces; returns the new cut edges
        (a -> b order) or None if the run cannot be resolved (the caller restores the mesh).

        A loop that closes at a single point (Artist decision 2026-09-30, option (a)) — the run
        crosses itself inside one face, or leaves a vertex and comes back into it — is kept apart
        while walking (the run goes on from the closing point) and built at the end of the run as
        its own face with one bridge (`close_loop_at_vertex`)."""
        m = self.mesh
        if a == b and not positions:
            return None
        targets = list(positions) + [m.vertex_position(b)]
        last = len(targets) - 1
        p, k, out = a, 0, []
        # (the loop's vertex — a VertexId, or the position of a point another loop or cut creates —,
        # its other points)
        loops: list[tuple[VertexId | Position, list[Position]]] = []
        for _guard in range(4 * (len(targets) + len(m.all_face_ids())) + 8):
            if p == b and k == last:
                return self._build_loops(loops, root, out)
            step = self._step_from(p, targets[k], root)
            if step is None:
                return None
            if step[0] == "along":
                p = step[1]
                if k < last and dist3(m.vertex_position(p), targets[k]) <= GEO_EPS:
                    return None  # an interior point on an existing vertex: not a clean cut
                continue
            fr = step[1]
            if root is None:
                root = self._root(fr.face_id)  # a straight run stays in the face it starts in, too
            i0 = fr.boundary.index(p)
            cur2, skip, pending = fr.pts2[i0], i0, []
            trail = [cur2]                          # the run inside this face so far, in 2D ...
            trail3 = [m.vertex_position(p)]         # ... and in 3D
            pinches: list[tuple[Position, list[Position]]] = []   # (crossing X, loop points)
            while True:
                t2 = fr.p2(targets[k])
                hit = self._first_hit(fr, cur2, t2, skip)
                end2 = t2 if hit is None else (cur2[0] + hit[0] * (t2[0] - cur2[0]),
                                                cur2[1] + hit[0] * (t2[1] - cur2[1]))
                cross = self._self_crossing(trail, cur2, end2, fr.eps)
                if cross is not None:
                    # The run crosses itself inside this face at X: X -> (the points since the
                    # crossed segment) -> X is a loop, the run goes on from X. X becomes a vertex
                    # of this face's cut; the loop is built on it once the run is through.
                    # An earlier X among those points is fine: its loop hangs off this loop and is
                    # built once this loop has made X a vertex (`_build_loops`).
                    j, lam = cross
                    c3, d3 = trail3[j], trail3[j + 1]
                    x3 = tuple(c3[q] + lam * (d3[q] - c3[q]) for q in range(3))
                    pinches.append((x3, pending[j:]))
                    pending = pending[:j] + [x3]
                    trail, trail3 = trail[:j + 1] + [fr.p2(x3)], trail3[:j + 1] + [x3]
                    cur2, skip = trail[-1], None
                    continue
                if hit is None:
                    if k == last:
                        return None  # b is not on this face's boundary where the run ends
                    pending.append(targets[k])
                    trail.append(t2)
                    trail3.append(targets[k])
                    cur2, skip, k = t2, None, k + 1
                    continue
                s = hit[0]
                if hit[1] == "vertex":
                    q = fr.boundary[hit[2]]
                else:
                    j, lam = hit[2], hit[3]
                    va, vb = fr.boundary[j], fr.boundary[(j + 1) % len(fr.boundary)]
                    eid = find_edge(m, va, vb)
                    if not self._crossable(eid):
                        return None  # the run would leave its click-time face
                    t = lam if m.edge_vertices(eid)[0] == va else 1.0 - lam
                    q, _e1, _e2 = m.split_edge(eid, t)
                if s >= 1.0 - GEO_EPS * 10 and k < last:
                    k += 1  # the interior point itself lies on that boundary point
                if q == p:
                    # Back into the vertex the run entered this face through: a loop at that
                    # vertex. Nothing else is cut in this face; the run goes on from p. Loops that
                    # crossed on the way (a bow-tie, Artist play test 2026-09-30) hang off points
                    # of this loop.
                    if len(pending) < 2:
                        self._loop_at_point = LOOP_NO_AREA
                        return None
                    loops.append((p, pending))
                    loops.extend(pinches)
                    break
                edges, children = cut_in_face(m, fr.face_id, p, q, pending)
                self._adopt(fr.face_id, children)
                out.extend(edges)
                loops.extend(pinches)
                p = q
                break
        return None

    def _build_loops(self, loops, root: FaceId | None, out: list[EdgeId]):
        """Build the loops a run closed at single points (see `_walk_run`), each in the face at its
        vertex that holds it; None (the run is dropped) if one cannot be built.

        A loop's vertex is a VertexId or the position of a crossing X, which becomes a vertex when
        the face's cut or another loop through X is built — so loops are built in that order: a loop
        whose X is still missing waits for the others (any order of clicks gives the same result)."""
        m = self.mesh

        def vertex_at(anchor):
            if not isinstance(anchor, tuple):
                return anchor
            return next((v for v in m.all_vertex_ids() if dist3(m.vertex_position(v), anchor) <= 1e-12), None)

        todo = list(loops)
        while todo:
            ready = next((i for i, (anchor, _pts) in enumerate(todo) if vertex_at(anchor) is not None), None)
            if ready is None:
                self._loop_at_point = LOOP_NESTED
                return None
            anchor, pts = todo.pop(ready)
            x = vertex_at(anchor)
            probe = pts[0]
            face = None
            for f in sorted({f for e in m.vertex_edges(x) for f in m.edge_faces(e)}, key=int):
                # No flatness test: every face here is a piece of the run's click-time face (`root`,
                # always set once the run entered a face), so the probe came from it; on a non-planar
                # face it lies off the piece's Newell plane by the face's own warp (S3b, 2026-10-01).
                if (root is None or self._root(f) == root) and segment_in_face(m, f, probe, probe) == "inside":
                    face = f
                    break
            outline = [m.vertex_position(x)] + list(pts) + [m.vertex_position(x)]
            if face is None or any(segment_in_face(m, face, u, v) != "inside" for u, v in zip(outline, outline[1:])):
                self._loop_at_point = self._loop_reason(outline, out)
                return None
            try:
                # Bridges go to vertices that existed before this commit (outside corners) first.
                outside = {v for v in m.all_vertex_ids() if int(v) in self.before_state["vertices"]}
                _vs, f_loop, ring, loop_edges = close_loop_at_vertex(m, face, x, pts, outside)
            except MeshError:
                self._loop_at_point = LOOP_NO_BRIDGE
                return None
            self._adopt(face, [f_loop] + ring)
            out.extend(loop_edges)
            self.loops_built += 1
        return out

    def _loop_reason(self, outline: list[Position], out: list[EdgeId]) -> str:
        """Why a loop does not lie inside one face: an edge this run cut (or another of its loops)
        crosses the outline, in the loop's own plane — or nothing of the run does (S3b)."""
        m = self.mesh
        try:
            fr = FaceFrame.of_points(outline[:-1])
        except MeshError:
            return LOOP_CROSSED
        ring = [fr.p2(p) for p in outline]
        for e in out:
            if m.is_valid_edge(e):
                a, b = (fr.p2(m.vertex_position(v)) for v in m.edge_vertices(e))
                if any(proper_cross2(a, b, c, d, fr.eps) for c, d in zip(ring, ring[1:])):
                    return LOOP_CROSSED
        return LOOP_OFF_FACE

    def _apply_run(self, run: list[dict], resolved: dict) -> bool:
        first, last = run[0], run[-1]
        interior = run[1:-1]
        # Every interior point of a run lies in one click-time face (the planner puts a crossing
        # at every face change; D accepts no other face) — the run may not leave it.
        root = interior[0]["face_id"] if interior else None
        state, roots, built = self.mesh.export_state(), dict(self.face_root), self.loops_built
        saved_resolved = dict(resolved)
        saved_splits = {e: list(v) for e, v in self._edge_splits.items()}
        self._loop_at_point = None
        try:
            # The run's own end splits happen here, inside its rollback scope (Task B).
            a, b = self._run_end_vertex(first, resolved), self._run_end_vertex(last, resolved)
            edges = None if a is None or b is None else \
                self._walk_run(a, [p["position"] for p in interior], b, root)
        except (MeshError, LookupError, ValueError, ZeroDivisionError):
            # Safety net: a run that trips over Core degrades to a dropped run (HUD "N/M") —
            # never an exception out of commit, which would skip the History push for
            # whatever earlier runs already mutated.
            edges = None
        if not edges:
            # None: dropped. []: the run only walks along existing edges (D, no planner) — it cuts
            # nothing, so it is not "applied" either, and its end splits go too.
            # A dropped run leaves nothing behind, its end splits included (Task B, 2026-09-30).
            self.mesh.load_state(state)
            self.face_root = roots
            self.loops_built = built
            resolved.clear()
            resolved.update(saved_resolved)
            self._edge_splits = saved_splits
            if self._loop_at_point:
                self.loops_dropped[self._loop_at_point] += 1
            return False
        self.path_edges.extend(edges)
        return True

    def _resolve_closed_loop(self, path: list[dict]) -> ClosedShape:
        fid = path[0]["face_id"]
        positions = [p["position"] for p in path]
        boundary = self.mesh.face_vertices(fid)
        state = self.mesh.export_state()
        try:
            i1, bv1, i2, bv2 = select_bridge(self.mesh, boundary, positions)
            _loop_vs, f_inner, f_a, f_b, loop_edges = close_loop_with_bridges(
                self.mesh, fid, positions, i1, bv1, i2, bv2,
            )
        except MeshError as exc:
            self.mesh.load_state(state)  # the first split may already have happened
            return ClosedShape(len(positions), error=str(exc))
        problem = next((pr for pr in (face_problem(self.mesh, f) for f in (f_inner, f_a, f_b)) if pr), None)
        if problem is not None:
            # An outline that crosses itself, or a bridge through the loop (Task A observation):
            # only this shape is taken back, the rest of the commit stands.
            self.mesh.load_state(state)
            return ClosedShape(len(positions), problem=problem)
        self._adopt(fid, (f_inner, f_a, f_b))
        self.path_edges.extend(loop_edges)
        return ClosedShape(len(positions))

    def _result(self, res: KnifeResolution) -> KnifeResolution:
        res.path_edges = list(self.path_edges)
        res.loops_built = self.loops_built
        res.loops_dropped = collections.Counter(self.loops_dropped)
        return res

    def resolve(self, path: list[dict]) -> KnifeResolution:
        res = KnifeResolution()
        if not path:
            res.empty = True
            return res

        if all(p["kind"] == "face" for p in path):
            fid = path[0]["face_id"]
            if len(path) < 3 or any(p["face_id"] != fid for p in path):
                res.short_shapes.append(len(path))
                return self._result(res)
            res.closed_shapes.append(self._resolve_closed_loop(path))
            return self._result(res)

        # Leading interior points before the first boundary point have no boundary vertex to
        # anchor a cut on (the discovery's FC5 "dangling start" — only the pure-interior loop
        # above closes on itself) — dropped, same as a dangling tail.
        lead_drop = 0
        while lead_drop < len(path) and path[lead_drop]["kind"] == "face":
            lead_drop += 1
        res.dropped_lead = lead_drop > 0
        path = path[lead_drop:]

        runs: list[list[dict]] = []
        current: list[dict] = []
        for p in path:
            current.append(p)
            if p["kind"] in ("vertex", "edge"):
                if len(current) >= 2:
                    runs.append(current)
                current = [p]
        res.dropped_tail = len(current) > 1

        resolved: dict = {}
        res.applied = sum(1 for run in runs if self._apply_run(run, resolved))
        res.runs = len(runs)
        return self._result(res)


# ---------------------------------------------------------------------------
# Variant Q5 — chains, gaps, closes, seeds, earlier points, tail join
# ---------------------------------------------------------------------------

class CrossFaceResolver(KnifeResolver):
    """Variant Q5's commit-time resolution (`resolve_cross_face`): D's run machinery per break-free
    stretch of each chain, plus cyclic closes, seeded chains (a closed chain's start continues the
    next one), merged repeats of earlier points and the tail join (decision.md 2026-09-29/30)."""

    def __init__(self, mesh, before_state: dict):
        super().__init__(mesh, before_state)
        self.interior_vertices: dict = {}   # point id of an interior point -> the vertex its cut made

    # -- a cut whose last click lies inside a face (Artist decision 2026-09-30) ----------

    def _tail_corners(self, tail: list[dict]) -> list[VertexId]:
        """Corners of the face the tail's last click lies in, nearest to that click first (ties by
        position): commit joins the tail to the first one it can cut to. The tail's own boundary
        start is no candidate. Read on the session-start mesh (what the Artist clicked on)."""
        m = self.mesh
        last = tail[-1]
        fid = last["face_id"]
        if not m.is_valid_face(fid):
            return []
        start = tail[0]["vertex_id"] if tail[0]["kind"] == "vertex" else None
        pos = last["position"]
        cands = [v for v in m.face_vertices(fid) if v != start]
        return sorted(cands, key=lambda v: (round(math.dist(pos, m.vertex_position(v)), 9),
                                            tuple(m.vertex_position(v))))

    # -- interior start points shared by a seeded chain ---------------------------------

    def _record_new_vertices(self, points: list[dict], before: set) -> None:
        """Remember which mesh vertex a run / loop created for each interior point, so a
        chain seeded with that point can be anchored on it (positions are unique per
        point: an interior click never lands within 14 px of another one — snap)."""
        new = [v for v in self.mesh.all_vertex_ids() if v not in before]
        for pt in points:
            for v in new:
                if math.dist(self.mesh.vertex_position(v), pt["position"]) < 1e-9:
                    self.interior_vertices[pt["pid"]] = v
                    break

    @staticmethod
    def _runs_of(chunk: list[dict]) -> tuple[list[list[dict]], bool, list[dict]]:
        """D's run splitting for one break-free stretch: leading interior points
        have no anchor and are dropped (FC5). The tail — the last boundary point and the
        interior points after it — is returned (empty if the stretch ends on a boundary):
        commit joins it to the nearest corner (Artist decision 2026-09-30)."""
        lead = 0
        while lead < len(chunk) and chunk[lead]["kind"] == "face":
            lead += 1
        runs, cur = [], []
        for p in chunk[lead:]:
            cur.append(p)
            if p["kind"] in ("vertex", "edge"):
                if len(cur) >= 2:
                    runs.append(cur)
                cur = [p]
        return runs, lead > 0 and len(chunk) > 1, cur if len(cur) > 1 else []

    @staticmethod
    def _merge_repeated_points(groups: list[list[list[dict]]]) -> tuple[list[list[list[dict]]], int]:
        """One entry per boundary point, one run per segment. Connecting to an earlier point puts
        that point into a run again — usually as the very same point, but a segment retraced under
        another camera brings fresh crossings on the same edge/t, which resolving separately
        would split twice (zero-length edge). Boundary run ends on the same edge point / vertex are
        replaced by their first record (`resolved` is keyed by point id), and a straight segment
        between the same two points that an earlier run already cuts (or from a point to itself)
        is dropped. Works over all `groups` of runs together (a segment can repeat across chains) and
        returns them in the same shape with the number of dropped repeats. Interior points and the vertex
        placeholders of an interior seed (vertex_id still None) are never touched."""
        canon: dict[tuple, dict] = {}

        def key(p: dict):
            if p["kind"] == "edge":
                return ("e", p["edge_id"], round(p["t"], 9))
            if p["kind"] == "vertex" and p["vertex_id"] is not None:
                return ("v", p["vertex_id"])
            return None

        def unify(p: dict) -> dict:
            k = key(p)
            return p if k is None else canon.setdefault(k, p)

        result, cut, dropped = [], set(), 0
        for runs in groups:
            out = []
            for run in runs:
                run = [unify(run[0])] + run[1:-1] + [unify(run[-1])]
                if len(run) == 2:
                    a, b = run
                    pair = frozenset((a["pid"], b["pid"]))
                    if _same(a, b) or pair in cut:
                        dropped += 1
                        continue
                    cut.add(pair)
                out.append(run)
            result.append(out)
        return result, dropped

    def _apply_run(self, run: list[dict], resolved: dict) -> bool:
        interior = run[1:-1]
        before = set(self.mesh.all_vertex_ids()) if interior else set()
        ok = super()._apply_run(run, resolved)
        if ok and interior:
            self._record_new_vertices(interior, before)
        return ok

    def _resolve_closed_loop(self, path: list[dict]) -> ClosedShape:
        before = set(self.mesh.all_vertex_ids())
        shape = super()._resolve_closed_loop(path)
        self._record_new_vertices(path, before)
        return shape

    def resolve(self, path: list[dict]) -> KnifeResolution:
        res = KnifeResolution()
        if not path:
            res.empty = True
            return res

        runs: list[list[dict]] = []
        seeded_runs: list[list[dict]] = []     # chains anchored on an interior start point: applied last
        anchors: dict = {}                     # point id of an interior seed -> (seed, vertex placeholder)
        loops: list[list[dict]] = []
        tails: list[tuple[list[dict], list[VertexId], bool]] = []   # (tail, corners, seeded)
        for entries, closed, cyclic, seeded in split_chains(path):
            target_runs = runs
            if seeded:
                first = next(p for p in entries if not is_break(p))
                if first["kind"] == "face":
                    # An interior start is no vertex before commit: this chain waits for the
                    # vertex that the closed chain's cut creates at that point. The placeholder
                    # is bound (vertex_id resolved) right before its runs are applied.
                    ph = anchors.setdefault(first["pid"], (first, self.helper_point(kind="vertex", vertex_id=None)))[1]
                    entries = [ph if not is_break(p) and _same(p, first) else p for p in entries]
                    target_runs = seeded_runs
            chunks, cur = [], []
            for p in entries:
                if is_break(p):
                    if cur:
                        chunks.append(cur)
                    cur = []
                else:
                    cur.append(p)
            if cur:
                chunks.append(cur)
            if not chunks:
                continue

            if len(chunks) == 1 and all(p["kind"] == "face" for p in chunks[0]):
                pts = chunks[0]
                # Closed by click, or by D's implicit close at commit (D parity).
                if len(pts) < 3 or any(p["face_id"] != pts[0]["face_id"] for p in pts):
                    res.short_shapes.append(len(pts))
                else:
                    loops.append(pts)
                continue

            if closed and cyclic:
                pts = chunks[0]
                start = next(i for i, p in enumerate(pts) if p["kind"] != "face")
                # Start and end on the same boundary point so the loop resolves with
                # no bridges (probe P8 (c)); the same point closes it.
                chunks = [pts[start:] + pts[:start] + [pts[start]]]
            for chunk in chunks:
                r, lead, tail = self._runs_of(chunk)
                target_runs.extend(r)
                res.dropped_lead |= lead
                if tail:
                    # Corners are read now, before any run changes the faces.
                    tails.append((tail, self._tail_corners(tail), target_runs is seeded_runs))

        (runs, seeded_runs), res.repeats = self._merge_repeated_points([runs, seeded_runs])
        resolved: dict = {}
        applied = sum(1 for run in runs if self._apply_run(run, resolved))
        joined = 0

        def join_tails(seeded: bool) -> None:
            # The tail's last click is joined to the nearest corner it can be cut to (Artist
            # decision 2026-09-30); a corner that does not work (the cut would leave the face or
            # cross itself) is taken back like any dropped run and the next one is tried.
            nonlocal joined
            for tail, corners, is_seeded in tails:
                if is_seeded != seeded:
                    continue
                ends = [self.helper_point(kind="vertex", vertex_id=v) for v in corners]
                before = self.loops_dropped.copy()
                ok = any(self._apply_run(tail + [end], resolved)
                         for end in ends if self.mesh.is_valid_vertex(end["vertex_id"]))
                # A loop reason is a property of the tail, not of each corner tried: counted once, and
                # only if no corner worked.
                tried = self.loops_dropped - before
                self.loops_dropped = before
                if ok:
                    joined += 1
                else:
                    res.dropped_tail = True
                    if tried:
                        self.loops_dropped[tried.most_common(1)[0][0]] += 1

        join_tails(False)

        res.shape_chains = len(loops)
        for pts in loops:
            fid: FaceId = pts[0]["face_id"]
            if not self.mesh.is_valid_face(fid):
                res.skipped_shapes += 1
                continue
            res.closed_shapes.append(self._resolve_closed_loop(pts))

        def bind_anchors() -> None:
            for seed, ph in anchors.values():
                vid = self.interior_vertices.get(seed["pid"])
                if vid is not None and self.mesh.is_valid_vertex(vid):
                    resolved[ph["pid"]] = vid

        for run in seeded_runs:
            bind_anchors()
            if self._apply_run(run, resolved):
                applied += 1
        bind_anchors()
        join_tails(True)
        res.lost_continuation = any(self.interior_vertices.get(seed["pid"]) is None for seed, _ph in anchors.values())

        res.runs = len(runs) + len(seeded_runs) + len(tails)
        res.applied = applied + joined
        res.joined = joined
        res.gaps = sum(1 for p in path if is_break(p) and p.get("reason") in ("gap", "edge"))
        return self._result(res)


def resolve_collected(mesh, path: list[dict], before_state: dict) -> KnifeResolution:
    """Variant D's resolution of `path` on `mesh` (see `KnifeResolver`)."""
    return KnifeResolver(mesh, before_state).resolve(path)


def resolve_cross_face(mesh, path: list[dict], before_state: dict) -> KnifeResolution:
    """Variant Q5's resolution of `path` on `mesh` (see `CrossFaceResolver`)."""
    return CrossFaceResolver(mesh, before_state).resolve(path)
