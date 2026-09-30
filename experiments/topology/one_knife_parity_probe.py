"""PROBE — One Knife: Production `KnifeTool` vs Lab Q5 `KnifeFaceCrossFace` on the same clicks.

Evidence for `docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md` (proposal, no decision).
Not a tool, not wired anywhere, no Core / Production / Playground change. Both engines are driven
through their public session interface only — `activate`, `begin`, `accepts`, `hover`, `click`,
`undo_step`, `redo_step`, `commit`, `cancel` (Q5 additionally `set_view`, the camera its planner needs) —
the way `src/mirai/application.py` and `playground/window.py` drive them.

Targets are written as world positions and resolved against each engine's *current* mesh: the
Production Knife cuts at every click (an edge it split is two edges now), Q5 changes nothing before
commit. A click on a point the Q5 session already holds becomes `{"kind": "path", "index": i}`, which
is what the window's 14 px snap (`snap_target`) turns such a click into.

Sections:
  --parity    same edge/vertex-only click lists on both engines: accepted clicks, resulting mesh
              (position-canonical), selection residue, mode, History entries, Undo/Redo after commit
  --session   in-session Undo/Redo (A->B->C, Undo, Redo), cancel, undo-everything-then-commit
  --defects   R3 / R5 (`playground/experiments/knife_face/decision.md`, "Q5 integrity findings") on
              Production-only sessions, the same clicks on Q5, and what a click-time geometric gate
              would say; R3 through Vertex Connect (the shared helper)
  --core      which public Core mutators each engine calls (outermost calls only), incl. face-interior cases
  --b2c       Q5's two bridge constructions rebuilt as two calls of the B2c-shaped path split
  --cost      wall-clock timings on `head` (headless, THIS machine — not the reference PC)

Run:  python experiments/topology/one_knife_parity_probe.py            # all sections
      python experiments/topology/one_knife_parity_probe.py --parity   # one section
"""

from __future__ import annotations

import argparse
import contextlib
import io
import math
import statistics
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
# src/ last-inserted = first on sys.path: the top-level `viewport` must resolve to src/viewport.
for _p in (str(_ROOT / "tests"), str(_ROOT / "examples"), str(_ROOT), str(_ROOT / "src")):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from core import Mesh, Scene  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj, create_cube  # noqa: E402
from mirai.topology.connect_per_face import TopologyToolError, connect_selected_edges_per_face  # noqa: E402
from mirai.topology.connect_vertices_per_face import connect_vertices_per_face  # noqa: E402
from mirai.topology.knife import KnifeTool  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from mirai.viewport.picking_cache import PickCache  # noqa: E402
from playground._paths import DEFAULT_HEAD_ASSET  # noqa: E402
from playground.experiments.knife_face.engine import (  # noqa: E402
    close_loop_at_vertex,
    close_loop_with_bridges,
    face_problem,
    segment_in_face,
    select_bridge,
    split_face_path,
)
from playground.experiments.knife_face.engine_q5 import KnifeFaceCrossFace  # noqa: E402

W, H = 1280, 800
EPS = 1e-9


# -- scenes ------------------------------------------------------------------------------

def build_grid(n: int = 4) -> Mesh:
    """n x n unit quads in z = 0 (same fixture as `playground/tests/test_knife_face_q5.py`)."""
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


def build_l_face() -> Mesh:
    """One concave L-shaped hexagon (an imported n-gon, or what a bent cut leaves behind):
    (0,0) (2,0) (2,1) (1,1) (1,2) (0,2) — the corner (2,2) is missing."""
    mesh = Mesh()
    vs = [mesh.add_vertex(p) for p in ((0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0))]
    mesh.add_face(vs)
    return mesh


def head_mesh() -> Mesh:
    return build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh


SCENES = {"grid": build_grid, "cube": create_cube, "L": build_l_face, "head": head_mesh}
CAMS = {"grid": (20.0, 35.0), "cube": (35.0, 30.0), "L": (0.0, 0.0), "head": (20.0, 10.0)}


def camera_for(mesh, yaw: float, pitch: float) -> OrbitCamera:
    cam = OrbitCamera(yaw=math.radians(yaw), pitch=math.radians(pitch))
    center, radius = mesh_center_and_radius(mesh)
    cam.frame_on_bounds(center, radius, margin=1.4)
    return cam


# -- sessions ----------------------------------------------------------------------------

