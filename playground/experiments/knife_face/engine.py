"""Knife Face Cut Lab — engine (Discovery, no Core change, no Production change).

LAB STAND-IN: every mesh mutation below goes through the *public* Core API only
(add_vertex, add_face, remove_face, split_edge, connect_vertices) — the same
"B2b" pattern as `experiments/topology/knife_face_cut_probe.py::split_face_path`,
which is the evidence base for this file
(`docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md` §2/§3). It is not a Core
primitive proposal by itself — that would be a separate AD (§3 "B2c sketch").

Two session engines, both `mirai.interaction.tool.Tool` subclasses (same
session/undo/commit/cancel state machine `mirai.topology.knife.KnifeTool`
already uses — reused as-is here, not modified):

  KnifeFaceImmediate (Variant B) — interior clicks are pending (non-mutating)
    steps inside the *current* face; the whole path (start -> interior* ->
    boundary) is applied in one mutation as soon as it reaches a vertex/edge
    of that face. No interior start. Covers FC1-FC4.

  KnifeFaceCollected (Variant D) — every click (vertex/edge/face) only
    extends a virtual path; nothing mutates the mesh until commit. At commit,
    the path is grouped into per-face runs and each run is resolved
    (boundary-interior*-boundary -> split; interior-only closed path with
    >=3 points -> closed shape with 2 bridges; anything left over is
    dropped). Interior start allowed. Each run is walked through the faces
    the runs before it left behind; where it crosses one of their cuts it
    gets an intersection vertex (integrity fix 2026-09-29, decision.md
    "Q5 integrity findings").

Per AD-017 §1.10/decision #1 ("no universal Cut Engine"): the two variants
are written independently, sharing only small mode-agnostic helpers (picking,
`split_face_path`, `connect_in_shared_face`) - not a shared "path resolver".
Both share the commit safety net: faces the session touched are checked
before History, a broken result is rolled back as a whole.
"""

from __future__ import annotations

import collections
import math
from typing import Any

from core import EdgeId, FaceId, VertexId
from core.mesh import MeshError
from core.selection import SelectionMode
from core.operations.topology import MeshStateCommand

from mirai.interaction.tool import Tool
from mirai.topology.knife_pick import knife_pick as _base_knife_pick
from mirai.topology.topology_points import connect_in_shared_face
from viewport.derived import triangulate_mesh_face

Position = tuple[float, float, float]

# H3 (discovery §0): production edge pick radius is 9px — an interior point
# needs at least that much clearance from every edge of its face, or there is
# no room to distinguish "on the edge" from "inside the face".
EDGE_MARGIN_PX = 9.0


# ---------------------------------------------------------------------------
# Picking — lab-local face-interior hit position (H1: pick_face returns only
# the FaceId; src/mirai/viewport/picking.py is not touched, its algorithm is
# duplicated here on purpose so the fan-triangulation/non-planar behaviour
# (H2) matches exactly what Production already does for face hover).
# ---------------------------------------------------------------------------

def _ray_triangle_t(origin, direction, a, b, c):
    """Same Möller-Trumbore test as `mirai.viewport.picking._ray_triangle_intersection`."""
    eps = 1e-9
    edge1 = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    edge2 = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    h = (
        direction[1] * edge2[2] - direction[2] * edge2[1],
        direction[2] * edge2[0] - direction[0] * edge2[2],
        direction[0] * edge2[1] - direction[1] * edge2[0],
    )
    det = edge1[0] * h[0] + edge1[1] * h[1] + edge1[2] * h[2]
    if abs(det) < eps:
        return None
    inv_det = 1.0 / det
    s = (origin[0] - a[0], origin[1] - a[1], origin[2] - a[2])
    u = inv_det * (s[0] * h[0] + s[1] * h[1] + s[2] * h[2])
    if u < -eps or u > 1.0 + eps:
        return None
    q = (
        s[1] * edge1[2] - s[2] * edge1[1],
        s[2] * edge1[0] - s[0] * edge1[2],
        s[0] * edge1[1] - s[1] * edge1[0],
    )
    v = inv_det * (direction[0] * q[0] + direction[1] * q[1] + direction[2] * q[2])
    if v < -eps or u + v > 1.0 + eps:
        return None
    t = inv_det * (edge2[0] * q[0] + edge2[1] * q[1] + edge2[2] * q[2])
    return t if t > eps else None


def face_interior_hit(camera, mesh, face_id: FaceId, sx, sy, width, height) -> Position | None:
    """World-space ray-hit position on `face_id`'s fan triangulation.

    Same triangulation as `pick_face` (`viewport.derived.triangulate_mesh_face`)
    — so a hit on a non-planar quad (H2, the `head` asset) or a concave face
    lands on the same triangle `pick_face` itself used to select this face. Returns None only in the numerically-degenerate
    case where the ray, recomputed here, no longer intersects any fan
    triangle of this specific face (should not happen since `pick_face`
    already chose it, kept as a defensive fallback -> caller treats it as
    "outside").
    """
    origin, direction = camera.screen_to_ray(sx, sy, width, height)
    best_t = None
    for tri in triangulate_mesh_face(mesh, face_id):
        p0, p1, p2 = (mesh.vertex_position(v) for v in tri)
        t = _ray_triangle_t(origin, direction, p0, p1, p2)
        if t is not None and (best_t is None or t < best_t):
            best_t = t
    if best_t is None:
        return None
    return (
        origin[0] + best_t * direction[0],
        origin[1] + best_t * direction[1],
        origin[2] + best_t * direction[2],
    )


def _point_segment_distance_px(px, py, ax, ay, bx, by) -> float:
    abx, aby = bx - ax, by - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    qx, qy = ax + t * abx, ay + t * aby
    return math.hypot(px - qx, py - qy)


def min_edge_distance_px(camera, mesh, face_id: FaceId, sx, sy, width, height) -> float | None:
    """Screen-space distance from the cursor to the nearest boundary edge of
    `face_id` — H3's "9px from every edge" gate. Since the face-interior hit
    position corresponds to the cursor itself, this is simply the cursor's
    own screen distance to each boundary edge (no reprojection needed)."""
    boundary = mesh.face_vertices(face_id)
    n = len(boundary)
    best = None
    for i in range(n):
        a = camera.project_to_screen(mesh.vertex_position(boundary[i]), width, height)
        b = camera.project_to_screen(mesh.vertex_position(boundary[(i + 1) % n]), width, height)
        if a is None or b is None:
            continue
        d = _point_segment_distance_px(sx, sy, a[0], a[1], b[0], b[1])
        if best is None or d < best:
            best = d
    return best


def knife_face_pick(camera, mesh, sx, sy, width, height, *, cache=None, occlusion: bool = False) -> dict:
    """Like `mirai.topology.knife_pick.knife_pick`, plus a hit position and
    edge-clearance for the "face" kind (reused unmodified for vertex/edge/
    outside — H1 only needs a position on top of what it already returns).

    `cache`/`occlusion` pass straight through to the base pick (WP-06 B8). The
    face-only lookups below work on the face it already resolved, so they
    need no occlusion pass of their own."""
    target = _base_knife_pick(camera, mesh, sx, sy, width, height, cache=cache, occlusion=occlusion)
    if target.get("kind") != "face":
        return target
    fid = target["face_id"]
    pos = face_interior_hit(camera, mesh, fid, sx, sy, width, height)
    if pos is None:
        return {"kind": "outside"}
    dist_px = min_edge_distance_px(camera, mesh, fid, sx, sy, width, height)
    return {"kind": "face", "face_id": fid, "position": pos, "distance_px": dist_px}


