"""Symmetric Soft Selection in the app (AD-SYM-04 slice SS2).

- Field (D-1, R6-A): one distance per mirror pair (the minimum over seeds ∪ mirrored seeds and
  over both members), one weight per pair; on the exactly symmetric assets the pair minimum is a
  no-op and the seeds' side equals plain Soft bit for bit; on `partial` meshes it is what keeps
  the pairs equal; the Euclidean bounding-box prefilter is pair-consistent.
- Categories (O-1 = K-side, `PROVISIONAL`) and the refusals (D-2; seeds on both sides / only on
  the seam, fail-closed until Manu answers).
- Gestures through `Application` (W/E/R) on `subd_cube` X/Z and `head_basemesh` X: every pair a
  bitwise mirror, seam exactly on the plane, `symmetry_state` unchanged, one Undo step,
  Undo/Redo/Cancel exact; P-a (falloff seam vertices slide, a selected seam vertex keeps today's
  refusals, texts and pivot, D-3); R6-1 on the straddling fixtures of `test_weighted_transforms`;
  refusals visible before anything moves; bands stay hidden under symmetry (D-5 is SS3).
"""

from __future__ import annotations

import math
import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import Mesh  # noqa: E402
from core.operations.transform import mirror_point  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj, mesh_from_positions_and_faces  # noqa: E402
from mirai.soft_selection import (  # noqa: E402
    EMPTY_BANDS,
    METRICS,
    SoftSymmetryRefusal,
    compute_influence,
    symmetric_influence,
)
from mirai.soft_selection.influence import curve_shape  # noqa: E402
from mirai.soft_selection.symmetric import (  # noqa: E402
    BOTH_SIDES_TEXT,
    NO_PARTNER_TEXT,
    SEAM_ONLY_TEXT,
)
from mirai.symmetry import CorrespondenceState, SymmetryState, symmetry_state, vertex_correspondence  # noqa: E402
from mirai.symmetry_axis import AXIS_INDEX, AXIS_NORMALS, ORIGIN, set_symmetry_axis  # noqa: E402

WIDTH, HEIGHT = 800, 600
W, E, R = Input("key", "w"), Input("key", "e"), Input("key", "r")
O = Input("key", "o")
X_KEY = Input("key", "x")
ESC = Input("key", "ESCAPE")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
KEYS = {"move": W, "rotate": E, "scale": R}
LABELS = {"move": "Move", "rotate": "Rotate", "scale": "Scale"}
METRIC_NAMES = sorted(METRICS)
#: (asset, axis) cases whose state is `valid` (AD-SYM-04 SS0 §1).
VALID_CASES = [("subd_cube", "X"), ("subd_cube", "Z"), ("head_basemesh", "X")]


# -- helpers ---------------------------------------------------------------------------------


_STATES: dict[str, dict] = {}


def _mesh(asset: str, axis: str) -> Mesh:
    if asset not in _STATES:
        _STATES[asset] = build_core_scene_from_obj(asset_path(asset)).mesh.export_state()
    mesh = Mesh.from_state(_STATES[asset])
    set_symmetry_axis(mesh, axis)
    return mesh


def _side(mesh, vid, axis):
    x = mesh.vertex_position(vid)[AXIS_INDEX[axis]]
    return (x > 0.0) - (x < 0.0)


def _seeds(mesh, axis, which="ring", sign=1):
    """Paired seeds on one side: the vertex nearest the plane (+ its same-side paired one-ring
    for `ring`), or the farthest one (`far`)."""
    i = AXIS_INDEX[axis]
    corr = vertex_correspondence(mesh)
    side = sorted(
        (abs(mesh.vertex_position(v)[i]), int(v), v) for v, c in corr.items()
        if c.state is CorrespondenceState.PAIRED and _side(mesh, v, axis) == sign
    )
    first = side[-1][2] if which == "far" else side[0][2]
    seeds = {first}
    if which == "ring":
        for eid in mesh.vertex_edges(first):
            for w in mesh.edge_vertices(eid):
                if corr[w].state is CorrespondenceState.PAIRED and _side(mesh, w, axis) == sign:
                    seeds.add(w)
    return seeds


