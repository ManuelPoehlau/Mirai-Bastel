"""Knife session tool — a virtual path of explicit points, resolved at commit (AD-017 §1.7).

Moved (not copied) from `playground/topology_tools/knife.py` in WP-06 Slice B7
(session engine PROMOTED, AD-017 DECIDED). Production (`mirai.application`)
and the Playground (`playground/window.py`, `knife` family) share this one
implementation.

WP-KNIFE-01 S2 (M1, AD-017 addendum 2026-10-01 "One Knife S2", PROVISIONAL
until Manu's verdict): the session no longer cuts at every click. It keeps an
ordered path of points — vertex or edge point (`t` along the edge as it was
clicked), each with an explicit point id `pid` — and the mesh is untouched
until commit, where the Knife's resolver (`knife_resolve.resolve_cross_face`,
WP-KNIFE-01 S1) cuts it and `check_commit` guards History. The model is the
Knife Face Lab's Q5 (KEEP 2026-09-30), restricted to vertex/edge targets:
no face-interior points, no planner (cross-face segments stay refused — S3/S4).

Modal tool. Headless-testable (no window code).

Rules (the parity rows P01–P15 / S1–S5 of the promotion discovery,
`tests/test_knife_parity.py`):
- The first click places the start point. Every further click must share a
  face with the last point; the segment between them is
  - a **cut** when its straight chord is valid in a shared face (F2,
    `chord_validity`: inside the face, not along its boundary, not out of a
    concave face);
  - a **skip** when it runs along an existing edge — the neighbour vertex,
    the end of the clicked edge, a second point on the same edge, a straight
    run of boundary edges, or the session's own earlier cut retraced (Artist
    decision AQ1, 2026-10-01 = Q5 behaviour): accepted, nothing cut, the
    chain continues from the new point. Stored as a `{"kind": "break",
    "reason": "edge"}` record before the point, so the resolver never runs a
    cut across it;
  - refused otherwise (no shared face, or the chord leaves every shared face
    — the planner's job, slice S4).
- The same point twice in a row is refused. A click on an earlier own point
  (`{"kind": "point", "pid": ...}` from the own-point snap, or a vertex
  already on the path) puts that very record on the path again: the segment
  to it is cut like any other and the chain continues from it — what the
  real-cut tool did with the vertex it had created there (P05).
- In-session Undo removes the last click's records, Redo puts them back; a
  new click clears the Redo branch (AD-017 DECIDED 2026-09-22).
- Cancel / Esc: the path is dropped; mesh and History were never touched.
- Commit: resolve, check (`check_commit`: a broken result is taken back as a
  whole), push exactly one `MeshStateCommand` ("Knife") if the mesh changed,
  select the cut edges in Edge mode. Nothing changed → no command.
"""

from __future__ import annotations

import itertools

from core.operations.topology import MeshStateCommand
from core.selection import SelectionMode
from ..interaction.tool import Tool
from .chord_validity import chord_valid_in_polygon
from .face_geometry import GEO_EPS, segment_in_face
from .knife_preview import target_position
from .knife_resolve import KnifeResolution, check_commit, is_break, resolve_cross_face


def _faces_of(mesh, p: dict) -> set:
    if p["kind"] == "edge":
        return set(mesh.edge_faces(p["edge_id"]))
    return {f for e in mesh.vertex_edges(p["vertex_id"]) for f in mesh.edge_faces(e)}


