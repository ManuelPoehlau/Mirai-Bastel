"""Weighted transforms in the Core (AD-SYM-05, slice SS1): the SS1 gate tests of §6.

- T-2  all weights 1.0 == no weights, bitwise (Move/Rotate/Scale, with and without symmetry,
       with a basis, Rotate with an axis change).
- T-5  refusals before anything moves.
- T-6  symmetric + weighted exactness on `subd_cube` X and `head_basemesh` X.
- T-7  P-a: falloff seam vertices (absolute, on the plane, exempt from both seam checks);
       a selected seam vertex keeps today's refusals and texts.
- T-8  R-6: the SS0 straddling quad and a straddling fixture with seam vertices in the falloff.
- the restated F3 tripwire (5): what the Core `_on_begin` reads from `params`.

Weights here are hand-built and pair-consistent (no SS2 field code in SS1): one weight per
pair, computed once from the member on the +X side; categories by side (plain on +X,
conjugate on -X, falloff seam on the plane). Pair consistency is the caller's precondition
(AD-SYM-05 §4.3, R6-3); the Core gets weights and categories only.
T-1 are the existing Core suites, T-3 `test_soft_selection_replay.py`, T-4 the ported
`test_soft_selection_ops.py`, T-9 the Mehlsack and S1 suites under `experiments/`.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
import tests.soft_selection_fixtures  # noqa: F401  (puts examples/ on the path for the OBJ loader)

from core import HistoryStack, Mesh, MoveOperation, OperationContext, RotateOperation, ScaleOperation
from core.operations.transform import (
    SeamConstraintError,
    VertexTransformOperation,
    mirror_point,
    rotate_around_axis,
)
from mirai.interaction.tools.selection_helpers import _VertexSelectionView as _View
from mirai.interaction.tools.selection_helpers import resolve_symmetry
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.scene_factory import build_core_scene_from_obj, mesh_from_positions_and_faces
from mirai.symmetry import CorrespondenceState, SymmetryState, symmetry_state, vertex_correspondence
from mirai.symmetry_axis import set_symmetry_axis

_MESHES = Path(__file__).resolve().parent.parent / "examples" / "meshes"
ORIGIN = (0.0, 0.0, 0.0)
NX = (1.0, 0.0, 0.0)
_C, _S = math.cos(math.pi / 6), math.sin(math.pi / 6)
TILTED = ((_C, _S, 0.0), (-_S, _C, 0.0), (0.0, 0.0, 1.0))
OBLIQUE = (0.3, 1.0, -0.2)
OPS = {"move": MoveOperation, "rotate": RotateOperation, "scale": ScaleOperation,
       "scale-tilted": ScaleOperation}


def _positions(mesh):
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def _ctx(mesh, vertex_ids, history=None, **params):
    return OperationContext(target=mesh, selection=_View(set(vertex_ids)),
                            history=history if history is not None else HistoryStack(), params=params)


def _steps(op, n=60, seed=3, axis_change=False):
    rng = random.Random(seed)
    if op == "move":
        return [{"delta": tuple(rng.uniform(-0.04, 0.04) for _ in range(3))} for _ in range(n)]
    if op == "rotate":
        axes = [OBLIQUE, (1.0, -0.4, 0.2)] if axis_change else [OBLIQUE]
        return [{"axis": axes[i % len(axes)], "angle": rng.uniform(-0.08, 0.08)} for i in range(n)]
    basis = TILTED if op == "scale-tilted" else None
    return [{"factor": tuple(rng.uniform(0.97, 1.03) for _ in range(3)), "basis": basis}
            for _ in range(n)]


@lru_cache(maxsize=None)
def _asset_state(name):
    return build_core_scene_from_obj(_MESHES / name).mesh.export_state()


def _asset(name):
    mesh = Mesh.from_state(_asset_state(name))
    set_symmetry_axis(mesh, "X")
    return mesh


ASSETS = {"subd_cube": "SubD_Cube.obj", "head_basemesh": "head_basemesh.obj"}


# -- fixtures for the symmetric weighted gesture -----------------------------------------


def _seed_ring(mesh, corr):
    """The paired +X vertex nearest the plane plus its paired +X one-ring."""
    side = sorted((mesh.vertex_position(v)[0], int(v), v) for v, c in corr.items()
                  if c.state is CorrespondenceState.PAIRED and mesh.vertex_position(v)[0] > 0.0)
    first = side[0][2]
    seeds = {first}
    for eid in mesh.vertex_edges(first):
        for w in mesh.edge_vertices(eid):
            if corr[w].state is CorrespondenceState.PAIRED and mesh.vertex_position(w)[0] > 0.0:
                seeds.add(w)
    return seeds


def _symmetric_weights(mesh, seeds, radius, selected_seam=()):
    """Pair-consistent weights and categories (K-side) for explicit `seeds` on +X.

    Weight `1 - d / radius`, `d` the distance from the +X representative of a vertex (itself on
    +X or on the plane, its mirror on -X) to the nearest seed; one value per pair by
    construction. Selected seam vertices are seeds with weight 1.0."""
    corr = vertex_correspondence(mesh)
    seed_pos = [mesh.vertex_position(s) for s in seeds]
    weights, mirrored, falloff = {}, set(), set()
    for vid in mesh.all_vertex_ids():
        pos = mesh.vertex_position(vid)
        rep = pos if pos[0] >= 0.0 else mirror_point(pos, ORIGIN, NX)
        d = min(math.dist(rep, s) for s in seed_pos)
        w = 1.0 if (vid in seeds or vid in selected_seam) else 1.0 - d / radius
        if not w > 0.0:
            continue
        weights[vid] = w
        if corr[vid].state is CorrespondenceState.SEAM:
            if vid not in selected_seam:
                falloff.add(vid)
        elif pos[0] < 0.0:
            mirrored.add(vid)
    symmetry = {"plane_normal": NX, "plane_point": ORIGIN, "mirrored_vertex_ids": mirrored,
                "seam_vertex_ids": set(selected_seam), "falloff_seam_vertex_ids": falloff}
    return weights, symmetry


def _assert_exact_mirror(mesh, corr):
    """Every pair a bitwise mirror (E1), every seam vertex exactly on the plane, still valid."""
    for vid, c in corr.items():
        p = mesh.vertex_position(vid)
        if c.state is CorrespondenceState.PAIRED:
            assert mesh.vertex_position(c.partner) == mirror_point(p, ORIGIN, NX), vid
        elif c.state is CorrespondenceState.SEAM:
            assert p[0] == 0.0, vid
    assert symmetry_state(mesh) is SymmetryState.VALID


def _gesture_checks(mesh, op_name, weights, symmetry, pivot, steps):
    """T-6's oracle: exact after every update, one History entry, Undo/Redo and cancel exact."""
    corr = vertex_correspondence(mesh)
    start = _positions(mesh)
    history = HistoryStack()
    op = OPS[op_name](_ctx(mesh, weights, history, influence=weights, symmetry=symmetry, pivot=pivot))
    op.begin()
    for kwargs in steps:
        op.update(**kwargs)
        _assert_exact_mirror(mesh, corr)
    assert _positions(mesh) != start
    op.commit()
    end = _positions(mesh)
    assert len(history) == 1
    history.undo()
    assert _positions(mesh) == start
    history.redo()
    assert _positions(mesh) == end
    history.undo()

    op = OPS[op_name](_ctx(mesh, weights, influence=weights, symmetry=symmetry, pivot=pivot))
    op.begin()
    for kwargs in steps[:7]:
        op.update(**kwargs)
    op.cancel()
    assert _positions(mesh) == start


