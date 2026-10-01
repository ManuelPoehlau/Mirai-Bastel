"""WP-KNIFE-01 S2 — parity rows P01–P15 / S1–S5 / R3 / R5 as a headless driver for `KnifeTool`.

Not a test module itself (no `test_` prefix): `tests/test_knife_parity.py` asserts what this driver
records. The rows are the ones of `docs/research/topology/ONE_KNIFE_PROMOTION_DISCOVERY.md` §1.2
(`experiments/topology/one_knife_parity_probe.py` played them first); here they drive the Production tool
only, through its public session interface (`activate`, `begin`, `accepts`, `click`, `undo_step`,
`redo_step`, `commit`, `cancel`) the way `mirai.application` does.

Clicks are written as world positions and resolved against the mesh *as the tool sees it*:
`("v", pos)` a vertex, `("e", a, b, t)` the point `a + t (b - a)` on whichever edge holds it now,
`("out",)` outside the mesh. A tool that keeps its points virtually (`KnifeTool.path`, S2) gets a click
on one of its own edge points as the own-point target `{"kind": "point", "pid": ...}` — what the
window's own-point snap turns such a click into; a tool that cuts at every click has a real vertex
there instead, which the vertex lookup finds.

Run directly to print the current signatures (used to write the literals in the test module):

    python tests/knife_parity_driver.py
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLES = _ROOT / "examples"
for _p in (str(_EXAMPLES), str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core import Mesh, Scene  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj, create_cube  # noqa: E402
from mirai.topology.face_geometry import face_problem  # noqa: E402
from mirai.topology.knife import KnifeTool  # noqa: E402
from tests.mesh_invariants import assert_mesh_invariants  # noqa: E402

HEAD_ASSET = _EXAMPLES / "meshes" / "head_basemesh.obj"
EPS = 1e-9


# -- scenes -------------------------------------------------------------------------------

def build_grid(n: int = 4) -> Mesh:
    """n x n unit quads in z = 0 (the probe's and the Lab's fixture)."""
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


def build_l_face() -> Mesh:
    """One concave L-shaped hexagon (R5): (0,0) (2,0) (2,1) (1,1) (1,2) (0,2)."""
    mesh = Mesh()
    vs = [mesh.add_vertex(p) for p in ((0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0))]
    mesh.add_face(vs)
    return mesh


_HEAD_STATE: dict | None = None


def head_mesh() -> Mesh:
    global _HEAD_STATE
    if _HEAD_STATE is None:
        _HEAD_STATE = build_core_scene_from_obj(HEAD_ASSET).mesh.export_state()
    return Mesh.from_state(_HEAD_STATE)


SCENES = {"grid": build_grid, "cube": create_cube, "L": build_l_face, "head": head_mesh}
# Planar reference surfaces: total face area must stay exactly this (an overlap shows up as extra area).
REFERENCE_AREA = {"grid": 16.0, "L": 3.0, "cube": 24.0}


# -- click specs ----------------------------------------------------------------------------

def v(p) -> tuple:
    return ("v", tuple(float(c) for c in p))


def e(a, b, t: float) -> tuple:
    return ("e", tuple(float(c) for c in a), tuple(float(c) for c in b), t)


OUT = ("out",)


def spec_position(spec) -> tuple:
    if spec[0] == "e":
        a, b, t = spec[1], spec[2], spec[3]
        return tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
    return spec[1]


def _vid_at(mesh, pos):
    for vid in mesh.all_vertex_ids():
        if math.dist(mesh.vertex_position(vid), pos) < EPS:
            return vid
    return None


def _own_point_at(tool, mesh, pos):
    """The pid of the session's own (virtual) edge point at `pos`, if the tool keeps a path."""
    for p in getattr(tool, "path", ()):
        if p.get("kind") != "edge":
            continue
        a, b = (mesh.vertex_position(x) for x in mesh.edge_vertices(p["edge_id"]))
        q = tuple(a[k] + p["t"] * (b[k] - a[k]) for k in range(3))
        if math.dist(q, pos) < EPS:
            return p["pid"]
    return None


