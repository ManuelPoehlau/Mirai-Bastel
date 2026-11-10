"""AD-031 P6: symmetric Weld and Bridge (decided P6-a…P6-d, Manu 2026-11-10) - `symmetric_ops.plan_symmetric_weld` /
`coordinate_weld` / `plan_symmetric_bridge` / `coordinate_bridge` through `Application.weld_vertices` /
`bridge_borders`.

Weld (P6-a/b): the selection and its image (every point at the mirror position) weld as whole groups on both sides in
one step; the pairs stay exact (mirror snap, projection onto the plane); coincident (AMBIGUOUS) points weld - one
selected point takes its twin and their mirror images along; a seam doubled by Detach + Attach is zipped shut with
symmetry on and the seam is whole again (Re-Symmetrize plans); a group across the plane lands on it and the edge between
two such points joins the seam; refusals (no image, plane not exact, the declaration removed, a result that would not be
mirror-complete) change nothing. Bridge (P6-c): (1) two borders on one side bridged together with their mirror image -
the ears of the P5 acceptance test in one step with symmetry on; (2) two borders across the plane joined by one
mirror-symmetric bridge whose rungs on the plane join the seam, refused when no mirror-symmetric pairing exists; (3)
borders that are each other's image, (4) one across the plane and one not, a closed image, the declaration removed -
refused, nothing changed. Every successful step: one Undo step, exact Undo / Redo (the definition included), the
invariants, state VALID. The layer rules (P6-d) are the symmetric fixtures in `test_layer_topology_ops.py` /
`test_weights_topology_ops.py`."""

from __future__ import annotations

import math
import random
from types import MappingProxyType

import pytest

import tests._bootstrap  # noqa: F401
from core import Mesh, SelectionMode, SymmetryDefinition
from mirai import symmetry_declarations
from mirai.interaction import commands
from mirai.resymmetrize import plan_resymmetrize
from mirai.symmetric_ops import (
    TEXT_BRIDGE_ACROSS,
    TEXT_BRIDGE_IMAGE_CLOSED,
    TEXT_BRIDGE_MIXED,
    TEXT_BRIDGE_NOT_MIRRORED,
    TEXT_DELTA,
    TEXT_NON_EXACT_PLANE,
    TEXT_UNPAIRED,
)
from mirai.symmetry import SymmetryState, symmetry_state
from mirai.symmetry_axis import AXIS_NORMALS, ORIGIN, definition_for_axis
from mirai.symmetry_coordination import SymmetryIndex
from mirai.symmetry_topology import topological_sides
from mirai.topology.border import border_loops, cap_winding
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_bridge import CTRL_Y, CTRL_Z, _app, _assert_oriented, _ear, _select_points, _snapshot
from tests.test_symmetric_ops import make_app, plus_x_quad

T = 0.001
F = SelectionMode.FACE


def _body(mesh) -> dict:
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")}


def _mirror(p):
    return (-p[0], p[1], p[2])


def _assert_mirror_exact(mesh: Mesh) -> None:
    """Every point has a point at its exact mirror position (the pairs Weld's snap keeps exact)."""
    positions = {tuple(mesh.vertex_position(v)) for v in mesh.all_vertex_ids()}
    assert all(_mirror(p) in positions for p in positions)


def _undo_redo_exact(app, before: dict) -> None:
    mesh = app.scene.mesh
    after = _body(mesh)
    assert app.key_press(CTRL_Z), app.status_message
    assert _body(mesh) == before
    assert app.key_press(CTRL_Y), app.status_message
    assert _body(mesh) == after


def _seam_is_every_edge_on_the_plane(mesh: Mesh) -> None:
    on_plane = {e for e in mesh.all_edge_ids() if all(mesh.vertex_position(v)[0] == 0.0 for v in mesh.edge_vertices(e))}
    assert set(mesh.symmetry_definition.seam_edges) == on_plane


# -- Weld --------------------------------------------------------------------------------------------------------------


def sym_soup(jitter: float = 0.0002, seed: int = 0) -> Mesh:
    """A 4 x 2 grid of quads across the plane x = 0 with every face's points unshared: the +X quads jittered by up to
    `jitter` (points on the plane only in y and z), the -X quads their exact mirror images. Welded, it is the shared 5 x 3
    grid. `jitter` 0: the doubled points off the plane coincide (AMBIGUOUS before the weld)."""
    rng = random.Random(seed)
    mesh = Mesh()
    for i in range(2):
        for j in range(2):
            x, y = float(i), float(j)
            pts = []
            for cx, cy in ((x, y), (x + 1, y), (x + 1, y + 1), (x, y + 1)):
                jx = rng.uniform(-jitter, jitter) if cx != 0.0 else 0.0
                pts.append((cx + jx, cy + rng.uniform(-jitter, jitter), rng.uniform(-jitter, jitter)))
            mesh.add_face([mesh.add_vertex(p) for p in pts])
            mesh.add_face([mesh.add_vertex((-p[0] if p[0] else 0.0, p[1], p[2])) for p in pts][::-1])
    return mesh