def _centroid(mesh, vids):
    ps = [mesh.vertex_position(v) for v in vids]
    return tuple(sum(p[i] for p in ps) / len(ps) for i in range(3))


# -- T-6 symmetric + weighted exactness ----------------------------------------------------


@pytest.mark.parametrize("op_name", sorted(OPS))
@pytest.mark.parametrize("asset", sorted(ASSETS))
def test_t6_symmetric_weighted_gesture_is_an_exact_mirror(asset, op_name):
    mesh = _asset(ASSETS[asset])
    corr = vertex_correspondence(mesh)
    seeds = _seed_ring(mesh, corr)
    radius = 0.6 * mesh_center_and_radius(mesh)[1]
    weights, symmetry = _symmetric_weights(mesh, seeds, radius)
    assert symmetry["falloff_seam_vertex_ids"], "the falloff must reach the seam"
    assert symmetry["mirrored_vertex_ids"]
    assert any(w < 1.0 for v, w in weights.items() if v in symmetry["mirrored_vertex_ids"])
    _gesture_checks(mesh, op_name, weights, symmetry, _centroid(mesh, seeds), _steps(op_name))


# -- T-8 R-6 fixtures -----------------------------------------------------------------------

#: SS0 quad s -> v' -> v -> a (X axis, `valid`, four straddling edges, self-intersecting at rest).
QUAD = [(0.5, 0.0, 0.0), (-0.1, 1.0, 0.0), (0.1, 1.0, 0.0), (-0.5, 0.0, 0.0)]


