"""AD-025 Phase 5: topology operations on a mesh with morph targets, through `Application` (T-7 rule
fixtures for the entries Phase 5 declares in `mirai.layer_declarations.LAYER_SAFE_OPERATIONS`).

Per operation, on a plain and a symmetric layered fixture (three layers: two dense, one sparse; on the
symmetric fixture the values are mirror images across the plane): the operation runs, every new or
merged vertex gets the analytic value of AD-025 §3 (bit-exact where the rule is the Core's own
arithmetic, else 1e-12), every other vertex keeps its value bit for bit, the mirror side's values are
the mirrored source values, L1-L5 hold, and Undo / Redo are exact (export incl. "point_layers",
counters forward). `RULE_FIXTURES` is imported by `test_layer_gate.py`: a declared entry without a row
here or there fails (declaration = tested support).

The Knife's own rule tests (barycentric origins, bridges, crossings, checkpoints, the symmetric replay)
are in `test_layer_knife.py`; here the Knife runs end to end with real picks.
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, PointLayerInfo, SelectionMode
from mirai.controllers.gestures import OffsetGesture
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.topology.contextual_c import CContext
from tests.mesh_invariants import assert_layer_invariants
from tests.test_application_delete_dissolve import _app, _edge, _grid_face, _grid_vertex, _select
from tests.test_symmetric_ops import make_app, plus_x_quad

V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE
TEST_KEY = Input("key", "f12")
CTRL_Z, CTRL_Y = Input("key", "z", frozenset({"ctrl"})), Input("key", "y", frozenset({"ctrl"}))
TOL = 1e-12


def add_layers(mesh: Mesh, seed: int = 0) -> list:
    """Two dense layers and a sparse one (every third vertex). On a mesh with a symmetry definition the
    values are mirror images: the partner of a vertex gets the X-mirror of its value, a seam vertex an
    x component of 0 (the symmetric fixtures are all X-symmetric)."""
    rng = random.Random(seed)
    partners = {}
    if mesh.symmetry_definition is not None:
        from mirai.symmetry import vertex_correspondence

        partners = {v: getattr(c, "partner", None) for v, c in vertex_correspondence(mesh).items()}
    lids = []
    for i, name in enumerate(("Smile", "Blink", "Brow")):
        lid = mesh.add_point_layer(PointLayerInfo(name))
        lids.append(lid)
        for v in sorted(mesh.all_vertex_ids(), key=int):
            if i == 2 and int(v) % 3:
                continue
            partner = partners.get(v)
            if partners and partner is not None and int(partner) < int(v):
                continue  # set with its partner
            value = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            if partner == v:
                value = (0.0, value[1], value[2])
            mesh.set_layer_value(lid, v, value)
            if partner is not None and partner != v:
                mesh.set_layer_value(lid, partner, (-value[0], value[1], value[2]))
    return lids


def _press(app, command: str) -> bool:
    app.bindings.bind(TEST_KEY, command)
    return app.key_press(TEST_KEY)


def _layers(mesh: Mesh) -> dict:
    return {lid: dict(mesh.layer_items(lid)) for lid in mesh.point_layer_ids()}


def _close(a, b, tol=TOL) -> bool:
    return max(abs(x - y) for x, y in zip(a, b)) <= tol


def _mirror(p):
    return (-p[0], p[1], p[2])


# -- rules ---------------------------------------------------------------------------------------------


def midpoint_rule(ref: Mesh, mesh: Mesh, info) -> int:
    """Every new vertex is the midpoint of a session-start edge (a, b): value = a·0.5 + b·0.5 per
    component, the position's own expression (bit-exact)."""
    mids = {}
    for e in ref.all_edge_ids():
        a, b = ref.edge_vertices(e)
        pa, pb = ref.vertex_position(a), ref.vertex_position(b)
        mids[tuple(x * 0.5 + y * 0.5 for x, y in zip(pa, pb))] = (a, b)
    new = [v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)]
    for v in new:
        a, b = mids[tuple(mesh.vertex_position(v))]
        for lid in mesh.point_layer_ids():
            da, db = ref.layer_value(lid, a), ref.layer_value(lid, b)
            assert mesh.layer_value(lid, v) == tuple(x * 0.5 + y * 0.5 for x, y in zip(da, db)), (v, lid)
    return len(new)


