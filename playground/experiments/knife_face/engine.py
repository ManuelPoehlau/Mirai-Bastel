"""Knife Face Cut Lab — session engines (Discovery, no Production change).

The commit-time resolver of Variants D and Q5 lives in `src/mirai/topology/knife_resolve.py` since
WP-KNIFE-01 S1 (one implementation, camera-free, faces built through `Mesh.split_face`); the face
geometry it uses in `src/mirai/topology/face_geometry.py`. What stays here is the Lab's click-time
part: face-interior picking, the sessions' path / undo / redo / accepts / hover / click, the HUD text.

Three session engines, all `mirai.interaction.tool.Tool` subclasses (same
session/undo/commit/cancel state machine `mirai.topology.knife.KnifeTool`
already uses — reused as-is here, not modified):

  KnifeFaceImmediate (Variant B, REJECTed, still runnable) — interior clicks are
    pending (non-mutating) steps inside the *current* face; the whole path
    (start -> interior* -> boundary) is applied in one mutation as soon as it
    reaches a vertex/edge of that face. No interior start. Covers FC1-FC4.

  KnifeFaceCollected (Variant D) — every click (vertex/edge/face) only
    extends a virtual path; nothing mutates the mesh until commit, where
    `knife_resolve.resolve_collected` resolves it (runs walked through the
    faces the runs before them left behind, closed shapes, loops at a point).
    Interior start allowed.

  KnifeFaceCrossFace (Variant Q5, `engine_q5.py`) — D plus the planner.

Every path point carries an explicit point id (`"pid"`), assigned when it is clicked; the resolver
identifies points by it (never by object identity). All variants share the commit safety net
(`knife_resolve.check_commit`): faces the session touched are checked before History, a broken result
is rolled back as a whole.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

from core import EdgeId, FaceId, VertexId
from core.mesh import MeshError
from core.selection import SelectionMode
from core.operations.topology import MeshStateCommand

from mirai.interaction.tool import Tool
from mirai.topology.face_geometry import Position
from mirai.topology.knife_pick import knife_pick as _base_knife_pick
from mirai.topology.knife_resolve import (
    ClosedShape,
    KnifeResolution,
    check_commit,
    resolve_collected,
    split_face_path,
)
from mirai.topology.topology_points import connect_in_shared_face
from viewport.derived import triangulate_mesh_face

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
# Click-time helper (AD-017 §11 shape: small, no session state) - the same
# non-adjacency test KnifeTool already makes.
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
        # Never commit half-broken geometry: a broken result takes the whole session back,
        # History gets nothing, the HUD names the reason (`knife_resolve.check_commit`).
        check = check_commit(self._mesh, self._session_before)
        if check.rolled_back:
            self._path_edges = []
            self.last_message = f"commit rolled back — {check.problem}; mesh unchanged"
            return None
        if check.after_state is None:
            self.last_message = self.last_message or "commit: nothing changed"
            return None
        valid_path = [e for e in self._path_edges if self._mesh.is_valid_edge(e)]
        cmd = MeshStateCommand(
            mesh=self._mesh,
            before_state=self._session_before,
            after_state=check.after_state,
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
        # Explicit point ids (WP-KNIFE-01 S1): the resolver identifies a point by its "pid",
        # never by object identity. Monotonic per session; undo/redo never reuses one.
        self._pids = itertools.count()

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
        self._path.append(dict(target, pid=next(self._pids)))
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

    # -- commit-time resolution (`mirai.topology.knife_resolve`) -------------------------

    def _records(self) -> list[dict]:
        """The path as resolver records: every point with its explicit id. Clicks get theirs at
        click time; a point put into the path some other way (a test) gets one here — one id per
        object, so a point that appears twice keeps one id."""
        out: list[dict] = []
        assigned: list[tuple[dict, dict]] = []
        for p in self._path:
            if p["kind"] == "break" or "pid" in p:
                out.append(p)
                continue
            rec = next((r for q, r in assigned if q is p), None)
            if rec is None:
                rec = dict(p, pid=next(self._pids))
                assigned.append((p, rec))
            out.append(rec)
        return out

    def _resolve_path(self) -> None:
        res = resolve_collected(self._mesh, self._records(), self._session_before)
        self._path_edges.extend(res.path_edges)
        self.last_message = self._message(res)

    @staticmethod
    def _message(res: KnifeResolution) -> str:
        if res.empty:
            return "no points"
        if res.short_shapes:
            return (f"closed shape needs >= 3 points in one face — dropped "
                    f"({res.short_shapes[0]} point(s)); mesh unchanged")
        if res.closed_shapes:
            return closed_shape_text(res.closed_shapes[0])
        msg = f"{res.applied}/{res.runs} cut(s) applied" if res.runs else "no complete cut"
        notes = []
        if res.dropped_lead:
            notes.append("leading interior point(s) dropped (no boundary reached before them)")
        if res.dropped_tail:
            notes.append("trailing interior point(s) dropped (no boundary reached)")
        notes.extend(loop_at_point_notes(res))
        if notes:
            msg += "; " + "; ".join(notes)
        return msg

    def _on_commit(self) -> Any:
        self._resolve_path()
        return super()._on_commit()


# ---------------------------------------------------------------------------
# HUD text for what the resolver reports (shared by D and Q5)
# ---------------------------------------------------------------------------

def closed_shape_text(shape: ClosedShape) -> str:
    if shape.error is not None:
        return f"closed shape rejected: {shape.error}"
    if shape.problem is not None:
        return f"closed shape rejected: a face would {shape.problem} (its outline or a bridge crosses the loop)"
    return f"closed shape — {shape.points} points, 2 bridges, 3 faces"


def loop_at_point_notes(res: KnifeResolution) -> list[str]:
    notes = []
    if res.loops_built:
        each = " each" if res.loops_built > 1 else ""
        notes.append(f"{res.loops_built} loop(s) closed at a single point — own face, 1 bridge{each}")
    for reason, n in sorted(res.loops_dropped.items()):
        notes.append(f"{n} cut(s) closing a loop at a single point dropped ({reason})")
    return notes
