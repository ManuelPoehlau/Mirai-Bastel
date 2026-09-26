"""Punkt-Overlay (WP-06 B2b): Weltpositionen headless, Viewport-Verdrahtung,
Base-Mesh-Invariante, Face-Tint entfernt.

Headless (TraceStore, kein GL-Kontext). Der echte GL-Zeichenpfad liegt in
`tests/test_gl_point_overlay.py`.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import Selection, SelectionMode
from mirai.application import Application
from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from viewport import GLPointOverlay, Viewport
from viewport.gl_render_store import FRAGMENT_SRC
from viewport.overlay import HOVER_LAYER, POINT_LAYERS, SELECTED_LAYER, SelectionOverlay


class RecordingPointOverlay:
    """Stellvertreter für `GLPointOverlay` (gleiche Schnittstelle, kein GL)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list]] = []
        self.draws: list[list[float]] = []

    def set_points(self, layer, positions) -> None:
        self.calls.append((layer, [tuple(p) for p in positions]))

    def draw(self, camera_uniforms) -> None:
        self.draws.append(list(camera_uniforms))


@pytest.fixture
def mesh():
    return create_cube()


@pytest.fixture
def selection():
    return Selection()


# -- SelectionOverlay: Positionen ------------------------------------------------


def test_selected_positions_are_exact_world_positions(mesh, selection):
    overlay = SelectionOverlay(selection)
    ids = mesh.all_vertex_ids()
    selection.set({ids[5], ids[2]})
    assert overlay.selected_vertex_positions(mesh) == [
        mesh.vertex_position(ids[2]),
        mesh.vertex_position(ids[5]),
    ]


def test_empty_selection_gives_no_points(mesh, selection):
    overlay = SelectionOverlay(selection)
    assert overlay.point_layers(mesh) == {HOVER_LAYER: [], SELECTED_LAYER: []}


def test_hovered_vertex_gives_one_position(mesh, selection):
    overlay = SelectionOverlay(selection)
    vid = mesh.all_vertex_ids()[3]
    selection.hovered = vid
    assert overlay.hovered_vertex_positions(mesh) == [mesh.vertex_position(vid)]


def test_edge_or_face_hover_gives_no_point(mesh, selection):
    overlay = SelectionOverlay(selection)
    selection.hovered = mesh.all_face_ids()[0]
    assert overlay.hovered_vertex_positions(mesh) == []
    selection.hovered = mesh.all_edge_ids()[0]
    assert overlay.hovered_vertex_positions(mesh) == []


def test_selected_points_only_in_vertex_mode(mesh, selection):
    overlay = SelectionOverlay(selection)
    selection.set({mesh.all_vertex_ids()[0]})
    selection.mode = SelectionMode.FACE
    assert overlay.selected_vertex_positions(mesh) == []


def test_point_layers_order_is_hover_then_selected():
    assert POINT_LAYERS == (HOVER_LAYER, SELECTED_LAYER)


# -- Viewport-Verdrahtung ----------------------------------------------------------


def test_default_viewport_creates_no_point_overlay_but_computes_positions(mesh, selection):
    vp = Viewport(mesh, selection=selection)
    assert vp.point_overlay is None
    vid = mesh.all_vertex_ids()[1]
    selection.set({vid})
    selection.hovered = vid
    vp.on_selection_changed()
    vp.sync()
    assert vp.point_positions == {
        HOVER_LAYER: [mesh.vertex_position(vid)],
        SELECTED_LAYER: [mesh.vertex_position(vid)],
    }


def test_selection_change_pushes_points_to_overlay(mesh, selection):
    vp = Viewport(mesh, selection=selection, point_overlay_type=RecordingPointOverlay)
    vp.sync()
    vp.point_overlay.calls.clear()

    vid = mesh.all_vertex_ids()[4]
    selection.set({vid})
    vp.on_selection_changed()
    vp.sync()
    assert dict(vp.point_overlay.calls) == {
        HOVER_LAYER: [],
        SELECTED_LAYER: [mesh.vertex_position(vid)],
    }


def test_no_push_without_change(mesh, selection):
    vp = Viewport(mesh, selection=selection, point_overlay_type=RecordingPointOverlay)
    vp.sync()
    vp.point_overlay.calls.clear()
    vp.on_camera_changed(aspect=1.5)
    vp.sync()
    vp.sync()
    assert vp.point_overlay.calls == []