def _quad():
    mesh = mesh_from_positions_and_faces(QUAD, [(0, 1, 2, 3)])
    set_symmetry_axis(mesh, "X")
    s, vp, v, a = mesh.all_vertex_ids()
    weights = {s: 1.0, a: 1.0, v: 0.6, vp: 0.6}
    symmetry = {"plane_normal": NX, "plane_point": ORIGIN, "mirrored_vertex_ids": {a, vp},
                "seam_vertex_ids": set(), "falloff_seam_vertex_ids": set()}
    return mesh, weights, symmetry, mesh.vertex_position(s)


def _quad_with_seam():
    """The quad plus a fan over v'–v to two seam vertices c0, c1 on the plane (review R-11):
    still `valid`, still straddling, now with seam vertices inside the falloff."""
    positions = QUAD + [(0.0, 1.5, 0.0), (0.0, 2.5, 0.0)]
    faces = [(0, 1, 2, 3), (2, 1, 4), (4, 1, 5), (4, 5, 2)]
    mesh = mesh_from_positions_and_faces(positions, faces)
    set_symmetry_axis(mesh, "X")
    s, vp, v, a, c0, c1 = mesh.all_vertex_ids()
    weights = {s: 1.0, a: 1.0, v: 0.6, vp: 0.6, c0: 0.4, c1: 0.2}
    symmetry = {"plane_normal": NX, "plane_point": ORIGIN, "mirrored_vertex_ids": {a, vp},
                "seam_vertex_ids": set(), "falloff_seam_vertex_ids": {c0, c1}}
    return mesh, weights, symmetry, mesh.vertex_position(s)


@pytest.mark.parametrize("op_name", sorted(OPS))
@pytest.mark.parametrize("fixture", [_quad, _quad_with_seam], ids=["quad", "quad+seam"])
def test_t8_straddling_fixtures_stay_exact(fixture, op_name):
    mesh, weights, symmetry, pivot = fixture()
    corr = vertex_correspondence(mesh)
    assert symmetry_state(mesh) is SymmetryState.VALID
    straddling = [e for e in mesh.all_edge_ids()
                  if math.prod(mesh.vertex_position(v)[0] for v in mesh.edge_vertices(e)) < 0.0]
    assert len(straddling) == 4
    assert {c.state for v, c in corr.items() if v in symmetry["falloff_seam_vertex_ids"]} <= {
        CorrespondenceState.SEAM}
    _gesture_checks(mesh, op_name, weights, symmetry, pivot, _steps(op_name))


# -- T-7 P-a -------------------------------------------------------------------------------


def test_t7_falloff_seam_rotate_is_chunk_independent_scratch_case():
    """AD-SYM-05 §4.2: plane x = 0, pivot (0.5, 0, 0), axis y, seam vertex (0, 0, 1), w = 0.5,
    90° in total: z = 1.061 for any chunking (rotate-then-project per step would give 1.222
    for two steps and 1.387 for sixty)."""
    for n in (1, 2, 60):
        mesh = Mesh()
        seam = mesh.add_vertex((0.0, 0.0, 1.0))
        op = RotateOperation(_ctx(
            mesh, {seam}, influence={seam: 0.5}, pivot=(0.5, 0.0, 0.0),
            symmetry={"plane_normal": NX, "falloff_seam_vertex_ids": {seam}}))
        op.begin()
        for _ in range(n):
            op.update(axis=(0.0, 1.0, 0.0), angle=(math.pi / 2) / n)
        x, y, z = mesh.vertex_position(seam)
        assert x == 0.0 and y == 0.0
        assert z == pytest.approx(math.sqrt(0.5) * 1.5, abs=1e-12)  # 1.0607