def target(tool, mesh, spec) -> dict:
    if spec[0] == "out":
        return {"kind": "outside"}
    pos = spec_position(spec)
    pid = _own_point_at(tool, mesh, pos)
    if pid is not None:
        return {"kind": "point", "pid": pid}
    vid = _vid_at(mesh, pos)
    if vid is not None:
        return {"kind": "vertex", "vertex_id": vid}
    for eid in mesh.all_edge_ids():
        p0, p1 = (mesh.vertex_position(x) for x in mesh.edge_vertices(eid))
        d = [p1[k] - p0[k] for k in range(3)]
        dd = sum(c * c for c in d)
        u = sum((pos[k] - p0[k]) * d[k] for k in range(3)) / dd
        if EPS < u < 1.0 - EPS and math.dist(pos, tuple(p0[k] + u * d[k] for k in range(3))) < 1e-9:
            return {"kind": "edge", "edge_id": eid, "t": u}
    raise LookupError(f"no vertex/edge holds {pos}")


# -- signatures (ids never compared) ---------------------------------------------------------

def _r(p) -> tuple:
    """Positions rounded to 6 digits, through 9 digits first. Float noise of one ulp must not flip a
    digit: the head OBJ has 6 decimals, so an edge midpoint lies exactly half-way between two 6-digit
    values, and a direct `round(c, 6)` went either way with how the clicked `t` was summed (Python 3.12
    made `sum()` of floats compensated — the P15 head rings hashed differently on 3.12+)."""
    return tuple(round(round(c, 9), 6) + 0.0 for c in p)


def canon_faces(mesh) -> list:
    """Faces as position cycles rotated to their smallest position, winding kept — id-free."""
    out = []
    for fid in mesh.all_face_ids():
        cyc = [_r(mesh.vertex_position(x)) for x in mesh.face_vertices(fid)]
        k = cyc.index(min(cyc))
        out.append(tuple(cyc[k:] + cyc[:k]))
    return sorted(out)


def faces_hash(mesh) -> str:
    return hashlib.sha256(repr(canon_faces(mesh)).encode()).hexdigest()[:16]


def residue(mesh, edges) -> list:
    return sorted(
        tuple(sorted(_r(mesh.vertex_position(x)) for x in mesh.edge_vertices(ed)))
        for ed in edges if mesh.is_valid_edge(ed)
    )


def content(state: dict) -> dict:
    """A mesh state without its id counters (`load_state` only moves them forward)."""
    return {k: val for k, val in state.items() if not k.endswith("_counter")}


def vef(mesh) -> str:
    return f"{len(mesh.all_vertex_ids())}/{len(mesh.all_edge_ids())}/{len(mesh.all_face_ids())}"


def _newell(pts):
    n = [0.0, 0.0, 0.0]
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return n


def broken(mesh, scene: str) -> list[str]:
    """Geometric problems: per face (no area, crossing itself), facing (grid/L: +z, cube: outward),
    total area of a planar reference surface, and the topological invariants."""
    out = [p for p in (face_problem(mesh, f) for f in mesh.all_face_ids()) if p]
    total = 0.0
    for fid in mesh.all_face_ids():
        pts = [mesh.vertex_position(x) for x in mesh.face_vertices(fid)]
        n = _newell(pts)
        area = 0.5 * math.sqrt(sum(c * c for c in n))
        total += area
        if area < 1e-12:
            continue
        if scene in ("grid", "L"):
            wrong = n[2] <= 0.0
        elif scene == "cube":
            centre = [sum(p[k] for p in pts) / len(pts) for k in range(3)]
            wrong = sum(n[k] * centre[k] for k in range(3)) <= 0.0
        else:
            wrong = False
        if wrong:
            out.append("a face flipped")
    if scene in REFERENCE_AREA and abs(total - REFERENCE_AREA[scene]) > 1e-6:
        out.append(f"faces cover {total:.4f} instead of {REFERENCE_AREA[scene]:.1f}")
    try:
        assert_mesh_invariants(mesh)
    except AssertionError as exc:
        out.append(f"invariants: {str(exc)[:80]}")
    return out


# -- sessions ------------------------------------------------------------------------------------

