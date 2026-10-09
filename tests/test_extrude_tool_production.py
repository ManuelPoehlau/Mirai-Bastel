"""Production `ExtrudeTool` (`mirai.topology.extrude`, WP-06 B9) at tool level.

Headless, no GL, no window: a `Scene` with the cube (or a small grid) and a stub
camera whose world delta is chosen by the test. The algorithm is the Playground's
AP-05 boundary-edge rule, moved unchanged; these tests pin it from the Production
side (the Playground keeps its own `test_topology_extrude_baseline.py`).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, Scene
from core.selection import SelectionMode
from mirai.interaction.routing import tool_for_command
from mirai.interaction import commands as cmd
from mirai.interaction.tool import ToolState
from mirai.scene_factory import create_cube
from mirai.topology.connect_per_face import TopologyToolError
from mirai.topology.extrude import ExtrudeTool, _compute_face_normal


class _Camera:
    """World delta of every `update()`: a fixed vector (tests pick it per face)."""

    def __init__(self, delta=(0.0, 0.0, 0.5)) -> None:
        self.delta = delta

    def screen_delta_to_world(self, point, dx, dy, width, height):
        return self.delta


def _cube_scene() -> Scene:
    scene = Scene()
    scene.mesh = create_cube()
    return scene


def _grid_scene(n: int = 2) -> Scene:
    """n x n quads in the XY plane (normal +Z), (n+1)^2 vertices."""
    scene = Scene()
    mesh = scene.mesh
    verts = [[mesh.add_vertex((float(x), float(y), 0.0)) for x in range(n + 1)] for y in range(n + 1)]
    for y in range(n):
        for x in range(n):
            mesh.add_face([verts[y][x], verts[y][x + 1], verts[y + 1][x + 1], verts[y + 1][x]])
    return scene


def _state(mesh: Mesh) -> dict:
    """`export_state()` without the monotonic ID counters (AD-001: they only run forward,
    also across Undo and cancel - `Mesh.load_state`)."""
    return {k: v for k, v in mesh.export_state().items() if not k.endswith("_id_counter")}


def _counts(mesh: Mesh) -> tuple[int, int, int]:
    return len(mesh.all_vertex_ids()), len(mesh.all_edge_ids()), len(mesh.all_face_ids())


def _normal(mesh, fid):
    return _compute_face_normal(mesh, mesh.face_vertices(fid))


def _face_with_normal(mesh, n, tol=0.99):
    return next(f for f in mesh.all_face_ids() if sum(a * b for a, b in zip(_normal(mesh, f), n)) > tol)


def _extrude(scene, faces, delta=(0.0, 0.0, 0.5), steps=1, commit=True):
    tool = ExtrudeTool()
    tool.activate()
    tool.begin(scene=scene, camera=_Camera(delta), face_ids=set(faces))
    for _ in range(steps):
        tool.update(dx=1.0, dy=0.0, width=100, height=100)
    result = tool.commit() if commit else None
    return tool, result


def _no_loose_geometry(mesh) -> None:
    for eid in mesh.all_edge_ids():
        assert mesh.edge_faces(eid), f"free edge {eid!r} left behind"
    for vid in mesh.all_vertex_ids():
        assert mesh.vertex_edges(vid), f"free vertex {vid!r} left behind"


def _adjacent_pair(mesh):
    faces = mesh.all_face_ids()
    for i, a in enumerate(faces):
        for b in faces[i + 1:]:
            shared = set(mesh.face_edges(a)) & set(mesh.face_edges(b))
            if shared:
                return a, b, shared
    raise AssertionError("no adjacent faces")


def _opposite_pair(mesh):
    faces = mesh.all_face_ids()
    for i, a in enumerate(faces):
        for b in faces[i + 1:]:
            if not set(mesh.face_edges(a)) & set(mesh.face_edges(b)):
                return a, b
    raise AssertionError("no non-adjacent faces")


# -- Tool contract ------------------------------------------------------------------


def test_command_routes_to_the_production_tool_with_a_parameterless_constructor():
    tool_class = tool_for_command(cmd.EXTRUDE)
    assert tool_class is ExtrudeTool
    tool = tool_class()  # parameterless: context arrives through begin()
    assert tool.state is ToolState.IDLE


def test_playground_shim_is_the_same_algorithm_with_the_legacy_signature():
    from playground.topology_tools.extrude import ExtrudeTool as LegacyExtrudeTool

    assert issubclass(LegacyExtrudeTool, ExtrudeTool)
    scene = _cube_scene()
    face = scene.mesh.all_face_ids()[0]
    tool = LegacyExtrudeTool(scene, _Camera())
    tool.activate()
    tool.begin(face_ids={face})
    tool.update(dx=1.0, dy=0.0, width=100, height=100)
    tool.commit()
    assert _counts(scene.mesh) == (12, 20, 10)


# -- Geometry ------------------------------------------------------------------------


def test_single_face_on_a_cube_counts_walls_cap_and_original_face_gone():
    scene = _cube_scene()
    mesh = scene.mesh
    assert _counts(mesh) == (8, 12, 6)
    face = _face_with_normal(mesh, (0, 0, 1))
    old_vertices = set(mesh.face_vertices(face))
    _, caps = _extrude(scene, {face})
    # 4 new vertices; 4 walls + 1 cap replace the original face; 4 vertical + 4 cap edges.
    assert _counts(mesh) == (12, 20, 10)
    assert not mesh.is_valid_face(face)
    assert len(caps) == 1
    (cap,) = caps
    assert mesh.is_valid_face(cap)
    cap_vertices = set(mesh.face_vertices(cap))
    assert not cap_vertices & old_vertices
    # the cap moved +0.5 along its normal; the old ring stayed
    assert {round(mesh.vertex_position(v)[2], 6) for v in cap_vertices} == {1.5}
    assert {round(mesh.vertex_position(v)[2], 6) for v in old_vertices} == {1.0}
    _no_loose_geometry(mesh)


def test_two_adjacent_faces_get_no_wall_on_their_shared_edge():
    scene = _cube_scene()
    mesh = scene.mesh
    a, b, shared = _adjacent_pair(mesh)
    shared_edge = next(iter(shared))
    _, caps = _extrude(scene, {a, b}, delta=(0.0, 0.0, 0.0))
    # 6 distinct vertices -> 6 new; boundary edges = 4 + 4 - 2 = 6 walls; 2 caps replace 2 faces.
    assert _counts(mesh)[0] == 8 + 6
    assert _counts(mesh)[2] == 6 - 2 + 6 + 2
    assert len(caps) == 2
    # The internal edge was the region's own: no wall, no face, so it is gone.
    assert not mesh.is_valid_edge(shared_edge)
    _no_loose_geometry(mesh)


def test_two_non_adjacent_faces_each_get_a_full_wall_ring():
    scene = _cube_scene()
    mesh = scene.mesh
    a, b = _opposite_pair(mesh)
    _, caps = _extrude(scene, {a, b}, delta=(0.0, 0.0, 0.0))
    assert _counts(mesh)[0] == 8 + 8
    assert _counts(mesh)[2] == 6 - 2 + 8 + 2
    assert len(caps) == 2
    _no_loose_geometry(mesh)


def test_inward_distance_makes_a_pocket_with_a_floor():
    scene = _cube_scene()
    mesh = scene.mesh
    face = _face_with_normal(mesh, (0, 0, 1))
    _, caps = _extrude(scene, {face}, delta=(0.0, 0.0, -0.5))
    assert _counts(mesh) == (12, 20, 10)  # same topology as outward: walls + a cap (the floor)
    (cap,) = caps
    assert {round(mesh.vertex_position(v)[2], 6) for v in mesh.face_vertices(cap)} == {0.5}
    _no_loose_geometry(mesh)


def test_opposite_regions_move_along_their_own_component_normal():
    scene = _cube_scene()
    mesh = scene.mesh
    left = _face_with_normal(mesh, (-1, 0, 0))
    right = _face_with_normal(mesh, (1, 0, 0))
    # Opposite normals sum to zero -> the distance scalar's reference falls back to +Z
    # (known, accepted); the geometry still follows each component's own normal.
    _, caps = _extrude(scene, {left, right}, delta=(0.0, 0.0, 0.5))
    xs = sorted(
        {round(mesh.vertex_position(v)[0], 6) for cap in caps for v in mesh.face_vertices(cap)}
    )
    assert xs == [-1.5, 1.5]


def test_distance_accumulates_over_updates():
    scene = _cube_scene()
    face = _face_with_normal(scene.mesh, (0, 0, 1))
    tool, _ = _extrude(scene, {face}, delta=(0.0, 0.0, 0.25), steps=3, commit=False)
    assert tool.total_distance == pytest.approx(0.75)
    assert len(tool.vertex_ids) == 4
    tool.cancel()


# -- Selection / history ---------------------------------------------------------------


def test_selection_after_commit_is_exactly_the_cap_faces_in_face_mode():
    scene = _cube_scene()
    mesh = scene.mesh
    a, b, _ = _adjacent_pair(mesh)
    scene.selection.mode = SelectionMode.FACE
    scene.selection.set({a, b})
    tool, caps = _extrude(scene, {a, b})
    assert caps == tool.new_face_ids
    assert scene.selection.mode is SelectionMode.FACE
    assert scene.selection.faces == set(caps)
    assert all(mesh.is_valid_face(f) for f in scene.selection.faces)


def test_commit_pushes_exactly_one_history_entry():
    scene = _cube_scene()
    face = scene.mesh.all_face_ids()[0]
    assert len(scene.history) == 0
    _extrude(scene, {face}, steps=4)
    assert len(scene.history) == 1


def test_undo_and_redo_restore_the_exact_mesh_state():
    scene = _cube_scene()
    mesh = scene.mesh
    a, b, _ = _adjacent_pair(mesh)
    before = _state(mesh)
    _extrude(scene, {a, b})
    after = _state(mesh)
    assert after != before
    scene.history.undo()
    assert _state(mesh) == before
    scene.history.redo()
    assert _state(mesh) == after


def test_cancel_restores_the_exact_state_and_records_no_history():
    scene = _cube_scene()
    mesh = scene.mesh
    a, b, _ = _adjacent_pair(mesh)
    scene.selection.mode = SelectionMode.FACE
    scene.selection.set({a, b})
    before = _state(mesh)
    tool, _ = _extrude(scene, {a, b}, steps=3, commit=False)
    assert _state(mesh) != before
    tool.cancel()
    assert _state(mesh) == before
    assert len(scene.history) == 0
    assert scene.selection.mode is SelectionMode.FACE
    assert scene.selection.faces == {a, b}


def test_ids_are_never_reused_after_a_cancel():
    scene = _cube_scene()
    mesh = scene.mesh
    face = mesh.all_face_ids()[0]
    tool, _ = _extrude(scene, {face}, commit=False)
    burnt = set(tool.vertex_ids)
    tool.cancel()
    assert not burnt & set(mesh.all_vertex_ids())
    tool.deactivate()
    _, _ = _extrude(scene, {face})
    assert not burnt & set(mesh.all_vertex_ids())  # AD-001: allocators only run forward


# -- Refusals ----------------------------------------------------------------------------


@pytest.mark.parametrize("faces", [set(), "stale"])
def test_empty_or_invalid_face_ids_raise_and_touch_nothing(faces):
    scene = _cube_scene()
    mesh = scene.mesh
    if faces == "stale":
        face = mesh.all_face_ids()[0]
        mesh.remove_face(face)
        faces = {face}
    before = _state(mesh)
    tool = ExtrudeTool()
    tool.activate()
    with pytest.raises(TopologyToolError):
        tool.begin(scene=scene, camera=_Camera(), face_ids=faces)
    assert _state(mesh) == before
    assert tool.state is ToolState.ACTIVE
    assert len(scene.history) == 0


def test_a_failure_while_building_restores_the_mesh_and_selection(monkeypatch):
    scene = _cube_scene()
    mesh = scene.mesh
    face = mesh.all_face_ids()[0]
    scene.selection.mode = SelectionMode.FACE
    scene.selection.set({face})
    before = _state(mesh)

    real_add_face = mesh.add_face
    calls = []

    def failing_add_face(vertex_ids):
        calls.append(1)
        if len(calls) == 3:
            raise RuntimeError("core refused")
        return real_add_face(vertex_ids)

    monkeypatch.setattr(mesh, "add_face", failing_add_face)
    tool = ExtrudeTool()
    tool.activate()
    with pytest.raises(RuntimeError):
        tool.begin(scene=scene, camera=_Camera(), face_ids={face})
    monkeypatch.undo()
    assert _state(mesh) == before
    assert scene.selection.faces == {face}
    assert len(scene.history) == 0


# -- No leftovers ------------------------------------------------------------------------


def test_interior_edges_and_vertices_of_a_multi_face_region_are_pruned():
    scene = _grid_scene(2)
    mesh = scene.mesh
    faces = set(mesh.all_face_ids())
    interior_vertex = next(v for v in mesh.all_vertex_ids() if len(mesh.vertex_edges(v)) == 4)
    interior_edges = {e for e in mesh.all_edge_ids() if len(mesh.edge_faces(e)) == 2}
    assert len(interior_edges) == 4
    _, caps = _extrude(scene, faces, delta=(0.0, 0.0, 0.5))
    # 9 old vertices -> 9 new, minus the interior old one; 8 walls + 4 caps.
    assert _counts(mesh)[0] == 9 - 1 + 9
    assert _counts(mesh)[2] == 8 + 4
    assert not mesh.is_valid_vertex(interior_vertex)
    assert not any(mesh.is_valid_edge(e) for e in interior_edges)
    assert len(caps) == 4
    _no_loose_geometry(mesh)


def test_unrelated_free_edges_stay():
    scene = _cube_scene()
    mesh = scene.mesh
    lone_a = mesh.add_vertex((5.0, 5.0, 5.0))
    lone_b = mesh.add_vertex((6.0, 5.0, 5.0))
    stray = mesh.add_edge(lone_a, lone_b)
    _extrude(scene, {mesh.all_face_ids()[0]})
    assert mesh.is_valid_edge(stray)
    assert mesh.is_valid_vertex(lone_a) and mesh.is_valid_vertex(lone_b)
