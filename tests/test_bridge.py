"""AD-031 P5: Bridge (§5) - the kernel `mirai.topology.bridge` and the app path `Application.bridge_plan` /
`bridge_borders`.

Kernel: two closed borders of equal size become `n` quads - the pairing with the minimal summed squared distance over
both directions and every rotation (brute force as the oracle), the plan independent of which point or edge of the
borders is selected, the winding against the neighbour faces (every edge of the result used once each way), no new
point, no UVs on the new faces (the old ones kept), no region; refusals: no / one / three borders, unequal sizes (O-11),
an open border, normals that disagree, faces along a border not oriented alike, a rung that already has faces (the
ends of an open tube). App: one Undo step with exact Undo / Redo, the new faces selected in face mode, every refusal
changing nothing (mode, editing view, nothing selected, posed rig, hidden geometry), a failure after
the change rolled back exactly, and the P5 acceptance test (§9.3): two ears as islands next to a symmetric head block
Re-Symmetrize; bridged into the head, the seam splits the mesh into two parts again and Re-Symmetrize runs. The layer
rules are `test_layer_topology_ops.py` / `test_weights_topology_ops.py`; the GL frames `test_gl_bridge.py`; Bridge under a
symmetry definition (AD-031 P6) is `test_symmetric_weld_bridge.py`."""

from __future__ import annotations

import dataclasses
import math
import random
from collections import Counter

import pytest

import tests._bootstrap  # noqa: F401
from core import FaceRegion, FaceRegions, LayerKind, Mesh, PointLayerInfo, SelectionMode
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.resymmetrize import ResymmetrizeRejected, plan_resymmetrize
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import definition_for_axis
from mirai.symmetry_topology import topological_sides
from mirai.topology import bridge as bridge_api
from mirai.topology.border import border_loops, cap_winding
from mirai.topology.bridge import plan_bridge
from tests.mesh_invariants import assert_mesh_invariants, assert_uv_invariants
from tests.test_skinning import _random_pose, _rig
from tests.test_symmetric_ops import make_app, plus_x_quad

V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE
WIDTH, HEIGHT = 800, 600
CTRL_Z, CTRL_Y = Input("key", "z", frozenset({"ctrl"})), Input("key", "y", frozenset({"ctrl"}))


def _annulus(mesh: Mesh, n: int, z: float, *, up: bool, turn: float = 0.0, start: int = 0) -> list:
    """A flat ring of `n` quads at height `z` (inner radius 1, outer 2), normal +Z when `up`; returns the inner points
    in angle order. `turn` rotates it, `start` changes which point is created first (other ids)."""
    angles = [turn + 2.0 * math.pi * ((k + start) % n) / n for k in range(n)]
    inner = {}
    outer = {}
    for k in range(n):
        a = angles[k]
        idx = (k + start) % n
        inner[idx] = mesh.add_vertex((math.cos(a), math.sin(a), z))
        outer[idx] = mesh.add_vertex((2.0 * math.cos(a), 2.0 * math.sin(a), z))
    for k in range(n):
        quad = [inner[k], outer[k], outer[(k + 1) % n], inner[(k + 1) % n]]  # counter-clockwise from above: +Z
        mesh.add_face(quad if up else quad[::-1], uvs=[(0.1 * k, 0.0), (0.1 * k, 1.0), (0.1 * k + 0.1, 1.0), (0.1 * k + 0.1, 0.0)])
    return [inner[k] for k in range(n)]


def _rings(n: int = 8, m: int | None = None, *, turn: float = 0.0, start: int = 3, flip: bool = False) -> tuple:
    """A bottom ring facing down and a top ring facing up (a tube between their inner borders is consistent)."""
    mesh = Mesh()
    bottom = _annulus(mesh, n, 0.0, up=False)
    top = _annulus(mesh, n if m is None else m, 1.0, up=not flip, turn=turn, start=start)
    return mesh, bottom, top


def _cost(mesh, first, partner) -> float:
    return sum(sum((p - q) ** 2 for p, q in zip(mesh.vertex_position(a), mesh.vertex_position(b)))
               for a, b in zip(first, partner))


