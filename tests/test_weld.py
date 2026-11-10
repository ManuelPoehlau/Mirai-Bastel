"""AD-031 P4: Weld (§4, W1-W11) - the kernel `mirai.topology.weld` and the app path `Application.weld_plan` /
`weld_vertices` / `weld_default_threshold`.

Kernel: groups by distance through the spatial hash (W1, singletons and unselected points untouched), the exact group
centroid and per-layer group mean for every merge order (W7) and the canonical survivor (W8, and why it is needed),
the W2-W4 / W6 refusals predicted read-only, W5 allowed and reported (Manu 2026-11-10, "Change W5": a seam welded point
by point), UVs per face and regions kept (W9), the W11 count. App: one Undo step with
exact Undo / Redo, the threshold in world space (scaled object) and its default from the world bounding box (D10), the
command with the default, every refusal changing nothing (mode, editing view, nothing selected, a
posed rig, no pair within the distance, W2-W4 / W6, W10 hidden), the check after the change rolled back exactly, save /
load, and the artist's case: a part detached and attached back is zipped shut again. Headless (`Application` with its
trace viewport). The layer rules with morph targets and weights are `test_layer_topology_ops.py` /
`test_weights_topology_ops.py`; the window is `test_gui_menus.py`, the GL frames `test_gl_weld.py`; Weld under a symmetry
definition (AD-031 P6) is `test_symmetric_weld_bridge.py`."""

from __future__ import annotations

import itertools
import math
import random

import pytest

import tests._bootstrap  # noqa: F401
from core import FaceRegion, FaceRegions, LayerKind, Mesh, ObjectTransform, PointLayerInfo, SelectionMode
from core.mesh import combine_values
from core.operations.collapse import collapse_elements
from mirai import object_space
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.object_space import axis_angle_rotation
from mirai.scene_factory import create_plane
from mirai.topology import weld as weld_api
from mirai.topology.weld import differing_points, plan_weld, weld, world_threshold_default
from tests.mesh_invariants import assert_layer_invariants, assert_mesh_invariants, assert_uv_invariants
from tests.test_skinning import _random_pose, _rig

V = SelectionMode.VERTEX
WIDTH, HEIGHT = 800, 600
T = 0.001
CTRL_Z, CTRL_Y = Input("key", "z", frozenset({"ctrl"})), Input("key", "y", frozenset({"ctrl"}))


def _soup(faces, jitter: float = 0.0002, seed: int = 0) -> Mesh:
    """Every face with its own points (positions jittered by up to `jitter` per axis, so welded groups stay cliques
    well inside `T`), UVs per corner, faces in the given order."""
    rng = random.Random(seed)
    mesh = Mesh()
    for i, corners in enumerate(faces):
        ids = [mesh.add_vertex(tuple(c + rng.uniform(-jitter, jitter) for c in p)) for p in corners]
        mesh.add_face(ids, uvs=[(0.1 * i + 0.01 * k, 0.2 + 0.03 * k) for k in range(len(ids))])
    return mesh


def _grid4() -> list:
    """Four quads of a 2x2 grid (z = 0, normal +Z): the centre is a group of 4, the edge midpoints groups of 2."""
    quads = []
    for i in range(2):
        for j in range(2):
            x, y = float(i), float(j)
            quads.append([(x, y, 0.0), (x + 1, y, 0.0), (x + 1, y + 1, 0.0), (x, y + 1, 0.0)])
    return quads


def _fan3() -> list:
    """Three triangles around the origin closing a fan: the centre is a group of 3, the spokes groups of 2."""
    spokes = [(math.cos(a), math.sin(a), 0.0) for a in (0.0, 2.0 * math.pi / 3, 4.0 * math.pi / 3)]
    return [[(0.0, 0.0, 0.0), spokes[k], spokes[(k + 1) % 3]] for k in range(3)]


def _add_layers(mesh: Mesh, seed: int = 1) -> tuple:
    rng = random.Random(seed)
    vec = mesh.add_point_layer(PointLayerInfo("Smile"))
    skin = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(vec, v, tuple(rng.uniform(-1, 1) for _ in range(3)))
        keys = rng.sample(range(5), rng.randint(1, 3))
        raw = [rng.uniform(0.1, 1.0) for _ in keys]
        total = sum(raw) / rng.uniform(0.6, 1.0)
        mesh.set_layer_value(skin, v, tuple(sorted((k, w / total) for k, w in zip(keys, raw))))
    return vec, skin


