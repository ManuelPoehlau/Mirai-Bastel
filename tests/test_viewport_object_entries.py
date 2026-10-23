"""`Viewport` object entries (AD-021 M1, §4.4 "Drawing") and `pick_object`, headless.

A non-edit object is drawn as its own `RenderMesh` without `SelectionOverlay`; only the
colour is a look parameter (`PROVISIONAL`). TraceStore only, no GL.
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from core import Selection, VertexId
from mirai.scene_factory import create_cube
from mirai.viewport import OrbitCamera
from mirai.viewport.picking import PickCache, pick_object
from viewport import Viewport
from viewport.gl_render_store import DEFAULT_BASE_COLOR

WIDTH, HEIGHT = 800, 600


def _viewport() -> tuple[Viewport, OrbitCamera]:
    selection = Selection()
    viewport = Viewport(create_cube(), selection=selection)
    camera = OrbitCamera()
    camera.frame_on_bounds((0.0, 0.0, 0.0), 2.0)
    viewport.bind_camera(camera)
    return viewport, camera


def test_an_entry_is_a_render_mesh_without_overlay_and_with_its_colour():
    viewport, camera = _viewport()
    other = create_cube()
    assert viewport.set_object_entry("ref", other, (0.1, 0.2, 0.3)) is True
    entry = viewport.object_entries["ref"]
    assert entry.mesh is other
    assert entry.overlay is None
    assert entry.camera is camera
    assert entry.material.color == (0.1, 0.2, 0.3)
    viewport.sync()
    assert entry.store.data("material_uniforms")[:3] == [0.1, 0.2, 0.3]
    assert len(entry.store.data("camera_uniforms")) == 32
    assert not entry.store.has("highlight_flags")


def test_a_colour_change_does_not_rebuild_the_entry():
    viewport, _ = _viewport()
    other = create_cube()
    viewport.set_object_entry("ref", other, (0.1, 0.2, 0.3))
    viewport.sync()
    entry = viewport.object_entries["ref"]
    rebuilds = entry.benchmark_counters["mesh_rebuilds"]
    assert viewport.set_object_entry("ref", other, (0.1, 0.2, 0.3)) is False
    assert viewport.set_object_entry("ref", other, None) is True
    viewport.sync()
    assert viewport.object_entries["ref"] is entry
    assert entry.benchmark_counters["mesh_rebuilds"] == rebuilds
    assert entry.store.data("material_uniforms")[:3] == list(DEFAULT_BASE_COLOR)


def test_another_mesh_under_the_same_key_replaces_the_entry_and_remove_drops_it():
    viewport, _ = _viewport()
    viewport.set_object_entry("ref", create_cube())
    first = viewport.object_entries["ref"]
    viewport.set_object_entry("ref", create_cube())
    assert viewport.object_entries["ref"] is not first
    assert viewport.remove_object_entry("ref") is True
    assert viewport.remove_object_entry("ref") is False
    assert viewport.object_entries == {}


def test_camera_changes_reach_every_entry():
    viewport, camera = _viewport()
    viewport.set_object_entry("ref", create_cube())
    viewport.sync()
    entry = viewport.object_entries["ref"]
    updates = entry.benchmark_counters.get("camera_updates", 0)
    camera.orbit(0.3, 0.1)
    viewport.on_camera_changed(WIDTH / HEIGHT)
    viewport.sync()
    assert entry.benchmark_counters["camera_updates"] == updates + 1
    assert entry.aspect == WIDTH / HEIGHT


def test_selection_overlays_stay_on_the_edit_mesh_only():
    """Both cubes have VertexId(0): selecting it lights up one point, the edit mesh's."""
    viewport, _ = _viewport()
    viewport.set_object_entry("ref", create_cube(2.0))
    viewport.selection.vertices = {VertexId(0)}
    viewport.on_selection_changed()
    viewport.sync()
    assert viewport.point_positions["selected"] == [viewport.mesh.vertex_position(VertexId(0))]


def test_pick_object_returns_the_front_most_mesh_under_the_cursor():
    camera = OrbitCamera()
    camera.frame_on_bounds((0.0, 0.0, 0.0), 3.0)
    small, large = create_cube(1.0), create_cube(4.0)
    centre = (WIDTH / 2, HEIGHT / 2)
    candidates = [
        ("small", small, PickCache(), camera, 1.0),
        ("large", large, PickCache(), camera, 1.0),
    ]
    # The large cube encloses the small one: its front face is hit first.
    assert pick_object(candidates, *centre, WIDTH, HEIGHT) == "large"
    assert pick_object(candidates[:1], *centre, WIDTH, HEIGHT) == "small"
    assert pick_object(candidates, 1.0, 1.0, WIDTH, HEIGHT) is None