def test_points_follow_moved_vertices(mesh, selection):
    vp = Viewport(mesh, selection=selection, point_overlay_type=RecordingPointOverlay)
    vid = mesh.all_vertex_ids()[0]
    selection.set({vid})
    vp.on_selection_changed()
    vp.sync()

    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x + 1.0, y, z))
    vp.on_vertices_moved({vid})
    vp.sync()
    assert vp.point_positions[SELECTED_LAYER] == [(x + 1.0, y, z)]
    assert vp.point_overlay.calls[-1] == (SELECTED_LAYER, [(x + 1.0, y, z)])


def test_topology_change_drops_stale_ids(mesh, selection):
    vp = Viewport(mesh, selection=selection)
    edge = mesh.all_edge_ids()[0]
    v0, v1 = mesh.edge_vertices(edge)
    selection.set({v0, v1})
    selection.hovered = v1
    vp.on_selection_changed()
    vp.sync()
    assert len(vp.point_positions[SELECTED_LAYER]) == 2

    mesh.collapse_edge(edge)  # v1 wird ungültig, v0 wandert zur Kantenmitte
    vp.on_topology_changed()
    vp.sync()
    assert not mesh.is_valid_vertex(v1)
    assert vp.point_positions == {
        HOVER_LAYER: [],
        SELECTED_LAYER: [mesh.vertex_position(v0)],
    }


def test_render_draws_points_with_mesh_camera_packet(mesh, selection):
    vp = Viewport(mesh, selection=selection, point_overlay_type=RecordingPointOverlay)
    camera = OrbitCamera()
    vp.bind_camera(camera)
    vp.on_camera_changed(aspect=2.0)
    vp.sync()
    vp.render()
    assert vp.point_overlay.draws == [
        list(camera.build_view_matrix()) + list(camera.build_projection_matrix(2.0))
    ]
    # Dieselbe Quelle wie die hochgeladenen Mesh-`camera_uniforms`.
    assert vp.point_overlay.draws[0] == vp.render_mesh.store.data("camera_uniforms")


def test_render_without_camera_draws_nothing(mesh, selection):
    vp = Viewport(mesh, selection=selection, point_overlay_type=RecordingPointOverlay)
    vp.sync()
    vp.render()
    assert vp.point_overlay.draws == []


# -- Invariante: Selektion/Hover bauen das Base-Mesh nicht neu -----------------


@pytest.mark.parametrize("change", ["selection", "hover"])
def test_selection_or_hover_change_does_not_rebuild_mesh(mesh, selection, change):
    vp = Viewport(mesh, selection=selection, point_overlay_type=RecordingPointOverlay)
    vp.bind_camera(OrbitCamera())
    vp.sync()
    counters_before = dict(vp.benchmark_counters)
    ids_before = vp.resource_ids()

    vid = mesh.all_vertex_ids()[2]
    if change == "selection":
        selection.set({vid})
    else:
        selection.hovered = vid
    vp.on_selection_changed()
    vp.sync()

    counters_after = vp.benchmark_counters
    assert vp.resource_ids() == ids_before
    for key in ("mesh_rebuilds", "structural_rebuilds", "gpu_resource_creations",
                "geometry_uploads"):
        assert counters_after.get(key, 0) == counters_before.get(key, 0), key
    # Unverändert gegenüber B2: genau ein Partial-Update (highlight_flags).
    assert counters_after["partial_updates"] - counters_before.get("partial_updates", 0) == 1


# -- GLPointOverlay ohne GL-Kontext --------------------------------------------------


def test_gl_point_overlay_set_points_needs_no_gl_and_marks_only_real_changes():
    overlay = GLPointOverlay()
    overlay.set_points(SELECTED_LAYER, [(0.0, 1.0, 2.0)])
    assert overlay.points(SELECTED_LAYER) == [(0.0, 1.0, 2.0)]
    assert overlay._stale == {SELECTED_LAYER}
    overlay._stale.clear()
    overlay.set_points(SELECTED_LAYER, [(0.0, 1.0, 2.0)])
    assert overlay._stale == set()
    assert overlay.rebuilds == 0
    assert overlay.vertex_list(SELECTED_LAYER) is None


def test_gl_point_overlay_rejects_unknown_layer():
    with pytest.raises(KeyError):
        GLPointOverlay().set_points("edges", [])


# -- Application-Durchreichung --------------------------------------------------------


def test_application_passes_point_overlay_type_through():
    app = Application()
    app.init_scene("cube")
    assert app.viewport.point_overlay is None
    app.init_scene("cube", point_overlay_type=RecordingPointOverlay)
    assert isinstance(app.viewport.point_overlay, RecordingPointOverlay)


# -- E18: Face-Tint entfernt -------------------------------------------------------------


def test_fragment_shader_output_no_longer_uses_highlight():
    body = FRAGMENT_SRC.split("void main()", 1)[1]
    assert "v_highlight" not in body
    assert "out_color = vec4(shaded, 1.0);" in body
