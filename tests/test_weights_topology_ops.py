"""AD-028 T-5: every gated topology operation on a mesh with a weights layer, through `Application`, plain and
symmetric - and Apply transform and mirror copy.

The fixtures are the AD-025 Phase 5 / H1 rule fixtures (`test_layer_topology_ops.RULE_FIXTURES`,
`test_layer_gate.RULE_FIXTURES`); the mesh carries one dense weights layer instead of the vector layers (one to three
keys per point, some points fully bound; on the symmetric fixture a pair holds the same value - an on-plane bone's
weights). Per operation: every new or merged vertex has the §3.5 rule's value (`core.mesh.combine_values` of its
sources: the edge blend, the group mean, the barycentric origin of the hit triangle, a copy), every other vertex keeps
its value bit for bit, the mirror side's values equal the source side's, W1-W4 hold (`assert_layer_invariants`), and
Undo / Redo are exact. The Knife runs its open cut, closed shape and self-crossing on the primitives
(`test_layer_knife`) and end to end with real picks, plain and symmetric.
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh
from core.mesh import LayerKind, PointLayerInfo, combine_values
from core.rig import Rig
from mirai import object_space
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.skinning import BonePose, evaluate, placement_of, skin_layer
from mirai.symmetry import vertex_correspondence
from mirai.topology.contextual_c import CContext
from tests import test_layer_gate as h1
from tests import test_layer_topology_ops as phase5
from tests.mesh_invariants import assert_layer_invariants
from tests.test_application_delete_dissolve import _app
from tests.test_layer_knife import T_f, T_v, _closed_shape, area_weights, build_grid, grid_face, on_segment, run, vertex_at
from tests.test_symmetric_ops import make_app
from viewport.derived import triangulate_mesh_face

TOL = 1e-12
KEYS = range(6)


def add_weights(mesh: Mesh, seed: int = 0):
    """One dense weights layer; under a symmetry definition the partner of a vertex gets the same value."""
    rng = random.Random(seed)
    partners = {}
    if mesh.symmetry_definition is not None:
        partners = {v: getattr(c, "partner", None) for v, c in vertex_correspondence(mesh).items()}
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in sorted(mesh.all_vertex_ids(), key=int):
        partner = partners.get(v)
        if partner is not None and int(partner) < int(v):
            continue
        keys = rng.sample(list(KEYS), rng.randint(1, 3))
        raw = [rng.uniform(0.05, 1.0) for _ in keys]
        total = sum(raw) / (1.0 if rng.random() < 0.4 else rng.uniform(0.5, 0.95))  # 40 % fully bound
        value = tuple(sorted((k, w / total) for k, w in zip(keys, raw)))
        mesh.set_layer_value(lid, v, value)
        if partner is not None and partner != v:
            mesh.set_layer_value(lid, partner, mesh.layer_value(lid, v))
    return lid


def _w(mesh: Mesh, v) -> tuple:
    return mesh.layer_value(skin_layer(mesh), v)


def _rule(sources, rule: str = "affine") -> tuple:
    return combine_values(LayerKind.WEIGHTS, sources, rule)


def _close(a, b, tol=TOL) -> bool:
    da, db = dict(a), dict(b)
    return set(da) == set(db) and all(abs(da[k] - db[k]) <= tol for k in da)


# -- the rules on weights ---------------------------------------------------------------------------------------


def midpoint_rule(ref: Mesh, mesh: Mesh, info) -> int:
    mids = {}
    for e in ref.all_edge_ids():
        a, b = ref.edge_vertices(e)
        pa, pb = ref.vertex_position(a), ref.vertex_position(b)
        mids[tuple(x * 0.5 + y * 0.5 for x, y in zip(pa, pb))] = (a, b)
    new = [v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)]
    for v in new:
        a, b = mids[tuple(mesh.vertex_position(v))]
        assert _w(mesh, v) == _rule(((_w(ref, a), 0.5), (_w(ref, b), 0.5)), "midpoint"), v
    return len(new)


def collapse_rule(ref: Mesh, mesh: Mesh, info) -> int:
    removed = {v for v in ref.all_vertex_ids() if not mesh.is_valid_vertex(v)}
    assert removed and all(ref.is_valid_vertex(v) for v in mesh.all_vertex_ids())
    moved = [v for v in mesh.all_vertex_ids() if tuple(mesh.vertex_position(v)) != tuple(ref.vertex_position(v))]
    count = 0
    for s in moved:
        group, todo = {s}, [s]
        while todo:
            u = todo.pop()
            for e in ref.vertex_edges(u):
                x = next(y for y in ref.edge_vertices(e) if y != u)
                if x in removed and x not in group:
                    group.add(x)
                    todo.append(x)
        n = len(group)
        assert n > 1
        assert _w(mesh, s) == _rule([(_w(ref, v), 1.0 / n) for v in sorted(group, key=int)], "mean"), s
        count += 1
    return count


def copy_rule(ref: Mesh, mesh: Mesh, info) -> int:
    pairs = info["old_to_new"]
    for old, new in pairs.items():
        assert _w(mesh, new) == _w(ref, old), (old, new)  # bit-exact copies
    assert {v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)} == set(pairs.values())
    return len(pairs)


def source_copy_rule(ref: Mesh, mesh: Mesh, info) -> int:
    for new, old in info["sources"].items():
        assert _w(mesh, new) == _w(ref, old), (old, new)
    return len(info["sources"])


RULES = {
    phase5.midpoint_rule: midpoint_rule,
    phase5.collapse_rule: collapse_rule,
    phase5.copy_rule: copy_rule,
    phase5.source_copy_rule: source_copy_rule,
}


def _check_mirror(ref: Mesh, mesh: Mesh) -> int:
    """Every vertex created or moved on the +X side: its mirror partner (by position) holds the same weights."""
    by_pos = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
    pairs = 0
    for v in mesh.all_vertex_ids():
        pos = tuple(mesh.vertex_position(v))
        if pos[0] <= 0.0 or (ref.is_valid_vertex(v) and tuple(ref.vertex_position(v)) == pos):
            continue
        partner = by_pos[(-pos[0], pos[1], pos[2])]
        assert _close(_w(mesh, partner), _w(mesh, v)), (v, partner)
        pairs += 1
    return pairs


def _others_unchanged(ref: Mesh, mesh: Mesh, touched=()) -> None:
    for v in mesh.all_vertex_ids():
        if ref.is_valid_vertex(v) and v not in touched:
            assert _w(mesh, v) == _w(ref, v), v


# -- Phase 5 operations (create or merge vertices) ------------------------------------------------------------


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
@pytest.mark.parametrize("key", list(phase5.RULE_FIXTURES), ids=str)
def test_a_vertex_creating_or_merging_operation_follows_the_weights_rule(key, symmetric):
    plain, sym, vector_rule = phase5.RULE_FIXTURES[key]
    app = make_app("subd_cube") if symmetric else _app(3)
    command = (sym if symmetric else plain)(app)
    mesh = app.scene.mesh
    add_weights(mesh, seed=sum(map(ord, str(key))))
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    info: dict = {}
    phase5._run(app, command, info)
    assert RULES[vector_rule](ref, mesh, info) >= 1
    moved = {v for v in mesh.all_vertex_ids() if ref.is_valid_vertex(v)
             and tuple(mesh.vertex_position(v)) != tuple(ref.vertex_position(v))}
    _others_unchanged(ref, mesh, moved if key == commands.COLLAPSE else ())
    if symmetric:
        assert _check_mirror(ref, mesh) >= 1
    assert_layer_invariants(mesh)
    phase5._assert_undo_redo_exact(app, before)


# -- H1 operations (create none, remove some) -----------------------------------------------------------------


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
@pytest.mark.parametrize("key", list(h1.RULE_FIXTURES), ids=str)
def test_a_removing_operation_keeps_the_survivors_weights(key, symmetric):
    command, plain, sym = h1.RULE_FIXTURES[key]
    app = make_app("subd_cube") if symmetric else _app(3)
    (sym if symmetric else plain)(app)
    mesh = app.scene.mesh
    add_weights(mesh, 7)
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    history = len(app.history)
    assert h1._press(app, command) is True, app.status_message
    assert len(app.history) == history + 1
    assert set(mesh.all_vertex_ids()) <= set(ref.all_vertex_ids())
    _others_unchanged(ref, mesh)
    assert_layer_invariants(mesh)
    phase5._assert_undo_redo_exact(app, before)


# -- the Knife --------------------------------------------------------------------------------------------------


def _containing(start: Mesh, face, p):
    best = None
    for tri in triangulate_mesh_face(start, face):
        w = area_weights(*[start.vertex_position(v) for v in tri], p)
        key = max(0.0, -min(w))
        if best is None or key < best[0]:
            best = (key, tri, w)
    assert best[0] <= 1e-9
    return best[1], best[2]


def check_knife(start: Mesh, mesh: Mesh, path: list[dict]) -> dict:
    """Every new vertex's weights against the rule: an interior point the barycentric combination of its hit
    triangle's corners, an edge point the edge blend at its t (positions -> factors, 1e-12)."""
    faces = {tuple(p["position"]): p["face_id"] for p in path if p.get("kind") == "face"}
    edges = [start.edge_vertices(e) for e in start.all_edge_ids()]
    counts = {"face": 0, "edge": 0, "other": 0}
    for v in mesh.all_vertex_ids():
        if start.is_valid_vertex(v):
            continue
        pos = tuple(mesh.vertex_position(v))
        face = faces.get(pos)
        if face is not None:
            tri, w = _containing(start, face, pos)
            expected = _rule([(_w(start, c), wi) for c, wi in zip(tri, w)])
            counts["face"] += 1
        else:
            ends = next((ab for ab in edges if on_segment(start.vertex_position(ab[0]), start.vertex_position(ab[1]), pos)), None)
            if ends is None:
                counts["other"] += 1
                continue
            a, b = ends
            t = math.dist(start.vertex_position(a), pos) / math.dist(start.vertex_position(a), start.vertex_position(b))
            expected = _rule(((_w(start, a), 1.0 - t), (_w(start, b), t)))
            counts["edge"] += 1
        assert _close(_w(mesh, v), expected), (v, pos, _w(mesh, v), expected)
    return counts