def collapse_rule(ref: Mesh, mesh: Mesh, info) -> int:
    """Each survivor gets the component mean of its group's original values (H3, `_centroid`'s
    arithmetic). A group = a moved survivor plus the removed vertices reachable from it over removed
    vertices (the fixtures collapse separate edges)."""
    removed = {v for v in ref.all_vertex_ids() if not mesh.is_valid_vertex(v)}
    assert removed
    assert all(ref.is_valid_vertex(v) for v in mesh.all_vertex_ids()), "Collapse created a vertex"
    moved = [v for v in mesh.all_vertex_ids() if tuple(mesh.vertex_position(v)) != tuple(ref.vertex_position(v))]
    survivors, covered = 0, set()
    for s in moved:
        group, todo = {s}, [s]
        while todo:
            u = todo.pop()
            for e in ref.vertex_edges(u):
                w = next(x for x in ref.edge_vertices(e) if x != u)
                if w in removed and w not in group:
                    group.add(w)
                    todo.append(w)
        assert len(group) > 1, s
        covered |= group
        for lid in mesh.point_layer_ids():
            values = [ref.layer_value(lid, v) for v in sorted(group, key=int)]
            n = len(values)
            mean = tuple(sum(p[k] for p in values) / n for k in range(3))
            assert mesh.layer_value(lid, s) == mean, (s, lid)
        survivors += 1
    assert removed <= covered
    return survivors


def copy_rule(ref: Mesh, mesh: Mesh, info) -> int:
    """Extrude: every cap vertex is a copy of its source vertex (bit-exact), walls create none."""
    old_to_new = info["old_to_new"]
    assert old_to_new
    for old, new in old_to_new.items():
        for lid in mesh.point_layer_ids():
            assert mesh.layer_value(lid, new) == ref.layer_value(lid, old), (old, new, lid)
    created = {v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)}
    assert created == set(old_to_new.values())
    return len(created)


def source_copy_rule(ref: Mesh, mesh: Mesh, info) -> int:
    """Bevel: every new vertex is a copy of the vertex it grew from (bit-exact); several may share one."""
    sources = info["sources"]
    assert sources
    for new, old in sources.items():
        for lid in mesh.point_layer_ids():
            assert mesh.layer_value(lid, new) == ref.layer_value(lid, old), (old, new, lid)
    created = {v for v in mesh.all_vertex_ids() if not ref.is_valid_vertex(v)}
    assert created == set(sources)
    return len(created)


def knife_rule(ref: Mesh, mesh: Mesh, info) -> int:
    from tests.test_layer_knife import check_values

    counts = check_values(ref, mesh, info["path"], mirror=_mirror if info["symmetric"] else None)
    assert counts["face"] >= 1 and counts["edge"] >= 1, counts
    return counts["face"] + counts["edge"]


# -- fixtures: each prepares the selection (or the session) and returns (command, info) -----------------


def _plain_split(app):
    mesh = app.scene.mesh
    _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2))})
    return commands.CONNECT


def _sym_split(app):
    mesh = app.scene.mesh
    a, b, _, _ = mesh.face_vertices(plus_x_quad(mesh, touching_seam=False))
    _select(app, E, {_edge(mesh, a, b)})
    return commands.CONNECT


def _plain_edge_connect(app):
    mesh = app.scene.mesh
    _select(app, E, {
        _edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2)),
        _edge(mesh, _grid_vertex(app, 2, 1), _grid_vertex(app, 2, 2)),
    })
    return commands.CONNECT


def _sym_edge_connect(app):
    mesh = app.scene.mesh
    a, b, c, d = mesh.face_vertices(plus_x_quad(mesh, touching_seam=False))
    _select(app, E, {_edge(mesh, a, b), _edge(mesh, c, d)})
    return commands.CONNECT


def _plain_loop_insert(app):
    mesh = app.scene.mesh
    _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 2, 1))})
    return commands.LOOP_INSERT


def _sym_loop_insert(app):
    mesh = app.scene.mesh
    a, b, _, _ = mesh.face_vertices(plus_x_quad(mesh, touching_seam=False))
    _select(app, E, {_edge(mesh, a, b)})
    return commands.LOOP_INSERT


def _plain_collapse(app):
    mesh = app.scene.mesh
    _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 2, 1))})
    return commands.COLLAPSE


def _plain_collapse_face(app):
    _select(app, F, {_grid_face(app, 1, 1)})
    return commands.COLLAPSE