# ---------------------------------------------------------------------------
# Shared mode-agnostic helpers (AD-017 §11 shape: small, reusable, no session
# state) - not a "generic CutPath", just the same non-adjacency test KnifeTool
# already makes and a chain-edge lookup after a face split.
# ---------------------------------------------------------------------------

def _shares_nonadjacent_face(mesh, a: VertexId, b: VertexId) -> bool:
    """True if some face contains both `a` and `b` and they are not adjacent
    in it. Local copy of `mirai.topology.knife._connectable_in_shared_face`
    (private there) — same rule, used by both variants' "no pending points"
    case (plain vertex-vertex connect, same as Production Knife)."""
    if a == b:
        return False
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        if a not in boundary or b not in boundary:
            continue
        n = len(boundary)
        dist = (boundary.index(b) - boundary.index(a)) % n
        if dist not in (1, n - 1):
            return True
    return False


def _find_edge(mesh, a: VertexId, b: VertexId) -> EdgeId:
    for eid in mesh.vertex_edges(a):
        if set(mesh.edge_vertices(eid)) == {a, b}:
            return eid
    raise MeshError(f"internal: no edge between {a!r} and {b!r} after split")


def _cyclic_walk(seq: list, i: int, j: int, step: int = 1) -> list:
    """Walk `seq` cyclically from index `i` to index `j` (inclusive),
    stepping by `step` (+1 forward / -1 backward), wrapping with `% n`."""
    n = len(seq)
    out = []
    k = i
    while True:
        out.append(seq[k])
        if k == j:
            break
        k = (k + step) % n
    return out


def split_face_path(mesh, face_id: FaceId, a: VertexId, b: VertexId, positions: list[Position]):
    """LAB STAND-IN for a possible Core `split_face` primitive (discovery §3
    "B2c sketch") - split `face_id` along a path a -> positions... -> b, both
    `a` and `b` existing boundary vertices of `face_id` (adjacent allowed,
    unlike `Mesh.connect_vertices` - that is exactly what makes FC3/FC4
    possible here).

    Adapted from `experiments/topology/knife_face_cut_probe.py::split_face_path`
    (same B2b construction: remove_face + add_vertex + add_face): the boundary
    is partitioned into its two arcs a->b and b->a via a cyclic walk (correct
    for every boundary order, including a/b adjacent through the wrap - the
    probe's own index-slice-with-swap turns out to already be a correct,
    equivalent normalization; the cyclic walk here is written out explicitly
    because it is what this file's own reasoning was checked against).

    H7: `Mesh.add_face` does not reject repeated boundary vertices - checked
    here explicitly (both resulting loops, plus the path itself).

    Returns (new_vertex_ids, face_1, face_2, path_edge_ids) - `face_1` is the
    side running a -> b in boundary order (matches the B2c sketch's stated
    convention); `path_edge_ids` are the k+1 new edges a-p0-p1-...-pk-b, in
    that order.
    """
    if a == b:
        raise MeshError("split_face_path: a and b must be distinct vertices")
    boundary = mesh.face_vertices(face_id)
    if a not in boundary or b not in boundary:
        raise MeshError("split_face_path: a, b must be boundary vertices of face_id")

    new_vs = [mesh.add_vertex(p) for p in positions]
    chain = [a] + new_vs + [b]
    if len(set(chain)) != len(chain):
        raise MeshError("split_face_path: cut path revisits a vertex")

    i, j = boundary.index(a), boundary.index(b)
    seg_ab = _cyclic_walk(boundary, i, j)      # a .. b, forward
    seg_ba = _cyclic_walk(boundary, j, i)      # b .. a, forward
    loop1 = seg_ab + list(reversed(new_vs))    # face 1: a -> b along boundary, back through the path
    loop2 = seg_ba + list(new_vs)              # face 2: b -> a along boundary, forward through the path

    for name, loop in (("1", loop1), ("2", loop2)):
        if len(loop) < 3 or len(set(loop)) != len(loop):
            raise MeshError(f"split_face_path: face {name} degenerate ({loop!r})")

    mesh.remove_face(face_id)
    f1 = mesh.add_face(loop1)
    f2 = mesh.add_face(loop2)
    path_edges = [_find_edge(mesh, u, v) for u, v in zip(chain, chain[1:])]
    return new_vs, f1, f2, path_edges


# Why a loop closed at a single point could not be built (HUD note; decision.md, 2026-09-30).
LOOP_NO_AREA = "out to one point and straight back — no area"
LOOP_NESTED = "it winds round another loop's point"
LOOP_CROSSED = "the run cuts through its own loop again"
LOOP_NO_BRIDGE = "no bridge fits"

# Distances closer than this are ties (a symmetric shape: the same distance up to float noise).
_TIE_DIGITS = 9


def _dist3(p, q) -> float:
    return math.sqrt(sum((p[k] - q[k]) ** 2 for k in range(3)))


def _loop_adjacent(a: int, b: int, k: int) -> bool:
    return (a - b) % k in (1, k - 1)


def _newell(points: list[Position]) -> Position:
    """Newell normal (unnormalised; its length is twice the projected area) of a polygon."""
    nx = ny = nz = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    return (nx, ny, nz)


