"""WP-KNIFE-01 S1: the Knife's commit-time resolver in `src` (`mirai.topology.knife_resolve`).

Headless, no camera, no Playground: paths are built by hand as the resolver's plain records. The
Lab sessions that produce these records in practice are covered in `playground/tests/`
(`test_knife_face_lab.py`, `test_knife_face_q5.py`, the golden net `test_knife_resolver_golden.py`,
the construction oracle `test_split_face_equivalence.py`).
"""

from __future__ import annotations

import ast
import copy
import json
import math
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh
from core.mesh import MeshError
from mirai.scene_factory import create_cube
from mirai.topology import knife_resolve
from mirai.topology.face_geometry import FaceFrame, segment_in_face
from mirai.topology.knife_resolve import (
    KnifeResolver,
    check_commit,
    resolve_collected,
    resolve_cross_face,
    split_chains,
)
from tests.mesh_invariants import assert_mesh_invariants

_TOPOLOGY = Path(__file__).resolve().parent.parent / "src" / "mirai" / "topology"


# -- scenes and path records --------------------------------------------------------------------

def _grid(n: int = 4) -> Mesh:
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


class _Path:
    """Builds resolver records with explicit point ids, the way a session does at click time."""

    def __init__(self, mesh: Mesh):
        self.mesh = mesh
        self.next_pid = 0

    def _pid(self) -> int:
        self.next_pid += 1
        return self.next_pid

    def v(self, pos) -> dict:
        vid = next(v for v in self.mesh.all_vertex_ids() if math.dist(self.mesh.vertex_position(v), pos) < 1e-9)
        return {"pid": self._pid(), "kind": "vertex", "vertex_id": vid}

    def e(self, a, b, t) -> dict:
        pos = tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
        for eid in self.mesh.all_edge_ids():
            p0, p1 = (self.mesh.vertex_position(x) for x in self.mesh.edge_vertices(eid))
            d = [p1[k] - p0[k] for k in range(3)]
            u = sum((pos[k] - p0[k]) * d[k] for k in range(3)) / sum(c * c for c in d)
            if 1e-9 < u < 1 - 1e-9 and math.dist(pos, tuple(p0[k] + u * d[k] for k in range(3))) < 1e-9:
                return {"pid": self._pid(), "kind": "edge", "edge_id": eid, "t": u}
        raise LookupError(pos)

    def f(self, pos) -> dict:
        for fid in self.mesh.all_face_ids():
            if FaceFrame(self.mesh, fid).height(pos) <= 1e-9 and segment_in_face(self.mesh, fid, pos, pos) == "inside":
                return {"pid": self._pid(), "kind": "face", "face_id": fid, "position": tuple(pos)}
        raise LookupError(pos)


def _partition(mesh: Mesh) -> list:
    """Faces as position cycles (rotation-normalised, winding kept) — id-free."""
    out = []
    for f in mesh.all_face_ids():
        cyc = [tuple(round(c, 9) + 0.0 for c in mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
        k = cyc.index(min(cyc))
        out.append(tuple(cyc[k:] + cyc[:k]))
    return sorted(out)


def _vertices_at(mesh: Mesh, pos) -> list:
    return [v for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), pos) < 1e-9]


def _commit(mesh: Mesh, before: dict) -> dict:
    check = check_commit(mesh, before)
    assert not check.rolled_back, check.problem
    assert_mesh_invariants(mesh, context="knife_resolve")
    return check.after_state


# -- contract: imports and mutations ----------------------------------------------------------------

FORBIDDEN_IMPORTS = ("viewport", "mirai.viewport", "playground", "mirai.interaction", "core.selection",
                     "core.history", "pyglet")


@pytest.mark.parametrize("module", ["knife_resolve.py", "face_geometry.py"])
def test_resolver_modules_import_no_viewport_playground_tool_selection_or_history(module):
    tree = ast.parse((_TOPOLOGY / module).read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(("." * node.level) + (node.module or ""))
            names += [a.name for a in node.names]
    bad = [n for n in names if any(n == f or n.startswith(f + ".") for f in FORBIDDEN_IMPORTS)
           or n in ("Tool", "Selection", "History", "SelectionMode")]
    assert bad == [], bad
    relative = [n for n in names if n.startswith(".")]
    assert set(relative) <= {".face_geometry"}, relative


def test_resolver_source_never_calls_face_surgery_or_id():
    """AD-017 B5 / K1: faces only through split_face (+ split_edge, connect_vertices); no object
    identity (`id()`) anywhere in the resolver."""
    tree = ast.parse((_TOPOLOGY / "knife_resolve.py").read_text(encoding="utf-8"))
    calls = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            calls.add(fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None))
    assert not calls & {"remove_face", "add_face", "add_vertex", "id"}, calls & {"remove_face", "add_face", "add_vertex", "id"}
    assert "split_face" in calls