def _soup_app(jitter: float = 0.0002):
    app = _app(sym_soup(jitter))
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    return app, mesh


def test_symmetric_weld_welds_the_image_too_and_keeps_the_pairs_exact():
    """P6-a: the +X points only are selected; their mirror images weld in the same step, the pairs stay exact."""
    app, mesh = _soup_app()
    assert symmetry_state(mesh) is SymmetryState.VALID
    before = _body(mesh)
    _select_points(app, [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] > 0.5])
    plan = app.weld_plan(T)
    assert plan.refusal is None and len(plan.groups) == 8 and plan.points == 20  # 4 groups on each side
    history = len(app.history)
    assert app.weld_vertices(T), app.status_message
    assert app.status_message.startswith("Weld: 20 points into 8 (distance 0.001, mirrored)")
    assert len(app.history) == history + 1
    assert len(mesh.all_vertex_ids()) == 20
    assert symmetry_state(mesh) is SymmetryState.VALID
    _assert_mirror_exact(mesh)
    assert_mesh_invariants(mesh)
    _undo_redo_exact(app, before)


def test_the_whole_soup_welds_into_the_grid_and_the_seam_follows():
    """P6-a/b: everything selected - the 5 x 3 grid; the seam doubled on the plane became one column of edges, the dead
    seam ids are gone and the merged edges on the plane are the seam (Shift+S's rule)."""
    app, mesh = _soup_app()
    before = _body(mesh)
    _select_points(app, mesh.all_vertex_ids())
    assert app.weld_vertices(T), app.status_message
    assert (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())) == (15, 22, 8)
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert len(mesh.symmetry_definition.seam_edges) == 2
    _seam_is_every_edge_on_the_plane(mesh)
    _assert_mirror_exact(mesh)
    assert_mesh_invariants(mesh)
    assert topological_sides(mesh).component_count == 2
    _undo_redo_exact(app, before)


def test_coincident_points_weld_one_selected_point_takes_its_twin_and_their_images_along():
    """P6-a, the documented P6 question: doubled points off the plane coincide - each has two mirror candidates
    (AMBIGUOUS). One selected point: its twin (the image of its image) and both mirror points weld, two groups."""
    app, mesh = _soup_app(jitter=0.0)
    assert symmetry_state(mesh) is SymmetryState.AMBIGUOUS
    position = (1.0, 1.0, 0.0)  # the centre of the +X half: four coincident points, and four at its mirror position
    point = min((v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) == position), key=int)
    _select_points(app, {point})
    plan = app.weld_plan(T)
    assert plan.refusal is None and [len(g) for g in plan.groups] == [4, 4]
    assert app.weld_vertices(T), app.status_message
    assert len(mesh.all_vertex_ids()) == 32 - 6
    _select_points(app, mesh.all_vertex_ids())
    assert app.weld_vertices(T), app.status_message
    assert len(mesh.all_vertex_ids()) == 15
    assert symmetry_state(mesh) is SymmetryState.VALID
    _assert_mirror_exact(mesh)
    assert_mesh_invariants(mesh)


def test_a_seam_doubled_by_detach_and_attach_is_welded_with_symmetry_on():
    """The case P6 is for: the +X half of a symmetric cube detached and attached back (symmetry off), the definition
    derived again (Shift+S: both copies of the seam are on the plane); Weld with symmetry on and the default distance
    zips it shut - the cube's counts, the cube's seam, VALID, Re-Symmetrize plans again."""
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    counts = (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids()))
    seam = len(mesh.symmetry_definition.seam_edges)
    mesh.symmetry_definition = None
    half = [f for f in mesh.all_face_ids() if sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0]
    app.dispatch_command(commands.SET_FACE_MODE)
    app.selection.faces = set(half)
    objects = set(app.scene.objects)
    assert app.detach_faces(), app.status_message
    (part,) = set(app.scene.objects) - objects
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = {part}
    assert app.attach_objects(), app.status_message
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert symmetry_state(mesh) is SymmetryState.VALID  # both copies of the seam are seam points
    doubled = len(mesh.all_vertex_ids()) - counts[0]
    assert doubled > 0
    _select_points(app, [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] >= 0.0])
    assert app.weld_vertices(), app.status_message
    assert f"{2 * doubled} points into {doubled}" in app.status_message
    assert (len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())) == counts
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert len(mesh.symmetry_definition.seam_edges) == seam
    _seam_is_every_edge_on_the_plane(mesh)
    assert_mesh_invariants(mesh)
    source = next(v for v, s in sorted(topological_sides(mesh).vertex_side.items()) if s == 1)
    assert plan_resymmetrize(mesh, source) is not None