def _copy(mesh: Mesh) -> Mesh:
    out = Mesh()
    out.load_state(mesh.export_state())
    return out


def _welded(mesh: Mesh, vertices=None, distance: float = T) -> list:
    plan = plan_weld(mesh, mesh.all_vertex_ids() if vertices is None else vertices, distance)
    assert plan.refusal is None, plan.refusal
    change = mesh.begin_change()
    survivors = weld(mesh, plan)
    mesh.end_change(change)
    return survivors


# -- kernel ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("make, size", [(_fan3, 3), (_grid4, 4)], ids=["fan3", "grid4"])
def test_the_group_centroid_and_mean_do_not_depend_on_the_merge_order(make, size):
    """W7: position = Σp / n of the original positions in ascending-id order, every layer = the Core's group mean -
    for all 6 / 24 helper-edge orders of `collapse_elements`, bit for bit. W8: the survivor of those orders differs,
    so Weld builds the star from the smallest id - its survivor is that id for every selection order."""
    mesh = _soup(make())
    lids = _add_layers(mesh)
    plan = plan_weld(mesh, mesh.all_vertex_ids(), T)
    (group,) = [g for g in plan.groups if len(g) == size]
    assert list(group) == sorted(group, key=int)
    n = len(group)
    points = [mesh.vertex_position(v) for v in group]
    centroid = tuple(sum(p[k] for p in points) / n for k in range(3))
    means = {
        lid: combine_values(mesh.point_layer_info(lid).kind, [(mesh.layer_value(lid, v), 1.0 / n) for v in group], "mean")
        for lid in lids
    }
    survivors = set()
    for order in itertools.permutations(group):
        m = _copy(mesh)
        edges = [m.add_edge(order[0], v) for v in order[1:]]
        (s,) = collapse_elements(m, list(order), edges)
        survivors.add(s)
        assert tuple(m.vertex_position(s)) == centroid
        assert {lid: m.layer_value(lid, s) for lid in lids} == means
    assert len(survivors) == n  # the survivor follows the helper order (W8's reason)
    for order in itertools.permutations(group):
        m = _copy(mesh)
        others = [v for v in m.all_vertex_ids() if v not in group]
        survivors = _welded(m, list(order) + others)
        assert group[0] in survivors and not any(m.is_valid_vertex(v) for v in group[1:])
        assert tuple(m.vertex_position(group[0])) == centroid
        assert {lid: m.layer_value(lid, group[0]) for lid in lids} == means
        assert_mesh_invariants(m)
        assert_layer_invariants(m)


def test_welding_the_grid_soup_gives_the_shared_grid():
    mesh = _soup(_grid4())
    faces = sorted(mesh.all_face_ids())
    survivors = _welded(mesh)
    assert len(survivors) == 5  # centre + four edge midpoints; the four corners have no partner
    assert (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), sorted(mesh.all_face_ids())) == (9, 12, faces)
    assert_mesh_invariants(mesh)
    assert_uv_invariants(mesh)


def test_groups_come_from_the_selection_only_in_any_order():
    """W1: unselected points stay even within the distance; points without a partner are in no group; the plan is the
    same for every order of the input."""
    mesh = _soup(_grid4())
    centre = [v for v in mesh.all_vertex_ids() if max(abs(c - 1.0) for c in mesh.vertex_position(v)[:2]) < 0.01]
    corner = next(v for v in mesh.all_vertex_ids() if max(abs(c) for c in mesh.vertex_position(v)[:2]) < 0.01)
    picked = centre[:3] + [corner]
    plans = {plan_weld(mesh, order, T) for order in itertools.permutations(picked)}
    assert len(plans) == 1
    (plan,) = plans
    assert plan.groups == (tuple(sorted(centre[:3], key=int)),) and plan.points == 3


def test_the_spatial_hash_finds_pairs_across_cells_and_respects_the_distance():
    """Pairs straddling a cell border are found; a pair just beyond the distance is not."""
    mesh = Mesh()
    a = mesh.add_vertex((0.0099999, 0.0, 0.0))
    b = mesh.add_vertex((0.0100004, 0.0, 0.0))  # other cell (cell = 0.001 → index 9 and 10), 0.0005 apart
    c = mesh.add_vertex((5.0, 0.0, 0.0))
    d = mesh.add_vertex((5.0 + 0.0010001, 0.0, 0.0))
    plan = plan_weld(mesh, [a, b, c, d], T)
    assert plan.groups == ((a, b),)