@pytest.fixture
def mutation_spy(monkeypatch):
    """Records remove_face / add_face / add_vertex calls made outside split_face / load_state. A test
    clears it after building its scene (which uses add_vertex / add_face itself)."""
    depth = [0]
    seen = []

    def inside(name):
        real = getattr(Mesh, name)

        def wrapper(self, *a, **kw):
            depth[0] += 1
            try:
                return real(self, *a, **kw)
            finally:
                depth[0] -= 1
        monkeypatch.setattr(Mesh, name, wrapper)

    def guarded(name):
        real = getattr(Mesh, name)

        def wrapper(self, *a, **kw):
            if depth[0] == 0:
                seen.append(name)
            return real(self, *a, **kw)
        monkeypatch.setattr(Mesh, name, wrapper)

    for name in ("remove_face", "add_face", "add_vertex"):
        guarded(name)
    for name in ("split_face", "load_state", "split_edge", "connect_vertices"):
        inside(name)
    return seen


# -- what the resolver builds -----------------------------------------------------------------------

def test_closed_shape_is_independent_of_click_order_and_direction(mutation_spy):
    """Task A (2026-09-29): the bridges depend on geometry only — every rotation and both
    directions of the same triangle give the same three faces."""
    tri = [(1.3, 1.3, 0.0), (1.7, 1.3, 0.0), (1.5, 1.7, 0.0)]
    results = set()
    for order in (tri, tri[1:] + tri[:1], tri[2:] + tri[:2], tri[::-1], (tri[::-1])[1:] + (tri[::-1])[:1]):
        mesh = _grid()
        before = mesh.export_state()
        mk = _Path(mesh)
        mutation_spy.clear()
        res = resolve_collected(mesh, [mk.f(p) for p in order], before)
        assert [s.built for s in res.closed_shapes] == [True]
        assert len(res.path_edges) == 3 and len(mesh.all_face_ids()) == 16 + 2
        _commit(mesh, before)
        results.add(tuple(_partition(mesh)))
    assert len(results) == 1
    assert mutation_spy == []


def test_loop_back_to_the_same_edge_point_is_its_own_face_with_one_bridge(mutation_spy):
    """Form 2 of a loop at a single point (Artist 2026-09-30, option (a)): out of an edge point
    and back into the *same point* (same point id) — its own face, joined by one bridge."""
    for interior in ([(0.3, 0.3, 0.0), (0.3, 0.7, 0.0)], [(0.3, 0.7, 0.0), (0.3, 0.3, 0.0)]):
        mesh = _grid()
        before = mesh.export_state()
        mk = _Path(mesh)
        start = mk.e((1, 0, 0), (1, 1, 0), 0.5)
        path = [start] + [mk.f(p) for p in interior] + [start, {"kind": "break", "reason": "closed", "cyclic": False}]
        mutation_spy.clear()
        res = resolve_cross_face(mesh, path, before)
        assert (res.applied, res.runs, res.loops_built) == (1, 1, 1)
        _commit(mesh, before)
        (e,) = _vertices_at(mesh, (1.0, 0.5, 0.0))
        loop = [f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) ==
                {e, *(_vertices_at(mesh, interior[0]) + _vertices_at(mesh, interior[1]))}]
        assert len(loop) == 1
        others = [v for v in mesh.face_vertices(loop[0]) if v != e]
        assert sorted(len(mesh.vertex_edges(v)) for v in others) == [2, 3]     # exactly one bridge
    assert mutation_spy == []


def test_crossing_cuts_share_one_intersection_vertex(mutation_spy):
    """HB1 (Artist 2026-09-29, "crossing cuts like Blender"): the straight second run crosses the
    first (bent) run inside one quad — one vertex at the crossing, both cuts applied."""
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    path = [mk.e((0, 0, 0), (1, 0, 0), 0.2), mk.f((0.8, 0.5, 0)), mk.e((0, 0, 0), (1, 0, 0), 0.6),
            mk.e((0, 1, 0), (1, 1, 0), 0.5)]
    mutation_spy.clear()
    res = resolve_collected(mesh, path, before)
    assert (res.applied, res.runs) == (2, 2)
    _commit(mesh, before)
    # The chord (0.6, 0) -> (0.5, 1) crosses the bent run's first segment (0.2, 0) -> (0.8, 0.5)
    # at s = 0.4 / 0.65 along it.
    s = 0.4 / 0.65
    x = (0.2 + 0.6 * s, 0.5 * s, 0.0)
    (xv,) = [v for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), x) < 1e-9]
    assert len(mesh.vertex_edges(xv)) == 4                            # part of both cuts
    assert mutation_spy == []


