"""Read-only probe for the symmetric Knife Discovery (AD-SYM-03 slice 6, Type B, 2026-10-08).

Evidence for `docs/research/symmetry/SYMMETRY_KNIFE_DISCOVERY.md`. The question: how can the Production
Knife (`KnifeTool` + `knife_resolve.resolve_cross_face`) run under symmetry as *one* mirrored intent, and
where can it not? The whole Knife rule set (K1-K11) is run through five throwaway coordination methods:

  K-A  mirror the path records (vertex -> partner, edge+t -> partner edge + mapped t, face+position ->
       partner face + `mirror_position`, crossings as stored), append them after a pen lift, **one**
       `resolve_cross_face` call, then snap mirror vertices to `mirror_position(source)` by pid pairs;
  K-B  resolve the source path, then the mirrored path in a **second** call (same mesh, same transaction);
  K-C  resolve the source path alone, then **replay its kept mutations mirrored** (`split_edge`,
       `split_face` with partner ids and mirrored positions; ids of created elements mapped through the
       call results). The kept-call log comes from wrapping the Mesh *instance* (no resolver change);
  K-D  K-A with **mirror-aware tie-breaks**: probe-local copies of `select_bridge`, `close_loop_at_vertex`
       and `CrossFaceResolver._tail_corners` whose position key is reflection-invariant, monkeypatched for
       the call only;
  K-E  K-A, refused by the completeness delta check only (the safety net every method keeps anyway).
  (K-A0, diagnostic only: K-A without the snap, to show where P3 recurs.)

Equivariance criterion (handoff section 2.3), reported per part, never merged:
  E-a  completeness report against the session-start mesh: `delta_check` clean (no surviving complete
       element incomplete, no created element without a partner, no new dead seam id, no new
       self-mirrored face) and `symmetry_state` not worse than before;
  E-b  source side unchanged by the mirroring: the faces on the source side (all vertices x >= 0, one > 0)
       have exactly the positions of resolving the source path alone on a copy;
  E-c  mirror side = exact mirror image: the multiset of all faces equals its own mirror image
       (positions through `mirror_position`, winding reversed); no tolerance - a failure reports the
       largest distance of a created vertex's mirror position to the nearest vertex as a number;
  E-d  one history entry (`MeshStateCommand`); Undo restores mesh and symmetry definition, Redo the result.

Nothing here is a tool, a capability or a proposal for `src/`; nothing in `src/` is edited. Where a method
needs something from the resolver (pid -> created vertex, the kept calls), the probe takes it by wrapping
(`KnifeResolver._run_end_vertex` for the pid report, Mesh instance methods for the call log) and the
Discovery names it as a requirement. In-memory only; no file is written.

Section KC (added 2026-10-09, Type C handoff after review CLAUDE-001; runs last, the K1-K11 / KD tables are
unchanged): **K-C+clip** = the side rule and a path-level clip before K-C (Manu's F1 = C: the cut is clipped
at the seam, only the working side - where the cut starts - is cut and mirrored), a side check on the kept
calls, a strict replay; E-b against the clipped path resolved alone. Re-runs R1, R8, R10, R9 (the review's
scratch probes), K4, K5, K7, K10 and the seam-biased fuzz R7; duplicate-vertex check (N4); the self-partner
edge across the plane (N5). The exit code is 1 when its gate fails (a union, an E-b failure, a duplicate
vertex, an exception, a committed result that is not E ++++), 0 otherwise.

Run from the repo root (Windows and Linux alike; no window, no pyglet):
    python experiments/topology/symmetry_knife_probe.py             # everything (~15-20 min in a Linux container)
    python experiments/topology/symmetry_knife_probe.py --quick     # small fuzz, smoke run (~2 min)
Options: --fuzz N (camera-free fuzz paths per asset, default 500), --seed S (default 20261008),
--only K1,K10,KC,... (run only these sections).
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import io
import math
import os
import platform
import random
import statistics
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "experiments", REPO / "examples", REPO, REPO / "src"):  # src/ first on sys.path
    if str(_p) in sys.path:
        sys.path.remove(str(_p))
    sys.path.insert(0, str(_p))

from core import Mesh, Scene  # noqa: E402
from core.history import HistoryStack  # noqa: E402
from core.mesh import MeshError, SymmetryDefinition  # noqa: E402
from core.operations.topology import MeshStateCommand  # noqa: E402
from mirai.symmetry import SymmetryState, mirror_position, symmetry_state  # noqa: E402
from mirai.symmetry_coordination import (  # noqa: E402
    SymmetryIndex,
    completeness_report,
    delta_check,
    is_exact_plane,
    seam_after_split,
)
from mirai.topology import knife_resolve as kr  # noqa: E402
from mirai.topology.face_geometry import GEO_EPS, FaceFrame, dist3, face_problem  # noqa: E402
from mirai.topology.knife import KnifeTool  # noqa: E402
from mirai.topology.knife_pick import (  # noqa: E402
    EDGE_MARGIN_PX,
    OWN_POINT_SNAP_PX,
    knife_pick,
    snap_own_point,
    space_point,
)
from mirai.topology.knife_planner import VERTEX_TOL_PX  # noqa: E402
from mirai.topology.knife_preview import build_knife_render_data  # noqa: E402
from mirai.viewport.picking import DEPTH_TOLERANCE, face_edge_distance_px, point_occluded  # noqa: E402
from mirai.viewport.picking_cache import PickCache  # noqa: E402
from symmetry_lab.lab_symmetry import derive_seam_edges  # noqa: E402
from topology.knife_integrity_probe import camera_for  # noqa: E402  (fixture reuse: camera framing)
from topology.symmetry_coordination_probe import seam_face_and_edges  # noqa: E402
from topology.symmetry_ops_probe import load  # noqa: E402  (asset + Lab E1/E3 X definition)

W, H = 1280, 800
ORIGIN = (0.0, 0.0, 0.0)
X_NORMAL = (1.0, 0.0, 0.0)
LIFT = {"kind": "break", "reason": "lift"}
STATE_RANK = {SymmetryState.VALID: 0, SymmetryState.PARTIAL: 1, SymmetryState.AMBIGUOUS: 2,
              SymmetryState.VIOLATED: 3, SymmetryState.OFF: 4}


# =============================================================================================
# Output
# =============================================================================================

def section(title: str) -> None:
    print(f"\n{'=' * 100}\n{title}\n{'=' * 100}")


def table(header: list[str], rows: list[list], note: str = "") -> None:
    cells = [[str(c) for c in header]] + [[str(c) for c in r] for r in rows]
    widths = [max(len(r[i]) for r in cells) for i in range(len(header))]
    line = lambda r: "| " + " | ".join(c.ljust(w) for c, w in zip(r, widths)) + " |"  # noqa: E731
    print(line(cells[0]))
    print("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for r in cells[1:]:
        print(line(r))
    if note:
        print(note)


def pct(n: int, d: int) -> str:
    return "-" if d == 0 else f"{100.0 * n / d:.1f}% ({n}/{d})"


def flag(x) -> str:
    return "." if x is None else ("+" if x else "-")


@contextlib.contextmanager
def quiet():
    """`KnifeTool` prints a [KNIFE] trace per click; the probe keeps its own output readable."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


# =============================================================================================
# Meshes (assets through the Discovery probe's `load`, synthetic fixtures here)
# =============================================================================================

_STATES: dict[str, dict] = {}


def x_definition(mesh: Mesh) -> SymmetryDefinition:
    return SymmetryDefinition(ORIGIN, X_NORMAL, derive_seam_edges(mesh, "X"))


def tie_grid(half: int = 3, rows: int = 3, holes: frozenset = frozenset()) -> Mesh:
    """Flat unit-square grid x in [-half, half], y in [0, rows], z = 0, plane x = 0, seam = the x = 0 edges.
    Every centred click in a square is an exact distance tie (probe I's fixture, wider). `holes`: lower-left
    (column, row) of squares left out (pass mirror pairs for a symmetric hole)."""
    m, p = Mesh(), {}
    for r in range(rows + 1):
        for c in range(-half, half + 1):
            p[(c, r)] = m.add_vertex((float(c), float(r), 0.0))
    for r in range(rows):
        for c in range(-half, half):
            if (c, r) not in holes:
                m.add_face([p[(c, r)], p[(c + 1, r)], p[(c + 1, r + 1)], p[(c, r + 1)]])
    m.symmetry_definition = x_definition(m)
    return m


def span_grid() -> Mesh:
    """x in {-1.5, -0.5, 0.5, 1.5}, y in [0, 2]: the middle column of squares spans the plane x = 0 and
    no vertex lies on it (no seam). Every middle face is its own mirror (self-mirrored)."""
    m, p = Mesh(), {}
    xs = (-1.5, -0.5, 0.5, 1.5)
    for r in range(3):
        for i, x in enumerate(xs):
            p[(i, r)] = m.add_vertex((x, float(r), 0.0))
    for r in range(2):
        for i in range(3):
            m.add_face([p[(i, r)], p[(i + 1, r)], p[(i + 1, r + 1)], p[(i, r + 1)]])
    m.symmetry_definition = x_definition(m)
    return m


def hexagon_grid() -> Mesh:
    """`tie_grid(2, 3)` with the middle seam edge (0,1)-(0,2) dissolved: one hexagon spanning the plane,
    whose two plane vertices (0,1), (0,2) are non-adjacent in it and stay seam vertices (each is still the
    end of a live seam edge). The dead seam id is dropped from the definition."""
    m = tie_grid(2, 3)
    pos = {m.vertex_position(v): v for v in m.all_vertex_ids()}
    e = kr.find_edge(m, pos[(0.0, 1.0, 0.0)], pos[(0.0, 2.0, 0.0)])
    m.dissolve_edges([e], cleanup=False)
    d = m.symmetry_definition
    m.symmetry_definition = SymmetryDefinition(d.plane_point, d.plane_normal,
                                               frozenset(x for x in d.seam_edges if m.is_valid_edge(x)))
    return m


FIXTURES = {
    "tie_grid": lambda: tie_grid(),
    "hole_grid": lambda: tie_grid(3, 3, frozenset({(1, 1), (-2, 1)})),
    "span_grid": span_grid,
    "hexagon_grid": hexagon_grid,
}


def start_state(name: str) -> dict:
    """Session-start state of an asset (X definition, Lab E1/E3) or fixture; loaded once, copied per run."""
    if name not in _STATES:
        mesh = FIXTURES[name]() if name in FIXTURES else load(name).mesh
        _STATES[name] = mesh.export_state()
    return _STATES[name]


def fresh(name: str) -> Mesh:
    return Mesh.from_state(start_state(name))


# =============================================================================================
# Geometry helpers
# =============================================================================================

def sd(p) -> float:
    """Signed distance to the plane x = 0 (exact)."""
    return p[0]


def mirror(p) -> tuple:
    return tuple(mirror_position(tuple(p), ORIGIN, X_NORMAL))


def vpos(mesh, v):
    return mesh.vertex_position(v)


def face_class(pts) -> str:
    xs = [p[0] for p in pts]
    if min(xs) >= 0.0 and max(xs) > 0.0:
        return "+"
    if max(xs) <= 0.0 and min(xs) < 0.0:
        return "-"
    if all(x == 0.0 for x in xs):
        return "0"
    return "span"


def canon_poly(pts) -> tuple:
    i = min(range(len(pts)), key=lambda k: pts[k])
    return tuple(pts[i:] + pts[:i])


def mirror_canon(c) -> tuple:
    return canon_poly([mirror(p) for p in reversed(c)])


