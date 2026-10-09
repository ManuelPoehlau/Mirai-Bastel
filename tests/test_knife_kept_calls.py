"""AD-SYM-03 slice 6a / AD-017 §13: the Knife resolver's kept-call report (`knife_resolve.KnifeResolution.kept_calls`).

Headless, no camera. Item numbers are AD-017 §13's:

- items 1, 2: static (AST) tests — the resolver mutates and rolls back only through the recording helpers
  (the list of mutating `Mesh` methods is derived from `src/core/mesh.py`, not written down here);
- item 3: entry content of the two recording helpers, on small fixtures and through the resolver;
- items 2, 3: nested rollbacks (a dropped bridge candidate, run and closed shape leave no entry);
- item 4: a session `check_commit` takes back leaves an empty report;
- item 5: the report replayed verbatim on a session-start copy rebuilds the resolved mesh, over a seeded fuzz
  (the golden net's sessions: `playground/tests/test_knife_kept_calls_golden.py`);
- item 7: the report is the only new field of `KnifeResolution` and nothing in `src/` outside the resolver reads it
  (item 8). The golden net and `tests/test_knife_parity.py` are the proof that nothing else changed.
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import random
import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh
from core.mesh import MeshError
from mirai.topology import knife_resolve
from mirai.topology.knife_resolve import (
    Checkpoint,
    KeptSplitEdge,
    KeptSplitFace,
    KnifeResolution,
    RecordedMesh,
    check_commit,
    checkpoint,
    kept_split_edge,
    kept_split_face,
    resolve_collected,
    resolve_cross_face,
    rollback,
)
from tests.knife_kept_replay import assert_report_replays
from tests.test_knife_resolve import _grid, _Path

_ROOT = Path(__file__).resolve().parent.parent
_RESOLVE_PY = _ROOT / "src" / "mirai" / "topology" / "knife_resolve.py"
_MESH_PY = _ROOT / "src" / "core" / "mesh.py"


# -- items 1, 2: static tests ------------------------------------------------------------------------

# Calls that change a container the method owns; a `Mesh` method reaching one of them through `self` mutates.
_CONTAINER_MUTATORS = {"append", "extend", "insert", "remove", "pop", "popitem", "clear", "add", "discard",
                       "update", "setdefault", "sort", "reverse"}
_ALLOCATOR_CALLS = {"allocate", "restore_counter"}


def _root_name(node: ast.AST) -> str | None:
    while True:
        if isinstance(node, (ast.Attribute, ast.Subscript)):
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        else:
            return node.id if isinstance(node, ast.Name) else None


def _mutating_mesh_methods() -> set[str]:
    """Every `Mesh` method that changes the mesh, derived from `src/core/mesh.py`: it assigns to or deletes
    from something reached through `self` (or a local taken from it), calls a mutating method on such a
    container, draws from an id allocator, or calls another mutating `Mesh` method."""
    tree = ast.parse(_MESH_PY.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Mesh")
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}

    def direct(fn: ast.FunctionDef) -> bool:
        roots = {"self"}
        for _ in range(3):      # locals taken from self (`data = self._edges[e]`), a few hops
            for n in ast.walk(fn):
                if isinstance(n, ast.Assign) and _root_name(n.value) in roots:
                    roots |= {t.id for t in n.targets if isinstance(t, ast.Name)}
                elif isinstance(n, ast.For) and _root_name(n.iter) in roots:
                    roots |= {t.id for t in ast.walk(n.target) if isinstance(t, ast.Name)}
        for n in ast.walk(fn):
            targets = []
            if isinstance(n, ast.Assign):
                targets = n.targets
            elif isinstance(n, (ast.AugAssign, ast.AnnAssign)):
                targets = [n.target]
            elif isinstance(n, ast.Delete):
                targets = n.targets
            if any(isinstance(t, (ast.Attribute, ast.Subscript)) and _root_name(t) in roots for t in targets):
                return True
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
                if n.func.attr in _CONTAINER_MUTATORS and _root_name(n.func.value) in roots:
                    return True
                if n.func.attr in _ALLOCATOR_CALLS and _root_name(n.func.value) == "self":
                    return True
        return False

    mutating = {name for name, fn in methods.items() if name != "__init__" and direct(fn)}
    changed = True
    while changed:
        changed = False
        for name, fn in methods.items():
            if name in mutating or name == "__init__":
                continue
            called = {n.func.attr for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                      and isinstance(n.func.value, ast.Name) and n.func.value.id == "self"}
            if called & mutating:
                mutating.add(name)
                changed = True
    return mutating


def _resolver_tree() -> ast.Module:
    return ast.parse(_RESOLVE_PY.read_text(encoding="utf-8"))


def _enclosing_functions(tree: ast.Module) -> dict[ast.AST, str]:
    """node -> name of the innermost function that contains it (module level: '')."""
    out: dict[ast.AST, str] = {}

    def visit(node: ast.AST, current: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else current
            out[child] = name
            visit(child, name)

    visit(tree, "")
    return out


def _uses_of(names: set[str]) -> list[tuple[str, int, str]]:
    """(name, line, enclosing function) for every attribute access and every `getattr` / `hasattr` lookup in the resolver
    that names one of `names` (the `getattr(mesh, "split_face")` form is caught too)."""
    tree = _resolver_tree()
    where = _enclosing_functions(tree)
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in names:
            uses.append((node.attr, node.lineno, where.get(node, "")))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("getattr", "hasattr")
              and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) and node.args[1].value in names):
            uses.append((node.args[1].value, node.lineno, where.get(node, "")))
    return uses


def test_the_mutating_mesh_methods_are_derived_from_core_and_cover_the_primitives():
    """The derivation itself: it finds the known mutators and none of the known readers, so the static tests
    below cannot pass on an empty or a too-small list."""
    mutating = _mutating_mesh_methods()
    assert {"split_edge", "split_face", "connect_vertices", "load_state", "add_vertex", "add_face", "remove_face",
            "set_vertex_position", "collapse_edge", "dissolve_edges", "dissolve_faces", "dissolve_vertex",
            "delete_faces", "delete_edges", "delete_vertices"} <= mutating, mutating
    assert not mutating & {"export_state", "vertex_position", "face_vertices", "face_edges", "edge_vertices",
                           "edge_faces", "vertex_edges", "all_vertex_ids", "all_edge_ids", "all_face_ids",
                           "is_valid_vertex", "is_valid_edge", "is_valid_face"}, mutating


def test_no_mutating_mesh_call_in_the_resolver_outside_the_recording_helpers():
    """AD-017 §13 item 1. `split_edge` / `split_face` only inside their recording helper, `load_state` only
    inside `rollback`; any other mutating `Mesh` method nowhere in `knife_resolve.py`."""
    mutating = _mutating_mesh_methods()
    allowed = {"split_edge": {"kept_split_edge"}, "split_face": {"kept_split_face"}, "load_state": {"rollback"}}
    bad = [(name, line, fn) for name, line, fn in _uses_of(mutating) if fn not in allowed.get(name, set())]
    assert bad == [], f"mutating Mesh call outside a recording helper: {bad}"
    inside = {(name, fn) for name, _line, fn in _uses_of(mutating)}
    assert inside == {("split_edge", "kept_split_edge"), ("split_face", "kept_split_face"), ("load_state", "rollback")}


def test_no_bare_export_state_or_load_state_in_the_resolver():
    """AD-017 §13 item 2: every rollback pair goes through `checkpoint` / `rollback`."""
    allowed = {"export_state": {"checkpoint"}, "load_state": {"rollback"}}
    bad = [(name, line, fn) for name, line, fn in _uses_of({"export_state", "load_state"})
           if fn not in allowed[name]]
    assert bad == [], f"bare export_state / load_state: {bad}"


def test_the_resolver_does_not_use_connect_vertices_and_the_docstring_says_so():
    assert not [u for u in _uses_of({"connect_vertices"}) if u[2]], "connect_vertices is neither called nor recorded"
    mutations = knife_resolve.__doc__.split("**Mutations**")[1].split("- **Kept-call report**")[0]
    assert "split_face" in mutations and "split_edge" in mutations and "checkpoint" in mutations
    assert "`connect_vertices` is not used" in mutations


def test_nothing_in_src_outside_the_resolver_reads_the_report():
    """AD-017 §13 item 8: not a provenance layer; the first reader is slice 6b's coordinator."""
    readers = [p.relative_to(_ROOT).as_posix() for p in (_ROOT / "src").rglob("*.py")
               if "kept_calls" in p.read_text(encoding="utf-8") and p != _RESOLVE_PY]
    assert readers == []


