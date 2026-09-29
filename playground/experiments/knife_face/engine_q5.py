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
    (probe P8 (c)) — and the next click starts a new, independent chain;
  * one snap rule: within 14 px of a mesh vertex or of one of the session's own
    clicked points the prospective point jumps onto it;
  * A5 lock off (its reason — hide the missing cross-face cut — is gone here).

LAB DEFAULTS flagged in decision.md, not decisions: a snapped earlier point that
is not the chain's start is rejected; crossings are not snap targets; a segment
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

from playground.experiments.knife_face.engine import (
    EDGE_MARGIN_PX,
    KnifeFaceCollected,
    Position,
    _shares_nonadjacent_face,
)
from playground.experiments.knife_face.planner import View, plan_crossings, point_faces, point_position

# Manu, 2026-09-29: the cursor always snaps within this radius of any vertex —
# same radius as the existing vertex pick (H3) and D's close-on-start zone.
SNAP_PX = 14.0
MIN_CLOSE_POINTS = 3
EARLIER_POINT_NOTE = "connecting to earlier cut points not supported yet"

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
        """How two consecutive points connect: "cut" (a chord in a shared face),
        "edge" (they lie along an existing edge — nothing to cut, Blender skips
        it) or None (no shared face — a gap)."""
        m = self._mesh
        if not (point_faces(m, a) & point_faces(m, b)):
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
        return "cut"

    def _vertex_entries(self, vid: VertexId) -> list[dict]:
        found = [p for p in self._path if p["kind"] == "vertex" and p["vertex_id"] == vid]
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
            return Q5Plan(False, EARLIER_POINT_NOTE, snap_position=snap)
        if existing is chain[-1]:
            return Q5Plan(False, "already the last point", snap_position=snap)
        if existing is chain[0]:
            if len(self._clicked()) < MIN_CLOSE_POINTS:
                return Q5Plan(False, f"closing needs at least {MIN_CLOSE_POINTS} points", snap_position=snap)
            return self._plan_segment(chain[-1], existing, closing=True, snap=snap)
        return Q5Plan(False, EARLIER_POINT_NOTE, snap_position=snap)

    def _plan_segment(self, a: dict, b: dict, *, closing: bool, snap: Position | None) -> Q5Plan:
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
        last = len(nodes) - 1
        for k in range(1, last + 1):
            link = self._link(nodes[k - 1], nodes[k])
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

        parts = [f"{len(crossing_positions)} crossing(s)"]
        if closing:
            parts.append("closes the chain" if cyclic else "closes the chain (open pieces: a stretch is skipped)")
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
        for p in self._path:
            if _is_chain_end(p):
                if p.get("cyclic") and prev is not None and first is not None:
                    cut.append((prev, first))
                prev = first = pending_skip = None
                continue
            if _is_break(p):
                pending_skip, prev = prev, None
                continue
            pos = self._pos(p)
            (crossings if p.get("crossing") else points).append(pos)
            if prev is not None:
                cut.append((prev, pos))
            elif pending_skip is not None:
                skip.append((pending_skip, pos))
            pending_skip = None
            prev = pos
            if first is None:
                first = pos
        return {"cut": cut, "skip": skip, "points": points, "crossings": crossings}

    # -- commit-time resolution -------------------------------------------------------

    def _chains(self) -> list[tuple[list[dict], bool, bool]]:
        """[(entries, closed, cyclic)] — a chain's entries keep its gap breaks."""
        out, cur = [], []
        for p in self._path:
            if _is_chain_end(p):
                out.append((cur, True, bool(p.get("cyclic"))))
                cur = []
            else:
                cur.append(p)
        if any(not _is_break(p) for p in cur):
            out.append((cur, False, False))
        return out

    @staticmethod
    def _runs_of(chunk: list[dict]) -> tuple[list[list[dict]], bool, bool]:
        """D's run splitting for one break-free stretch: leading interior points
        have no anchor and are dropped (FC5), a dangling tail likewise."""
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
        return runs, lead > 0 and len(chunk) > 1, len(cur) > 1

    def _resolve_path(self) -> None:
        if not self._path:
            self.last_message = "no points"
            return

        runs: list[list[dict]] = []
        loops: list[list[dict]] = []
        notes: list[str] = []
        dropped_lead = dropped_tail = False
        for entries, closed, cyclic in self._chains():
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
                runs.extend(r)
                dropped_lead |= lead
                dropped_tail |= tail

        resolved = self._resolve_boundary_points(runs)
        applied = sum(1 for run in runs if self._apply_run(run, resolved))

        parts: list[str] = []
        if runs:
            parts.append(f"{applied}/{len(runs)} cut(s) applied")
        for pts in loops:
            fid: FaceId = pts[0]["face_id"]
            if not self._mesh.is_valid_face(fid):
                notes.append("closed shape skipped — its face was already cut by another run")
                continue
            parts.append(self._resolve_closed_loop(pts))
        if not runs and not loops:
            parts.append("no complete cut")
        if dropped_lead:
            notes.append("leading interior point(s) dropped (no boundary reached before them)")
        if dropped_tail:
            notes.append("trailing interior point(s) dropped (no boundary reached)")
        gaps = sum(1 for p in self._path if _is_break(p) and p.get("reason") in ("gap", "edge"))
        if gaps:
            notes.append(f"{gaps} stretch(es) skipped (hole/border/hidden part or along an existing edge)")
        self.last_message = "; ".join(parts + notes)