@pytest.mark.parametrize("distance", [0.0, -1.0, math.nan, math.inf])
def test_a_distance_not_above_zero_is_refused(distance):
    mesh = _soup(_grid4())
    plan = plan_weld(mesh, mesh.all_vertex_ids(), distance)
    assert plan.refusal is not None and "above 0" in plan.refusal and plan.groups == ()


def _chain() -> Mesh:
    """Three triangles whose first corners lie in a row 0.0006 apart: 0-1 and 1-2 within T, 0-2 not."""
    return _soup([[(0.0006 * k, 0.0, 0.0), (0.0006 * k, -1.0 - k, 0.0), (1.0 + k, -1.0, 0.0)] for k in range(3)], 0.0)


def _short_edge() -> Mesh:
    mesh = Mesh()
    ids = [mesh.add_vertex(p) for p in [(0, 0, 0), (0.0005, 0, 0), (1, 1, 0), (0, 1, 0)]]
    mesh.add_face(ids)
    return mesh


def _close_diagonal() -> Mesh:
    mesh = Mesh()
    ids = [mesh.add_vertex(p) for p in [(0, 0, 0), (1, -1, 0), (0.0004, 0, 0), (1, 1, 0)]]
    mesh.add_face(ids)
    return mesh


def _twin_quads() -> Mesh:
    q = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    return _soup([q, q], 0.0)


def _book() -> Mesh:
    """Three quads on one spine (x = 0, y = 0..1), pages in three directions."""
    pages = [(1.0, 0.0), (-0.5, 0.8), (-0.5, -0.8)]
    return _soup([[(0, 0, 0), (dx, 0, dz), (dx, 1, dz), (0, 1, 0)] for dx, dz in pages], 0.0)


