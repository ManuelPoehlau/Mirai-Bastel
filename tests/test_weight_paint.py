"""AD-041 slice 1: the weight brush's arithmetic (`mirai.weight_paint`, `skin_weights.clean_weights`), headless.

Footprint (sphere, falloff, connected only, front only, on a moved cage); Add / Subtract / Replace from the press values
(formulas, opacity cap, path-independence, parent rule); Smooth on the current values; W1-W4 / Σw <= 1 / <= 4 keys after
every operation; mask; Esc exact and one Undo step; a dab reads and writes O(footprint); Clean.
"""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import BoneId, HistoryStack, LayerKind, Mesh, PointLayerInfo, Rig
from core.operations import MeshDeltaCommand, record_mesh_change
from mirai.paint.brush import falloff
from mirai.skin_weights import CLEAN_THRESHOLD, bone_share, clean_value, clean_weights, parent_function
from mirai.surface_positions import SurfacePositions
from mirai.weight_paint import (
    OP_ADD, OP_REPLACE, OP_SMOOTH, OP_SUBTRACT, BrushWeightStroke, Footprint, VertexCloud, WeightBrushSettings,
    footprint,
)
from tests.mesh_invariants import assert_layer_invariants

HEAD, JAW, CHEEK, LIP, BROW, EAR = 0, 1, 2, 3, 4, 5


def _rig() -> Rig:
    rig = Rig()
    rig, _ = rig.with_new_bone("Head", (0, 0, 0), (0, 1, 0))
    rig, _ = rig.with_new_bone("Jaw", (0, 0, 0), (0, -1, 1), parent=BoneId(HEAD))
    rig, _ = rig.with_new_bone("Cheek", (1, 0, 0), (1, 1, 0))
    rig, _ = rig.with_new_bone("Lip", (0, -1, 1), (0, -1, 2), parent=BoneId(JAW))
    rig, _ = rig.with_new_bone("Brow", (0, 1, 1), (0, 2, 1))
    rig, _ = rig.with_new_bone("Ear", (2, 0, 0), (2, 1, 0))
    return rig


RIG = _rig()


def _grid(mesh: Mesh, n: int, origin=(0.0, 0.0, 0.0), step: float = 1.0, flip: bool = False) -> list[list]:
    """An n x n vertex grid of quads in the XY plane at `origin` (normal +z, -z when `flip`)."""
    ox, oy, oz = origin
    rows = [[mesh.add_vertex((ox + i * step, oy + j * step, oz)) for i in range(n)] for j in range(n)]
    for j in range(n - 1):
        for i in range(n - 1):
            quad = [rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]]
            mesh.add_face(quad[::-1] if flip else quad)
    return rows


def _skinned(n: int = 9, value=()) -> tuple[Mesh, object, list[list]]:
    mesh = Mesh()
    rows = _grid(mesh, n)
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    if value:
        for v in mesh.all_vertex_ids():
            mesh.set_layer_value(lid, v, value)
    return mesh, lid, rows


def _face_at(mesh: Mesh, v):
    return mesh.edge_faces(mesh.vertex_edges(v)[0])[0]


def _values(mesh: Mesh, lid) -> dict:
    return {v: mesh.layer_value(lid, v) for v in mesh.all_vertex_ids()}


def _check(mesh: Mesh) -> None:
    assert_layer_invariants(mesh)  # W1-W4 (canonical, <= 4 keys, 0 < w, Σw <= 1)
    for lid in mesh.point_layer_ids():
        for _, value in mesh.layer_items(lid):
            assert len(value) <= 4
            assert math.fsum(w for _, w in value) <= 1.0 + 1e-9


# -- footprint ------------------------------------------------------------------------------------------------------


def test_the_footprint_is_the_sphere_with_the_paint_falloff():
    mesh, _, rows = _skinned(9)
    cloud = VertexCloud(mesh)
    centre = rows[4][4]
    settings = WeightBrushSettings(radius=2.5, hardness=0.2, curve="smooth", connected=False)
    fp = footprint(cloud, mesh.vertex_position(centre), settings)
    p = np.array(mesh.vertex_position(centre))
    expected = {}
    for v in mesh.all_vertex_ids():
        d = float(np.linalg.norm(np.array(mesh.vertex_position(v)) - p))
        c = float(falloff(np.array([d / 2.5]), 0.2, "smooth")[0])
        if c > 0.0:
            expected[v] = c
    assert dict(zip(fp.vertices, fp.coverage.tolist())) == pytest.approx(expected, abs=1e-15)
    assert centre in fp.vertices and len(fp) == len(expected)
    assert footprint(cloud, (100.0, 0.0, 0.0), settings).vertices == ()


