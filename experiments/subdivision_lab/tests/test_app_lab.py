"""The SubD Lab on the app path (WP-SUBD-LAB-02), headless (TraceStore, no window).

Built like `run.build_app_lab`. The app's tools change the control mesh; the replacement surface
(AD-013 H7) must follow exactly — always equal to `apply_full` of the current control positions —
through moves, Undo/Redo and topology changes; an unsupported control mesh switches the surface off
visibly. The lab keys change view state only and leave every other key to `Application`.
"""

from __future__ import annotations

import pytest

from mirai.interaction.input import Input
from mirai.scene_factory import mesh_from_positions_and_faces

from subdivision_lab.lab_app import (
    CYCLE_VIEW,
    LAB_KEYS,
    LabBindingConflict,
    assert_lab_keys_free,
    lab_key_press,
)
from subdivision_lab.lab_lines import CAGE_LAYER, ISO_LAYER
from subdivision_lab.lab_state import VIEW_BOTH, VIEW_CAGE, VIEW_ISO
from subdivision_lab.lab_surface import SubdSurfaceProvider
from subdivision_lab.run import build_app_lab
from subdivision_lab.subd import SubdSurface

WIDTH, HEIGHT = 800, 600
V = Input("key", "v")
B = Input("key", "b")
SHIFT_V = Input("key", "v", frozenset({"shift"}))
W = Input("key", "w")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))


def ctrl(n: int) -> Input:
    return Input("key", str(n), frozenset({"ctrl"}))


@pytest.fixture
def lab_app():
    app, lab = build_app_lab("subd_cube", WIDTH, HEIGHT)
    return app, lab


def frame(app) -> None:
    app.viewport.sync()


def expected_positions(mesh, level: int) -> list:
    surface = SubdSurface(mesh)
    positions = [tuple(mesh.vertex_position(v)) for v in surface.topology.vertex_ids]
    return surface.level(level).apply_full(positions)


def shown_positions(lab) -> list:
    surface = lab.provider.surface_mesh
    return [tuple(surface.vertex_position(v)) for v in surface.all_vertex_ids()]


def assert_surface_matches(app, lab) -> None:
    got = shown_positions(lab)
    want = expected_positions(app.viewport.mesh, lab.level)
    assert len(got) == len(want)
    for a, b in zip(got, want):
        assert a == pytest.approx(b, abs=1e-9)


def move_hovered_vertex(app) -> None:
    """Hover the vertex nearest the screen centre's right half, hold W, move, release."""
    mesh = app.viewport.mesh
    for vid in sorted(mesh.all_vertex_ids(), key=int):
        sx, sy = app.camera.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
        app.pointer_motion(sx, sy)
        if app.selection.hovered:
            break
    assert app.selection.hovered, "no vertex hoverable"
    before = mesh.export_state()
    app.key_press(W)
    app.pointer_motion(sx + 25, sy + 10, 25, 10)
    app.key_release(W)
    assert mesh.export_state() != before


def test_lab_keys_are_free_in_the_app_and_conflicts_abort(lab_app):
    app, _lab = lab_app
    # installed in the lab context only: the app's own contexts still resolve them to nothing
    assert_lab_keys_free(app.bindings)
    app.bindings.set_default(V, "Something")
    with pytest.raises(LabBindingConflict):
        assert_lab_keys_free(app.bindings)


def test_start_draws_the_control_mesh(lab_app):
    app, lab = lab_app
    frame(app)
    assert lab.effective_view() == VIEW_CAGE
    assert app.viewport.surface_provider is lab.provider
    assert app.viewport.surface_render_mesh is None


def test_v_cycles_views_and_the_surface_matches(lab_app):
    app, lab = lab_app
    assert lab_key_press(app, lab, V)
    frame(app)
    assert lab.effective_view() == VIEW_BOTH
    assert app.viewport.surface_render_mesh.mesh is lab.provider.surface_mesh
    assert_surface_matches(app, lab)
    assert lab.lines.segments[CAGE_LAYER] and not lab.lines.segments[ISO_LAYER]

    lab_key_press(app, lab, V)
    frame(app)
    assert lab.effective_view() == VIEW_ISO
    assert lab.lines.segments[ISO_LAYER] and not lab.lines.segments[CAGE_LAYER]

    lab_key_press(app, lab, V)
    frame(app)
    assert lab.effective_view() == VIEW_CAGE
    assert app.viewport.surface_render_mesh is None