@contextlib.contextmanager
def quiet():
    """`KnifeTool` prints its temporary [KNIFE] diagnosis trace on every call."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


class Session:
    """One engine session on its own mesh/scene. `engine` is "prod" or "q5"."""

    def __init__(self, engine: str, mesh: Mesh, scene_name: str, scene: Scene | None = None):
        self.engine = engine
        self.mesh = mesh
        self.scene = scene or Scene()
        self.scene.mesh = mesh
        self.tool = KnifeTool() if engine == "prod" else KnifeFaceCrossFace()
        with quiet():
            self.tool.activate()
            self.tool.begin(mesh=mesh, scene=self.scene, selection=self.scene.selection)
        if engine == "q5":
            self.tool.set_view(camera_for(mesh, *CAMS[scene_name]), W, H, occlusion=True)

    def target(self, spec) -> dict:
        return resolve(self.mesh, spec, self.tool if self.engine == "q5" else None)

    def click(self, spec) -> tuple[bool, bool, bool]:
        """(accepts before, hover valid before, click result)."""
        tgt = self.target(spec)
        with quiet():
            acc = self.tool.accepts(tgt)
            hov = bool(self.tool.hover(tgt).get("valid"))
            ok = self.tool.click(tgt)
        return acc, hov, ok

    def undo(self) -> bool:
        with quiet():
            return self.tool.undo_step()

    def redo(self) -> bool:
        with quiet():
            return self.tool.redo_step()

    def commit(self):
        with quiet():
            cmd = self.tool.commit()
            self.tool.deactivate()
        return cmd

    def cancel(self) -> None:
        with quiet():
            self.tool.cancel()
            self.tool.deactivate()


def _vid_at(mesh, pos):
    for v in mesh.all_vertex_ids():
        if math.dist(mesh.vertex_position(v), pos) < 1e-9:
            return v
    return None


def _q5_path_index(tool, mesh, pos):
    """The index of a clicked (not planner) point of the Q5 session at `pos` — the window's snap."""
    for i, p in enumerate(tool.path):
        if p["kind"] == "break" or p.get("crossing"):
            continue
        if p["kind"] == "face":
            q = p["position"]
        elif p["kind"] == "vertex":
            q = mesh.vertex_position(p["vertex_id"])
        else:
            a, b = (mesh.vertex_position(x) for x in mesh.edge_vertices(p["edge_id"]))
            q = tuple(a[k] + p["t"] * (b[k] - a[k]) for k in range(3))
        if math.dist(q, pos) < 1e-9:
            return i
    return None


def _spec_pos(spec):
    if spec[0] == "e":
        a, b, t = spec[1], spec[2], spec[3]
        return tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
    return tuple(float(c) for c in spec[1])


def resolve(mesh, spec, q5_tool=None) -> dict:
    """World-position spec -> target dict on the current mesh.
    ("v", pos) vertex · ("e", a, b, t) point a + t (b - a) on whichever current edge holds it ·
    ("f", pos) face interior · ("out",) outside the mesh."""
    if spec[0] == "out":
        return {"kind": "outside"}
    pos = _spec_pos(spec)
    if q5_tool is not None and q5_tool.path:
        i = _q5_path_index(q5_tool, mesh, pos)
        if i is not None and spec[0] != "v":
            return {"kind": "path", "index": i}
    v = _vid_at(mesh, pos)
    if v is not None:
        return {"kind": "vertex", "vertex_id": v}
    if spec[0] in ("e", "v"):
        for eid in mesh.all_edge_ids():
            p0, p1 = (mesh.vertex_position(x) for x in mesh.edge_vertices(eid))
            d = [p1[k] - p0[k] for k in range(3)]
            dd = sum(c * c for c in d)
            u = sum((pos[k] - p0[k]) * d[k] for k in range(3)) / dd
            if EPS < u < 1.0 - EPS and math.dist(pos, tuple(p0[k] + u * d[k] for k in range(3))) < 1e-9:
                return {"kind": "edge", "edge_id": eid, "t": u}
        raise LookupError(f"no vertex/edge holds {pos}")
    for fid in mesh.all_face_ids():
        if segment_in_face(mesh, fid, pos, pos) == "inside":
            return {"kind": "face", "face_id": fid, "position": pos, "distance_px": 99.0}
    raise LookupError(f"no face holds {pos}")


# -- comparison --------------------------------------------------------------------------

def _r(p):
    return tuple(round(c, 6) + 0.0 for c in p)