def loop_matches_winding(loop_positions: list[Position], boundary_positions: list[Position]) -> bool:
    """True if the loop, in the given order, winds like the parent face's boundary (its Newell
    normal points to the same side). A degenerate loop (no area, e.g. a bow-tie) has no winding
    of its own and counts as matching — it is left as clicked."""
    nl, nb = _newell(loop_positions), _newell(boundary_positions)
    return sum(nl[k] * nb[k] for k in range(3)) >= 0.0


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

    Simplification flagged in decision.md: "nearest" is measured in *world*
    space, not screen space as the spec's default wording suggests - this
    engine has no camera (kept headless-testable, see §6); for a face viewed
    close to head-on the two rankings coincide in practice.

    Returns (loop_index_1, boundary_vertex_1, loop_index_2, boundary_vertex_2).
    """
    k = len(loop_positions)
    candidates = []
    for li, pos in enumerate(loop_positions):
        best = None
        for bv in boundary:
            bpos = mesh.vertex_position(bv)
            key = (round(_dist3(pos, bpos), _TIE_DIGITS), tuple(bpos))
            if best is None or key < best[0]:
                best = (key, bv)
        candidates.append((best[0][0], tuple(pos), best[0][1], li, best[1]))
    candidates.sort(key=lambda c: c[:4])

    i1, bv1 = candidates[0][3], candidates[0][4]
    for _dist, _pos, _bpos, li, bv in candidates[1:]:
        if bv == bv1:
            continue
        if k > 3 and _loop_adjacent(li, i1, k):
            continue
        return i1, bv1, li, bv
    raise MeshError("select_bridge: no valid second bridge point (lab default rule)")


def close_loop_with_bridges(
    mesh, face_id: FaceId, loop_positions: list[Position],
    i1: int, bv1: VertexId, i2: int, bv2: VertexId,
):
    """LAB STAND-IN: close an interior loop (>=3 points) inside `face_id` by
    bridging it to the boundary with 2 edges (spec §2 "closed shape stand-in").

    Splits `face_id` into exactly 3 faces (spec: "3 pieces in a quad"):
      - the loop itself (a pure k-gon, all loop edges);
      - the wing between boundary-arc(bv1->bv2) and the loop arc between the bridge points on
        that side;
      - the wing between boundary-arc(bv2->bv1) and the loop arc on the other side;
    the two bridge edges (bv1-loop[i1], bv2-loop[i2]) each border both wings.

    Winding (Artist decision 2026-09-29, Task A; `FACE_HOLES_DISCOVERY.md` §6): the loop is
    first oriented like the parent face's boundary, whichever way it was clicked, so the inner
    face has the parent's orientation and the wings traverse every loop edge *against* the inner
    face (consistent interior edges) — they cover the ring, never the loop. `i1`/`i2` and the
    returned `loop_vs` / `loop_edges` keep the caller's (click) order; only the faces are built
    in the canonical order.

    This is a genuine 3-way split of one face - not two applications of
    `split_face_path` - because neither wing can be built without the other
    already existing (each bridge edge borders both of them, and the loop's
    own edges border the loop face and exactly one wing each). Written out
    directly (H7 checked per resulting loop) rather than composed.
    """
    k = len(loop_positions)
    if k < 3:
        raise MeshError("close_loop_with_bridges: needs >= 3 interior points")
    if i1 == i2 or bv1 == bv2:
        raise MeshError("close_loop_with_bridges: bridges must be distinct")
    boundary = mesh.face_vertices(face_id)
    if bv1 not in boundary or bv2 not in boundary:
        raise MeshError("close_loop_with_bridges: bridge vertices must be on face_id's boundary")

    reverse = not loop_matches_winding(loop_positions, [mesh.vertex_position(v) for v in boundary])
    loop_vs = [mesh.add_vertex(p) for p in loop_positions]
    order = list(range(k - 1, -1, -1)) if reverse else list(range(k))
    canon = [loop_vs[j] for j in order]                    # loop, wound like the parent
    c1, c2 = order.index(i1), order.index(i2)              # bridge points in canonical indices

    bi, bj = boundary.index(bv1), boundary.index(bv2)
    seg_ab = _cyclic_walk(boundary, bi, bj)                      # bv1 .. bv2, forward
    seg_ba = _cyclic_walk(boundary, bj, bi)                      # bv2 .. bv1, forward
    # Each wing runs its boundary arc forward, crosses to the loop, and comes back along the
    # loop arc *backward* (decreasing canonical index): the loop face walks the same edges
    # forward, so every loop edge is used once in each direction. The two arcs
    # (c2 down to c1, c1 down to c2) are complements of each other.
    arc_a = _cyclic_walk(canon, c2, c1, step=-1)                 # canon[c2] .. canon[c1], backward
    arc_b = _cyclic_walk(canon, c1, c2, step=-1)                 # canon[c1] .. canon[c2], backward

    face_inner = list(canon)
    face_a = seg_ab + arc_a
    face_b = seg_ba + arc_b

    for name, loop in (("inner", face_inner), ("A", face_a), ("B", face_b)):
        if len(loop) < 3 or len(set(loop)) != len(loop):
            raise MeshError(f"close_loop_with_bridges: face {name} degenerate ({loop!r})")

    mesh.remove_face(face_id)
    f_inner = mesh.add_face(face_inner)
    f_a = mesh.add_face(face_a)
    f_b = mesh.add_face(face_b)
    loop_edges = [_find_edge(mesh, loop_vs[idx], loop_vs[(idx + 1) % k]) for idx in range(k)]
    return loop_vs, f_inner, f_a, f_b, loop_edges


def close_loop_at_vertex(mesh, face_id: FaceId, x: VertexId, loop_positions: list[Position]):
    """LAB STAND-IN: a loop x -> loop_positions -> x inside `face_id`, touching its boundary at the
    one vertex `x` only (a cut that crosses itself, or leaves a point and comes back to it —
    Artist decision 2026-09-30, option (a)). Built as its own face plus **one** bridge, the same
    H0 idea as the closed-shape stand-in: one boundary list per face cannot visit `x` twice, and
    one bridge from a loop point to another boundary vertex splits the pinched ring into two simple
    faces (a loop that touches nothing needs two, `close_loop_with_bridges`).

    Order- and direction-independent like the closed shape (Task A, 2026-09-29): the loop is wound
    like the parent; the bridge is the shortest one (loop point, boundary vertex other than `x`)
    that leaves every face simple and facing like the parent — ties by position, never by index.

    Returns (loop_vertices, loop_face, ring_faces, loop_edges) — `loop_edges` in `loop_positions`
    order, x -> first ... last -> x. Raises MeshError (mesh possibly changed: the caller restores
    it) when the loop is degenerate or no bridge fits.
    """
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
    reverse = not loop_matches_winding([mesh.vertex_position(x)] + list(loop_positions),
                                       [mesh.vertex_position(v) for v in boundary])
    loop_vs = [mesh.add_vertex(p) for p in loop_positions]
    canon = loop_vs[::-1] if reverse else list(loop_vs)          # x, c1 .. cm wound like the parent
    # The ring walks the outer boundary from x round to x, then the loop against its own face
    # (cm .. c1). A bridge c(j) - f(i) splits that walk into two faces holding x once each.
    ring = outer + [x] + canon[::-1]
    mesh.remove_face(face_id)
    f_loop = mesh.add_face([x] + canon)
    candidates = []
    for j, c in enumerate(canon):
        pc = mesh.vertex_position(c)
        for bi in range(1, n):
            pb = mesh.vertex_position(outer[bi])
            candidates.append((round(_dist3(pc, pb), _TIE_DIGITS), tuple(pc), tuple(pb), j, bi))
    candidates.sort(key=lambda c: c[:3])
    base = mesh.export_state()
    for *_key, j, bi in candidates:
        ic = n + m - j                                           # canon[j] in `ring`
        face_p = ring[bi:ic + 1]
        face_q = ring[ic:] + ring[:bi + 1]
        if min(len(face_p), len(face_q)) < 3 or any(len(set(f)) != len(f) for f in (face_p, face_q)):
            continue
        try:
            fp, fq = mesh.add_face(face_p), mesh.add_face(face_q)
            ok = all(face_problem(mesh, f) is None and _v_dot(FaceFrame(mesh, f).normal, parent_normal) > 0.0
                     for f in (f_loop, fp, fq))
        except MeshError:
            ok = False
        if ok:
            chain = [x] + loop_vs + [x]
            return loop_vs, f_loop, [fp, fq], [_find_edge(mesh, u, v) for u, v in zip(chain, chain[1:])]
        mesh.load_state(base)
    raise MeshError("close_loop_at_vertex: no bridge fits")


# ---------------------------------------------------------------------------
# Geometric integrity (decision.md "Q5 integrity findings (2026-09-29)"): a run is
# walked through the *current* faces at commit, and the faces a commit touched are
# checked before anything reaches History. Lab-local, public Core API only.
# ---------------------------------------------------------------------------

# Lengths closer than this (relative to the face's size) are one point; directions
# closer than this (radians) are one direction.
_GEO_EPS = 1e-9
_ANGLE_EPS = 1e-9


def _v_sub(p, q):
    return (p[0] - q[0], p[1] - q[1], p[2] - q[2])


def _v_dot(p, q):
    return p[0] * q[0] + p[1] * q[1] + p[2] * q[2]


def _v_cross(p, q):
    return (p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0])


def _v_len(p) -> float:
    return math.sqrt(_v_dot(p, p))


def _c2(o, a, b) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


class FaceFrame:
    """One face in its own Newell plane: 2D coordinates in which the boundary runs
    counter-clockwise (u x v = the face normal), the unit normal and a length scale.
    Raises MeshError for a face without area (no plane to work in)."""

    def __init__(self, mesh, face_id: FaceId):
        self.face_id = face_id
        self.boundary = mesh.face_vertices(face_id)
        pts = [mesh.vertex_position(v) for v in self.boundary]
        n = _newell(pts)
        length = _v_len(n)
        lo = [min(p[k] for p in pts) for k in range(3)]
        hi = [max(p[k] for p in pts) for k in range(3)]
        self.size = max(1e-12, max(hi[k] - lo[k] for k in range(3)))
        if length <= _GEO_EPS * self.size * self.size:
            raise MeshError(f"face {face_id!r} has no area")
        self.normal = (n[0] / length, n[1] / length, n[2] / length)
        self.area = 0.5 * length
        axis = (1.0, 0.0, 0.0) if abs(self.normal[0]) < 0.9 else (0.0, 1.0, 0.0)
        u = _v_cross(axis, self.normal)
        lu = _v_len(u)
        self.u = (u[0] / lu, u[1] / lu, u[2] / lu)
        self.v = _v_cross(self.normal, self.u)
        self.origin = pts[0]
        self.pts2 = [self.p2(p) for p in pts]
        self.eps = _GEO_EPS * self.size

    def p2(self, p: Position) -> tuple[float, float]:
        d = _v_sub(p, self.origin)
        return (_v_dot(d, self.u), _v_dot(d, self.v))

    def height(self, p: Position) -> float:
        return abs(_v_dot(_v_sub(p, self.origin), self.normal))


def _proper_cross2(a, b, c, d, eps: float) -> bool:
    """Segments ab and cd cross at one point strictly inside both: each end of one lies more
    than `eps` (a distance) off the other's line, on opposite sides."""
    lab, lcd = math.dist(a, b), math.dist(c, d)
    if lab <= eps or lcd <= eps:
        return False
    o1, o2 = _c2(a, b, c) / lab, _c2(a, b, d) / lab
    o3, o4 = _c2(c, d, a) / lcd, _c2(c, d, b) / lcd
    return ((o1 > eps and o2 < -eps) or (o1 < -eps and o2 > eps)) and \
           ((o3 > eps and o4 < -eps) or (o3 < -eps and o4 > eps))