# -- item 7: additive output -------------------------------------------------------------------------

_FIELDS_BEFORE_6A = {"path_edges", "empty", "applied", "runs", "joined", "dropped_lead", "dropped_tail", "repeats",
                     "loops_built", "loops_dropped", "closed_shapes", "shape_chains", "short_shapes",
                     "skipped_shapes", "lost_continuation", "gaps"}


def test_the_report_is_the_only_new_field_of_knife_resolution_and_it_has_a_default():
    names = {f.name for f in dataclasses.fields(KnifeResolution)}
    assert names - _FIELDS_BEFORE_6A == {"kept_calls"}
    assert _FIELDS_BEFORE_6A <= names
    assert KnifeResolution().kept_calls == () and KnifeResolution(applied=2).kept_calls == ()   # every old constructor stays valid


def test_a_path_without_points_and_a_path_that_cuts_nothing_report_nothing():
    mesh = _grid()
    before = mesh.export_state()
    assert resolve_cross_face(mesh, [], before).kept_calls == ()
    mk = _Path(mesh)
    only_one_point = resolve_cross_face(mesh, [mk.v((1, 1, 0))], before)
    assert only_one_point.kept_calls == () and mesh.export_state() == before


# -- item 3: entry content of the recording helpers --------------------------------------------------