@pytest.mark.parametrize("op_name", ["rotate", "scale", "scale-tilted"])
def test_t7_falloff_seam_runs_off_plane_and_is_absolute(op_name):
    """Falloff seam only, pivot off the plane: Rotate about an oblique axis and non-uniform
    Scale (also in a tilted basis) run — no seam check applies — stay on the plane, and one
    step equals sixty to rounding."""
    results = []
    for n in (1, 60):
        mesh = _asset(ASSETS["head_basemesh"])
        corr = vertex_correspondence(mesh)
        seeds = _seed_ring(mesh, corr)
        weights, symmetry = _symmetric_weights(mesh, seeds, 0.6 * mesh_center_and_radius(mesh)[1])
        pivot = _centroid(mesh, seeds)
        assert pivot[0] > 0.0 and symmetry["falloff_seam_vertex_ids"]
        if op_name == "rotate":
            steps = [{"axis": OBLIQUE, "angle": 0.9 / n}] * n
        else:
            basis = TILTED if op_name == "scale-tilted" else None
            steps = [{"factor": tuple(f ** (1.0 / n) for f in (1.6, 0.8, 1.3)), "basis": basis}] * n
        op = OPS[op_name](_ctx(mesh, weights, influence=weights, symmetry=symmetry, pivot=pivot))
        op.begin()
        start = {v: mesh.vertex_position(v) for v in symmetry["falloff_seam_vertex_ids"]}
        for kwargs in steps:
            op.update(**kwargs)
        _assert_exact_mirror(mesh, corr)
        moved = {v: mesh.vertex_position(v) for v in start}
        assert any(moved[v] != start[v] for v in start)
        results.append(moved)
    one, sixty = results
    assert all(math.dist(one[v], sixty[v]) <= 1e-12 for v in one)


def test_t7_falloff_seam_rotate_equals_the_closed_form():
    mesh = _asset(ASSETS["subd_cube"])
    corr = vertex_correspondence(mesh)
    seeds = _seed_ring(mesh, corr)
    weights, symmetry = _symmetric_weights(mesh, seeds, 0.6 * mesh_center_and_radius(mesh)[1])
    pivot = _centroid(mesh, seeds)
    start = _positions(mesh)
    op = RotateOperation(_ctx(mesh, weights, influence=weights, symmetry=symmetry, pivot=pivot))
    op.begin()
    for angle in (0.2, -0.05, 0.4):
        op.update(axis=OBLIQUE, angle=angle)
    for vid in symmetry["falloff_seam_vertex_ids"]:
        r = rotate_around_axis(start[vid], pivot, OBLIQUE, weights[vid] * ((0.2 + -0.05) + 0.4))
        assert mesh.vertex_position(vid) == (0.0, r[1], r[2])


def _selected_seam_case(pivot_on_plane):
    mesh = _asset(ASSETS["subd_cube"])
    corr = vertex_correspondence(mesh)
    seeds = _seed_ring(mesh, corr)
    seam_seed = min((v for v, c in corr.items() if c.state is CorrespondenceState.SEAM),
                    key=lambda v: min(math.dist(mesh.vertex_position(v), mesh.vertex_position(s))
                                      for s in seeds))
    weights, symmetry = _symmetric_weights(
        mesh, seeds, 1.2 * mesh_center_and_radius(mesh)[1], selected_seam={seam_seed})
    assert symmetry["seam_vertex_ids"] == {seam_seed} and symmetry["falloff_seam_vertex_ids"]
    pivot = _centroid(mesh, seeds)
    if pivot_on_plane:
        pivot = (0.0, pivot[1], pivot[2])
    return mesh, weights, symmetry, pivot


def test_t7_selected_seam_vertex_keeps_the_pivot_refusal():
    mesh, weights, symmetry, pivot = _selected_seam_case(pivot_on_plane=False)
    start = _positions(mesh)
    for cls in (RotateOperation, ScaleOperation):
        op = cls(_ctx(mesh, weights, influence=weights, symmetry=symmetry, pivot=pivot))
        with pytest.raises(SeamConstraintError, match="^Pivot liegt nicht auf der Symmetrieebene$"):
            op.begin()
        assert not op.is_active
    assert _positions(mesh) == start


@pytest.mark.parametrize("cls,kwargs,text", [
    (RotateOperation, {"axis": OBLIQUE, "angle": 0.2},
     "^Rotation um diese Achse würde den Seam-Vertex von der Ebene lösen "
     r"\(nur Achse parallel zur Ebenennormale\)$"),
    (ScaleOperation, {"factor": (1.2, 1.0, 1.0), "basis": TILTED},
     "^Skalierung würde den Seam-Vertex von der Ebene lösen "
     r"\(nur uniform oder an der Ebenennormale ausgerichtet\)$"),
])
def test_t7_selected_seam_vertex_keeps_the_step_refusal(cls, kwargs, text):
    mesh, weights, symmetry, pivot = _selected_seam_case(pivot_on_plane=True)
    start = _positions(mesh)
    op = cls(_ctx(mesh, weights, influence=weights, symmetry=symmetry, pivot=pivot))
    op.begin()
    with pytest.raises(SeamConstraintError, match=text):
        op.update(**kwargs)
    assert _positions(mesh) == start
    op.cancel()


