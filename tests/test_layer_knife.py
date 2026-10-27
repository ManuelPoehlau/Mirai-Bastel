"""AD-025 Phase 5 (T-6): the Knife on a mesh with point layers (morph targets).

Rule (AD-025 §3 / §4.1): an edge point gets the edge blend (1 - t, t) of its click-time edge's ends;
an interior point gets the barycentric weights of the triangle it was picked on, over the **original**
face's corners (`picking.face_hit`; headless targets get the same rule from `face_point_origin`); a
point the run makes where it crosses itself is the affine blend of its segment's ends. The values do
not depend on how the resolver decomposes or bridges a cut, Undo / Redo and every rollback stay exact,
the cut's topology is the one without layers, and the symmetric Knife replays the mirror side at the
mapped t with the mirrored origins (F-6).

Every check of a value is against an independent computation over the session-start mesh (area
barycentrics, edge parameter from positions), at 1e-12 on values in [-1, 1].
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, PointLayerInfo
from core.mesh import MeshError
from mirai.symmetric_knife import coordinate_knife
from mirai.topology import knife_resolve as kr
from tests.knife_parity_driver import build_grid, quiet
from tests.mesh_invariants import assert_layer_invariants
from tests.symmetric_knife_support import T_f, T_p, T_v, fuzz_paths, make_tool, start_state, vertex_at
from viewport.derived import triangulate_mesh_face

TOL = 1e-12
ZERO = (0.0, 0.0, 0.0)


# -- fixtures ------------------------------------------------------------------------------------


def add_layers(mesh: Mesh, seed: int = 0, *, mirrored: bool = False) -> list:
    """Three layers (the automated tests use 3, Manu's test 1 - AD-025 §16): two dense, one sparse
    (every third vertex). `mirrored`: a vertex at the X-mirror of another gets the X-mirror of its
    value (a symmetric target)."""
    rng = random.Random(seed)
    by_pos = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
    lids = []
    for i, name in enumerate(("Smile", "Blink", "Brow")):
        lid = mesh.add_point_layer(PointLayerInfo(name))
        lids.append(lid)
        for v in sorted(mesh.all_vertex_ids(), key=int):
            if i == 2 and int(v) % 3:
                continue
            p = mesh.vertex_position(v)
            if mirrored and p[0] < 0.0:
                continue
            value = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            if mirrored and p[0] == 0.0:
                value = (0.0, value[1], value[2])
            mesh.set_layer_value(lid, v, value)
            if mirrored and p[0] > 0.0:
                partner = by_pos.get((-p[0], p[1], p[2]))
                if partner is not None:
                    mesh.set_layer_value(lid, partner, (-value[0], value[1], value[2]))
    return lids


def layered_state(state: dict, seed: int = 0, *, mirrored: bool = False) -> dict:
    mesh = Mesh.from_state(state)
    add_layers(mesh, seed, mirrored=mirrored)
    return mesh.export_state()


def without_layers(state: dict) -> dict:
    return {k: v for k, v in state.items() if k not in ("point_layers",) and not k.endswith("_counter")}


def area_weights(a, b, c, p) -> tuple[float, float, float]:
    """Barycentric weights of p in (a, b, c) from signed areas - independent of `triangle_origin`."""
    def sub(x, y):
        return (x[0] - y[0], x[1] - y[1], x[2] - y[2])

    def cross(x, y):
        return (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])

    def dot(x, y):
        return x[0] * y[0] + x[1] * y[1] + x[2] * y[2]

    n = cross(sub(b, a), sub(c, a))
    nn = dot(n, n)
    wa = dot(cross(sub(b, p), sub(c, p)), n) / nn
    wb = dot(cross(sub(c, p), sub(a, p)), n) / nn
    return wa, wb, 1.0 - wa - wb


def barycentric_value(start: Mesh, face, lid, p, *, corners=None):
    """The rule's value at p inside `face` of the session-start mesh: the triangle of the face's
    triangulation that holds p (least outside), its corners' values with the area weights.
    `corners`: a position map to the corners whose values count instead (the mirror side)."""
    best = None
    for tri in triangulate_mesh_face(start, face):
        pts = [start.vertex_position(v) for v in tri]
        w = area_weights(*pts, p)
        key = max(0.0, -min(w))
        if best is None or key < best[0]:
            best = (key, tri, w)
    _, tri, w = best
    assert best[0] <= 1e-9, "point outside its face"
    if corners is not None:
        by_pos = {tuple(start.vertex_position(v)): v for v in start.all_vertex_ids()}
        tri = [by_pos[tuple(corners(start.vertex_position(v)))] for v in tri]
    return tuple(sum(wi * start.layer_value(lid, v)[k] for wi, v in zip(w, tri)) for k in range(3))


def edge_value(start: Mesh, edge_ends, lid, p):
    a, b = edge_ends
    pa, pb = start.vertex_position(a), start.vertex_position(b)
    t = math.dist(pa, p) / math.dist(pa, pb)
    da, db = start.layer_value(lid, a), start.layer_value(lid, b)
    return tuple(x * (1.0 - t) + y * t for x, y in zip(da, db))


def on_segment(pa, pb, p) -> bool:
    length = math.dist(pa, pb)
    return abs(math.dist(pa, p) + math.dist(p, pb) - length) <= 1e-12 * max(1.0, length) and min(
        math.dist(pa, p), math.dist(p, pb)) > 1e-12


def close(a, b, tol=TOL) -> bool:
    return max(abs(x - y) for x, y in zip(a, b)) <= tol


def check_values(start: Mesh, mesh: Mesh, path: list[dict], *, mirror=None) -> dict:
    """Every new vertex's value in every layer against the rule. Returns counts per category.
    `mirror`: x -> mirrored position (symmetric commits: mirror-side points are checked through
    their source point's record)."""
    lids = mesh.point_layer_ids()
    faces = {}
    for p in path:
        if p.get("kind") == "face":
            faces[tuple(p["position"])] = p["face_id"]
            if mirror is not None:
                faces[tuple(mirror(p["position"]))] = ("mirror", p["face_id"], tuple(p["position"]))
    edges = [start.edge_vertices(e) for e in start.all_edge_ids()]
    counts = {"face": 0, "edge": 0, "other": 0}
    for v in mesh.all_vertex_ids():
        if start.is_valid_vertex(v):
            continue
        pos = tuple(mesh.vertex_position(v))
        hit = faces.get(pos)
        if hit is not None:
            counts["face"] += 1
            if isinstance(hit, tuple):
                # A mirror-side interior point: the source point's weights on the mirrored corners (the
                # origin goes through the vertex map; the mirror face's own triangulation may take the
                # other diagonal, AD-025 §16).
                _, fid, src = hit
                expected = {lid: barycentric_value(start, fid, lid, src, corners=mirror) for lid in lids}
            else:
                expected = {lid: barycentric_value(start, hit, lid, pos) for lid in lids}
        else:
            ends = next((ab for ab in edges if on_segment(start.vertex_position(ab[0]), start.vertex_position(ab[1]), pos)), None)
            if ends is None:
                counts["other"] += 1
                continue
            counts["edge"] += 1
            expected = {lid: edge_value(start, ends, lid, pos) for lid in lids}
        for lid in lids:
            assert close(mesh.layer_value(lid, v), expected[lid]), (v, pos, lid, mesh.layer_value(lid, v), expected[lid])
    return counts


def grid_face(mesh: Mesh, corner) -> object:
    return next(f for f in mesh.all_face_ids()
                if min(tuple(mesh.vertex_position(v)) for v in mesh.face_vertices(f)) == (*map(float, corner), 0.0))


def run(mesh: Mesh, targets, *, coordinator=None):
    knife, scene = make_tool(mesh, coordinator=coordinator)
    with quiet():
        for t in targets:
            assert knife.click(t(knife) if callable(t) else t), t
        cmd = knife.commit()
    return knife, scene, cmd


def assert_undo_redo_exact(scene, mesh: Mesh, start_state_: dict) -> None:
    after = mesh.export_state()
    counters = {k: v for k, v in after.items() if k.endswith("_counter")}
    scene.history.undo()
    undone = mesh.export_state()
    assert without_layers(undone) == without_layers(start_state_)
    assert undone["point_layers"] == start_state_["point_layers"]
    assert all(undone[k] >= start_state_[k] for k in counters)
    scene.history.redo()
    assert mesh.export_state() == after


# -- the rule on explicit cuts -------------------------------------------------------------------


def test_open_cut_interior_and_edge_points_follow_the_rule():
    mesh = build_grid(4)
    add_layers(mesh, 1)
    start = mesh.export_state()
    ref = Mesh.from_state(start)
    f = grid_face(mesh, (1, 1))
    e_right = next(e for e in mesh.face_edges(f)
                   if all(mesh.vertex_position(v)[0] == 2.0 for v in mesh.edge_vertices(e)))
    targets = [T_v(vertex_at(mesh, (1.0, 1.0, 0.0))), T_f(f, (1.3, 1.6, 0.0)), T_f(f, (1.7, 1.45, 0.0)),
               {"kind": "edge", "edge_id": e_right, "t": 0.3}]
    knife, scene, cmd = run(mesh, targets)
    assert cmd is not None
    assert all("origin" in p for p in knife.path if p["kind"] == "face")
    counts = check_values(ref, mesh, knife.path)
    assert counts == {"face": 2, "edge": 1, "other": 0}
    assert_layer_invariants(mesh)
    assert_undo_redo_exact(scene, mesh, start)


def _closed_shape(mesh: Mesh):
    f = grid_face(mesh, (1, 1))
    pts = [(1.3, 1.4, 0.0), (1.6, 1.3, 0.0), (1.7, 1.7, 0.0), (1.35, 1.65, 0.0)]
    return [T_f(f, p) for p in pts] + [lambda knife: T_p(knife.points[0]["pid"])]


def test_closed_shape_values_are_independent_of_the_bridges(monkeypatch):
    """Two `split_face` calls with a burned intermediate face; another bridge rule gives other faces
    and the same value at every point, bit for bit (AD-025 §4.1, X-10)."""
    def commit_with(rule):
        mesh = build_grid(4)
        add_layers(mesh, 2)
        start = mesh.export_state()
        if rule is not None:
            monkeypatch.setattr(kr, "select_bridge", rule)
        knife, scene, cmd = run(mesh, _closed_shape(mesh))
        monkeypatch.undo()
        assert cmd is not None and knife.last_resolution.closed_shapes[0].built
        values = {tuple(mesh.vertex_position(v)): tuple(mesh.layer_value(l, v) for l in mesh.point_layer_ids())
                  for v in mesh.all_vertex_ids() if int(v) >= start["vertex_id_counter"]}
        counts = check_values(Mesh.from_state(start), mesh, knife.path)
        assert counts == {"face": 4, "edge": 0, "other": 0}
        assert_undo_redo_exact(scene, mesh, start)
        return values, sorted(sorted(map(int, mesh.face_vertices(f))) for f in mesh.all_face_ids())

    original = kr.select_bridge

    def far_bridges(mesh, boundary, loop_positions):
        i1, bv1, i2, bv2 = original(mesh, boundary, loop_positions)
        k, n = len(loop_positions), len(boundary)
        return (i1 + 1) % k, boundary[(boundary.index(bv1) + 1) % n], (i2 + 1) % k, boundary[(boundary.index(bv2) + 1) % n]

    default_values, default_faces = commit_with(None)
    other_values, other_faces = commit_with(far_bridges)
    assert default_faces != other_faces
    assert default_values == other_values


def test_a_self_crossing_run_gives_its_crossing_the_blend():
    """A run that crosses itself inside one triangle of the face: the crossing X is a vertex the
    resolver makes (no click); its origin is the blend of its segment's ends, which inside one
    triangle is the barycentric rule at X."""
    mesh = build_grid(4)
    add_layers(mesh, 3)
    start = mesh.export_state()
    ref = Mesh.from_state(start)
    f = grid_face(mesh, (1, 1))
    targets = [T_v(vertex_at(mesh, (1.0, 1.0, 0.0))), T_f(f, (1.8, 1.2, 0.0)), T_f(f, (1.8, 1.5, 0.0)),
               T_f(f, (1.4, 1.05, 0.0)), T_v(vertex_at(mesh, (2.0, 1.0, 0.0)))]
    knife, scene, cmd = run(mesh, targets)
    assert cmd is not None and knife.last_resolution.loops_built == 1, knife.last_resolution
    counts = check_values(ref, mesh, knife.path)
    assert counts["face"] == 3 and counts["other"] == 1
    (x,) = [v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)
            and tuple(mesh.vertex_position(v)) not in {tuple(p["position"]) for p in knife.path if p["kind"] == "face"}]
    for lid in mesh.point_layer_ids():
        assert close(mesh.layer_value(lid, x), barycentric_value(ref, f, lid, mesh.vertex_position(x)))
    assert_undo_redo_exact(scene, mesh, start)


def test_rollbacks_inside_the_commit_and_a_refused_commit_stay_exact(monkeypatch):
    """Dropped runs (their checkpoint rolled back), the whole-session rollback of a broken result
    (`check_commit`) and a cancelled session leave every layer exactly as it was."""
    mesh = build_grid(4)
    add_layers(mesh, 4)
    start = mesh.export_state()
    rollbacks = []
    real = kr.rollback
    monkeypatch.setattr(kr, "rollback", lambda m, cp: (rollbacks.append(cp), real(m, cp))[1])
    # a closed shape whose loop the bridge cannot hold (an interior point on top of a corner: dropped)
    knife, scene, cmd = run(mesh, _closed_shape(mesh))
    assert cmd is not None
    scene.history.undo()
    assert mesh.export_state()["point_layers"] == start["point_layers"]
    assert without_layers(mesh.export_state()) == without_layers(start)

    # a commit that check_commit takes back as a whole
    monkeypatch.setattr(kr, "integrity_problem", lambda *a, **k: "forced")
    knife, scene, cmd = run(mesh, _closed_shape(mesh))
    assert cmd is None and knife.last_problem == "forced"
    assert mesh.export_state()["point_layers"] == start["point_layers"]
    assert without_layers(mesh.export_state()) == without_layers(start)

    # cancel: nothing was ever written
    knife, _ = make_tool(mesh, coordinator=None)
    with quiet():
        for t in _closed_shape(mesh):
            knife.click(t(knife) if callable(t) else t)
        knife.cancel()
    assert mesh.export_state()["point_layers"] == start["point_layers"]


def test_a_dropped_candidate_leaves_no_value_behind(monkeypatch):
    """`close_loop_at_vertex` takes back every bridge candidate that does not fit (a checkpoint
    rollback per candidate): the kept candidate's values follow the rule, Undo is exact."""
    mesh = build_grid(4)
    add_layers(mesh, 5)
    start = mesh.export_state()
    ref = Mesh.from_state(start)
    tried = []
    real = kr.kept_split_face

    def first_candidates_fail(m, face_id, a, b, positions=()):
        tried.append(face_id)
        result = real(m, face_id, a, b, positions)
        if len(tried) <= 2:   # the first candidate's second call: the candidate is rolled back
            if len(tried) == 2:
                raise MeshError("forced: candidate does not fit")
        return result

    monkeypatch.setattr(kr, "kept_split_face", first_candidates_fail)
    f = grid_face(mesh, (1, 1))
    targets = [T_v(vertex_at(mesh, (1.0, 1.0, 0.0))), T_f(f, (1.8, 1.2, 0.0)), T_f(f, (1.8, 1.5, 0.0)),
               T_f(f, (1.4, 1.05, 0.0)), T_v(vertex_at(mesh, (2.0, 1.0, 0.0)))]
    knife, scene, cmd = run(mesh, targets)
    assert cmd is not None and len(tried) > 3
    check_values(ref, mesh, knife.path)
    assert_layer_invariants(mesh)
    assert_undo_redo_exact(scene, mesh, start)


def test_the_core_backstop_drops_a_face_point_without_an_origin():
    """A path record without an origin (a host bypassing the tool) on a layered mesh: Core refuses
    the interior call, the run is dropped, the mesh is untouched."""
    mesh = build_grid(4)
    add_layers(mesh, 6)
    start = mesh.export_state()
    f = grid_face(mesh, (1, 1))
    path = [{"pid": 0, "kind": "vertex", "vertex_id": vertex_at(mesh, (1.0, 1.0, 0.0))},
            {"pid": 1, "kind": "face", "face_id": f, "position": (1.5, 1.4, 0.0)},
            {"pid": 2, "kind": "vertex", "vertex_id": vertex_at(mesh, (2.0, 2.0, 0.0))}]
    session = kr.SessionStart(mesh)
    with quiet():
        res = kr.resolve_cross_face(mesh, path, session)
    assert res.applied == 0 and res.runs == 1
    assert session.unchanged()
    session.abandon()
    assert mesh.export_state() == start


# -- randomized sessions: plain and symmetric ------------------------------------------------------


@pytest.mark.parametrize("name", ["tie_grid", "hole_grid", "head_basemesh"])
def test_random_sessions_follow_the_rule_and_keep_the_topology(name):
    """Fuzzed sessions through the Production click rules (vertices, edge points, face points, closes,
    lifts, earlier points, in-session Undo) on a layered mesh: the cut is the one without layers,
    every edge and interior point follows its rule, L1-L5 hold, Undo / Redo exact."""
    base = start_state(name)
    state = layered_state(base, 7)
    rnd = random.Random(f"layers-{name}")
    totals = {"face": 0, "edge": 0, "other": 0}
    for path in fuzz_paths(state, rnd, 25):
        mesh, plain = Mesh.from_state(state), Mesh.from_state(base)
        for m in (mesh, plain):
            knife, scene = make_tool(m, coordinator=None)
            knife._path = list(path)
            with quiet():
                cmd = knife.commit()
            if m is mesh:
                layered_cmd, layered_scene = cmd, scene
        assert without_layers(mesh.export_state()) == without_layers(plain.export_state())
        if layered_cmd is None:
            assert without_layers(mesh.export_state()) == without_layers(state)
            assert mesh.export_state()["point_layers"] == state["point_layers"]
            continue
        assert_layer_invariants(mesh)
        counts = check_values(Mesh.from_state(state), mesh, path) if name != "head_basemesh" else None
        if counts:
            for k in totals:
                totals[k] += counts[k]
        assert_undo_redo_exact(layered_scene, mesh, state)
    if name != "head_basemesh":
        assert totals["face"] > 5 and totals["edge"] > 5, totals


def _mirror_x(p):
    return (-p[0], p[1], p[2])


@pytest.mark.parametrize("name", ["tie_grid", "hole_grid"])
def test_symmetric_sessions_mirror_the_values(name):
    """Symmetric Knife (F-6, Phase 5): with a symmetric target every mirror-side value is the X-mirror
    of its source value (the mirror split runs at the mapped t, interior origins go through the vertex
    map); every value also follows its own side's rule; the cut is the one without layers."""
    base = start_state(name)
    state = layered_state(base, 8, mirrored=True)
    rnd = random.Random(f"sym-layers-{name}")
    committed = mirrored_points = 0
    for path in fuzz_paths(state, rnd, 25, guarded=True):
        mesh, plain = Mesh.from_state(state), Mesh.from_state(base)
        cmds = []
        for m in (mesh, plain):
            knife, scene = make_tool(m)
            knife._path = list(path)
            with quiet():
                cmds.append((knife.commit(), scene))
        assert without_layers(mesh.export_state()) == without_layers(plain.export_state())
        cmd, scene = cmds[0]
        if cmd is None:
            continue
        committed += 1
        ref = Mesh.from_state(state)
        check_values(ref, mesh, path, mirror=_mirror_x)
        new = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)}
        for pos, v in new.items():
            if pos[0] <= 0.0:
                continue
            partner = new.get(_mirror_x(pos))
            assert partner is not None, pos
            mirrored_points += 1
            for lid in mesh.point_layer_ids():
                assert close(mesh.layer_value(lid, partner), _mirror_x(mesh.layer_value(lid, v))), (pos, lid)
        assert_layer_invariants(mesh)
        assert_undo_redo_exact(scene, mesh, state)
    assert committed >= 5 and mirrored_points >= 10, (committed, mirrored_points)