def _recorded_grid(n: int = 4) -> tuple[RecordedMesh, Mesh]:
    """A recorded grid and an identical, unrecorded twin (ids are allocated the same way)."""
    return RecordedMesh(_grid(n)), _grid(n)


def _edge_between(mesh, p, q):
    return next(e for e in mesh.all_edge_ids()
                if {tuple(mesh.vertex_position(v)) for v in mesh.edge_vertices(e)} == {p, q})


def test_kept_split_edge_records_arguments_results_and_position():
    rec, twin = _recorded_grid()
    edge = _edge_between(rec, (1.0, 1.0, 0.0), (1.0, 2.0, 0.0))
    a, b = rec.edge_vertices(edge)
    result = kept_split_edge(rec, edge, 0.25)
    assert result == twin.split_edge(edge, 0.25)                      # Core's results, in Core's order
    (entry,) = rec.kept
    assert isinstance(entry, KeptSplitEdge) and entry.op == "split_edge"
    assert (entry.edge_id, entry.t) == (edge, 0.25)
    assert (entry.vertex, entry.half_1, entry.half_2) == result
    assert entry.position == rec.vertex_position(entry.vertex)
    assert set(rec.edge_vertices(entry.half_1)) == {a, entry.vertex}  # the half at the edge's first end ...
    assert set(rec.edge_vertices(entry.half_2)) == {entry.vertex, b}  # ... and at its second
    assert rec.raw.export_state() == twin.export_state()              # Core was called unchanged


def test_kept_split_face_records_arguments_results_positions_and_halves():
    rec, twin = _recorded_grid()
    face = rec.all_face_ids()[5]
    corners = rec.face_vertices(face)
    a, b = corners[0], corners[2]
    pa, pb = rec.vertex_position(a), rec.vertex_position(b)
    inner = [tuple(pa[k] + f * (pb[k] - pa[k]) for k in range(3)) for f in (0.3, 0.7)]   # on the diagonal a - b
    result = kept_split_face(rec, face, a, b, inner)
    assert result == twin.split_face(face, a, b, inner)
    (entry,) = rec.kept
    assert isinstance(entry, KeptSplitFace) and entry.op == "split_face"
    assert (entry.face_id, entry.a, entry.b) == (face, a, b)
    assert entry.positions == tuple(inner)
    new_vs, new_edges, f1, f2 = result
    assert (entry.new_vertices, entry.new_edges, entry.face_1, entry.face_2) == (tuple(new_vs), tuple(new_edges), f1, f2)
    assert entry.created_positions == tuple(inner) == tuple(rec.vertex_position(v) for v in new_vs)
    assert len(new_vs) == 2 and len(new_edges) == 3
    # new edges in path order: a - p0, p0 - p1, p1 - b
    chain = [a, *new_vs, b]
    assert [set(rec.edge_vertices(e)) for e in new_edges] == [{u, w} for u, w in zip(chain, chain[1:])]
    # the halves right after the call
    assert entry.face_1_vertices == tuple(rec.face_vertices(f1)) and entry.face_2_vertices == tuple(rec.face_vertices(f2))
    assert set(entry.face_1_vertices) | set(entry.face_2_vertices) == {*corners, *new_vs}
    assert rec.raw.export_state() == twin.export_state()