def _undo_redo(scene, mesh: Mesh, start: dict) -> None:
    after = mesh.export_state()
    scene.history.undo()
    undone = mesh.export_state()
    assert {k: x for k, x in undone.items() if not k.endswith("_counter")} == {
        k: x for k, x in start.items() if not k.endswith("_counter")
    }
    scene.history.redo()
    assert mesh.export_state() == after


def test_knife_open_cut_on_weights():
    mesh = build_grid(4)
    add_weights(mesh, 1)
    start = mesh.export_state()
    ref = Mesh.from_state(start)
    f = grid_face(mesh, (1, 1))
    e_right = next(e for e in mesh.face_edges(f) if all(mesh.vertex_position(v)[0] == 2.0 for v in mesh.edge_vertices(e)))
    knife, scene, cmd = run(mesh, [T_v(vertex_at(mesh, (1.0, 1.0, 0.0))), T_f(f, (1.3, 1.6, 0.0)),
                                   T_f(f, (1.7, 1.45, 0.0)), {"kind": "edge", "edge_id": e_right, "t": 0.3}])
    assert cmd is not None
    assert check_knife(ref, mesh, knife.path) == {"face": 2, "edge": 1, "other": 0}
    assert_layer_invariants(mesh)
    _undo_redo(scene, mesh, start)


