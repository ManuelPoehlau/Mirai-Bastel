"""WP-KNIFE-01 S3 — the same click sequences through the Lab's Q5 and the Production `KnifeTool`.

Not a test module itself (no `test_` prefix): `test_knife_q5_differential.py` asserts what this driver
records. Q5 (`playground/experiments/knife_face/engine_q5.py`, KEEP 2026-09-30) is the oracle for
everything S3 promotes: what Q5 does *inside one face* the Production Knife must do too — same path
records, same accepted clicks, same mesh, same counts and notes at commit, same History and residue.

Sequences are written as world positions and resolved against each tool's mesh the way the window's
picks and snaps would resolve them:

    ("v", pos)                  a mesh vertex
    ("e", a, b, t)              the point a + t (b - a) on whichever edge holds it now
    ("f", pos[, dist_px])       a face-interior point (dist_px: its screen clearance from the face's
                                edges, 20 px unless given — the 9 px margin is a picking matter)
    "undo" / "redo"             in-session undo / redo

A click at the position of one of the session's own points (edge or interior) is a click on that very
point — the 14 px own-point snap: `{"kind": "path", "index"}` for Q5, `{"kind": "point", "pid"}` for
Production. Vertices need no snap (both tools find a vertex already on the path themselves).

Q5 runs **without a camera view**: a segment that needs the planner (one straight line not held by a
face the two points share — cross-face, slice S4) is refused by Q5 ("no camera view …") exactly where
the Production tool refuses it ("cross-face: not yet"). So both sides play single-face sequences, and a
multi-face sequence shows up as the same refused click in both.

WP-KNIFE-01 S4: `play_q5` / `play_production` / `play_both` take an optional `view` — `(yaw, pitch,
occlusion)` of the play-test camera (`knife_golden_driver.camera`, 1280 x 800) — given to both tools
(`set_view`) before the first click; inside a sequence `("cam", yaw, pitch)` orbits to another camera and
`("occl", bool)` switches the occlusion (wireframe) for the clicks after it, `"commit"` commits and begins a
new session on the same mesh. With a view, Q5 plans a segment across faces; so does the Production tool once
it can (before S4 it has no `set_view` and refuses). Per click the planner's result is kept (`planned`:
method, hidden crossings, the stored crossings by position) and compared too.

Ids are never compared: positions, rounded (9 digits), and point identity as "first seen as the k-th
distinct point". Run directly to print the recorded cases:

    python playground/tests/knife_q5_differential_driver.py
"""

from __future__ import annotations