@pytest.mark.parametrize("op_name,steps", [
    ("rotate", [{"axis": (2.0, 0.0, 0.0), "angle": 0.3}, {"axis": (2.0, 0.0, 0.0), "angle": -0.1}]),
    ("scale", [{"factor": 1.3}, {"factor": (1.1, 0.9, 0.95)}]),  # second: aligned with the normal
])
def test_t7_selected_and_falloff_seam_together_stay_exact(op_name, steps):
    mesh, weights, symmetry, pivot = _selected_seam_case(pivot_on_plane=True)
    _gesture_checks(mesh, op_name, weights, symmetry, pivot, steps)


# -- T-2 all weights 1.0 == no weights ------------------------------------------------------


def _t2_contexts(variant):
    """(mesh factory, vertex set, params) for the T-2 variants."""
    if variant == "plain":
        def make():
            return _asset(ASSETS["head_basemesh"])
        mesh = make()
        mesh.symmetry_definition = None
        vids = set(mesh.all_vertex_ids()[90:130])
        return (lambda: _no_symmetry(make())), vids, {"pivot": _centroid(mesh, vids)}
    mesh = _asset(ASSETS["subd_cube"])
    corr = vertex_correspondence(mesh)
    selected = _seed_ring(mesh, corr)
    if variant == "symmetric+seam":
        selected.add(next(v for v, c in corr.items() if c.state is CorrespondenceState.SEAM))
    affected, symmetry = resolve_symmetry(mesh, selected)
    pivot = _centroid(mesh, selected)
    if variant == "symmetric+seam":
        pivot = (0.0, pivot[1], pivot[2])
        assert symmetry["seam_vertex_ids"]
    return (lambda: _asset(ASSETS["subd_cube"])), affected, {"pivot": pivot, "symmetry": symmetry}


def _no_symmetry(mesh):
    mesh.symmetry_definition = None
    return mesh


_T2_STEPS = {
    "move": _steps("move", 20),
    "rotate": _steps("rotate", 20, axis_change=True),
    "scale": _steps("scale", 20),
    "scale-tilted": _steps("scale-tilted", 20),
}
#: With a selected seam vertex only plane-keeping steps run (axis ∥ normal, its length and
#: sign changing; uniform or normal-aligned factors).
_T2_SEAM_STEPS = {
    "move": _steps("move", 20),
    "rotate": [{"axis": (1.0 + i % 3, 0.0, 0.0) if i % 2 else (-1.0, 0.0, 0.0), "angle": 0.05 * (i - 7)}
               for i in range(20)],
    "scale": [{"factor": (1.0 + 0.01 * (i - 9), 1.02, 0.99) if i % 2 else 1.01} for i in range(20)],
    "scale-tilted": [{"factor": 1.0 + 0.01 * (i - 9), "basis": TILTED} for i in range(20)],
}


@pytest.mark.parametrize("op_name", sorted(OPS))
@pytest.mark.parametrize("variant", ["plain", "symmetric", "symmetric+seam"])
def test_t2_all_weights_one_equal_no_weights_bitwise(variant, op_name):
    make, vids, params = _t2_contexts(variant)
    steps = (_T2_SEAM_STEPS if variant == "symmetric+seam" else _T2_STEPS)[op_name]
    meshes, commands = [], []
    for weighted in (False, True):
        mesh = make()
        extra = {"influence": {v: 1.0 for v in vids}} if weighted else {}
        op = OPS[op_name](_ctx(mesh, vids, **params, **extra))
        op.begin()
        trail = []
        for kwargs in steps:
            op.update(**kwargs)
            trail.append(_positions(mesh))
        meshes.append(trail)
        commands.append(op.commit())
    assert meshes[0] == meshes[1]
    assert commands[0].start_positions == commands[1].start_positions
    assert commands[0].end_positions == commands[1].end_positions
    assert commands[0].description == commands[1].description


# -- T-5 refusals before anything moves ----------------------------------------------------