def _positions(mesh):
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def _assert_exact_mirror(mesh, corr, axis):
    normal, i = AXIS_NORMALS[axis], AXIS_INDEX[axis]
    for vid, c in corr.items():
        p = mesh.vertex_position(vid)
        if c.state is CorrespondenceState.PAIRED:
            assert mesh.vertex_position(c.partner) == mirror_point(p, ORIGIN, normal), vid
        elif c.state is CorrespondenceState.SEAM:
            assert p[i] == 0.0, vid


def _assert_pairs_equal(weights, corr):
    for vid, w in weights.items():
        c = corr.get(vid)
        if c is not None and c.state is CorrespondenceState.PAIRED:
            assert weights.get(c.partner) == w, vid


# == Field (D-1, R6-A) ==========================================================================


@pytest.mark.parametrize("metric", METRIC_NAMES)
@pytest.mark.parametrize("which", ["ring", "far"])
@pytest.mark.parametrize("asset,axis", VALID_CASES)
def test_d1_one_weight_per_pair_and_the_seeds_side_is_plain_soft(asset, axis, which, metric):
    mesh = _mesh(asset, axis)
    corr = vertex_correspondence(mesh)
    seeds = _seeds(mesh, axis, which)
    bounding = mesh_center_and_radius(mesh)[1]
    reached_seam = False
    for fraction in (0.15, 0.5, 1.0, 2.0):
        radius = fraction * bounding
        field = symmetric_influence(mesh, seeds, radius, metric=metric)
        _assert_pairs_equal(field.weights, corr)
        assert all(0.0 < w <= 1.0 for w in field.weights.values())
        plain = compute_influence(mesh, seeds, radius, metric=metric)
        # Observation, not a promise (R6-A): no straddling edge on these assets, so the seeds'
        # side carries exactly plain Soft and the other side its mirror.
        for vid, w in field.weights.items():
            if _side(mesh, vid, axis) == 1 and corr[vid].state is not CorrespondenceState.SEAM:
                assert plain[vid] == w, vid
        for vid, w in plain.items():
            if _side(mesh, vid, axis) == 1:
                assert field.weights.get(vid) == w, vid
        reached_seam = reached_seam or bool(field.falloff_seam_vertex_ids)
    assert reached_seam


@pytest.mark.parametrize("metric", METRIC_NAMES)
@pytest.mark.parametrize("asset,axis", VALID_CASES)
def test_d1_the_union_field_is_already_mirrored_so_the_pair_minimum_is_a_no_op(asset, axis, metric):
    """Raw union distances (also through the Euclidean bounding-box prefilter): every pair equal
    bit for bit; the prefilter's box over seeds ∪ partners is symmetric (fl(-a - r) = -fl(a + r))."""
    mesh = _mesh(asset, axis)
    corr = vertex_correspondence(mesh)
    seeds = _seeds(mesh, axis, "ring")
    union = set(seeds) | {corr[s].partner for s in seeds}
    radius = 0.6 * mesh_center_and_radius(mesh)[1]
    distances = METRICS[metric](mesh, union, radius)
    for vid, d in distances.items():
        c = corr[vid]
        if c.state is CorrespondenceState.PAIRED:
            assert distances.get(c.partner) == d, vid


def test_d1_partial_mesh_pairs_stay_equal_where_the_union_field_does_not():
    """SS0: on `man_with_shoes` X (partial) the geodesic union field differs within pairs; the
    pair minimum levels it, and every unpaired vertex keeps its own union value (D-2)."""
    mesh = _mesh("man_with_shoes_basemesh", "X")
    assert symmetry_state(mesh) is SymmetryState.PARTIAL
    corr = vertex_correspondence(mesh)
    seeds = _seeds(mesh, "X", "ring")
    radius = 0.5 * mesh_center_and_radius(mesh)[1]
    union = set(seeds) | {corr[s].partner for s in seeds}
    distances = METRICS["geodesic"](mesh, union, radius)
    differing = [v for v, d in distances.items() if corr[v].state is CorrespondenceState.PAIRED
                 and distances.get(corr[v].partner, math.inf) != d]
    assert differing
    field = symmetric_influence(mesh, seeds, radius, metric="geodesic")
    _assert_pairs_equal(field.weights, corr)
    shape = curve_shape("smooth")
    unpaired = [v for v in field.weights if corr[v].state is CorrespondenceState.UNPAIRED]
    assert unpaired
    for vid in unpaired:
        assert field.weights[vid] == shape(1.0 - distances[vid] / radius)
        expected_mirrored = _side(mesh, vid, "X") == -1
        assert (vid in field.mirrored_vertex_ids) is expected_mirrored