import contextlib
import io
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests"),
           str(_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import Mesh, Scene  # noqa: E402
from mirai.topology import knife_resolve  # noqa: E402
from mirai.topology.knife import KnifeTool  # noqa: E402
from viewport.derived import triangulate_face  # noqa: E402

from playground.experiments.knife_face import engine_q5  # noqa: E402
from playground.experiments.knife_face.engine_q5 import KnifeFaceCrossFace  # noqa: E402
from playground.experiments.knife_face.planner import point_faces, point_position  # noqa: E402
from playground.tests.knife_golden_driver import H, W, build_scene, camera  # noqa: E402

EPS = 1e-9
FACE_CLEARANCE_PX = 20.0


def _r(p) -> tuple:
    return tuple(round(c, 9) + 0.0 for c in p)


def canon_faces(mesh: Mesh) -> list:
    out = []
    for f in mesh.all_face_ids():
        cyc = [_r(mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
        k = cyc.index(min(cyc))
        out.append(tuple(cyc[k:] + cyc[:k]))
    return sorted(out)


def residue(mesh: Mesh, selection) -> list:
    edges = [e for e in selection.edges if mesh.is_valid_edge(e)]
    return sorted(tuple(sorted(_r(mesh.vertex_position(v)) for v in mesh.edge_vertices(e))) for e in edges)


def content(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.endswith("_counter")}


def face_key(mesh: Mesh, fid) -> frozenset:
    return frozenset(_r(mesh.vertex_position(v)) for v in mesh.face_vertices(fid))


# -- click specs ---------------------------------------------------------------------------

def v(p) -> tuple:
    return ("v", tuple(float(c) for c in p))


def e(a, b, t: float) -> tuple:
    return ("e", tuple(float(c) for c in a), tuple(float(c) for c in b), t)


def f(p, dist_px: float = FACE_CLEARANCE_PX, key: frozenset | None = None) -> tuple:
    return ("f", tuple(float(c) for c in p), dist_px, key)


def spec_position(spec) -> tuple:
    if spec[0] == "e":
        a, b, t = spec[1], spec[2], spec[3]
        return tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
    return spec[1]


def _vid_at(mesh, pos):
    return next((x for x in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(x), pos) < EPS), None)


def _edge_at(mesh, pos):
    for eid in mesh.all_edge_ids():
        p0, p1 = (mesh.vertex_position(x) for x in mesh.edge_vertices(eid))
        d = [p1[k] - p0[k] for k in range(3)]
        u = sum((pos[k] - p0[k]) * d[k] for k in range(3)) / sum(c * c for c in d)
        if EPS < u < 1 - EPS and math.dist(pos, tuple(p0[k] + u * d[k] for k in range(3))) < EPS:
            return eid, u
    return None


def _face_at(mesh, pos, key):
    if key is not None:
        return next(fid for fid in mesh.all_face_ids() if face_key(mesh, fid) == key)
    from mirai.topology.face_geometry import FaceFrame, segment_in_face
    for fid in mesh.all_face_ids():
        if FaceFrame(mesh, fid).height(pos) > EPS:
            continue
        if segment_in_face(mesh, fid, pos, pos) == "inside":
            return fid
    raise LookupError(f"no face holds {pos}")


def _own_index(path, mesh, pos):
    """Index of the first clicked edge / interior point of `path` at `pos` (the own-point snap)."""
    for i, p in enumerate(path):
        if p["kind"] in ("edge", "face") and not p.get("crossing") and math.dist(point_position(mesh, p), pos) < EPS:
            return i
    return None


def mesh_target(mesh, spec) -> dict:
    """The pick's target for `spec` (no own-point snap)."""
    pos = spec_position(spec)
    if spec[0] == "v":
        return {"kind": "vertex", "vertex_id": _vid_at(mesh, pos)}
    if spec[0] == "e":
        hit = _edge_at(mesh, pos)
        if hit is None:
            raise LookupError(f"no edge holds {pos}")
        return {"kind": "edge", "edge_id": hit[0], "t": hit[1]}
    return {"kind": "face", "face_id": _face_at(mesh, pos, spec[3]), "position": tuple(pos),
            "distance_px": spec[2]}


def q5_target(knife, mesh, spec) -> dict:
    if spec[0] != "v":
        i = _own_index(knife.path, mesh, spec_position(spec))
        if i is not None:
            return {"kind": "path", "index": i}
    return mesh_target(mesh, spec)


def production_target(tool, mesh, spec) -> dict:
    if spec[0] != "v":
        i = _own_index(tool.path, mesh, spec_position(spec))
        if i is not None:
            return {"kind": "point", "pid": tool.path[i]["pid"]}
    return mesh_target(mesh, spec)


# -- signatures ------------------------------------------------------------------------------

def path_signature(mesh, path) -> list:
    """Records as (kind, position, k) — k: the point is the k-th distinct point id — or breaks."""
    ids: dict = {}
    out = []
    for p in path:
        if p["kind"] == "break":
            out.append(("break", p.get("reason"), p.get("cyclic")))
        else:
            out.append((p["kind"], _r(point_position(mesh, p)), ids.setdefault(p["pid"], len(ids)))
                       + (("crossing",) if p.get("crossing") else ()))
    return out


RESOLUTION_FIELDS = ("empty", "applied", "runs", "joined", "dropped_lead", "dropped_tail", "repeats",
                     "loops_built", "shape_chains", "short_shapes", "skipped_shapes", "lost_continuation", "gaps")


def resolution_signature(res) -> dict | None:
    """What the commit resolved — every count and note of `KnifeResolution` (the cut edge ids aside)."""
    if res is None:
        return None
    sig = {name: getattr(res, name) for name in RESOLUTION_FIELDS}
    sig["loops_dropped"] = sorted(res.loops_dropped.items())
    sig["closed_shapes"] = [(s.points, s.error, s.problem) for s in res.closed_shapes]
    return sig


@contextlib.contextmanager
def quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


@contextlib.contextmanager
def capture_q5_resolution(box: list):
    """Q5 words its resolution into HUD text; keep the `KnifeResolution` itself for the comparison."""
    original = engine_q5.resolve_cross_face

    def recording(mesh, path, before_state):
        res = original(mesh, path, before_state)
        box.append(res)
        return res

    engine_q5.resolve_cross_face = recording
    try:
        yield
    finally:
        engine_q5.resolve_cross_face = original


# -- one session through one tool ------------------------------------------------------------------

@dataclass
class Side:
    accepted: str = ""                 # "+" / "-" per click
    consistent: bool = True            # accepts() == click() on every click
    reasons: list = field(default_factory=list)       # refusal reason per refused click
    steps: str = ""                    # in-session undo / redo results
    paths: list = field(default_factory=list)         # path signature after every op
    mutated: bool = False              # the mesh changed during the session
    faces: list = field(default_factory=list)
    vef: str = ""
    history: int = 0
    residue: list = field(default_factory=list)
    mode: str = "-"
    resolution: dict | None = None
    problem: str | None = None
    undo_restores: bool | None = None
    redo_restores: bool | None = None
    planned: list = field(default_factory=list)       # per click: (method, hidden, stored crossings) (S4)


def _finish(side: Side, mesh, scene, before, cmd, res, problem) -> None:
    side.faces = canon_faces(mesh)
    side.vef = f"{len(mesh.all_vertex_ids())}/{len(mesh.all_edge_ids())}/{len(mesh.all_face_ids())}"
    side.history = len(scene.history)
    side.residue = residue(mesh, scene.selection) if cmd is not None else []
    side.mode = scene.selection.mode.name if cmd is not None else "-"
    side.resolution = resolution_signature(res)
    side.problem = problem
    if cmd is not None:
        scene.history.undo()
        side.undo_restores = content(mesh.export_state()) == content(before)
        scene.history.redo()
        side.redo_restores = canon_faces(mesh) == side.faces


def _reason_production(tool, target) -> str:
    plan = getattr(tool, "plan", None)
    return plan(target).reason if plan is not None else "no plan()"


@contextlib.contextmanager
def capture_planner(module, box: list):
    """Keep every `plan_crossings` result `module` asks for (the last one of a click is the click's)."""
    original = getattr(module, "plan_crossings", None)
    if original is None:
        yield
        return

    def recording(view, mesh, a, b):
        res = original(view, mesh, a, b)
        box.append(res)
        return res

    module.plan_crossings = recording
    try:
        yield
    finally:
        module.plan_crossings = original


def _set_view(tool, mesh, view) -> None:
    """`view` = (yaw, pitch, occlusion) or None; a tool without `set_view` (Production before S4) gets none."""
    if view is None or not hasattr(tool, "set_view"):
        return
    yaw, pitch, occlusion = view
    tool.set_view(camera(mesh, yaw, pitch), W, H, occlusion=occlusion)


def _planned(mesh, box: list, before: list, after: list) -> tuple:
    """What the click's planner call found: (method, hidden, the crossings the click stored, by position)."""
    stored = [(p["kind"], _r(point_position(mesh, p))) for p in after[len(before):]
              if p.get("crossing") and not any(p is q for q in before)]
    if not box:
        return ("direct", 0, stored)
    res = box[-1]
    return (res.method, res.hidden, stored)


def _play(tool, side: Side, mesh, scene, specs, finish, view, target_of, accepts_of, reason_of, box) -> object:
    before = mesh.export_state()
    cur_view = view
    _set_view(tool, mesh, cur_view)
    cmd = None
    for spec in specs:
        if isinstance(spec, tuple) and spec[0] == "cam":
            cur_view = (spec[1], spec[2], cur_view[2] if cur_view else True)
            _set_view(tool, mesh, cur_view)
            continue
        if isinstance(spec, tuple) and spec[0] == "occl":
            cur_view = (cur_view[0], cur_view[1], spec[1])
            _set_view(tool, mesh, cur_view)
            continue
        if spec == "commit":
            cmd = tool.commit()
            tool.deactivate()
            tool.activate()
            tool.begin(mesh=mesh, scene=scene, selection=scene.selection)
            _set_view(tool, mesh, cur_view)
            before = mesh.export_state()
            continue
        if spec in ("undo", "redo"):
            ok = tool.undo_step() if spec == "undo" else tool.redo_step()
            side.steps += ("u" if spec == "undo" else "r") + ("+" if ok else "-")
        else:
            target = target_of(tool, mesh, spec)
            acc = accepts_of(tool, target)
            path_before = tool.path
            box.clear()
            ok = tool.click(target)
            side.consistent &= acc == ok
            side.accepted += "+" if ok else "-"
            if not ok:
                side.reasons.append(reason_of(tool, target))
            side.planned.append(_planned(mesh, box, path_before, tool.path) if ok else None)
        side.paths.append(path_signature(mesh, tool.path))
        side.mutated |= content(mesh.export_state()) != content(before)
    return before, cmd


def play_q5(mesh: Mesh, specs, finish: str = "commit", view=None) -> Side:
    scene = Scene()
    scene.mesh = mesh
    knife = KnifeFaceCrossFace()
    side = Side()
    box: list = []
    planner_box: list = []
    with quiet(), capture_q5_resolution(box), capture_planner(engine_q5, planner_box):
        knife.activate()
        knife.begin(mesh=mesh, scene=scene, selection=scene.selection)

        def accepts(k, target):
            return k.plan(target).ok

        def reason(k, target):
            return k.plan(target).reason

        start, _cmd = _play(knife, side, mesh, scene, specs, finish, view, q5_target, accepts, reason, planner_box)
        cmd = knife.commit() if finish == "commit" else knife.cancel()
        knife.deactivate()
    problem = None
    if knife.last_message.startswith("commit rolled back"):
        problem = knife.last_message
    _finish(side, mesh, scene, start, cmd, box[-1] if box else None, problem)
    return side


def play_production(mesh: Mesh, specs, finish: str = "commit", view=None) -> Side:
    from mirai.topology import knife as knife_module

    scene = Scene()
    scene.mesh = mesh
    tool = KnifeTool()
    side = Side()
    planner_box: list = []
    with quiet(), capture_planner(knife_module, planner_box):
        tool.activate()
        tool.begin(mesh=mesh, scene=scene, selection=scene.selection)
        start, _cmd = _play(tool, side, mesh, scene, specs, finish, view, production_target,
                            lambda t, target: t.accepts(target), _reason_production, planner_box)
        if finish == "commit":
            cmd = tool.commit()
        else:
            tool.cancel()
            cmd = None
        tool.deactivate()
    _finish(side, mesh, scene, start, cmd, tool.last_resolution, tool.last_problem)
    return side


# Refusal reasons: Q5's text -> the Production tool's text for the same case.
REASONS = {
    "no camera view — cannot plan a cross-face segment": "no shared face holds the cut (cross-face: not yet)",
}


def compare(q5: Side, prod: Side) -> list[str]:
    """Every difference between the two sides, as text (empty: identical)."""
    out = []
    for name in ("accepted", "steps", "paths", "mutated", "faces", "vef", "history", "residue", "mode",
                 "resolution", "undo_restores", "redo_restores", "planned"):
        a, b = getattr(q5, name), getattr(prod, name)
        if a != b:
            out.append(f"{name}: Q5 {a!r} != Production {b!r}")
    if [REASONS.get(r, r) for r in q5.reasons] != prod.reasons:
        out.append(f"reasons: Q5 {q5.reasons!r} != Production {prod.reasons!r}")
    if (q5.problem is None) != (prod.problem is None):
        out.append(f"rollback: Q5 {q5.problem!r} != Production {prod.problem!r}")
    if not q5.consistent:
        out.append("Q5: accepts() != click()")
    if not prod.consistent:
        out.append("Production: accepts() != click()")
    if prod.mutated:
        out.append("Production: the mesh changed during the session")
    return out


def play_both(scene_name: str, specs, finish: str = "commit", view=None) -> tuple[Side, Side]:
    return (play_q5(build_scene(scene_name), specs, finish, view),
            play_production(build_scene(scene_name), specs, finish, view))


# -- recorded sequences ---------------------------------------------------------------------------
# Grid: 4 x 4 unit quads in z = 0, quad (c, r) = [c, c+1] x [r, r+1]. Cube: [-1, 1]^3, top y = 1.

MANU_TOP = [e((1, 1, -1), (1, 1, 1), 0.6), f((-0.5, 1, -0.6)), f((0.6, 1, -0.7))]
MANU_FRONT = f((-0.4, 0.3, 1))
LOOP = [e((1, 0, 0), (1, 1, 0), 0.3), f((0.2, 0.6, 0)), f((0.8, 0.8, 0)), e((0, 0, 0), (1, 0, 0), 0.4)]
BACK_TO_START = [e((1, 0, 0), (1, 1, 0), 0.5), f((0.3, 0.3, 0)), f((0.3, 0.7, 0))]
BOWTIE = [e((1, 0, 0), (1, 1, 0), 0.5), f((0.1, 0.45, 0)), f((0.5, 0.9, 0)), f((0.4, 0.1, 0))]
TRIANGLE = [f((1.3, 1.3, 0)), f((1.7, 1.3, 0)), f((1.5, 1.7, 0))]
# quad (1, 1): left, bottom, right, top edge midpoints
QL, QB, QR, QT = e((1, 1, 0), (1, 2, 0), .5), e((1, 1, 0), (2, 1, 0), .5), e((2, 1, 0), (2, 2, 0), .5), \
    e((1, 2, 0), (2, 2, 0), .5)

# name -> (scene, click specs, expected V/E/F or None). Every segment lies in one face.
RECORDED = {
    "FC1 bent cut, one interior click": ("grid", [QL, f((1.5, 1.4, 0)), QR], None),
    "FC2 bent cut, two interior clicks": ("grid", [QL, f((1.3, 1.3, 0)), f((1.7, 1.7, 0)), QR], None),
    "FC3 notch": ("grid", [e((1, 1, 0), (2, 1, 0), 0.2), f((1.5, 1.5, 0)), e((1, 1, 0), (2, 1, 0), 0.8)], None),
    "FC4 start inside, then two edges": ("grid", [f((1.5, 1.5, 0)), QB, QT], None),
    "FC4 start inside, then one edge": ("grid", [f((1.5, 1.5, 0)), QB], None),
    "closed shape, Enter": ("grid", TRIANGLE, None),
    "closed shape, Enter, clicked backwards": ("grid", TRIANGLE[::-1], None),
    "closed shape by click": ("grid", TRIANGLE + [TRIANGLE[0]], None),
    "closed shape by click, backwards": ("grid", TRIANGLE[::-1] + [TRIANGLE[2]], None),
    "closed shape by click, then continue": ("grid", TRIANGLE + [TRIANGLE[0], QB, e((1, 0, 0), (2, 0, 0), 0.5)], None),
    "vertex start closed by click, then continue": (
        "grid", [v((1, 1, 0)), f((1.4, 1.2, 0)), f((1.6, 1.6, 0)), f((1.2, 1.5, 0)), v((1, 1, 0)),
                 e((0, 0, 0), (1, 0, 0), 0.5)], None),
    "edge start closed by click, then continue": (
        "grid", [QB, f((1.3, 1.4, 0)), f((1.7, 1.4, 0)), f((1.5, 1.7, 0)), QB, e((1, 0, 0), (2, 0, 0), 0.5)], None),
    "loop at a single point": ("grid", LOOP, None),
    "loop at a single point, reversed": ("grid", LOOP[::-1], None),
    "loop back to the start point": ("grid", BACK_TO_START + [BACK_TO_START[0]], None),
    "loop back to the start point, other direction": (
        "grid", [BACK_TO_START[0], BACK_TO_START[2], BACK_TO_START[1], BACK_TO_START[0]], None),
    "bow-tie back to the start": ("grid", BOWTIE + [BOWTIE[0]], None),
    "bow-tie back to the start, other direction": ("grid", [BOWTIE[0]] + BOWTIE[:0:-1] + [BOWTIE[0]], None),
    "crossing cut inside one face (HB1)": (
        "grid", [e((0, 0, 0), (1, 0, 0), 0.2), f((0.8, 0.5, 0)), e((0, 0, 0), (1, 0, 0), 0.6),
                 e((0, 1, 0), (1, 1, 0), 0.5)], None),
    "tail join": ("grid", [e((0, 0, 0), (0, 1, 0), 0.5), f((0.6, 0.7, 0))], None),
    "tail join, tie by position": ("grid", [e((0, 0, 0), (1, 0, 0), 0.5), f((0.5, 0.5, 0))], None),
    "out to one point and straight back (start)": ("grid", [v((1, 1, 0)), f((1.5, 1.4, 0)), v((1, 1, 0))], None),
    "out to one point and straight back (earlier point)": (
        "grid", [QR, v((1, 1, 0)), f((1.5, 1.4, 0)), v((1, 1, 0))], None),
    "earlier-point connect, boundary": ("grid", [QL, QB, QR, QT, QB, e((1, 0, 0), (2, 0, 0), 0.5)], None),
    "earlier-point connect from an interior point": ("grid", [QL, QB, QR, f((1.6, 1.6, 0)), QB], None),
    "earlier interior point is refused": ("grid", [QL, f((1.3, 1.6, 0)), f((1.7, 1.6, 0)), f((1.3, 1.6, 0))], None),
    "closing needs three points": ("grid", [f((1.3, 1.3, 0)), f((1.7, 1.3, 0)), f((1.3, 1.3, 0))], None),
    "too close to an edge": ("grid", [QL, f((1.5, 1.05, 0), 5.0), f((1.5, 1.5, 0)), QR], None),
    "same point twice": ("grid", [QL, f((1.5, 1.5, 0)), f((1.5, 1.5, 0)), QR], None),
    "interior points, undo, redo, undo": (
        "grid", [QL, f((1.3, 1.3, 0)), f((1.7, 1.7, 0)), "undo", "redo", "undo", QR], None),
    "closing click undone and redone": ("grid", TRIANGLE + [TRIANGLE[0], "undo", "redo", QB], None),
    "everything undone": ("grid", TRIANGLE + ["undo", "undo", "undo", "undo"], None),
    "cube bow-tie (Manu)": ("cube", [e((1, 1, -1), (1, 1, 1), 0.6), f((-0.6, 1, 0)), f((0.1, 1, -0.8)),
                                     f((-0.2, 1, 0.8)), e((1, 1, -1), (1, 1, 1), 0.6)], "13/21/10"),
    # Manu's tail join (decision.md 2026-09-30) with the planner's crossing on the top/front edge clicked
    # explicitly — `q5_crossing_t` checks it is the crossing Q5 plans there with the play-test camera.
    "cube tail join (Manu), crossing clicked": ("cube", None, "14/22/10"),
}

# Sequences that need a segment across several faces (the planner, slice S4): Q5 with a camera cuts them,
# both tools without one refuse the click marked by the accepted string.
MULTI_FACE = {
    "edge to far edge": ("grid", [e((0, 1, 0), (0, 2, 0), 0.5), e((4, 1, 0), (4, 2, 0), 0.5)], "+-"),
    "interior points in neighbouring quads": ("grid", [f((1.5, 1.5, 0)), f((2.5, 1.5, 0))], "+-"),
    "cube tail join (Manu), as clicked": ("cube", MANU_TOP + [MANU_FRONT], "+++-"),
}

MANU_FRONT_EDGE = ((-1, 1, 1), (1, 1, 1))


def q5_crossing_t() -> float:
    """t of the planner's crossing on the top/front edge in Manu's tail-join sequence (play-test camera)."""
    from playground.tests.knife_golden_driver import begin, spec_target
    mesh = build_scene("cube")
    knife, _scene = begin(KnifeFaceCrossFace, mesh, camera(mesh, 35.0, 30.0))
    specs = [("e", MANU_TOP[0][1], MANU_TOP[0][2], MANU_TOP[0][3]), ("f", MANU_TOP[1][1]), ("f", MANU_TOP[2][1]),
             ("f", MANU_FRONT[1])]
    for sp in specs:
        assert knife.click(spec_target(mesh, sp))
    crossing = next(p for p in knife.path if p.get("crossing"))
    a, b = (mesh.vertex_position(x) for x in mesh.edge_vertices(crossing["edge_id"]))
    knife.cancel()
    t = crossing["t"]
    return t if tuple(a) == MANU_FRONT_EDGE[0] else 1.0 - t


def recorded_specs(name: str) -> tuple[str, list]:
    scene_name, specs, _expect = RECORDED[name]
    if specs is None:  # the tail join with its crossing clicked
        specs = MANU_TOP + [e(*MANU_FRONT_EDGE, q5_crossing_t()), MANU_FRONT]
    return scene_name, specs


# -- documented differences (decision.md "One Knife S3", open points) ----------------------------------
# Both are vertex/edge-only cases the Production tool already decided in S2 (KEEP): S3 keeps them.

DIFFERENCES = {
    # S2-b: retracing the session's own cut (boundary points) — Production: a skip, Q5: the earlier point
    # again, merged at commit ("1 repeated segment(s) merged"). Same mesh.
    "retraced segment (S2-b)": ("grid", [QL, QB, QR, QB, e((1, 0, 0), (2, 0, 0), 0.5)]),
    # Back to the chain start after one other boundary click — Production (S2): accepted (here a retrace,
    # a skip), Q5: "closing needs at least 3 points". Same mesh.
    "back to the start after one click (S2-b)": ("grid", [QL, QB, QL]),
}


def s2_divergence(tool, target) -> str | None:
    """Would this Production click fall under one of the DIFFERENCES above? (vertex/edge-only cases)."""
    point = tool._point_for(target) if hasattr(tool, "_point_for") else None
    last = tool.last_point
    if point is None or last is None or "pid" not in point:
        return None
    if point["kind"] == "face" or last["kind"] == "face":
        return None
    chain = tool.chain_points if hasattr(tool, "chain_points") else tool.points
    if chain and point["pid"] == chain[0]["pid"] and len(chain) < 3:
        return "back to the start"
    if any({a["pid"], b["pid"]} == {last["pid"], point["pid"]} for a, b in tool.cut_segments):
        return "retrace"
    return None


# -- seeded random single-face sessions ----------------------------------------------------------------

RANDOM_RUNS = {"grid": 150, "cube": 150, "head": 40}


def _interior_point(rnd, mesh, fid):
    """A random point inside face `fid`: on one of its render triangles, pulled towards the centroid."""
    cyc = mesh.face_vertices(fid)
    pos = {x: mesh.vertex_position(x) for x in cyc}
    tri = rnd.choice(triangulate_face(cyc, pos))
    u, w = rnd.random(), rnd.random()
    if u + w > 1:
        u, w = 1 - u, 1 - w
    a, b, c = (pos[x] for x in tri)
    p = tuple(a[k] + u * (b[k] - a[k]) + w * (c[k] - a[k]) for k in range(3))
    centre = tuple((a[k] + b[k] + c[k]) / 3.0 for k in range(3))
    return tuple(centre[k] + 0.8 * (p[k] - centre[k]) for k in range(3))


def _random_spec(rnd, mesh, tool):
    """Mostly a target in a face of the last point (single-face), now and then an own point, a point
    anywhere (often cross-face: refused by both), or an interior point too close to an edge."""
    last = tool.last_point
    roll = rnd.random()
    chain = getattr(tool, "chain_points", tool.points)
    if len(chain) >= 2 and rnd.random() < 0.15:  # back to the chain start: a close (or its refusal)
        start = chain[0]
        if start["kind"] == "vertex":
            return v(mesh.vertex_position(start["vertex_id"]))
        return ("own", point_position(mesh, start))
    own = [p for p in tool.points if p["kind"] in ("edge", "face")]
    if own and roll < 0.12:
        return ("own", point_position(mesh, rnd.choice(own)))
    if last is not None and roll < 0.9:
        faces = sorted(point_faces(mesh, last), key=lambda fid: sorted(face_key(mesh, fid)))
    else:
        faces = sorted(mesh.all_face_ids(), key=lambda fid: sorted(face_key(mesh, fid)))
    fid = rnd.choice(faces)
    kind = rnd.random()
    if kind < 0.2:
        return v(mesh.vertex_position(rnd.choice(mesh.face_vertices(fid))))
    if kind < 0.5:
        eid = rnd.choice(mesh.face_edges(fid))
        a, b = (mesh.vertex_position(x) for x in mesh.edge_vertices(eid))
        return e(a, b, rnd.uniform(0.1, 0.9))
    return f(_interior_point(rnd, mesh, fid), 5.0 if rnd.random() < 0.05 else FACE_CLEARANCE_PX, face_key(mesh, fid))


def random_run(scene_name: str, seed: int) -> list[tuple[list, list[str], Side]]:
    """One seeded run: 1-2 sessions of 2-8 steps on the mesh the previous session left; returns
    [(specs, differences, Production side)] per session. Clicks under a documented S2 difference are
    not played."""
    rnd = random.Random(f"{scene_name}/differential/{seed}")
    mesh_q5, mesh_prod = build_scene(scene_name), build_scene(scene_name)
    out = []
    for _session in range(rnd.randint(1, 2)):
        # Plan the session on a scratch Production tool (on a copy: the same mesh as both sides).
        scratch_mesh = Mesh.from_state(mesh_prod.export_state())
        scratch_scene = Scene()
        scratch_scene.mesh = scratch_mesh
        scratch = KnifeTool()
        specs: list = []
        with quiet():
            scratch.activate()
            scratch.begin(mesh=scratch_mesh, scene=scratch_scene, selection=scratch_scene.selection)
            for _ in range(rnd.randint(2, 8)):
                op = rnd.random()
                if op < 0.07 and specs:
                    scratch.undo_step()
                    specs.append("undo")
                    continue
                if op < 0.1 and specs:
                    scratch.redo_step()
                    specs.append("redo")
                    continue
                spec = _random_spec(rnd, scratch_mesh, scratch)
                if spec[0] == "own":
                    i = _own_index(scratch.path, scratch_mesh, spec[1])
                    p = scratch.path[i]
                    spec = (e(*(scratch_mesh.vertex_position(x) for x in scratch_mesh.edge_vertices(p["edge_id"])), p["t"])
                            if p["kind"] == "edge" else f(p["position"], FACE_CLEARANCE_PX,
                                                          face_key(scratch_mesh, p["face_id"])))
                target = production_target(scratch, scratch_mesh, spec)
                if s2_divergence(scratch, target):
                    continue
                scratch.click(target)
                specs.append(spec)
            scratch.cancel()
            scratch.deactivate()
        q5 = play_q5(mesh_q5, specs)
        prod = play_production(mesh_prod, specs)
        out.append((specs, compare(q5, prod), prod))
    return out


def _print_all() -> None:
    for name in RECORDED:
        scene_name, specs = recorded_specs(name)
        q5, prod = play_both(scene_name, specs)
        print(f"{name}: Q5 {q5.accepted} {q5.vef} h{q5.history} | Production {prod.accepted} {prod.vef} "
              f"h{prod.history} | {len(compare(q5, prod))} difference(s)")
    for name, (scene_name, specs, _acc) in MULTI_FACE.items():
        q5, prod = play_both(scene_name, specs)
        print(f"multi-face {name}: Q5 {q5.accepted} | Production {prod.accepted} {prod.reasons}")
    for name, (scene_name, specs) in DIFFERENCES.items():
        q5, prod = play_both(scene_name, specs)
        print(f"difference {name}: {compare(q5, prod)}")


if __name__ == "__main__":
    _print_all()
