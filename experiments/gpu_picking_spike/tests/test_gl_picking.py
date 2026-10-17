"""The ID picker on real GL (needs a display: `xvfb-run -a`; without one these are skipped by the
repo-root `conftest.py`). Small hand-built scenes with a known answer, plus the head mesh against
the production CPU picker."""

from __future__ import annotations

import math

import pytest

from gpu_picking_spike.id_picker import EDGES, FACES, VERTICES, GpuIdPicker

WIDTH, HEIGHT = 400, 300


@pytest.fixture(scope="module")
def window():
    import pyglet

    win = pyglet.window.Window(width=WIDTH, height=HEIGHT, visible=False)
    yield win
    win.close()


def _camera():
    from mirai.viewport.camera import OrbitCamera

    return OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.0, yaw=0.0, pitch=0.0)  # eye (0, 0, 5)


def _occluder_scene():
    """An occluder quad at z = 2 over a hidden vertex `h` at z = 0, and a visible vertex `v` at
    z = 3 a few pixels to the side (as `tests/test_picking_equivalence.py`)."""
    from core import Mesh

    mesh = Mesh()
    h = mesh.add_vertex((0.0, 0.0, 0.0))
    corners = [mesh.add_vertex(p) for p in ((-1.0, -1.0, 2.0), (1.0, -1.0, 2.0), (1.0, 1.0, 2.0), (-1.0, 1.0, 2.0))]
    quad = mesh.add_face(corners)
    v = mesh.add_vertex((0.05, 0.0, 3.0))
    return mesh, h, v, quad


def test_hidden_vertex_is_skipped_and_the_face_is_hit(window):
    mesh, h, v, quad = _occluder_scene()
    camera = _camera()
    picker = GpuIdPicker(mesh, WIDTH, HEIGHT)
    try:
        picker.render(camera, occlusion=True)
        hx, hy = camera.project_to_screen(mesh.vertex_position(h), WIDTH, HEIGHT)
        assert picker.pick_vertex(hx, hy) == v  # h lies under the quad
        assert picker.pick_face(hx + 3.0, hy + 3.0) == quad
        assert picker.pick_face(2.0, 2.0) is None
        assert h not in picker.elements_in_rect(VERTICES, (hx - 2, hy - 2, hx + 2, hy + 2))
        picker.render(camera, occlusion=False)  # Wireframe: everything pickable
        assert picker.pick_vertex(hx, hy) == h
        assert h in picker.elements_in_rect(VERTICES, (hx - 2, hy - 2, hx + 2, hy + 2))
    finally:
        picker.release()


def test_edges_of_the_front_face_are_pickable_through_the_polygon_offset(window):
    mesh, _h, _v, quad = _occluder_scene()
    camera = _camera()
    picker = GpuIdPicker(mesh, WIDTH, HEIGHT)
    try:
        picker.render(camera, occlusion=True)
        a, b = mesh.face_vertices(quad)[:2]
        pa = camera.project_to_screen(mesh.vertex_position(a), WIDTH, HEIGHT)
        pb = camera.project_to_screen(mesh.vertex_position(b), WIDTH, HEIGHT)
        mx, my = (pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0
        edge = picker.pick_edge(mx, my + 2.0)
        assert edge is not None and set(mesh.edge_vertices(edge)) == {a, b}
        assert picker.read_ids(EDGES, 0, 0, WIDTH - 1, HEIGHT - 1)  # the target holds edges
        assert picker.read_ids(FACES, 0, 0, WIDTH - 1, HEIGHT - 1) == {0}
    finally:
        picker.release()


def test_head_mesh_mostly_agrees_with_the_cpu_picker(window):
    """Not an equivalence claim: the spike measures the agreement; here only that the picker is
    wired right (most picks equal, every disagreement counted)."""
    from gpu_picking_spike import probe_gpu_picking as probe
    from loaders.assets import asset_path
    from mirai.scene_factory import build_core_scene_from_obj

    mesh = build_core_scene_from_obj(asset_path("head_basemesh")).mesh
    picker = GpuIdPicker(mesh, probe.WIDTH, probe.HEIGHT)
    try:
        cfg = type("Cfg", (), {"cursors": 60})()
        rows = probe.agreement_rows(mesh, picker, cfg)
    finally:
        picker.release()
    for (name, _occlusion), row in rows.items():
        assert row.total == 120
        assert row.same + row.half_px >= 0.9 * row.total, (name, row)


def test_depth_variant_keeps_the_cpu_box_rule_on_the_occluder_scene(window):
    """The depth oracle: the hidden vertex stays out of a Shaded box, the visible one and the
    occluder's own corners are in; the quad itself is selected (its centroid shows its own ID)."""
    mesh, h, v, quad = _occluder_scene()
    camera = _camera()
    picker = GpuIdPicker(mesh, WIDTH, HEIGHT)
    try:
        picker.render(camera, occlusion=True)
        everything = (0.0, 0.0, WIDTH - 1.0, HEIGHT - 1.0)
        assert picker.elements_in_rect_depth(VERTICES, everything) == set(mesh.all_vertex_ids()) - {h}
        assert picker.elements_in_rect_depth(FACES, everything) == {quad}
        hx, hy = camera.project_to_screen(mesh.vertex_position(h), WIDTH, HEIGHT)
        assert picker.pick_vertex_depth(hx, hy) == v
        picker.render(camera, occlusion=False)
        assert picker.elements_in_rect_depth(VERTICES, everything, occlusion=False) == set(mesh.all_vertex_ids())
    finally:
        picker.release()


def test_depth_variant_box_matches_the_cpu_box_on_the_head(window):
    """Head, front camera, 150 px box in all three modes: within 2 elements of production
    `elements_in_rect` (the spike's README has the full numbers)."""
    from gpu_picking_spike import probe_gpu_picking as probe
    from loaders.assets import asset_path
    from mirai.scene_factory import build_core_scene_from_obj

    mesh = build_core_scene_from_obj(asset_path("head_basemesh")).mesh
    picker = GpuIdPicker(mesh, probe.WIDTH, probe.HEIGHT)
    try:
        rows = [r for r in probe.box_rows(mesh, picker) if r[0] == "front" and r[1] == 150]
    finally:
        picker.release()
    assert len(rows) == 3
    for _cam, _size, name, n_cpu, _ids, _a, _b, n_depth, only_cpu, only_depth in rows:
        assert n_cpu > 0 and only_cpu + only_depth <= 2, (name, n_cpu, n_depth, only_cpu, only_depth)