def _across(triangle: bool = False) -> Mesh:
    """A quad (or triangle) on each side whose inner points lie 0.0003 from the plane: each inner point and its image are
    one group across the plane."""
    mesh = Mesh()
    d = 0.0003
    right = [(d, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0)] + ([] if triangle else [(d, 1.0, 0.0)])
    mesh.add_face([mesh.add_vertex(p) for p in right])
    mesh.add_face([mesh.add_vertex(_mirror(p)) for p in right][::-1])
    return mesh


def test_a_group_across_the_plane_lands_on_it_and_its_edge_joins_the_seam():
    """P6-a: a group around the plane is projected onto it; P6-b: the edge between two welded points on the plane joins
    the seam (the definition had none) - VALID, two components."""
    app = _app(_across())
    mesh = app.scene.mesh
    mesh.symmetry_definition = SymmetryDefinition(ORIGIN, AXIS_NORMALS["X"], frozenset())
    assert symmetry_state(mesh) is SymmetryState.VALID
    before = _body(mesh)
    _select_points(app, [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] > 0])
    assert app.weld_vertices(T), app.status_message
    assert len(mesh.all_vertex_ids()) == 6
    on_plane = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] == 0.0]
    assert len(on_plane) == 2
    (edge,) = mesh.symmetry_definition.seam_edges
    assert set(mesh.edge_vertices(edge)) == set(on_plane)
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert topological_sides(mesh).component_count == 2
    _undo_redo_exact(app, before)


def _weld_refusal(case: str):
    if case == "delta":  # one point lands on the plane without an edge there: it loses its partner
        app = _app(_across(triangle=True))
        mesh = app.scene.mesh
        mesh.symmetry_definition = SymmetryDefinition(ORIGIN, AXIS_NORMALS["X"], frozenset())
        _select_points(app, mesh.all_vertex_ids())
        return app, TEXT_DELTA
    app, mesh = _soup_app()
    _select_points(app, mesh.all_vertex_ids())
    if case == "unpaired":
        stray = mesh.add_vertex((3.0, 0.5, 0.0))
        app.selection.vertices = set(app.selection.vertices) | {stray}
        return app, TEXT_UNPAIRED
    if case == "plane not exact":
        mesh.symmetry_definition = SymmetryDefinition((0.5, 0.0, 0.0), AXIS_NORMALS["X"], frozenset())
        return app, TEXT_NON_EXACT_PLANE
    raise AssertionError(case)


@pytest.mark.parametrize("case", ["unpaired", "plane not exact", "delta"])
def test_symmetric_weld_refusals_change_nothing(case):
    app, text = _weld_refusal(case)
    before = _snapshot(app)
    if case != "delta":  # the delta is judged after the change (and rolled back); the others are refused by the plan
        assert app.weld_plan(T).refusal == text
    assert app.weld_vertices(T) is False
    assert app.status_message == text
    assert _snapshot(app) == before


def _undeclared(monkeypatch, table: str) -> None:
    monkeypatch.setattr(symmetry_declarations, table, MappingProxyType({}))


def test_without_its_declaration_weld_is_refused_under_a_definition(monkeypatch):
    """Fail-closed (D-b): the table entry is the switch; without it Weld refuses under a definition, nothing changes."""
    _undeclared(monkeypatch, "WELD_COORDINATORS")
    app, mesh = _soup_app()
    _select_points(app, mesh.all_vertex_ids())
    before = _snapshot(app)
    assert app.weld_vertices(T) is False and "not with symmetry on" in app.status_message
    assert app.dispatch_command(commands.WELD) is False
    assert _snapshot(app) == before


# -- Bridge ------------------------------------------------------------------------------------------------------------