def polygon_is_simple(pts2: list, eps: float) -> bool:
    """No two boundary edges meet except neighbours at their shared corner, and the
    boundary never turns straight back on itself (a spike) — no two corners coincide either."""
    n = len(pts2)
    for i in range(n):
        for j in range(i + 1, n):
            if math.dist(pts2[i], pts2[j]) <= eps:
                return False
    for i in range(n):
        a, b, c = pts2[i - 1], pts2[i], pts2[(i + 1) % n]
        if abs(_c2(a, b, c)) <= eps * max(math.dist(a, b), math.dist(b, c)) and \
                (a[0] - b[0]) * (c[0] - b[0]) + (a[1] - b[1]) * (c[1] - b[1]) > 0.0:
            return False
    for i in range(n):
        a, b = pts2[i], pts2[(i + 1) % n]
        for j in range(i + 2, n):
            if (j + 1) % n == i:
                continue
            c, d = pts2[j], pts2[(j + 1) % n]
            if _proper_cross2(a, b, c, d, eps):
                return False
            # A corner lying on another (non-neighbouring) edge: the boundary touches itself.
            for p, (s, t) in ((a, (c, d)), (b, (c, d)), (c, (a, b)), (d, (a, b))):
                if abs(_c2(s, t, p)) <= eps * math.dist(s, t) and \
                        min(s[0], t[0]) - eps <= p[0] <= max(s[0], t[0]) + eps and \
                        min(s[1], t[1]) - eps <= p[1] <= max(s[1], t[1]) + eps:
                    return False
    return True


def face_problem(mesh, face_id: FaceId) -> str | None:
    """Why a face is geometrically broken ("have no area", "cross itself"), or None."""
    try:
        fr = FaceFrame(mesh, face_id)
    except MeshError:
        return "have no area"
    if not polygon_is_simple(fr.pts2, fr.eps):
        return "cross itself"
    return None


def segment_in_face(mesh, face_id: FaceId, p: Position, q: Position) -> str:
    """Where the straight segment p-q (both on or in the face) lies: "inside" (it may touch the
    boundary only at its own ends), "boundary" (it runs along the boundary) or "outside" (it
    leaves the face or passes through a corner — a concave face)."""
    try:
        fr = FaceFrame(mesh, face_id)
    except MeshError:
        return "outside"
    a2, b2 = fr.p2(p), fr.p2(q)
    m2 = (0.5 * (a2[0] + b2[0]), 0.5 * (a2[1] + b2[1]))
    k = len(fr.pts2)
    inside = False
    for j in range(k):
        c, d = fr.pts2[j], fr.pts2[(j + 1) % k]
        e_len = math.dist(c, d)
        if e_len > 0.0 and abs(_c2(c, d, m2)) <= fr.eps * e_len and \
                min(c[0], d[0]) - fr.eps <= m2[0] <= max(c[0], d[0]) + fr.eps and \
                min(c[1], d[1]) - fr.eps <= m2[1] <= max(c[1], d[1]) + fr.eps:
            return "boundary"
        if (c[1] > m2[1]) != (d[1] > m2[1]) and c[0] + (m2[1] - c[1]) * (d[0] - c[0]) / (d[1] - c[1]) > m2[0]:
            inside = not inside
    if not inside:
        return "outside"
    seg = math.dist(a2, b2)
    for j in range(k):
        c, d = fr.pts2[j], fr.pts2[(j + 1) % k]
        if _proper_cross2(a2, b2, c, d, fr.eps):
            return "outside"
        if min(math.dist(c, a2), math.dist(c, b2)) > fr.eps and seg > 0.0 and \
                abs(_c2(a2, b2, c)) <= fr.eps * seg and \
                0.0 < (c[0] - a2[0]) * (b2[0] - a2[0]) + (c[1] - a2[1]) * (b2[1] - a2[1]) < seg * seg:
            return "outside"  # passes through a corner
    return "inside"


def cut_in_face(mesh, face_id: FaceId, a: VertexId, b: VertexId, positions: list[Position]):
    """Cut one face from boundary vertex `a` to boundary vertex `b` through `positions`
    (straight when empty). Returns (path_edges, new_face_ids); ([], []) when a and b are
    neighbours on the face (along an existing edge: nothing to cut)."""
    if not positions:
        boundary = mesh.face_vertices(face_id)
        n = len(boundary)
        if (boundary.index(a) - boundary.index(b)) % n in (1, n - 1):
            return [], []
        eid, f1, f2 = mesh.connect_vertices(face_id, a, b)
        return [eid], [f1, f2]
    _new_vs, f1, f2, path_edges = split_face_path(mesh, face_id, a, b, positions)
    return path_edges, [f1, f2]


def _copy_attr(value):
    return list(value) if isinstance(value, list) else value


