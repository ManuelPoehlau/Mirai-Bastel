"""Support for `tests/test_symmetric_knife.py` (AD-SYM-03 slice 6b): meshes (assets, synthetic grids, any exact
plane), the frozen regression sessions, a runner through the real `KnifeTool`, the equivariance evaluation
E-a…E-d, and the camera-free fuzz generators.

Nothing here imports the Discovery probe (`experiments/topology/symmetry_knife_probe.py`); its sessions are
frozen path data in `tests/fixtures/symmetric_knife_sessions.json` (extracted once by
`experiments/topology/extract_symmetric_knife_sessions.py`).

The evaluation is the probe's `evaluate`, generalised from the plane x = 0 to every exact plane:

- E-a  completeness: `delta_check` against the session-start mesh is clean and `symmetry_state` is not worse;
- E-b  the working side equals resolving the **clipped** path alone (the faces of the working side's class);
- E-c  the result is its own exact mirror image (all faces, positions through `mirror_position`, winding
       reversed; no tolerance);
- E-d  exactly one history entry; Undo restores mesh **and seam**, Redo the result.
"""

from __future__ import annotations

import collections
import contextlib
import io
import json
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import tests._bootstrap  # noqa: F401 — production path src/core, src/mirai

_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLES = _ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import Mesh, Scene  # noqa: E402
from core.ids import EdgeId, FaceId, VertexId  # noqa: E402
from core.mesh import SymmetryDefinition  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.symmetric_knife import KnifeRefusal, clip_path, coordinate_knife  # noqa: E402
from mirai.symmetry import SymmetryState, mirror_position, symmetry_state  # noqa: E402
from mirai.symmetry_coordination import completeness_report, delta_check  # noqa: E402
from mirai.topology import knife_resolve as kr  # noqa: E402
from mirai.topology.knife import KnifeTool  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "symmetric_knife_sessions.json"
ORIGIN = (0.0, 0.0, 0.0)
STATE_RANK = {SymmetryState.VALID: 0, SymmetryState.PARTIAL: 1, SymmetryState.AMBIGUOUS: 2,
              SymmetryState.VIOLATED: 3, SymmetryState.OFF: 4}


@contextlib.contextmanager
def quiet():
    """`KnifeTool` prints a [KNIFE] trace per click and commit."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


# ---------------------------------------------------------------------------------------------
# Meshes
# ---------------------------------------------------------------------------------------------

def normal_for(axis: int, sign: int) -> tuple[float, float, float]:
    n = [0.0, 0.0, 0.0]
    n[axis] = float(sign)
    return tuple(n)


def seam_on_plane(mesh: Mesh, axis: int) -> frozenset:
    """The edges lying in the plane (all vertices at coordinate 0 on `axis`) — the Lab's derived seam."""
    return frozenset(e for e in mesh.all_edge_ids()
                     if all(mesh.vertex_position(v)[axis] == 0.0 for v in mesh.edge_vertices(e)))


def set_plane(mesh: Mesh, axis: int = 0, sign: int = 1) -> Mesh:
    mesh.symmetry_definition = SymmetryDefinition(ORIGIN, normal_for(axis, sign), seam_on_plane(mesh, axis))
    return mesh


def permute(position, axis: int) -> tuple:
    """The cyclic coordinate permutation that moves the x axis to `axis` (a rotation: windings stay)."""
    q = [0.0, 0.0, 0.0]
    q[axis], q[(axis + 1) % 3], q[(axis + 2) % 3] = position
    return tuple(q)


def to_axis(mesh: Mesh, axis: int) -> Mesh:
    """A copy of `mesh` with its x axis moved to `axis` by `permute`. Every id is kept, so a path of the
    original (with its positions `permute`d, `permute_path`) is a path of the copy. The definition is the
    caller's to set."""
    state = mesh.export_state()
    state["vertices"] = {k: list(permute(pos, axis)) for k, pos in state["vertices"].items()}
    copy = Mesh.from_state(state)
    copy.symmetry_definition = None
    return copy


def permute_path(path: list[dict], axis: int) -> list[dict]:
    """`path` for the copy `to_axis(mesh, axis)`: only the stored positions change (face points, points in
    space); element ids and edge parameters stay."""
    by_pid: dict = {}
    out = []
    for p in path:
        if p["kind"] == "break":
            out.append(dict(p))
        elif p["pid"] in by_pid:
            out.append(by_pid[p["pid"]])
        else:
            q = dict(p)
            if "position" in q:
                q["position"] = permute(q["position"], axis)
            by_pid[p["pid"]] = q
            out.append(q)
    return out