def test_connected_only_keeps_the_hit_sheet_and_leaves_the_other_lip():
    """Two sheets 0.5 apart (upper / lower lip), the sphere reaches both: connected keeps the hit face's sheet."""
    mesh = Mesh()
    upper = _grid(mesh, 5, (0.0, 0.0, 0.0))
    lower = _grid(mesh, 5, (0.0, 0.0, -0.5))
    hit_v = upper[2][2]
    point = mesh.vertex_position(hit_v)
    cloud = VertexCloud(mesh)
    both = footprint(cloud, point, WeightBrushSettings(radius=1.5, connected=False))
    lower_ids = {v for row in lower for v in row}
    assert lower_ids & set(both.vertices)
    only = footprint(cloud, point, WeightBrushSettings(radius=1.5, connected=True), hit_face=_face_at(mesh, hit_v))
    assert set(only.vertices) <= {v for row in upper for v in row}
    assert set(only.vertices) == set(both.vertices) - lower_ids
    # no hit face given: the candidate nearest to the point is the seed
    assert set(footprint(cloud, point, WeightBrushSettings(radius=1.5)).vertices) == set(only.vertices)


def test_connected_only_does_not_cross_a_gap_inside_the_sphere():
    """One strip bent back (a U): both arms inside the sphere, connected over a path that leaves it -> dropped."""
    mesh = Mesh()
    a = [mesh.add_vertex((float(i), 0.0, 0.0)) for i in range(6)]
    b = [mesh.add_vertex((float(i), 1.0, 0.0)) for i in range(6)]
    c = [mesh.add_vertex((float(i), 0.0, -0.6)) for i in range(6)]
    d = [mesh.add_vertex((float(i), 1.0, -0.6)) for i in range(6)]
    for i in range(5):
        mesh.add_face([a[i], a[i + 1], b[i + 1], b[i]])
        mesh.add_face([d[i], d[i + 1], c[i + 1], c[i]])
    mesh.add_face([a[5], c[5], d[5], b[5]])  # the bend at x = 5, outside the sphere around x = 0
    cloud = VertexCloud(mesh)
    fp = footprint(cloud, (0.0, 0.5, 0.0), WeightBrushSettings(radius=1.5), hit_face=_face_at(mesh, a[0]))
    assert not set(fp.vertices) & (set(c) | set(d))
    loose = footprint(cloud, (0.0, 0.5, 0.0), WeightBrushSettings(radius=1.5, connected=False))
    assert set(loose.vertices) & set(c)


def test_front_only_drops_vertices_facing_away():
    mesh = Mesh()
    front = _grid(mesh, 4, (0.0, 0.0, 0.0))
    back = _grid(mesh, 4, (0.0, 0.0, -0.3), flip=True)  # normal -z
    cloud = VertexCloud(mesh)
    s = WeightBrushSettings(radius=2.0, connected=False, front_only=True)
    fp = footprint(cloud, mesh.vertex_position(front[1][1]), s, toward_viewer=(0.0, 0.0, 1.0))
    assert set(fp.vertices) and set(fp.vertices) <= {v for row in front for v in row}
    off = footprint(cloud, mesh.vertex_position(front[1][1]), WeightBrushSettings(radius=2.0, connected=False))
    assert set(off.vertices) & {v for row in back for v in row}


def test_the_footprint_follows_the_shown_cage():
    """A `SurfacePositions` (the posed / morphed cage) moved by +10 in x: the footprint is taken there; refresh."""
    mesh, _, rows = _skinned(5)
    shift = [10.0]
    cage = SurfacePositions(mesh, position=lambda v: tuple(np.add(mesh.vertex_position(v), (shift[0], 0.0, 0.0))))
    cloud = VertexCloud(cage)
    v = rows[2][2]
    x, y, z = mesh.vertex_position(v)
    s = WeightBrushSettings(radius=0.5)
    assert footprint(cloud, (x + 10.0, y, z), s).vertices == (v,)
    assert footprint(cloud, (x, y, z), s).vertices == ()
    cage.P[:, 0] += 1.0  # the owner moved the surface
    cloud.refresh()
    assert footprint(cloud, (x + 11.0, y, z), s).vertices == (v,)


def test_settings_are_validated():
    with pytest.raises(ValueError):
        WeightBrushSettings(operation="blur")
    with pytest.raises(ValueError):
        WeightBrushSettings(radius=0.0)
    with pytest.raises(ValueError):
        WeightBrushSettings(flow=1.5)
    with pytest.raises(ValueError):
        WeightBrushSettings(curve="custom")


