"""LabState (GL-free): view cycle, A/B, level refusal (A9), HUD content."""

from __future__ import annotations

from loaders.assets import asset_path
from mirai.scene_factory import build_core_scene_from_obj

from subdivision_lab import lab_state as ls
from subdivision_lab.subd import SubdSurface, extract_control


def state_for(asset):
    mesh = build_core_scene_from_obj(str(asset_path(asset))).mesh
    topology, _ = extract_control(mesh)
    return ls.LabState(topology.face_sizes, len(topology.vertex_ids), "test-host")


def test_cap_is_the_documented_provisional_constant():
    assert ls.MAX_DERIVED_FACES == 25_000


def test_a9_man_with_shoes_level_3_refused_level_2_accepted():
    state = state_for("man_with_shoes_basemesh")
    assert state.predicted_faces(2) == 14_816 and state.predicted_faces(3) == 59_264
    assert state.request_level(2) is True
    assert state.level == 2 and state.warning is None

    assert state.request_level(3) is False  # no exception, state untouched
    assert state.level == 2
    assert "abgelehnt" in state.warning and "59.264" in state.warning and "25.000" in state.warning
    assert any(line.style == "warning" for line in state.hud_lines(None))

    assert state.request_level(1) is True and state.warning is None


def test_a9_head_level_3_is_allowed():
    state = state_for("head_basemesh")
    assert state.predicted_faces(3) == 20_736
    assert state.request_level(3) is True and state.level == 3


def test_a9_refusal_builds_nothing():
    mesh = build_core_scene_from_obj(str(asset_path("man_with_shoes_basemesh"))).mesh
    surface = SubdSurface(mesh)
    state = ls.LabState(surface.topology.face_sizes, len(surface.topology.vertex_ids))
    assert state.request_level(3) is False
    assert surface.built_levels == (0,)  # nothing was built for the refused level


def test_unknown_level_is_refused():
    state = state_for("subd_cube")
    assert state.request_level(4) is False and state.level == ls.DEFAULT_LEVEL
    assert state.request_level(0) is False


def test_view_cycle_and_ab():
    state = state_for("subd_cube")
    assert state.view == ls.VIEW_CAGE and not state.needs_surface()
    assert [state.cycle_view() for _ in range(3)] == [ls.VIEW_BOTH, ls.VIEW_ISO, ls.VIEW_CAGE]
    state.cycle_view()
    assert state.view == ls.VIEW_BOTH and state.needs_surface()
    assert state.toggle_ab() is True
    assert state.effective_view() == ls.VIEW_CAGE and not state.needs_surface()
    assert state.view == ls.VIEW_BOTH  # A/B never changes the chosen view
    assert state.toggle_ab() is False and state.effective_view() == ls.VIEW_BOTH


def test_cage_depth_and_hud_toggle():
    state = state_for("subd_cube")
    assert state.cage_depth_test is True
    assert state.toggle_cage_depth() is False and state.toggle_cage_depth() is True
    assert state.hud_visible is True and state.toggle_hud() is False


def test_revision_changes_with_every_hud_relevant_change():
    state = state_for("subd_cube")
    seen = {state.revision}
    for action in (state.cycle_view, state.toggle_ab, state.toggle_cage_depth, state.toggle_hud):
        action()
        assert state.revision not in seen
        seen.add(state.revision)
    for action in (lambda: state.record_build(12.5), lambda: state.record_drag(3.25),
                   lambda: state.set_derived_counts((10, 8))):
        action()
        assert state.revision not in seen
        seen.add(state.revision)
    revision = state.revision
    state.set_derived_counts((10, 8))  # unchanged value: no HUD change
    assert state.revision == revision


def test_hud_shows_everything_the_handoff_lists():
    state = state_for("head_basemesh")
    state.set_gl_info("3.3.0 test", "Test Renderer")
    state.record_build(123.4)
    state.record_drag(5.5)
    state.set_derived_counts((5186, 5184))
    text = "\n".join(line.text for line in state.hud_lines(16.7))
    for needle in (
        "Nicht Artist-validiert", "V-CAGE", "Stufe: 1", "326 V / 324 F", "5186 V / 5184 F",
        "Käfig-Tiefentest: an", "123.4 ms", "5.50 ms", "16.7 ms", "GL_VERSION: 3.3.0 test",
        "GL_RENDERER: Test Renderer", "test-host",
    ):
        assert needle in text, needle