def _cube_with_two_holes():
    """subd_cube (X definition) with a +X quad and its mirror deleted: (app, +X hole in Cap's winding, -X hole corners)."""
    app = make_app("subd_cube")
    mesh = app.scene.mesh
    quad = plus_x_quad(mesh, touching_seam=False)
    position = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
    image = {position[_mirror(mesh.vertex_position(v))] for v in mesh.face_vertices(quad)}
    mirror = next(f for f in mesh.all_face_ids() if set(mesh.face_vertices(f)) == image)
    corners, mirrored = mesh.face_vertices(quad), mesh.face_vertices(mirror)
    mesh.delete_faces([quad, mirror])
    loop = next(lp for lp in border_loops(mesh, [e for v in corners for e in mesh.vertex_edges(v)])
                if set(lp.vertices) == set(corners))
    return app, cap_winding(mesh, loop), list(mirrored)


def test_two_borders_on_one_side_are_bridged_with_their_mirror_image():
    """P6-c (1), the P5 acceptance scene with symmetry on: one point of the +X hole and one of the +X ear - both ears are
    bridged in one step (the mirror quads are the exact mirror of the plan's); VALID, the seam splits the mesh into two
    parts again and Re-Symmetrize plans; the new faces on the selection's side are selected."""
    app, hole, _ = _cube_with_two_holes()
    mesh = app.scene.mesh
    right = _ear(mesh, hole, mirror=False)
    _ear(mesh, hole, mirror=True)
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert symmetry_state(mesh) is SymmetryState.VALID and topological_sides(mesh).component_count == 4
    before = _body(mesh)
    faces = set(mesh.all_face_ids())
    _select_points(app, {hole[0], right[0]})
    plan = app.bridge_plan()
    assert plan.refusal is None and len(plan.quads) == 8 and len(plan.loops) == 4
    history = len(app.history)
    assert app.bridge_borders(), app.status_message
    assert app.status_message == (
        "Bridge: 8 quads (mirrored) between two borders of 4 points on each side (no UVs, no group)"
    )
    assert len(app.history) == history + 1
    new = set(mesh.all_face_ids()) - faces
    assert len(new) == 8
    index = SymmetryIndex(mesh)
    assert {index.face_partner(f) for f in new} == new  # every new quad has its mirror quad among them
    assert app.selection.mode is F and len(app.selection.faces) == 4
    assert all(sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0 for f in app.selection.faces)
    assert_mesh_invariants(mesh)
    _assert_oriented(mesh)
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert topological_sides(mesh).component_count == 2
    source = next(v for v, s in sorted(topological_sides(mesh).vertex_side.items()) if s == 1)
    assert plan_resymmetrize(mesh, source) is not None
    _undo_redo_exact(app, before)


def test_the_plan_is_the_same_when_both_sides_are_selected():
    """A mirror pair of borders counts once: selecting the -X ear and hole too changes nothing in the plan."""
    app, hole, mirrored = _cube_with_two_holes()
    mesh = app.scene.mesh
    right = _ear(mesh, hole, mirror=False)
    left = _ear(mesh, hole, mirror=True)
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    _select_points(app, {hole[0], right[0]})
    one_side = app.bridge_plan()
    _select_points(app, {hole[0], right[0], mirrored[0], left[0]})
    assert app.bridge_plan() == one_side and one_side.refusal is None


def _ring(n: int, r: float, turn: float = 0.0) -> list:
    """`n` points on a circle of radius `r` in the XY plane, exact mirror images across x = 0 (`turn` rotates the circle
    before it is made exact; a turn that leaves no point on the plane leaves none)."""
    pts = [(r * math.cos(turn + 2.0 * math.pi * k / n), r * math.sin(turn + 2.0 * math.pi * k / n)) for k in range(n)]
    out = list(pts)
    for k, (x, y) in enumerate(pts):
        if abs(x) < 1e-12:
            out[k] = (0.0, y)
            continue
        if x > 0:
            m = min(range(n), key=lambda i: (pts[i][0] + x) ** 2 + (pts[i][1] - y) ** 2)
            out[m] = (-x, y)
    return out


def _annulus(mesh: Mesh, n: int, z: float, *, up: bool, turn: float = 0.0) -> list:
    inner = [mesh.add_vertex((x, y, z)) for x, y in _ring(n, 1.0, turn)]
    outer = [mesh.add_vertex((x, y, z)) for x, y in _ring(n, 2.0, turn)]
    for k in range(n):
        quad = [inner[k], outer[k], outer[(k + 1) % n], inner[(k + 1) % n]]
        mesh.add_face(quad if up else quad[::-1])
    return inner


def _rings_across(turn: float = 0.0):
    """Two rings centred on the plane (each border is its own mirror image), the top one facing up."""
    mesh = Mesh()
    bottom = _annulus(mesh, 8, 0.0, up=False)
    top = _annulus(mesh, 8, 1.0, up=True, turn=turn)
    app = _app(mesh)
    mesh = app.scene.mesh
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert symmetry_state(mesh) is SymmetryState.VALID
    return app, mesh, bottom, top