def tie_grid(half: int = 3, rows: int = 3, holes: frozenset = frozenset()) -> Mesh:
    """Flat unit-square grid x in [-half, half], y in [0, rows], z = 0; every centred click in a square is an
    exact distance tie. `holes`: lower-left (column, row) of squares left out (pass mirror pairs)."""
    m, p = Mesh(), {}
    for r in range(rows + 1):
        for c in range(-half, half + 1):
            p[(c, r)] = m.add_vertex((float(c), float(r), 0.0))
    for r in range(rows):
        for c in range(-half, half):
            if (c, r) not in holes:
                m.add_face([p[(c, r)], p[(c + 1, r)], p[(c + 1, r + 1)], p[(c, r + 1)]])
    return set_plane(m)


def span_grid() -> Mesh:
    """x in {-1.5, -0.5, 0.5, 1.5}, y in [0, 2]: the middle squares span the plane and no vertex lies on it."""
    m, p = Mesh(), {}
    xs = (-1.5, -0.5, 0.5, 1.5)
    for r in range(3):
        for i, x in enumerate(xs):
            p[(i, r)] = m.add_vertex((x, float(r), 0.0))
    for r in range(2):
        for i in range(3):
            m.add_face([p[(i, r)], p[(i + 1, r)], p[(i + 1, r + 1)], p[(i, r + 1)]])
    return set_plane(m)


def hexagon_grid() -> Mesh:
    """`tie_grid(2, 3)` with the middle seam edge dissolved: one hexagon spanning the plane whose two plane
    vertices stay seam vertices (each is still the end of a live seam edge)."""
    m = tie_grid(2, 3)
    pos = {m.vertex_position(v): v for v in m.all_vertex_ids()}
    e = kr.find_edge(m, pos[(0.0, 1.0, 0.0)], pos[(0.0, 2.0, 0.0)])
    m.dissolve_edges([e], cleanup=False)
    d = m.symmetry_definition
    m.symmetry_definition = SymmetryDefinition(d.plane_point, d.plane_normal,
                                               frozenset(x for x in d.seam_edges if m.is_valid_edge(x)))
    return m


_FIXTURES = {
    "tie_grid": lambda: tie_grid(),
    "hole_grid": lambda: tie_grid(3, 3, frozenset({(1, 1), (-2, 1)})),
    "span_grid": span_grid,
    "hexagon_grid": hexagon_grid,
}
_ASSET_FILES = {"subd_cube", "head_basemesh", "man_with_shoes_basemesh"}
_STATES: dict = {}


def start_state(name: str, axis: int = 0, sign: int = 1) -> dict:
    """The session-start state of an asset or grid under the plane (`axis`, `sign`); built once, copied per run."""
    key = (name, axis, sign)
    if key not in _STATES:
        if name in _FIXTURES:
            base = _FIXTURES[name]()
        else:
            base = build_core_scene_from_obj(asset_path(name)).mesh
        mesh = to_axis(base, axis)
        _STATES[key] = set_plane(mesh, axis, sign).export_state()
    return _STATES[key]


def fresh(name: str, axis: int = 0, sign: int = 1) -> Mesh:
    return Mesh.from_state(start_state(name, axis, sign))


# ---------------------------------------------------------------------------------------------
# Frozen sessions
# ---------------------------------------------------------------------------------------------

_ID_KEYS = {"vertex_id": VertexId, "edge_id": EdgeId, "face_id": FaceId}


def _load_record(raw: dict, by_pid: dict) -> dict:
    if raw["kind"] == "break":
        return dict(raw)
    if raw["pid"] in by_pid:           # the same point id is the very same record, as the tool stores it
        return by_pid[raw["pid"]]
    rec = {}
    for k, v in raw.items():
        rec[k] = _ID_KEYS[k](v) if k in _ID_KEYS else tuple(v) if k == "position" else v
    by_pid[raw["pid"]] = rec
    return rec


@dataclass
class FrozenSession:
    group: str
    mesh: str
    label: str
    path: list
    source_valid: bool
    k_c_refused: bool
    side: int
    expect: dict
    camera: str = ""
    index: int = -1
    r10: bool = False


def frozen_sessions() -> list[FrozenSession]:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    out = []
    for raw in doc["sessions"]:
        by_pid: dict = {}
        out.append(FrozenSession(
            raw["group"], raw["mesh"], raw["label"], [_load_record(p, by_pid) for p in raw["path"]],
            raw["source_valid"], raw["k_c_refused"], raw["side"], raw["expect"],
            raw.get("camera", ""), raw.get("index", -1), raw.get("r10", False)))
    return out


