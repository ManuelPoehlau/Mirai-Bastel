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
    dropped). Interior start allowed.

Per AD-017 §1.10/decision #1 ("no universal Cut Engine"): the two variants
are written independently, sharing only small mode-agnostic helpers (picking,
`split_face_path`, `connect_in_shared_face`) - not a shared "path resolver".
"""

from __future__ import annotations

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

    def _on_commit(self) -> Any:
        current_state = self._mesh.export_state()
        if current_state == self._session_before:
            self.last_message = self.last_message or "commit: nothing changed"
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

    def _live_face_for(self, face_id: FaceId, a: VertexId, b: VertexId) -> FaceId | None:
        """The face an interior run cuts. The click-time `face_id` goes stale
        when an earlier run of the same commit already split that face; then
        the face now holding both run ends (lowest id, like
        `connect_in_shared_face`) is the one the interior points lie in."""
        m = self._mesh
        if m.is_valid_face(face_id):
            vs = m.face_vertices(face_id)
            if a in vs and b in vs:
                return face_id
        for fid in sorted(m.all_face_ids(), key=int):
            vs = m.face_vertices(fid)
            if a in vs and b in vs:
                return fid
        return None

    def _apply_run(self, run: list[dict], resolved: dict[int, VertexId]) -> bool:
        first, last = run[0], run[-1]
        interior = run[1:-1]
        positions = [p["position"] for p in interior]

        a, b = resolved.get(id(first)), resolved.get(id(last))
        if a is None or b is None:
            return False

        try:
            if not positions:
                eid = connect_in_shared_face(self._mesh, a, b)
                if eid is None:
                    return False
                self._path_edges.append(eid)
                return True

            face_id = self._live_face_for(interior[0]["face_id"], a, b)
            if face_id is None:
                return False
            _new_vs, _f1, _f2, path_edges = split_face_path(self._mesh, face_id, a, b, positions)
        except (MeshError, LookupError):
            # Safety net: a run that trips over Core degrades to a dropped
            # run (HUD "N/M") — never an exception out of commit, which would
            # skip the History push for whatever earlier runs already mutated.
            return False
        self._path_edges.extend(path_edges)
        return True

    def _resolve_closed_loop(self, path: list[dict]) -> str:
        fid = path[0]["face_id"]
        positions = [p["position"] for p in path]
        boundary = self._mesh.face_vertices(fid)
        try:
            i1, bv1, i2, bv2 = select_bridge(self._mesh, boundary, positions)
            _loop_vs, _f_inner, _f_a, _f_b, loop_edges = close_loop_with_bridges(
                self._mesh, fid, positions, i1, bv1, i2, bv2,
            )
        except MeshError as exc:
            return f"closed shape rejected: {exc}"
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
        if notes:
            msg += "; " + "; ".join(notes)
        self.last_message = msg

    def _on_commit(self) -> Any:
        self._resolve_path()
        return super()._on_commit()