def test_two_borders_across_the_plane_get_one_mirror_symmetric_bridge():
    """P6-c (2): both borders straddle the plane - one bridge of 8 quads, mirror-symmetric (each quad's mirror is a quad
    of it); its two rungs on the plane join the seam (as Cap's split edge does), so the seam splits the tube in two."""
    app, mesh, bottom, top = _rings_across()
    seam = set(mesh.symmetry_definition.seam_edges)
    before = _body(mesh)
    faces = set(mesh.all_face_ids())
    _select_points(app, {bottom[0], top[3]})
    assert app.bridge_borders(), app.status_message
    assert app.status_message == "Bridge: 8 quads between two borders of 8 points (no UVs, no group)"
    new = set(mesh.all_face_ids()) - faces
    index = SymmetryIndex(mesh)
    assert len(new) == 8 and {index.face_partner(f) for f in new} == new
    added = set(mesh.symmetry_definition.seam_edges) - seam
    assert len(added) == 2 and all(
        set(mesh.edge_vertices(e)) & set(bottom) and set(mesh.edge_vertices(e)) & set(top) for e in added
    )
    _seam_is_every_edge_on_the_plane(mesh)
    assert symmetry_state(mesh) is SymmetryState.VALID
    assert topological_sides(mesh).component_count == 2
    assert_mesh_invariants(mesh)
    _assert_oriented(mesh)
    _undo_redo_exact(app, before)


def _bridge_refusal(case: str):
    if case == "no mirror-symmetric pairing":  # the top ring turned so that none of its points is on the plane
        app, mesh, bottom, top = _rings_across(turn=math.pi / 8)
        _select_points(app, {bottom[0], top[0]})
        return app, TEXT_BRIDGE_NOT_MIRRORED
    app, hole, mirrored = _cube_with_two_holes()
    mesh = app.scene.mesh
    if case == "each other's image":
        _select_points(app, {hole[0], mirrored[0]})
        return app, TEXT_BRIDGE_ACROSS
    if case == "opposite sides":
        _ear(mesh, hole, mirror=False)
        left = _ear(mesh, hole, mirror=True)
        mesh.symmetry_definition = definition_for_axis(mesh, "X")
        _select_points(app, {hole[0], left[0]})
        return app, TEXT_BRIDGE_ACROSS
    if case == "one across the plane":
        face = plus_x_quad(mesh, touching_seam=True)
        index = SymmetryIndex(mesh)
        corners = mesh.face_vertices(face)
        mesh.delete_faces([face, index.face_partner(face)])
        _select_points(app, {hole[0], next(v for v in corners if mesh.vertex_position(v)[0] == 0.0)})
        return app, TEXT_BRIDGE_MIXED
    if case == "closed image":  # the -X hole closed again: the +X hole's image is no border
        mesh.add_face(mirrored)
        _ear(mesh, hole, mirror=False)
        _ear(mesh, hole, mirror=True)
        mesh.symmetry_definition = definition_for_axis(mesh, "X")
        _select_points(app, {hole[0]})
        return app, TEXT_BRIDGE_IMAGE_CLOSED
    if case == "unpaired":  # an ear on the +X side only: its border has no mirror image
        right = _ear(mesh, hole, mirror=False)
        _select_points(app, {hole[0], right[0]})
        return app, TEXT_UNPAIRED
    raise AssertionError(case)


@pytest.mark.parametrize("case", [
    "no mirror-symmetric pairing", "each other's image", "opposite sides", "one across the plane", "closed image",
    "unpaired",
])
def test_symmetric_bridge_refusals_change_nothing(case):
    """P6-c (2)-(4) and the image checks: refused by the plan, the status says why, nothing changes."""
    app, text = _bridge_refusal(case)
    before = _snapshot(app)
    assert app.bridge_plan().refusal == text
    assert app.bridge_borders() is False and app.status_message == text
    assert _snapshot(app) == before


def test_without_its_declaration_bridge_is_refused_under_a_definition(monkeypatch):
    _undeclared(monkeypatch, "BRIDGE_COORDINATORS")
    app, hole, _ = _cube_with_two_holes()
    mesh = app.scene.mesh
    right = _ear(mesh, hole, mirror=False)
    _ear(mesh, hole, mirror=True)
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    _select_points(app, {hole[0], right[0]})
    before = _snapshot(app)
    assert app.bridge_borders() is False and "not with symmetry on" in app.status_message
    assert app.dispatch_command(commands.BRIDGE) is False
    assert _snapshot(app) == before