class KnifeTool(Tool):
    """Knife modal tool.

    Usage lifecycle:
      knife = KnifeTool()
      knife.activate()
      knife.begin(mesh=..., scene=..., selection=...)
      # during session (the mesh is not changed):
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
    {"kind": "point", "pid"} (one of the session's own points); anything else
    ({"kind": "face"}, {"kind": "outside"}) is refused.
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
        self.last_resolution = None
        self.last_problem = None
        print("[KNIFE] session begin (virtual path, mesh unchanged until commit)")

    # -- session state (read-only) ---------------------------------------------------------

    @property
    def path(self) -> list[dict]:
        """The path records in click order, skip breaks included (copy; the records are shared
        and never changed after the click that adds them) — `knife_resolve`'s record format."""
        return list(self._path)

    @property
    def points(self) -> list[dict]:
        """The placed points in path order; an earlier point clicked again appears again."""
        return [p for p in self._path if not is_break(p)]

    @property
    def last_point(self) -> dict | None:
        """The point the next segment starts from; None before the first click."""
        return next((p for p in reversed(self._path) if not is_break(p)), None)

    @property
    def cut_segments(self) -> list[tuple[dict, dict]]:
        """Consecutive point pairs that commit will cut (not across a skip break)."""
        out, prev = [], None
        for p in self._path:
            if is_break(p):
                prev = None
                continue
            if prev is not None:
                out.append((prev, p))
            prev = p
        return out

    @property
    def path_edges(self) -> list:
        """The edges the committed session cut (the residue); empty before commit."""
        return list(self._path_edges)

    def point_position(self, p: dict):
        """World position of a path record or of a vertex / edge / own-point target; None if unknown."""
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

    def _point_for(self, target: dict | None) -> dict | None:
        """The path record a click on `target` would add: an existing record for an own point or a
        vertex already on the path (the same point id), a new one (no pid yet) otherwise."""
        kind = target.get("kind") if target else None
        m = self._mesh
        if kind == "vertex":
            vid = target.get("vertex_id")
            if vid is None or not m.is_valid_vertex(vid):
                return None
            known = next((p for p in self.points if p["kind"] == "vertex" and p["vertex_id"] == vid), None)
            return known or {"kind": "vertex", "vertex_id": vid}
        if kind == "edge":
            eid, t = target.get("edge_id"), target.get("t", 0.5)
            if eid is None or not m.is_valid_edge(eid) or not (0.0 < t < 1.0):
                return None
            return {"kind": "edge", "edge_id": eid, "t": t}
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
        if "pid" in a and "pid" in b and any(
            {x["pid"], y["pid"]} == {a["pid"], b["pid"]} for x, y in self.cut_segments
        ):
            return "edge"  # retracing the session's own cut (AQ1 applied to the session's edges)
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
        pa, pb = target_position(m, a), target_position(m, b)
        if any(segment_in_face(m, f, pa, pb) == "boundary" for f in shared):
            return "edge"
        return None

    def _plan(self, target: dict | None) -> tuple[list[dict] | None, str]:
        """(records a click on `target` would add, or None; reason / outcome text)."""
        point = self._point_for(target)
        if point is None:
            kind = target.get("kind") if target else None
            return None, f"no vertex/edge target ({kind})"
        last = self.last_point
        if last is None:
            return [point], "start point"
        if self._same(point, last):
            return None, "already the last point"
        link = self._link(last, point)
        if link is None:
            return None, "no shared face holds the cut (cross-face: not yet)"
        if link == "edge":
            return [{"kind": "break", "reason": "edge"}, point], "along an existing edge: skipped"
        return [point], "cut"

    def accepts(self, target: dict) -> bool:
        """Would `click(target)` be accepted? Same rules, no change (the preview gate)."""
        return self._plan(target)[0] is not None

    def hover(self, target: dict) -> dict:
        """Preview info, no change: {"valid": bool, "target", "start": the last point record or None}.

        Deliberately looser than `click()` / `accepts()` (the Playground `knife` family's preview, F2
        addendum): "valid" = a vertex, an edge point or an own point the session knows — a segment
        with no shared face (P10), out of a concave face (R5) or the same point twice (P13) is only
        refused by `click()`. The old exception "edge incident to the start" is gone: since AQ1 such
        a click is accepted (a skip). `Application` previews through `accepts()`."""
        return {"valid": self._point_for(target) is not None, "target": target, "start": self.last_point}

    def click(self, target: dict) -> bool:
        """Add a point. Returns True if accepted, False if refused (no change)."""
        entries, why = self._plan(target)
        if entries is None:
            print(f"[KNIFE] rejected: {why}")
            return False
        for p in entries:
            if not is_break(p) and "pid" not in p:
                p["pid"] = next(self._pids)   # a new point: its id comes with this click
        self._path.extend(entries)
        self._steps.append(len(entries))
        self._redo.clear()
        print(f"[KNIFE] point {entries[-1]['pid']} ({entries[-1]['kind']}): {why}; "
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
        result was broken and taken back (`last_problem` says why)."""
        self._redo.clear()
        self.last_problem = None
        if not self.cut_segments:
            self.last_resolution = None
            print(f"[KNIFE] commit: no cut segment (points={len(self.points)}) -> no history, mesh untouched")
            return None
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