# ---------------------------------------------------------------------------
# Session base — shared step/undo/redo/commit/cancel bookkeeping only (AD-017
# §1.10 decision #1: the two variants' own click/accepts/hover logic is NOT
# shared - "no universal Cut Engine").
# ---------------------------------------------------------------------------

class _KnifeFaceSession(Tool):
    history_description = "Knife Face"
    _SNAPSHOT_ATTRS: tuple[str, ...] = ()

    def _on_activate(self) -> None:
        self._mesh = None
        self._scene = None
        self._selection = None
        self._session_before: Any = None
        self._path_edges: list[EdgeId] = []
        self._step_stack: list[dict] = []
        self._redo_stack: list[tuple[dict, dict]] = []
        self.last_message = ""

    def _on_begin(self, mesh=None, scene=None, selection=None, **_) -> None:
        self._mesh = mesh
        self._scene = scene
        self._selection = selection
        self._session_before = mesh.export_state()
        self._path_edges = []
        self._step_stack = []
        self._redo_stack = []
        self.last_message = ""
        self._init_state()

    def _init_state(self) -> None:
        """Subclass hook: reset variant-specific session state."""

    @property
    def path_edges(self) -> list[EdgeId]:
        return list(self._path_edges)

    def _snapshot(self) -> dict:
        snap = {"state": self._mesh.export_state(), "path_edges": list(self._path_edges)}
        for attr in self._SNAPSHOT_ATTRS:
            snap[attr] = _copy_attr(getattr(self, attr))
        return snap

    def _restore(self, snap: dict) -> None:
        self._mesh.load_state(snap["state"])
        self._path_edges = list(snap["path_edges"])
        for attr in self._SNAPSHOT_ATTRS:
            setattr(self, attr, _copy_attr(snap[attr]))

    def _push_step(self) -> None:
        self._step_stack.append(self._snapshot())

    def undo_step(self) -> bool:
        if not self._step_stack:
            return False
        before = self._step_stack.pop()
        after = self._snapshot()
        self._redo_stack.append((before, after))
        self._restore(before)
        return True

    def redo_step(self) -> bool:
        if not self._redo_stack:
            return False
        before, after = self._redo_stack.pop()
        self._restore(after)
        self._step_stack.append(before)
        return True

    def _on_update(self, **kwargs) -> None:
        pass

    def _integrity_problem(self) -> str | None:
        """Safety net before History (integrity findings, 2026-09-29): the first geometric
        problem among the faces this session touched (new, or boundary changed), or None.
        Checks each touched face (area, simple polygon) and, across each of its edges, the
        neighbour: at most two faces per edge, walked in opposite directions, and not
        facing the other way where the two lie (nearly) in one plane."""
        m = self._mesh
        before = self._session_before["faces"]
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
                        if _v_dot(normal(f), normal(g)) < -0.5:
                            return "a face would be flipped against its neighbour"
                    except MeshError:
                        return "a face would have no area"
        return None

    def _on_commit(self) -> Any:
        current_state = self._mesh.export_state()
        if current_state == self._session_before:
            self.last_message = self.last_message or "commit: nothing changed"
            return None
        problem = self._integrity_problem()
        if problem is not None:
            # Never commit half-broken geometry: the whole session is taken back, History
            # gets nothing, the HUD names the reason.
            self._mesh.load_state(self._session_before)
            self._path_edges = []
            self.last_message = f"commit rolled back — {problem}; mesh unchanged"
            return None
        valid_path = [e for e in self._path_edges if self._mesh.is_valid_edge(e)]
        cmd = MeshStateCommand(
            mesh=self._mesh,
            before_state=self._session_before,
            after_state=current_state,
            description=self.history_description,
        )
        self._scene.history.push(cmd)
        self._redo_stack.clear()
        self._selection.mode = SelectionMode.EDGE
        self._selection.clear()
        self._selection.add(set(valid_path))
        return cmd

    def _on_cancel(self) -> None:
        self._mesh.load_state(self._session_before)
        self._step_stack.clear()
        self._redo_stack.clear()
        self._path_edges = []
        self._init_state()


# ---------------------------------------------------------------------------
# Variant B — Immediate (control): existing Knife semantics extended.
# ---------------------------------------------------------------------------