def test_kept_split_face_keeps_cores_face_order_whatever_order_the_ends_are_given_in():
    """`split_face` orders its halves by boundary index, not by argument (AD-017 addendum K1); the entry holds
    what Core returned, the construction functions swap for their callers afterwards."""
    for ends in (lambda c: (c[0], c[2]), lambda c: (c[2], c[0])):
        rec, twin = _recorded_grid()
        face = rec.all_face_ids()[5]
        a, b = ends(rec.face_vertices(face))
        got = kept_split_face(rec, face, a, b)
        want = twin.split_face(face, a, b)
        (entry,) = rec.kept
        assert got == want and (entry.face_1, entry.face_2) == want[2:]
        assert entry.positions == () and entry.created_positions == () and entry.new_vertices == ()


def test_a_call_that_raises_leaves_no_entry_and_no_change():
    rec, twin = _recorded_grid()
    face = rec.all_face_ids()[0]
    a = rec.face_vertices(face)[0]
    with pytest.raises(MeshError):
        kept_split_face(rec, face, a, a)
    edge = rec.all_edge_ids()[0]
    with pytest.raises(MeshError):
        kept_split_edge(rec, edge, 1.0)
    assert rec.kept == [] and rec.raw.export_state() == twin.export_state()


def test_the_helpers_pass_a_plain_mesh_straight_through():
    mesh, twin = _grid(), _grid()
    edge = mesh.all_edge_ids()[0]
    assert kept_split_edge(mesh, edge, 0.5) == twin.split_edge(edge, 0.5)
    face = mesh.all_face_ids()[3]
    a, b = mesh.face_vertices(face)[:3:2]
    assert kept_split_face(mesh, face, a, b) == twin.split_face(face, a, b)
    cp = checkpoint(mesh)
    assert isinstance(cp, Checkpoint) and cp.mark == 0
    rollback(mesh, Checkpoint(twin.export_state(), 0))
    assert knife_resolve.mesh_content(mesh.export_state()) == knife_resolve.mesh_content(twin.export_state())


def test_rollback_restores_the_mesh_and_cuts_the_report_back_last_in_first_out():
    rec = RecordedMesh(_grid())
    edge = _edge_between(rec, (1.0, 1.0, 0.0), (1.0, 2.0, 0.0))
    kept_split_edge(rec, edge, 0.5)
    outer = checkpoint(rec)
    assert outer.mark == 1
    face = rec.all_face_ids()[7]
    a, b = rec.face_vertices(face)[:3:2]
    kept_split_face(rec, face, a, b)
    inner = checkpoint(rec)
    assert inner.mark == 2
    kept_split_edge(rec, rec.all_edge_ids()[0], 0.5)
    assert len(rec.kept) == 3
    rollback(rec, inner)
    assert [e.op for e in rec.kept] == ["split_edge", "split_face"]
    assert knife_resolve.mesh_content(rec.raw.export_state()) == knife_resolve.mesh_content(inner.state)
    rollback(rec, outer)
    assert [e.op for e in rec.kept] == ["split_edge"]
    assert knife_resolve.mesh_content(rec.raw.export_state()) == knife_resolve.mesh_content(outer.state)


# -- item 3 through the resolver ---------------------------------------------------------------------

def _two_edge_points_and_a_bent_cut(mesh):
    mk = _Path(mesh)
    return [mk.e((1, 1, 0), (1, 2, 0), 0.5), mk.f((1.3, 1.3, 0)), mk.f((1.7, 1.7, 0)), mk.e((2, 1, 0), (2, 2, 0), 0.5)]