@contextlib.contextmanager
def quiet():
    """`KnifeTool` prints its temporary [KNIFE] diagnosis trace on every call."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


@dataclass
class Result:
    accepted: str                      # "+" / "-" per click, in click order (ops clicks included)
    consistent: bool                   # accepts() == click() for every click
    faces: str                         # position-canonical face hash after commit
    vef: str
    history: int
    residue: list
    mode: str                          # selection mode after commit ("-" when nothing was committed)
    broken: list
    content_changed: bool
    undo_restores: bool | None = None  # History Undo -> session-start content; None: nothing committed
    redo_restores: bool | None = None  # History Redo -> the committed faces
    steps: str = ""                    # in-session undo/redo results ("u+" / "r-" ...)
    session_mutations: list = field(default_factory=list)  # content changed during the session, per click


def begin(mesh, scene: Scene | None = None):
    scene = scene or Scene()
    scene.mesh = mesh
    tool = KnifeTool()
    with quiet():
        tool.activate()
        tool.begin(mesh=mesh, scene=scene, selection=scene.selection)
    return tool, scene


def click(tool, mesh, spec) -> tuple[bool, bool]:
    tgt = target(tool, mesh, spec)
    with quiet():
        acc = tool.accepts(tgt)
        ok = tool.click(tgt)
    return acc, ok


def run(scene_name: str, specs, ops=(), mesh: Mesh | None = None, finish: str = "commit") -> Result:
    """Play `specs`, then `ops` ("undo" / "redo" / ("click", spec)), then commit (or cancel)."""
    mesh = mesh if mesh is not None else SCENES[scene_name]()
    before = mesh.export_state()
    tool, scene = begin(mesh)
    clicks, steps, mutated = [], [], []
    for sp in specs:
        clicks.append(click(tool, mesh, sp))
        mutated.append(content(mesh.export_state()) != content(before))
    for op in ops:
        if op == "undo":
            with quiet():
                steps.append("u+" if tool.undo_step() else "u-")
        elif op == "redo":
            with quiet():
                steps.append("r+" if tool.redo_step() else "r-")
        else:
            clicks.append(click(tool, mesh, op[1]))
            mutated.append(content(mesh.export_state()) != content(before))
    with quiet():
        if finish == "commit":
            cmd = tool.commit()
        else:
            tool.cancel()
            cmd = None
        tool.deactivate()
    res = Result(
        accepted="".join("+" if ok else "-" for _a, ok in clicks),
        consistent=all(a == ok for a, ok in clicks),
        faces=faces_hash(mesh),
        vef=vef(mesh),
        history=len(scene.history),
        residue=residue(mesh, scene.selection.edges) if cmd is not None else [],
        mode=scene.selection.mode.name if cmd is not None else "-",
        broken=broken(mesh, scene_name),
        content_changed=content(mesh.export_state()) != content(before),
        steps=" ".join(steps),
        session_mutations=mutated,
    )
    if cmd is not None:
        committed = canon_faces(mesh)
        scene.history.undo()
        res.undo_restores = content(mesh.export_state()) == content(before)
        scene.history.redo()
        res.redo_restores = canon_faces(mesh) == committed
    return res


def ring_walk(mesh, n_points: int, seed_face_index: int = 0) -> list:
    """A chain of edge midpoints across quads (an edge ring): consecutive points share a face."""
    faces = [fc for fc in mesh.all_face_ids() if len(mesh.face_vertices(fc)) == 4]
    for start in faces[seed_face_index:]:
        fc = start
        cur = mesh.face_edges(fc)[0]
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
            out = []
            for ed in pts:
                a, b = (mesh.vertex_position(x) for x in mesh.edge_vertices(ed))
                out.append(("e", tuple(a), tuple(b), 0.5))
            return out
    raise LookupError("no quad ring found")


# -- the rows (discovery §1.2) ---------------------------------------------------------------------

ROWS = {
    "P01": ("grid", [e((0, 0, 0), (1, 0, 0), .5), e((0, 1, 0), (1, 1, 0), .5)]),
    "P02": ("grid", [v((1, 1, 0)), v((2, 2, 0))]),
    "P03": ("grid", [v((0, 0, 0)), e((1, 0, 0), (1, 1, 0), .5), e((2, 0, 0), (2, 1, 0), .5), v((3, 1, 0))]),
    "P04": ("grid", [e((0, 0, 0), (0, 1, 0), .3), e((1, 0, 0), (1, 1, 0), .6), e((2, 0, 0), (2, 1, 0), .3),
                     e((3, 0, 0), (3, 1, 0), .6)]),
    "P05": ("grid", [e((1, 2, 0), (2, 2, 0), .5), e((2, 2, 0), (2, 3, 0), .5), e((2, 2, 0), (3, 2, 0), .5),
                     e((2, 1, 0), (2, 2, 0), .5), e((1, 2, 0), (2, 2, 0), .5)]),
    "P06": ("cube", [e((1, 1, -1), (1, 1, 1), .5), e((-1, 1, 1), (1, 1, 1), .5)]),
    "P07": ("cube", [e((-1, 1, 1), (1, 1, 1), .5), e((-1, -1, 1), (1, -1, 1), .5), e((-1, -1, -1), (1, -1, -1), .5),
                     e((-1, 1, -1), (1, 1, -1), .5), e((-1, 1, 1), (1, 1, 1), .5)]),
    "P08": ("grid", [v((1, 1, 0)), v((2, 1, 0))]),
    # P08 continued (practical test step 3): neighbour along an edge, then a vertex across the next quad.
    "P08b": ("grid", [v((1, 1, 0)), v((2, 1, 0)), v((3, 2, 0))]),
    "P09": ("grid", [e((1, 1, 0), (2, 1, 0), .3), e((1, 1, 0), (2, 1, 0), .7)]),
    # P09 continued: the chain goes on from the second point on the edge.
    "P09b": ("grid", [e((1, 1, 0), (2, 1, 0), .3), e((1, 1, 0), (2, 1, 0), .7), e((1, 2, 0), (2, 2, 0), .5)]),
    "P10": ("grid", [e((0, 0, 0), (0, 1, 0), .5), e((2, 0, 0), (2, 1, 0), .5)]),
    "P11": ("grid", [e((1, 1, 0), (2, 1, 0), .5)]),
    "P12": ("grid", [v((1, 1, 0))]),
    "P13": ("grid", [v((1, 1, 0)), v((1, 1, 0))]),
    "P14": ("grid", [e((0, 0, 0), (1, 0, 0), .5), OUT]),
}

# References for the rows whose *new* result is a plain cut today's tool already makes.
REFERENCES = {
    "P08b": ("grid", [v((2, 1, 0)), v((3, 2, 0))]),
    "P09b": ("grid", [e((1, 1, 0), (2, 1, 0), .7), e((1, 2, 0), (2, 2, 0), .5)]),
}

SESSION_BASE = ROWS["P04"][1]
SESSIONS = {
    "S1": ["undo", "redo"],
    "S2": ["undo", "undo"],
    "S3": ["undo", ("click", e((2, 1, 0), (3, 1, 0), .5)), "redo"],
    "S4": ["undo"] * 4,
}

# R3 (HD2): session 1 leaves a straight-angle vertex at (1.5, 1); session 2 runs from (1, 1) along that
# straight bottom line to (1.75, 1). R5: a chord leaving the concave L face.
R3_SETUP = [e((1, 1, 0), (2, 1, 0), .5), e((1, 2, 0), (2, 2, 0), .5)]
R3_CLICKS = [v((1, 1, 0)), e((1.5, 1, 0), (2, 1, 0), .5)]
R5_CLICKS = [v((2, 1, 0)), v((1, 2, 0))]

HEAD_RINGS = [(n, start) for n in (3, 6, 10) for start in (0, 18, 36)]


def untouched_hash(scene_name: str) -> str:
    return faces_hash(SCENES[scene_name]())


def r3_mesh() -> Mesh:
    mesh = build_grid()
    run("grid", R3_SETUP, mesh=mesh)
    return mesh


def _print_all() -> None:
    for name, (scene_name, specs) in ROWS.items():
        print(name, run(scene_name, specs))
    for name, (scene_name, specs) in REFERENCES.items():
        print("ref", name, run(scene_name, specs))
    for name, ops in SESSIONS.items():
        print(name, run("grid", SESSION_BASE, ops=ops))
    print("R3", run("grid", R3_CLICKS, mesh=r3_mesh()))
    print("R5", run("L", R5_CLICKS))
    for scene_name in ("grid", "cube", "L"):
        print("untouched", scene_name, untouched_hash(scene_name))
    if HEAD_ASSET.is_file():
        for n, start in HEAD_RINGS:
            r = run("head", ring_walk(head_mesh(), n, start))
            print("head", n, start, r.faces, r.vef, r.accepted, len(r.residue), r.broken)


if __name__ == "__main__":
    _print_all()