class KnifeFaceImmediate(_KnifeFaceSession):
    """Variant B: interior clicks are pending inside the *current* face; the
    whole a -> interior* -> boundary path applies in one mutation as soon as
    the path reaches a vertex/edge of that face. No interior start (spec §2,
    acceptance criterion 3)."""

    history_description = "Knife Face (Immediate)"
    _SNAPSHOT_ATTRS = ("_start", "_pending_face", "_pending_positions", "_face_cut_lock")

    def _init_state(self) -> None:
        self._start: VertexId | None = None
        self._pending_face: FaceId | None = None
        self._pending_positions: list[Position] = []
        # Manu, A5 (2026-09-28): moving from a just-finished interior cut
        # straight into a *neighbouring* face's interior must stay invalid,
        # with no line — that would visually read as a cross-face cut
        # (Blender-like), which is explicitly deferred (discovery Q5), not
        # this lab. Set True the moment an interior-involving cut resolves;
        # cleared by any subsequent plain (no-interior) vertex/edge click —
        # an explicit boundary hop "un-ambiguates" which face comes next.
        # Matches the discovery doc's own §8 "Expected" note for the
        # original Variant B ("the neighbour-quad click in task 4 is
        # invalid by design").
        self._face_cut_lock: bool = False

    @property
    def start(self) -> VertexId | None:
        return self._start

    @property
    def pending_face(self) -> FaceId | None:
        return self._pending_face

    @property
    def pending_positions(self) -> list[Position]:
        return list(self._pending_positions)

    def accepts(self, target: dict) -> bool:
        kind = target.get("kind") if target else None
        if kind == "vertex":
            vid = target.get("vertex_id")
            if vid is None or not self._mesh.is_valid_vertex(vid):
                return False
            if self._start is None:
                return True
            if self._pending_positions:
                return vid in self._mesh.face_vertices(self._pending_face)
            return _shares_nonadjacent_face(self._mesh, self._start, vid)

        if kind == "edge":
            eid, t = target.get("edge_id"), target.get("t", 0.5)
            if eid is None or not self._mesh.is_valid_edge(eid) or not (0.0 < t < 1.0):
                return False
            if self._start is None:
                return True
            if self._pending_positions:
                return eid in self._mesh.face_edges(self._pending_face)
            if self._start in self._mesh.edge_vertices(eid):
                return False
            start_faces = {f for e in self._mesh.vertex_edges(self._start) for f in self._mesh.edge_faces(e)}
            return bool(start_faces & set(self._mesh.edge_faces(eid)))

        if kind == "face":
            fid = target.get("face_id")
            if fid is None or self._start is None:
                return False  # B: no interior start (acceptance criterion 3)
            if self._pending_positions:
                if fid != self._pending_face:
                    return False
            else:
                if self._face_cut_lock:
                    return False  # A5: neighbour face right after a cut — invalid, no line
                if self._start not in self._mesh.face_vertices(fid):
                    return False
            dist = target.get("distance_px")
            return dist is not None and dist >= EDGE_MARGIN_PX

        return False

    def hover(self, target: dict) -> dict:
        """`valid` follows `accepts()` exactly (acceptance criterion 6)."""
        return {
            "valid": self.accepts(target),
            "target": target,
            "start": self._start,
            "pending_face": self._pending_face,
            "pending_positions": list(self._pending_positions),
        }

    def _resolve_boundary(self, target: dict, face_id: FaceId) -> VertexId | None:
        if target["kind"] == "vertex":
            vid = target["vertex_id"]
            return vid if vid in self._mesh.face_vertices(face_id) else None
        eid = target["edge_id"]
        if eid not in self._mesh.face_edges(face_id):
            return None
        new_v, _, _ = self._mesh.split_edge(eid, target["t"])
        return new_v

    def click(self, target: dict) -> bool:
        if not self.accepts(target):
            self.last_message = "rejected"
            return False
        kind = target["kind"]

        if kind == "face":
            self._push_step()
            if self._pending_face is None:
                self._pending_face = target["face_id"]
            self._pending_positions.append(target["position"])
            self._redo_stack.clear()
            self.last_message = f"pending interior point ({len(self._pending_positions)})"
            return True

        self._push_step()

        if self._pending_positions:
            face_id = self._pending_face
            b = self._resolve_boundary(target, face_id)
            if b is None:
                self._step_stack.pop()
                self.last_message = "rejected: target not on the pending face's boundary"
                return False
            try:
                new_vs, _f1, _f2, path_edges = split_face_path(
                    self._mesh, face_id, self._start, b, self._pending_positions,
                )
            except MeshError as exc:
                self._step_stack.pop()
                self.last_message = f"cut rejected: {exc}"
                return False
            self._path_edges.extend(path_edges)
            self._start = b
            self._pending_face = None
            self._pending_positions = []
            self._face_cut_lock = True  # A5: block a neighbour-face interior click next
            self._redo_stack.clear()
            self.last_message = f"cut applied ({len(new_vs)} interior point(s))"
            return True

        # No pending points — same semantics as Production Knife (AD-017).
        # A plain boundary click always clears the lock: it is the explicit
        # "un-ambiguating" hop A5 asks for before a new face may be opened.
        if kind == "vertex":
            vid = target["vertex_id"]
            if self._start is None:
                self._start = vid
                self._face_cut_lock = False
                self.last_message = "start set"
                return True
            eid = connect_in_shared_face(self._mesh, self._start, vid)
            if eid is None:
                self._step_stack.pop()
                self.last_message = "connect failed"
                return False
            self._path_edges.append(eid)
            self._start = vid
            self._face_cut_lock = False
            self._redo_stack.clear()
            self.last_message = "cut applied"
            return True

        # kind == "edge"
        eid, t = target["edge_id"], target["t"]
        if self._start is None:
            new_v, _, _ = self._mesh.split_edge(eid, t)
            self._start = new_v
            self._face_cut_lock = False
            self.last_message = "start set"
            return True
        new_v, _, _ = self._mesh.split_edge(eid, t)
        conn = connect_in_shared_face(self._mesh, self._start, new_v)
        if conn is None:
            step = self._step_stack.pop()
            self._restore(step)
            self.last_message = "connect failed"
            return False
        self._path_edges.append(conn)
        self._start = new_v
        self._face_cut_lock = False
        self._redo_stack.clear()
        self.last_message = "cut applied"
        return True


# ---------------------------------------------------------------------------
# Variant D — Collected (Silo-like): applied at commit.
# ---------------------------------------------------------------------------