def _sym_collapse(app):
    mesh = app.scene.mesh
    a, b, _, _ = mesh.face_vertices(plus_x_quad(mesh, touching_seam=False))
    _select(app, E, {_edge(mesh, a, b)})
    return commands.COLLAPSE


def _plain_extrude(app):
    _select(app, F, {_grid_face(app, 1, 1)})
    return commands.EXTRUDE


def _sym_extrude(app):
    _select(app, F, {plus_x_quad(app.scene.mesh, touching_seam=False)})
    return commands.EXTRUDE


def _plain_inset(app):
    _select(app, F, {_grid_face(app, 1, 1)})
    return commands.INSET


def _sym_inset(app):
    _select(app, F, {plus_x_quad(app.scene.mesh, touching_seam=False)})
    return commands.INSET


def _plain_bevel(app):
    mesh = app.scene.mesh
    _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2))})
    return commands.BEVEL


def _sym_bevel(app):
    mesh = app.scene.mesh
    a, b, _, _ = mesh.face_vertices(plus_x_quad(mesh, touching_seam=False))
    _select(app, E, {_edge(mesh, a, b)})
    return commands.BEVEL


#: key -> (plain fixture, symmetric fixture, rule). The fixtures build their own app.
RULE_FIXTURES = {
    CContext.SPLIT: (_plain_split, _sym_split, midpoint_rule),
    CContext.EDGE_CONNECT: (_plain_edge_connect, _sym_edge_connect, midpoint_rule),
    commands.LOOP_INSERT: (_plain_loop_insert, _sym_loop_insert, midpoint_rule),
    commands.COLLAPSE: (_plain_collapse, _sym_collapse, collapse_rule),
    commands.EXTRUDE: (_plain_extrude, _sym_extrude, copy_rule),
    commands.INSET: (_plain_inset, _sym_inset, copy_rule),
    commands.BEVEL: (_plain_bevel, _sym_bevel, source_copy_rule),
}
#: Declared entries whose rule test runs through other fixtures here: the Knife (real picks, below)
#: and mirror copy (a new mesh, below).
OTHER_FIXTURES = {CContext.KNIFE: "test_knife_cuts_a_layered_mesh_by_its_rule",
                  "mirror_copy": "test_mirror_copy_carries_the_layers_through_the_index_map"}


def _run(app, command: str, info: dict) -> None:
    history = len(app.history)
    assert _press(app, command), app.status_message
    if app.interaction_owner == "transform":  # Extrude / Inset: hold, drag, release
        for _ in range(4):
            app.pointer_motion(400, 300, 20.0, -15.0)
        if isinstance(app._gestures.session, OffsetGesture):  # Inset / Bevel: each new vertex is keyed first by the vertex it copies
            info["sources"] = {new: key[0] for new, key in app._gestures.session.result.keys.items()}
            info["old_to_new"] = {old: new for new, old in info["sources"].items()}
        else:
            info["old_to_new"] = dict(app.tool_manager.active_tool._old_to_new)
        app.key_release(TEST_KEY)
    assert len(app.history) == history + 1, app.status_message


def _check_mirror(ref: Mesh, mesh: Mesh) -> int:
    """Every vertex the operation created or moved on the +X side has a partner at the mirror
    position whose values are the mirrored values (up to rounding)."""
    by_pos = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
    pairs = 0
    for v in mesh.all_vertex_ids():
        pos = tuple(mesh.vertex_position(v))
        if pos[0] <= 0.0 or (ref.is_valid_vertex(v) and tuple(ref.vertex_position(v)) == pos):
            continue
        partner = by_pos.get(_mirror(pos))
        assert partner is not None, pos
        pairs += 1
        for lid in mesh.point_layer_ids():
            assert _close(mesh.layer_value(lid, partner), _mirror(mesh.layer_value(lid, v))), (v, partner, lid)
    return pairs


def _assert_others_unchanged(ref: Mesh, mesh: Mesh, touched: set) -> None:
    for lid in mesh.point_layer_ids():
        for v in mesh.all_vertex_ids():
            if ref.is_valid_vertex(v) and v not in touched:
                assert mesh.layer_value(lid, v) == ref.layer_value(lid, v), (v, lid)


