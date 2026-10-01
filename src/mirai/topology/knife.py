"""Knife session tool — a virtual path of explicit points, resolved at commit (AD-017 §1.7).

Moved (not copied) from `playground/topology_tools/knife.py` in WP-06 Slice B7
(session engine PROMOTED, AD-017 DECIDED). Production (`mirai.application`)
and the Playground (`playground/window.py`, `knife` family) share this one
implementation.

WP-KNIFE-01 S2 (M1, AD-017 addendum 2026-10-01 "One Knife S2", KEEP 2026-10-01):
the session does not cut at every click. It keeps an ordered path of points,
each with an explicit point id `pid`, and the mesh is untouched until commit,
where the Knife's resolver (`knife_resolve.resolve_cross_face`, WP-KNIFE-01 S1)
cuts it and `check_commit` guards History.

WP-KNIFE-01 S3 (PROVISIONAL until Manu's verdict): everything the Knife Face
Lab's Q5 (KEEP 2026-09-30) does *inside one face* — face-interior points (notch,
bent cuts, closed shapes, loops at a point, the last click joined to the nearest
corner at commit), closing a shape by clicking its start, connecting to an
earlier point. The click-time rules are Q5's `plan()` without the planner: a
segment that no face of its two points holds stays refused (cross-face, slice
S4). Where the S2 rules had already decided a vertex/edge-only case differently
from Q5, S2 is kept (decision.md "One Knife S3", open points S3-a/b).

Modal tool. Headless-testable (no window code).

Path records (`knife_resolve`'s format): `{"kind": "vertex", "vertex_id"}`,
`{"kind": "edge", "edge_id", "t"}` (t along the edge as it was clicked),
`{"kind": "face", "face_id", "position"}` (an interior click), each with its
`pid`; `{"kind": "break", "reason": "edge"}` before a skipped point;
`{"kind": "break", "reason": "closed", "cyclic": bool}` where a chain was closed
— followed by the closing point again (the *seed*: the next chain starts there).

Rules (parity rows P01–P15 / S1–S5, `tests/test_knife_parity.py`; the Q5
differential spec, `playground/tests/test_knife_q5_differential.py`):
- The first click places the start point (an interior point too). Every further
  click must share a face with the last point; the segment between them is
  - a **cut** when it lies inside a shared face — for two boundary points the
    F2 chord check (`chord_validity`: inside the face, not along its boundary,
    not out of a concave face), with an interior point Q5's `segment_in_face`;
  - a **skip** when it runs along an existing edge — the neighbour vertex, the
    end of the clicked edge, a second point on the same edge, a straight run of
    boundary edges, or (two boundary points) the session's own earlier cut
    retraced (AQ1, S2-b): accepted, nothing cut, the chain continues from the
    new point, a `{"kind": "break", "reason": "edge"}` record before it;
  - refused otherwise (no shared face, or no shared face holds the straight
    line — the planner's job, slice S4).
- An interior click needs `EDGE_MARGIN_PX` clearance from its face's edges.
- A click on the **start** of the current chain (an own point, or the vertex)
  after at least 3 points of that chain **closes** it — it does not commit; the
  path gets a "closed" break and the start again, so the next click continues
  from the closing point. Fewer than 3 points: refused when an interior point is
  involved (Q5), the S2 rule otherwise (S3-a).
- A click on an earlier **boundary** point (own edge point, a vertex on the
  path) connects to that very record and continues from it; an earlier
  **interior** point is refused (not supported yet). The same point twice in a
  row is refused.
- In-session Undo removes the last click's records, Redo puts them back; a new
  click clears the Redo branch (AD-017 DECIDED 2026-09-22).
- Cancel / Esc: the path is dropped; mesh and History were never touched.
- Commit: resolve, check (`check_commit`: a broken result is taken back as a
  whole), push exactly one `MeshStateCommand` ("Knife") if the mesh changed,
  select the cut edges in Edge mode. Nothing changed → no command.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from core.operations.topology import MeshStateCommand
from core.selection import SelectionMode
from ..interaction.tool import Tool
from .chord_validity import chord_valid_in_polygon
from .face_geometry import GEO_EPS, segment_in_face
from .knife_pick import EDGE_MARGIN_PX
from .knife_preview import target_position
from .knife_resolve import KnifeResolution, check_commit, is_break, is_chain_end, resolve_cross_face

# A chain is closed by a click on its start after at least this many points (Q5's MIN_CLOSE_POINTS).
MIN_CLOSE_POINTS = 3

CROSS_FACE = "no shared face holds the cut (cross-face: not yet)"
TOO_CLOSE = "too close to an edge"
CLOSE_NEEDS = f"closing needs at least {MIN_CLOSE_POINTS} points"
EARLIER_INTERIOR = "connecting to an earlier interior point is not supported yet"
SAME_POINT = "already the last point"


def _faces_of(mesh, p: dict) -> set:
    if p["kind"] == "face":
        return {p["face_id"]}
    if p["kind"] == "edge":
        return set(mesh.edge_faces(p["edge_id"]))
    return {f for e in mesh.vertex_edges(p["vertex_id"]) for f in mesh.edge_faces(e)}


@dataclass
class KnifePlan:
    """What a click on a target would do — `accepts()`, `click()` and the status line share it."""

    ok: bool
    reason: str = ""                                   # why refused, or what the click does
    entries: list = field(default_factory=list)        # records the click appends
    start: bool = False                                # the first point of the session
    skip: bool = False                                 # along an existing edge: nothing to cut
    closing: bool = False                              # closes the current chain (no commit)
    cyclic: bool = False                               # ... as one loop (no skipped stretch in it)
    earlier: bool = False                              # connects to an earlier point


class KnifeTool(Tool):
    """Knife modal tool.

    Usage lifecycle:
      knife = KnifeTool()
      knife.activate()
      knife.begin(mesh=..., scene=..., selection=...)
      # during session (the mesh is not changed):
      knife.plan(target)    # what a click would do (KnifePlan), no change
      knife.accepts(target) # would click(target) be accepted?
      knife.hover(target)   # preview info
      knife.click(target)   # add a point to the path
      knife.undo_step()     # remove the most recent click
      knife.redo_step()     # put the most recently undone click back
      # end session:
      knife.commit()        # resolve the path, push one history entry, residue
      # or:
      knife.cancel()        # drop the path, no history

    Targets: {"kind": "vertex", "vertex_id"}, {"kind": "edge", "edge_id", "t"},
    {"kind": "face", "face_id", "position", "distance_px"} (a `knife_pick` face hit),
    {"kind": "point", "pid"} (one of the session's own points); anything else
    ({"kind": "outside"}) is refused.
    """

    def _on_activate(self) -> None:
        self._mesh = None
        self._scene = None
        self._selection = None
        self._session_before = None
        self._path: list[dict] = []
        self._steps: list[int] = []            # records added per accepted click
        self._redo: list[list[dict]] = []      # undone clicks' records, most recent last
        self._pids = itertools.count()
        self._path_edges: list = []
        self.last_plan: KnifePlan | None = None
        self.last_resolution: KnifeResolution | None = None
        self.last_problem: str | None = None

    def _on_begin(self, mesh=None, scene=None, selection=None, **_) -> None:
        self._mesh = mesh
        self._scene = scene
        self._selection = selection
        self._session_before = mesh.export_state()
        self._path = []
        self._steps = []
        self._redo = []
        self._pids = itertools.count()
        self._path_edges = []
        self.last_plan = None
        self.last_resolution = None
        self.last_problem = None
        print("[KNIFE] session begin (virtual path, mesh unchanged until commit)")

    # -- session state (read-only) ---------------------------------------------------------

    @property
    def path(self) -> list[dict]:
        """The path records in click order, breaks included (copy; the records are shared and
        never changed after the click that adds them) — `knife_resolve`'s record format."""
        return list(self._path)

    @property
    def points(self) -> list[dict]:
        """The placed points in path order; a point clicked again (or a chain's seed) appears again."""
        return [p for p in self._path if not is_break(p)]

    def _chain_start(self) -> int:
        for i in range(len(self._path) - 1, -1, -1):
            if is_chain_end(self._path[i]):
                return i + 1
        return 0

    @property
    def chain_points(self) -> list[dict]:
        """The points of the current (open) chain — after a close, it starts with the closing point."""
        return [p for p in self._path[self._chain_start():] if not is_break(p)]

    @property
    def last_point(self) -> dict | None:
        """The point the next segment starts from; None before the first click."""
        return next((p for p in reversed(self._path) if not is_break(p)), None)

    @property
    def cut_segments(self) -> list[tuple[dict, dict]]:
        """Point pairs that commit will cut: consecutive points of each chain (not across a skip
        break), plus the closing segment of a chain closed as one loop."""
        segs: list[tuple[dict, dict]] = []
        prev = first = None
        for p in self._path:
            if is_chain_end(p):
                if p.get("cyclic") and prev is not None and first is not None and prev is not first:
                    segs.append((prev, first))
                prev = first = None
                continue
            if is_break(p):
                prev = None
                continue
            if prev is not None and prev is not p:
                segs.append((prev, p))
            if first is None:
                first = p
            prev = p
        return segs

    @property
    def path_edges(self) -> list:
        """The edges the committed session cut (the residue); empty before commit."""
        return list(self._path_edges)

    def point_position(self, p: dict):
        """World position of a path record or of a vertex / edge / face / own-point target; None if unknown."""
        if p.get("kind") == "point":
            p = self._point_by_pid(p.get("pid"))
            if p is None:
                return None
        return target_position(self._mesh, p)

    # -- acceptance -------------------------------------------------------------------------

    def _point_by_pid(self, pid) -> dict | None:
        if pid is None:
            return None
        return next((p for p in self._path if not is_break(p) and p["pid"] == pid), None)

    def _invalid(self, target: dict | None) -> str | None:
        """Why `target` is no point at all (None: it is one)."""
        kind = target.get("kind") if target else None
        m = self._mesh
        if kind == "vertex":
            vid = target.get("vertex_id")
            return None if vid is not None and m.is_valid_vertex(vid) else "invalid vertex"
        if kind == "edge":
            eid, t = target.get("edge_id"), target.get("t", 0.5)
            return None if eid is not None and m.is_valid_edge(eid) and 0.0 < t < 1.0 else "invalid edge point"
        if kind == "face":
            fid = target.get("face_id")
            if fid is None or target.get("position") is None or not m.is_valid_face(fid):
                return "invalid face point"
            dist = target.get("distance_px")
            return None if dist is not None and dist >= EDGE_MARGIN_PX else TOO_CLOSE
        if kind == "point":
            return None if self._point_by_pid(target.get("pid")) is not None else "invalid own point"
        return f"no target ({kind})"

    def _point_for(self, target: dict | None) -> dict | None:
        """The path record a click on `target` would add: an existing record for an own point or a
        vertex already on the path (the same point id), a new one (no pid yet) otherwise. Does not
        check the face point margin (`_invalid`)."""
        kind = target.get("kind") if target else None
        m = self._mesh
        if kind == "vertex":
            vid = target.get("vertex_id")
            if vid is None or not m.is_valid_vertex(vid):
                return None
            known = [p for p in self.points if p["kind"] == "vertex" and p["vertex_id"] == vid]
            chain = self.chain_points
            known.sort(key=lambda p: 0 if chain and p is chain[0] else 1)   # the chain start first (Q5)
            return known[0] if known else {"kind": "vertex", "vertex_id": vid}
        if kind == "edge":
            eid, t = target.get("edge_id"), target.get("t", 0.5)
            if eid is None or not m.is_valid_edge(eid) or not (0.0 < t < 1.0):
                return None
            return {"kind": "edge", "edge_id": eid, "t": t}
        if kind == "face":
            fid, pos = target.get("face_id"), target.get("position")
            if fid is None or pos is None or not m.is_valid_face(fid):
                return None
            return {"kind": "face", "face_id": fid, "position": tuple(pos)}
        if kind == "point":
            return self._point_by_pid(target.get("pid"))
        return None

    @staticmethod
    def _same(a: dict, b: dict) -> bool:
        if a is b or ("pid" in a and "pid" in b and a["pid"] == b["pid"]):
            return True
        if a["kind"] == b["kind"] == "vertex":
            return a["vertex_id"] == b["vertex_id"]
        if a["kind"] == b["kind"] == "edge":
            return a["edge_id"] == b["edge_id"] and abs(a["t"] - b["t"]) <= GEO_EPS
        return False

    def _chord_valid(self, face, a: dict, b: dict) -> bool:
        """F2 (`chord_validity`) for two path points on `face`'s boundary: an edge point is inserted
        into a copy of the boundary where `split_edge` would put it."""
        m = self._mesh
        boundary = m.face_vertices(face)
        edges = m.face_edges(face)
        points, index = [], {}
        for i, vid in enumerate(boundary):
            for key, p in (("a", a), ("b", b)):
                if p["kind"] == "vertex" and p["vertex_id"] == vid:
                    index[key] = len(points)
            points.append(m.vertex_position(vid))
            for key, p in (("a", a), ("b", b)):
                if p["kind"] == "edge" and p["edge_id"] == edges[i]:
                    index[key] = len(points)
                    points.append(target_position(m, p))
        if len(index) < 2:
            return False
        return chord_valid_in_polygon(points, index["a"], index["b"])

    def _link(self, a: dict, b: dict) -> str | None:
        """"cut", "edge" (along an existing edge: skip) or None (refused) for the segment a -> b."""
        m = self._mesh
        shared = _faces_of(m, a) & _faces_of(m, b)
        if not shared:
            return None
        pa, pb = target_position(m, a), target_position(m, b)
        if a["kind"] == "face" or b["kind"] == "face":
            # Q5's rule for a segment with an interior end: the straight line has to lie in a shared face.
            where = {segment_in_face(m, f, pa, pb) for f in shared}
            if "inside" in where:
                return "cut"
            return "edge" if "boundary" in where else None
        if "pid" in a and "pid" in b and any(
            {x["pid"], y["pid"]} == {a["pid"], b["pid"]} for x, y in self.cut_segments
        ):
            return "edge"  # retracing the session's own cut (AQ1 applied to the session's edges, S2-b)
        ka, kb = a["kind"], b["kind"]
        if ka == "vertex" and kb == "edge" and a["vertex_id"] in m.edge_vertices(b["edge_id"]):
            return "edge"
        if ka == "edge" and kb == "vertex" and b["vertex_id"] in m.edge_vertices(a["edge_id"]):
            return "edge"
        if ka == kb == "edge" and a["edge_id"] == b["edge_id"]:
            return "edge"
        if any(self._chord_valid(f, a, b) for f in sorted(shared, key=int)):
            return "cut"
        # Neighbour vertices, or a straight run of boundary edges (R3): nothing to cut.
        if any(segment_in_face(m, f, pa, pb) == "boundary" for f in shared):
            return "edge"
        return None

    def plan(self, target: dict | None) -> KnifePlan:
        """What `click(target)` would do (no change)."""
        bad = self._invalid(target)
        if bad is not None:
            return KnifePlan(False, bad)
        point = self._point_for(target)
        last = self.last_point
        if last is None:
            return KnifePlan(True, "start point", entries=[point], start=True)
        if "pid" in point:
            return self._plan_existing(point, last)
        if self._same(point, last):
            return KnifePlan(False, SAME_POINT)
        return self._plan_segment(last, point)

    def _plan_existing(self, point: dict, last: dict) -> KnifePlan:
        """A click on a point already on the path (an own point, or a vertex clicked before)."""
        if self._same(point, last):
            return KnifePlan(False, SAME_POINT)
        chain = self.chain_points
        if chain and self._same(point, chain[0]):
            if len(chain) >= MIN_CLOSE_POINTS:
                return self._plan_segment(last, point, closing=True)
            if point["kind"] == "face" or last["kind"] == "face":
                return KnifePlan(False, CLOSE_NEEDS)
            # S2 (S3-a): back on a boundary start after one other boundary point is an ordinary
            # earlier-point click (a retrace is a skip, S2-b) — Q5 refuses it (CLOSE_NEEDS).
        elif point["kind"] == "face":
            return KnifePlan(False, EARLIER_INTERIOR)
        return self._plan_segment(last, point, earlier=True)

    def _plan_segment(self, a: dict, b: dict, *, closing: bool = False, earlier: bool = False) -> KnifePlan:
        link = self._link(a, b)
        if link is None:
            return KnifePlan(False, CROSS_FACE)
        entries: list[dict] = []
        if link == "edge":
            entries.append({"kind": "break", "reason": "edge"})
        entries.append(b)
        cyclic = False
        if closing:
            chain = self._path[self._chain_start():]
            cyclic = link == "cut" and not any(is_break(p) for p in chain)
            if cyclic:
                entries.pop()  # the closing point is the start already: resolved as a loop at commit
            entries.append({"kind": "break", "reason": "closed", "cyclic": cyclic})
            # The seed of the next chain: the closing point again — the very same record (one point id,
            # one vertex at commit). Without a loop (a skipped stretch) it is also the chain's last point.
            entries.append(b)
        if closing:
            reason = "closed" if cyclic else "closed (with a skipped stretch)"
        elif link == "edge":
            reason = "along an existing edge: skipped"
        else:
            reason = "connects to an earlier point" if earlier else "cut"
        return KnifePlan(True, reason, entries=entries, skip=link == "edge", closing=closing,
                         cyclic=cyclic, earlier=earlier)

    def accepts(self, target: dict) -> bool:
        """Would `click(target)` be accepted? Same rules, no change (the preview gate)."""
        return self.plan(target).ok

    def hover(self, target: dict) -> dict:
        """Preview info, no change: {"valid": bool, "target", "start": the last point record or None}.

        Deliberately looser than `click()` / `accepts()` (the Playground `knife` family's preview, F2
        addendum): "valid" = a vertex, an edge point, a face point or an own point the session knows — a
        segment with no shared face (P10), out of a concave face (R5), the same point twice (P13) or a
        face point inside the edge margin is only refused by `click()`. `Application` previews through
        `accepts()`."""
        return {"valid": self._point_for(target) is not None, "target": target, "start": self.last_point}

    def click(self, target: dict) -> bool:
        """Add a point. Returns True if accepted, False if refused (no change); `last_plan` says why."""
        plan = self.plan(target)
        self.last_plan = plan
        if not plan.ok:
            print(f"[KNIFE] rejected: {plan.reason}")
            return False
        for p in plan.entries:
            if not is_break(p) and "pid" not in p:
                p["pid"] = next(self._pids)   # a new point: its id comes with this click
        self._path.extend(plan.entries)
        self._steps.append(len(plan.entries))
        self._redo.clear()
        last = plan.entries[-1]
        print(f"[KNIFE] point {last['pid']} ({last['kind']}): {plan.reason}; "
              f"points={len(self.points)} cuts={len(self.cut_segments)}")
        return True

    def undo_step(self) -> bool:
        """Remove the most recent click. Returns True if a click was undone."""
        if not self._steps:
            print("[KNIFE] undo_step: nothing to undo")
            return False
        n = self._steps.pop()
        self._redo.append(self._path[-n:])
        del self._path[-n:]
        print(f"[KNIFE] undo_step: points={len(self.points)}")
        return True

    def redo_step(self) -> bool:
        """Put the most recently undone click back. Empty redo branch → no-op."""
        if not self._redo:
            print("[KNIFE] redo_step: nothing to redo")
            return False
        entries = self._redo.pop()
        self._path.extend(entries)
        self._steps.append(len(entries))
        print(f"[KNIFE] redo_step: points={len(self.points)}")
        return True

    def _on_update(self, **kwargs) -> None:
        pass

    # -- end of session ------------------------------------------------------------------------

    def _on_commit(self):
        """Resolve the path; returns the MeshStateCommand, or None if nothing changed or the
        result was broken and taken back (`last_problem` says why). `last_resolution` holds what
        the resolver did (counts and notes; `empty` for a path without points)."""
        self._redo.clear()
        self.last_problem = None
        res = resolve_cross_face(self._mesh, list(self._path), self._session_before)
        check = check_commit(self._mesh, self._session_before)
        self.last_resolution = res
        self.last_problem = check.problem
        if check.after_state is None:
            print(f"[KNIFE] commit: {res.applied}/{res.runs} cut(s); "
                  + (f"rolled back ({check.problem})" if check.rolled_back else "nothing changed")
                  + " -> no history")
            return None
        self._path_edges = [e for e in res.path_edges if self._mesh.is_valid_edge(e)]
        print(f"[KNIFE] commit: {res.applied}/{res.runs} cut(s) applied; "
              f"path_edges={[int(e) for e in self._path_edges]} -> 1 history entry")
        cmd = MeshStateCommand(
            mesh=self._mesh,
            before_state=self._session_before,
            after_state=check.after_state,
            description="Knife",
        )
        self._scene.history.push(cmd)
        # Residue (AD-017, DECIDED): select the cut edges, switch to Edge mode
        self._selection.mode = SelectionMode.EDGE
        self._selection.clear()
        self._selection.add(set(self._path_edges))
        return cmd

    def _on_cancel(self) -> None:
        """Drop the path. The mesh was never changed; nothing pushed to history."""
        print(f"[KNIFE] cancel: {len(self.points)} point(s) discarded")
        self._path = []
        self._steps = []
        self._redo = []