def test_a_bent_cut_reports_two_edge_splits_then_one_face_split_with_its_interior_points():
    mesh = _grid()
    before = mesh.export_state()
    res = resolve_collected(mesh, _two_edge_points_and_a_bent_cut(mesh), before)
    assert (res.applied, res.runs) == (1, 1)
    e1, e2, cut = res.kept_calls
    assert [c.op for c in res.kept_calls] == ["split_edge", "split_edge", "split_face"]
    assert (e1.t, e2.t) == (0.5, 0.5)
    assert (e1.position, e2.position) == ((1.0, 1.5, 0.0), (2.0, 1.5, 0.0))
    assert (cut.a, cut.b) == (e1.vertex, e2.vertex)
    assert cut.positions == cut.created_positions == ((1.3, 1.3, 0.0), (1.7, 1.7, 0.0))
    assert [tuple(mesh.vertex_position(v)) for v in cut.new_vertices] == list(cut.created_positions)
    assert res.path_edges == list(cut.new_edges)                     # the report and the residue name the same edges
    assert_report_replays(before, res.kept_calls, mesh.export_state())


def test_a_straight_cut_reports_a_split_face_without_interior_points():
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    res = resolve_cross_face(mesh, [mk.e((0, 1, 0), (0, 2, 0), 0.5), mk.e((1, 1, 0), (1, 2, 0), 0.5)], before)
    assert [c.op for c in res.kept_calls] == ["split_edge", "split_edge", "split_face"]
    cut = res.kept_calls[2]
    assert cut.positions == () and cut.new_vertices == () and len(cut.new_edges) == 1
    assert_report_replays(before, res.kept_calls, mesh.export_state())


def test_the_report_is_what_the_mesh_calls_returned_in_call_order(monkeypatch):
    """Every kept entry is one real Core call with the ids and results Core gave, in order."""
    seen = []
    real_edge, real_face = Mesh.split_edge, Mesh.split_face

    def edge(self, edge_id, t=0.5):
        out = real_edge(self, edge_id, t)
        seen.append(("split_edge", edge_id, t, out))
        return out

    def face(self, face_id, a, b, positions=()):
        out = real_face(self, face_id, a, b, positions)
        seen.append(("split_face", face_id, a, b, tuple(tuple(p) for p in positions), out))
        return out

    mesh = _grid()
    before = mesh.export_state()
    path = _two_edge_points_and_a_bent_cut(mesh)
    monkeypatch.setattr(Mesh, "split_edge", edge)
    monkeypatch.setattr(Mesh, "split_face", face)
    res = resolve_cross_face(mesh, path, before)
    assert len(seen) == len(res.kept_calls) == 3
    for call, entry in zip(seen, res.kept_calls):
        assert call[0] == entry.op
        if entry.op == "split_edge":
            assert call[1:3] == (entry.edge_id, entry.t) and call[3] == (entry.vertex, entry.half_1, entry.half_2)
        else:
            assert call[1:5] == (entry.face_id, entry.a, entry.b, entry.positions)
            new_vs, new_edges, f1, f2 = call[5]
            assert (tuple(new_vs), tuple(new_edges), f1, f2) == (entry.new_vertices, entry.new_edges, entry.face_1, entry.face_2)


# -- items 2, 3: nested rollbacks --------------------------------------------------------------------

def _loop_at_an_edge_point(mk):
    """An edge point, two clicks in the face on its left, back to the edge point: a loop at a single vertex."""
    start = mk.e((1, 0, 0), (1, 1, 0), 0.5)
    return [start, mk.f((0.3, 0.3, 0)), mk.f((0.3, 0.7, 0)), start, {"kind": "break", "reason": "closed", "cyclic": False}]


class _CountCoreCalls:
    """Counts every real `split_face` / `split_edge` call (also the ones a rollback takes back)."""

    def __init__(self, monkeypatch):
        self.edge = self.face = 0
        real_edge, real_face = Mesh.split_edge, Mesh.split_face

        def edge(inner, *a, **k):
            self.edge += 1
            return real_edge(inner, *a, **k)

        def face(inner, *a, **k):
            self.face += 1
            return real_face(inner, *a, **k)

        monkeypatch.setattr(Mesh, "split_edge", edge)
        monkeypatch.setattr(Mesh, "split_face", face)