def canon_faces(mesh) -> list[tuple[str, tuple]]:
    out = []
    for f in mesh.all_face_ids():
        pts = [tuple(mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
        out.append((face_class(pts), canon_poly(pts)))
    return out


def plus_faces(mesh, strict: bool = False) -> list:
    """Faces on the +X side: every vertex x > 0 (`strict`) or x >= 0 with one > 0."""
    out = []
    for f in sorted(mesh.all_face_ids()):
        xs = [vpos(mesh, v)[0] for v in mesh.face_vertices(f)]
        if (min(xs) > 0.0) if strict else (min(xs) >= 0.0 and max(xs) > 0.0):
            out.append(f)
    return out


def centroid(mesh, f):
    pts = [vpos(mesh, v) for v in mesh.face_vertices(f)]
    return tuple(sum(p[k] for p in pts) / len(pts) for k in range(3))


def lerp(a, b, t):
    return tuple(a[k] + t * (b[k] - a[k]) for k in range(3))


def edge_point(mesh, e, t):
    a, b = mesh.edge_vertices(e)
    return lerp(vpos(mesh, a), vpos(mesh, b), t)


def seam_vertices(mesh) -> set:
    d = mesh.symmetry_definition
    return {v for e in d.seam_edges if mesh.is_valid_edge(e) for v in mesh.edge_vertices(e)}


def duplicates(mesh) -> tuple[int, int]:
    """(vertex pairs at identical positions, pairs closer than 1e-9 but not identical)."""
    pts = sorted((tuple(vpos(mesh, v)), v) for v in mesh.all_vertex_ids())
    same = near = 0
    for (p, _), (q, _) in zip(pts, pts[1:]):
        if p == q:
            same += 1
        elif math.dist(p, q) < 1e-9:
            near += 1
    return same, near


# =============================================================================================
# Sessions: the Production KnifeTool's click rules produce every path (camera-free unless a view is given)
# =============================================================================================

def T_v(v):
    return {"kind": "vertex", "vertex_id": v}


def T_e(e, t):
    return {"kind": "edge", "edge_id": e, "t": t}


def T_f(f, pos):
    # `distance_px` is the click's screen clearance (a pick rule, 9 px); headless sessions pass a value
    # above the margin - whether a point is far enough from an edge on *screen* is K6's question.
    return {"kind": "face", "face_id": f, "position": tuple(pos), "distance_px": 100.0}


def T_p(pid):
    return {"kind": "point", "pid": pid}


def new_knife(mesh, view=None) -> KnifeTool:
    scene = Scene()
    scene.mesh = mesh
    knife = KnifeTool()
    with quiet():
        knife.activate()
        knife.begin(mesh=mesh, scene=scene, selection=scene.selection)
    if view is not None:
        knife.set_view(*view)
    return knife


def play(mesh, actions, view=None) -> tuple[KnifeTool, list[bool]]:
    """Run `actions` = [("click", target) | ("lift",) | ("finish",) | ("undo",) | ("redo",)] on a fresh
    session; returns the tool (not committed) and the acceptance of each action."""
    knife = new_knife(mesh, view)
    accepted = []
    with quiet():
        for act in actions:
            if act[0] == "click":
                accepted.append(knife.click(act[1]))
            elif act[0] == "lift":
                accepted.append(knife.lift())
            elif act[0] == "finish":
                accepted.append(knife.finish_chain())
            elif act[0] == "undo":
                accepted.append(knife.undo_step())
            elif act[0] == "redo":
                accepted.append(knife.redo_step())
    return knife, accepted


def resolver_path(knife) -> list[dict]:
    """What `KnifeTool._on_commit` hands the resolver: the path without points in space."""
    return [p for p in knife.path if p["kind"] != "space"]


# =============================================================================================
# Mirroring the path records (K-A, K-B, K-D)
# =============================================================================================

class Unmirrorable(Exception):
    """A record, call or element has no partner: the method refuses (D-strict, INV-5)."""


class Mirror:
    """Partners on the session-start mesh (`SymmetryIndex`, indexed; taken as plain maps before anything is
    cut, so they stay readable after the source cut) and the record mirroring rule."""

    def __init__(self, mesh):
        self.mesh = mesh
        self.index = SymmetryIndex(mesh)
        self.vp = {v: self.index.vertex_partner(v) for v in mesh.all_vertex_ids()}
        self.ep = {e: self.index.edge_partner(e) for e in mesh.all_edge_ids()}
        self.fp = {f: self.index.face_partner(f) for f in mesh.all_face_ids()}
        self.ends = {e: mesh.edge_vertices(e) for e in mesh.all_edge_ids()}

    def record(self, p: dict, memo: dict) -> dict:
        if p["kind"] == "break":
            return dict(p)
        if p["pid"] in memo:
            return memo[p["pid"]]          # the same point (a seed, an earlier point) -> the same record
        q = dict(p)
        q["pid"] = ("m", p["pid"])
        kind = p["kind"]
        if kind == "vertex":
            q["vertex_id"] = self.vp.get(p["vertex_id"])
            if q["vertex_id"] is None:
                raise Unmirrorable("vertex without partner")
        elif kind == "edge":
            e2 = self.ep.get(p["edge_id"])
            if e2 is None:
                raise Unmirrorable("edge without partner")
            a, _b = self.ends[p["edge_id"]]
            same = self.ends[e2][0] == self.vp.get(a)
            q["edge_id"], q["t"] = e2, (p["t"] if same else 1.0 - p["t"])
        elif kind == "face":
            f2 = self.fp.get(p["face_id"])
            if f2 is None:
                raise Unmirrorable("face without partner")
            q["face_id"], q["position"] = f2, mirror(p["position"])
        elif kind == "space":
            q["position"] = mirror(p["position"])
        memo[p["pid"]] = q
        return q

    def path(self, path: list[dict]) -> list[dict]:
        memo: dict = {}
        return [self.record(p, memo) for p in path]


# =============================================================================================
# Instrumentation (probe only; the resolver itself is not edited)
# =============================================================================================

@contextlib.contextmanager
def pid_report(sink: dict):
    """pid -> the vertex the resolver resolved it to (what AD-SYM-03 item 4 calls the slice-6 report)."""
    orig = kr.KnifeResolver._run_end_vertex

    def wrapped(self, p, resolved):
        v = orig(self, p, resolved)
        if v is not None:
            sink[p["pid"]] = v
        return v

    kr.KnifeResolver._run_end_vertex = wrapped
    try:
        yield
    finally:
        kr.KnifeResolver._run_end_vertex = orig


class KeptLog:
    """Kept-call log on one Mesh instance: every `split_edge` / `split_face` the resolver makes, minus the
    calls a `load_state` rollback took back (each `export_state` marks the log length; a `load_state` of
    that very state truncates the log to the mark; an unknown state - the session start - empties it)."""

    def __init__(self, mesh):
        self.mesh = mesh
        self.calls: list[tuple] = []
        self._marks: dict[int, tuple[int, dict]] = {}

    def __enter__(self):
        m = self.mesh
        m.split_edge = self._split_edge
        m.split_face = self._split_face
        m.export_state = self._export_state
        m.load_state = self._load_state
        return self

    def __exit__(self, *exc):
        for name in ("split_edge", "split_face", "export_state", "load_state"):
            self.mesh.__dict__.pop(name, None)
        return False

    def _split_edge(self, edge_id, t=0.5):
        ends = self.mesh.edge_vertices(edge_id)
        result = Mesh.split_edge(self.mesh, edge_id, t)
        self.calls.append(("split_edge", edge_id, ends, t, result, tuple(self.mesh.vertex_position(result[0]))))
        return result

    def _split_face(self, face_id, v_a, v_b, positions=()):
        positions = [tuple(p) for p in positions]
        result = Mesh.split_face(self.mesh, face_id, v_a, v_b, positions)
        sides = (tuple(self.mesh.face_vertices(result[2])), tuple(self.mesh.face_vertices(result[3])))
        self.calls.append(("split_face", face_id, v_a, v_b, positions, result, sides))
        return result

    def _export_state(self):
        state = Mesh.export_state(self.mesh)
        self._marks[id(state)] = (len(self.calls), state)
        return state

    def _load_state(self, state):
        mark = self._marks.get(id(state))
        keep = mark[0] if mark is not None and mark[1] is state else 0
        del self.calls[keep:]
        Mesh.load_state(self.mesh, state)


def apply_s1(mesh, calls) -> int:
    """Seam rule S1 (`seam_after_split`, src) for every kept split of a (current) seam edge, in order."""
    d = mesh.symmetry_definition
    n = 0
    for c in calls:
        if c[0] == "split_edge" and c[1] in d.seam_edges:
            d = seam_after_split(d, {c[1]: (c[4][1], c[4][2])})
            n += 1
    mesh.symmetry_definition = d
    return n


def snap_pairs(mesh, pairs, pid_vertex) -> tuple[int, int]:
    """Set every mirror vertex of a (source pid, mirror pid) pair to mirror_position(source vertex).
    Returns (pairs moved, pairs seen)."""
    moved = seen = 0
    for sp, mp in pairs:
        vs, vm = pid_vertex.get(sp), pid_vertex.get(mp)
        if vs is None or vm is None or vs == vm:
            continue
        if not (mesh.is_valid_vertex(vs) and mesh.is_valid_vertex(vm)):
            continue
        seen += 1
        target = mirror(vpos(mesh, vs))
        if tuple(vpos(mesh, vm)) != target:
            mesh.set_vertex_position(vm, target)
            moved += 1
    return moved, seen


# =============================================================================================
# K-D: mirror-aware tie-breaks (probe-local copies; the key is reflection-invariant)
# =============================================================================================

_KD = {"plane": None, "zero_side": 0}


def _kd_side(points) -> int:
    if _KD["plane"] is None:
        return 1
    o, n = _KD["plane"]
    total = sum(sum((p[k] - o[k]) * n[k] for k in range(3)) for p in points)
    return (total > 0) - (total < 0)


def _kd_key(p, s: int) -> tuple:
    """The tie-break position: on the normal's side (or with no plane) the position itself, on the other
    side its mirror image, so a candidate and its mirror image get the same key."""
    if _KD["plane"] is None or s >= 0:
        return tuple(p)
    return tuple(mirror_position(tuple(p), *_KD["plane"]))


def _kd_ref_side(mesh, boundary, extra) -> int:
    s = _kd_side([mesh.vertex_position(v) for v in boundary]) or _kd_side(extra)
    if s == 0 and _KD["plane"] is not None:
        _KD["zero_side"] += 1       # self-symmetric input: no side to read the tie from
    return s


def select_bridge_kd(mesh, boundary, loop_positions):
    """`knife_resolve.select_bridge` (lines 161-197) with `_kd_key` instead of `tuple(...)`."""
    s = _kd_ref_side(mesh, boundary, loop_positions)
    k = len(loop_positions)
    candidates = []
    for li, pos in enumerate(loop_positions):
        best = None
        for bv in boundary:
            bpos = mesh.vertex_position(bv)
            key = (round(dist3(pos, bpos), kr._TIE_DIGITS), _kd_key(bpos, s))
            if best is None or key < best[0]:
                best = (key, bv)
        candidates.append((best[0][0], _kd_key(pos, s), best[0][1], li, best[1]))
    candidates.sort(key=lambda c: c[:4])
    i1, bv1 = candidates[0][3], candidates[0][4]
    for _dist, _pos, _bpos, li, bv in candidates[1:]:
        if bv == bv1:
            continue
        if k > 3 and (li - i1) % k in (1, k - 1):
            continue
        return i1, bv1, li, bv
    raise MeshError("select_bridge: no valid second bridge point (lab default rule)")


def close_loop_at_vertex_kd(mesh, face_id, x, loop_positions, outside=None):
    """`knife_resolve.close_loop_at_vertex` (lines 248-308) with `_kd_key` in the candidate key."""
    m = len(loop_positions)
    if m < 2:
        raise MeshError("close_loop_at_vertex: a loop needs >= 2 points besides its vertex")
    boundary = mesh.face_vertices(face_id)
    if x not in boundary:
        raise MeshError("close_loop_at_vertex: x must be on face_id's boundary")
    s = _kd_ref_side(mesh, boundary, loop_positions)
    parent_normal = FaceFrame(mesh, face_id).normal
    i = boundary.index(x)
    outer = boundary[i:] + boundary[:i]
    n = len(outer)
    along = kr.loop_matches_winding([mesh.vertex_position(x)] + list(loop_positions),
                                    [mesh.vertex_position(v) for v in boundary])
    cj = (lambda j: j) if along else (lambda j: m - 1 - j)
    canon_positions = [loop_positions[cj(j)] for j in range(m)]
    candidates = []
    for j, pc in enumerate(canon_positions):
        for bi in range(1, n):
            pb = mesh.vertex_position(outer[bi])
            first = 0 if outside is None or outer[bi] in outside else 1
            candidates.append((first, round(dist3(pc, pb), kr._TIE_DIGITS), _kd_key(pc, s), _kd_key(pb, s), j, bi))
    candidates.sort(key=lambda c: c[:4])
    base = mesh.export_state()
    for *_key, j, bi in candidates:
        jc = cj(j)
        try:
            vs1, _e1, g1, g2 = mesh.split_face(face_id, x, outer[bi], loop_positions[:jc + 1])
            host = g1 if kr._walks(mesh, g1, x, vs1[0]) == along else g2
            ring_1 = g2 if host == g1 else g1
            vs2, _e2, h1, h2 = mesh.split_face(host, vs1[-1], x, loop_positions[jc + 1:])
            loop_vs = vs1 + vs2
            loop_set = {x, *loop_vs}
            f_loop = h1 if set(mesh.face_vertices(h1)) == loop_set else h2
            ring = [h2 if f_loop == h1 else h1, ring_1]
            ok = all(face_problem(mesh, f) is None and kr.v_dot(FaceFrame(mesh, f).normal, parent_normal) > 0.0
                     for f in (f_loop, *ring))
        except MeshError:
            ok = False
        if ok:
            chain = [x] + loop_vs + [x]
            return loop_vs, f_loop, ring, [kr.find_edge(mesh, u, v) for u, v in zip(chain, chain[1:])]
        mesh.load_state(base)
    raise MeshError("close_loop_at_vertex: no bridge fits")


def _tail_corners_kd(self, tail):
    """`CrossFaceResolver._tail_corners` (lines 930-943) with `_kd_key`."""
    m = self.mesh
    last = tail[-1]
    fid = last["face_id"]
    if not m.is_valid_face(fid):
        return []
    start = tail[0]["vertex_id"] if tail[0]["kind"] == "vertex" else None
    pos = last["position"]
    s = _kd_ref_side(m, m.face_vertices(fid), [pos])
    cands = [v for v in m.face_vertices(fid) if v != start]
    return sorted(cands, key=lambda v: (round(math.dist(pos, m.vertex_position(v)), 9),
                                        _kd_key(m.vertex_position(v), s)))


@contextlib.contextmanager
def kd_tiebreaks(plane):
    """Install the K-D keys for the duration of one resolve. `plane=None`: the non-symmetric Knife."""
    saved = (kr.select_bridge, kr.close_loop_at_vertex, kr.CrossFaceResolver._tail_corners, _KD["plane"])
    kr.select_bridge, kr.close_loop_at_vertex = select_bridge_kd, close_loop_at_vertex_kd
    kr.CrossFaceResolver._tail_corners = _tail_corners_kd
    _KD["plane"] = plane
    try:
        yield
    finally:
        kr.select_bridge, kr.close_loop_at_vertex, kr.CrossFaceResolver._tail_corners, _KD["plane"] = saved


# =============================================================================================
# K9: which tie-break / order site decided (counting copies; results come from the originals)
# =============================================================================================

TIES: collections.Counter = collections.Counter()


@contextlib.contextmanager
def tie_counters():
    """Counts, per resolver site, the calls whose result was decided by a tie-break (equal rounded
    distance / equal tilt between the deciding candidates). Results always come from the originals."""
    o_sb, o_cl, o_tc, o_step = kr.select_bridge, kr.close_loop_at_vertex, kr.CrossFaceResolver._tail_corners, \
        kr.KnifeResolver._step_from

    def sb(mesh, boundary, loop_positions):
        TIES["select_bridge calls"] += 1
        cands = []
        near = exact = False
        for pos in loop_positions:
            ds = sorted(dist3(pos, mesh.vertex_position(bv)) for bv in boundary)
            if round(ds[0], kr._TIE_DIGITS) == round(ds[1], kr._TIE_DIGITS):
                exact |= ds[0] == ds[1]
                near |= ds[0] != ds[1]
            cands.append(round(ds[0], kr._TIE_DIGITS))
        cands.sort()
        if len(cands) > 1 and cands[0] == cands[1]:
            TIES["select_bridge: first bridge point decided by position"] += 1
        if exact:
            TIES["select_bridge: nearest corner decided by position (exact tie)"] += 1
        if near:
            TIES["select_bridge: near-tie made a tie by round(., 9)"] += 1
        return o_sb(mesh, boundary, loop_positions)

    def cl(mesh, face_id, x, loop_positions, outside=None):
        TIES["close_loop_at_vertex calls"] += 1
        boundary = mesh.face_vertices(face_id)
        i = boundary.index(x) if x in boundary else 0
        outer = boundary[i:] + boundary[:i]
        keys = sorted((0 if outside is None or outer[bi] in outside else 1,
                       round(dist3(pc, mesh.vertex_position(outer[bi])), kr._TIE_DIGITS))
                      for pc in loop_positions for bi in range(1, len(outer)))
        if len(keys) > 1 and keys[0] == keys[1]:
            TIES["close_loop_at_vertex: bridge decided by position"] += 1
        return o_cl(mesh, face_id, x, loop_positions, outside)

    def tc(self, tail):
        TIES["_tail_corners calls"] += 1
        out = o_tc(self, tail)
        if len(out) > 1:
            pos = tail[-1]["position"]
            d0, d1 = (round(math.dist(pos, self.mesh.vertex_position(v)), 9) for v in out[:2])
            if d0 == d1:
                TIES["_tail_corners: nearest corner decided by position"] += 1
        return out

    def step(self, p, target, root):
        TIES["_step_from calls"] += 1
        m = self.mesh
        pp = m.vertex_position(p)
        dist = dist3(pp, target)
        tilts = []
        if dist > GEO_EPS:
            for f in {f for e in m.vertex_edges(p) for f in m.edge_faces(e)}:
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
                nxt, prv = fr.pts2[(i + 1) % k], fr.pts2[i - 1]
                e1 = (nxt[0] - p2[0], nxt[1] - p2[1])
                e2 = (prv[0] - p2[0], prv[1] - p2[1])

                def angle(w):
                    return math.atan2(e1[0] * w[1] - e1[1] * w[0], e1[0] * w[0] + e1[1] * w[1]) % (2 * math.pi)

                a_d, a_e2 = angle(d2), angle(e2)
                if a_d < kr._ANGLE_EPS or a_d > 2 * math.pi - kr._ANGLE_EPS or abs(a_d - a_e2) < kr._ANGLE_EPS \
                        or a_d < a_e2:
                    tilts.append(fr.height(target) / dist)
        tilts.sort()
        if len(tilts) > 1 and tilts[1] < tilts[0] + GEO_EPS:
            TIES["_step_from: face chosen by FaceId order (tilt tie)"] += 1
        return o_step(self, p, target, root)

    kr.select_bridge, kr.close_loop_at_vertex = sb, cl
    kr.CrossFaceResolver._tail_corners = tc
    kr.KnifeResolver._step_from = step
    try:
        yield
    finally:
        kr.select_bridge, kr.close_loop_at_vertex = o_sb, o_cl
        kr.CrossFaceResolver._tail_corners = o_tc
        kr.KnifeResolver._step_from = o_step


# =============================================================================================
# K-C: replay the kept mutations mirrored
# =============================================================================================

def replay_mirrored(mesh, calls, mir: Mirror, strict: bool = False, crossed_n5: bool = False) -> int:
    """Apply the mirror of every kept call. Original elements map through the session-start index,
    created ones through the call results (vertex lists in path order, faces by vertex sets). A seam edge
    is its own partner and is not split again (S1 handles it). Returns the number of replayed calls.

    `strict` (K-C+clip, review CLAUDE-001 N5 / Q4 item 6; off for the K-C rows of K1-K11, which stay as
    run on 2026-10-08): a self-partner edge whose ends are not both on the plane (it crosses the plane, so
    it lies only in self-mirrored faces) is refused instead of mapping its halves to themselves, and a
    kept call of any kind other than `split_edge` / `split_face` is refused (fail-closed). `crossed_n5`
    (the N5 measurement only): such an edge split on the plane maps its halves crossed instead."""
    vmap: dict = {}
    emap: dict = {}
    fmap: dict = {}

    def mv(v):
        w = vmap[v] if v in vmap else mir.vp.get(v)
        if w is None:
            raise Unmirrorable("vertex without partner")
        return w

    def me(e):
        w = emap[e] if e in emap else mir.ep.get(e)
        if w is None:
            raise Unmirrorable("edge without partner")
        return w

    def mf(f):
        w = fmap[f] if f in fmap else mir.fp.get(f)
        if w is None:
            raise Unmirrorable("face without partner")
        return w

    n = 0
    for c in calls:
        if c[0] == "split_edge":
            _op, eid, (a, b), _t, (v, ea, eb), p = c
            e2 = me(eid)
            if e2 == eid:
                crosses = vpos(mesh, a)[0] != 0.0 or vpos(mesh, b)[0] != 0.0
                if strict and crosses:
                    raise Unmirrorable("self-mirrored edge crossing the plane (N5)")
                if p[0] != 0.0:
                    raise Unmirrorable("self-mirrored edge split off the plane")
                vmap[v], emap[ea], emap[eb] = v, ea, eb
                if crossed_n5 and crosses:
                    emap[ea], emap[eb] = eb, ea     # the half at `a` mirrors onto the half at `b` = partner(a)
                continue
            a2 = mv(a)
            mv(b)                       # both ends need a partner (raises otherwise)
            if not mesh.is_valid_edge(e2):
                raise Unmirrorable("mirror edge already cut by the source (the path reaches the other side)")
            try:
                v2, x1, x2 = Mesh.split_edge(mesh, e2, 0.5)
            except (MeshError, KeyError) as exc:
                raise Unmirrorable(f"mirror edge gone ({type(exc).__name__})") from None
            mesh.set_vertex_position(v2, mirror(p))
            vmap[v] = v2
            first_is_a = set(mesh.edge_vertices(x1)) == {a2, v2}
            emap[ea], emap[eb] = (x1, x2) if first_is_a else (x2, x1)
            n += 1
        elif strict and c[0] != "split_face":
            raise Unmirrorable(f"unknown kept call {c[0]!r} (fail-closed)")
        else:
            _op, fid, va, vb, positions, (nvs, nes, f1, f2), (vs1, vs2) = c
            g = mf(fid)
            if g == fid:
                raise Unmirrorable("cut inside a self-mirrored face")
            if not mesh.is_valid_face(g):
                raise Unmirrorable("mirror face already cut by the source (the path reaches the other side)")
            try:
                nv2, ne2, g1, g2 = Mesh.split_face(mesh, g, mv(va), mv(vb), [mirror(p) for p in positions])
            except (MeshError, KeyError) as exc:
                raise Unmirrorable(f"mirror face cut refused ({str(exc)[:40]})") from None
            vmap.update(zip(nvs, nv2))
            emap.update(zip(nes, ne2))
            # Match the two halves by inclusion, not equality: a seam split the source made *after* this
            # call already put its (self-mirrored) vertex into the mirror face too, so a mirror half can hold
            # plane vertices the recorded half did not have yet.
            c1 = {mv(v) for v in vs1}
            c2 = {mv(v) for v in vs2}
            h1, h2 = set(mesh.face_vertices(g1)), set(mesh.face_vertices(g2))
            straight, crossed = c1 <= h1 and c2 <= h2, c1 <= h2 and c2 <= h1
            if straight == crossed:
                raise Unmirrorable("mirror halves not distinguishable")
            fmap[f1], fmap[f2] = (g1, g2) if straight else (g2, g1)
            n += 1
    return n


# =============================================================================================
# The methods and the evaluation
# =============================================================================================

@dataclass
class Res:
    method: str
    status: str = "ok"                 # ok | nothing | refused: .. | rolled back: .. | exception: ..
    ea: bool | None = None
    eb: bool | None = None
    ec: bool | None = None
    ed: bool | None = None
    ms: float = 0.0                    # mirroring + resolve(s) + snap + S1 + commit check
    report_ms: float = 0.0             # the two completeness reports + delta (E-a), as a coordinator runs it
    snapped: int = 0
    snap_seen: int = 0
    maxdev: float = 0.0
    ec_kind: str = ""                  # when E-c fails: "conn" (dev 0: same points, other edges), "float", "geom"
    mesh: Mesh | None = None
    info: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def flags(self) -> str:
        return "".join(flag(x) for x in (self.ea, self.eb, self.ec, self.ed))


class Session:
    """One source path on a session-start state, with its one-sided reference (E-b)."""

    def __init__(self, name: str, path: list[dict], state: dict | None = None, label: str = ""):
        self.name = name
        self.state = state if state is not None else start_state(name)
        self.path = path
        self.label = label
        ref = Mesh.from_state(self.state)
        self.ref_res = kr.resolve_cross_face(ref, path, self.state)
        check = kr.check_commit(ref, self.state)
        self.ref_ok = check.after_state is not None
        self.ref_problem = check.problem
        self.ref_plus = sorted(c for cls, c in canon_faces(ref) if cls == "+") if self.ref_ok else None
        self.ref_mesh = ref
        base = Mesh.from_state(self.state)
        self.base_report = completeness_report(base)
        self.base_state_sym = symmetry_state(base)


def run(method: str, s: Session, *, mirrored_path: list[dict] | None = None, pairs=None) -> Res:
    """Run one method on session `s` and evaluate E-a..E-d. `mirrored_path`: K4 (ii) - a re-planned
    mirror path instead of the mirrored records (K-A shape); `pairs` then names the (source pid, mirror pid)
    pairs of the clicked points the snap may use (crossings of a re-planned path have no source pid)."""
    r = Res(method)
    mesh = Mesh.from_state(s.state)
    t0 = time.perf_counter()
    try:
        mir = Mirror(mesh)
        sink: dict = {}
        if method in ("K-A", "K-A0", "K-D", "K-E"):
            mpath = mirrored_path if mirrored_path is not None else mir.path(s.path)
            full = s.path + [LIFT] + mpath
            plane = (ORIGIN, X_NORMAL) if method == "K-D" else None
            with KeptLog(mesh) as log, pid_report(sink), (kd_tiebreaks(plane) if method == "K-D"
                                                          else contextlib.nullcontext()):
                resolver = kr.CrossFaceResolver(mesh, s.state)
                resolver.resolve(full)
            sink.update(resolver.interior_vertices)
            if method != "K-A0":
                if pairs is None:
                    pairs = [(p["pid"], ("m", p["pid"])) for p in s.path if p["kind"] != "break"]
                r.snapped, r.snap_seen = snap_pairs(mesh, pairs, sink)
            apply_s1(mesh, log.calls)
        elif method == "K-B":
            mpath = mir.path(s.path)
            with KeptLog(mesh) as log, pid_report(sink):
                r1 = kr.CrossFaceResolver(mesh, s.state)
                r1.resolve(s.path)
                r2 = kr.CrossFaceResolver(mesh, s.state)
                r2.resolve(mpath)
            sink.update(r1.interior_vertices)
            sink.update(r2.interior_vertices)
            pairs = [(p["pid"], ("m", p["pid"])) for p in s.path if p["kind"] != "break"]
            r.snapped, r.snap_seen = snap_pairs(mesh, pairs, sink)
            apply_s1(mesh, log.calls)
        elif method == "K-C":
            with KeptLog(mesh) as log:
                kr.CrossFaceResolver(mesh, s.state).resolve(s.path)
            kept = list(log.calls)
            r.info["replayed"] = replay_mirrored(mesh, kept, mir)
            apply_s1(mesh, kept)
        else:
            raise ValueError(method)
        check = kr.check_commit(mesh, s.state)
    except Unmirrorable as exc:
        r.status = f"refused: {exc}"
        r.ms = 1000 * (time.perf_counter() - t0)
        return r
    except Exception as exc:  # noqa: BLE001 - a probe counts exceptions, it does not hide them
        r.status = f"exception: {type(exc).__name__}: {str(exc)[:60]}"
        r.info["trace"] = traceback.format_exc()
        r.ms = 1000 * (time.perf_counter() - t0)
        return r
    r.ms = 1000 * (time.perf_counter() - t0)
    if check.rolled_back:
        r.status = f"rolled back: {check.problem}"
        return r
    if check.after_state is None:
        r.status = "nothing"
        return r
    r.mesh = mesh
    evaluate(r, s, mesh, check.after_state)
    if method == "K-E" and not r.ea:
        r.status = "refused: delta check"
    return r


_UNSET = object()


def evaluate(r: Res, s: Session, mesh, after_state, *, ref=_UNSET, side_cls: str = "+") -> None:
    """E-a..E-d. `ref` / `side_cls` (K-C+clip only): E-b compares the faces of class `side_cls` (the
    working side) with `ref` (the clipped path resolved alone) instead of the "+" faces with
    `s.ref_plus`."""
    t0 = time.perf_counter()
    after = completeness_report(mesh)
    delta = delta_check(s.base_report, after)
    state = symmetry_state(mesh)
    r.report_ms = 1000 * (time.perf_counter() - t0)
    r.ea = delta.ok and STATE_RANK[state] <= STATE_RANK[s.base_state_sym]
    r.info["delta"] = delta.violations
    r.info["state"] = state.value
    faces = canon_faces(mesh)
    ref_faces = s.ref_plus if ref is _UNSET else ref
    if ref_faces is not None:
        r.eb = sorted(c for cls, c in faces if cls == side_cls) == ref_faces
    allc = sorted(c for _cls, c in faces)
    r.ec = allc == sorted(mirror_canon(c) for _cls, c in faces)
    if not r.ec:
        r.maxdev = max_deviation(mesh, s.state)
        r.ec_kind = "conn" if r.maxdev == 0.0 else "float" if r.maxdev < 1e-9 else "geom"
    hist = HistoryStack()
    hist.push(MeshStateCommand(mesh=mesh, before_state=s.state, after_state=after_state, description="Knife"))
    hist.undo()
    undone = kr.mesh_content(mesh.export_state()) == kr.mesh_content(s.state)
    hist.redo()
    redone = kr.mesh_content(mesh.export_state()) == kr.mesh_content(after_state)
    r.ed = len(hist) == 1 and undone and redone


def max_deviation(mesh, state) -> float:
    """Largest distance from a created vertex's mirror position to the nearest vertex (a number, no verdict)."""
    old = state["vertices"]
    allp = [tuple(vpos(mesh, v)) for v in mesh.all_vertex_ids()]
    dev = 0.0
    for v in mesh.all_vertex_ids():
        if int(v) in old:
            continue
        q = mirror(vpos(mesh, v))
        dev = max(dev, min(math.dist(q, p) for p in allp))
    return dev


def run_all(s: Session, methods=("K-A0", "K-A", "K-B", "K-C", "K-D")) -> dict[str, Res]:
    out = {m: run(m, s) for m in methods}
    if "K-A" in out:
        ka = out["K-A"]
        ke = Res("K-E", ka.status, ka.ea, ka.eb, ka.ec, ka.ed, ka.ms, ka.report_ms, ka.snapped, ka.snap_seen,
                 ka.maxdev, ka.ec_kind, None, ka.info)
        if ka.ok and not ka.ea:
            ke.status = "refused: delta check"
        out["K-E"] = ke
    return out


def describe(r: Res) -> str:
    if not r.ok:
        return r.status
    extra = f" snap {r.snapped}/{r.snap_seen}" if r.snap_seen else ""
    dev = f" dev {r.maxdev:.1e}({r.ec_kind})" if r.ec is False else ""
    return f"E {r.flags()}{extra}{dev}"


def case_rows(asset: str, case: str, s: Session, methods=("K-A0", "K-A", "K-B", "K-C", "K-D", "K-E")):
    res = run_all(s, tuple(m for m in methods if m != "K-E"))
    row = [asset, case, "ok" if s.ref_ok else f"src: {s.ref_problem or 'nothing'}"]
    row += [describe(res[m]) for m in methods]
    return row, res


CASE_HEADER = ["asset", "case", "source alone", "K-A0 (no snap)", "K-A", "K-B", "K-C", "K-D", "K-E"]
CASE_NOTE = ("E flags = E-a E-b E-c E-d ('+' pass, '-' fail, '.' n/a); snap = mirror vertices moved / pairs; "
             "dev = largest distance of a created vertex's mirror position to the nearest vertex: conn = 0 (every "
             "point has its mirror, the edges differ), float = below 1e-9 (P3-type), geom = 1e-9 or more.")


# =============================================================================================
# Path recipes
# =============================================================================================

def session_from(name: str, actions, label: str = "", view=None, state=None) -> Session:
    mesh = Mesh.from_state(state if state is not None else start_state(name))
    knife, acc = play(mesh, actions, view)
    s = Session(name, resolver_path(knife), state, label)
    s.accepted = acc
    s.actions = actions
    s.knife = knife
    return s


def interior_quad(mesh):
    return plus_faces(mesh, strict=True)[0]


def k1(args) -> None:
    section("K1 - edge -> edge in one +X quad (Shift snap t = 0.5, and t not 0.5)")
    rows = []
    snap_sites = []
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        m = fresh(asset)
        f = interior_quad(m)
        e = m.face_edges(f)
        for t0, t1 in ((0.5, 0.5), (0.3, 0.6), (0.37, 0.37), (0.123456789, 0.87654321)):
            s = session_from(asset, [("click", T_e(e[0], t0)), ("click", T_e(e[2], t1))])
            row, res = case_rows(asset, f"f{int(f)} t=({t0},{t1})", s)
            rows.append(row)
            ka = res["K-A"]
            snap_sites.append([asset, f"({t0},{t1})", f"{ka.snapped}/{ka.snap_seen}",
                               "pid -> created vertex (edge record, `_run_end_vertex`)"])
    table(CASE_HEADER, rows, CASE_NOTE)
    print("\nWhere the snap acts (K-A): mirror vertices moved / (source pid, mirror pid) pairs with two vertices")
    table(["asset", "t", "moved/pairs", "site"], snap_sites)


def k2(args) -> None:
    section("K2 - vertex -> vertex chord; vertex -> edge point")
    rows = []
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        m = fresh(asset)
        f = interior_quad(m)
        vs, es = m.face_vertices(f), m.face_edges(f)
        for label, actions in (
            ("vertex -> vertex (diagonal)", [("click", T_v(vs[0])), ("click", T_v(vs[2]))]),
            ("vertex -> edge t=0.3", [("click", T_v(vs[0])), ("click", T_e(es[1], 0.3))]),
            ("vertex -> edge t=0.5", [("click", T_v(vs[0])), ("click", T_e(es[2], 0.5))]),
        ):
            row, _res = case_rows(asset, label, session_from(asset, actions))
            rows.append(row)
    table(CASE_HEADER, rows, CASE_NOTE)


# -- K3: interior points --------------------------------------------------------------------

def k3_recipes(mesh, f, tie: bool):
    """The five interior-point rules of one face. `tie`: centred / symmetric clicks (square faces give exact
    distance ties); otherwise the same shapes moved by irrational offsets."""
    vs, es = mesh.face_vertices(f), mesh.face_edges(f)
    c = centroid(mesh, f)
    corners = [vpos(mesh, v) for v in vs]
    off = (0.0, 0.0, 0.0) if tie else (0.0731, 0.0417, 0.0)

    def inner(k, scale=0.25):
        p = lerp(c, corners[k % len(corners)], scale)
        return tuple(p[i] + off[i] * 0.3 for i in range(3)) if not tie else p

    def shift(p):
        return tuple(p[i] + off[i] * 0.3 for i in range(3)) if not tie else p

    loop = [inner(k) for k in range(len(corners))]
    out = {
        "notch (edge -> inside -> same edge)": [("click", T_e(es[0], 0.3)), ("click", T_f(f, shift(c))),
                                                ("click", T_e(es[0], 0.7))],
        "bent cut (edge -> inside -> edge)": [("click", T_e(es[0], 0.5)), ("click", T_f(f, shift(c))),
                                              ("click", T_e(es[2], 0.5))],
        "closed shape (select_bridge)": [("click", T_f(f, p)) for p in loop] + [("click", T_p(0))],
        # A loop at a point: corner 0 -> two inside points -> corner 0 (`close_loop_at_vertex`).
        "loop at a point (close_loop_at_vertex)": [("click", T_v(vs[0])), ("click", T_f(f, inner(1, 0.45))),
                                                   ("click", T_f(f, inner(3, 0.45))), ("click", T_v(vs[0]))],
        "tail joined to corner (_tail_corners)": [("click", T_e(es[0], 0.5)), ("click", T_f(f, shift(c)))],
    }
    return out


def k3(args) -> None:
    section("K3 - interior points: notch, bent cut, closed shape, loop at a point, tail join (tie / no tie)")
    rows = []
    for asset in ("tie_grid", "subd_cube", "head_basemesh"):
        m = fresh(asset)
        f = interior_quad(m)
        for tie in (True, False):
            for recipe, actions in k3_recipes(m, f, tie).items():
                TIES.clear()
                with tie_counters():
                    s = session_from(asset, actions)
                fired = [k for k, v in TIES.items() if "calls" not in k and v]
                row, _res = case_rows(asset, f"{'TIE ' if tie else 'no tie '}{recipe}", s)
                row.insert(3, ", ".join(fired) or "-")
                rows.append(row)
    table(CASE_HEADER[:3] + ["tie-break that fired (source)"] + CASE_HEADER[3:], rows, CASE_NOTE)

    print("\nHow often the tie-break decides on the real assets: every +X face (x >= 0), centred / symmetric")
    print("clicks (the 'TIE' recipes); counts from the one-sided resolve; then K-A / K-C / K-D on the same paths.")
    hdr = ["asset", "recipe", "faces", "tie fired", "K-A E-a+E-c pass", "K-C E-a+E-c pass", "K-D E-a+E-c pass",
           "K-D self-symmetric"]
    rows = []
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        m = fresh(asset)
        faces = plus_faces(m)
        if args.quick:
            faces = faces[:12]
        stats = collections.defaultdict(lambda: collections.Counter())
        for f in faces:
            for recipe, actions in k3_recipes(m, f, True).items():
                if recipe.startswith("notch") or recipe.startswith("bent"):
                    continue
                TIES.clear()
                with tie_counters():
                    s = session_from(asset, actions)
                st = stats[recipe]
                if not s.ref_ok:
                    st["source invalid"] += 1
                    continue
                st["faces"] += 1
                if any(v for k, v in TIES.items() if "calls" not in k):
                    st["tie"] += 1
                _KD["zero_side"] = 0
                for meth in ("K-A", "K-C", "K-D"):
                    rr = run(meth, s)
                    if rr.ok and rr.ea and rr.ec:
                        st[meth] += 1
                st["kd zero"] += 1 if _KD["zero_side"] else 0
        for recipe, st in stats.items():
            n = st["faces"]
            rows.append([asset, recipe, f"{n} (+{st['source invalid']} src invalid)", pct(st["tie"], n),
                         pct(st["K-A"], n), pct(st["K-C"], n), pct(st["K-D"], n), st["kd zero"]])
    table(hdr, rows)


# -- K4/K5: cameras -------------------------------------------------------------------------

CAMERAS = {"front": (0.0, 10.0), "3/4 (+X)": (35.0, 10.0), "side (+X)": (90.0, 15.0)}
K5_SAMPLES = (("hole_grid", "front"), ("hole_grid", "3/4 (+X)"),
              ("head_basemesh", "front"), ("head_basemesh", "3/4 (+X)"), ("head_basemesh", "side (+X)"))
# (section, mesh, camera, index, session) of every K4 / K5 session, in generation order, for the K-C+clip
# section (it regenerates them with the same seeds when K4 / K5 did not run).
CAMERA_SAMPLES: list[tuple] = []


def make_view(mesh, cam_key: str, occlusion=True):
    yaw, pitch = CAMERAS[cam_key]
    cam = camera_for(mesh, yaw, pitch)
    return cam, (cam, W, H), PickCache()


def camera_session(name: str, rnd: random.Random, cam_key: str, n_clicks: int, p_space: float = 0.12):
    """Clicks at random +X targets as the window makes them: project -> `knife_pick` (occlusion on) ->
    own-point snap -> a point in space outside the mesh (`Application._knife_pick`'s order)."""
    mesh = fresh(name)
    cam, _v, cache = make_view(mesh, cam_key)
    knife = new_knife(mesh)
    knife.set_view(cam, W, H, cache=cache, occlusion=True)
    actions, click_pids = [], []
    faces = plus_faces(mesh)
    tries = 0
    while len(actions) < n_clicks and tries < n_clicks * 8:
        tries += 1
        if rnd.random() < p_space:
            sx, sy = rnd.choice((rnd.uniform(5, 60), rnd.uniform(W - 60, W - 5))), rnd.uniform(60, H - 60)
        else:
            f = rnd.choice(faces)
            r = rnd.random()
            if r < 0.2:
                world = vpos(mesh, rnd.choice(mesh.face_vertices(f)))
            elif r < 0.65:
                world = edge_point(mesh, rnd.choice(mesh.face_edges(f)), rnd.uniform(0.15, 0.85))
            else:
                world = centroid(mesh, f)
            scr = cam.project_to_screen(world, W, H)
            if scr is None:
                continue
            sx, sy = scr[0] + rnd.uniform(-1.5, 1.5), scr[1] + rnd.uniform(-1.5, 1.5)
        target = knife_pick(cam, mesh, sx, sy, W, H, cache=cache, occlusion=True)
        target = snap_own_point(cam, mesh, sx, sy, W, H, knife.snap_points, target, cache=cache, occlusion=True)
        if target.get("kind") == "outside":
            target = {"kind": "space", "position": space_point(cam, sx, sy, W, H)}
        elif target.get("kind") in ("vertex", "edge", "face") and \
                (target.get("position") or target_world(mesh, target))[0] <= 0.0:
            continue
        with quiet():
            if knife.click(target):
                actions.append(("click", target))
                click_pids.append(clicked_pid(knife))
    s = Session(name, resolver_path(knife))
    s.actions, s.knife, s.cam_key, s.click_pids = actions, knife, cam_key, click_pids
    return s


def clicked_pid(knife):
    """The point id of the record the last accepted click placed (or reused)."""
    return next(p["pid"] for p in reversed(knife.last_plan.entries) if p["kind"] != "break")


def reaches_other_side(s: Session) -> bool:
    """A record of the source path (clicked point or planner crossing) lies on the -X side."""
    mesh = Mesh.from_state(s.state)
    return any(p["kind"] != "break" and target_world(mesh, p)[0] < 0.0 for p in s.path)


def target_world(mesh, t):
    if t["kind"] == "vertex":
        return vpos(mesh, t["vertex_id"])
    if t["kind"] == "edge":
        return edge_point(mesh, t["edge_id"], t["t"])
    return t["position"]


def mirror_target(mir: Mirror, t: dict) -> dict:
    """The mirrored click target (K4 (ii), K6): what a click on the mirror side would have been."""
    kind = t["kind"]
    if kind == "vertex":
        w = mir.vp.get(t["vertex_id"])
        if w is None:
            raise Unmirrorable("vertex without partner")
        return T_v(w)
    if kind == "edge":
        rec = mir.record({"pid": 0, **t}, {})
        return T_e(rec["edge_id"], rec["t"])
    if kind == "face":
        f2 = mir.fp.get(t["face_id"])
        if f2 is None:
            raise Unmirrorable("face without partner")
        return {"kind": "face", "face_id": f2, "position": mirror(t["position"]),
                "distance_px": t.get("distance_px", 100.0)}
    if kind == "space":
        return {"kind": "space", "position": mirror(t["position"])}
    return dict(t)     # own point: the pids of a replayed session follow the source's


def replanned_mirror(s: Session, view_key: str | None) -> tuple[list[dict], KnifeTool]:
    """K4 (ii): click the mirrored targets in a fresh session with the *same* camera (re-planning every
    segment), and return its resolver path with pids relabelled ("m", pid) for the K-A snap."""
    mesh = Mesh.from_state(s.state)
    mir = Mirror(mesh)
    view = None
    if view_key is not None:
        cam, _v, cache = make_view(mesh, view_key)
        view = (cam, W, H)
    knife = new_knife(mesh)
    if view is not None:
        knife.set_view(view[0], W, H, cache=cache, occlusion=True)
    rep_pids = []
    with quiet():
        for act in s.actions:
            if act[0] == "click":
                rep_pids.append(clicked_pid(knife) if knife.click(mirror_target(mir, act[1])) else None)
            elif act[0] == "lift":
                knife.lift()
            elif act[0] == "finish":
                knife.finish_chain()
            elif act[0] == "undo":
                knife.undo_step()
            elif act[0] == "redo":
                knife.redo_step()
    memo: dict = {}

    def relabel(p):
        if p["kind"] == "break":
            return dict(p)
        if p["pid"] not in memo:
            memo[p["pid"]] = {**p, "pid": ("m", p["pid"])}
        return memo[p["pid"]]

    path = [relabel(p) for p in resolver_path(knife)]
    pairs = [(a, ("m", b)) for a, b in zip(getattr(s, "click_pids", []), rep_pids) if b is not None]
    return path, knife, pairs


def segment_signature(mesh, mir: Mirror, path: list[dict], mirrored: bool) -> list[tuple]:
    """Per chain stretch: the crossing records between consecutive clicked points, as comparable tuples
    (source records are first mapped to their mirror elements). Breaks are part of the signature."""
    out = []
    memo: dict = {}
    for p in path:
        if p["kind"] == "break":
            out.append(("break", p.get("reason"), p.get("cyclic")))
            continue
        q = mir.record(p, memo) if mirrored else p
        if q["kind"] == "vertex":
            out.append(("v", int(q["vertex_id"]), bool(q.get("crossing"))))
        elif q["kind"] == "edge":
            out.append(("e", int(q["edge_id"]), q["t"], bool(q.get("crossing"))))
        elif q["kind"] == "face":
            out.append(("f", int(q["face_id"]), tuple(q["position"])))
    return out


def k4(args) -> None:
    section("K4 - cross-face runs on head_basemesh: (i) stored crossings mirrored vs (ii) re-planned from the same camera")
    rnd = random.Random(args.seed + 4)
    n = 12 if args.quick else 60
    rows = []
    examples = []
    for cam_key in CAMERAS:
        st = collections.Counter()
        for i in range(n):
            s = camera_session("head_basemesh", rnd, cam_key, rnd.randint(2, 6), p_space=0.0)
            CAMERA_SAMPLES.append(("K4", "head_basemesh", cam_key, i, s))
            if not s.ref_ok:
                st["source invalid"] += 1
                continue
            st["sessions"] += 1
            mesh = Mesh.from_state(s.state)
            mir = Mirror(mesh)
            try:
                sig_i = segment_signature(mesh, mir, s.path, True)
                mpath_ii, _mknife, pairs_ii = replanned_mirror(s, cam_key)
            except Unmirrorable:
                st["unmirrorable"] += 1
                continue
            sig_ii = segment_signature(mesh, mir, mpath_ii, False)
            st["crossings (i)"] += sum(1 for x in sig_i if x[0] in ("v", "e") and x[-1])
            st["crossings (ii)"] += sum(1 for x in sig_ii if x[0] in ("v", "e") and x[-1])
            st["gaps (i)"] += sum(1 for x in sig_i if x[0] == "break" and x[1] == "gap")
            st["gaps (ii)"] += sum(1 for x in sig_ii if x[0] == "break" and x[1] == "gap")
            same_el = [x[:2] for x in sig_i] == [x[:2] for x in sig_ii]
            if sig_i == sig_ii:
                st["identical"] += 1
            elif same_el:
                st["same elements, other t"] += 1
            else:
                st["different elements/breaks"] += 1
                if len(examples) < 4:
                    examples.append((cam_key, len(sig_i), len(sig_ii),
                                     sum(1 for x in sig_i if x[0] == "break" and x[1] == "gap"),
                                     sum(1 for x in sig_ii if x[0] == "break" and x[1] == "gap")))
            r_i = run("K-A", s)
            r_ii = run("K-A", s, mirrored_path=mpath_ii, pairs=pairs_ii)
            r_c = run("K-C", s)
            if r_c.status.startswith("refused"):
                st["K-C refused, path on -X"] += reaches_other_side(s)
            for tag, rr in (("(i)", r_i), ("(ii)", r_ii), ("K-C", r_c)):
                if rr.ok and rr.ea and rr.ec:
                    st[f"pass {tag}"] += 1
                elif rr.ok and rr.ec_kind:
                    st[f"fail {tag} {rr.ec_kind}"] += 1
                elif not rr.ok:
                    st[f"fail {tag} {rr.status.split(':')[0]}"] += 1
        k = st["sessions"]
        fails = lambda tag: ", ".join(f"{key.split()[-1]} {v}" for key, v in sorted(st.items())  # noqa: E731
                                      if key.startswith(f"fail {tag} ")) or "-"
        rows.append([cam_key, f"{k} (+{st['source invalid']} src invalid, {st['unmirrorable']} unmirrorable)",
                     pct(st["identical"], k), pct(st["same elements, other t"], k),
                     pct(st["different elements/breaks"], k),
                     f"{st['crossings (i)']}/{st['crossings (ii)']}", f"{st['gaps (i)']}/{st['gaps (ii)']}",
                     pct(st["pass (i)"], k), fails("(i)"), pct(st["pass (ii)"], k), fails("(ii)"),
                     pct(st["pass K-C"], k), f"{fails('K-C')} ({st['K-C refused, path on -X']} with a record on -X)"])
    table(["camera", "sessions", "(ii) == (i)", "same elements, other t", "different elements / breaks",
           "crossings (i)/(ii)", "gap breaks (i)/(ii)", "K-A E-a+E-c (i)", "(i) failures", "K-A E-a+E-c (ii)",
           "(ii) failures", "K-C E-a+E-c", "K-C failures"], rows,
          "(i) = the source session's stored records mirrored (K-A); (ii) = the mirrored clicks re-planned with "
          "the same camera (snap on the clicked points only: a re-planned crossing has no source pid). "
          "Failure kinds as in CASE_NOTE (conn / float / geom) or the status. Sessions click visible +X targets.")
    if examples:
        print("examples of (ii) != (i): (camera, records (i), records (ii), gaps (i), gaps (ii))")
        for ex in examples:
            print("  ", ex)


def k5(args) -> None:
    section("K5 - points in space and gap breaks (hole / border / hidden part): are the same stretches skipped?")
    rnd = random.Random(args.seed + 5)
    rows = []
    n = 10 if args.quick else 40
    # A symmetric hole pair on the flat grid, camera in the plane (front) and oblique.
    for name, cam_key in (("hole_grid", "front"), ("hole_grid", "3/4 (+X)"),
                          ("head_basemesh", "front"), ("head_basemesh", "3/4 (+X)"), ("head_basemesh", "side (+X)")):
        st = collections.Counter()
        for i in range(n):
            s = camera_session(name, rnd, cam_key, rnd.randint(2, 6), p_space=0.3)
            CAMERA_SAMPLES.append(("K5", name, cam_key, i, s))
            if not s.ref_ok:
                st["source invalid"] += 1
                continue
            st["sessions"] += 1
            st["space points"] += sum(1 for a in s.actions if a[1]["kind"] == "space")
            mesh = Mesh.from_state(s.state)
            mir = Mirror(mesh)
            try:
                sig_i = segment_signature(mesh, mir, s.path, True)
                mpath_ii, _k, pairs_ii = replanned_mirror(s, cam_key)
            except Unmirrorable:
                st["unmirrorable"] += 1
                continue
            sig_ii = segment_signature(mesh, mir, mpath_ii, False)
            for tag, sig in (("i", sig_i), ("ii", sig_ii)):
                for x in sig:
                    if x[0] == "break" and x[1] in ("gap", "edge", "space"):
                        st[f"{x[1]} ({tag})"] += 1
            src_breaks = [x[1] for x in segment_signature(mesh, mir, s.path, False) if x[0] == "break"]
            if src_breaks == [x[1] for x in sig_ii if x[0] == "break"]:
                st["same breaks (ii)"] += 1
            r_i, r_ii = run("K-A", s), run("K-A", s, mirrored_path=mpath_ii, pairs=pairs_ii)
            r_c = run("K-C", s)
            st["pass (i)"] += 1 if (r_i.ok and r_i.ea and r_i.ec) else 0
            st["pass (ii)"] += 1 if (r_ii.ok and r_ii.ea and r_ii.ec) else 0
            st["pass K-C"] += 1 if (r_c.ok and r_c.ea and r_c.ec) else 0
            if r_c.status.startswith("refused"):
                st["refused K-C"] += 1
                st["refused K-C on -X"] += reaches_other_side(s)
        k = st["sessions"]
        rows.append([name, cam_key, k, st["space points"],
                     f"{st['gap (i)']}/{st['gap (ii)']}", f"{st['space (i)']}/{st['space (ii)']}",
                     pct(st["same breaks (ii)"], k), pct(st["pass (i)"], k), pct(st["pass (ii)"], k),
                     f"{pct(st['pass K-C'], k)}; refused {st['refused K-C']} ({st['refused K-C on -X']} with a record "
                     f"on -X)"])
    table(["mesh", "camera", "sessions", "space points", "gap breaks (i)/(ii)", "space breaks (i)/(ii)",
           "(ii) skips the same stretches", "K-A E-a+E-c (i)", "K-A E-a+E-c (ii)", "K-C E-a+E-c"], rows,
          "(i): the mirrored records carry the source's breaks by construction (same stretches skipped). "
          "(ii): re-planned with the same camera.")


# -- K6: session rules ----------------------------------------------------------------------

def k6(args, fuzz_sessions) -> None:
    section("K6 - session rules: click + mirror as one step; rules that depend on camera / pixels")
    print("Code facts (no camera needed for the mirror of a path record):")
    facts = [
        ["EDGE_MARGIN_PX", f"{EDGE_MARGIN_PX} px", "knife.py:317 `_invalid` (face point clearance)", "camera (screen)"],
        ["OWN_POINT_SNAP_PX", f"{OWN_POINT_SNAP_PX} px", "knife_pick.py:254 `snap_own_point`", "camera (screen)"],
        ["VERTEX_TOL_PX", f"{VERTEX_TOL_PX} px", "knife_planner.py:229/272/334 walk + plane", "camera (screen)"],
        ["occlusion (DEPTH_TOLERANCE)", f"{DEPTH_TOLERANCE}", "knife_planner.py:72-82, picks", "camera (depth)"],
        ["ENDPOINT_THRESHOLD", "0.05 (t)", "knife_pick.py:167-174 endpoint snap", "camera (t from the ray)"],
        ["chord / segment_in_face", "GEO_EPS * size", "knife.py:387-416 `_link`", "geometry only"],
        ["MIN_CLOSE_POINTS", "3", "knife.py:442, 521", "path only"],
        ["undo / redo / lift", "-", "knife.py:573-610 `_apply` / steps", "path only"],
    ]
    table(["rule", "value", "where", "depends on"], facts)

    # (a) The mirrored session judged by the same click rules: does every accepted source click have an
    # accepted mirror click, and does the mirrored session's path equal the mirrored records?
    st = collections.Counter()
    for s in fuzz_sessions:
        if not hasattr(s, "actions"):
            continue
        mesh = Mesh.from_state(s.state)
        mir = Mirror(mesh)
        try:
            mact = [(a[0], mirror_target(mir, a[1])) if a[0] == "click" else a for a in s.actions]
        except Unmirrorable:
            st["unmirrorable target"] += 1
            continue
        knife, acc = play(mesh, mact)
        st["sessions"] += 1
        if acc == s.accepted:
            st["same acceptance"] += 1
        try:
            mrec = mir.path(s.path)
        except Unmirrorable:
            continue
        a = normal_form(mrec)
        b = normal_form(resolver_path(knife))
        if a == b:
            st["path == mirrored records"] += 1
        elif [x[:2] for x in a] == [x[:2] for x in b]:
            st["same records, t differs"] += 1
    print("\n(a) the mirror session clicked by the same rules (camera-free fuzz sessions of K10):")
    table(["sessions", "same acceptance per click", "mirror path == mirrored records", "same records, t differs",
           "unmirrorable target"],
          [[st["sessions"], pct(st["same acceptance"], st["sessions"]),
            pct(st["path == mirrored records"], st["sessions"]), st["same records, t differs"],
            st["unmirrorable target"]]])

    # (b) Pixel rules on the hidden / foreshortened mirror side (head, three cameras).
    rows = []
    mesh = fresh("head_basemesh")
    mir = Mirror(mesh)
    for cam_key in CAMERAS:
        cam, _v, cache = make_view(mesh, cam_key)
        c = collections.Counter()
        for f in plus_faces(mesh):
            p = centroid(mesh, f)
            scr = cam.project_to_screen(p, W, H)
            if scr is None or point_occluded(cam, mesh, cache, p, W, H, {f}, DEPTH_TOLERANCE):
                continue
            d = face_edge_distance_px(cam, mesh, f, scr[0], scr[1], W, H, cache=cache)
            if d is None or d < EDGE_MARGIN_PX:
                continue
            c["source clicks (visible, >= 9 px)"] += 1
            f2 = mir.index.face_partner(f)
            q = mirror(p)
            scr2 = cam.project_to_screen(q, W, H)
            if f2 is None or scr2 is None:
                c["mirror off screen / no partner"] += 1
                continue
            if point_occluded(cam, mesh, cache, q, W, H, {f2}, DEPTH_TOLERANCE):
                c["mirror hidden"] += 1
                continue
            d2 = face_edge_distance_px(cam, mesh, f2, scr2[0], scr2[1], W, H, cache=cache)
            if d2 is None or d2 < EDGE_MARGIN_PX:
                c["mirror visible, < 9 px"] += 1
            else:
                c["mirror visible, >= 9 px"] += 1
        k = c["source clicks (visible, >= 9 px)"]
        rows.append([cam_key, k, pct(c["mirror visible, >= 9 px"], k), pct(c["mirror visible, < 9 px"], k),
                     pct(c["mirror hidden"], k), c["mirror off screen / no partner"]])
    print("\n(b) a face-point click at each +X face centre that passes the 9 px rule: what the same rule says about"
          " its mirror point under the same camera (head_basemesh):")
    table(["camera", "source clicks", "mirror visible >= 9 px", "mirror visible < 9 px", "mirror hidden",
           "off screen"], rows)

    # (c) In-session undo/redo: the mirror is a pure function of the path, so it needs no step of its own.
    k = 0
    same = 0
    for s in fuzz_sessions[:100]:
        mesh = Mesh.from_state(s.state)
        acts = list(s.actions) + [("undo",), ("undo",), ("redo",)]
        knife, _acc = play(mesh, acts)
        mir = Mirror(mesh)
        try:
            a = mir.path(resolver_path(knife))
            b = mir.path(resolver_path(knife))
        except Unmirrorable:
            continue
        k += 1
        same += normal_form(a) == normal_form(b)
    print(f"\n(c) after undo, undo, redo the derived mirror path is a function of the session path: "
          f"{pct(same, k)} identical on re-derivation; the session's step count is untouched (the mirror is "
          f"derived, never stored).")


def normal_form(path):
    out = []
    ids: dict = {}
    for p in path:
        if p["kind"] == "break":
            out.append(("break", p.get("reason"), p.get("cyclic")))
            continue
        pid = ids.setdefault(p["pid"], len(ids))
        if p["kind"] == "vertex":
            out.append(("v", int(p["vertex_id"]), pid, bool(p.get("crossing"))))
        elif p["kind"] == "edge":
            out.append(("e", int(p["edge_id"]), pid, p["t"], bool(p.get("crossing"))))
        elif p["kind"] == "face":
            out.append(("f", int(p["face_id"]), pid, tuple(p["position"])))
        else:
            out.append(("s", pid, tuple(p["position"])))
    return out


# -- K7: seam --------------------------------------------------------------------------------

def k7_cases(asset: str) -> dict:
    """K7's seam recipes on one asset (label -> actions); also used by the K-C+clip section."""
    m = fresh(asset)
    f, se, opp = seam_face_and_edges(m)          # a +X quad with a seam edge, and its opposite edge
    g = next(x for x in m.edge_faces(se) if x != f)  # the -X quad across the seam edge
    g_opp = m.face_edges(g)[(m.face_edges(g).index(se) + 2) % 4]
    sv = m.edge_vertices(se)
    # an edge of f that touches the seam vertex sv[0] but is not the seam edge
    side_edge = next(e for e in m.face_edges(f) if e not in (se, opp) and sv[0] in m.edge_vertices(e))
    mir = Mirror(m)
    mrec = mir.record({"pid": 0, "kind": "edge", "edge_id": opp, "t": 0.3}, {})
    return {
        "a. start on a seam vertex -> edge t=0.3": [("click", T_v(sv[0])), ("click", T_e(opp, 0.3))],
        "a'. edge t=0.3 -> end on a seam vertex": [("click", T_e(opp, 0.3)), ("click", T_v(sv[1]))],
        "b. seam edge point t=0.3 -> opposite edge t=0.6 (S1)": [("click", T_e(se, 0.3)), ("click", T_e(opp, 0.6))],
        "b2. two points on one seam edge (0.3, 0.7), two chains": [
            ("click", T_e(se, 0.3)), ("click", T_e(opp, 0.4)), ("lift",),
            ("click", T_e(se, 0.7)), ("click", T_e(opp, 0.8))],
        "c. path crossing the seam into the other side": [
            ("click", T_e(opp, 0.3)), ("click", T_e(se, 0.5)), ("click", T_e(g_opp, 0.6))],
        "d. drawn symmetric by the Artist (exact mirror)": [
            ("click", T_e(opp, 0.3)), ("click", T_e(se, 0.5)), ("click", T_e(mrec["edge_id"], mrec["t"]))],
        "d'. drawn symmetric, mirror t off by 1e-12": [
            ("click", T_e(opp, 0.3)), ("click", T_e(se, 0.5)), ("click", T_e(mrec["edge_id"], mrec["t"] + 1e-12))],
        "d''. drawn symmetric, mirror t off by 1e-6": [
            ("click", T_e(opp, 0.3)), ("click", T_e(se, 0.5)), ("click", T_e(mrec["edge_id"], mrec["t"] + 1e-6))],
        "g. along the seam (seam vertex -> seam vertex) then into the face": [
            ("click", T_v(sv[0])), ("click", T_v(sv[1])), ("click", T_e(opp, 0.5))],
        "h. seam vertex -> side edge point (one end on the seam)": [
            ("click", T_v(sv[1])), ("click", T_e(side_edge, 0.4))],
    }


def k7_synthetic() -> dict:
    """K7's plane-spanning rows ((fixture, label) -> actions); also used by the K-C+clip section."""
    hx = fresh("hexagon_grid")
    hexf = next(f for f in hx.all_face_ids() if len(hx.face_vertices(f)) == 6)
    pos = {tuple(vpos(hx, v)): v for v in hx.all_vertex_ids()}
    s1, s2 = pos[(0.0, 1.0, 0.0)], pos[(0.0, 2.0, 0.0)]
    right = kr.find_edge(hx, pos[(1.0, 1.0, 0.0)], pos[(1.0, 2.0, 0.0)])
    left = kr.find_edge(hx, pos[(-1.0, 1.0, 0.0)], pos[(-1.0, 2.0, 0.0)])
    sp = fresh("span_grid")
    sp_pos = {tuple(vpos(sp, v)): v for v in sp.all_vertex_ids()}
    sp_r = kr.find_edge(sp, sp_pos[(0.5, 0.0, 0.0)], sp_pos[(0.5, 1.0, 0.0)])
    sp_l = kr.find_edge(sp, sp_pos[(-0.5, 0.0, 0.0)], sp_pos[(-0.5, 1.0, 0.0)])
    return {
        ("hexagon_grid", "e. chord between two seam points in one face (in the plane)"):
            [("click", T_v(s1)), ("click", T_v(s2))],
        ("hexagon_grid", "e'. bent chord seam point -> inside (+X part) -> seam point"):
            [("click", T_v(s1)), ("click", T_f(hexf, (0.4, 1.5, 0.0))), ("click", T_v(s2))],
        ("hexagon_grid", "f. through the plane-spanning face, right edge 0.3 -> left edge 0.6"):
            [("click", T_e(right, 0.3)), ("click", T_e(left, 0.6))],
        ("hexagon_grid", "f'. through it, symmetric (right 0.5 -> left 0.5)"):
            [("click", T_e(right, 0.5)), ("click", T_e(left, 0.5))],
        ("span_grid", "f''. span grid (no seam): right edge 0.3 -> left edge 0.6"):
            [("click", T_e(sp_r, 0.3)), ("click", T_e(sp_l, 0.6))],
    }


def k7(args) -> None:
    section("K7 - seam cases")
    rows = []
    detail = []
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        for label, actions in k7_cases(asset).items():
            s = session_from(asset, actions)
            row, res = case_rows(asset, label, s)
            rows.append(row)
            for meth in ("K-A", "K-B", "K-C", "K-D"):
                rr = res[meth]
                if rr.mesh is not None:
                    mm = rr.mesh
                    dd = mm.symmetry_definition
                    live = sum(1 for e in dd.seam_edges if mm.is_valid_edge(e))
                    detail.append([asset, label[:3], meth,
                                   f"{len(mm.all_vertex_ids())}/{len(mm.all_edge_ids())}/{len(mm.all_face_ids())}",
                                   "%d/%d" % duplicates(mm), f"{live}/{len(dd.seam_edges)}", rr.info.get("state")])
    # synthetic: plane-spanning faces
    for (name, label), actions in k7_synthetic().items():
        s = session_from(name, actions)
        row, res = case_rows(name, label, s)
        rows.append(row)
        for meth in ("K-A", "K-B", "K-C", "K-D"):
            rr = res[meth]
            if rr.mesh is not None:
                mm = rr.mesh
                dd = mm.symmetry_definition
                live = sum(1 for e in dd.seam_edges if mm.is_valid_edge(e))
                detail.append([name, label[:3], meth,
                               f"{len(mm.all_vertex_ids())}/{len(mm.all_edge_ids())}/{len(mm.all_face_ids())}",
                               "%d/%d" % duplicates(mm), f"{live}/{len(dd.seam_edges)}", rr.info.get("state")])
    table(CASE_HEADER, rows, CASE_NOTE)
    print("\nWhat each method produced (committed results only): V/E/F, duplicate vertex pairs (identical / < 1e-9),"
          " seam live/declared, symmetry_state")
    table(["mesh", "case", "method", "V/E/F", "dup =/~", "seam", "state"], detail)

    # _merge_repeated_points with mirrored t on a reversed edge: when do 1 - t and t round to one key?
    rnd = random.Random(args.seed + 7)
    st = collections.Counter()
    for _ in range(100000):
        t = rnd.uniform(0.01, 0.99)
        u = 1.0 - (1.0 - t)
        st["1-(1-t) != t"] += u != t
        st["round(1-(1-t), 9) != round(t, 9)"] += round(u, 9) != round(t, 9)
    print(f"\n`_merge_repeated_points` key round(t, 9) (knife_resolve.py:991), 100 000 random t: "
          f"1-(1-t) != t in {st['1-(1-t) != t']}, the 9-digit keys differ in {st['round(1-(1-t), 9) != round(t, 9)']}. "
          f"A mirror record meets a source record on the *same* edge only on a seam edge (its own partner, t "
          f"unchanged) or when the path itself reaches the other side (cases c/d).")
    seam_chords = 0
    for asset in ("subd_cube", "head_basemesh", "man_with_shoes_basemesh"):
        m = fresh(asset)
        svs = seam_vertices(m)
        for f in m.all_face_ids():
            b = m.face_vertices(f)
            on = [i for i, v in enumerate(b) if v in svs]
            for i in on:
                for j in on:
                    if i < j and (j - i) % len(b) not in (1, len(b) - 1):
                        seam_chords += 1
    print(f"Faces of the Lab assets with two non-adjacent seam vertices (a seam chord possible): {seam_chords}.")


# -- K8: unpaired geometry -------------------------------------------------------------------

def k8(args, rnd) -> None:
    section("K8 - next to unpaired geometry (man_with_shoes_basemesh, partial): can D-strict refuse at click time?")
    name = "man_with_shoes_basemesh"
    mesh = fresh(name)
    mir = Mirror(mesh)
    idx = mir.index
    pv = [v for v in mesh.all_vertex_ids() if vpos(mesh, v)[0] > 0]
    pe = [e for e in mesh.all_edge_ids() if min(vpos(mesh, v)[0] for v in mesh.edge_vertices(e)) >= 0]
    pf = plus_faces(mesh)
    print(f"+X targets without a partner: vertices {sum(1 for v in pv if idx.vertex_partner(v) is None)}/{len(pv)}, "
          f"edges {sum(1 for e in pe if idx.edge_partner(e) is None)}/{len(pe)}, "
          f"faces {sum(1 for f in pf if idx.face_partner(f) is None)}/{len(pf)}")
    n = 60 if args.quick else 400
    conf = collections.Counter()
    for s in fuzz_sessions_for(name, rnd, n, near_unpaired=True):
        if not s.ref_ok:
            conf["source invalid"] += 1
            continue
        p1 = any(record_unpaired(idx, mesh, p) for p in s.path if p["kind"] != "break")
        p2 = p1 or any(f is not None and idx.face_partner(f) is None for f in segment_faces(mesh, s.path))
        res = {m: run(m, s) for m in ("K-A", "K-C")}
        for meth, rr in res.items():
            refused = not (rr.ok and rr.ea)
            conf[(meth, "P1" if p1 else "-", "refused" if refused else "kept")] += 1
            conf[(meth, "P2" if p2 else "-", "refused" if refused else "kept", "p2")] += 1
            if rr.ok and rr.ea and not rr.ec:
                conf[(meth, "kept but E-c fails")] += 1
        conf["sessions"] += 1
    rows = []
    for meth in ("K-A", "K-C"):
        for pred, key in (("P1 = a record has no partner", None), ("P2 = P1 or a cut face has no partner", "p2")):
            tag = "P1" if key is None else "P2"

            def g(a, b):
                return conf[(meth, a, b)] if key is None else conf[(meth, a, b, key)]

            rows.append([meth, pred, g(tag, "refused"), g(tag, "kept"), g("-", "refused"), g("-", "kept")])
    table(["method", "click-time predictor", "predicted + refused at commit", "predicted but kept",
           "not predicted but refused", "not predicted, kept"], rows,
          f"{conf['sessions']} sessions near unpaired vertices (+{conf['source invalid']} with an invalid source "
          f"path). 'refused at commit' = no result or delta check (E-a) fails (D-strict).")


def record_unpaired(idx, mesh, p) -> bool:
    if p["kind"] == "vertex":
        return idx.vertex_partner(p["vertex_id"]) is None
    if p["kind"] == "edge":
        return idx.edge_partner(p["edge_id"]) is None
    if p["kind"] == "face":
        return idx.face_partner(p["face_id"]) is None
    return False


def point_faces(mesh, p) -> set:
    if p["kind"] == "face":
        return {p["face_id"]}
    if p["kind"] == "edge":
        return set(mesh.edge_faces(p["edge_id"]))
    if p["kind"] == "vertex":
        return {f for e in mesh.vertex_edges(p["vertex_id"]) for f in mesh.edge_faces(e)}
    return set()


def segment_faces(mesh, path) -> set:
    """The faces a click-time segment cuts: the faces shared by consecutive points (no break between)."""
    out = set()
    prev = None
    for p in path:
        if p["kind"] == "break":
            prev = None       # a chain end or a skipped stretch: no cut across it
            continue
        if prev is not None:
            shared = point_faces(mesh, prev) & point_faces(mesh, p)
            out |= shared if len(shared) <= 1 else {min(shared)}
        prev = p
    return out


# -- K10: fuzz ---------------------------------------------------------------------------------

def fuzz_sessions_for(name: str, rnd: random.Random, n: int, near_unpaired: bool = False) -> list[Session]:
    """`n` random camera-free sessions of 2-8 accepted clicks on +X faces (x >= 0), through the Production
    click rules: vertices, edge points (t = 0.5 in 30 %), face points (centred in 30 %), closes, pen lifts,
    earlier points and in-session undo. `near_unpaired`: start next to an unpaired vertex."""
    out = []
    mesh0 = fresh(name)
    faces = plus_faces(mesh0)
    if near_unpaired:
        idx = SymmetryIndex(mesh0)
        bad = {v for v in mesh0.all_vertex_ids() if idx.vertex_partner(v) is None}
        near = [f for f in faces if any(v in bad for v in mesh0.face_vertices(f))]
        far = [f for f in faces if f not in near]
    allowed = set(faces)
    for _ in range(n):
        mesh = Mesh.from_state(start_state(name))
        knife = new_knife(mesh)
        actions, accepted = [], []
        goal = rnd.randint(2, 8)
        clicks = 0
        tries = 0
        start_faces = (near if rnd.random() < 0.7 else far) if near_unpaired else faces
        while clicks < goal and tries < goal * 10:
            tries += 1
            chain = knife.chain_points
            r = rnd.random()
            act = None
            if chain and len([p for p in chain if not p.get("crossing")]) >= 3 and r < 0.12:
                first = chain[0]
                act = ("click", T_v(first["vertex_id"]) if first["kind"] == "vertex" else T_p(first["pid"]))
            elif knife.last_point is not None and r < 0.18:
                act = ("lift",)
            elif r < 0.22 and knife.snap_points:
                own = [p for p in knife.snap_points if p["kind"] in ("edge", "vertex")]
                if own:
                    p = rnd.choice(own)
                    act = ("click", T_v(p["vertex_id"]) if p["kind"] == "vertex" else T_p(p["pid"]))
            elif r < 0.25 and actions:
                act = ("undo",)
            if act is None:
                last = knife.last_point
                cand = [f for f in point_faces(mesh, last) if f in allowed] if last is not None else []
                f = rnd.choice(cand) if cand else rnd.choice(start_faces)
                act = ("click", random_target(rnd, mesh, f))
            with quiet():
                if act[0] == "click":
                    ok = knife.click(act[1])
                elif act[0] == "lift":
                    ok = knife.lift()
                else:
                    ok = knife.undo_step()
            actions.append(act)
            accepted.append(ok)
            if ok and act[0] == "click":
                clicks += 1
        s = Session(name, resolver_path(knife))
        s.actions, s.accepted, s.knife = actions, accepted, knife
        out.append(s)
    return out


def random_target(rnd, mesh, f):
    vs, es = mesh.face_vertices(f), mesh.face_edges(f)
    r = rnd.random()
    if r < 0.25:
        return T_v(rnd.choice(vs))
    if r < 0.70:
        t = 0.5 if rnd.random() < 0.3 else rnd.uniform(0.08, 0.92)
        return T_e(rnd.choice(es), t)
    pts = [vpos(mesh, v) for v in vs]
    if rnd.random() < 0.3:
        w = [1.0] * len(pts)
    else:
        w = [rnd.uniform(0.2, 1.0) for _ in pts]
    tot = sum(w)
    return T_f(f, tuple(sum(w[i] * pts[i][k] for i in range(len(pts))) / tot for k in range(3)))


def touches_seam(mesh, path) -> bool:
    svs = seam_vertices(mesh)
    seam = mesh.symmetry_definition.seam_edges
    for p in path:
        if p["kind"] == "vertex" and p["vertex_id"] in svs:
            return True
        if p["kind"] == "edge" and p["edge_id"] in seam:
            return True
    return False


def deviation_origins(s: Session, method: str = "K-A") -> collections.Counter:
    """For a K-A / K-D run whose E-c fails: which created vertices are not exact mirrors after the snap, by
    origin - a pid vertex (snapped pair), a vertex the resolver made itself while walking across a cut of
    this commit (`split_edge` in `_walk_run`: an intersection), or one it placed inside a face construction
    (`split_face` positions that are no click: the crossing point of a loop)."""
    mesh = Mesh.from_state(s.state)
    mir = Mirror(mesh)
    sink: dict = {}
    full = s.path + [LIFT] + mir.path(s.path)
    with KeptLog(mesh) as log, pid_report(sink), (kd_tiebreaks((ORIGIN, X_NORMAL)) if method == "K-D"
                                                  else contextlib.nullcontext()):
        resolver = kr.CrossFaceResolver(mesh, s.state)
        resolver.resolve(full)
    sink.update(resolver.interior_vertices)
    snap_pairs(mesh, [(p["pid"], ("m", p["pid"])) for p in s.path if p["kind"] != "break"], sink)
    pid_vs = set(sink.values())
    by_edge = {c[4][0] for c in log.calls if c[0] == "split_edge"}
    by_face = {v for c in log.calls if c[0] == "split_face" for v in c[5][0]}
    old = s.state["vertices"]
    allp = [tuple(vpos(mesh, v)) for v in mesh.all_vertex_ids()]
    out = collections.Counter()
    for v in mesh.all_vertex_ids():
        if int(v) in old:
            continue
        q = mirror(vpos(mesh, v))
        if any(q == p for p in allp):
            continue
        if v in pid_vs:
            out["pid vertex"] += 1
        elif v in by_edge:
            out["resolver: intersection with a cut of this commit (split_edge)"] += 1
        elif v in by_face:
            out["resolver: crossing point inside a face construction (split_face)"] += 1
        else:
            out["other"] += 1
    return out


def k10(args, rnd) -> dict[str, list[Session]]:
    section(f"K10 - fuzz: random valid paths (2-8 clicks, mixed kinds) on the +X side, {args.fuzz} per asset, "
            f"seed {args.seed}")
    print(f"machine: {platform.platform()}, {platform.processor() or platform.machine()}, "
          f"Python {platform.python_version()}, {os.cpu_count()} CPUs")
    all_sessions = {}
    rows = []
    trows = []
    excrows = []
    origins = collections.defaultdict(collections.Counter)
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        sessions = fuzz_sessions_for(asset, rnd, args.fuzz)
        all_sessions[asset] = sessions
        mesh0 = fresh(asset)
        st = collections.defaultdict(collections.Counter)
        times = collections.defaultdict(list)
        single = []
        for s in sessions:
            if not s.ref_ok:
                st["all"]["source invalid"] += 1
                st["all"]["source rolled back" if s.ref_problem else "source cuts nothing"] += 1
                continue
            stratum = "seam" if touches_seam(mesh0, s.path) else "off seam"
            t0 = time.perf_counter()
            mm = Mesh.from_state(s.state)
            kr.resolve_cross_face(mm, s.path, s.state)
            kr.check_commit(mm, s.state)
            single.append(1000 * (time.perf_counter() - t0))
            res = run_all(s, ("K-A", "K-B", "K-C", "K-D"))
            for meth in ("K-A", "K-D"):
                rr = res[meth]
                if rr.ok and rr.ec is False and rr.ec_kind in ("float", "geom"):
                    origins[(asset, meth)].update(deviation_origins(s, meth))
                    origins[(asset, meth)]["runs"] += 1
            for meth, rr in res.items():
                for stra in (stratum, "all"):
                    c = st[(meth, stra)]
                    c["n"] += 1
                    if rr.ok:
                        c["ok"] += 1
                        c["ea"] += bool(rr.ea)
                        c["eb"] += bool(rr.eb)
                        c["ec"] += bool(rr.ec)
                        c["ed"] += bool(rr.ed)
                        c["all4"] += bool(rr.ea and rr.eb and rr.ec and rr.ed)
                        c["silent"] += bool(rr.ea and not (rr.eb and rr.ec))
                        c["ec conn"] += rr.ec_kind == "conn"
                        c["ec float"] += rr.ec_kind == "float"
                        c["ec geom"] += rr.ec_kind == "geom"
                    elif rr.status.startswith("refused"):
                        c["refused"] += 1
                    elif rr.status.startswith("exception"):
                        c["exception"] += 1
                        if len(excrows) < 5:
                            excrows.append([asset, meth, rr.status])
                    elif rr.status.startswith("rolled back"):
                        c["rolled back"] += 1
                    else:
                        c["nothing"] += 1
                if meth != "K-E":
                    times[meth].append(rr.ms)
                    times[meth + " report"].append(rr.report_ms)
        for meth in ("K-A", "K-B", "K-C", "K-D", "K-E"):
            for stra in ("all", "off seam", "seam"):
                c = st[(meth, stra)]
                if not c["n"]:
                    continue
                n = c["n"]
                rows.append([asset, meth, stra, n, pct(c["ea"], n), pct(c["eb"], n), pct(c["ec"], n), pct(c["ed"], n),
                             pct(c["all4"], n), c["refused"], c["rolled back"], c["nothing"], c["exception"],
                             c["silent"], f"{c['ec conn']}/{c['ec float']}/{c['ec geom']}"])
        med = lambda xs: f"{statistics.median(xs):.2f}" if xs else "-"  # noqa: E731
        p95 = lambda xs: f"{sorted(xs)[int(0.95 * (len(xs) - 1))]:.2f}" if xs else "-"  # noqa: E731
        trows.append([asset, "source alone (resolve + check)", med(single), p95(single)])
        for meth in ("K-A", "K-B", "K-C", "K-D"):
            trows.append([asset, meth, med(times[meth]), p95(times[meth])])
        trows.append([asset, "completeness reports + delta (any method)", med(times["K-A report"]),
                      p95(times["K-A report"])])
        print(f"{asset}: {len(sessions)} sessions, {st['all']['source invalid']} excluded because the source path "
              f"alone is no valid one-sided cut ({st['all']['source cuts nothing']} cut nothing - e.g. a single "
              f"click, only skips -, {st['all']['source rolled back']} rolled back by the commit check)")
    table(["asset", "method", "stratum", "n", "E-a", "E-b", "E-c", "E-d", "all four", "refused", "rolled back",
           "nothing", "exception", "silent (E-a+, E-b/E-c-)", "E-c fail conn/float/geom"], rows,
          "stratum 'seam': a record on a seam vertex or seam edge. K-E = K-A with the delta check refusing "
          "(its 'refused' = K-A's E-a failures + K-A's refusals). 'silent' = E-a passes although E-b or E-c fails "
          "(a delta check alone would let it through).")
    print("\nK-A / K-D runs whose E-c fails by float / geometry (not by a tie): the created vertices that are no "
          "exact mirror after the snap, by origin")
    orow = []
    for (asset, meth), c in sorted(origins.items()):
        runs = c.pop("runs", 0)
        orow.append([asset, meth, runs, "; ".join(f"{k}: {v}" for k, v in sorted(c.items()))])
    table(["asset", "method", "runs", "vertices by origin"], orow)
    print()
    table(["asset", "what", "median ms", "p95 ms"], trows)
    if excrows:
        print("first exceptions:")
        table(["asset", "method", "status"], excrows)
    return all_sessions


# -- K9: order / id dependence ---------------------------------------------------------------

def remap_state(state: dict, perm_v, perm_e, perm_f) -> dict:
    """The same mesh with new ids (vertex / edge / face renumbered by the permutations)."""
    new = {
        "vertex_id_counter": state["vertex_id_counter"],
        "edge_id_counter": state["edge_id_counter"],
        "face_id_counter": state["face_id_counter"],
        "vertices": {perm_v[int(v)]: list(p) for v, p in state["vertices"].items()},
        "edges": {perm_e[int(e)]: {"v0": perm_v[d["v0"]], "v1": perm_v[d["v1"]],
                                   "faces": [perm_f[f] for f in d["faces"]]} for e, d in state["edges"].items()},
        "faces": {perm_f[int(f)]: [perm_v[v] for v in b] for f, b in state["faces"].items()},
        "symmetry": None if state["symmetry"] is None else {
            **state["symmetry"], "seam_edges": sorted(perm_e[e] for e in state["symmetry"]["seam_edges"])},
    }
    return new


def remap_path(path, perm_v, perm_e, perm_f):
    memo = {}
    out = []
    for p in path:
        if p["kind"] == "break":
            out.append(dict(p))
            continue
        if p["pid"] in memo:
            out.append(memo[p["pid"]])
            continue
        q = dict(p)
        if p["kind"] == "vertex":
            q["vertex_id"] = type(p["vertex_id"])(perm_v[int(p["vertex_id"])])
        elif p["kind"] == "edge":
            q["edge_id"] = type(p["edge_id"])(perm_e[int(p["edge_id"])])
        elif p["kind"] == "face":
            q["face_id"] = type(p["face_id"])(perm_f[int(p["face_id"])])
        memo[p["pid"]] = q
        out.append(q)
    return out


def variant(kind: str, state: dict, path: list[dict], rnd: random.Random):
    """X1 reflect (positions mirrored exactly, every boundary reversed, ids and t unchanged),
    X2 id permutation, X3 boundary rotation, X4 edge orientation flipped (t -> 1 - t)."""
    ids = lambda key: [int(k) for k in state[key]]  # noqa: E731
    if kind == "X1 reflect":
        new = {**state, "vertices": {v: list(mirror(p)) for v, p in state["vertices"].items()},
               "faces": {f: list(reversed(b)) for f, b in state["faces"].items()}}
        memo, out = {}, []
        for p in path:
            if p["kind"] == "break" or p["pid"] in memo:
                out.append(dict(p) if p["kind"] == "break" else memo[p["pid"]])
                continue
            q = dict(p)
            if p["kind"] == "face":
                q["position"] = mirror(p["position"])
            memo[p["pid"]] = q
            out.append(q)
        return new, out
    if kind == "X2 id permutation":
        perms = []
        for key in ("vertices", "edges", "faces"):
            xs = ids(key)
            ys = list(xs)
            rnd.shuffle(ys)
            perms.append(dict(zip(xs, ys)))
        pv, pe, pf = perms
        return remap_state(state, pv, pe, pf), remap_path(path, pv, pe, pf)
    if kind == "X3 boundary rotation":
        new = {**state, "faces": {}}
        for f, b in state["faces"].items():
            k = rnd.randrange(len(b))
            new["faces"][f] = b[k:] + b[:k]
        return new, [dict(p) if p["kind"] == "break" else p for p in path]
    if kind == "X4 edge orientation":
        new = {**state, "edges": {e: {**d, "v0": d["v1"], "v1": d["v0"]} for e, d in state["edges"].items()}}
        memo, out = {}, []
        for p in path:
            if p["kind"] == "break" or p["pid"] in memo:
                out.append(dict(p) if p["kind"] == "break" else memo[p["pid"]])
                continue
            q = dict(p)
            if p["kind"] == "edge":
                q["t"] = 1.0 - p["t"]
            memo[p["pid"]] = q
            out.append(q)
        return new, out
    raise ValueError(kind)


def resolved_faces(state, path, reflect_back=False):
    mesh = Mesh.from_state(state)
    kr.resolve_cross_face(mesh, path, state)
    check = kr.check_commit(mesh, state)
    if check.after_state is None:
        return None
    faces = [c for _cls, c in canon_faces(mesh)]
    if reflect_back:
        faces = [mirror_canon(c) for c in faces]
    return sorted(faces)


def rounded(faces, digits=9):
    return sorted(tuple(tuple(round(x, digits) for x in p) for p in c) for c in faces)


def k9(args, fuzz) -> None:
    section("K9 - order / id dependence inside the resolver")
    sites = [
        ["knife_resolve.py:184-188", "select_bridge", "distance tie -> boundary vertex position, loop point position (lexicographic)", "reflection flips x order"],
        ["knife_resolve.py:286-287", "close_loop_at_vertex", "(outside first, distance, loop point pos, boundary pos)", "reflection flips x order"],
        ["knife_resolve.py:942-943", "CrossFaceResolver._tail_corners", "(distance rounded 9, corner position)", "reflection flips x order"],
        ["knife_resolve.py:552, 584", "KnifeResolver._step_from", "faces in FaceId order; first wins on a tilt tie (< best - GEO_EPS)", "FaceId order"],
        ["knife_resolve.py:772-778", "KnifeResolver._build_loops", "first face (FaceId order) where the probe point is inside", "FaceId order"],
        ["knife_resolve.py:184/286 (_TIE_DIGITS=9)", "select_bridge / close_loop_at_vertex", "round(d, 9): near-ties become ties", "rounding"],
        ["knife_resolve.py:991", "_merge_repeated_points", "key (edge id, round(t, 9))", "edge orientation (t vs 1-t)"],
        ["knife_resolve.py:506-518", "_run_end_vertex", "t within GEO_EPS = same split; split_edge(piece, u or 1-u)", "edge orientation"],
        ["knife_resolve.py:954, 760", "_record_new_vertices / vertex_at", "position match < 1e-9 / <= 1e-12", "float noise"],
        ["face_geometry.py:104-111", "FaceFrame", "origin = first boundary vertex; u from a fixed axis", "boundary start / direction"],
        ["knife_planner.py:154, 164", "_pick_face_at / _face_in_direction", "faces in FaceId order (camera)", "FaceId order"],
        ["knife.py:411", "KnifeTool._link", "any() over shared faces in FaceId order", "none (any)"],
        ["symmetry_coordination.py:67", "SymmetryIndex face lookup", "duplicate vertex set -> lowest FaceId", "FaceId order"],
    ]
    table(["file:line", "site", "rule", "what a mirror changes"], sites)

    print("\nThe four ways the mirror side differs from the source, isolated (one-sided resolve of every fuzz path, "
          "result compared position-canonically with the original; X1 compared after reflecting back):")
    rows = []
    for asset, sessions in fuzz.items():
        rnd = random.Random(args.seed + 9)
        use = [s for s in sessions if s.ref_ok][: (60 if args.quick else 300)]
        for kind in ("X1 reflect", "X2 id permutation", "X3 boundary rotation", "X4 edge orientation"):
            st = collections.Counter()
            TIES.clear()
            for s in use:
                base = resolved_faces(s.state, s.path)
                new_state, new_path = variant(kind, s.state, s.path, rnd)
                with tie_counters():
                    other = resolved_faces(new_state, new_path, reflect_back=(kind == "X1 reflect"))
                st["n"] += 1
                if other is None or base is None:
                    st["one side rolled back / nothing"] += 1
                elif other == base:
                    st["identical"] += 1
                elif rounded(other) == rounded(base):
                    st["float only"] += 1
                else:
                    st["topology"] += 1
            n = st["n"]
            rows.append([asset, kind, n, pct(st["identical"], n), pct(st["float only"], n), pct(st["topology"], n),
                         st["one side rolled back / nothing"]])
    table(["asset", "variant", "paths", "identical", "positions differ < 1e-9 only", "topology differs",
           "rolled back on one side"], rows)
    TIES.clear()
    with tie_counters():
        for asset, sessions in fuzz.items():
            for s in sessions[: (60 if args.quick else 300)]:
                resolved_faces(s.state, s.path)
    print("\nTie-break counters over the same fuzz paths (one-sided resolve):")
    table(["site", "count"], [[k, v] for k, v in sorted(TIES.items())])


# -- K11: preview -------------------------------------------------------------------------------

def k11(args, fuzz) -> None:
    section("K11 - preview data: what of KnifeRenderData mirrors by mirror_position alone, and its cost")
    mesh = fresh("head_basemesh")
    t0 = time.perf_counter()
    for _ in range(20):
        SymmetryIndex(mesh)
    index_ms = 1000 * (time.perf_counter() - t0) / 20
    mir = Mirror(mesh)
    exact_edges = sum(
        1 for e in mesh.all_edge_ids()
        if mir.index.edge_partner(e) is not None
        and sorted(mirror(vpos(mesh, v)) for v in mesh.edge_vertices(e))
        == sorted(tuple(vpos(mesh, v)) for v in mesh.edge_vertices(mir.index.edge_partner(e))))
    fields = [
        ["start_point", "world position", "yes", "a seam point is its own mirror"],
        ["prospective_point", "world position", "position yes; validity no",
         "needs the partner check of the hovered target (no partner / self-mirrored face -> not clickable)"],
        ["target_edge", "segment", "yes (= partner edge exactly on E1 planes)", f"{exact_edges}/{len(mesh.all_edge_ids())} head edges"],
        ["line_preview", "segment", "yes", "a rubber band crossing the plane mirrors into an X"],
        ["path_segments", "segments", "yes", "skips / space stretches already absent"],
        ["placed_points", "positions", "yes", "seam points drawn twice on top of each other"],
        ["prospective_crossings", "positions", "only for (i)", "the hover's crossings were planned for the source camera"],
    ]
    table(["field", "type", "mirror_position alone?", "note"], fields)
    rows = []
    sessions = [s for s in fuzz["head_basemesh"] if s.ref_ok][:50]
    for npts in (8, 50, 200):
        times = []
        for s in sessions[:20]:
            path = scaled_path(s.knife.path, npts)
            data = build_knife_render_data(mesh, path, None, None, ())
            t0 = time.perf_counter()
            for _ in range(10):
                mirrored = (
                    None if data.start_point is None else mirror(data.start_point),
                    tuple(mirror(p) for p in data.placed_points),
                    tuple((mirror(a), mirror(b)) for a, b in data.path_segments),
                    tuple(mirror(c) for c in data.prospective_crossings),
                )
            times.append(1000 * (time.perf_counter() - t0) / 10)
        rows.append([npts, f"{statistics.median(times):.3f}", len(mirrored[1])])
    table(["path points", "mirror all fields, median ms per frame", "placed points mirrored (last)"], rows,
          f"SymmetryIndex for the hover partner check, built once per session: {index_ms:.2f} ms (head_basemesh); "
          "a lookup is a dict access.")
    # mirrored records vs mirrored preview positions
    worst = 0.0
    n = 0
    for s in sessions:
        try:
            mpath = mir.path(s.path)
        except Unmirrorable:
            continue
        a = build_knife_render_data(mesh, s.path, None, None, ())
        b = build_knife_render_data(mesh, mpath, None, None, ())
        for p, q in zip(a.placed_points, b.placed_points):
            worst = max(worst, math.dist(mirror(p), q))
            n += 1
    print(f"Mirror of the source preview vs. preview of the mirrored records: {n} placed points, largest distance "
          f"{worst:.2e} (edge points on orientation-reversed edges: t -> 1 - t, P3).")


def scaled_path(path, npts):
    """The session path repeated (pids relabelled per copy, chains separated by a lift) to ~`npts` points."""
    out = []
    copy = 0
    while sum(1 for p in out if p["kind"] != "break") < npts and path:
        out.extend(dict(p) if p["kind"] == "break" else {**p, "pid": (copy, p["pid"])} for p in path)
        out.append(dict(LIFT))
        copy += 1
    return out


# -- K-D: non-symmetric behaviour with no plane -----------------------------------------------

def kd_golden(args) -> None:
    section("K-D - would the mirror-aware key change the non-symmetric Knife? (no plane given)")
    try:
        from playground.tests.knife_golden_driver import GOLDEN_PATH, dumps, record_all
    except Exception as exc:  # noqa: BLE001
        print(f"golden driver not importable here ({type(exc).__name__}: {exc}); skipped")
        return
    t0 = time.perf_counter()
    with kd_tiebreaks(None), quiet():
        text = dumps(record_all())
    same = text == GOLDEN_PATH.read_text(encoding="utf-8")
    print(f"playground/tests golden net (345 seeded sessions + recorded sequences) with the K-D keys and plane=None: "
          f"byte-identical = {same} ({time.perf_counter() - t0:.1f} s)")
    # The parity rows of the Production KnifeTool, if pytest is installed (optional; the probe needs no pytest).
    try:
        import pytest
    except ImportError:
        print("tests/test_knife_parity.py: pytest not installed here; skipped")
        return
    with kd_tiebreaks(None), quiet():
        code = pytest.main(["-q", "-p", "no:cacheprovider", str(REPO / "tests" / "test_knife_parity.py")])
    print(f"tests/test_knife_parity.py with the K-D keys and plane=None: pytest exit code {int(code)} "
          f"(0 = all passed)")
    # By construction: with no plane `_kd_key` returns `tuple(p)`, the original key.


# =============================================================================================
# KC - K-C + side rule + clip (Type C handoff 2026-10-09; review CLAUDE-001 B1 / Q6 / R9; Manu F1 = C)
# =============================================================================================
#
# Throwaway probe code for the decision preparation (the review's scratch probes A-D reused where they
# fit; nothing here is a proposal for a module layout). The clip acts on the session path *before* the
# resolver - in production that is the Knife's commit coordinator; the resolver stays unchanged and
# camera-free (AD-017 #1). Rules as run:
#
#   side of a record   exact sign of its plane coordinate on the session-start mesh (AR-1, no tolerance);
#                      0 = on the plane (a seam vertex, an edge point on a seam edge): both sides
#   working side       the side of the first *mesh* record (vertex / edge / face, clicked or a planner
#                      crossing) off the plane. A point in space does not choose it: it is not cut, and
#                      its plane coordinate is the arbitrary depth `space_point` gives it (refinement of
#                      the planner's reading; how often it would matter is counted)
#   refusal            a cut segment (no break between) from a working-side record straight to an
#                      other-side record: the plane is crossed inside a face, there is no seam record to
#                      clip at (AD-SYM-03 item 9 interim rule)
#   clip               every maximal stretch of records on the other side (mesh records and points in
#                      space) becomes one pen lift, the breaks inside it go with it; a record on the plane
#                      (seam vertex, seam edge point) ends or starts a run there. A cyclic chain with such
#                      a stretch is first rotated to start right after its last other-side stretch, so
#                      its closing segment stays a cut
#   kept-call guard    every kept `split_edge` lies on the working side or on the plane, every kept
#                      `split_face` in a face of the working side; a face on / spanning the plane is
#                      refused (item 9). The net under the clip (B1: the side rule checked before the
#                      replay); it should never fire after the clip
#   replay             `replay_mirrored(..., strict=True)`: partners from the session-start state, N5
#                      refused, unknown call kinds refused; the "already cut by the source" collisions
#                      stay as a safety net (they should never fire after the clip)
#   E-b reference      the clipped path resolved alone, faces of the working side's class

is_break, is_chain_end = kr.is_break, kr.is_chain_end
LIFT_CLIP = {"kind": "break", "reason": "lift", "clip": True}
TEXT_PLANE_IN_FACE = "the plane is crossed inside a face: no seam point to clip at (item 9)"
TEXT_SEED_LOST = "a clipped closed chain whose interior start the next chain continues (not handled)"
KC_GATE: collections.Counter = collections.Counter()   # unions, E-b failures, duplicates, exceptions
KC_TOTALS: collections.Counter = collections.Counter()  # every K-C+clip run of the section (not a gate)


def plane_sign(x: float) -> int:
    return (x > 0.0) - (x < 0.0)


def record_side(mesh, p: dict) -> int:
    return plane_sign(target_world(mesh, p)[0])


def is_mesh_record(p: dict) -> bool:
    return p["kind"] in ("vertex", "edge", "face")


@dataclass
class SideRule:
    side: int = 0                      # working side +1 / -1; 0 = no mesh record off the plane
    path: list = field(default_factory=list)   # the clipped session path
    refusal: str | None = None
    stretches: int = 0                 # maximal other-side stretches replaced by one pen lift
    dropped: int = 0                   # records dropped (mesh records and points in space)
    dropped_space: int = 0
    rotated: int = 0                   # cyclic chains rotated before the clip
    side_with_space: int = 0           # what the side would be if points in space chose it too
    side_first_click: int = 0          # the side of the first *clicked* mesh record off the plane

    @property
    def clipped(self) -> bool:
        """Mesh records were dropped or a chain was rotated (a dropped point in space alone changes
        nothing the resolver sees)."""
        return self.dropped > self.dropped_space or self.rotated > 0


SIDE_READINGS = ("first record", "first click", "with space")


def side_rule(mesh, path: list[dict], reading: str = "first record") -> SideRule:
    """Working side, the item-9 refusal, and the clipped session path (rules in the section comment).
    `reading` (the open point of the working side, measured only where the readings disagree): "first
    record" = the first mesh record off the plane (planner's reading, the rule as run); "first click" = the
    first *clicked* mesh record off the plane (planner crossings do not choose; falls back to the first
    record); "with space" = the first record off the plane, points in space included."""
    rule = SideRule(path=list(path))
    side = {id(p): record_side(mesh, p) for p in path if not is_break(p)}
    sd_ = lambda p: side[id(p)]  # noqa: E731
    rule.side = next((sd_(p) for p in path if is_mesh_record(p) and sd_(p)), 0)
    rule.side_with_space = next((sd_(p) for p in path if not is_break(p) and sd_(p)), 0)
    rule.side_first_click = next((sd_(p) for p in path if is_mesh_record(p) and not p.get("crossing") and sd_(p)), 0)
    if reading == "first click" and rule.side_first_click:
        rule.side = rule.side_first_click
    elif reading == "with space":
        rule.side = rule.side_with_space
    w = rule.side
    if not w:
        return rule                    # every record on the plane: nothing to clip (the replay decides)
    crossing = {w, -w}
    prev = first = None
    for p in path:                     # 1. a cut straight across the plane
        if is_break(p):
            if is_chain_end(p):
                if p.get("cyclic") and prev is not None and first is not None and {sd_(prev), sd_(first)} == crossing:
                    rule.refusal = TEXT_PLANE_IN_FACE
                    return rule
                first = None
            prev = None
            continue
        if first is None:
            first = p
        if prev is not None and {sd_(prev), sd_(p)} == crossing:
            rule.refusal = TEXT_PLANE_IN_FACE
            return rule
        prev = p
    out, cur = [], []                  # 2. rotate cyclic chains that hold an other-side stretch
    for i, p in enumerate(path):
        if not is_chain_end(p):
            cur.append(p)
            continue
        if p.get("cyclic") and any(sd_(q) == -w for q in cur if not is_break(q)):
            j = max(k for k, q in enumerate(cur) if not is_break(q) and sd_(q) == -w)
            start = cur[0]
            nxt = path[i + 1] if i + 1 < len(path) else None
            if start["kind"] == "face" and nxt is not None and not is_break(nxt) and nxt["pid"] == start["pid"]:
                rule.refusal = TEXT_SEED_LOST
                return rule
            cur = cur[j + 1:] + cur[:j + 1]
            rule.rotated += 1
            p = dict(LIFT_CLIP)        # no closing segment any more: it is inside the rotated chain
        out.extend(cur)
        out.append(p)
        cur = []
    out.extend(cur)
    clipped, off = [], False           # 3. clip
    for p in out:
        if is_break(p):
            if not off:
                clipped.append(p)
            continue
        if sd_(p) == -w:
            if not off:
                rule.stretches += 1
                if clipped and not is_chain_end(clipped[-1]):
                    clipped.append(dict(LIFT_CLIP))
            off = True
            rule.dropped += 1
            rule.dropped_space += p["kind"] == "space"
            continue
        off = False
        clipped.append(p)
    rule.path = clipped
    return rule


def guard_kept(mesh, kept, w: int) -> int:
    """The side rule on the kept mutations (raises `Unmirrorable`); returns the working side (taken from
    the first off-plane kept call when no record chose it)."""
    for c in kept:
        if c[0] == "split_edge":
            s = plane_sign(c[5][0])
        elif c[0] == "split_face":
            cls = face_class([vpos(mesh, v) for v in set(c[6][0]) | set(c[6][1])])
            if cls in ("0", "span"):
                raise Unmirrorable("kept cut inside a face on / spanning the plane (item 9)")
            s = 1 if cls == "+" else -1
        else:
            raise Unmirrorable(f"unknown kept call {c[0]!r} (fail-closed)")
        if s and not w:
            w = s
        if s and s != w:
            raise Unmirrorable("kept mutation on the other side (side rule)")
    return w


def session_path(s) -> list[dict]:
    """The full session path (points in space included) - what the commit coordinator would clip."""
    knife = getattr(s, "knife", None)
    return knife.path if knife is not None else list(s.path)


def clipped_reference(state: dict, rpath: list[dict], cls: str):
    ref = Mesh.from_state(state)
    kr.resolve_cross_face(ref, rpath, state)
    check = kr.check_commit(ref, state)
    if check.after_state is None:
        return None
    return sorted(c for k, c in canon_faces(ref) if k == cls)


def run_kc_clip(s: Session, reading: str = "first record") -> Res:
    """K-C+clip: side rule -> clip -> resolve -> kept-call log -> guard -> mirrored replay -> S1 ->
    `check_commit` -> E-a..E-d (E-b against the clipped path resolved alone) + duplicate vertices."""
    r = Res("K-C+clip")
    mesh = Mesh.from_state(s.state)
    full = session_path(s)
    t0 = time.perf_counter()
    try:
        mir = Mirror(mesh)                       # partners from the session-start state (N8)
        t_rule = time.perf_counter()
        rule = side_rule(mesh, full, reading)
        r.info["rule"] = rule
        r.info["clip_ms"] = 1000 * (time.perf_counter() - t_rule)
        if rule.refusal:
            raise Unmirrorable(rule.refusal)
        rpath = [p for p in rule.path if p["kind"] != "space"]
        with KeptLog(mesh) as log:
            kr.CrossFaceResolver(mesh, s.state).resolve(rpath)
        kept = list(log.calls)
        w = guard_kept(mesh, kept, rule.side)
        r.info["side"] = w
        r.info["replayed"] = replay_mirrored(mesh, kept, mir, strict=True)
        apply_s1(mesh, kept)
        check = kr.check_commit(mesh, s.state)
    except Unmirrorable as exc:
        r.ms = 1000 * (time.perf_counter() - t0)
        r.status = f"refused: {exc}"
        Mesh.load_state(mesh, s.state)           # N8: the source mutations are taken back; no history entry
        r.info["restored"] = kr.mesh_content(mesh.export_state()) == kr.mesh_content(s.state)
        return r
    except Exception as exc:  # noqa: BLE001 - counted, not hidden
        r.ms = 1000 * (time.perf_counter() - t0)
        r.status = f"exception: {type(exc).__name__}: {str(exc)[:60]}"
        r.info["trace"] = traceback.format_exc()
        return r
    r.ms = 1000 * (time.perf_counter() - t0)
    if check.rolled_back:
        r.status = f"rolled back: {check.problem}"
        return r
    if check.after_state is None:
        r.status = "nothing"
        return r
    r.mesh = mesh
    cls = "-" if w < 0 else "+"
    ref = s.ref_plus if (not rule.clipped and cls == "+") else clipped_reference(s.state, rpath, cls)
    evaluate(r, s, mesh, check.after_state, ref=ref, side_cls=cls)
    r.info["dup"] = duplicates(mesh)
    return r


def describe_clip(r: Res) -> str:
    if not r.ok:
        return r.status
    same, near = r.info["dup"]
    return f"E {r.flags()} dup {same}/{near}"


def rule_cell(r: Res) -> str:
    rule = r.info.get("rule")
    if rule is None:
        return "-"
    w = {1: "+X", -1: "-X", 0: "?"}[rule.side]
    if rule.refusal:
        return f"{w}, refused by the rule"
    if not rule.stretches and not rule.rotated:
        return f"{w}, no clip"
    return f"{w}, {rule.stretches} stretch(es) -> lift, {rule.dropped} rec dropped" + \
        (f" ({rule.dropped_space} space)" if rule.dropped_space else "") + (f", {rule.rotated} rotated" if rule.rotated else "")


class ClipTally:
    """Counts per sample: rule, E-a..E-d, refusals by reason, unions, duplicates, timings; K-C before."""

    def __init__(self, label: str):
        self.label = label
        self.c = collections.Counter()
        self.reasons = collections.Counter()
        self.ms, self.clip_ms, self.kc_ms = [], [], []
        self.examples: list[str] = []

    def add(self, r: Res, old: Res | None = None) -> None:
        c = self.c
        c["n"] += 1
        KC_TOTALS["runs"] += 1
        KC_TOTALS["committed, E ++++"] += bool(r.ok and r.ea and r.eb and r.ec and r.ed)
        KC_TOTALS["refused"] += r.status.startswith("refused")
        KC_TOTALS["refused, session-start state restored"] += bool(r.info.get("restored"))
        KC_TOTALS["nothing cut"] += r.status == "nothing"
        KC_TOTALS["kept mutation on the other side (guard)"] += r.status.endswith("(side rule)")
        KC_TOTALS["collision (already cut by the source)"] += "already cut by the source" in r.status
        rule = r.info.get("rule")
        if rule is not None:
            c[{1: "w+", -1: "w-", 0: "w?"}[rule.side]] += 1
            c["clipped"] += rule.clipped
            c["rotated"] += rule.rotated > 0
            c["space only"] += (rule.dropped_space > 0 and not rule.clipped)
            c["first click other side"] += bool(rule.side and rule.side_first_click and rule.side_first_click != rule.side)
            c["space would choose other side"] += bool(rule.side and rule.side_with_space and rule.side_with_space != rule.side)
        if r.ok:
            c["committed"] += 1
            for k in ("ea", "eb", "ec", "ed"):
                c[k] += bool(getattr(r, k))
            all4 = bool(r.ea and r.eb and r.ec and r.ed)
            c["all4"] += all4
            union = bool(r.ea and r.eb is False)
            c["union"] += union
            same, near = r.info["dup"]
            c["dup"] += same + near
            KC_GATE["union (E-a+, E-b-)"] += union
            KC_GATE["E-b failure"] += r.eb is False
            KC_GATE["duplicate vertices"] += same + near
            KC_GATE["committed, not all four"] += not all4
            if not all4 and len(self.examples) < 3:
                self.examples.append(f"{describe_clip(r)}; {rule_cell(r)}")
        elif r.status.startswith("refused"):
            c["refused"] += 1
            self.reasons[r.status[len("refused: "):]] += 1
            c["restored"] += bool(r.info.get("restored"))
        elif r.status.startswith("exception"):
            c["exception"] += 1
            KC_GATE["exception"] += 1
            if len(self.examples) < 3:
                self.examples.append(r.status)
        elif r.status.startswith("rolled back"):
            c["rolled back"] += 1
        else:
            c["nothing"] += 1
        self.ms.append(r.ms)
        self.clip_ms.append(r.info.get("clip_ms", 0.0))
        if old is not None:
            c["old n"] += 1
            c["old all4"] += bool(old.ok and old.ea and old.eb and old.ec and old.ed)
            c["old union"] += bool(old.ok and old.ea and old.eb is False)
            c["old refused"] += old.status.startswith("refused")
            self.kc_ms.append(old.ms)

    def row(self) -> list:
        c, n = self.c, self.c["n"]
        k = c["committed"]
        med = lambda xs: f"{statistics.median(xs):.2f}" if xs else "-"  # noqa: E731
        p95 = lambda xs: f"{sorted(xs)[int(0.95 * (len(xs) - 1))]:.2f}" if xs else "-"  # noqa: E731
        old = (f"{c['old all4']} / {c['old union']} / {c['old refused']}" if c["old n"] else "-")
        return [self.label, n, f"{c['w+']}/{c['w-']}/{c['w?']}", f"{c['clipped']} ({c['rotated']})",
                f"{c['first click other side']} / {c['space would choose other side']}",
                f"{c['ea']}/{k}", f"{c['eb']}/{k}", f"{c['ec']}/{k}", f"{c['ed']}/{k}", pct(c["all4"], n),
                c["refused"], f"{c['nothing']} / {c['rolled back']}", c["union"], c["dup"], c["exception"], old,
                f"{med(self.ms)} / {p95(self.ms)}", med(self.clip_ms), med(self.kc_ms)]


TALLY_HEADER = ["sample", "n", "side +/-/?", "clipped (rotated)", "1st click / space other side", "E-a", "E-b", "E-c",
                "E-d", "all four", "refused", "nothing / rolled back", "union", "dup", "exc",
                "K-C before: all four / union / refused", "K-C+clip ms med / p95", "rule+clip ms", "K-C ms med"]
TALLY_NOTE = ("side = working side by the first mesh record off the plane (? = none); clipped = mesh records dropped "
              "or a chain rotated; '1st click / space other side' = sessions whose first *clicked* record, resp. "
              "whose first record including points in space, lies on the other side; E-x = passes / committed; "
              "union = E-a passes, E-b fails (B1); dup = duplicate vertex pairs (identical + < 1e-9, N4); "
              "K-C before = the K-C method of 2026-10-08 on the same session (E-b against the unclipped path).")


def print_tallies(tallies: list[ClipTally], title: str) -> None:
    print(f"\n{title}")
    table(TALLY_HEADER, [t.row() for t in tallies], TALLY_NOTE)
    rows = [[t.label, reason, n] for t in tallies for reason, n in sorted(t.reasons.items(), key=lambda kv: -kv[1])]
    if rows:
        print("refusals by reason (every refusal restored the session-start state: "
              f"{sum(t.c['restored'] for t in tallies)}/{sum(t.c['refused'] for t in tallies)}):")
        table(["sample", "reason", "n"], rows)
    for t in tallies:
        for ex in t.examples:
            print(f"  {t.label}: {ex}")


def records_string(mesh, path) -> str:
    """One character per record: + / - / 0 by side, | for a break, s for a point in space."""
    out = []
    for p in path:
        if is_break(p):
            out.append("|")
        else:
            ch = {1: "+", -1: "-", 0: "0"}[record_side(mesh, p)]
            out.append(ch if p["kind"] != "space" else "s")
    return "".join(out)


# -- samples (review CLAUDE-001 probes A-D, reused) ---------------------------------------------

def _xy(m):
    return {tuple(vpos(m, v)[:2]): v for v in m.all_vertex_ids()}


def grid_edge(m, p, q):
    pos = _xy(m)
    return kr.find_edge(m, pos[p], pos[q])


def grid_edge_point(m, p, q, at) -> dict:
    """A click on the tie_grid edge p-q at the point `at` (t from the edge's stored orientation)."""
    e = grid_edge(m, p, q)
    a = vpos(m, m.edge_vertices(e)[0])
    return T_e(e, math.dist(a[:2], at) / math.dist(p, q))


def loop_cases() -> list[tuple[str, str, list]]:
    """Closed chains across the seam on tie_grid (squares (0,1) on +X and (-1,1) on -X): the cyclic rotation
    before the clip, and a loop whose interior start the next chain continues (refused by the probe clip)."""
    m = fresh("tie_grid")
    ge = lambda p, q, at: ("click", grid_edge_point(m, p, q, at))  # noqa: E731
    loop = [ge((0.0, 1.0), (1.0, 1.0), (0.5, 1.0)), ge((0.0, 1.0), (0.0, 2.0), (0.0, 1.5)),
            ge((-1.0, 1.0), (0.0, 1.0), (-0.5, 1.0)), ge((-1.0, 2.0), (0.0, 2.0), (-0.5, 2.0)),
            ge((0.0, 2.0), (0.0, 3.0), (0.0, 2.5)), ge((0.0, 2.0), (1.0, 2.0), (0.5, 2.0)), ("click", T_p(0))]
    f = next(x for x in plus_faces(m) if {tuple(vpos(m, v)[:2]) for v in m.face_vertices(x)}
             == {(0.0, 1.0), (1.0, 1.0), (1.0, 2.0), (0.0, 2.0)})
    seeded = [("click", T_f(f, (0.5, 1.5, 0.0))), ge((0.0, 1.0), (0.0, 2.0), (0.0, 1.75)),
              ge((-1.0, 1.0), (0.0, 1.0), (-0.5, 1.0)), ge((-1.0, 2.0), (0.0, 2.0), (-0.5, 2.0)),
              ge((0.0, 1.0), (0.0, 2.0), (0.0, 1.25)), ("click", T_p(0)), ge((1.0, 1.0), (1.0, 2.0), (1.0, 1.5))]
    return [("tie_grid", "closed loop across the seam (cyclic chain, rotated before the clip)", loop),
            ("tie_grid", "the same with an interior start the next chain continues from", seeded)]


def r1_cases() -> list[tuple[str, str, list]]:
    """R1 (probe A): a +X chain and a -X chain after a pen lift (Manu: 'Fall 3'), one chain entirely on -X,
    the head two-chain path; plus the same two chains in the other order (the working side becomes -X)."""
    m = fresh("tie_grid")
    e1a, e1b = grid_edge(m, (1.0, 0.0), (1.0, 1.0)), grid_edge(m, (2.0, 0.0), (2.0, 1.0))
    e2a, e2b = grid_edge(m, (-3.0, 2.0), (-3.0, 3.0)), grid_edge(m, (-2.0, 2.0), (-2.0, 3.0))
    plus = [("click", T_e(e1a, 0.3)), ("click", T_e(e1b, 0.6))]
    minus = [("click", T_e(e2a, 0.4)), ("click", T_e(e2b, 0.7))]
    out = [("tie_grid", "R1 +X chain, lift, -X chain (non-partner face)", plus + [("lift",)] + minus),
           ("tie_grid", "R1 one chain entirely on -X", minus),
           ("tie_grid", "R1' -X chain, lift, +X chain (started on -X)", minus + [("lift",)] + plus)]
    h = fresh("head_basemesh")
    mir = Mirror(h)
    pf = plus_faces(h, strict=True)
    fa = pf[0]
    fb = next(f for f in pf[40:] if not set(h.face_vertices(f)) & set(h.face_vertices(fa)))
    gb = mir.fp[fb]
    ea, eb = h.face_edges(fa)[0], h.face_edges(fa)[2]
    ga, gbb = h.face_edges(gb)[0], h.face_edges(gb)[2]
    out.append(("head_basemesh", f"R1 head: +X chain in f{int(fa)}, lift, -X chain in f{int(gb)}",
                [("click", T_e(ea, 0.3)), ("click", T_e(eb, 0.6)), ("lift",),
                 ("click", T_e(ga, 0.4)), ("click", T_e(gbb, 0.7))]))
    return out


def seam_vertex_crossings(asset: str, limit: int = 40) -> list[tuple]:
    """R8 (probe C): edge point in F (+X) -> seam vertex s -> edge point in H (-X), H != partner(F), both
    edges not touching s. One per (s, F, H) until `limit`."""
    m = fresh(asset)
    mir = Mirror(m)
    svs = seam_vertices(m)
    plus, minus = set(plus_faces(m)), set()
    for f in m.all_face_ids():
        xs = [vpos(m, v)[0] for v in m.face_vertices(f)]
        if max(xs) <= 0.0 and min(xs) < 0.0:
            minus.add(f)
    out = []
    for s in sorted(svs):
        around = {f for e in m.vertex_edges(s) for f in m.edge_faces(e)}
        for F in sorted(around & plus):
            for H in sorted(around & minus):
                if mir.fp.get(F) == H:
                    continue
                ef = next((e for e in m.face_edges(F) if s not in m.edge_vertices(e)), None)
                eh = next((e for e in m.face_edges(H) if s not in m.edge_vertices(e)), None)
                if ef is None or eh is None:
                    continue
                out.append((F, H, [("click", T_e(ef, 0.4)), ("click", T_v(s)), ("click", T_e(eh, 0.6))]))
                if len(out) >= limit:
                    return out
    return out


def seam_fuzz(name: str, rnd: random.Random, n: int) -> list[Session]:
    """R7 (probe B): +X faces touching the seam only, targets biased to seam vertices / seam edges /
    near-seam face points. Same RNG use as the review's probe (the session keeps its knife)."""
    mesh0 = fresh(name)
    svs = seam_vertices(mesh0)
    seam = mesh0.symmetry_definition.seam_edges
    faces = [f for f in plus_faces(mesh0) if set(mesh0.face_vertices(f)) & svs]
    allowed = set(plus_faces(mesh0))
    out = []

    def target(mesh, f):
        vs, es = mesh.face_vertices(f), mesh.face_edges(f)
        r = rnd.random()
        if r < 0.3:
            sv = [v for v in vs if v in svs]
            return T_v(rnd.choice(sv) if sv and rnd.random() < 0.7 else rnd.choice(vs))
        if r < 0.75:
            se = [e for e in es if e in seam]
            e = rnd.choice(se) if se and rnd.random() < 0.6 else rnd.choice(es)
            return T_e(e, 0.5 if rnd.random() < 0.3 else rnd.uniform(0.08, 0.92))
        pts = [vpos(mesh, v) for v in vs]
        w = [rnd.uniform(1.0, 3.0) if v in svs else rnd.uniform(0.2, 1.0) for v in vs]
        tot = sum(w)
        return T_f(f, tuple(sum(w[i] * pts[i][k] for i in range(len(pts))) / tot for k in range(3)))

    for _ in range(n):
        mesh = Mesh.from_state(start_state(name))
        knife = new_knife(mesh)
        acts, goal, clicks, tries = [], rnd.randint(2, 8), 0, 0
        while clicks < goal and tries < goal * 10:
            tries += 1
            r = rnd.random()
            act = None
            chain = knife.chain_points
            if chain and len([p for p in chain if not p.get("crossing")]) >= 3 and r < 0.12:
                first = chain[0]
                act = ("click", T_v(first["vertex_id"]) if first["kind"] == "vertex" else T_p(first["pid"]))
            elif knife.last_point is not None and r < 0.18:
                act = ("lift",)
            elif r < 0.22 and knife.snap_points:
                own = [p for p in knife.snap_points if p["kind"] in ("edge", "vertex")]
                if own:
                    p = rnd.choice(own)
                    act = ("click", T_v(p["vertex_id"]) if p["kind"] == "vertex" else T_p(p["pid"]))
            if act is None:
                last = knife.last_point
                cand = [f for f in point_faces(mesh, last) if f in allowed] if last is not None else []
                f = rnd.choice(cand) if cand and rnd.random() < 0.8 else rnd.choice(faces)
                act = ("click", target(mesh, f))
            with quiet():
                ok = knife.click(act[1]) if act[0] == "click" else knife.lift()
            acts.append(act)
            if ok and act[0] == "click":
                clicks += 1
        s = Session(name, resolver_path(knife))
        s.knife = knife
        out.append(s)
    return out


def camera_samples(args) -> list[tuple]:
    """Every K4 / K5 session (section, mesh, camera, index, session): the stash of K4 / K5, or the same
    sessions regenerated with the same seeds when those sections did not run."""
    have = {x[0] for x in CAMERA_SAMPLES}
    out = list(CAMERA_SAMPLES)
    if "K4" not in have:
        rnd, n = random.Random(args.seed + 4), (12 if args.quick else 60)
        for cam_key in CAMERAS:
            for i in range(n):
                out.append(("K4", "head_basemesh", cam_key, i,
                            camera_session("head_basemesh", rnd, cam_key, rnd.randint(2, 6), p_space=0.0)))
    if "K5" not in have:
        rnd, n = random.Random(args.seed + 5), (10 if args.quick else 40)
        for name, cam_key in K5_SAMPLES:
            for i in range(n):
                out.append(("K5", name, cam_key, i, camera_session(name, rnd, cam_key, rnd.randint(2, 6), p_space=0.3)))
    order = {"K4": 0, "K5": 1}
    return sorted(out, key=lambda x: order[x[0]])


def kc_case_rows(cases) -> list[list]:
    rows = []
    for name, label, actions in cases:
        s = session_from(name, actions)
        old, new = run("K-C", s), run_kc_clip(s)
        tally = ClipTally(label)
        tally.add(new, old)             # feeds KC_GATE
        mesh = Mesh.from_state(s.state)
        rows.append([name, label, "".join("y" if a else "n" for a in s.accepted),
                     records_string(mesh, session_path(s)), rule_cell(new),
                     "ok" if s.ref_ok else f"src: {s.ref_problem or 'nothing'}", describe(old), describe_clip(new)])
    return rows


CASE_CLIP_HEADER = ["mesh", "case", "accepted", "records", "working side, clip", "unclipped source alone", "K-C (2026-10-08)",
                    "K-C+clip"]
CASE_CLIP_NOTE = ("records: + / - / 0 per record by side, | a break, s a point in space. K-C+clip E flags: E-b against "
                  "the clipped path resolved alone, on the working side; dup = duplicate vertex pairs identical / "
                  "< 1e-9 (N4).")


def kc_n5() -> None:
    print("\nN5 - a self-partner edge that crosses the plane (both ends off the plane, mirror images of each other):")
    counts = []
    for asset in ("subd_cube", "head_basemesh", "man_with_shoes_basemesh", "tie_grid", "span_grid"):
        m = fresh(asset)
        idx = SymmetryIndex(m)
        n = sum(1 for e in m.all_edge_ids() if idx.edge_partner(e) == e
                and any(vpos(m, v)[0] != 0.0 for v in m.edge_vertices(e)))
        counts.append(f"{asset} {n}")
    print("  such edges at session start: " + ", ".join(counts))
    sp = fresh("span_grid")
    pos = {tuple(vpos(sp, v)): v for v in sp.all_vertex_ids()}
    bottom = kr.find_edge(sp, pos[(-0.5, 0.0, 0.0)], pos[(0.5, 0.0, 0.0)])
    top = kr.find_edge(sp, pos[(-0.5, 1.0, 0.0)], pos[(0.5, 1.0, 0.0)])
    right = kr.find_edge(sp, pos[(0.5, 0.0, 0.0)], pos[(0.5, 1.0, 0.0)])
    rows = kc_case_rows([
        ("span_grid", "N5 path: crossing edge t=0.5 -> crossing edge t=0.5 (a chord in the plane)",
         [("click", T_e(bottom, 0.5)), ("click", T_e(top, 0.5))]),
        ("span_grid", "N5 path: crossing edge t=0.5 -> right edge t=0.5 (into +X, same face)",
         [("click", T_e(bottom, 0.5)), ("click", T_e(right, 0.5))]),
    ])
    table(CASE_CLIP_HEADER, rows, CASE_CLIP_NOTE)
    # The halves question in isolation: a hand-made kept log (the resolver never makes it without a
    # split_face in the self-mirrored face): split the crossing edge at its midpoint (on the plane), then
    # split its +X half at its midpoint (x = 0.25).
    out = []
    for mode in ("identity halves (K-C as run 2026-10-08)", "crossed halves", "strict: refuse (K-C+clip)"):
        m = fresh("span_grid")
        mir = Mirror(m)
        with KeptLog(m) as log:
            v, ha, hb = m.split_edge(bottom, 0.5)
            plus_half = ha if any(vpos(m, x)[0] > 0 for x in m.edge_vertices(ha)) else hb
            m.split_edge(plus_half, 0.5)
        kept = list(log.calls)
        try:
            replay_mirrored(m, kept, mir, strict=mode.startswith("strict"), crossed_n5=mode == "crossed halves")
            faces = [c for _k, c in canon_faces(m)]
            sym = sorted(faces) == sorted(mirror_canon(c) for c in faces)
            out.append([mode, "replayed", f"mirror-symmetric = {sym}, dup {'%d/%d' % duplicates(m)}"])
        except Unmirrorable as exc:
            out.append([mode, "refused", str(exc)])
    table(["half mapping", "result", "detail"], out)


def kc(args, fuzz) -> None:
    section("KC - K-C + side rule + clip (Manu 2026-10-09: F1 = C, the working side is where the cut starts)")
    KC_GATE.clear()
    KC_TOTALS.clear()
    print("Rules as run (section comment in the probe source): side = exact sign of the plane coordinate (0 = on the "
          "plane, both sides); working side = side of the first mesh record off the plane (points in space do not "
          "choose it); a cut straight across the plane (no seam record between) is refused (item 9); every maximal "
          "other-side stretch -> one pen lift (cyclic chains rotated first); kept-call guard; strict replay; E-b "
          "reference = the clipped path resolved alone.")
    t_sec = time.perf_counter()

    print("\nR1 / Fall 3 - two chains on both sides, one chain entirely on -X; closed chains across the seam:")
    table(CASE_CLIP_HEADER, kc_case_rows(r1_cases() + loop_cases()), CASE_CLIP_NOTE)

    print("\nR8 - one run through a seam VERTEX into a non-partner -X face (60 constructed paths):")
    tallies, examples = [], []
    for asset in ("tie_grid", "subd_cube", "head_basemesh"):
        t = ClipTally(f"R8 {asset}")
        example = None
        for F, H, acts in seam_vertex_crossings(asset):
            s = session_from(asset, acts)
            if not s.ref_ok:
                t.c["source invalid"] += 1
                continue
            old, new = run("K-C", s), run_kc_clip(s)
            t.add(new, old)
            if example is None:
                example = [asset, f"f{int(F)} -> seam vertex -> f{int(H)}", records_string(fresh(asset), session_path(s)),
                           rule_cell(new), describe(old), describe_clip(new)]
        tallies.append(t)
        if example is not None:
            examples.append(example)
    print_tallies(tallies, "R8 summary:")
    table(["mesh", "path", "records", "working side, clip", "K-C (2026-10-08)", "K-C+clip"], examples)

    print("\nK7 - every seam row (cube, head, tie grid; hexagon / span fixtures):")
    cases = [(asset, label, acts) for asset in ("subd_cube", "head_basemesh", "tie_grid")
             for label, acts in k7_cases(asset).items()]
    cases += [(name, label, acts) for (name, label), acts in k7_synthetic().items()]
    table(CASE_CLIP_HEADER, kc_case_rows(cases), CASE_CLIP_NOTE)

    print("\nK4 / K5 - camera sessions (the Discovery's seeds; the same sessions as K4 / K5 and the review's R2 / R9 / R10):")
    samples = camera_samples(args)
    tallies, by_key, r9, excluded, r10 = [], {}, ClipTally("R9: sessions K-C refused"), \
        ClipTally("K4/K5 sessions excluded there (unclipped source invalid)"), []
    alt_click = ClipTally("reading 'first click' where it disagrees")
    alt_space = ClipTally("reading 'with space' where it disagrees")
    alt_rows: list[list] = []
    for sec, name, cam_key, i, s in samples:
        key = (sec, name, cam_key)
        if key not in by_key:
            by_key[key] = ClipTally(f"{sec} {name} {cam_key}")
            tallies.append(by_key[key])
        if not s.ref_ok:
            excluded.add(run_kc_clip(s))
            continue
        old, new = run("K-C", s), run_kc_clip(s)
        by_key[key].add(new, old)
        if old.status.startswith("refused"):
            r9.add(new, old)
        rule = new.info.get("rule")
        if rule is not None and rule.side:
            if rule.side_first_click and rule.side_first_click != rule.side:
                alt_click.add(run_kc_clip(s, "first click"), new)
                kept_mesh = sum(1 for p in rule.path if is_mesh_record(p))
                alt_click.c["more mesh records dropped than kept"] += rule.dropped - rule.dropped_space > kept_mesh
                alt_click.c["started in space"] += next((p["kind"] for p in session_path(s) if not is_break(p)), "") == "space"
                alt_click.c["rule as run: nothing cut"] += new.status == "nothing"
                alt_rows.append([f"{sec} {name} {cam_key} #{i}", records_string(fresh(name), session_path(s)),
                                 "first click", rule_cell(new), describe_clip(new)])
            if rule.side_with_space and rule.side_with_space != rule.side:
                alt_space.add(run_kc_clip(s, "with space"), new)
        if sec == "K5" and name == "head_basemesh" and cam_key == "side (+X)" and i == 15:
            r10.append([f"{sec} {name} {cam_key} #{i}", records_string(fresh(name), session_path(s)),
                        rule_cell(new), describe(old), describe_clip(new)])
    print_tallies(tallies + [r9, excluded], "K4 / K5 summary (n = sessions whose unclipped source is valid, as in K4 / K5; "
                                           "the last row: the sessions K4 / K5 excluded):")
    print("\nR10 - the K5 session the review found committed as a union (head, side camera, #15):")
    table(["session", "records", "working side, clip", "K-C (2026-10-08)", "K-C+clip"], r10)
    print("\nOpen point of the working side: sessions where the first *clicked* mesh record, or the first record "
          "including points in space, lies on the other side than the first mesh record. Each is run again with "
          "that reading ('K-C before' column = the rule as run on the same session):")
    print_tallies([alt_click, alt_space], "Readings compared:")
    print(f"  'first click' disagreements: {alt_click.c['n']}, of these started with a point in space "
          f"{alt_click.c['started in space']}; the rule as run dropped more mesh records than it kept in "
          f"{alt_click.c['more mesh records dropped than kept']} and cut nothing at all in "
          f"{alt_click.c['rule as run: nothing cut']}")
    table(["session", "records", "reading", "rule as run (first record)", "result as run"], alt_rows[:8])

    print("\nK10 / R7 - camera-free fuzz on +X faces (K10, seed as K10) and the review's seam-biased fuzz (R7, seed + 77):")
    if not fuzz:
        rnd = random.Random(args.seed)
        fuzz = {a: fuzz_sessions_for(a, rnd, args.fuzz) for a in ("subd_cube", "head_basemesh", "tie_grid")}
    tallies = []
    for asset, sessions in fuzz.items():
        t = ClipTally(f"K10 {asset}")
        for s in sessions:
            if s.ref_ok:
                t.add(run_kc_clip(s), run("K-C", s))
        tallies.append(t)
    rnd = random.Random(args.seed + 77)
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        t = ClipTally(f"R7 {asset}")
        for s in seam_fuzz(asset, rnd, 60 if args.quick else 400):
            if s.ref_ok:
                t.c["touches seam"] += touches_seam(fresh(asset), s.path)
                t.add(run_kc_clip(s), run("K-C", s))
        tallies.append(t)
    print_tallies(tallies, "K10 / R7 summary:")
    print("  R7 paths with a record on the seam: " + ", ".join(f"{t.label[3:]} {t.c['touches seam']}" for t in tallies[3:]))

    kc_n5()

    print("\nKC totals over every K-C+clip run of this section (case rows, tallies, the readings compared): "
          + ", ".join(f"{k} {v}" for k, v in KC_TOTALS.items()))
    print(f"\nKC gate (handoff 2026-10-09 §3.1 target: every K-C+clip result = the clipped working-side cut + its exact "
          f"mirror, 0 unions): {dict(KC_GATE) if any(KC_GATE.values()) else 'all zero'} "
          f"({'TARGET MET' if not any(KC_GATE.values()) else 'STOP - see handoff §9'}; section {time.perf_counter() - t_sec:.1f} s)")


# =============================================================================================
# main
# =============================================================================================

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fuzz", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20261008)
    ap.add_argument("--quick", action="store_true", help="small fuzz and samples (smoke run)")
    ap.add_argument("--only", default="", help="comma-separated sections, e.g. K1,K7,K10")
    args = ap.parse_args(argv)
    if args.quick:
        args.fuzz = min(args.fuzz, 60)
    only = {x.strip().upper() for x in args.only.split(",") if x.strip()}
    want = lambda key: not only or key in only  # noqa: E731
    rnd = random.Random(args.seed)
    t_start = time.perf_counter()
    print("Symmetric Knife probe (AD-SYM-03 slice 6, Discovery). Plane x = 0 (Lab E1), seam by Lab E3. "
          f"exact plane: {is_exact_plane(SymmetryDefinition(ORIGIN, X_NORMAL, frozenset()))}")
    if want("K1"):
        k1(args)
    if want("K2"):
        k2(args)
    if want("K3"):
        k3(args)
    fuzz = {}
    if want("K10") or want("K6") or want("K9") or want("K11"):
        fuzz = k10(args, rnd)
    if want("K4"):
        k4(args)
    if want("K5"):
        k5(args)
    if want("K6"):
        k6(args, [s for s in fuzz.get("subd_cube", []) + fuzz.get("head_basemesh", []) + fuzz.get("tie_grid", [])
                  if s.ref_ok])
    if want("K7"):
        k7(args)
    if want("K8"):
        k8(args, rnd)
    if want("K9"):
        k9(args, fuzz)
    if want("K11"):
        k11(args, fuzz)
    if want("KD"):
        kd_golden(args)
    if want("KC"):
        kc(args, fuzz)
    print(f"\ndone in {time.perf_counter() - t_start:.1f} s")
    # Exit 1 only when the K-C+clip gate fails (a union, an E-b failure, a duplicate vertex, an exception or a
    # committed result that is not E ++++): the handoff's stop condition, made visible to the caller.
    return 1 if any(KC_GATE.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