def _assert_undo_redo_exact(app, before: dict) -> None:
    mesh = app.scene.mesh
    after = mesh.export_state()
    assert app.key_press(CTRL_Z)
    undone = mesh.export_state()
    for k, v in before.items():
        if k.endswith("_counter"):
            assert undone[k] >= v
        else:
            assert undone[k] == v, k
    assert app.key_press(CTRL_Y)
    assert mesh.export_state() == after


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
@pytest.mark.parametrize("key", list(RULE_FIXTURES), ids=str)
def test_declared_phase5_operation_follows_its_rule(key, symmetric):
    plain, sym, rule = RULE_FIXTURES[key]
    app = make_app("subd_cube") if symmetric else _app(3)
    command = (sym if symmetric else plain)(app)
    mesh = app.scene.mesh
    add_layers(mesh, seed=sum(map(ord, str(key))))  # stable across runs (str hashes are salted)
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    info: dict = {}
    _run(app, command, info)
    assert rule(ref, mesh, info) >= 1
    moved = {v for v in mesh.all_vertex_ids() if ref.is_valid_vertex(v)
             and tuple(mesh.vertex_position(v)) != tuple(ref.vertex_position(v))}
    _assert_others_unchanged(ref, mesh, moved if key == commands.COLLAPSE else set())
    if symmetric:
        assert _check_mirror(ref, mesh) >= 1
    assert_layer_invariants(mesh)
    _assert_undo_redo_exact(app, before)


def test_face_collapse_averages_the_whole_group():
    app = _app(3)
    command = _plain_collapse_face(app)
    mesh = app.scene.mesh
    add_layers(mesh, 3)
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    _run(app, command, {})
    assert collapse_rule(ref, mesh, {}) == 1
    _assert_undo_redo_exact(app, before)


# -- the Knife, end to end with real picks ------------------------------------------------------------------


def _knife_app(symmetric: bool):
    import itertools

    from tests.test_application_knife import HEIGHT, WIDTH

    from mirai.application import Application

    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.knife_clock = itertools.count(0.0, 10.0).__next__
    mesh = app.scene.mesh
    # a warped +X face (non-planar quad): the hit triangle matters
    top = max((v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] > 0),
              key=lambda v: (mesh.vertex_position(v)[1] + mesh.vertex_position(v)[2], int(v)))
    x, y, z = mesh.vertex_position(top)
    mesh.set_vertex_position(top, (x + 0.3, y, z))
    if symmetric:
        from core import SymmetryDefinition
        from mirai.symmetry_axis import AXIS_NORMALS, ORIGIN

        partner = next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) == (-x, y, z))
        mesh.set_vertex_position(partner, (-x - 0.3, y, z))
        mesh.symmetry_definition = SymmetryDefinition(ORIGIN, AXIS_NORMALS["X"], frozenset())
    app.viewport.on_topology_changed()
    return app


def _screen_of(app, p):
    from tests.test_application_knife import HEIGHT, WIDTH

    return app.camera.project_to_screen(p, WIDTH, HEIGHT)


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
def test_knife_cuts_a_layered_mesh_by_its_rule(symmetric):
    """C with nothing selected on a layered mesh starts the session (no lock any more); edge points
    and interior points picked on the warped +X face; Enter commits one Undo step. Every interior
    record carries its origin from the pick - the barycentric weights of the hit triangle - and the
    new point lies on the target's drawn surface (p + d on the displaced hit triangle)."""
    from mirai.viewport.picking import triangle_origin
    from tests.test_application_knife import ENTER, LMB
    from viewport.derived import triangulate_mesh_face

    app = _knife_app(symmetric)
    mesh = app.scene.mesh
    add_layers(mesh, 21)
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    face = max(mesh.all_face_ids(), key=lambda f: min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)))  # +X
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
    assert app.knife_active
    clicks = [on_edge(edges[0], 0.35), inside(0.45, 0.4), inside(0.6, 0.65), on_edge(edges[2], 0.4)]
    for p in clicks:
        sx, sy = _screen_of(app, p)
        app.pointer_motion(sx, sy)
        app.pointer_press(LMB, sx, sy)
        assert app.pointer_release("LEFT", sx, sy), app.status_message
    path = [dict(p) for p in app._knife.tool.path]
    interior = [p for p in path if p["kind"] == "face"]
    assert len(interior) == 2 and all("origin" in p for p in interior)
    for p in interior:  # the origin is the hit triangle's barycentrics; p + d is on the drawn target
        tri = tuple(v for v, _ in p["origin"])
        assert tri in [tuple(t) for t in triangulate_mesh_face(ref, p["face_id"])]
        assert p["origin"] == triangle_origin(ref, tri, p["position"])
    history = len(app.history)
    assert app.key_press(ENTER)
    assert len(app.history) == history + 1, app.status_message
    knife_rule(ref, mesh, {"path": path, "symmetric": symmetric})
    by_pos = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
    for p in interior:
        v = by_pos[tuple(p["position"])]
        tri = [v_ for v_, _ in p["origin"]]
        for lid in mesh.point_layer_ids():
            q = [tuple(a + b for a, b in zip(ref.vertex_position(c), ref.layer_value(lid, c))) for c in tri]
            x = tuple(a + b for a, b in zip(mesh.vertex_position(v), mesh.layer_value(lid, v)))
            n = _cross(_sub(q[1], q[0]), _sub(q[2], q[0]))
            assert abs(_dot(_sub(x, q[0]), n)) / math.sqrt(_dot(n, n)) < 1e-12
    if symmetric:
        assert _check_mirror(ref, mesh) >= 4
    assert_layer_invariants(mesh)
    _assert_undo_redo_exact(app, before)


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