def test_a_dropped_run_leaves_no_entry_and_the_kept_run_after_it_does(monkeypatch):
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
    counted = _CountCoreCalls(monkeypatch)
    res = resolve_collected(mesh, path, before)
    assert (res.applied, res.runs) == (1, 2)
    assert counted.edge > 2                                               # the dropped run's end splits did happen ...
    assert [c.op for c in res.kept_calls] == ["split_edge", "split_edge", "split_face"]   # ... and are not reported
    assert {c.position for c in res.kept_calls if c.op == "split_edge"} == {(1.0, 1.5, 0.0), (2.0, 1.5, 0.0)}
    assert_report_replays(before, res.kept_calls, mesh.export_state())


def test_a_dropped_bridge_candidate_leaves_no_entry_and_the_next_one_is_reported(monkeypatch):
    mesh = _grid()
    before = mesh.export_state()
    path = _loop_at_an_edge_point(_Path(mesh))
    counted = _CountCoreCalls(monkeypatch)
    real_problem, seen = knife_resolve.face_problem, []

    def first_candidate_fails(m, f):
        seen.append(f)
        return "forced" if len(seen) == 1 else real_problem(m, f)

    monkeypatch.setattr(knife_resolve, "face_problem", first_candidate_fails)
    res = resolve_cross_face(mesh, path, before)
    assert res.loops_built == 1 and (res.applied, res.runs) == (1, 1)
    assert counted.face == 4                                              # two calls per candidate: the first was taken back
    assert [c.op for c in res.kept_calls] == ["split_edge", "split_face", "split_face"]
    assert assert_report_replays(before, res.kept_calls, mesh.export_state())   # True: the dropped candidate burned ids the report does not know


def test_a_dropped_run_with_dropped_candidates_inside_leaves_nothing_and_a_later_run_is_kept(monkeypatch):
    """Candidates inside a run inside the session: every candidate fails, so the run is dropped with its end
    split; a second chain after it is cut and reported."""
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    loop = _loop_at_an_edge_point(mk)
    second = [mk.e((2, 1, 0), (2, 2, 0), 0.5), mk.e((3, 1, 0), (3, 2, 0), 0.5)]
    monkeypatch.setattr(knife_resolve, "face_problem", lambda m, f: "forced")
    res = resolve_cross_face(mesh, loop + second, before)
    assert dict(res.loops_dropped) == {knife_resolve.LOOP_NO_BRIDGE: 1}
    assert (res.applied, res.runs) == (1, 2)
    assert [c.op for c in res.kept_calls] == ["split_edge", "split_edge", "split_face"]
    assert {c.position for c in res.kept_calls if c.op == "split_edge"} == {(2.0, 1.5, 0.0), (3.0, 1.5, 0.0)}
    assert_report_replays(before, res.kept_calls, mesh.export_state())


def test_a_closed_shape_taken_back_leaves_no_entry(monkeypatch):
    for how in ("problem", "second split raises"):
        mesh = _grid()
        before = mesh.export_state()
        mk = _Path(mesh)
        path = [mk.f((0.2, 0.2, 0)), mk.f((0.8, 0.3, 0)), mk.f((0.5, 0.8, 0))]
        with monkeypatch.context() as m:
            if how == "problem":
                m.setattr(knife_resolve, "face_problem", lambda mesh_, f: "forced")
            else:
                real, calls = knife_resolve.kept_split_face, []

                def second_raises(*args):
                    calls.append(args)
                    if len(calls) == 2:
                        raise MeshError("forced")
                    return real(*args)

                m.setattr(knife_resolve, "kept_split_face", second_raises)
            res = resolve_collected(mesh, path, before)
        (shape,) = res.closed_shapes
        assert not shape.built, how
        assert res.kept_calls == (), how
        assert knife_resolve.mesh_content(mesh.export_state()) == knife_resolve.mesh_content(before), how


def test_a_closed_shape_that_is_built_is_reported_as_two_face_splits():
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    res = resolve_collected(mesh, [mk.f((0.2, 0.2, 0)), mk.f((0.8, 0.3, 0)), mk.f((0.5, 0.8, 0))], before)
    assert res.closed_shapes[0].built
    assert [c.op for c in res.kept_calls] == ["split_face", "split_face"]
    assert_report_replays(before, res.kept_calls, mesh.export_state())