def _corner_touch() -> Mesh:
    return _soup([[(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(1, 1, 0), (2, 1, 0), (2, 2, 0), (1, 2, 0)]], 0.0)


def _flipped() -> Mesh:
    return _soup([[(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(1, 1, 0), (2, 1, 0), (2, 0, 0), (1, 0, 0)]], 0.0)


REFUSALS = [
    ("W2 chain", _chain, "further apart than the distance"),
    ("W3 edge", _short_edge, "share an edge"),
    ("W3 face", _close_diagonal, "share a face"),
    ("W4 twin faces", _twin_quads, "same points"),
    ("W4 three faces", _book, "more than two faces"),
    ("W6 normals", _flipped, "normals"),
]


@pytest.mark.parametrize("name, make, text", REFUSALS, ids=[r[0] for r in REFUSALS])
def test_the_kernel_predicts_every_refusal_read_only(name, make, text):
    mesh = make()
    state = mesh.export_state()
    plan = plan_weld(mesh, mesh.all_vertex_ids(), T)
    assert plan.refusal is not None and text in plan.refusal, plan.refusal
    assert mesh.export_state() == state
    with pytest.raises(weld_api.WeldRefused):
        weld(mesh, plan)
    assert mesh.export_state() == state


def _two_strips() -> Mesh:
    """Two 1x3 strips of quads side by side (normal +Z), unconnected: the seam at x = 1 has four points on each side."""
    mesh = Mesh()
    for x0 in (0.0, 1.0):
        ids = {(i, k): mesh.add_vertex((x0 + i, float(k), 0.0)) for i in (0, 1) for k in range(4)}
        for k in range(3):
            mesh.add_face([ids[0, k], ids[1, k], ids[1, k + 1], ids[0, k + 1]])
    return mesh


def _seam_pairs(mesh: Mesh) -> list:
    """The seam's pairs, bottom to top."""
    pairs: dict = {}
    for v in mesh.all_vertex_ids():
        p = mesh.vertex_position(v)
        if p[0] == 1.0:
            pairs.setdefault(p[1], []).append(v)
    return [pairs[y] for y in sorted(pairs)]


def test_a_single_pair_of_two_parts_welds_and_is_reported():
    """W5 (Manu 2026-11-10, "Change W5"): a pair whose parts would touch at that point only (a bowtie) is welded, not
    refused; the plan names the survivor; the result is valid topology."""
    mesh = _corner_touch()
    plan = plan_weld(mesh, mesh.all_vertex_ids(), T)
    assert plan.refusal is None and len(plan.groups) == 1 and plan.bowties == (plan.groups[0][0],)
    survivors = _welded(mesh)
    assert len(mesh.all_vertex_ids()) == 7 and len(mesh.vertex_edges(survivors[0])) == 4
    assert_mesh_invariants(mesh)


def test_a_seam_welded_point_by_point_equals_the_seam_welded_at_once():
    """Both ways (Manu 2026-11-10: "Brauchen also beide Möglichkeiten"): pair by pair the first weld leaves a bowtie,
    the next one merges the edge between them (W6 checked there) and the bowtie is gone; the end result has the same
    topology and positions as welding the whole seam in one step."""
    at_once = _two_strips()
    _welded(at_once)
    mesh = _two_strips()
    reported = []
    for pair in _seam_pairs(mesh):
        plan = plan_weld(mesh, pair, T)
        assert plan.refusal is None, plan.refusal
        reported.append(len(plan.bowties))
        change = mesh.begin_change()
        weld(mesh, plan)
        mesh.end_change(change)
        assert_mesh_invariants(mesh)
    assert reported == [1, 0, 0, 0]
    assert mesh.export_state() == at_once.export_state()


def test_a_flipped_part_welded_point_by_point_is_refused_at_the_first_merged_edge():
    """W6 needs an edge both sides use: the first pair of a flipped strip welds (a bowtie, reported), the second pair
    would merge an edge with disagreeing normals and is refused."""
    flipped = Mesh()
    for x0 in (0.0, 1.0):
        ids = {(i, k): flipped.add_vertex((x0 + i, float(k), 0.0)) for i in (0, 1) for k in range(4)}
        for k in range(3):
            quad = [ids[0, k], ids[1, k], ids[1, k + 1], ids[0, k + 1]]
            flipped.add_face(quad if x0 == 0.0 else quad[::-1])
    first, second = _seam_pairs(flipped)[:2]
    assert _welded(flipped, first)
    plan = plan_weld(flipped, second, T)
    assert plan.refusal is not None and "normals" in plan.refusal


def test_uvs_per_face_and_regions_stay():
    """W9: Weld keeps every face id, its corner UVs (a UV seam along the weld stays) and the regions."""
    mesh = _soup(_grid4())
    regions = FaceRegions((FaceRegion("Left", frozenset(sorted(mesh.all_face_ids())[:2])),))
    mesh.face_regions = regions
    uvs = {f: mesh.face_uvs(f) for f in mesh.all_face_ids()}
    _welded(mesh)
    assert {f: mesh.face_uvs(f) for f in mesh.all_face_ids()} == uvs
    assert mesh.face_regions == regions


def test_differing_points_counts_the_averaged_border_values():
    """W11: the points of groups whose layer values differ (each group of the soup has random values: all 12 of the
    5 groups); equal values in a group are not counted."""
    mesh = _soup(_grid4())
    (vec,) = _add_layers(mesh)[:1]
    plan = plan_weld(mesh, mesh.all_vertex_ids(), T)
    assert differing_points(mesh, plan.groups) == plan.points == 12
    plain = _soup(_grid4())
    lid = plain.add_point_layer(PointLayerInfo("Smile"))
    for v in plain.all_vertex_ids():
        plain.set_layer_value(lid, v, (0.0, 0.5, 0.0))
    assert differing_points(plain, plan_weld(plain, plain.all_vertex_ids(), T).groups) == 0
    assert differing_points(_soup(_grid4()), plan.groups) == 0  # no layers


def test_the_default_is_a_thousandth_of_the_diagonal():
    assert world_threshold_default(2.0) == 0.002
    assert world_threshold_default(0.0) is None and world_threshold_default(math.nan) is None


# -- app ---------------------------------------------------------------------------------------------------------------


def _app(mesh: Mesh | None = None) -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state((mesh if mesh is not None else _soup(_grid4())).export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _select_points(app: Application, vertices=None) -> None:
    app.dispatch_command(commands.SET_VERTEX_MODE)
    app.selection.clear()
    mesh = app.scene.mesh
    app.selection.vertices = set(mesh.all_vertex_ids() if vertices is None else vertices)


def _body(mesh) -> dict:
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}


def _snapshot(app: Application) -> tuple:
    selection = app.selection
    return (
        _body(app.scene.mesh), len(app.history), selection.mode, frozenset(selection.vertices),
        frozenset(selection.edges), frozenset(selection.faces), app.scene.edit_object_id,
    )


def test_weld_is_one_step_and_undo_redo_are_exact():
    app = _app()
    mesh = app.scene.mesh
    _select_points(app)
    before = _snapshot(app)
    history = len(app.history)
    assert app.weld_vertices(T), app.status_message
    assert app.status_message.startswith("Weld: 12 points into 5 (distance 0.001)")
    assert len(app.history) == history + 1
    after = _body(mesh)
    assert len(mesh.all_vertex_ids()) == 9 and app.selection.mode is V
    assert app.selection.vertices == set(mesh.all_vertex_ids())  # the points that remain stay selected
    assert_mesh_invariants(mesh)
    assert app.key_press(CTRL_Z)
    assert _snapshot(app) == before
    assert app.key_press(CTRL_Y)
    assert _body(mesh) == after


def test_the_command_welds_with_the_default_distance():
    app = _app()
    _select_points(app)
    default = app.weld_default_threshold()
    assert default == pytest.approx(0.001 * math.dist((0, 0, 0), (2, 2, 0)), rel=1e-3)
    assert app.dispatch_command(commands.WELD), app.status_message
    assert f"(distance {default:.6g})" in app.status_message
    assert len(app.scene.mesh.all_vertex_ids()) == 9


def test_the_threshold_is_in_world_space_and_the_default_from_the_world_box():
    """D10: the distance is compared in world space (object space `t / s`); the default is 0.001 × the diagonal of the
    world-space axis-aligned bounding box of the edit object."""
    # two quads side by side, the right one moved 0.0004 along x (object space): its seam points are that far apart
    mesh = _soup([[(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(1.0004, 0, 0), (2, 0, 0), (2, 1, 0), (1.0004, 1, 0)]], 0.0)
    rotation = axis_angle_rotation((0.0, 0.0, 1.0), 0.4)
    for scale, welds in ((2.0, True), (3.0, False)):  # 0.0008 world: within T; 0.0012: beyond it
        app = _app(mesh)
        obj = app.scene.edit_object
        obj.transform = ObjectTransform(translation=(1.0, 2.0, 3.0), rotation=rotation, scale=scale)
        world = [object_space.to_world(obj, obj.mesh.vertex_position(v)) for v in obj.mesh.all_vertex_ids()]
        lo = [min(p[i] for p in world) for i in range(3)]
        hi = [max(p[i] for p in world) for i in range(3)]
        assert app.weld_default_threshold() == pytest.approx(0.001 * math.dist(lo, hi), rel=1e-12)
        _select_points(app)
        assert app.weld_plan(T).points == (4 if welds else 0)
        assert app.weld_vertices(T) is welds, app.status_message
        assert len(obj.mesh.all_vertex_ids()) == (6 if welds else 8)


def test_no_pair_within_the_distance_changes_nothing():
    app = _app()
    _select_points(app)
    before = _snapshot(app)
    assert app.weld_vertices(1e-6) is False
    assert "nothing to weld" in app.status_message and _snapshot(app) == before


def _refusal(app: Application, case: str) -> None:
    mesh = app.scene.mesh
    if case == "edge mode":
        app.dispatch_command(commands.SET_EDGE_MODE)
        app.selection.edges = set(mesh.all_edge_ids())
    elif case == "object mode":
        app.dispatch_command(commands.SET_OBJECT_MODE)
    elif case == "nothing selected":
        app.selection.clear()
    elif case == "editing view":
        assert app.create_morph_target("Smile") is not None, app.status_message
        assert app.edit_morph_target(), app.status_message
        _select_points(app)
    elif case == "hidden":
        # W10: hide a corner point of the centre's quads; the centre group touches it through its faces
        corner = next(v for v in mesh.all_vertex_ids() if max(abs(c) for c in mesh.vertex_position(v)[:2]) < 0.01)
        _select_points(app, [corner])
        assert app.dispatch_command(commands.HIDE_SELECTION), app.status_message
        _select_points(app, [v for v in mesh.all_vertex_ids() if v != corner])


@pytest.mark.parametrize("case, text", [
    ("edge mode", "press 1"),
    ("object mode", "press 1"),
    ("nothing selected", "none selected"),
    ("editing view", "on the base only"),
    ("hidden", "hidden geometry in the way"),
])
def test_a_refusal_changes_nothing(case, text):
    app = _app()
    _select_points(app)
    _refusal(app, case)
    before = _snapshot(app)
    assert app.weld_vertices(T) is False
    assert text in app.status_message, app.status_message
    assert _snapshot(app) == before
    assert app.dispatch_command(commands.WELD) is False
    assert _snapshot(app) == before
    assert app.weld_plan(T).refusal is not None


@pytest.mark.parametrize("name, make, text", REFUSALS, ids=[r[0] for r in REFUSALS])
def test_the_topology_refusals_change_nothing_in_the_app(name, make, text):
    app = _app(make())
    _select_points(app)
    before = _snapshot(app)
    assert app.weld_vertices(T) is False
    assert text in app.status_message, app.status_message
    assert _snapshot(app) == before


def test_posed_rig_with_a_bound_mesh_is_refused():
    app = _app()
    rig = _rig()
    app.scene.rig = rig
    mesh = app.scene.mesh
    skin = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(skin, v, ((int(rig.bone_ids()[0]), 1.0),))
    _select_points(app)
    app._skeleton.set_pose(_random_pose(random.Random(3), rig, share=1.0))
    assert app.posed
    before = _snapshot(app)
    assert app.weld_vertices(T) is False
    assert "is posed" in app.status_message and _snapshot(app) == before
    assert app.dispatch_command(commands.WELD) is False and _snapshot(app) == before
    app._skeleton.set_pose({})
    assert app.weld_vertices(T), app.status_message


def test_a_failure_after_the_change_is_rolled_back_exactly(monkeypatch):
    """W4 / W6 are checked again on the real topology after the merge; a refusal there rolls the mesh back exactly and
    pushes nothing."""
    app = _app()
    _select_points(app)
    before = _snapshot(app)
    calls = []
    real = weld_api._result_refusal

    def after_the_change_refuses(*args, **kwargs):
        calls.append(kwargs["duplicates"])
        return real(*args, **kwargs) if kwargs["duplicates"] else "Weld: refused after the change for the test"

    monkeypatch.setattr(weld_api, "_result_refusal", after_the_change_refuses)
    assert app.weld_vertices(T) is False
    assert calls == [True, False]  # predicted, then checked on the result
    assert app.status_message == "Weld: refused after the change for the test"
    assert _snapshot(app) == before


def test_the_status_names_points_that_join_two_parts_only_there():
    app = _app(_corner_touch())
    _select_points(app)
    history = len(app.history)
    assert app.weld_vertices(T), app.status_message
    assert "1 point(s) join parts at that point only" in app.status_message
    assert len(app.history) == history + 1
    assert app.key_press(CTRL_Z) and len(app.scene.mesh.all_vertex_ids()) == 8


def test_status_names_the_averaged_layer_values():
    mesh = _soup(_grid4())
    _add_layers(mesh)
    app = _app(mesh)
    _select_points(app)
    assert app.weld_vertices(T), app.status_message
    assert "12 point(s) averaged differing target / weight values" in app.status_message


def test_save_and_load_keep_the_welded_mesh(tmp_path):
    app = _app()
    _select_points(app)
    assert app.weld_vertices(T), app.status_message
    state = app.scene.mesh.export_state()
    path = tmp_path / "welded.mirai.json"
    assert app.save_scene_file(path)
    app.load_scene("file", scene_path=path)
    assert app.scene.mesh.export_state() == state


def test_a_detached_and_attached_part_is_zipped_shut_again():
    """The artist's case (AD-031 §11): Detach a column of a plane, Attach it back (coincident points, bit-exact), Weld
    with the default distance - the plane's topology again (counts, one manifold surface), one step each."""
    plane = create_plane(2.0, 3)
    app = _app(plane)
    src = app.scene.edit_object
    mesh = src.mesh
    counts = (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids()))
    column = [f for f in mesh.all_face_ids() if min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0.3]
    assert len(column) == 3
    app.dispatch_command(commands.SET_FACE_MODE)
    app.selection.faces = set(column)
    objects = set(app.scene.objects)
    assert app.detach_faces(), app.status_message
    (part_id,) = set(app.scene.objects) - objects
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = {part_id}
    assert app.attach_objects(), app.status_message
    assert len(mesh.all_vertex_ids()) == counts[0] + 4  # the seam's four points twice
    _select_points(app)
    assert app.weld_vertices(), app.status_message
    assert "8 points into 4" in app.status_message
    assert (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())) == counts
    assert_mesh_invariants(mesh)
