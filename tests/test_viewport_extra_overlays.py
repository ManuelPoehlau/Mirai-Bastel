"""`Viewport.add_overlay` — a host's extra overlay (WP-SYM-LAB-03 H1).

Headless (TraceStore, recording stand-ins for the GL overlays). Plan
`docs/architecture/WP-SYM-LAB-03_REBASE_PLAN.md` §3 H1: `o.sync(mesh,
selection)` runs inside `Viewport.sync()` when selection/geometry/topology
were reported or `o.dirty` is set; `o.draw(camera_uniforms)` runs in
`render()` after the tool lines and before the point overlay; without extra
overlays nothing changes. Also: `GLPointOverlay` takes its layers as class
attributes, so a host can subclass it (no GL needed for the data side).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import Selection
from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from viewport import Viewport
from viewport.gl_point_overlay import DRAW_ORDER, LAYER_STYLES, GLPointOverlay
from viewport.overlay import TOOL_ACTIVE_LAYER

LOG: list[tuple] = []


class _Points:
    def set_points(self, layer, positions):
        pass

    def draw(self, camera_uniforms):
        LOG.append(("points",))


class _Lines:
    def set_segments(self, segments, layer=None):
        pass

    def draw(self, camera_uniforms, layers=()):
        LOG.append(("lines", tuple(layers)))


class _Faces:
    def set_triangles(self, layer, triangles):
        pass

    def draw(self, camera_uniforms):
        LOG.append(("faces",))


class _Extra:
    def __init__(self, name: str = "extra") -> None:
        self.name = name
        self.dirty = False
        self.syncs: list[tuple] = []
        self.draws: list[list] = []

    def sync(self, mesh, selection) -> None:
        self.syncs.append((mesh, selection))
        self.dirty = False

    def draw(self, camera_uniforms) -> None:
        self.draws.append(list(camera_uniforms))
        LOG.append((self.name,))


@pytest.fixture
def viewport():
    LOG.clear()
    vp = Viewport(
        create_cube(),
        selection=Selection(),
        point_overlay_type=_Points,
        line_overlay_type=_Lines,
        face_overlay_type=_Faces,
    )
    vp.bind_camera(OrbitCamera())
    vp.sync()
    return vp


def test_draw_order_extra_after_tool_lines_before_points(viewport):
    first, second = _Extra("extra1"), _Extra("extra2")
    viewport.add_overlay(first)
    viewport.add_overlay(second)
    viewport.set_tool_overlay(segments={TOOL_ACTIVE_LAYER: [((0, 0, 0), (1, 0, 0))]})
    viewport.sync()
    LOG.clear()
    viewport.render()
    names = [entry[0] for entry in LOG]
    assert names[-3:] == ["extra1", "extra2", "points"]
    assert LOG[-4][0] == "lines" and TOOL_ACTIVE_LAYER in LOG[-4][1]
    assert len(first.draws[0]) == 32  # view + projection, the mesh's camera packet


def test_extra_overlay_drawn_without_any_gl_overlay():
    LOG.clear()
    vp = Viewport(create_cube(), selection=Selection())
    vp.bind_camera(OrbitCamera())
    extra = _Extra()
    vp.add_overlay(extra)
    vp.sync()
    vp.render()
    assert LOG == [("extra",)]


def test_first_sync_after_add_then_only_on_notifications(viewport):
    extra = _Extra()
    viewport.add_overlay(extra)
    viewport.sync()
    assert extra.syncs == [(viewport.mesh, viewport.selection)]
    viewport.sync()
    viewport.on_camera_changed(aspect=1.5)
    viewport.sync()
    assert len(extra.syncs) == 1  # camera and idle frames are not a change

    viewport.on_selection_changed()
    viewport.sync()
    assert len(extra.syncs) == 2

    vid = viewport.mesh.all_vertex_ids()[0]
    viewport.on_vertices_moved({vid})
    viewport.sync()
    assert len(extra.syncs) == 3

    viewport.on_vertices_moved(set())  # nothing moved: no change
    viewport.sync()
    assert len(extra.syncs) == 3

    viewport.on_topology_changed()
    viewport.sync()
    assert len(extra.syncs) == 4


def test_overlay_dirty_flag_forces_sync(viewport):
    extra = _Extra()
    viewport.add_overlay(extra)
    viewport.sync()
    extra.dirty = True
    viewport.sync()
    assert len(extra.syncs) == 2
    assert extra.dirty is False
    viewport.sync()
    assert len(extra.syncs) == 2


def test_no_extra_overlays_is_a_no_op(viewport):
    assert viewport.extra_overlays == []
    viewport.on_selection_changed()
    viewport.sync()
    LOG.clear()
    viewport.render()
    assert [entry[0] for entry in LOG] == ["points"]


def test_point_overlay_layers_are_class_attributes():
    assert GLPointOverlay.LAYERS == DRAW_ORDER
    assert GLPointOverlay.LAYER_STYLES is LAYER_STYLES

    class HostPoints(GLPointOverlay):
        LAYERS = ("host_a", "host_b")
        LAYER_STYLES = {"host_a": ((0.1, 0.2, 0.3, 1.0), 6.0), "host_b": ((0.3, 0.2, 0.1, 1.0), 9.0)}

    points = HostPoints()
    points.set_points("host_b", [(1.0, 2.0, 3.0)])
    assert points.points("host_b") == [(1.0, 2.0, 3.0)]
    assert points.points("host_a") == []
    with pytest.raises(KeyError):
        points.set_points("selected", [])
    # The base class keeps the production layers.
    GLPointOverlay().set_points("selected", [(0.0, 0.0, 0.0)])