# -- item 4: a session taken back reports nothing ---------------------------------------------------

def test_a_session_check_commit_takes_back_leaves_an_empty_report():
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    res = resolve_cross_face(mesh, [mk.e((0, 1, 0), (0, 2, 0), 0.5), mk.e((1, 1, 0), (1, 2, 0), 0.5)], before)
    assert len(res.kept_calls) == 3
    # A face turned the other way round next to its neighbours (as in test_knife_resolve): the whole session goes.
    fid = mesh.all_face_ids()[-1]
    corners = mesh.face_vertices(fid)
    mesh.remove_face(fid)
    mesh.add_face(corners[::-1])
    check = check_commit(mesh, before, res)
    assert check.rolled_back and check.after_state is None
    assert res.kept_calls == ()
    assert knife_resolve.mesh_content(mesh.export_state()) == knife_resolve.mesh_content(before)


def test_a_session_that_commits_keeps_its_report():
    mesh = _grid()
    before = mesh.export_state()
    mk = _Path(mesh)
    res = resolve_cross_face(mesh, [mk.e((0, 1, 0), (0, 2, 0), 0.5), mk.e((1, 1, 0), (1, 2, 0), 0.5)], before)
    check = check_commit(mesh, before, res)
    assert check.after_state is not None and not check.rolled_back
    assert len(res.kept_calls) == 3
    nothing = KnifeResolution()
    assert check_commit(Mesh.from_state(before), before, nothing).after_state is None and nothing.kept_calls == ()


# -- item 5: identity replay over a seeded fuzz ------------------------------------------------------

FUZZ_ASSETS = ("subd_cube", "head_basemesh", "tie_grid")
FUZZ_PER_ASSET = 110


@contextlib.contextmanager
def _probe_on_path():
    """The probe puts `experiments/`, `examples/` and `src/` first on `sys.path` while it imports and builds
    its fixtures; keep that to this block so no other test sees the change."""
    saved = list(sys.path)
    sys.path[:0] = [str(_ROOT / "examples"), str(_ROOT / "experiments")]
    try:
        yield
    finally:
        sys.path[:] = saved


@pytest.fixture(scope="module")
def fuzz_sessions():
    """Camera-free paths from the symmetric-Knife probe's generator (Production click rules through `KnifeTool`):
    [(asset, session-start state, resolver path)]. The probe imports without pyglet."""
    with _probe_on_path():
        try:
            from topology import symmetry_knife_probe as probe
        except ImportError as exc:                                # pragma: no cover - the probe is importable today
            pytest.skip(f"probe not importable: {exc}")
        out = []
        for name in FUZZ_ASSETS:
            for s in probe.fuzz_sessions_for(name, random.Random(f"kept-calls/{name}"), FUZZ_PER_ASSET):
                out.append((name, s.state, s.path))
    return out


def test_the_report_replayed_verbatim_rebuilds_the_resolved_mesh_over_a_camera_free_fuzz(fuzz_sessions):
    assert len(fuzz_sessions) >= 300
    entries = burned = 0
    kinds = set()
    for i, (name, state, path) in enumerate(fuzz_sessions):
        mesh = Mesh.from_state(state)
        res = resolve_cross_face(mesh, path, state)
        resolved = mesh.export_state()
        burned += assert_report_replays(state, res.kept_calls, resolved, context=f"[{name} #{i}]")
        entries += len(res.kept_calls)
        kinds |= {c.op for c in res.kept_calls}
    assert kinds == {"split_edge", "split_face"}
    assert entries >= 300                                             # the fuzz does cut
    assert burned > 0                                                 # and some sessions took calls back (ids burned)


def test_the_report_is_the_same_on_a_second_run_of_the_same_session(fuzz_sessions):
    """Deterministic (AD-017 decision #1): same mesh state and path, same report — entry for entry, ids included."""
    for name, state, path in fuzz_sessions[::25]:
        first = resolve_cross_face(Mesh.from_state(state), path, state)
        second = resolve_cross_face(Mesh.from_state(state), path, state)
        assert first.kept_calls == second.kept_calls, name