# -- Add / Subtract / Replace ---------------------------------------------------------------------------------------


def _one(value) -> tuple[Mesh, object, object]:
    mesh = Mesh()
    v = mesh.add_vertex((0.0, 0.0, 0.0))
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    if value:
        mesh.set_layer_value(lid, v, value)
    return mesh, lid, v


@pytest.mark.parametrize("operation, goal", [(OP_ADD, 1.0), (OP_SUBTRACT, 0.0), (OP_REPLACE, 0.8)])
def test_the_press_operations_follow_their_formulas(operation, goal):
    mesh, lid, v = _one(((JAW, 0.3), (CHEEK, 0.5)))
    s = WeightBrushSettings(operation=operation, flow=0.5, opacity=0.6, value=0.8)
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, s)
    old = 0.3
    C = 0.0
    for c in (1.0, 0.4, 0.7):
        stroke.dab(Footprint((v,), np.array([c])))
        C = C + (1.0 - C) * 0.5 * c
        S = 0.6 * C
        expected = {OP_ADD: old + S * (1.0 - old), OP_SUBTRACT: old * (1.0 - S),
                    OP_REPLACE: old + S * (0.8 - old)}[operation]
        assert bone_share(mesh.layer_value(lid, v), JAW) == pytest.approx(expected, abs=1e-15)
        assert expected == pytest.approx(old + S * (goal - old), abs=1e-15)
    _check(mesh)


def test_opacity_caps_what_one_stroke_lays_down():
    mesh, lid, v = _one(((JAW, 0.2),))
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, WeightBrushSettings(flow=1.0, opacity=0.5))
    for _ in range(20):
        stroke.dab(Footprint((v,), np.array([1.0])))
    assert bone_share(mesh.layer_value(lid, v), JAW) == pytest.approx(0.2 + 0.5 * 0.8, abs=1e-15)


def test_subtract_gives_the_share_to_the_parent_and_a_root_to_the_object():
    mesh, lid, v = _one(((JAW, 0.6), (CHEEK, 0.4)))
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, WeightBrushSettings(operation=OP_SUBTRACT, flow=1.0))
    stroke.dab(Footprint((v,), np.array([1.0])))
    assert mesh.layer_value(lid, v) == ((HEAD, 0.6), (CHEEK, 0.4))  # jaw's parent is head
    mesh, lid, v = _one(((HEAD, 0.6), (CHEEK, 0.4)))
    stroke = BrushWeightStroke(mesh, lid, HEAD, RIG, WeightBrushSettings(operation=OP_SUBTRACT, flow=1.0))
    stroke.dab(Footprint((v,), np.array([1.0])))
    assert mesh.layer_value(lid, v) == ((CHEEK, 0.4),)  # a root: to the object


def test_add_raises_and_scales_the_others():
    mesh, lid, v = _one(((JAW, 0.2), (CHEEK, 0.3)))
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, WeightBrushSettings(flow=1.0, opacity=0.5))
    stroke.dab(Footprint((v,), np.array([1.0])))
    # x = 0.2 + 0.5 * 0.8 = 0.6; cheek scaled by (1 - 0.6) / (1 - 0.2)
    value = mesh.layer_value(lid, v)
    assert bone_share(value, JAW) == pytest.approx(0.6, abs=1e-15)
    assert bone_share(value, CHEEK) == pytest.approx(0.15, abs=1e-15)


@pytest.mark.parametrize("operation", [OP_ADD, OP_SUBTRACT, OP_REPLACE])
def test_the_press_operations_are_path_independent(operation):
    """The same dabs in another order give the same weights: each value is a function of the press values and C."""
    rng = random.Random(41)
    base = ((JAW, 0.3), (CHEEK, 0.2), (LIP, 0.1))
    results = []
    for order in range(3):
        mesh, lid, rows = _skinned(9, base)
        cloud = VertexCloud(mesh)
        s = WeightBrushSettings(operation=operation, radius=2.2, flow=0.4, opacity=0.9, value=0.7)
        centres = [mesh.vertex_position(rows[j][i]) for j, i in ((2, 2), (3, 4), (4, 4), (5, 3), (6, 6))]
        if order:
            rng.shuffle(centres)
        stroke = BrushWeightStroke(mesh, lid, JAW, RIG, s)
        for p in centres:
            stroke.dab(footprint(cloud, p, s))
            _check(mesh)
        results.append(_values(mesh, lid))
    for other in results[1:]:
        for v, value in results[0].items():
            got = other[v]
            assert [k for k, _ in got] == [k for k, _ in value]
            assert [w for _, w in got] == pytest.approx([w for _, w in value], abs=1e-12)