def _partners(plan) -> list:
    first, second = plan.loops
    n = len(first)
    return [second[(plan.offset - i) % n] if plan.reversed_ else second[(plan.offset + i) % n] for i in range(n)]


def _assert_oriented(mesh: Mesh) -> None:
    """Every edge with two faces is used once in each direction (consistent normals)."""
    uses = Counter()
    for f in mesh.all_face_ids():
        vs = mesh.face_vertices(f)
        for u, v in zip(vs, vs[1:] + vs[:1]):
            uses[(u, v)] += 1
    assert all(count == 1 for count in uses.values()), "an edge is used twice in one direction"


def _run(mesh: Mesh, plan) -> list:
    assert plan.refusal is None, plan.refusal
    change = mesh.begin_change()
    faces = bridge_api.bridge(mesh, plan)
    mesh.end_change(change)
    return faces


# -- kernel ------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("turn", [0.0, 0.3, 2.0 * math.pi * 3 / 8 + 0.1, -1.0])
def test_the_pairing_is_the_minimal_sum_of_squared_distances(turn):
    """Over both directions and all rotations (brute force as the oracle); the result is a closed, consistently
    oriented tube of n quads without a new point."""
    mesh, bottom, top = _rings(turn=turn)
    vertices = set(mesh.all_vertex_ids())
    plan = plan_bridge(mesh, V, {bottom[0], top[5]})
    assert plan.refusal is None and len(plan.quads) == 8
    first, second = plan.loops
    n = len(first)
    candidates = [[second[(k - i) % n] if d else second[(k + i) % n] for i in range(n)] for d in (0, 1) for k in range(n)]
    assert _cost(mesh, first, _partners(plan)) == min(_cost(mesh, first, c) for c in candidates)
    faces = _run(mesh, plan)
    assert len(faces) == 8 and set(mesh.all_vertex_ids()) == vertices
    assert_mesh_invariants(mesh)
    _assert_oriented(mesh)
    for q in plan.quads:  # each quad is a rung pair of the plan
        assert len(set(q)) == 4


def test_the_plan_does_not_depend_on_the_selection():
    mesh, bottom, top = _rings(turn=0.2)
    edges = [e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) <= set(bottom) | set(top)]
    plans = {plan_bridge(mesh, V, {b, t}) for b in bottom[:3] for t in top[2:5]}
    plans.add(plan_bridge(mesh, V, set(bottom) | set(top)))
    plans.add(plan_bridge(mesh, E, set(edges)))
    assert len(plans) == 1 and next(iter(plans)).refusal is None


def test_new_faces_have_no_uvs_and_no_region_and_old_ones_keep_theirs():
    """D8 / D9: the bridge faces carry no UVs and join no region; the existing faces keep both."""
    mesh, bottom, top = _rings()
    old = sorted(mesh.all_face_ids())
    regions = FaceRegions((FaceRegion("Lower", frozenset(old[:8])),))
    mesh.face_regions = regions
    uvs = {f: mesh.face_uvs(f) for f in old}
    faces = _run(mesh, plan_bridge(mesh, V, {bottom[0], top[0]}))
    assert all(mesh.face_uvs(f) is None for f in faces)
    assert {f: mesh.face_uvs(f) for f in old} == uvs
    assert mesh.face_regions == regions
    assert_uv_invariants(mesh)


def _open_tube() -> tuple:
    """A short open tube of 6 quads: its two ends are borders joined by the tube's own edges."""
    mesh = Mesh()
    n = 6
    low = [mesh.add_vertex((math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n), 0.0)) for k in range(n)]
    high = [mesh.add_vertex((math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n), 1.0)) for k in range(n)]
    for k in range(n):
        mesh.add_face([low[k], low[(k + 1) % n], high[(k + 1) % n], high[k]])
    return mesh, low, high


def _bowtie_and_ring() -> tuple:
    mesh = Mesh()
    a = [mesh.add_vertex(p) for p in [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]]
    b = [a[2]] + [mesh.add_vertex(p) for p in [(2, 1, 0), (2, 2, 0), (1, 2, 0)]]
    mesh.add_face(a)
    mesh.add_face(b)
    c = [mesh.add_vertex(p) for p in [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]]
    mesh.add_face(c)
    return mesh, a, c