class KnifeFaceCollected(_KnifeFaceSession):
    """Variant D: every click only extends a virtual path; the mesh changes
    only at commit. Interior start allowed (unlike B)."""

    history_description = "Knife Face (Collected)"
    _SNAPSHOT_ATTRS = ("_path", "_face_cut_lock")

    def _init_state(self) -> None:
        self._path: list[dict] = []
        # Manu, A5 (2026-09-28) — same rule as Variant B (see there for the
        # rationale): True right after the path completes a [boundary,
        # interior+, boundary] run, blocking a fresh interior click in a
        # *neighbouring* face until a plain boundary-to-boundary click
        # "un-ambiguates" which face comes next. Recomputed on every
        # boundary-kind click from the path itself (nothing mutates in D
        # before commit, so there is no click-time mesh state to hang a
        # simpler flag off of).
        self._face_cut_lock: bool = False

    @property
    def path(self) -> list[dict]:
        return list(self._path)

    def _point_faces(self, p: dict) -> set[FaceId]:
        if p["kind"] == "vertex":
            vid = p["vertex_id"]
            return {f for e in self._mesh.vertex_edges(vid) for f in self._mesh.edge_faces(e)}
        if p["kind"] == "edge":
            return set(self._mesh.edge_faces(p["edge_id"]))
        if p["kind"] == "face":
            return {p["face_id"]}
        return set()

    def accepts(self, target: dict) -> bool:
        kind = target.get("kind") if target else None
        if kind == "vertex":
            vid = target.get("vertex_id")
            if vid is None or not self._mesh.is_valid_vertex(vid):
                return False
        elif kind == "edge":
            eid, t = target.get("edge_id"), target.get("t", 0.5)
            if eid is None or not self._mesh.is_valid_edge(eid) or not (0.0 < t < 1.0):
                return False
        elif kind == "face":
            if target.get("face_id") is None or target.get("position") is None:
                return False
            dist = target.get("distance_px")
            if dist is None or dist < EDGE_MARGIN_PX:
                return False
        else:
            return False

        if not self._path:
            return True  # D: interior start allowed (acceptance criterion 3)

        prev = self._path[-1]
        if prev["kind"] == "face":
            fid = prev["face_id"]
            if kind == "face":
                return target["face_id"] == fid
            if kind == "vertex":
                return target["vertex_id"] in self._mesh.face_vertices(fid)
            return target["edge_id"] in self._mesh.face_edges(fid)  # kind == "edge"

        prev_faces = self._point_faces(prev)
        if kind == "face":
            if self._face_cut_lock:
                return False  # A5: neighbour face right after a completed run — invalid, no line
            return target["face_id"] in prev_faces
        if not (prev_faces & self._point_faces(target)):
            return False
        # Directly-adjacent boundary-to-boundary (no interior point between
        # them yet) follows the same non-adjacency rule as Production Knife;
        # once an interior point sits between two boundary points, that pair
        # is never checked against each other directly (each side is checked
        # against the face-interior point instead, above) — the notch/FC3/
        # FC4 cases stay reachable exactly as they are for Variant B.
        if kind == "vertex" and prev["kind"] == "vertex":
            return _shares_nonadjacent_face(self._mesh, prev["vertex_id"], target["vertex_id"])
        if kind == "edge" and prev["kind"] == "vertex":
            if prev["vertex_id"] in self._mesh.edge_vertices(target["edge_id"]):
                return False
        return True

    def hover(self, target: dict) -> dict:
        return {"valid": self.accepts(target), "target": target, "path": list(self._path)}

    def click(self, target: dict) -> bool:
        if not self.accepts(target):
            self.last_message = "rejected"
            return False
        self._push_step()
        self._path.append(dict(target))
        if target["kind"] in ("vertex", "edge"):
            # A5: lock iff an interior point occurred since the previous
            # boundary point — i.e. this click just closed a [boundary,
            # interior+, boundary] run, not a plain boundary-to-boundary hop.
            had_interior = False
            for p in reversed(self._path[:-1]):
                if p["kind"] in ("vertex", "edge"):
                    break
                had_interior = True
            self._face_cut_lock = had_interior
        self._redo_stack.clear()
        self.last_message = f"pending: {len(self._path)} point(s)"
        return True

    # -- commit-time resolution --------------------------------------------

    def _resolve_boundary_point(self, p: dict) -> VertexId:
        if p["kind"] == "vertex":
            return p["vertex_id"]
        v, _, _ = self._mesh.split_edge(p["edge_id"], p["t"])
        return v

    def _resolve_shared_edge_pair(self, eid: EdgeId, t_first: float, t_second: float):
        """Both run ends are edge-points on the *same* original (pre-commit)
        edge — the notch/FC3 case. Splits once at the smaller t, then splits
        the remainder at the adjusted second t; returns the two new vertices
        in click order (first, second)."""
        lo_t, hi_t = (t_first, t_second) if t_first <= t_second else (t_second, t_first)
        v_lo, _e_a, e_b = self._mesh.split_edge(eid, lo_t)
        hi_t_adj = (hi_t - lo_t) / (1.0 - lo_t)
        v_hi, _, _ = self._mesh.split_edge(e_b, hi_t_adj)
        return (v_lo, v_hi) if t_first <= t_second else (v_hi, v_lo)

    def _resolve_boundary_points(self, runs: list[list[dict]]) -> dict[int, VertexId]:
        """Resolve every run-end boundary point to a VertexId exactly once,
        keyed by `id(point)` (not by edge_id/t: two clicks can land at the same
        t on different edges, and float equality is fragile).

        Adjacent runs share their joint point (`[A, B]` and `[B, C]` both hold
        B), and `split_edge` consumes its edge id — resolving per run would
        split B's edge twice (KeyError). Edge points that share one original
        edge (notch/FC3, or across runs) are resolved together in t order,
        since splitting one invalidates the others' edge id/t. A point whose
        resolution fails is simply absent from the map; its runs get dropped."""
        resolved: dict[int, VertexId] = {}
        by_edge: dict[EdgeId, list[dict]] = {}
        seen: set[int] = set()
        # Only run ends: a lone boundary point with no run must not split its
        # edge (no cut, so the mesh has to stay untouched).
        for p in (q for run in runs for q in (run[0], run[-1])):
            if id(p) in seen:
                continue
            seen.add(id(p))
            if p["kind"] == "vertex":
                resolved[id(p)] = p["vertex_id"]
            elif p["t"] <= _GEO_EPS or p["t"] >= 1.0 - _GEO_EPS:
                # An edge point on the edge's end *is* that vertex — splitting there would put a
                # second vertex on top of it (a zero-area sliver, integrity finding R4).
                resolved[id(p)] = self._mesh.edge_vertices(p["edge_id"])[0 if p["t"] <= 0.5 else 1]
            else:
                by_edge.setdefault(p["edge_id"], []).append(p)
        for eid, pts in by_edge.items():
            try:
                if len(pts) == 1:
                    resolved[id(pts[0])] = self._resolve_boundary_point(pts[0])
                elif len(pts) == 2:
                    a, b = self._resolve_shared_edge_pair(eid, pts[0]["t"], pts[1]["t"])
                    resolved[id(pts[0])], resolved[id(pts[1])] = a, b
                else:
                    cur, prev_t = eid, 0.0
                    for p in sorted(pts, key=lambda q: q["t"]):
                        v, _e_a, e_b = self._mesh.split_edge(cur, (p["t"] - prev_t) / (1.0 - prev_t))
                        resolved[id(p)] = v
                        cur, prev_t = e_b, p["t"]
            except (MeshError, LookupError):
                continue
        return resolved

    # -- resolving one run against the current faces (integrity fix, 2026-09-29) --------------
    #
    # Runs are applied one after another, so a run meets the faces the runs before it left
    # behind — never the click-time face it was drawn on. It is therefore *walked*: from its
    # first vertex into the face that holds its next segment, cutting that face up to the
    # first point where the run meets the face's boundary, and on from there. Where it meets
    # a cut of this commit (an edge between two pieces of one click-time face) that edge is
    # split — one intersection vertex, part of both cuts (Artist decision 2026-09-29,
    # "crossing cuts like Blender"). Where it runs along the boundary nothing is cut. Where it
    # would leave its click-time face it cannot be resolved and is dropped (HUD "N-1/N"). Where
    # it crosses itself inside one face, or comes back into a vertex it left, the loop becomes
    # its own face with one bridge (Artist decision 2026-09-30, option (a)).

    def _root(self, face_id: FaceId) -> FaceId:
        """The click-time face a face descends from (itself for an untouched face)."""
        return self._face_root.get(face_id, face_id)

    def _adopt(self, parent: FaceId, children) -> None:
        root = self._root(parent)
        for f in children:
            self._face_root[f] = root

    def _crossable(self, eid: EdgeId) -> bool:
        """A cut of this commit: an edge between two pieces of one click-time face."""
        faces = self._mesh.edge_faces(eid)
        return len(faces) == 2 and self._root(faces[0]) == self._root(faces[1])

    def _step_from(self, p: VertexId, target: Position, root: FaceId | None):
        """Where the run goes from vertex `p` towards `target`: ("face", frame) — into that face
        (its corner at `p` holds the direction) — or ("along", q) — along the boundary edge p-q
        (q not beyond the target). Of several candidates, the face whose plane holds the target
        best wins (a fold edge borders two cube sides; only one holds the target). None: the run
        cannot continue (no face of `root` at `p` holds the direction)."""
        m = self._mesh
        pp = m.vertex_position(p)
        dist = _dist3(pp, target)
        if dist <= _GEO_EPS:
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
            if step[0] == "along" and _dist3(pp, m.vertex_position(step[1])) > dist + fr.eps:
                continue  # the target lies on this edge, before its far end: not a vertex to walk to
            if best is None or tilt < best[0] - _GEO_EPS:
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
            if not _proper_cross2(c, d, a2, b2, eps):
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
        m = self._mesh
        if a == b and not positions:
            return None
        targets = list(positions) + [m.vertex_position(b)]
        last = len(targets) - 1
        p, k, out = a, 0, []
        loops: list[tuple[VertexId, list[Position]]] = []   # (the loop's vertex, its other points)
        for _guard in range(4 * (len(targets) + len(m.all_face_ids())) + 8):
            if p == b and k == last:
                return self._build_loops(loops, root, out)
            step = self._step_from(p, targets[k], root)
            if step is None:
                return None
            if step[0] == "along":
                p = step[1]
                if k < last and _dist3(m.vertex_position(p), targets[k]) <= _GEO_EPS:
                    return None  # an interior point on an existing vertex: not a clean cut
                continue
            fr = step[1]
            if root is None:
                root = self._root(fr.face_id)  # a straight run stays in the face it starts in, too
            i0 = fr.boundary.index(p)
            cur2, skip, pending = fr.pts2[i0], i0, []
            trail = [cur2]                          # the run inside this face so far, in 2D ...
            trail3 = [m.vertex_position(p)]         # ... and in 3D
            pinches: list[tuple[int, list[Position]]] = []   # (index in pending, loop points)
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
                    j, lam = cross
                    if any(idx >= j for idx, _pts in pinches):
                        self._loop_at_point = LOOP_NESTED
                        return None
                    c3, d3 = trail3[j], trail3[j + 1]
                    x3 = tuple(c3[q] + lam * (d3[q] - c3[q]) for q in range(3))
                    pinches.append((j, pending[j:]))
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
                    eid = _find_edge(m, va, vb)
                    if not self._crossable(eid):
                        return None  # the run would leave its click-time face
                    t = lam if m.edge_vertices(eid)[0] == va else 1.0 - lam
                    q, _e1, _e2 = m.split_edge(eid, t)
                if s >= 1.0 - _GEO_EPS * 10 and k < last:
                    k += 1  # the interior point itself lies on that boundary point
                if q == p:
                    # Back into the vertex the run entered this face through: a loop at that
                    # vertex. Nothing else is cut in this face; the run goes on from p.
                    if len(pending) < 2 or pinches:
                        self._loop_at_point = LOOP_NO_AREA if len(pending) < 2 else LOOP_NESTED
                        return None
                    loops.append((p, pending))
                    break
                edges, children = cut_in_face(m, fr.face_id, p, q, pending)
                self._adopt(fr.face_id, children)
                out.extend(edges)
                for idx, pts in pinches:
                    x3 = pending[idx]
                    xv = next(v for f in children for v in m.face_vertices(f)
                               if _dist3(m.vertex_position(v), x3) <= 1e-12)
                    loops.append((xv, pts))
                p = q
                break
        return None

    def _build_loops(self, loops, root: FaceId | None, out: list[EdgeId]):
        """Build the loops a run closed at single points (see `_walk_run`), each in the face at its
        vertex that holds it; None (the run is dropped) if one cannot be built."""
        m = self._mesh
        for x, pts in loops:
            probe = pts[0]
            face = None
            for f in sorted({f for e in m.vertex_edges(x) for f in m.edge_faces(e)}, key=int):
                if root is not None and self._root(f) != root:
                    continue
                try:
                    if FaceFrame(m, f).height(probe) <= 1e-6 * FaceFrame(m, f).size and \
                            segment_in_face(m, f, probe, probe) == "inside":
                        face = f
                        break
                except MeshError:
                    continue
            outline = [m.vertex_position(x)] + list(pts) + [m.vertex_position(x)]
            if face is None or any(segment_in_face(m, face, u, v) != "inside" for u, v in zip(outline, outline[1:])):
                self._loop_at_point = LOOP_CROSSED
                return None
            try:
                _vs, f_loop, ring, loop_edges = close_loop_at_vertex(m, face, x, pts)
            except MeshError:
                self._loop_at_point = LOOP_NO_BRIDGE
                return None
            self._adopt(face, [f_loop] + ring)
            out.extend(loop_edges)
            self._loops_built += 1
        return out

    def _apply_run(self, run: list[dict], resolved: dict[int, VertexId]) -> bool:
        first, last = run[0], run[-1]
        interior = run[1:-1]
        a, b = resolved.get(id(first)), resolved.get(id(last))
        if a is None or b is None:
            return False
        # Every interior point of a run lies in one click-time face (the planner puts a crossing
        # at every face change; D accepts no other face) — the run may not leave it.
        root = interior[0]["face_id"] if interior else None
        state, roots, built = self._mesh.export_state(), dict(self._face_root), self._loops_built
        self._loop_at_point = None
        try:
            edges = self._walk_run(a, [p["position"] for p in interior], b, root)
        except (MeshError, LookupError, ValueError, ZeroDivisionError):
            # Safety net: a run that trips over Core degrades to a dropped run (HUD "N/M") —
            # never an exception out of commit, which would skip the History push for
            # whatever earlier runs already mutated.
            edges = None
        if edges is None:
            self._mesh.load_state(state)
            self._face_root = roots
            self._loops_built = built
            if self._loop_at_point:
                self._loops_at_point[self._loop_at_point] += 1
            return False
        self._path_edges.extend(edges)
        return True

    def _resolve_closed_loop(self, path: list[dict]) -> str:
        fid = path[0]["face_id"]
        positions = [p["position"] for p in path]
        boundary = self._mesh.face_vertices(fid)
        state = self._mesh.export_state()
        try:
            i1, bv1, i2, bv2 = select_bridge(self._mesh, boundary, positions)
            _loop_vs, f_inner, f_a, f_b, loop_edges = close_loop_with_bridges(
                self._mesh, fid, positions, i1, bv1, i2, bv2,
            )
        except MeshError as exc:
            return f"closed shape rejected: {exc}"
        problem = next((pr for pr in (face_problem(self._mesh, f) for f in (f_inner, f_a, f_b)) if pr), None)
        if problem is not None:
            # An outline that crosses itself, or a bridge through the loop (Task A observation):
            # only this shape is taken back, the rest of the commit stands.
            self._mesh.load_state(state)
            return f"closed shape rejected: a face would {problem} (its outline or a bridge crosses the loop)"
        self._adopt(fid, (f_inner, f_a, f_b))
        self._path_edges.extend(loop_edges)
        return f"closed shape — {len(positions)} points, 2 bridges, 3 faces"

    def _resolve_path(self) -> None:
        path = self._path
        if not path:
            self.last_message = "no points"
            return

        if all(p["kind"] == "face" for p in path):
            fid = path[0]["face_id"]
            if len(path) < 3 or any(p["face_id"] != fid for p in path):
                self.last_message = (
                    f"closed shape needs >= 3 points in one face — dropped "
                    f"({len(path)} point(s)); mesh unchanged"
                )
                return
            self.last_message = self._resolve_closed_loop(path)
            return

        # Leading interior points before the first boundary point have no
        # boundary vertex to anchor a split_face_path on (same class as the
        # discovery's FC5 "dangling start" — not a valid cut result unless
        # the path closes back on itself, which only the pure-interior-loop
        # branch above handles) — dropped, same as a dangling tail.
        lead_drop = 0
        while lead_drop < len(path) and path[lead_drop]["kind"] == "face":
            lead_drop += 1
        dropped_lead = lead_drop > 0
        path = path[lead_drop:]

        runs: list[list[dict]] = []
        current: list[dict] = []
        for p in path:
            current.append(p)
            if p["kind"] in ("vertex", "edge"):
                if len(current) >= 2:
                    runs.append(current)
                current = [p]
        dropped_tail = len(current) > 1

        resolved = self._resolve_boundary_points(runs)
        applied = 0
        for run in runs:
            if self._apply_run(run, resolved):
                applied += 1
        msg = f"{applied}/{len(runs)} cut(s) applied" if runs else "no complete cut"
        notes = []
        if dropped_lead:
            notes.append("leading interior point(s) dropped (no boundary reached before them)")
        if dropped_tail:
            notes.append("trailing interior point(s) dropped (no boundary reached)")
        notes.extend(self._loop_at_point_note())
        if notes:
            msg += "; " + "; ".join(notes)
        self.last_message = msg

    def _loop_at_point_note(self) -> list[str]:
        notes = []
        if self._loops_built:
            notes.append(f"{self._loops_built} loop(s) closed at a single point — own face, 1 bridge")
        for reason, n in sorted(self._loops_at_point.items()):
            notes.append(f"{n} cut(s) closing a loop at a single point dropped ({reason})")
        return notes

    def _on_commit(self) -> Any:
        self._face_root: dict[FaceId, FaceId] = {}
        self._loops_at_point: collections.Counter = collections.Counter()
        self._loops_built = 0
        self._resolve_path()
        return super()._on_commit()