def test_symmetric_edge_point_on_a_reversed_mirror_edge_uses_the_mapped_t():
    """An asymmetric target and a mirror edge stored the other way round: the mirror point's value is
    the blend of the mirror ends at the mirror point (1 - t), not the midpoint (the old t = 0.5 replay)."""
    state = start_state("tie_grid")
    mesh = Mesh.from_state(state)
    add_layers(mesh, 9)   # not mirrored: each side follows its own ends
    ref = Mesh.from_state(mesh.export_state())
    by_pos = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
    # find an edge on the +X side whose mirror is stored reversed
    found = None
    for e in sorted(mesh.all_edge_ids()):
        a, b = mesh.edge_vertices(e)
        pa, pb = mesh.vertex_position(a), mesh.vertex_position(b)
        if min(pa[0], pb[0]) <= 0.0:
            continue
        ma, mb = by_pos[_mirror_x(pa)], by_pos[_mirror_x(pb)]
        me = next((x for x in mesh.vertex_edges(ma) if set(mesh.edge_vertices(x)) == {ma, mb}), None)
        if me is not None and mesh.edge_vertices(me) == (mb, ma):
            found = (e, a, b, me)
            break
    assert found is not None
    e, a, b, me = found
    f = mesh.edge_faces(e)[0]
    other = next(v for v in mesh.face_vertices(f) if v not in (a, b) and mesh.vertex_position(v)[0] > 0.0)
    knife, scene, cmd = run(mesh, [T_v(other), {"kind": "edge", "edge_id": e, "t": 0.3}], coordinator=coordinate_knife)
    assert cmd is not None, knife.last_problem
    new = [v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)]
    assert len(new) == 2
    for v in new:
        pos = mesh.vertex_position(v)
        ends = (a, b) if pos[0] > 0.0 else ref.edge_vertices(me)
        for lid in mesh.point_layer_ids():
            assert close(mesh.layer_value(lid, v), edge_value(ref, ends, lid, pos))
            da, db = ref.layer_value(lid, ends[0]), ref.layer_value(lid, ends[1])
            if not close(da, db, 1e-3):  # the old t = 0.5 replay would have given the midpoint
                assert not close(mesh.layer_value(lid, v), tuple(0.5 * (x + y) for x, y in zip(da, db)), 1e-6)