def canon_faces(mesh) -> frozenset:
    """Faces as position cycles, rotation-normalised, winding kept — independent of ids."""
    out = []
    for f in mesh.all_face_ids():
        cyc = [_r(mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
        k = cyc.index(min(cyc))
        out.append(tuple(cyc[k:] + cyc[:k]))
    return frozenset(out)


def canon_edges(mesh, eids) -> frozenset:
    return frozenset(frozenset(_r(mesh.vertex_position(v)) for v in mesh.edge_vertices(e)) for e in eids)


def counts(mesh) -> str:
    return f"V{len(mesh.all_vertex_ids())}/E{len(mesh.all_edge_ids())}/F{len(mesh.all_face_ids())}"


# Planar reference surfaces: every face must face the reference way, and the faces must add up to
# the surface's area exactly (an overlap or a face built outside its parent shows up as extra area).
REFERENCE_AREA = {"grid": 16.0, "L": 3.0, "cube": 24.0}


def _newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def broken_faces(mesh, scene: str) -> list[str]:
    """Geometric problems after a commit: per face no area / crossing itself (the Lab's `face_problem`),
    facing the wrong way (grid/L: +z, cube: outward), total area != the reference surface (overlap), plus
    the topological invariants."""
    out = [p for p in (face_problem(mesh, f) for f in mesh.all_face_ids()) if p]
    total = 0.0
    for fid in mesh.all_face_ids():
        pts = [mesh.vertex_position(x) for x in mesh.face_vertices(fid)]
        n = _newell(pts)
        area = 0.5 * math.sqrt(sum(c * c for c in n))
        total += area
        if area < 1e-12:
            continue  # no area: already reported, has no facing
        if scene in ("grid", "L"):
            wrong = n[2] <= 0.0
        elif scene != "cube":
            continue  # no reference surface (head): area / simple / invariants only
        else:
            centre = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            wrong = sum(n[k] * centre[k] for k in range(3)) <= 0.0
        if wrong:
            out.append("a face flipped")
    if scene in REFERENCE_AREA and abs(total - REFERENCE_AREA[scene]) > 1e-6:
        out.append(f"faces cover {total:.4f} instead of {REFERENCE_AREA[scene]:.1f} (overlap)")
    try:
        assert_mesh_invariants(mesh)
    except AssertionError as exc:
        out.append(f"invariants: {str(exc)[:60]}")
    return out


def run_session(engine, scene_name, specs, mesh=None, ops=None):
    """Play `specs` (clicks) then `ops` (list of "undo"/"redo"/("click", spec)) and commit.
    Returns a result dict."""
    mesh = mesh if mesh is not None else SCENES[scene_name]()
    before = mesh.export_state()
    s = Session(engine, mesh, scene_name)
    clicks = [s.click(sp) for sp in specs]
    for op in ops or []:
        if op == "undo":
            s.undo()
        elif op == "redo":
            s.redo()
        else:
            clicks.append(s.click(op[1]))
    cmd = s.commit()
    res = {
        "clicks": clicks,
        "faces": canon_faces(mesh),
        "counts": counts(mesh),
        "residue": canon_edges(mesh, s.scene.selection.edges) if cmd is not None else frozenset(),
        "mode": s.scene.selection.mode.name if cmd is not None else "-",
        "history": len(s.scene.history),
        "broken": broken_faces(mesh, scene_name),
        "message": getattr(s.tool, "last_message", ""),
    }
    content_changed = _content(mesh.export_state()) != _content(before)
    res["content_changed"] = content_changed
    if cmd is not None:
        s.scene.history.undo()
        res["undo_restores"] = _content(mesh.export_state()) == _content(before)
        s.scene.history.redo()
        res["redo_restores"] = canon_faces(mesh) == res["faces"]
    return res


def _content(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.endswith("_counter")}


def _acc(clicks) -> str:
    return "".join("+" if ok else "-" for _a, _h, ok in clicks)


def _consistent(clicks) -> str:
    """accepts() == click() for every click; hover-valid where it differs from accepts()."""
    bad = sum(1 for a, _h, ok in clicks if a != ok)
    loose = sum(1 for a, h, _ok in clicks if h and not a)
    return f"accepts==click {'yes' if not bad else f'NO x{bad}'}" + (f", hover valid but refused x{loose}" if loose else "")


# -- sections ----------------------------------------------------------------------------

def e(a, b, t):
    return ("e", tuple(float(c) for c in a), tuple(float(c) for c in b), t)


def v(p):
    return ("v", tuple(float(c) for c in p))


def f(p):
    return ("f", tuple(float(c) for c in p))


PARITY = {
    # name: (scene, clicks, what)
    "P01 edge -> edge across one quad": ("grid", [e((0, 0, 0), (1, 0, 0), .5), e((0, 1, 0), (1, 1, 0), .5)],
                                          "straight chord, both ends on edges"),
    "P02 vertex -> vertex (diagonal)": ("grid", [v((1, 1, 0)), v((2, 2, 0))], "connect_vertices only"),
    "P03 vertex -> edge -> edge -> vertex (3 quads)": (
        "grid", [v((0, 0, 0)), e((1, 0, 0), (1, 1, 0), .5), e((2, 0, 0), (2, 1, 0), .5), v((3, 1, 0))],
        "AD-017 §4 composite path"),
    "P04 zig-zag edge chain (4 points)": (
        "grid", [e((0, 0, 0), (0, 1, 0), .3), e((1, 0, 0), (1, 1, 0), .6), e((2, 0, 0), (2, 1, 0), .3),
                 e((3, 0, 0), (3, 1, 0), .6)], "consecutive points share a face"),
    "P05 closed diamond on edges round a vertex": (
        "grid", [e((1, 2, 0), (2, 2, 0), .5), e((2, 2, 0), (2, 3, 0), .5), e((2, 2, 0), (3, 2, 0), .5),
                 e((2, 1, 0), (2, 2, 0), .5), e((1, 2, 0), (2, 2, 0), .5)],
        "last click back on the first point (Prod: its split vertex; Q5: snap -> close)"),
    "P06 cube: across the top corner": ("cube", [e((1, 1, -1), (1, 1, 1), .5), e((-1, 1, 1), (1, 1, 1), .5)],
                                        "chord on one side"),
    "P07 cube: ring round four sides, closed": (
        "cube", [e((-1, 1, 1), (1, 1, 1), .5), e((-1, -1, 1), (1, -1, 1), .5), e((-1, -1, -1), (1, -1, -1), .5),
                 e((-1, 1, -1), (1, 1, -1), .5), e((-1, 1, 1), (1, 1, 1), .5)],
        "a loop over folds, each segment in one side"),
    "P08 vertex -> adjacent vertex (along an edge)": ("grid", [v((1, 1, 0)), v((2, 1, 0))],
                                                      "nothing to cut between neighbours"),
    "P09 two points on the same edge": ("grid", [e((1, 1, 0), (2, 1, 0), .3), e((1, 1, 0), (2, 1, 0), .7)],
                                        "second point on the (piece of the) same edge"),
    "P10 edge -> edge in faces that share nothing": (
        "grid", [e((0, 0, 0), (0, 1, 0), .5), e((2, 0, 0), (2, 1, 0), .5)], "needs the Q5 planner"),
    "P11 one edge click, then Enter": ("grid", [e((1, 1, 0), (2, 1, 0), .5)], "start only, no segment"),
    "P12 one vertex click, then Enter": ("grid", [v((1, 1, 0))], "start only, no segment"),
    "P13 same vertex twice": ("grid", [v((1, 1, 0)), v((1, 1, 0))], "second click on the start"),
    "P14 click outside the mesh": ("grid", [e((0, 0, 0), (1, 0, 0), .5), ("out",)],
                                   "engines only; Application commits on outside, the Playground does not"),
}


def section_parity() -> None:
    print("\n== PARITY: same edge/vertex-only clicks on Production KnifeTool and Q5 ==")
    for name, (scene, specs, what) in PARITY.items():
        try:
            rp = run_session("prod", scene, specs)
            rq = run_session("q5", scene, specs)
        except LookupError as exc:
            print(f"[PROBE] {name}: setup failed ({exc})")
            continue
        same = rp["faces"] == rq["faces"]
        same_res = rp["residue"] == rq["residue"]
        print(f"[PROBE] {name} ({scene}; {what})")
        for label, r in (("prod", rp), ("q5  ", rq)):
            extra = ""
            if "undo_restores" in r:
                extra = f", Undo restores {r['undo_restores']}, Redo {r['redo_restores']}"
            print(f"      {label}: clicks {_acc(r['clicks'])} ({_consistent(r['clicks'])}); {r['counts']}; "
                  f"history {r['history']}; residue {len(r['residue'])} edge(s) {r['mode']}; "
                  f"content changed {r['content_changed']}{extra}; broken {r['broken'] or 'none'}"
                  + (f"; msg '{r['message']}'" if r['message'] else ""))
        print(f"      => mesh {'SAME' if same else 'DIFFERENT'}, residue {'SAME' if same_res else 'DIFFERENT'}")
    # The same on the curved, non-planar `head` quads: edge rings of 3 / 6 / 10 midpoints, several start faces.
    for n in (3, 6, 10):
        same = 0
        tried = 0
        for start in range(0, 60, 6):
            try:
                specs = _ring_walk(head_mesh(), n, start)
            except LookupError:
                continue
            tried += 1
            rp, rq = run_session("prod", "head", specs), run_session("q5", "head", specs)
            ok = rp["faces"] == rq["faces"] and rp["residue"] == rq["residue"] and not rp["broken"] and not rq["broken"]
            same += ok
            if not ok:
                print(f"      head ring n={n} start={start}: prod {_acc(rp['clicks'])} {rp['counts']} "
                      f"{rp['broken']}; q5 {_acc(rq['clicks'])} {rq['counts']} {rq['broken']} '{rq['message']}'")
        print(f"[PROBE] P15 head, {n}-point edge rings: mesh + residue identical and clean in {same}/{tried}")


def section_session() -> None:
    print("\n== SESSION: in-session Undo/Redo, cancel, undo-everything ==")
    base = PARITY["P04 zig-zag edge chain (4 points)"][1]
    cases = {
        "S1 A->B->C->D, Undo, Redo, commit (AD-017 redo workflow)": ["undo", "redo"],
        "S2 A->B->C->D, Undo, Undo, commit": ["undo", "undo"],
        "S3 A->B->C->D, Undo, new click E, Redo (redo branch cleared?)":
            ["undo", ("click", e((2, 1, 0), (3, 1, 0), .5)), "redo"],
        "S4 A->B->C->D, Undo x4 (everything), commit": ["undo"] * 4,
    }
    ref = {eng: run_session(eng, "grid", base) for eng in ("prod", "q5")}
    for name, ops in cases.items():
        print(f"[PROBE] {name}")
        for eng in ("prod", "q5"):
            r = run_session(eng, "grid", base, ops=ops)
            print(f"      {eng:4}: {r['counts']}; history {r['history']}; content changed {r['content_changed']}; "
                  f"residue {len(r['residue'])}; same mesh as no-undo run: {r['faces'] == ref[eng]['faces']}")
        rp, rq = (run_session(eng, "grid", base, ops=ops) for eng in ("prod", "q5"))
        print(f"      => prod vs q5 mesh {'SAME' if rp['faces'] == rq['faces'] else 'DIFFERENT'}")
    # Undo of the *start* click: nothing left; a following click is a new start.
    for eng in ("prod", "q5"):
        mesh = build_grid()
        before = mesh.export_state()
        s = Session(eng, mesh, "grid")
        s.click(e((0, 0, 0), (1, 0, 0), .5))
        split_now = _content(mesh.export_state()) != _content(before)
        s.undo()
        undone = _content(mesh.export_state()) == _content(before)
        s.click(e((0, 0, 0), (1, 0, 0), .5))
        s.click(e((2, 0, 0), (2, 1, 0), .5))
        s.cancel()
        cancelled = _content(mesh.export_state()) == _content(before)
        print(f"[PROBE] S5 {eng}: first edge click mutates the mesh during the session: {split_now}; "
              f"Undo of it restores: {undone}; Cancel after more clicks restores: {cancelled}; "
              f"history {len(s.scene.history)}")


def section_defects() -> None:
    print("\n== DEFECTS R3 / R5 ==")
    # R3 (HD2): session 1 leaves a straight-angle vertex at (1.5, 1) on the quad below;
    # session 2: vertex (1,1) -> edge point (1.75, 1) — both on that quad's straight bottom line.
    s1 = [e((1, 1, 0), (2, 1, 0), .5), e((1, 2, 0), (2, 2, 0), .5)]
    s2 = [v((1, 1, 0)), e((1.5, 1, 0), (2, 1, 0), .5)]
    for eng in ("prod", "q5"):
        mesh = build_grid()
        r1 = run_session("prod", "grid", s1, mesh=mesh)  # identical setup for both: a Production session
        r2 = run_session(eng, "grid", s2, mesh=mesh)
        print(f"[PROBE] R3 (HD2) session 2 on {eng}: clicks {_acc(r2['clicks'])}; {r2['counts']}; "
              f"history {r2['history']}; content changed {r2['content_changed']}; "
              f"broken {r2['broken'] or 'none'} (setup {r1['counts']}, broken {r1['broken'] or 'none'})"
              + (f"; msg '{r2['message']}'" if r2["message"] else ""))
    # What a click-time geometric gate would see for the Production click of R3.
    mesh = build_grid()
    run_session("prod", "grid", s1, mesh=mesh)
    a = _vid_at(mesh, (1.0, 1.0, 0.0))
    shared = {fc for ed in mesh.vertex_edges(a) for fc in mesh.edge_faces(ed)}
    tgt = resolve(mesh, s2[1])
    ea, eb = mesh.edge_vertices(tgt["edge_id"])
    p0, p1 = mesh.vertex_position(ea), mesh.vertex_position(eb)
    q = tuple(p0[k] + tgt["t"] * (p1[k] - p0[k]) for k in range(3))
    shared &= set(mesh.edge_faces(tgt["edge_id"]))
    where = {int(fc): segment_in_face(mesh, fc, mesh.vertex_position(a), q) for fc in shared}
    print(f"[PROBE] R3 gate: the chord (1,1)->(1.75,1) per shared face: {where}")

    # R5: a concave L face; Production vertex (2,1) -> vertex (1,2) straight across the missing corner.
    s5 = [v((2, 1, 0)), v((1, 2, 0))]
    for eng in ("prod", "q5"):
        r = run_session(eng, "L", s5)
        print(f"[PROBE] R5 (concave L face) {eng}: clicks {_acc(r['clicks'])}; {r['counts']}; "
              f"history {r['history']}; content changed {r['content_changed']}; broken {r['broken'] or 'none'}"
              + (f"; msg '{r['message']}'" if r["message"] else ""))
    mesh = build_l_face()
    fid = mesh.all_face_ids()[0]
    print(f"[PROBE] R5 gate: chord (2,1)->(1,2) in the L face: "
          f"{segment_in_face(mesh, fid, (2.0, 1.0, 0.0), (1.0, 2.0, 0.0))}; "
          f"chord (0,0)->(1,1) (for comparison): {segment_in_face(mesh, fid, (0.0, 0.0, 0.0), (1.0, 1.0, 0.0))}")
    # R5 through the grid, L1: Lab session 1 (bent cut) leaves a concave face, Production session 2.
    l1a = [e((0, 0, 0), (1, 0, 0), .5), f((0.5, 0.5, 0)), e((0, 0, 0), (0, 1, 0), .5)]
    l1b = [e((0.5, 0, 0), (1, 0, 0), .6), e((0, 0.5, 0), (0, 1, 0), .6)]
    for eng in ("prod", "q5"):
        mesh = build_grid()
        run_session("q5", "grid", l1a, mesh=mesh)
        r = run_session(eng, "grid", l1b, mesh=mesh)
        print(f"[PROBE] R5 (L1, grid) session 2 on {eng}: clicks {_acc(r['clicks'])}; {r['counts']}; "
              f"broken {r['broken'] or 'none'}" + (f"; msg '{r['message']}'" if r["message"] else ""))

    # R3 through the shared helper outside the Knife: Vertex Connect on (1,1) + (2,1) after a split at (1.5,1).
    mesh = build_grid()
    scene = Scene()
    scene.mesh = mesh
    ed = next(x for x in mesh.all_edge_ids()
              if {_r(mesh.vertex_position(y)) for y in mesh.edge_vertices(x)} == {(1.0, 1.0, 0.0), (2.0, 1.0, 0.0)})
    mesh.split_edge(ed, 0.5)
    created = connect_vertices_per_face(scene, {_vid_at(mesh, (1, 1, 0)), _vid_at(mesh, (2, 1, 0))})
    print(f"[PROBE] R3 via Vertex Connect (production, shared helper): {len(created)} edge(s) created; "
          f"broken {broken_faces(mesh, 'grid') or 'none'}")
    # The same shape through Edge Connect (its own lowest-id face search, same missing check): the two
    # halves of the split edge (1,1)-(2,1) selected, `C`.
    mesh = build_grid()
    scene = Scene()
    scene.mesh = mesh
    ed = next(x for x in mesh.all_edge_ids()
              if {_r(mesh.vertex_position(y)) for y in mesh.edge_vertices(x)} == {(1.0, 1.0, 0.0), (2.0, 1.0, 0.0)})
    mid, h1, h2 = mesh.split_edge(ed, 0.5)
    try:
        created = connect_selected_edges_per_face(scene, {h1, h2})
        print(f"[PROBE] R3 via Edge Connect (production): {len(created)} edge(s) created; "
              f"broken {broken_faces(mesh, 'grid') or 'none'}")
    except TopologyToolError as exc:
        print(f"[PROBE] R3 via Edge Connect (production): refused ({exc}); broken {broken_faces(mesh, 'grid') or 'none'}")


class _Counter:
    """Counts the outermost public Core mutator calls on one mesh instance, refused ones included
    (a `MeshError` a caller catches still counts) — read-only observation:
    the instance's bound methods are wrapped for the probe's own meshes only)."""

    NAMES = ("split_edge", "connect_vertices", "add_vertex", "add_face", "remove_face", "add_edge",
             "set_vertex_position", "load_state")

    def __init__(self, mesh):
        self.calls: dict[str, int] = {}
        self._depth = 0
        for name in self.NAMES:
            orig = getattr(mesh, name)
            setattr(mesh, name, self._wrap(name, orig))

    def _wrap(self, name, orig):
        def inner(*a, **k):
            if self._depth == 0:
                self.calls[name] = self.calls.get(name, 0) + 1
            self._depth += 1
            try:
                return orig(*a, **k)
            finally:
                self._depth -= 1
        return inner


def section_core() -> None:
    print("\n== CORE: public mutators called per session (outermost calls) ==")
    cases = {
        "edge-only chain (P04)": ("grid", PARITY["P04 zig-zag edge chain (4 points)"][1]),
        "closed ring on the cube (P07)": ("cube", PARITY["P07 cube: ring round four sides, closed"][1]),
        "cross-face segment (P10)": ("grid", PARITY["P10 edge -> edge in faces that share nothing"][1]),
        "bent cut e -> f -> e (FC1)": ("grid", [e((0, 0, 0), (0, 1, 0), .5), f((0.5, 0.6, 0)),
                                               e((1, 0, 0), (1, 1, 0), .5)]),
        "notch, in and out through one edge (FC3)": ("grid", [e((1, 1, 0), (2, 1, 0), .2), f((1.5, 1.6, 0)),
                                                              e((1, 1, 0), (2, 1, 0), .8)]),
        "closed interior shape (2 bridges)": ("grid", [f((1.3, 1.3, 0)), f((1.7, 1.3, 0)), f((1.5, 1.7, 0)),
                                                       f((1.3, 1.3, 0))]),
        "loop at a point (P2: edge point, 2 interior, back)": ("grid", [e((1, 0, 0), (1, 1, 0), .5),
                                                                        f((0.3, 0.3, 0)), f((0.3, 0.7, 0)),
                                                                        e((1, 0, 0), (1, 1, 0), .5)]),
        "last click inside a face (tail -> corner)": ("grid", [e((0, 0, 0), (0, 1, 0), .5), f((0.6, 0.55, 0))]),
        "crossing cuts (HB1)": ("grid", [e((0, 0, 0), (1, 0, 0), .2), f((0.8, 0.5, 0)), e((0, 0, 0), (1, 0, 0), .6),
                                         e((0, 1, 0), (1, 1, 0), .5)]),
    }
    for name, (scene, specs) in cases.items():
        out = []
        for eng in ("prod", "q5"):
            mesh = SCENES[scene]()
            cnt = _Counter(mesh)
            s = Session(eng, mesh, scene)
            acc = "".join("+" if s.click(sp)[2] else "-" for sp in specs)
            s.commit()
            calls = ", ".join(f"{k} {n}" for k, n in sorted(cnt.calls.items())) or "none"
            out.append(f"{eng} [{acc}] {calls}; broken {broken_faces(mesh, scene) or 'none'}")
        print(f"[PROBE] {name}:\n      " + "\n      ".join(out))


def section_b2c() -> None:
    """Can one primitive of the B2c shape (`KNIFE_FACE_CUT_DISCOVERY.md` §3: split a face from boundary
    vertex a to boundary vertex b through new positions) build Q5's two bridge constructions? The Lab's
    `split_face_path` *is* that shape (B2b stand-in), so: build each construction once with the Lab's own
    function and once as two `split_face_path` calls, and compare the resulting faces."""
    print("\n== B2c: the bridge constructions as two path splits ==")
    # Closed interior shape in quad (1,1), 4 points, wound like the parent (counter-clockwise).
    loop = [(1.3, 1.3, 0.0), (1.7, 1.3, 0.0), (1.7, 1.7, 0.0), (1.3, 1.7, 0.0)]
    ref = build_grid()
    quad = next(fc for fc in ref.all_face_ids()
                if {_r(ref.vertex_position(x)) for x in ref.face_vertices(fc)} ==
                {(1.0, 1.0, 0.0), (2.0, 1.0, 0.0), (2.0, 2.0, 0.0), (1.0, 2.0, 0.0)})
    i1, bv1, i2, bv2 = select_bridge(ref, ref.face_vertices(quad), loop)
    alt = Mesh.from_state(ref.export_state())
    close_loop_with_bridges(ref, quad, loop, i1, bv1, i2, bv2)
    k = len(loop)
    arc1 = [loop[(i1 + j) % k] for j in range((i2 - i1) % k + 1)]          # loop[i1] .. loop[i2]
    arc2 = [loop[(i2 + j) % k] for j in range((i1 - i2) % k + 1)]          # loop[i2] .. loop[i1]
    new_vs, f1, f2, _ = split_face_path(alt, quad, bv1, bv2, arc1)         # call 1: bv1 -> arc1 -> bv2
    a, b = new_vs[0], new_vs[-1]                                           # loop[i1], loop[i2] as vertices
    rest = next(fc for fc in (f1, f2) if segment_in_face(alt, fc, arc2[1], arc2[1]) == "inside")
    split_face_path(alt, rest, b, a, arc2[1:-1])                           # call 2: loop[i2] -> arc2 -> loop[i1]
    print(f"[PROBE] closed shape, 2 bridges: Lab 3-way split {counts(ref)} vs two path splits {counts(alt)}; "
          f"same faces: {canon_faces(ref) == canon_faces(alt)}; broken {broken_faces(alt, 'grid') or 'none'}")

    # Loop at a point: x = (1,1) corner of quad (1,1), loop x -> c1 -> c2 -> c3 -> x inside the quad.
    pts = [(1.4, 1.2, 0.0), (1.6, 1.5, 0.0), (1.2, 1.4, 0.0)]
    ref = build_grid()
    x = _vid_at(ref, (1.0, 1.0, 0.0))
    alt = Mesh.from_state(ref.export_state())
    loop_vs, f_loop, ring, _ = close_loop_at_vertex(ref, quad, x, pts)
    # The bridge the Lab chose: the ring edge from a loop vertex to a vertex that is neither x nor a loop vertex.
    loop_set = set(loop_vs)
    bridge = next((lv, w) for fc in ring for lv, w in zip(ref.face_vertices(fc), ref.face_vertices(fc)[1:] +
                                                              ref.face_vertices(fc)[:1])
                  if lv in loop_set and w not in loop_set and w != x)
    j = loop_vs.index(bridge[0])
    w = _vid_at(alt, ref.vertex_position(bridge[1]))
    x2 = _vid_at(alt, (1.0, 1.0, 0.0))
    new_vs, f1, f2, _ = split_face_path(alt, quad, x2, w, pts[:j + 1])       # call 1: x -> c1..cj -> bridge end
    cj = new_vs[-1]
    # The piece that holds the loop: the one containing the loop's centroid (a convex loop here).
    outline = [(1.0, 1.0, 0.0)] + pts
    centre = tuple(sum(p[q] for p in outline) / len(outline) for q in range(3))
    host = next(fc for fc in (f1, f2) if segment_in_face(alt, fc, centre, centre) == "inside")
    split_face_path(alt, host, cj, x2, pts[j + 1:])                         # call 2: cj -> c(j+1).. -> x
    print(f"[PROBE] loop at a point, 1 bridge: Lab {counts(ref)} vs two path splits {counts(alt)}; "
          f"same faces: {canon_faces(ref) == canon_faces(alt)}; broken {broken_faces(alt, 'grid') or 'none'}")


def _ring_walk(mesh, n_points: int, seed_face_index: int = 0):
    """A chain of edge midpoints across quads (edge ring): consecutive points share a face."""
    faces = [fc for fc in mesh.all_face_ids() if len(mesh.face_vertices(fc)) == 4]
    for start in faces[seed_face_index:]:
        fc = start
        edges = mesh.face_edges(fc)
        cur = edges[0]
        pts = [cur]
        ok = True
        while len(pts) < n_points:
            fe = mesh.face_edges(fc)
            if len(fe) != 4:
                ok = False
                break
            opp = fe[(fe.index(cur) + 2) % 4]
            pts.append(opp)
            nxt = [g for g in mesh.edge_faces(opp) if g != fc]
            if not nxt or len(mesh.face_vertices(nxt[0])) != 4:
                ok = False
                break
            fc, cur = nxt[0], opp
        if ok and len(set(pts)) == len(pts):
            specs = []
            for ed in pts:
                a, b = (mesh.vertex_position(x) for x in mesh.edge_vertices(ed))
                specs.append(("e", a, b, 0.5))
            return specs
    raise LookupError("no quad ring found")


def _ms(fn, repeat=1):
    t0 = time.perf_counter()
    for _ in range(repeat):
        fn()
    return (time.perf_counter() - t0) * 1000.0 / repeat


def section_cost() -> None:
    print("\n== COST on head (headless, this machine; NOT the reference PC) ==")
    base = head_mesh()
    print(f"[PROBE] head: {counts(base)}")
    state = base.export_state()
    print(f"[PROBE] export_state {_ms(base.export_state, 50):.2f} ms, "
          f"load_state {_ms(lambda: base.load_state(state), 50):.2f} ms (one full snapshot / restore)")
    for n in (4, 8):
        specs = _ring_walk(base, n)
        per = {"prod": [], "q5": []}
        commit = {}
        hover = []
        for eng in ("prod", "q5"):
            for _rep in range(3):
                mesh = Mesh.from_state(state)
                s = Session(eng, mesh, "grid")
                s.tool.set_view(camera_for(mesh, 20.0, 10.0), W, H, occlusion=True) if eng == "q5" else None
                for sp in specs:
                    tgt = s.target(sp)
                    if eng == "q5" and s.tool.path:
                        hover.append(_ms(lambda: s.tool.hover(tgt)))
                    t0 = time.perf_counter()
                    with quiet():
                        s.tool.click(tgt)
                    per[eng].append((time.perf_counter() - t0) * 1000.0)
                commit.setdefault(eng, []).append(_ms(s.commit))
        print(f"[PROBE] head, {n}-point edge ring: per click prod {statistics.median(per['prod']):.2f} ms, "
              f"q5 {statistics.median(per['q5']):.2f} ms; commit prod {statistics.median(commit['prod']):.2f} ms, "
              f"q5 {statistics.median(commit['q5']):.2f} ms; q5 hover plan (shared face) "
              f"{statistics.median(hover):.2f} ms")
    # Q5 hover on a cross-face segment (planner) — from the first ring point to a point k faces along,
    # without and with the shared PickCache the window passes (`set_view(..., cache=...)`).
    specs = _ring_walk(base, 8)
    for cached in (False, True):
        for k in (2, 4, 7):
            mesh = Mesh.from_state(state)
            s = Session("q5", mesh, "grid")
            s.tool.set_view(camera_for(mesh, 20.0, 10.0), W, H, occlusion=True,
                            cache=PickCache() if cached else None)
            s.click(specs[0])
            tgt = s.target(specs[k])
            times = [_ms(lambda: s.tool.hover(tgt)) for _ in range(5)]
            plan = s.tool.last_plan
            print(f"[PROBE] head q5 hover across {k} faces (planner, cache {'on' if cached else 'off'}): "
                  f"{statistics.median(times):.2f} ms; plan ok {plan.ok}, {len(plan.crossings)} crossing(s)"
                  + (f", {plan.reason}" if not plan.ok else ""))


SECTIONS = {"parity": section_parity, "session": section_session, "defects": section_defects,
            "core": section_core, "b2c": section_b2c, "cost": section_cost}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for name in SECTIONS:
        ap.add_argument(f"--{name}", action="store_true")
    args = ap.parse_args(argv)
    chosen = [n for n in SECTIONS if getattr(args, n)] or list(SECTIONS)
    for n in chosen:
        SECTIONS[n]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