def test_tail_joins_the_nearest_corner_of_its_face(mutation_spy):
    """Artist 2026-09-30, (ii): the last click inside a face is joined to that face's nearest corner."""
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    mutation_spy.clear()
    res = resolve_cross_face(mesh, [mk.e((0, 0, 0), (0, 1, 0), 0.5), mk.f((0.6, 0.7, 0))], before)
    assert (res.applied, res.runs, res.joined, res.dropped_tail) == (1, 1, 1, False)
    _commit(mesh, before)
    (i,) = _vertices_at(mesh, (0.6, 0.7, 0.0))
    ends = {tuple(mesh.vertex_position(v)) for e in mesh.vertex_edges(i) for v in mesh.edge_vertices(e) if v != i}
    assert ends == {(0.0, 0.5, 0.0), (1.0, 1.0, 0.0)}
    assert mutation_spy == []


def test_out_to_one_point_and_straight_back_does_nothing():
    """Artist 2026-09-30: cutting back the same way is not a valid operation — dropped, the mesh
    content unchanged (only the id counters may move, AD-001)."""
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    res = resolve_collected(mesh, [mk.v((1, 1, 0)), mk.f((1.5, 1.4, 0)), mk.v((1, 1, 0))], before)
    assert (res.applied, res.runs) == (0, 1)
    assert dict(res.loops_dropped) == {knife_resolve.LOOP_NO_AREA: 1}
    assert check_commit(mesh, before).after_state is None


# -- point identity -----------------------------------------------------------------------------------

def _closed_then_continue(mesh: Mesh) -> list[dict]:
    """A loop of four interior clicks over four quads, closed by click (cyclic), then continued from
    its start (the seed: the same point id again) to an edge point."""
    mk = _Path(mesh)
    loop = [mk.f(p) for p in ((1.5, 1.5, 0.0), (2.5, 1.5, 0.0), (2.5, 2.5, 0.0), (1.5, 2.5, 0.0))]
    crossings = [mk.e((2, 1, 0), (2, 2, 0), 0.5), mk.e((2, 2, 0), (3, 2, 0), 0.5),
                 mk.e((2, 2, 0), (2, 3, 0), 0.5), mk.e((1, 2, 0), (2, 2, 0), 0.5)]
    for c in crossings:
        c["crossing"] = True
    path = [loop[0], crossings[0], loop[1], crossings[1], loop[2], crossings[2], loop[3], crossings[3],
            {"kind": "break", "reason": "closed", "cyclic": True}, loop[0],
            mk.e((1, 1, 0), (2, 1, 0), 0.5)]
    return path


def test_a_seed_is_the_same_point_by_its_id_not_by_its_object():
    """The closed chain's start and the next chain's seed are one point because they carry one
    point id — even as two separate objects (here: a JSON round trip). One vertex at the seed."""
    results = []
    for fresh in (False, True):
        mesh = _grid()
        before = mesh.export_state()
        path = _closed_then_continue(mesh)
        if fresh:
            path = json.loads(json.dumps(path))   # no shared object left: identity is the pid only
            assert path[0] is not path[9] and path[0]["pid"] == path[9]["pid"]
        chains = split_chains(path)
        assert [(c, cy, s) for _e, c, cy, s in chains] == [(True, True, False), (False, False, True)]
        res = resolve_cross_face(mesh, path, before)
        assert res.applied == res.runs and not res.lost_continuation
        _commit(mesh, before)
        assert len(_vertices_at(mesh, (1.5, 1.5, 0.0))) == 1
        results.append((_partition(mesh), res.applied, res.runs))
    assert results[0] == results[1]