def test_knife_closed_shape_on_weights():
    mesh = build_grid(4)
    add_weights(mesh, 2)
    start = mesh.export_state()
    knife, scene, cmd = run(mesh, _closed_shape(mesh))
    assert cmd is not None and knife.last_resolution.closed_shapes[0].built
    assert check_knife(Mesh.from_state(start), mesh, knife.path) == {"face": 4, "edge": 0, "other": 0}
    assert_layer_invariants(mesh)
    _undo_redo(scene, mesh, start)


def test_knife_self_crossing_on_weights():
    mesh = build_grid(4)
    add_weights(mesh, 3)
    start = mesh.export_state()
    ref = Mesh.from_state(start)
    f = grid_face(mesh, (1, 1))
    targets = [T_v(vertex_at(mesh, (1.0, 1.0, 0.0))), T_f(f, (1.8, 1.2, 0.0)), T_f(f, (1.8, 1.5, 0.0)),
               T_f(f, (1.4, 1.05, 0.0)), T_v(vertex_at(mesh, (2.0, 1.0, 0.0)))]
    knife, scene, cmd = run(mesh, targets)
    assert cmd is not None and knife.last_resolution.loops_built == 1
    counts = check_knife(ref, mesh, knife.path)
    assert counts["face"] == 3 and counts["other"] == 1
    clicked = {tuple(p["position"]) for p in knife.path if p["kind"] == "face"}
    (x,) = [v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v) and tuple(mesh.vertex_position(v)) not in clicked]
    tri, w = _containing(ref, f, mesh.vertex_position(x))
    assert _close(_w(mesh, x), _rule([(_w(ref, c), wi) for c, wi in zip(tri, w)]))
    assert_layer_invariants(mesh)
    _undo_redo(scene, mesh, start)


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
def test_knife_end_to_end_on_weights(symmetric):
    """C with nothing selected on a weighted mesh, clicks on the warped +X face (edge and interior points), Enter:
    one Undo step; under symmetry the mirror side's new points hold the source side's weights."""
    from tests.test_application_knife import ENTER, LMB

    app = phase5._knife_app(symmetric)
    mesh = app.scene.mesh
    add_weights(mesh, 21)
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    face = max(mesh.all_face_ids(), key=lambda f: min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)))
    corners = mesh.face_vertices(face)
    edges = mesh.face_edges(face)
    pa = [mesh.vertex_position(v) for v in corners]

    def inside(u, w):
        return tuple(pa[0][k] * (1 - u) * (1 - w) + pa[1][k] * u * (1 - w) + pa[2][k] * u * w + pa[3][k] * (1 - u) * w
                     for k in range(3))

    def on_edge(e, t):
        a, b = mesh.edge_vertices(e)
        p0, p1 = mesh.vertex_position(a), mesh.vertex_position(b)
        return tuple(p0[k] + t * (p1[k] - p0[k]) for k in range(3))

    app.selection.clear()
    assert app.key_press(Input("key", "c")) is True, app.status_message
    for p in (on_edge(edges[0], 0.35), inside(0.45, 0.4), inside(0.6, 0.65), on_edge(edges[2], 0.4)):
        sx, sy = phase5._screen_of(app, p)
        app.pointer_motion(sx, sy)
        app.pointer_press(LMB, sx, sy)
        assert app.pointer_release("LEFT", sx, sy), app.status_message
    path = [dict(p) for p in app._knife.tool.path]
    history = len(app.history)
    assert app.key_press(ENTER)
    assert len(app.history) == history + 1
    counts = check_knife(ref, mesh, path)  # the mirror side's interior points: `_check_mirror`
    assert counts["face"] == 2 and counts["edge"] >= 1, counts
    if symmetric:
        assert _check_mirror(ref, mesh) >= 4
    assert_layer_invariants(mesh)
    phase5._assert_undo_redo_exact(app, before)