def test_every_operation_keeps_w1_to_w4_on_random_weights():
    rng = random.Random(7)
    mesh, lid, rows = _skinned(10)
    for v in mesh.all_vertex_ids():
        bones = rng.sample(range(6), rng.randint(0, 4))
        ws = [rng.random() for _ in bones]
        total = sum(ws) + rng.random() * 0.5
        mesh.set_layer_value(lid, v, tuple((b, w / total) for b, w in zip(bones, ws)) if bones else ())
    cloud = VertexCloud(mesh)
    for operation in (OP_ADD, OP_SUBTRACT, OP_REPLACE, OP_SMOOTH):
        for bone in (JAW, LIP, BROW):
            s = WeightBrushSettings(operation=operation, radius=2.5, flow=rng.random(), opacity=rng.random(),
                                    hardness=rng.random() * 0.9, value=rng.random())
            stroke = BrushWeightStroke(mesh, lid, bone, RIG, s)
            for _ in range(6):
                p = mesh.vertex_position(rows[rng.randrange(10)][rng.randrange(10)])
                stroke.dab(footprint(cloud, p, s))
                _check(mesh)


# -- mask, Esc, Undo, cost ------------------------------------------------------------------------------------------


def test_the_mask_protects_and_a_partial_mask_scales_the_change():
    mesh = Mesh()
    vs = [mesh.add_vertex((float(i), 0.0, 0.0)) for i in range(3)]
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in vs:
        mesh.set_layer_value(lid, v, ((JAW, 0.2),))
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, WeightBrushSettings(flow=1.0))
    stroke.dab(Footprint(tuple(vs), np.ones(3)), mask={vs[1]: 1.0, vs[2]: 0.5})
    assert bone_share(mesh.layer_value(lid, vs[0]), JAW) == pytest.approx(1.0)
    assert mesh.layer_value(lid, vs[1]) == ((JAW, 0.2),)
    assert bone_share(mesh.layer_value(lid, vs[2]), JAW) == pytest.approx(0.2 + 0.5 * 0.8, abs=1e-15)


def test_esc_restores_exactly_and_release_is_one_undo_step():
    mesh, lid, rows = _skinned(9, ((JAW, 0.3), (CHEEK, 0.4)))
    before = _values(mesh, lid)
    cloud = VertexCloud(mesh)
    for operation in (OP_ADD, OP_SMOOTH):
        s = WeightBrushSettings(operation=operation, radius=2.0, flow=0.7)
        change = mesh.begin_change()
        stroke = BrushWeightStroke(mesh, lid, JAW, RIG, s)
        for j in range(2, 7):
            stroke.dab(footprint(cloud, mesh.vertex_position(rows[j][j]), s))
        assert _values(mesh, lid) != before or operation == OP_SMOOTH
        mesh.rollback_change(change)  # Esc
        assert _values(mesh, lid) == before
    history = HistoryStack()
    s = WeightBrushSettings(radius=2.0, flow=0.7)
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, s)

    def paint():
        for j in range(2, 7):
            stroke.dab(footprint(cloud, mesh.vertex_position(rows[j][j]), s))

    delta, _ = record_mesh_change(mesh, paint)
    history.push(MeshDeltaCommand(mesh, delta, "Weight brush"))
    after = _values(mesh, lid)
    assert after != before
    history.undo()
    assert _values(mesh, lid) == before
    history.redo()
    assert _values(mesh, lid) == after


class _Counting:
    """Counts the layer reads and writes of a mesh (the cost of a dab)."""

    def __init__(self, mesh: Mesh) -> None:
        self.reads = self.writes = 0
        read, write = mesh.layer_value, mesh.set_layer_value

        def layer_value(lid, v):
            self.reads += 1
            return read(lid, v)

        def set_layer_value(lid, v, value):
            self.writes += 1
            return write(lid, v, value)

        mesh.layer_value = layer_value
        mesh.set_layer_value = set_layer_value


@pytest.mark.parametrize("operation", [OP_ADD, OP_REPLACE, OP_SMOOTH])
def test_a_dab_reads_and_writes_only_its_footprint(operation):
    """F-3: after a long stroke has touched a large area, one more dab still costs O(footprint)."""
    mesh, lid, rows = _skinned(40, ((JAW, 0.2), (HEAD, 0.3)))
    cloud = VertexCloud(mesh)
    s = WeightBrushSettings(operation=operation, radius=1.6, flow=0.3, value=0.9)
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, s)
    counter = _Counting(mesh)
    for j in range(2, 38, 2):
        for i in range(2, 38, 4):
            stroke.dab(footprint(cloud, mesh.vertex_position(rows[j][i]), s))
    assert len(stroke.press) > 600  # the stroke touched much of the mesh
    fp = footprint(cloud, mesh.vertex_position(rows[20][20]), s)
    counter.reads = counter.writes = 0
    stroke.dab(fp)
    ring = 4 if operation == OP_SMOOTH else 0  # Smooth also reads the footprint's neighbours (valence 4)
    assert counter.reads <= (2 + ring) * len(fp)
    assert counter.writes <= len(fp)