def test_ab_and_cage_depth_are_view_state_only(lab_app):
    app, lab = lab_app
    lab_key_press(app, lab, V)
    frame(app)
    state = app.viewport.mesh.export_state()
    lab_key_press(app, lab, B)
    frame(app)
    assert app.viewport.surface_render_mesh is None
    lab_key_press(app, lab, B)
    lab_key_press(app, lab, SHIFT_V)
    frame(app)
    assert app.viewport.surface_render_mesh is not None
    assert lab.lines.cage_depth_test is False
    assert app.viewport.mesh.export_state() == state


def test_levels_and_refusal_above_the_limit(lab_app):
    app, lab = lab_app
    lab_key_press(app, lab, V)
    frame(app)
    faces_1 = lab.provider.derived_counts[1]
    assert lab_key_press(app, lab, ctrl(2))
    frame(app)
    assert lab.level == 2 and lab.provider.derived_counts[1] == 4 * faces_1
    assert_surface_matches(app, lab)

    lab.provider.max_faces = 4 * faces_1
    assert not lab_key_press(app, lab, ctrl(3))
    assert "abgelehnt" in app.status_message
    assert lab.level == 2


def test_w_move_through_the_app_updates_without_rebuild(lab_app):
    app, lab = lab_app
    lab_key_press(app, lab, V)
    frame(app)
    rm = app.viewport.surface_render_mesh
    move_hovered_vertex(app)
    frame(app)
    assert app.viewport.surface_render_mesh is rm  # positions only: no new RenderMesh
    assert lab.provider.last_update_ms is not None
    assert_surface_matches(app, lab)

    app.key_press(CTRL_Z)
    frame(app)
    assert_surface_matches(app, lab)
    app.key_press(CTRL_Y)
    frame(app)
    assert_surface_matches(app, lab)


def test_topology_change_rebuilds_and_undo_restores(lab_app):
    app, lab = lab_app
    lab_key_press(app, lab, V)
    frame(app)
    mesh = app.viewport.mesh
    faces_before = lab.provider.derived_counts[1]
    edge = next(iter(mesh.all_edge_ids()))

    def mutate():
        mesh.split_edge(edge)
        return None

    assert app.apply_mesh_change("Split (Test)", mutate)
    frame(app)
    assert lab.provider.derived_counts[1] != faces_before
    assert_surface_matches(app, lab)

    app.key_press(CTRL_Z)
    frame(app)
    assert lab.provider.derived_counts[1] == faces_before
    assert_surface_matches(app, lab)


def test_lab_keys_are_refused_while_a_transform_is_armed(lab_app):
    app, lab = lab_app
    mesh = app.viewport.mesh
    vid = sorted(mesh.all_vertex_ids(), key=int)[0]
    app.selection.set({vid})
    app.key_press(W)
    assert app.interaction_owner == "transform"
    assert not lab_key_press(app, lab, V)
    assert lab.effective_view() == VIEW_CAGE
    assert "ignoriert" in app.status_message
    app.key_release(W)


def test_other_keys_go_to_the_app(lab_app):
    app, lab = lab_app
    assert lab_key_press(app, lab, Input("key", "2"))  # Edge mode, an app key
    assert app.selection.mode.name == "EDGE"
    assert lab.effective_view() == VIEW_CAGE


def test_unsupported_control_mesh_switches_the_surface_off_visibly():
    # Two quads sharing only one vertex: its faces do not form one fan.
    positions = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (-1, 0, 0), (-1, -1, 0), (0, -1, 0)]
    mesh = mesh_from_positions_and_faces(positions, [(0, 1, 2, 3), (0, 4, 5, 6)])
    provider = SubdSurfaceProvider()
    messages = []
    provider.on_message = messages.append
    provider.set_enabled(True)
    assert provider.sync(mesh, None) == set()
    assert provider.surface_mesh is None
    assert messages and messages[0].startswith("SubD aus:")
    provider.set_enabled(False)
    provider.sync(mesh, None)
    provider.set_enabled(True)
    provider.sync(mesh, None)
    assert provider.surface_mesh is None and provider.message.startswith("SubD aus:")


def test_switching_off_and_on_follows_moves_made_while_off(lab_app):
    app, lab = lab_app
    lab_key_press(app, lab, V)
    frame(app)
    lab_key_press(app, lab, B)  # A/B: cage view, provider off
    frame(app)
    move_hovered_vertex(app)
    frame(app)
    lab_key_press(app, lab, B)
    frame(app)
    assert_surface_matches(app, lab)


def test_every_lab_key_is_listed_once():
    inputs = [entry.input for entry in LAB_KEYS]
    assert len(inputs) == len(set(inputs))
    assert CYCLE_VIEW in {entry.command for entry in LAB_KEYS}