# ---------------------------------------------------------------------------------------------
# Geometry of the evaluation (any exact plane)
# ---------------------------------------------------------------------------------------------

def sd(definition: SymmetryDefinition, position) -> float:
    return sum((p - o) * n for p, o, n in zip(position, definition.plane_point, definition.plane_normal))


def face_class(definition, pts) -> int | str:
    """+1 / -1: the face lies on the normal's / the opposite side (vertices on the plane allowed, one off);
    "0": in the plane; "span": across it."""
    ds = [sd(definition, p) for p in pts]
    if min(ds) >= 0.0 and max(ds) > 0.0:
        return 1
    if max(ds) <= 0.0 and min(ds) < 0.0:
        return -1
    return "0" if all(d == 0.0 for d in ds) else "span"


def canon_poly(pts) -> tuple:
    i = min(range(len(pts)), key=lambda k: pts[k])
    return tuple(pts[i:] + pts[:i])


def mirror(definition, p) -> tuple:
    return tuple(mirror_position(tuple(p), definition.plane_point, definition.plane_normal))


def canon_faces(mesh: Mesh) -> list[tuple]:
    d = mesh.symmetry_definition
    out = []
    for f in mesh.all_face_ids():
        pts = [tuple(mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
        out.append((face_class(d, pts), canon_poly(pts)))
    return out


def mirror_canon(definition, c) -> tuple:
    return canon_poly([mirror(definition, p) for p in reversed(c)])


def duplicates(mesh: Mesh) -> tuple[int, int]:
    """(vertex pairs at identical positions, pairs closer than 1e-9 but not identical)."""
    import math

    pts = sorted(tuple(mesh.vertex_position(v)) for v in mesh.all_vertex_ids())
    same = near = 0
    for p, q in zip(pts, pts[1:]):
        if p == q:
            same += 1
        elif math.dist(p, q) < 1e-9:
            near += 1
    return same, near


def content(mesh_or_state) -> dict:
    state = mesh_or_state if isinstance(mesh_or_state, dict) else mesh_or_state.export_state()
    return kr.mesh_content(state)


def clipped_reference(state: dict, path: list[dict], cls) -> list | None:
    """The faces of class `cls` after resolving the **clipped** path alone on a copy of the session start
    (the one-sided cut the symmetric commit must reproduce on the working side); None if that is no commit."""
    ref = Mesh.from_state(state)
    clip = clip_path(ref, ref.symmetry_definition, path)
    with quiet():
        kr.resolve_cross_face(ref, [p for p in clip.path if p["kind"] != "space"], state)
    if kr.check_commit(ref, state).after_state is None:
        return None
    return sorted(c for k, c in canon_faces(ref) if k == cls)


# ---------------------------------------------------------------------------------------------
# The runner (the real KnifeTool with the coordinator injected) and the evaluation
# ---------------------------------------------------------------------------------------------

@dataclass
class Outcome:
    status: str = "committed"          # committed | nothing | refused | rolled back
    text: str | None = None            # the status text of a refusal / the integrity problem
    ms: float = 0.0
    mesh: Mesh | None = None
    scene: Scene | None = None
    knife: KnifeTool | None = None
    before: dict | None = None
    restored: bool | None = None       # refused / nothing / rolled back: the mesh is the session start again
    ea: bool | None = None
    eb: bool | None = None
    ec: bool | None = None
    ed: bool | None = None
    dup: tuple = (0, 0)
    side: int = 0
    selected_ok: bool | None = None    # residue F4 = A: only the working side's (or on-plane) cut edges
    info: dict = field(default_factory=dict)

    @property
    def all_four(self) -> bool:
        return bool(self.ea and self.eb and self.ec and self.ed)

    @property
    def union(self) -> bool:
        return bool(self.ea and self.eb is False)


def make_tool(mesh: Mesh, *, coordinator=coordinate_knife) -> tuple[KnifeTool, Scene]:
    scene = Scene()
    scene.mesh = mesh
    knife = KnifeTool()
    with quiet():
        knife.activate()
        params = {"symmetric_commit": coordinator} if coordinator is not None else {}
        knife.begin(mesh=mesh, scene=scene, selection=scene.selection, **params)
    return knife, scene


def commit_session(state: dict, path: list[dict], *, coordinator=coordinate_knife) -> Outcome:
    """Commit the full session `path` through `KnifeTool.commit` on a fresh copy of `state`."""
    mesh = Mesh.from_state(state)
    knife, scene = make_tool(mesh, coordinator=coordinator)
    knife._path = list(path)           # the session's path, as the clicks stored it
    out = Outcome(mesh=mesh, scene=scene, knife=knife, before=state)
    t0 = time.perf_counter()
    with quiet():
        cmd = knife.commit()
    out.ms = 1000 * (time.perf_counter() - t0)
    if cmd is None:
        out.status = ("refused" if knife.last_resolution is None and knife.last_problem is not None
                      else "rolled back" if knife.last_problem is not None else "nothing")
        out.text = knife.last_problem
        out.restored = content(mesh) == content(state) and mesh.symmetry_definition == Mesh.from_state(state).symmetry_definition
    return out


def evaluate(out: Outcome, path: list[dict], base_report, base_state_sym) -> Outcome:
    """E-a…E-d, the duplicate check and the residue check on a committed `out`."""
    mesh, state = out.mesh, out.before
    d = mesh.symmetry_definition
    delta = delta_check(base_report, completeness_report(mesh))
    out.ea = delta.ok and STATE_RANK[symmetry_state(mesh)] <= STATE_RANK[base_state_sym]
    out.info["delta"] = delta.violations

    clip = clip_path(Mesh.from_state(state), Mesh.from_state(state).symmetry_definition, path)
    w = clip.side or _working_side_from_reference(state, clip)
    out.side = w
    faces = canon_faces(mesh)
    ref = clipped_reference(state, path, w)
    out.eb = ref is not None and sorted(c for k, c in faces if k == w) == ref
    allc = sorted(c for _k, c in faces)
    out.ec = allc == sorted(mirror_canon(d, c) for c in allc)

    history = out.scene.history
    after = content(mesh)
    entries = len(history)
    history.undo()
    undone_ok = content(mesh) == content(state) and mesh.symmetry_definition == Mesh.from_state(state).symmetry_definition
    history.redo()
    out.ed = (entries == 1 and undone_ok and len(history) == 1 and content(mesh) == after
              and mesh.symmetry_definition == d)

    out.dup = duplicates(mesh)
    out.selected_ok = _residue_ok(out, w)
    return out


def _working_side_from_reference(state: dict, clip) -> int:
    """No mesh record off the plane: the side the cut ended up on (the unique side of the new faces)."""
    ref = Mesh.from_state(state)
    base = collections.Counter(canon_faces(ref))
    with quiet():
        kr.resolve_cross_face(ref, [p for p in clip.path if p["kind"] != "space"], state)
    sides = {k for (k, _c), n in (collections.Counter(canon_faces(ref)) - base).items() if k in (1, -1)}
    return sides.pop() if len(sides) == 1 else 0


def _residue_ok(out: Outcome, w: int) -> bool:
    """Residue F4 = A, the part every committed result must show: the selection is not empty and every selected
    edge is valid and lies on the working side or the plane (never on the mirror side)."""
    mesh = out.mesh
    d = mesh.symmetry_definition
    selected = set(out.scene.selection.edges)
    if not selected:
        return False
    for e in selected:
        if not mesh.is_valid_edge(e):
            return False
        ds = [sd(d, mesh.vertex_position(v)) * w for v in mesh.edge_vertices(e)]
        if min(ds) < 0.0:
            return False
    return True


def run_and_evaluate(name: str, path: list[dict], axis: int = 0, sign: int = 1) -> Outcome:
    state = start_state(name, axis, sign)
    base = Mesh.from_state(state)
    out = commit_session(state, path)
    if out.status != "committed":
        return out
    return evaluate(out, path, completeness_report(base), symmetry_state(base))


# ---------------------------------------------------------------------------------------------
# Camera-free fuzz (the Production click rules through KnifeTool; no coordinator is involved)
# ---------------------------------------------------------------------------------------------

def T_v(v):
    return {"kind": "vertex", "vertex_id": v}


def T_e(e, t):
    return {"kind": "edge", "edge_id": e, "t": t}


def T_f(f, pos):
    # `distance_px` is the click's screen clearance (a pick rule, 9 px); headless sessions pass a value above it.
    return {"kind": "face", "face_id": f, "position": tuple(pos), "distance_px": 100.0}


def T_p(pid):
    return {"kind": "point", "pid": pid}


def _faces_of_point(mesh, p: dict) -> set:
    if p["kind"] == "space":
        return set()
    if p["kind"] == "face":
        return {p["face_id"]}
    if p["kind"] == "edge":
        return set(mesh.edge_faces(p["edge_id"]))
    return {f for e in mesh.vertex_edges(p["vertex_id"]) for f in mesh.edge_faces(e)}


def _seam_vertices(mesh) -> set:
    d = mesh.symmetry_definition
    return {v for e in d.seam_edges if mesh.is_valid_edge(e) for v in mesh.edge_vertices(e)}


def _random_target(rnd, mesh, f, *, seam_bias: bool, svs: set, seam: frozenset):
    vs, es = mesh.face_vertices(f), mesh.face_edges(f)
    r = rnd.random()
    if seam_bias:
        if r < 0.3:
            sv = [v for v in vs if v in svs]
            return T_v(rnd.choice(sv) if sv and rnd.random() < 0.7 else rnd.choice(vs))
        if r < 0.75:
            se = [e for e in es if e in seam]
            e = rnd.choice(se) if se and rnd.random() < 0.6 else rnd.choice(es)
            return T_e(e, 0.5 if rnd.random() < 0.3 else rnd.uniform(0.08, 0.92))
        pts = [mesh.vertex_position(v) for v in vs]
        w = [rnd.uniform(1.0, 3.0) if v in svs else rnd.uniform(0.2, 1.0) for v in vs]
    else:
        if r < 0.25:
            return T_v(rnd.choice(vs))
        if r < 0.70:
            return T_e(rnd.choice(es), 0.5 if rnd.random() < 0.3 else rnd.uniform(0.08, 0.92))
        pts = [mesh.vertex_position(v) for v in vs]
        w = [1.0] * len(pts) if rnd.random() < 0.3 else [rnd.uniform(0.2, 1.0) for _ in pts]
    tot = sum(w)
    return T_f(f, tuple(sum(w[i] * pts[i][k] for i in range(len(pts))) / tot for k in range(3)))


def fuzz_paths(state: dict, rnd: random.Random, n: int, *, region: str = "normal side",
               seam_bias: bool = False) -> list[list[dict]]:
    """`n` random camera-free sessions of 2–8 accepted clicks through the Production click rules (vertices,
    edge points — t = 0.5 in 30 % —, face points, closes, pen lifts, earlier points, in-session Undo),
    returned as the full session paths.

    `region`: "normal side" = faces on the normal's side only (the probe's K10 / R7); "both sides" = every
    face off the plane, so a path can walk over the seam (through seam vertices and seam edge points) and
    start on either side — the clip's and the side rule's cases. `seam_bias`: the targets favour seam
    vertices, seam edges and near-seam face points, and the start faces touch the seam (the review's R7)."""
    mesh = Mesh.from_state(state)
    d = mesh.symmetry_definition
    cls = {f: face_class(d, [mesh.vertex_position(v) for v in mesh.face_vertices(f)]) for f in mesh.all_face_ids()}
    wanted = (1,) if region == "normal side" else (1, -1)
    allowed = {f for f in sorted(mesh.all_face_ids()) if cls[f] in wanted}
    svs, seam = _seam_vertices(mesh), d.seam_edges
    starts = [f for f in sorted(allowed) if not seam_bias or set(mesh.face_vertices(f)) & svs]
    out = []
    for _ in range(n):
        knife, _scene = make_tool(Mesh.from_state(state), coordinator=None)
        mesh = knife._mesh
        goal, clicks, tries = rnd.randint(2, 8), 0, 0
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
            elif r < 0.25 and not seam_bias:
                act = ("undo",)
            if act is None:
                last = knife.last_point
                cand = [f for f in _faces_of_point(mesh, last) if f in allowed] if last is not None else []
                f = rnd.choice(cand) if cand and (not seam_bias or rnd.random() < 0.8) else rnd.choice(starts)
                act = ("click", _random_target(rnd, mesh, f, seam_bias=seam_bias, svs=svs, seam=seam))
            with quiet():
                if act[0] == "click":
                    ok = knife.click(act[1])
                elif act[0] == "lift":
                    ok = knife.lift()
                else:
                    ok = knife.undo_step()
            if ok and act[0] == "click":
                clicks += 1
        out.append(knife.path)
    return out


def source_commits(state: dict, path: list[dict]) -> bool:
    """Does the path, resolved alone on a copy, commit at all (the probe's `ref_ok`)?"""
    ref = Mesh.from_state(state)
    with quiet():
        kr.resolve_cross_face(ref, [p for p in path if p["kind"] != "space"], state)
    return kr.check_commit(ref, state).after_state is not None