# -- mirror copy --------------------------------------------------------------------------------------


@pytest.mark.parametrize("symmetric", [False, True], ids=["plain", "symmetric"])
def test_mirror_copy_carries_the_layers_through_the_index_map(symmetric):
    """Mirror copy of a layered source (AD-025 §4.3): the new mesh has the same layers in order with
    names and rules, each value at the copy of its vertex mapped v -> H·v, bit-exact for the axis
    plane; the source is untouched; Undo removes the copy."""
    from tests.test_mirror_pairs import _placed_sphere

    if symmetric:
        app = make_app("subd_cube")
        source = app.scene.edit_object
    else:
        app = _app()
        source = _placed_sphere(app)
    add_layers(source.mesh, 31)
    state = source.mesh.export_state()
    app.key_press(Input("key", "4"))
    app.selection.objects = {source.id}
    history = len(app.history)
    copy = app.mirror_copy("X")
    assert copy is not None, app.status_message
    assert len(app.history) == history + 1
    assert source.mesh.export_state() == state
    src, dst = source.mesh, copy.mesh
    assert [src.point_layer_info(l) for l in src.point_layer_ids()] == [dst.point_layer_info(l) for l in dst.point_layer_ids()]
    index = {v: i for i, v in enumerate(sorted(src.all_vertex_ids()))}
    new_ids = sorted(dst.all_vertex_ids())
    for ls, ld in zip(src.point_layer_ids(), dst.point_layer_ids()):
        expected = {new_ids[index[v]]: (-x, y, z) for v, (x, y, z) in src.layer_items(ls)}
        assert dict(dst.layer_items(ld)) == {v: d for v, d in expected.items() if d != (0.0, 0.0, 0.0)}
        for v, (x, y, z) in src.layer_items(ls):
            got = dst.layer_value(ld, new_ids[index[v]])
            assert math.copysign(1.0, got[0]) == -math.copysign(1.0, x) or x == 0.0
    for v in src.all_vertex_ids():  # positions and offsets mirror alike
        assert tuple(dst.vertex_position(new_ids[index[v]])) == _mirror(src.vertex_position(v))
    assert_layer_invariants(dst)
    assert app.key_press(CTRL_Z)
    assert copy.id not in app.scene.objects


# -- the editing view and the mix follow a base topology edit (AD-025 §15, Phase 5 item 6) ----------------