def _inconsistent() -> tuple:
    """Two quads sharing an edge with opposite windings (their outline is one border of 6) and a hexagon."""
    mesh = Mesh()
    p = [mesh.add_vertex(q) for q in [(0, 0, 0), (1, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (0, 1, 0)]]
    mesh.add_face([p[0], p[1], p[4], p[5]])
    mesh.add_face([p[1], p[2], p[3], p[4]][::-1])
    h = [mesh.add_vertex((x, y, 1.0)) for x, y in [(0, 0), (1, 0), (2, 0), (2, 1), (1, 1), (0, 1)]]
    mesh.add_face(h)
    return mesh, p, h


def _cases():
    def nothing():
        mesh, bottom, top = _rings()
        return mesh, set()

    def one():
        mesh, bottom, top = _rings()
        return mesh, {bottom[0], bottom[3]}

    def three():
        mesh, bottom, top = _rings()
        outer = next(v for v in mesh.all_vertex_ids() if math.hypot(*mesh.vertex_position(v)[:2]) > 1.5)
        return mesh, {bottom[0], top[0], outer}

    def unequal():
        mesh, bottom, top = _rings(8, 6)
        return mesh, {bottom[0], top[0]}

    def open_border():
        mesh, a, c = _bowtie_and_ring()
        return mesh, {a[0], c[0]}

    def flipped():
        mesh, bottom, top = _rings(flip=True)
        return mesh, {bottom[0], top[0]}

    def not_alike():
        mesh, p, h = _inconsistent()
        return mesh, {p[0], h[0]}

    def tube_ends():
        mesh, low, high = _open_tube()
        return mesh, {low[0], high[0]}

    return [
        ("nothing", nothing, "select points or edges of two open borders"),
        ("one border", one, "only one border"),
        ("three borders", three, "touches 3 borders"),
        ("unequal (O-11)", unequal, "8 and 6 points"),
        ("open border", open_border, "not closed"),
        ("normals", flipped, "normals of the two sides disagree"),
        ("not alike", not_alike, "not oriented alike"),
        ("rung has faces", tube_ends, "already joined by a face"),
    ]


CASES = _cases()


@pytest.mark.parametrize("name, make, text", CASES, ids=[c[0] for c in CASES])
def test_the_kernel_refuses_read_only(name, make, text):
    mesh, ids = make()
    state = mesh.export_state()
    plan = plan_bridge(mesh, V, ids)
    assert plan.refusal is not None and text in plan.refusal, plan.refusal
    assert plan.quads == () and mesh.export_state() == state
    with pytest.raises(bridge_api.BridgeRefused):
        bridge_api.bridge(mesh, plan)
    assert mesh.export_state() == state


def test_a_bridge_that_would_not_end_manifold_is_refused_inside_the_step():
    mesh, bottom, top = _rings()
    plan = plan_bridge(mesh, V, {bottom[0], top[0]})
    bad = dataclasses.replace(plan, quads=plan.quads + plan.quads[:1])
    state = _body(mesh)
    change = mesh.begin_change()
    with pytest.raises(bridge_api.BridgeRefused):
        bridge_api.bridge(mesh, bad)
    mesh.rollback_change(change)
    assert _body(mesh) == state  # the id counters stay forward (AD-001)


# -- app ---------------------------------------------------------------------------------------------------------------


def _app(mesh: Mesh) -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(mesh.export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _select_points(app: Application, vertices) -> None:
    app.dispatch_command(commands.SET_VERTEX_MODE)
    app.selection.clear()
    app.selection.vertices = set(vertices)


def _body(mesh) -> dict:
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}


def _snapshot(app: Application) -> tuple:
    selection = app.selection
    return (
        _body(app.scene.mesh), len(app.history), selection.mode, frozenset(selection.vertices),
        frozenset(selection.edges), frozenset(selection.faces), app.scene.edit_object_id,
    )


def _rings_app() -> tuple:
    mesh, bottom, top = _rings(turn=0.2)
    app = _app(mesh)
    _select_points(app, {bottom[0], top[0]})
    return app, bottom, top


def test_bridge_is_one_step_with_exact_undo_redo_and_selects_the_new_faces():
    app, bottom, top = _rings_app()
    mesh = app.scene.mesh
    before = _snapshot(app)
    faces = set(mesh.all_face_ids())
    assert app.bridge_borders(), app.status_message
    assert app.status_message == "Bridge: 8 quads between two borders of 8 points (no UVs, no group)"
    assert len(app.history) == before[1] + 1
    new = set(mesh.all_face_ids()) - faces
    assert len(new) == 8 and app.selection.mode is F and app.selection.faces == new
    after = _body(mesh)
    assert_mesh_invariants(mesh)
    assert app.key_press(CTRL_Z)
    assert _snapshot(app) == before
    assert app.key_press(CTRL_Y)
    assert _body(mesh) == after


def test_the_command_and_edge_mode_run_the_same_bridge():
    app, bottom, top = _rings_app()
    mesh = app.scene.mesh
    edge = next(e for e in mesh.vertex_edges(bottom[0]) if len(mesh.edge_faces(e)) == 1)
    edge2 = next(e for e in mesh.vertex_edges(top[0]) if len(mesh.edge_faces(e)) == 1)
    app.dispatch_command(commands.SET_EDGE_MODE)
    app.selection.clear()
    app.selection.edges = {edge, edge2}
    plan = app.bridge_plan()
    assert plan.refusal is None
    assert app.dispatch_command(commands.BRIDGE), app.status_message
    assert len(mesh.all_face_ids()) == 24


def _refusal(app: Application, case: str) -> None:
    mesh = app.scene.mesh
    if case == "face mode":
        app.dispatch_command(commands.SET_FACE_MODE)
        app.selection.faces = set(mesh.all_face_ids())
    elif case == "object mode":
        app.dispatch_command(commands.SET_OBJECT_MODE)
    elif case == "nothing selected":
        app.selection.clear()
    elif case == "editing view":
        selected = set(app.selection.vertices)
        assert app.create_morph_target("Smile") is not None, app.status_message
        assert app.edit_morph_target(), app.status_message
        _select_points(app, selected)
    elif case == "hidden":
        selected = set(app.selection.vertices)
        bottom_faces = sorted(f for f in mesh.all_face_ids() if mesh.vertex_position(mesh.face_vertices(f)[0])[2] == 0.0)
        app.dispatch_command(commands.SET_FACE_MODE)
        app.selection.faces = {bottom_faces[3]}
        assert app.dispatch_command(commands.HIDE_SELECTION), app.status_message
        _select_points(app, selected)


@pytest.mark.parametrize("case, text", [
    ("face mode", "press 1 or 2"),
    ("object mode", "press 1 or 2"),
    ("nothing selected", "none selected"),
    ("editing view", "on the base only"),
    ("hidden", "hidden geometry in the way"),
])
def test_a_refusal_changes_nothing(case, text):
    app, bottom, top = _rings_app()
    _refusal(app, case)
    before = _snapshot(app)
    assert app.bridge_borders() is False
    assert text in app.status_message, app.status_message
    assert _snapshot(app) == before
    assert app.dispatch_command(commands.BRIDGE) is False
    assert _snapshot(app) == before
    assert app.bridge_plan().refusal is not None


@pytest.mark.parametrize("name, make, text", CASES[1:], ids=[c[0] for c in CASES[1:]])
def test_the_kernel_refusals_change_nothing_in_the_app(name, make, text):
    mesh, ids = make()
    app = _app(mesh)
    _select_points(app, ids)
    before = _snapshot(app)
    assert app.bridge_borders() is False
    assert text in app.status_message, app.status_message
    assert _snapshot(app) == before


def test_posed_rig_with_a_bound_mesh_is_refused():
    app, bottom, top = _rings_app()
    rig = _rig()
    app.scene.rig = rig
    mesh = app.scene.mesh
    skin = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(skin, v, ((int(rig.bone_ids()[0]), 1.0),))
    app._skeleton.set_pose(_random_pose(random.Random(3), rig, share=1.0))
    assert app.posed
    before = _snapshot(app)
    assert app.bridge_borders() is False
    assert "is posed" in app.status_message and _snapshot(app) == before
    assert app.dispatch_command(commands.BRIDGE) is False and _snapshot(app) == before
    app._skeleton.set_pose({})
    assert app.bridge_borders(), app.status_message


def test_a_failure_after_the_change_is_rolled_back_exactly(monkeypatch):
    app, bottom, top = _rings_app()
    before = _snapshot(app)
    real = bridge_api.plan_bridge

    def doubled(*args):
        plan = real(*args)
        return dataclasses.replace(plan, quads=plan.quads + plan.quads[:1])

    monkeypatch.setattr(bridge_api, "plan_bridge", doubled)
    assert app.bridge_borders() is False
    assert "would not join exactly two faces" in app.status_message
    assert _snapshot(app) == before


# -- the P5 acceptance test (§9.3): Re-Symmetrize works again once the islands are bridged into the head ---------------


def _ear(mesh: Mesh, hole: list, *, mirror: bool) -> list:
    """An open box outside the hole (`hole` in Cap's winding, so its normal points out of the head): a ring of the
    hole's points pushed out by 0.3 along the normal, a smaller cap ring further out; its border is the first ring.
    `mirror`: the X-mirror image of the same ear (positions x -> -x, windings reversed)."""
    pts = [mesh.vertex_position(v) for v in hole]
    if mirror:
        pts = [(-p[0], p[1], p[2]) for p in pts]
    c = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
    u = [pts[1][i] - pts[0][i] for i in range(3)]
    w = [pts[2][i] - pts[1][i] for i in range(3)]
    nrm = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
    length = math.sqrt(sum(x * x for x in nrm))
    nrm = tuple(x / length for x in nrm)
    if mirror:
        nrm = tuple(-x for x in nrm)  # the mirrored points run the other way round
    ring = [mesh.add_vertex(tuple(p[i] + 0.3 * nrm[i] for i in range(3))) for p in pts]
    tip = [mesh.add_vertex(tuple(c[i] + 0.5 * (p[i] - c[i]) + 0.6 * nrm[i] for i in range(3))) for p in pts]
    n = len(ring)
    faces = [[ring[k], ring[(k + 1) % n], tip[(k + 1) % n], tip[k]] for k in range(n)] + [tip]
    for face in faces:
        mesh.add_face(face[::-1] if mirror else face)
    return ring


def test_re_symmetrize_works_again_after_the_ears_are_bridged_into_the_head():
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    quad = plus_x_quad(mesh, touching_seam=False)
    position = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
    mirror = next(
        f for f in mesh.all_face_ids()
        if {position.get((-p[0], p[1], p[2])) for p in (mesh.vertex_position(v) for v in mesh.face_vertices(f))}
        == set(mesh.face_vertices(quad))
    )
    corners = mesh.face_vertices(quad)
    mesh.delete_faces([quad, mirror])
    loop = next(lp for lp in border_loops(mesh, [e for v in corners for e in mesh.vertex_edges(v)])
                if set(lp.vertices) == set(corners))
    hole = cap_winding(mesh, loop)
    right = _ear(mesh, hole, mirror=False)
    left = _ear(mesh, hole, mirror=True)
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert symmetry_state(mesh) is SymmetryState.VALID
    with pytest.raises(ResymmetrizeRejected, match="Teile"):  # the ears are extra parts (§3.5)
        plan_resymmetrize(mesh, hole[0])
    mesh.symmetry_definition = None  # P5 path; the same with symmetry on (P6): test_symmetric_weld_bridge.py
    on_border = {v for v in mesh.all_vertex_ids() if any(len(mesh.edge_faces(e)) == 1 for e in mesh.vertex_edges(v))}
    for ear in (right, left):
        head_side = min((v for v in on_border if v not in ear), key=lambda v: sum(
            (a - b) ** 2 for a, b in zip(mesh.vertex_position(v), mesh.vertex_position(ear[0]))))
        _select_points(app, {head_side, ear[0]})  # one point of the hole, one of the ear
        assert app.bridge_borders(), app.status_message
    assert_mesh_invariants(mesh)
    _assert_oriented(mesh)
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert topological_sides(mesh).component_count == 2
    side = topological_sides(mesh)
    source = next(v for v, s in sorted(side.vertex_side.items()) if s == 1)
    assert plan_resymmetrize(mesh, source) is not None