def test_d1_a_seam_vertex_carries_one_weight_from_the_union_never_a_sum():
    mesh = _mesh("head_basemesh", "X")
    corr = vertex_correspondence(mesh)
    seeds = _seeds(mesh, "X", "ring")
    radius = 0.3 * mesh_center_and_radius(mesh)[1]
    field = symmetric_influence(mesh, seeds, radius, metric="geodesic")
    union = set(seeds) | set(field.partners)
    distances = METRICS["geodesic"](mesh, union, radius)
    shape = curve_shape("smooth")
    assert field.falloff_seam_vertex_ids
    for vid in field.falloff_seam_vertex_ids:
        assert corr[vid].state is CorrespondenceState.SEAM
        assert field.weights[vid] == shape(1.0 - distances[vid] / radius) < 1.0


def test_r6a_straddling_quad_own_side_takes_the_union_distance():
    """AD-SYM-05 §3.1: on the SS0 quad the union lets the own-side member `v` deviate from plain
    Soft (1.366 → 1.166 through the mirrored seed); both members carry that one weight."""
    mesh = mesh_from_positions_and_faces(
        [(0.5, 0.0, 0.0), (-0.1, 1.0, 0.0), (0.1, 1.0, 0.0), (-0.5, 0.0, 0.0)], [(0, 1, 2, 3)]
    )
    set_symmetry_axis(mesh, "X")
    s, vp, v, a = mesh.all_vertex_ids()
    field = symmetric_influence(mesh, {s}, 2.0, metric="geodesic", curve="linear")
    plain = compute_influence(mesh, {s}, 2.0, metric="geodesic", curve="linear")
    d_union = math.dist((-0.5, 0.0, 0.0), (0.1, 1.0, 0.0))
    assert field.weights[v] == field.weights[vp] == pytest.approx(1.0 - d_union / 2.0, abs=1e-15)
    assert field.weights[v] > plain[v]
    assert field.weights[s] == field.weights[a] == 1.0
    assert field.mirrored_vertex_ids == {a, vp}  # K-side: v is on the seed's side, v' is not
    assert not field.seam_vertex_ids and not field.falloff_seam_vertex_ids


# == Categories (K-side) and the refusals ===================================================


@pytest.mark.parametrize("sign", [1, -1])
def test_k_side_categories_follow_the_seeds_side(sign):
    mesh = _mesh("head_basemesh", "X")
    corr = vertex_correspondence(mesh)
    seeds = _seeds(mesh, "X", "ring", sign=sign)
    field = symmetric_influence(mesh, seeds, 0.3 * mesh_center_and_radius(mesh)[1])
    assert field.partners == {corr[s].partner for s in seeds}
    assert all(field.weights[p] == 1.0 for p in field.partners)
    assert not field.seam_vertex_ids
    for vid in field.weights:
        state = corr[vid].state
        if vid in seeds:
            assert vid not in field.mirrored_vertex_ids
        elif state is CorrespondenceState.SEAM:
            assert vid in field.falloff_seam_vertex_ids
        else:
            assert (vid in field.mirrored_vertex_ids) is (_side(mesh, vid, "X") == -sign)


def test_radius_zero_is_seeds_and_partners():
    mesh = _mesh("subd_cube", "X")
    corr = vertex_correspondence(mesh)
    seeds = _seeds(mesh, "X", "ring")
    field = symmetric_influence(mesh, seeds, 0.0)
    assert field.weights == {v: 1.0 for v in seeds | {corr[s].partner for s in seeds}}


def _seam_vertices(mesh):
    return sorted(v for v, c in vertex_correspondence(mesh).items()
                  if c.state is CorrespondenceState.SEAM)


def test_selected_seam_vertex_is_a_seed_with_todays_category():
    mesh = _mesh("head_basemesh", "X")
    seeds = _seeds(mesh, "X", "ring")
    seam = _seam_vertices(mesh)[0]
    field = symmetric_influence(mesh, seeds | {seam}, 0.3 * mesh_center_and_radius(mesh)[1])
    assert field.seam_vertex_ids == {seam} and field.weights[seam] == 1.0
    assert seam not in field.falloff_seam_vertex_ids