def _small():
    mesh = Mesh()
    ids = [mesh.add_vertex(p) for p in [(1.0, 0.0, 0.0), (2.0, 1.0, 0.0), (0.0, 1.0, 0.5),
                                         (-1.0, 0.0, 0.0), (-2.0, 1.0, 0.0)]]
    return mesh, ids


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.5, math.nan, math.inf])
@pytest.mark.parametrize("cls", [MoveOperation, RotateOperation, ScaleOperation])
def test_t5_weights_outside_unit_interval_refused(cls, bad):
    mesh, ids = _small()
    op = cls(_ctx(mesh, ids, influence={**{v: 0.5 for v in ids}, ids[0]: bad}, pivot=ORIGIN))
    with pytest.raises(ValueError, match="weight"):
        op.begin()
    assert not op.is_active


@pytest.mark.parametrize("cls", [MoveOperation, RotateOperation, ScaleOperation])
def test_t5_keys_must_be_the_vertex_set(cls):
    mesh, ids = _small()
    for influence in ({v: 0.5 for v in ids[:-1]}, {**{v: 0.5 for v in ids}, 10**6: 0.5}):
        op = cls(_ctx(mesh, ids, influence=influence, pivot=ORIGIN))
        with pytest.raises(ValueError, match="influenced vertex set"):
            op.begin()


@pytest.mark.parametrize("cls", [RotateOperation, ScaleOperation])
def test_t5_weighted_rotate_scale_need_a_pivot(cls):
    mesh, ids = _small()
    with pytest.raises(ValueError, match="pivot"):
        cls(_ctx(mesh, ids, influence={v: 0.5 for v in ids})).begin()
    cls(_ctx(mesh, ids)).begin()  # unweighted: the centroid default as before


def test_t5_weighted_move_needs_no_pivot():
    mesh, ids = _small()
    op = MoveOperation(_ctx(mesh, ids, influence={v: 0.5 for v in ids}))
    op.begin()
    op.update(delta=(0.0, 1.0, 0.0))
    assert mesh.vertex_position(ids[0]) == (1.0, 0.5, 0.0)


def test_t5_an_op_without_the_weighted_hook_refuses_influence():
    class Plain(VertexTransformOperation):
        def _transform_position(self, pos, **_):
            return pos

    mesh, ids = _small()
    with pytest.raises(ValueError, match="does not support params\\['influence'\\]"):
        Plain(_ctx(mesh, ids, influence={v: 1.0 for v in ids})).begin()


@pytest.mark.parametrize("cls", [MoveOperation, RotateOperation, ScaleOperation])
def test_t5_selected_seam_vertex_needs_weight_one(cls):
    mesh, ids = _small()
    seam = mesh.add_vertex((0.0, 2.0, 0.0))
    vids = ids + [seam]
    op = cls(_ctx(mesh, vids, influence={**{v: 0.5 for v in ids}, seam: 0.9}, pivot=ORIGIN,
                  symmetry={"plane_normal": NX, "seam_vertex_ids": {seam}}))
    with pytest.raises(ValueError, match="weight 1.0"):
        op.begin()


@pytest.mark.parametrize("cls", [MoveOperation, RotateOperation, ScaleOperation])
def test_t5_falloff_seam_category_rules(cls):
    mesh, ids = _small()
    seam = mesh.add_vertex((0.0, 2.0, 0.0))
    vids = ids + [seam]
    weights = {v: 0.5 for v in vids}
    with pytest.raises(ValueError, match="needs params\\['influence'\\]"):
        cls(_ctx(mesh, vids, pivot=ORIGIN,
                 symmetry={"plane_normal": NX, "falloff_seam_vertex_ids": {seam}})).begin()
    for other in ("seam_vertex_ids", "mirrored_vertex_ids"):
        sym = {"plane_normal": NX, "falloff_seam_vertex_ids": {seam}, other: {seam}}
        with pytest.raises(ValueError, match="disjoint"):
            cls(_ctx(mesh, vids, influence={**weights, seam: 1.0}, pivot=ORIGIN, symmetry=sym)).begin()