# -- Apply transform and mirror copy ------------------------------------------------------------------------------


def test_apply_transform_keeps_the_weights_and_the_posed_world_result():
    from tests.test_mirror_pairs import _placed_sphere

    app = _app()
    obj = _placed_sphere(app, "bound")
    mesh = obj.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    rng = random.Random(5)
    for v in mesh.all_vertex_ids():
        a = rng.uniform(0.0, 1.0)
        mesh.set_layer_value(lid, v, ((0, a), (1, (1.0 - a) * rng.uniform(0.0, 1.0))))
    rig, b0 = Rig().with_new_bone("Jaw", (2.0, 1.2, -0.5), (2.2, 0.6, -0.3))
    rig, b1 = rig.with_new_bone("Tip", (2.2, 0.6, -0.3), (2.3, 0.3, -0.2), parent=b0)
    app.scene.rig = rig
    pose = {
        b0: BonePose(rotation=object_space.axis_angle_rotation((1.0, 0.0, 0.0), 0.35)),
        b1: BonePose(rotation=object_space.axis_angle_rotation((0.0, 0.6, 0.8), -0.5), translation=(0.01, 0.0, 0.02)),
    }
    shown = evaluate(mesh, None, rig, pose, placement_of(obj))
    world_before = {v: object_space.to_world(obj, p) for v, p in shown.items()}
    values = dict(mesh.layer_items(lid))
    app.key_press(Input("key", "4"))
    app.selection.objects = {obj.id}
    assert app.dispatch_command(commands.APPLY_TRANSFORM) is True, app.status_message
    assert object_space.is_identity(obj.transform)
    assert dict(mesh.layer_items(lid)) == values  # weights unchanged (F-4)
    after = evaluate(mesh, None, rig, pose, placement_of(obj))
    assert max(math.dist(after[v], world_before[v]) for v in after) <= 1e-12
    assert_layer_invariants(mesh)
    # the placement stays locked while bound; Apply is the way
    assert app.dispatch_command(commands.CLEAR_TRANSFORM) is False
    assert app.status_message.endswith("'bound' is locked while bound to the rig")


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
def test_mirror_copy_of_a_weighted_mesh_is_refused_untouched(symmetric):
    from tests.test_mirror_pairs import _placed_sphere

    if symmetric:
        app = make_app("subd_cube")
        source = app.scene.edit_object
    else:
        app = _app()
        source = _placed_sphere(app)
    add_weights(source.mesh, 31)
    state = source.mesh.export_state()
    app.key_press(Input("key", "4"))
    app.selection.objects = {source.id}
    objects, history = set(app.scene.objects), len(app.history)
    assert app.mirror_copy("X") is None
    assert app.status_message == "Mirror copy: locked while this mesh has skin weights (bones cannot be mirrored yet)"
    assert set(app.scene.objects) == objects and len(app.history) == history
    assert source.mesh.export_state() == state


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
@pytest.mark.parametrize("entry", [commands.ATTACH, commands.ATTACH_TAKE_LOOK, "attach_objects"])
def test_attach_merges_the_weights_unchanged(entry, symmetric):
    """AD-031 §3.2 with weights: the source's values go into the destination's one weights layer unchanged (keys and
    weights), the destination's own values stay, no second weights layer; Undo restores both. No rig: not bound, so
    no O-5 question."""
    from mirai.scene_factory import create_cube

    app = make_app("subd_cube") if symmetric else _app()
    dst = app.scene.edit_object
    lid = add_weights(dst.mesh, 5)
    own = dict(dst.mesh.layer_items(lid))
    part_mesh = create_cube(0.5)
    for v in part_mesh.all_vertex_ids():  # off the destination, X-symmetric in itself
        x, y, z = part_mesh.vertex_position(v)
        part_mesh.set_vertex_position(v, (x, y + 5.0, z))
    src = add_weights(part_mesh, 9)
    incoming = sorted(part_mesh.layer_value(src, v) for v in part_mesh.all_vertex_ids())
    part = app.scene.add_object(part_mesh, name="Part")
    app.key_press(Input("key", "4"))
    app.selection.objects = {part.id}
    vertices, state = set(dst.mesh.all_vertex_ids()), _body_state(dst.mesh)
    ok = app.attach_objects() if entry == "attach_objects" else phase5._press(app, entry)
    assert ok, app.status_message
    mesh = dst.mesh
    assert skin_layer(mesh) == lid and [l for l in mesh.point_layer_ids()] == [lid]
    new = set(mesh.all_vertex_ids()) - vertices
    assert {v: mesh.layer_value(lid, v) for v in vertices} == {v: own.get(v, ()) for v in vertices}
    assert sorted(mesh.layer_value(lid, v) for v in new) == incoming
    assert_layer_invariants(mesh)
    assert app.key_press(phase5.CTRL_Z)
    assert _body_state(mesh) == state


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
@pytest.mark.parametrize("entry", [commands.DETACH, "detach_faces"])
def test_detach_keeps_the_weights_unchanged(entry, symmetric):
    """AD-031 §2.2 with weights: the new object's weights layer holds the extracted points' values unchanged (keys and
    weights), the source keeps its survivors' values; Undo restores the source exactly (`detach_layered`)."""
    from tests.test_application_delete_dissolve import _grid_face

    app = make_app("subd_cube") if symmetric else _app(3)
    face = phase5.plus_x_quad(app.scene.mesh, touching_seam=False) if symmetric else _grid_face(app, 1, 1)
    _, out = phase5.detach_layered(app, entry, face, lambda mesh: add_weights(mesh, 13))
    assert skin_layer(out) is not None


def _body_state(mesh: Mesh) -> dict:
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}


def test_every_declared_entry_is_covered_with_weights():
    """Declaration = tested support, with weights too (AD-028 §8.6): every declared entry has a weights test here."""
    from mirai import layer_declarations as gate

    covered = set(phase5.RULE_FIXTURES) | set(h1.RULE_FIXTURES) | {CContext.KNIFE, commands.APPLY_TRANSFORM, "mirror_copy"}
    covered |= {commands.ATTACH, commands.ATTACH_TAKE_LOOK, "attach_objects"}  # test_attach_merges_the_weights_…
    covered |= {commands.DETACH, "detach_faces"}  # test_detach_keeps_the_weights_unchanged
    assert covered == set(gate.LAYER_SAFE_OPERATIONS)