@pytest.mark.parametrize("command", [commands.LOOP_INSERT, commands.COLLAPSE, commands.EXTRUDE, commands.CONNECT])
def test_the_mix_and_the_view_follow_a_topology_edit_on_the_base(command):
    """A target dialled in at 60 %: a Phase 5 operation on the base rebuilds the shown mix on the new
    topology (every point at b + 0.6·d, the new ones with their interpolated d), and the editing view
    opened afterwards is b + d on the new topology. Topology still runs on the base only (the view
    refuses it: `test_morph_targets.test_topology_and_base_only_commands_are_refused_on_the_view`)."""
    from mirai import morph_targets

    app = _app(3)
    assert app.key_press(Input("key", "n", frozenset({"ctrl"}))), app.status_message
    base = app.scene.edit_object
    mesh = base.mesh
    lid = morph_targets.morph_target(mesh)
    rng = random.Random(5)
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(lid, v, (rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), rng.uniform(0, 0.3)))
    app.set_morph_weight(60)
    app.update_viewport(0.0)
    if command == commands.CONNECT:
        _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 1, 2))})
    elif command == commands.EXTRUDE:
        _select(app, F, {_grid_face(app, 1, 1)})
    else:
        _select(app, E, {_edge(mesh, _grid_vertex(app, 1, 1), _grid_vertex(app, 2, 1))})
    vertices = set(mesh.all_vertex_ids())
    before_surface = app.morph.provider.surface_mesh
    _run(app, command, {})
    assert set(mesh.all_vertex_ids()) != vertices

    def assert_mix():
        app.update_viewport(0.0)
        surface = app.morph.provider.surface_mesh
        rm = app.viewport.surface_render_mesh
        # patched in place (§16): the same surface mesh and RenderMesh, its triangles on the new faces
        assert surface is before_surface and rm.mesh is surface
        assert {f: surface.face_vertices(f) for f in surface.all_face_ids()} == {
            f: mesh.face_vertices(f) for f in mesh.all_face_ids()}
        assert set(rm._face_triangles) == set(mesh.all_face_ids())
        for v in mesh.all_vertex_ids():
            b, d = mesh.vertex_position(v), mesh.layer_value(lid, v)
            assert tuple(surface.vertex_position(v)) == morph_targets.blend(b, d, 60), v

    assert_mix()
    assert app.key_press(CTRL_Z)
    assert set(mesh.all_vertex_ids()) == vertices
    assert_mix()
    assert app.key_press(CTRL_Y)
    assert_mix()
    assert app.key_press(Input("key", "tab")), app.status_message
    view = app._morph.view.view_mesh
    for v in mesh.all_vertex_ids():
        b, d = mesh.vertex_position(v), mesh.layer_value(lid, v)
        assert tuple(view.vertex_position(v)) == (b[0] + d[0], b[1] + d[1], b[2] + d[2])
    assert app.key_press(Input("key", "tab"))


def test_a_kept_point_moved_away_and_back_with_a_topology_edit_keeps_its_mix():
    """One step that moves a point with an offset and puts it back, and splits an edge elsewhere: the
    point is in the journal but its record did not change - the in-place patch keeps its mixed position."""
    from mirai import morph_targets

    app = _app(3)
    assert app.key_press(Input("key", "n", frozenset({"ctrl"})))
    mesh = app.scene.mesh
    lid = morph_targets.morph_target(mesh)
    v = _grid_vertex(app, 1, 1)
    mesh.set_layer_value(lid, v, (0.1, 0.2, 0.3))
    app.set_morph_weight(100)
    app.update_viewport(0.0)
    edge = _edge(mesh, _grid_vertex(app, 3, 2), _grid_vertex(app, 3, 3))
    p = mesh.vertex_position(v)

    def step():
        mesh.set_vertex_position(v, (9.0, 9.0, 9.0))
        mesh.set_vertex_position(v, p)
        mesh.split_edge(edge)

    assert app.apply_mesh_change("away, back and split", step)
    app.update_viewport(0.0)
    surface = app.morph.provider.surface_mesh
    assert tuple(surface.vertex_position(v)) == morph_targets.blend(p, (0.1, 0.2, 0.3), 100)


def test_the_entry_surface_beside_the_view_is_patched_in_place():
    """H7-E: the base shown beside the editing view takes a topology change of the base in place too
    (`entry_topology_changed`)."""
    from mirai import morph_targets

    app = _app(3)
    assert app.key_press(Input("key", "n", frozenset({"ctrl"})))
    base = app.scene.edit_object
    mesh = base.mesh
    lid = morph_targets.morph_target(mesh)
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(lid, v, (0.0, 0.0, 0.1))
    app.set_morph_weight(50)
    assert app.key_press(Input("key", "tab"))
    app.update_viewport(0.0)
    rm = app.viewport.entry_surface_render_meshes[base.id]
    entry = app.morph.provider.entry_surfaces[base.id]
    face = _grid_face(app, 1, 1)
    a, _, c, _ = mesh.face_vertices(face)
    mesh.split_face(face, a, c)  # two new faces
    app.update_viewport(0.0)
    assert app.morph.provider.entry_surfaces[base.id] is entry
    assert app.viewport.entry_surface_render_meshes[base.id] is rm
    assert set(rm._face_triangles) == set(mesh.all_face_ids())
    assert sorted(entry.all_vertex_ids()) == sorted(mesh.all_vertex_ids())