def test_t5_weighted_scale_basis_change_and_non_finite_factor_refused():
    mesh, ids = _small()
    reference, _ = _small()
    weights = {v: 0.5 for v in ids}
    op = ScaleOperation(_ctx(mesh, ids, influence=weights, pivot=ORIGIN))
    op.begin()
    op.update(factor=(1.2, 1.0, 1.1), basis=TILTED)
    before = _positions(mesh)
    with pytest.raises(ValueError, match="basis"):
        op.update(factor=1.5)
    with pytest.raises(ValueError, match="finite"):
        op.update(factor=(math.nan, 1.0, 1.0), basis=TILTED)
    assert _positions(mesh) == before
    op.update(factor=0.9, basis=TILTED)
    ref = ScaleOperation(_ctx(reference, ids, influence=weights, pivot=ORIGIN))
    ref.begin()
    ref.update(factor=(1.2, 1.0, 1.1), basis=TILTED)
    ref.update(factor=0.9, basis=TILTED)
    assert _positions(mesh) == _positions(reference)


def test_t5_unweighted_scale_still_accepts_a_new_basis_per_update():
    mesh, ids = _small()
    op = ScaleOperation(_ctx(mesh, ids, pivot=ORIGIN))
    op.begin()
    op.update(factor=(1.2, 1.0, 1.0), basis=TILTED)
    op.update(factor=(1.2, 1.0, 1.0))  # FINDINGS L5 untouched without weights


def _falloff_rotate(mesh, ids):
    seam = mesh.add_vertex((0.0, 2.0, 0.0))
    vids = ids + [seam]
    weights = {**{v: 0.5 for v in ids}, seam: 0.5}
    return RotateOperation(_ctx(mesh, vids, influence=weights, pivot=(1.0, 0.0, 0.0),
                                symmetry={"plane_normal": NX, "falloff_seam_vertex_ids": {seam}}))


@pytest.mark.parametrize("bad,text", [
    ({"axis": (1.0, 0.0, 0.0), "angle": 0.1}, "same axis"),
    ({"axis": OBLIQUE, "angle": math.nan}, "finite"),
    ({"axis": OBLIQUE, "angle": math.inf}, "finite"),
    ({"axis": (0.0, 0.0, 0.0), "angle": 0.1}, None),
])
def test_t5_falloff_seam_rotate_refusals_keep_positions_and_total(bad, text):
    mesh, ids = _small()
    reference, ref_ids = _small()
    op = _falloff_rotate(mesh, ids)
    op.begin()
    if text is None:
        # A zero axis as the first step: refused before the axis is fixed or Θ accumulated.
        with pytest.raises(ValueError, match="Nullvektor"):
            op.update(**bad)
        text = "same axis"  # later it is a different axis
    op.update(axis=OBLIQUE, angle=0.2)
    before = _positions(mesh)
    with pytest.raises(ValueError, match=text):
        op.update(**bad)
    assert _positions(mesh) == before
    op.update(axis=OBLIQUE, angle=0.3)
    ref = _falloff_rotate(reference, ref_ids)
    ref.begin()
    ref.update(axis=OBLIQUE, angle=0.2)
    ref.update(axis=OBLIQUE, angle=0.3)
    assert list(_positions(mesh).values()) == list(_positions(reference).values())


def test_t5_weighted_rotate_without_falloff_seam_accepts_a_new_axis():
    """RQ-1 / review R-1: what non-symmetric Soft accepts today stays accepted."""
    mesh, ids = _small()
    op = RotateOperation(_ctx(mesh, ids, influence={v: 0.5 for v in ids}, pivot=ORIGIN))
    op.begin()
    op.update(axis=OBLIQUE, angle=0.2)
    op.update(axis=(1.0, 0.0, 0.0), angle=0.3)


# -- F3 tripwire (5), restated: what the Core reads from params ------------------------------


class _RecordingParams(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.read: set[str] = set()

    def get(self, key, default=None):
        self.read.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self.read.add(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        self.read.add(key)
        return super().__contains__(key)


@pytest.mark.parametrize("cls", [MoveOperation, RotateOperation, ScaleOperation])
def test_core_begin_reads_influence_pivot_and_symmetry_only(cls):
    """AD-SYM-05 §5.3 (5): the Core `_on_begin` reads `target`, `selection.vertices` and from
    `params` only `pivot`, `symmetry` and (new in SS1) `influence`, which it validates."""
    mesh, ids = _small()
    params = _RecordingParams(influence={v: 0.5 for v in ids}, pivot=ORIGIN, other="ignored")
    cls(OperationContext(target=mesh, selection=_View(set(ids)), history=HistoryStack(),
                         params=params)).begin()
    assert params.read == {"influence", "pivot", "symmetry"}
