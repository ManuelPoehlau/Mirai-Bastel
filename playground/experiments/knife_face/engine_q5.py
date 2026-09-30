"""Knife Face Lab — Variant Q5 engine: cross-face segments on top of Variant D.

Q5 is D's session (virtual path, mesh changes only at commit, one History entry,
same residue) plus:

  * a planner (`planner.py`): a click whose target lies outside the last point's
    faces is turned into the ordered visible crossings between them, fixed at
    that click with that click's camera and stored as ordinary path points — the
    commit-time resolver never sees a camera;
  * Blender-like gaps (Artist A-Q1, 2026-09-29): only visible crossings count, the
    visible ones form face-connected *pieces*, every piece is cut, the stretch
    between pieces is skipped. Skipped stretches are `{"kind": "break"}` markers
    in the path: D's resolver assumes consecutive points share a face, so runs are
    never connected across a break;
  * close without commit (A-Q3): a click on the snapped start point of the current
    chain (>= 3 clicked points) ends that chain — resolved *cyclically* at commit
    (probe P8 (c)). The new chain is *seeded* with the closing vertex (Artist play
    test 2026-09-29): the same start-point dict again, behind the break, so the next
    click draws a segment from there while no run is ever resolved across the closed
    loop. One shared dict = one vertex at commit (resolution is keyed by `id`); an
    interior start point has no vertex before commit, so the seeded chain is anchored
    on the vertex the closed chain's cut creates there (see `_resolve_path`);
  * one snap rule: within 14 px of a mesh vertex or of one of the session's own
    clicked points the prospective point jumps onto it;
  * A5 lock off (its reason — hide the missing cross-face cut — is gone here).

Earlier points (Artist decision 2026-09-29): a click on a snapped earlier *boundary* point (vertex or
edge point) of the chain that is not the start is accepted — a segment from the last point to it, through
the planner, appended with the very same dict, and the chain continues from that point. Commit resolves
repeated boundary points to one vertex (`_merge_repeated_points`). An earlier *interior* point is still
rejected: it has no vertex before commit and a second run through it would need a graph, not a polyline
(decision.md, "Task B").

LAB DEFAULTS flagged in decision.md, not decisions: crossings are not snap targets; a segment
along an existing edge is skipped, not refused; an unclosed all-interior chain of
>= 3 points in one face still closes implicitly at commit (D parity).

Path entries: D's point dicts (`vertex` / `edge`+`t` / `face`+`position`), plus
  crossing dicts flagged `"crossing": True` (planner output, not clicked) and
  `{"kind": "break", "reason": "gap" | "edge"}` (skipped stretch inside a chain) /
  `{"kind": "break", "reason": "closed", "cyclic": bool}` (chain end).
The engine never mutates an entry after creating it (snapshots share the dicts).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from core import FaceId, VertexId
from core.mesh import MeshError

from playground.experiments.knife_face.engine import (
    EDGE_MARGIN_PX,
    FaceFrame,
    KnifeFaceCollected,
    Position,
    _proper_cross2,
    _shares_nonadjacent_face,
    segment_in_face,
)
from playground.experiments.knife_face.planner import View, plan_crossings, point_faces, point_position

# Manu, 2026-09-29: the cursor always snaps within this radius of any vertex —
# same radius as the existing vertex pick (H3) and D's close-on-start zone.
SNAP_PX = 14.0
MIN_CLOSE_POINTS = 3
EARLIER_INTERIOR_NOTE = "connecting to an earlier interior point is not supported yet"

_GAP_TEXT = {
    "gap": "over a hole, border or hidden part",
    "edge": "along an existing edge",
}


@dataclass
class Q5Plan:
    """What a click at `target` would do — hover preview and click share it."""

    ok: bool
    reason: str = ""
    entries: list = field(default_factory=list)        # path entries the click appends
    lines: list = field(default_factory=list)          # (pos_a, pos_b, "cut" | "skip") from the last point
    crossings: list = field(default_factory=list)      # positions of the planned crossings
    snap_position: Position | None = None              # vertex / path-point snap highlight
    closing: bool = False
    cyclic: bool = False
    skipped: list = field(default_factory=list)        # human-readable skipped stretches
    message: str = ""


def _is_break(p: dict) -> bool:
    return p["kind"] == "break"


def _is_chain_end(p: dict) -> bool:
    return p["kind"] == "break" and p.get("reason") == "closed"


class KnifeFaceCrossFace(KnifeFaceCollected):
    """Variant Q5 session engine (see module docstring)."""

    history_description = "Knife Face (Cross-Face)"

    def _on_activate(self) -> None:
        super()._on_activate()
        self._view: View | None = None

    def _init_state(self) -> None:
        super()._init_state()  # `_face_cut_lock` exists for the snapshot but is never set in Q5
        self.last_plan: Q5Plan | None = None

    # -- view (camera) --------------------------------------------------------

    def set_view(self, camera, width: int, height: int, *, cache=None, occlusion: bool = True) -> None:
        """Camera for the *next* hover/click. Crossings are computed with the view
        of the click that adds them and stored (discovery §3) — later camera
        changes never touch what is already in the path."""
        self._view = View(camera, width, height, cache, occlusion)

    # -- chain helpers ----------------------------------------------------------

    def _chain_start(self) -> int:
        for i in range(len(self._path) - 1, -1, -1):
            if _is_chain_end(self._path[i]):
                return i + 1
        return 0

    @property
    def chain(self) -> list[dict]:
        """Entries of the current (open) chain, gap breaks included."""
        return list(self._path[self._chain_start():])

    def _chain_points(self) -> list[dict]:
        return [p for p in self._path[self._chain_start():] if not _is_break(p)]

    def _clicked(self) -> list[dict]:
        return [p for p in self._chain_points() if not p.get("crossing")]

    # -- geometry helpers -------------------------------------------------------

    def _pos(self, p: dict) -> Position:
        return point_position(self._mesh, p)

    def _link(self, a: dict, b: dict) -> str | None:
        """How two consecutive points connect: "cut" (a chord inside a shared face),
        "edge" (they lie along an existing edge, or a straight run of edges — nothing to
        cut, Blender skips it) or None (no shared face holds the straight line — a gap,
        or a concave face the line leaves: the planner finds the crossings)."""
        m = self._mesh
        shared = point_faces(m, a) & point_faces(m, b)
        if not shared:
            return None
        ka, kb = a["kind"], b["kind"]
        if ka == "vertex" and kb == "vertex":
            if not _shares_nonadjacent_face(m, a["vertex_id"], b["vertex_id"]):
                return "edge"
        elif ka == "vertex" and kb == "edge":
            if a["vertex_id"] in m.edge_vertices(b["edge_id"]):
                return "edge"
        elif ka == "edge" and kb == "vertex":
            if b["vertex_id"] in m.edge_vertices(a["edge_id"]):
                return "edge"
        elif ka == "edge" and kb == "edge":
            if a["edge_id"] == b["edge_id"]:
                return "edge"
        # Integrity finding R3/R5 (decision.md): sharing a face is not enough — the straight line
        # has to lie inside it. Along a straight run of boundary edges nothing is cut; out of a
        # concave face the line is planned like any cross-face segment.
        pa, pb = self._pos(a), self._pos(b)
        where = {segment_in_face(m, f, pa, pb) for f in shared}
        if "inside" in where:
            return "cut"
        if "boundary" in where:
            return "edge"
        return None

    @staticmethod
    def _same_point(a: dict, b: dict) -> bool:
        """The very same path entry, or two entries on one mesh vertex (a vertex needs no identity)."""
        return a is b or (a["kind"] == b["kind"] == "vertex" and a["vertex_id"] == b["vertex_id"])

    def _vertex_entries(self, vid: VertexId) -> list[dict]:
        """Clicked path entries on mesh vertex `vid` (a planner crossing on a vertex is not a click target)."""
        found = [p for p in self._path
                 if p["kind"] == "vertex" and p["vertex_id"] == vid and not p.get("crossing")]
        start = self._chain_points()[:1]
        found.sort(key=lambda p: 0 if start and p is start[0] else 1)  # chain start first
        return found

    # -- snap -----------------------------------------------------------------

    def snap_target(self, target: dict, sx: float, sy: float) -> dict:
        """Resolve the cursor's pick to the prospective point, applying the snap
        rule for the session's own *clicked* points. Mesh vertices already snap
        through the pick itself (14 px vertex pick); this adds the virtual path
        points (not mesh vertices before commit). The nearer of the two wins.
        Crossings and the chain's last point are not snap targets."""
        v = self._view
        if v is None or not self._path:
            return target
        m = self._mesh
        v.prepare(m)
        last = None
        cs = self._chain_start()
        for i in range(len(self._path) - 1, cs - 1, -1):
            if not _is_break(self._path[i]):
                last = i
                break
        best = None
        for i, p in enumerate(self._path):
            if _is_break(p) or p.get("crossing") or i == last:
                continue
            pos = self._pos(p)
            s = v.p2(pos)
            if s is None:
                continue
            d = math.hypot(s[0] - sx, s[1] - sy)
            if d > SNAP_PX or (best is not None and d >= best[0]):
                continue
            if v.point_hidden(m, pos, point_faces(m, p)):
                continue
            best = (d, i, p)
        if best is None:
            return target
        if target.get("kind") == "vertex":
            vid = target.get("vertex_id")
            if best[2]["kind"] == "vertex" and best[2]["vertex_id"] == vid:
                return target
            vs = v.p2(m.vertex_position(vid)) if m.is_valid_vertex(vid) else None
            if vs is not None and math.hypot(vs[0] - sx, vs[1] - sy) <= best[0]:
                return target
        return {"kind": "path", "index": best[1]}

    # -- planning -----------------------------------------------------------------

    def _validate(self, target: dict) -> str | None:
        kind = target.get("kind") if target else None
        m = self._mesh
        if kind == "vertex":
            vid = target.get("vertex_id")
            return None if vid is not None and m.is_valid_vertex(vid) else "invalid vertex"
        if kind == "edge":
            eid, t = target.get("edge_id"), target.get("t", 0.5)
            return None if eid is not None and m.is_valid_edge(eid) and 0.0 < t < 1.0 else "invalid edge point"
        if kind == "face":
            if target.get("face_id") is None or target.get("position") is None:
                return "invalid face point"
            dist = target.get("distance_px")
            return None if dist is not None and dist >= EDGE_MARGIN_PX else "too close to an edge"
        if kind == "path":
            i = target.get("index")
            ok = isinstance(i, int) and 0 <= i < len(self._path) and not _is_break(self._path[i])
            return None if ok else "invalid path point"
        return "no target"

    def plan(self, target: dict) -> Q5Plan:
        bad = self._validate(target)
        if bad:
            return Q5Plan(False, bad)
        kind = target["kind"]
        chain = self._chain_points()

        existing = None
        if kind == "path":
            existing = self._path[target["index"]]
        elif kind == "vertex":
            hits = self._vertex_entries(target["vertex_id"])
            existing = hits[0] if hits else None
        if existing is not None:
            return self._plan_existing(existing, chain)

        if kind == "vertex":
            new = {"kind": "vertex", "vertex_id": target["vertex_id"]}
        elif kind == "edge":
            new = {"kind": "edge", "edge_id": target["edge_id"], "t": target["t"]}
        else:
            new = {"kind": "face", "face_id": target["face_id"], "position": target["position"]}
        snap = self._pos(new) if kind == "vertex" else None
        if not chain:
            return Q5Plan(True, entries=[new], snap_position=snap, message="pending: chain start")
        return self._plan_segment(chain[-1], new, closing=False, snap=snap)

    def _plan_existing(self, existing: dict, chain: list[dict]) -> Q5Plan:
        """A prospective point that *is* an earlier path point (snapped)."""
        snap = self._pos(existing)
        if not chain:
            return Q5Plan(False, "no chain", snap_position=snap)
        if self._same_point(existing, chain[-1]):
            return Q5Plan(False, "already the last point", snap_position=snap)
        if self._same_point(existing, chain[0]):
            if len(self._clicked()) < MIN_CLOSE_POINTS:
                return Q5Plan(False, f"closing needs at least {MIN_CLOSE_POINTS} points", snap_position=snap)
            return self._plan_segment(chain[-1], chain[0], closing=True, snap=snap)
        if existing["kind"] == "face":
            return Q5Plan(False, EARLIER_INTERIOR_NOTE, snap_position=snap)
        # An earlier boundary point of this chain, or of an already closed chain: connect to it
        # and continue from it. `existing` (not a copy) goes into the path again, so commit
        # resolves both occurrences to one vertex.
        return self._plan_segment(chain[-1], existing, closing=False, snap=snap, earlier=True)

    def _plan_segment(
        self, a: dict, b: dict, *, closing: bool, snap: Position | None, earlier: bool = False,
    ) -> Q5Plan:
        m = self._mesh
        crossings: list[dict] = []
        hidden = 0
        if self._link(a, b) is None:
            if self._view is None:
                return Q5Plan(False, "no camera view — cannot plan a cross-face segment", snap_position=snap)
            res = plan_crossings(self._view, m, a, b)
            crossings, hidden = res.crossings, res.hidden

        nodes = [a] + crossings + [b]
        entries: list[dict] = []
        lines: list[tuple] = []
        skipped: list[str] = []
        crossing_positions: list[Position] = []
        new_segs: list[tuple[dict, dict]] = []
        last = len(nodes) - 1
        for k in range(1, last + 1):
            link = self._link(nodes[k - 1], nodes[k])
            if link == "cut":
                new_segs.append((nodes[k - 1], nodes[k]))
            lines.append((self._pos(nodes[k - 1]), self._pos(nodes[k]), "cut" if link == "cut" else "skip"))
            if link != "cut":
                reason = link or "gap"
                entries.append({"kind": "break", "reason": reason})
                skipped.append(_GAP_TEXT[reason])
            if k == last:
                entries.append(b)  # the clicked target (or the chain start again, on close)
            else:
                crossing = dict(nodes[k], crossing=True)
                entries.append(crossing)
                crossing_positions.append(self._pos(crossing))

        cyclic = False
        if closing:
            cyclic = not any(_is_break(p) for p in entries) and not any(_is_break(p) for p in self.chain)
            if cyclic:
                entries.pop()  # the closing point is the start already: resolved as a cycle at commit
            entries.append({"kind": "break", "reason": "closed", "cyclic": cyclic})
            # Seed of the next chain: the closing vertex (= the chain's start). Same dict on
            # purpose — never a copy — so commit resolves both occurrences to one vertex. With a
            # skipped stretch (no cyclic loop) `b` is also the chain's last point, so "seed from
            # the last point" and "seed from the closing vertex" coincide.
            entries.append(b)

        # Where the new segment crosses a stored cut inside one face: commit makes that one vertex
        # of both cuts — shown as a crossing dot like the planner's.
        meets = self._intersections(new_segs, self._stored_cut_segments())
        crossing_positions.extend(meets)
        parts = [f"{len(crossing_positions) - len(meets)} crossing(s)"]
        if meets:
            parts.append(f"{len(meets)} intersection(s) with earlier cuts")
        if earlier:
            parts.append("connects to an earlier cut point; the next cut continues from it")
        if closing:
            parts.append("closes the chain" if cyclic else "closes the chain (open pieces: a stretch is skipped)")
            parts.append("the next cut continues from the closing vertex")
        if b["kind"] == "face" and not closing and \
                any(p["kind"] != "face" for p in self._chain_points()):
            parts.append("Enter joins the last point to the nearest corner")
        if skipped:
            parts.append("skipped: " + ", ".join(sorted(set(skipped))))
        if hidden:
            parts.append(f"{hidden} hidden crossing(s) not cut")
        return Q5Plan(
            True, entries=entries, lines=lines, crossings=crossing_positions, snap_position=snap,
            closing=closing, cyclic=cyclic, skipped=skipped,
            message=("closed" if closing else "pending") + ": " + "; ".join(parts),
        )

    # -- D interface --------------------------------------------------------------

    def accepts(self, target: dict) -> bool:
        return self.plan(target).ok

    def hover(self, target: dict) -> dict:
        plan = self.plan(target)
        self.last_plan = plan
        return {"valid": plan.ok, "target": target, "path": list(self._path), "plan": plan}

    def click(self, target: dict) -> bool:
        plan = self.plan(target)
        if not plan.ok:
            self.last_message = f"rejected: {plan.reason}"
            return False
        self._push_step()  # one click = one in-session undo step, crossings included
        self._path.extend(plan.entries)
        self._redo_stack.clear()
        self.last_message = plan.message
        return True

    # -- crossing cuts (Artist decision 2026-09-29: intersection vertex, both cuts applied) -----

    def _stored_cut_segments(self) -> list[tuple[dict, dict]]:
        """Consecutive stored points of every chain that are cut (not across a break; a cyclic
        close adds last -> first) — what commit will cut."""
        segs, prev, first = [], None, None
        for p in self._path:
            if _is_chain_end(p):
                if p.get("cyclic") and prev is not None and first is not None and prev is not first:
                    segs.append((prev, first))
                prev = first = None
                continue
            if _is_break(p):
                prev = None
                continue
            if prev is not None and prev is not p:
                segs.append((prev, p))
            if first is None:
                first = p
            prev = p
        return segs

    def _intersections(self, new_segs, old_segs) -> list[Position]:
        """Where a segment of `new_segs` crosses one of `old_segs` inside a face they share — the
        intersection vertices commit will create. Preview only: commit finds them itself by walking
        each run through the faces the earlier runs left behind."""
        m = self._mesh
        frames: dict = {}
        out: list[Position] = []
        for a, b in new_segs:
            fa = point_faces(m, a) & point_faces(m, b)
            pa, pb = self._pos(a), self._pos(b)
            for c, d in old_segs:
                if {id(a), id(b)} & {id(c), id(d)}:
                    continue
                for f in fa & point_faces(m, c) & point_faces(m, d):
                    if f not in frames:
                        try:
                            frames[f] = FaceFrame(m, f)
                        except MeshError:
                            frames[f] = None
                    fr = frames[f]
                    if fr is None:
                        continue
                    a2, b2, c2, d2 = fr.p2(pa), fr.p2(pb), fr.p2(self._pos(c)), fr.p2(self._pos(d))
                    if not _proper_cross2(a2, b2, c2, d2, fr.eps):
                        continue
                    den = (b2[0] - a2[0]) * (d2[1] - c2[1]) - (b2[1] - a2[1]) * (d2[0] - c2[0])
                    t = ((c2[0] - a2[0]) * (d2[1] - c2[1]) - (c2[1] - a2[1]) * (d2[0] - c2[0])) / den
                    out.append(tuple(pa[k] + t * (pb[k] - pa[k]) for k in range(3)))
                    break
        return out

    # -- preview of what is already stored ------------------------------------------

    def preview_stored(self) -> dict:
        """Overlay data for the stored path: cut lines, skipped ("no cut") lines,
        clicked points and crossing dots, as world positions."""
        cut: list[tuple] = []
        skip: list[tuple] = []
        points: list[Position] = []
        crossings: list[Position] = []
        prev = first = None
        pending_skip = None
        first_entry = closed_first = None
        drawn: set[int] = set()
        for p in self._path:
            if _is_chain_end(p):
                if p.get("cyclic") and prev is not None and first is not None:
                    cut.append((prev, first))
                prev = first = pending_skip = None
                closed_first, first_entry = first_entry, None
                continue
            if _is_break(p):
                pending_skip, prev = prev, None
                continue
            pos = self._pos(p)
            if p is not closed_first and id(p) not in drawn:  # a repeated entry (seed, earlier point): one dot
                (crossings if p.get("crossing") else points).append(pos)
            drawn.add(id(p))
            if first_entry is None:
                first_entry = p
            closed_first = None
            if prev is not None:
                cut.append((prev, pos))
            elif pending_skip is not None:
                skip.append((pending_skip, pos))
            pending_skip = None
            prev = pos
            if first is None:
                first = pos
        segs = self._stored_cut_segments()
        for i, sg in enumerate(segs):
            crossings.extend(self._intersections([sg], segs[i + 1:]))
        tail = self._open_tail()
        corners = self._tail_corners(tail) if tail else []
        if corners:
            # What Enter does with a last click inside a face: joined to the nearest corner.
            cut.append((self._pos(tail[-1]), self._mesh.vertex_position(corners[0])))
        return {"cut": cut, "skip": skip, "points": points, "crossings": crossings}

    # -- commit-time resolution -------------------------------------------------------

    def _chains(self) -> list[tuple[list[dict], bool, bool, bool]]:
        """[(entries, closed, cyclic, seeded)] — a chain's entries keep its gap breaks.
        `seeded`: the chain starts with the closing vertex of the chain before it (the
        very same dict). A chain holding nothing but its seed has no cut and is left out."""
        out, cur, prev_first = [], [], None
        for p in self._path:
            if _is_chain_end(p):
                first = next((q for q in cur if not _is_break(q)), None)
                out.append((cur, True, bool(p.get("cyclic")), first is not None and first is prev_first))
                prev_first = first
                cur = []
            else:
                cur.append(p)
        points = [q for q in cur if not _is_break(q)]
        if points and not (len(points) == 1 and points[0] is prev_first):
            out.append((cur, False, False, points[0] is prev_first))
        return out

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

    # -- a cut whose last click lies inside a face (Artist decision 2026-09-30) ----------

    def _tail_corners(self, tail: list[dict]) -> list[VertexId]:
        """Corners of the face the tail's last click lies in, nearest to that click first (ties by
        position): commit joins the tail to the first one it can cut to. The tail's own boundary
        start is no candidate. Read on the session-start mesh (what the Artist clicked on)."""
        m = self._mesh
        last = tail[-1]
        fid = last["face_id"]
        if not m.is_valid_face(fid):
            return []
        start = tail[0]["vertex_id"] if tail[0]["kind"] == "vertex" else None
        pos = last["position"]
        cands = [v for v in m.face_vertices(fid) if v != start]
        return sorted(cands, key=lambda v: (round(math.dist(pos, m.vertex_position(v)), 9),
                                            tuple(m.vertex_position(v))))

    def _open_tail(self) -> list[dict]:
        """The open chain's tail (last boundary point + interior points after it), or []."""
        chunk = []
        for p in self._path[self._chain_start():]:
            chunk = [] if _is_break(p) else chunk + [p]
        return self._runs_of(chunk)[2] if chunk else []

    # -- interior start points shared by a seeded chain ---------------------------------

    def _record_new_vertices(self, points: list[dict], before: set) -> None:
        """Remember which mesh vertex a run / loop created for each interior point, so a
        chain seeded with that point can be anchored on it (positions are unique per
        point: an interior click never lands within 14 px of another one — snap)."""
        new = [v for v in self._mesh.all_vertex_ids() if v not in before]
        for pt in points:
            for v in new:
                if math.dist(self._mesh.vertex_position(v), pt["position"]) < 1e-9:
                    self._interior_vertices[id(pt)] = v
                    break

    @staticmethod
    def _merge_repeated_points(groups: list[list[list[dict]]]) -> tuple[list[list[list[dict]]], int]:
        """One entry per boundary point, one run per segment. Connecting to an earlier point puts
        that point into a run again — usually as the very same dict, but a segment retraced under
        another camera brings fresh crossing dicts on the same edge/t, which resolving separately
        would split twice (zero-length edge). Boundary run ends on the same edge point / vertex are
        replaced by their first dict (`resolved` is keyed by identity), and a straight segment
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
                    pair = frozenset((id(a), id(b)))
                    if a is b or pair in cut:
                        dropped += 1
                        continue
                    cut.add(pair)
                out.append(run)
            result.append(out)
        return result, dropped

    def _apply_run(self, run: list[dict], resolved: dict[int, VertexId]) -> bool:
        interior = run[1:-1]
        before = set(self._mesh.all_vertex_ids()) if interior else set()
        ok = super()._apply_run(run, resolved)
        if ok and interior:
            self._record_new_vertices(interior, before)
        return ok

    def _resolve_closed_loop(self, path: list[dict]) -> str:
        before = set(self._mesh.all_vertex_ids())
        msg = super()._resolve_closed_loop(path)
        self._record_new_vertices(path, before)
        return msg

    def _resolve_path(self) -> None:
        if not self._path:
            self.last_message = "no points"
            return

        self._interior_vertices: dict[int, VertexId] = {}
        runs: list[list[dict]] = []
        seeded_runs: list[list[dict]] = []     # chains anchored on an interior start point: applied last
        anchors: dict[int, tuple[dict, dict]] = {}  # id(interior seed) -> (seed, vertex placeholder)
        loops: list[list[dict]] = []
        tails: list[tuple[list[dict], list[VertexId], bool]] = []   # (tail, corners, seeded)
        notes: list[str] = []
        dropped_lead = dropped_tail = False
        for entries, closed, cyclic, seeded in self._chains():
            target_runs = runs
            if seeded:
                first = next(p for p in entries if not _is_break(p))
                if first["kind"] == "face":
                    # An interior start is no vertex before commit: this chain waits for the
                    # vertex that the closed chain's cut creates at that point. The placeholder
                    # is bound (vertex_id resolved) right before its runs are applied.
                    ph = anchors.setdefault(id(first), (first, {"kind": "vertex", "vertex_id": None}))[1]
                    entries = [ph if p is first else p for p in entries]
                    target_runs = seeded_runs
            chunks, cur = [], []
            for p in entries:
                if _is_break(p):
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
                    notes.append(f"closed shape needs >= 3 points in one face — dropped ({len(pts)} point(s))")
                else:
                    loops.append(pts)
                continue

            if closed and cyclic:
                pts = chunks[0]
                start = next(i for i, p in enumerate(pts) if p["kind"] != "face")
                # Start and end on the same boundary point so the loop resolves with
                # no bridges (probe P8 (c)); the same dict closes it.
                chunks = [pts[start:] + pts[:start] + [pts[start]]]
            for chunk in chunks:
                r, lead, tail = self._runs_of(chunk)
                target_runs.extend(r)
                dropped_lead |= lead
                if tail:
                    # Corners are read now, before any run changes the faces.
                    tails.append((tail, self._tail_corners(tail), target_runs is seeded_runs))

        (runs, seeded_runs), repeats = self._merge_repeated_points([runs, seeded_runs])
        resolved = self._resolve_boundary_points(runs + seeded_runs)
        applied = sum(1 for run in runs if self._apply_run(run, resolved))
        joined = 0

        def join_tails(seeded: bool) -> None:
            # The tail's last click is joined to the nearest corner it can be cut to (Artist
            # decision 2026-09-30); a corner that does not work (the cut would leave the face or
            # cross itself) is taken back like any dropped run and the next one is tried.
            nonlocal joined, dropped_tail
            for tail, corners, is_seeded in tails:
                if is_seeded != seeded:
                    continue
                ends = [{"kind": "vertex", "vertex_id": v} for v in corners]   # kept alive: `resolved` is keyed by id
                before = self._loops_at_point.copy()
                ok = any(self._apply_run(tail + [end], resolved)
                         for end in ends if self._mesh.is_valid_vertex(end["vertex_id"]))
                # A loop reason is a property of the tail, not of each corner tried: counted once, and
                # only if no corner worked.
                tried = self._loops_at_point - before
                self._loops_at_point = before
                if ok:
                    joined += 1
                else:
                    dropped_tail = True
                    if tried:
                        self._loops_at_point[tried.most_common(1)[0][0]] += 1

        join_tails(False)

        parts: list[str] = []
        for pts in loops:
            fid: FaceId = pts[0]["face_id"]
            if not self._mesh.is_valid_face(fid):
                notes.append("closed shape skipped — its face was already cut by another run")
                continue
            parts.append(self._resolve_closed_loop(pts))

        for run in seeded_runs:
            for seed, ph in anchors.values():
                vid = self._interior_vertices.get(id(seed))
                if vid is not None and self._mesh.is_valid_vertex(vid):
                    resolved[id(ph)] = vid
            if self._apply_run(run, resolved):
                applied += 1
        for seed, ph in anchors.values():
            vid = self._interior_vertices.get(id(seed))
            if vid is not None and self._mesh.is_valid_vertex(vid):
                resolved[id(ph)] = vid
        join_tails(True)
        if any(self._interior_vertices.get(id(seed)) is None for seed, _ph in anchors.values()):
            notes.append("continuation from an interior start point dropped (no cut created a vertex there)")

        total = len(runs) + len(seeded_runs) + len(tails)
        applied += joined
        if total:
            parts.insert(0, f"{applied}/{total} cut(s) applied")
        if not total and not loops:
            parts.append("no complete cut")
        if dropped_lead:
            notes.append("leading interior point(s) dropped (no boundary reached before them)")
        if joined:
            notes.append(f"{joined} last point(s) inside a face joined to the nearest corner")
        if dropped_tail:
            notes.append("trailing interior point(s) dropped (no corner of their face could be joined)")
        if repeats:
            notes.append(f"{repeats} repeated segment(s) merged")
        notes.extend(self._loop_at_point_note())
        gaps = sum(1 for p in self._path if _is_break(p) and p.get("reason") in ("gap", "edge"))
        if gaps:
            notes.append(f"{gaps} stretch(es) skipped (hole/border/hidden part or along an existing edge)")
        self.last_message = "; ".join(parts + notes)