def test_refusal_seed_without_partner():
    mesh = _mesh("man_with_shoes_basemesh", "X")
    corr = vertex_correspondence(mesh)
    unpaired = next(v for v, c in corr.items() if c.state is CorrespondenceState.UNPAIRED)
    with pytest.raises(SoftSymmetryRefusal) as info:
        symmetric_influence(mesh, {unpaired} | _seeds(mesh, "X", "ring"), 1.0)
    assert str(info.value) == NO_PARTNER_TEXT.format(count=1)


def test_refusal_ambiguous_seed_has_no_partner_either():
    # Two coincident vertices at x = +1 against one at x = -1: the -1 vertex is ambiguous.
    mesh = mesh_from_positions_and_faces(
        [(1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [(0, 3, 2), (1, 2, 3)]
    )
    set_symmetry_axis(mesh, "X")
    p0 = mesh.all_vertex_ids()[2]
    assert vertex_correspondence(mesh)[p0].state is CorrespondenceState.AMBIGUOUS
    with pytest.raises(SoftSymmetryRefusal, match="ohne Spiegelpartner"):
        symmetric_influence(mesh, {p0}, 1.0)


def test_refusal_seeds_on_both_sides_and_only_on_the_seam():
    mesh = _mesh("head_basemesh", "X")
    corr = vertex_correspondence(mesh)
    seed = next(iter(_seeds(mesh, "X", "near")))
    with pytest.raises(SoftSymmetryRefusal) as info:
        symmetric_influence(mesh, {seed, corr[seed].partner}, 1.0)
    assert str(info.value) == BOTH_SIDES_TEXT
    with pytest.raises(SoftSymmetryRefusal) as info:
        symmetric_influence(mesh, set(_seam_vertices(mesh)[:2]), 1.0)
    assert str(info.value) == SEAM_ONLY_TEXT


# == Gestures through Application ===============================================================


def _app(asset: str, axis: str, overlay=None) -> Application:
    app = Application()
    kwargs = {} if overlay is None else {"soft_overlay_type": overlay}
    app.init_scene("obj", obj_path=asset_path(asset), **kwargs)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.pointer_motion(2.0, 2.0)
    set_symmetry_axis(app.scene.mesh, axis)  # Shift+S is pinned in test_application_symmetry_cycle
    app.viewport.on_topology_changed()
    return app


def _soft_on(app, radius_steps=0):
    assert app.key_press(O) and app.soft_settings.enabled
    for _ in range(radius_steps):
        app.dispatch_command(commands.SOFT_RADIUS_UP)


def _select(app, vids):
    app.selection.set(set(vids))
    app.viewport.on_selection_changed()


def _drag(app, key, moves=((14.0, 9.0), (21.0, -6.0), (-5.0, 12.0), (30.0, 4.0))):
    assert app.key_press(key), app.status_message
    for i, (dx, dy) in enumerate(moves):
        assert app.pointer_motion(400.0 + i, 300.0, dx, dy), app.status_message
    return app.tool_manager.active_tool.operation


#: Radius steps up from the default 15 % until the falloff of the ring crosses the plane.
RADIUS_STEPS = {"subd_cube": 6, "head_basemesh": 0}


@pytest.mark.parametrize("op_name", sorted(KEYS))
@pytest.mark.parametrize("asset,axis", VALID_CASES)
def test_gesture_is_an_exact_mirror_with_one_undo_step(asset, axis, op_name):
    app = _app(asset, axis)
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    state = symmetry_state(mesh)
    assert state is SymmetryState.VALID
    seeds = _seeds(mesh, axis, "ring")
    _select(app, seeds)
    _soft_on(app, RADIUS_STEPS[asset])
    start = _positions(mesh)
    history = len(app.history)
    op = _drag(app, KEYS[op_name])
    symmetry = op.context.params["symmetry"]
    falloff_seam = set(symmetry["falloff_seam_vertex_ids"])
    assert falloff_seam and not symmetry["seam_vertex_ids"]
    assert symmetry["mirrored_vertex_ids"]
    tool = app.tool_manager.active_tool
    assert set(op.weights) == (tool.moves if op_name == "move" else tool.vertex_ids)
    _assert_exact_mirror(mesh, corr, axis)
    app.key_release(KEYS[op_name])
    assert app.status_message.startswith(f"{LABELS[op_name]} committed"), app.status_message
    end = _positions(mesh)
    assert end != start
    assert any(end[v] != start[v] for v in falloff_seam)  # P-a: falloff seam vertices slide
    _assert_exact_mirror(mesh, corr, axis)
    assert symmetry_state(mesh) is state
    assert vertex_correspondence(mesh) == corr
    assert len(app.history) == history + 1
    assert app.key_press(CTRL_Z) and _positions(mesh) == start
    assert app.key_press(CTRL_Y) and _positions(mesh) == end
    assert app.key_press(CTRL_Z) and _positions(mesh) == start
    _drag(app, KEYS[op_name])
    assert app.key_press(ESC)
    assert _positions(mesh) == start and len(app.history) == history


@pytest.mark.parametrize("op_name", sorted(KEYS))
def test_head_far_seed_keeps_off_the_seam_and_mirrors(op_name):
    app = _app("head_basemesh", "X")
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    _select(app, _seeds(mesh, "X", "far"))
    _soft_on(app)
    op = _drag(app, KEYS[op_name])
    assert not op.context.params["symmetry"]["falloff_seam_vertex_ids"]
    app.key_release(KEYS[op_name])
    _assert_exact_mirror(mesh, corr, "X")


# -- P-a / D-3: a selected seam vertex keeps today's rules ------------------------------------


def _seam_neighbour_case(app):
    """Ring seeds plus a seam vertex adjacent to the ring (head X)."""
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    seeds = _seeds(mesh, "X", "ring")
    seam = next(w for s in sorted(seeds) for e in mesh.vertex_edges(s) for w in mesh.edge_vertices(e)
                if corr[w].state is CorrespondenceState.SEAM)
    return seeds | {seam}


def test_selected_seam_vertex_rotate_refusal_text_equals_plain_symmetric_rotate():
    results = []
    for soft in (False, True):
        app = _app("head_basemesh", "X")
        mesh = app.scene.mesh
        _select(app, _seam_neighbour_case(app))
        if soft:
            _soft_on(app)
        before = (mesh.export_state(), len(app.history))
        assert app.key_press(E)
        assert app.pointer_motion(400.0, 300.0, 12.0, 3.0) is False
        results.append(app.status_message)
        assert (mesh.export_state(), len(app.history)) == before
        assert app.tool_manager.active_tool is None
    assert results[0] == results[1]
    assert "Seam-Vertex" in results[1]


def test_selected_seam_vertex_pivot_is_the_plain_symmetric_pivot_at_every_radius():
    """D-3 (review R-10): seeds ∪ partners as the fallback set, so the pivot does not move with
    the radius; it is the pivot plain symmetric R uses for the same selection."""
    pivots = []
    for radius_steps in (None, 0, 2, 5):
        app = _app("head_basemesh", "X")
        _select(app, _seam_neighbour_case(app))
        if radius_steps is not None:
            _soft_on(app, radius_steps)
        app.key_press(X_KEY)  # rotate about the mirror axis: allowed with a selected seam vertex
        op = _drag(app, E)
        pivots.append(op.pivot)
        assert op.pivot[0] == pytest.approx(0.0, abs=1e-12)
        if radius_steps is not None:
            assert op.context.params["symmetry"]["seam_vertex_ids"]
        app.key_release(E)
        _assert_exact_mirror(app.scene.mesh, vertex_correspondence(app.scene.mesh), "X")
    assert all(p == pytest.approx(pivots[0], abs=1e-12) for p in pivots)


def test_selected_seam_vertex_move_projects_and_falloff_seam_slides():
    app = _app("head_basemesh", "X")
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    seeds = _seam_neighbour_case(app)
    _select(app, seeds)
    _soft_on(app, 2)
    start = _positions(mesh)
    op = _drag(app, W)
    symmetry = op.context.params["symmetry"]
    assert symmetry["seam_vertex_ids"] and symmetry["falloff_seam_vertex_ids"]
    app.key_release(W)
    _assert_exact_mirror(mesh, corr, "X")
    moved = _positions(mesh)
    for vid in set(symmetry["seam_vertex_ids"]) | set(symmetry["falloff_seam_vertex_ids"]):
        assert moved[vid][0] == 0.0
    assert any(moved[v] != start[v] for v in symmetry["falloff_seam_vertex_ids"])


# -- R6-1: the straddling fixtures through the tools and Application ------------------------

QUAD = [(0.5, 0.0, 0.0), (-0.1, 1.0, 0.0), (0.1, 1.0, 0.0), (-0.5, 0.0, 0.0)]
FIXTURES = {
    "quad": (QUAD, [(0, 1, 2, 3)]),
    "quad+seam": (QUAD + [(0.0, 1.5, 0.0), (0.0, 2.5, 0.0)], [(0, 1, 2, 3), (2, 1, 4), (4, 1, 5), (4, 5, 2)]),
}


@pytest.mark.parametrize("op_name", sorted(KEYS))
@pytest.mark.parametrize("fixture", sorted(FIXTURES))
def test_r6_1_straddling_fixtures_stay_exact(fixture, op_name):
    positions, faces = FIXTURES[fixture]
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(mesh_from_positions_and_faces(positions, faces).export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    assert symmetry_state(mesh) is SymmetryState.VALID
    corr = vertex_correspondence(mesh)
    s = mesh.all_vertex_ids()[0]
    _select(app, {s})
    _soft_on(app, 8)
    start = _positions(mesh)
    op = _drag(app, KEYS[op_name])
    assert set(op.weights) == set(mesh.all_vertex_ids())  # the falloff covers the fixture
    if fixture == "quad+seam":
        assert len(op.context.params["symmetry"]["falloff_seam_vertex_ids"]) == 2
    app.key_release(KEYS[op_name])
    _assert_exact_mirror(mesh, corr, "X")
    assert symmetry_state(mesh) is SymmetryState.VALID
    end = _positions(mesh)
    assert end != start and len(app.history) == 1
    assert app.key_press(CTRL_Z) and _positions(mesh) == start
    assert app.key_press(CTRL_Y) and _positions(mesh) == end


# -- refusals through Application: visible, before anything moves ---------------------------


def _refusal_case(app, case):
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    if case == "no-partner":
        return {next(v for v, c in corr.items() if c.state is CorrespondenceState.UNPAIRED)}
    seed = next(iter(_seeds(mesh, "X", "near")))
    if case == "both-sides":
        return {seed, corr[seed].partner}
    return set(_seam_vertices(mesh)[:1])


@pytest.mark.parametrize("op_name", sorted(KEYS))
@pytest.mark.parametrize("case,asset,text", [
    ("no-partner", "man_with_shoes_basemesh", NO_PARTNER_TEXT.format(count=1)),
    ("both-sides", "head_basemesh", BOTH_SIDES_TEXT),
    ("seam-only", "head_basemesh", SEAM_ONLY_TEXT),
])
def test_refusals_are_visible_and_change_nothing(case, asset, text, op_name):
    app = _app(asset, "X")
    mesh = app.scene.mesh
    _select(app, _refusal_case(app, case))
    _soft_on(app)
    before = (mesh.export_state(), len(app.history))
    assert app.key_press(KEYS[op_name])
    serial = app.status_serial
    assert app.pointer_motion(400.0, 300.0, 12.0, 7.0) is False
    assert app.status_message == f"{LABELS[op_name]}: refused — {text}"
    assert app.status_serial > serial
    assert app.interaction_owner is None and app.tool_manager.active_tool is None
    assert (mesh.export_state(), len(app.history)) == before
    # Soft off: today's symmetric transform for the same selection (a lone seam vertex keeps
    # today's seam refusal for Rotate about the view axis).
    assert app.key_press(O)
    assert app.key_press(KEYS[op_name])
    app.pointer_motion(400.0, 300.0, 12.0, 7.0)
    assert app.transform_interacting or "Seam-Vertex" in app.status_message
    app.key_press(ESC)
    assert (mesh.export_state(), len(app.history)) == before


# -- bands stay hidden under symmetry (D-5 is SS3) ------------------------------------------


def test_bands_stay_hidden_during_a_symmetric_soft_gesture():
    from mirai.soft_selection import GLSoftBandOverlay

    app = _app("head_basemesh", "X", overlay=GLSoftBandOverlay)
    _select(app, _seeds(app.scene.mesh, "X", "ring"))
    _soft_on(app)
    assert app.soft_bands == EMPTY_BANDS
    _drag(app, W)
    assert app.soft_bands == EMPTY_BANDS
    app.key_release(W)
    assert app.soft_bands == EMPTY_BANDS