# -- Smooth ---------------------------------------------------------------------------------------------------------


def test_smooth_moves_towards_the_neighbour_average_and_keeps_a_constant_field():
    mesh, lid, rows = _skinned(7, ((JAW, 0.5),))
    cloud = VertexCloud(mesh)
    s = WeightBrushSettings(operation=OP_SMOOTH, radius=10.0, flow=1.0, hardness=1.0)
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, s)
    before = _values(mesh, lid)
    stroke.dab(footprint(cloud, mesh.vertex_position(rows[3][3]), s))
    assert _values(mesh, lid) == before  # constant: nothing written
    # a step in x: jaw 1 on the left half, 0 on the right
    for j in range(7):
        for i in range(7):
            mesh.set_layer_value(lid, rows[j][i], ((JAW, 1.0),) if i < 3 else ())
    v = rows[3][2]  # the step's last 1: neighbours (left 1, right 0, up 1, down 1) average 0.75
    u = rows[3][3]  # first 0: neighbours (1, 0, 0, 0) average 0.25
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, WeightBrushSettings(operation=OP_SMOOTH, radius=0.1, flow=0.5,
                                                                         hardness=1.0))
    stroke.dab(Footprint((v, u), np.ones(2)))  # both from the values before the dab
    assert bone_share(mesh.layer_value(lid, v), JAW) == pytest.approx(1.0 + 0.5 * (0.75 - 1.0))
    assert bone_share(mesh.layer_value(lid, u), JAW) == pytest.approx(0.0 + 0.5 * (0.25 - 0.0))
    _check(mesh)


def test_smooth_lowers_through_the_parent_rule():
    mesh, lid, rows = _skinned(3)
    centre = rows[1][1]
    mesh.set_layer_value(lid, centre, ((JAW, 0.8),))
    stroke = BrushWeightStroke(mesh, lid, JAW, RIG, WeightBrushSettings(operation=OP_SMOOTH, flow=1.0))
    stroke.dab(Footprint((centre,), np.ones(1)))
    value = mesh.layer_value(lid, centre)
    assert bone_share(value, JAW) == pytest.approx(0.0)
    assert bone_share(value, HEAD) == pytest.approx(0.8)  # jaw's freed share went to head


# -- Clean ----------------------------------------------------------------------------------------------------------


def test_clean_removes_small_shares_by_the_write_rule():
    parent = parent_function(RIG)
    # lip 0.004 -> jaw (0.004 + 0.003 = 0.007 < 0.01) -> head 0.507; cheek 0.005 (root) -> the object
    got = clean_value(((HEAD, 0.5), (JAW, 0.003), (CHEEK, 0.005), (LIP, 0.004)), 0.01, parent)
    assert [k for k, _ in got] == [HEAD]
    assert bone_share(got, HEAD) == pytest.approx(0.507, abs=1e-15)
    assert clean_value(((HEAD, 0.5), (JAW, 0.5)), 0.01, parent) == ((HEAD, 0.5), (JAW, 0.5))
    assert CLEAN_THRESHOLD == 0.01


def test_clean_over_the_mesh_is_one_undo_step_and_respects_the_mask():
    mesh, lid, rows = _skinned(4, ((HEAD, 0.6), (JAW, 0.005), (CHEEK, 0.3)))
    protected = rows[0][0]
    before = _values(mesh, lid)
    history = HistoryStack()
    delta, count = record_mesh_change(mesh, lambda: clean_weights(mesh, lid, RIG, mask={protected: 0.5}))
    history.push(MeshDeltaCommand(mesh, delta, "Aufräumen"))
    assert count == 15
    assert mesh.layer_value(lid, protected) == before[protected]
    for v in mesh.all_vertex_ids():
        if v != protected:
            assert bone_share(mesh.layer_value(lid, v), JAW) == 0.0
            assert bone_share(mesh.layer_value(lid, v), HEAD) == pytest.approx(0.605, abs=1e-15)
    _check(mesh)
    history.undo()
    assert _values(mesh, lid) == before
    with pytest.raises(ValueError):
        clean_weights(mesh, lid, RIG, threshold=0.0)