def test_two_points_with_different_ids_are_never_one_point_whatever_the_objects():
    """The CPython id-reuse class (decision.md, "Last click inside a face"): a key that a freed
    object left behind must not answer for another point. Here every record is rebuilt as a fresh
    object between two resolutions (old ones freed, ids free for reuse) — the result is identical,
    and a stale cache entry under another point's key does not leak into a vertex point."""
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    # Two tails in one commit (before the fix the second reused the first one's corner).
    path = [mk.e((0, 0, 0), (0, 1, 0), 0.5), mk.f((0.6, 0.7, 0)), {"kind": "break", "reason": "gap"},
            mk.e((3, 3, 0), (4, 3, 0), 0.5), mk.f((3.4, 3.3, 0))]
    state = mesh.export_state()
    outcomes = []
    for _round in range(3):
        m = Mesh.from_state(state)
        res = resolve_cross_face(m, [dict(p) for p in path], before)
        assert (res.applied, res.runs, res.joined) == (2, 2, 2)
        outcomes.append(m.export_state())
        for pos, corner in (((0.6, 0.7, 0.0), (1.0, 1.0, 0.0)), ((3.4, 3.3, 0.0), (3.0, 3.0, 0.0))):
            (i,) = _vertices_at(m, pos)
            (c,) = _vertices_at(m, corner)
            assert any(set(m.edge_vertices(e)) == {i, c} for e in m.vertex_edges(i))
    assert outcomes[0] == outcomes[1] == outcomes[2]                 # deterministic, ids included

    resolver = KnifeResolver(Mesh.from_state(state), before)
    corner = _Path(resolver.mesh).v((0, 0, 0))
    stale = {corner["pid"]: _Path(resolver.mesh).v((4, 4, 0))["vertex_id"]}
    assert resolver._run_end_vertex(corner, stale) == corner["vertex_id"]
    helpers = [resolver.helper_point(kind="vertex", vertex_id=None)["pid"] for _ in range(100)]
    assert len(set(helpers)) == 100 and not any(isinstance(h, int) for h in helpers)


def test_the_resolver_never_mutates_the_path_records():
    mesh = _grid()
    before = mesh.export_state()
    path = _closed_then_continue(mesh)
    snapshot = copy.deepcopy(path)
    resolve_cross_face(mesh, path, before)
    assert path == snapshot


# -- the commit check ------------------------------------------------------------------------------

def test_check_commit_unchanged_changed_and_rolled_back():
    mesh = _grid()
    before = mesh.export_state()
    assert check_commit(mesh, before).after_state is None              # nothing changed: nothing to commit

    mk = _Path(mesh)
    resolve_collected(mesh, [mk.e((0, 1, 0), (0, 2, 0), 0.5), mk.e((1, 1, 0), (1, 2, 0), 0.5)], before)
    ok = check_commit(mesh, before)
    assert ok.after_state == mesh.export_state() and not ok.rolled_back

    # A face turned the other way round next to its neighbours: the whole session is taken back.
    broken = Mesh.from_state(before)
    fid = broken.all_face_ids()[5]
    corners = broken.face_vertices(fid)
    broken.remove_face(fid)
    broken.add_face(corners[::-1])
    check = check_commit(broken, before)
    assert check.rolled_back and check.after_state is None
    assert check.problem == "a face would be wound against its neighbour"
    assert knife_resolve.mesh_content(broken.export_state()) == knife_resolve.mesh_content(before)


def test_a_run_tripping_over_core_is_dropped_and_leaves_nothing(monkeypatch):
    """Safety net: an exception from a face construction drops only that run; its end splits go too."""
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    path = [mk.e((0, 1, 0), (0, 2, 0), 0.5), mk.e((1, 1, 0), (1, 2, 0), 0.5), mk.e((2, 1, 0), (2, 2, 0), 0.5)]
    real, calls = knife_resolve.cut_in_face, []

    def flaky(*args):
        calls.append(args)
        if len(calls) == 1:
            raise MeshError("forced")
        return real(*args)

    monkeypatch.setattr(knife_resolve, "cut_in_face", flaky)
    res = resolve_collected(mesh, path, before)
    assert (res.applied, res.runs) == (1, 2)
    _commit(mesh, before)
    assert not _vertices_at(mesh, (0.0, 1.5, 0.0))                   # the dropped run's own end split
    assert len(_vertices_at(mesh, (1.0, 1.5, 0.0))) == 1


def test_cube_bow_tie_like_manus_play_test():
    """decision.md 2026-09-30 (Manu, confirmed): edge point on the top/right edge, three clicks inside
    the top, back to the edge point — two loops, each its own face with one bridge to an outside
    corner; V:13 E:21 F:10."""
    mesh = create_cube()
    before = mesh.export_state()
    mk = _Path(mesh)
    start = mk.e((1, 1, -1), (1, 1, 1), 0.6)
    path = [start, mk.f((-0.6, 1, 0)), mk.f((0.1, 1, -0.8)), mk.f((-0.2, 1, 0.8)), start,
            {"kind": "break", "reason": "closed", "cyclic": False}]
    res = resolve_cross_face(mesh, path, before)
    assert (res.applied, res.runs, res.loops_built) == (1, 1, 2)
    _commit(mesh, before)
    assert (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())) == (13, 21, 10)
