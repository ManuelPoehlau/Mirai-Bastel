"""GL tests on `head_basemesh` at a fixed 480x360 hidden window (Xvfb or EGL).

A5 (GL part): a simulated drag causes no structural rebuild / topology update
and leaves `resource_ids()` unchanged, `glGetError() == 0`.
A6: the control mesh is untouched by builds, level and view switches; the drag
path changes only the dragged vertex. A9 (GL part): refusal builds nothing.
Plus: views really render differently, A/B = V-CAGE, cage depth toggle, event
path (hover / grab / drag / orbit), stale-level refresh.
GL tests skip cleanly when no GL is available.
"""

from __future__ import annotations

import copy

import pytest

from ._pyglet_headless import import_pyglet

pyglet = import_pyglet()

from pyglet.window import key, mouse  # noqa: E402

from subdivision_lab import lab_scene as lsc  # noqa: E402
from subdivision_lab.lab_lines import LabLineOverlay  # noqa: E402
from subdivision_lab.lab_state import VIEW_BOTH, VIEW_CAGE, VIEW_ISO  # noqa: E402

WIDTH, HEIGHT = 480, 360


@pytest.fixture(scope="module")
def window():
    from pyglet import gl

    from subdivision_lab.lab_window import SubdLabWindow

    try:
        win = SubdLabWindow("head_basemesh", WIDTH, HEIGHT, visible=False)
    except Exception as exc:  # no GL / no display in this environment
        pytest.skip(f"no GL context available: {exc}")
    win.switch_to()
    fb_width, fb_height = win.get_framebuffer_size()
    gl.glViewport(0, 0, fb_width, fb_height)
    yield win
    win.close()


def gl_error() -> int:
    from pyglet import gl

    return int(gl.glGetError())


def read_rgba() -> bytes:
    from pyglet import gl

    gl.glFinish()
    image = pyglet.image.get_buffer_manager().get_color_buffer().get_region(0, 0, WIDTH, HEIGHT).get_image_data()
    return bytes(image.get_data("RGBA", WIDTH * 4))


def render(window, mode: str, level: int = 1, depth: bool = True) -> bytes:
    window.switch_to()
    window.scene.draw(mode, level, depth)
    return read_rgba()


def changed_pixels(a: bytes, b: bytes, level: int = 2) -> int:
    return sum(
        1 for i in range(0, len(a), 4)
        if max(abs(a[i] - b[i]), abs(a[i + 1] - b[i + 1]), abs(a[i + 2] - b[i + 2])) >= level
    )


def reset_window(window) -> None:
    """Back to V-CAGE, level 1, depth test on, no A/B, control mesh at its start positions."""
    scene = window.scene
    window.switch_to()
    state = window.state
    state.view, state.level, state.ab_active, state.cage_depth_test = VIEW_CAGE, 1, False, True
    topology = scene.topology
    for i, p in enumerate(scene.surface.initial_positions):
        scene.control_mesh.set_vertex_position(topology.vertex_ids[i], p)
        scene.control_positions[i] = p
    scene.version += 1
    scene.control_rm.mark_vertices_dirty(set(topology.vertex_ids))
    for view in scene.views.values():
        view.stale = True
    window._apply_surface_request()


def select_view(window, view: str, level: int) -> None:
    state = window.state
    state.view = view
    state.request_level(level)
    window._apply_surface_request()


def front_vertex(window):
    """The control vertex nearest to the camera eye (never occluded)."""
    scene = window.scene
    eye = scene.camera.eye()
    best = min(range(len(scene.control_positions)),
               key=lambda i: sum((a - b) ** 2 for a, b in zip(scene.control_positions[i], eye)))
    return best, scene.topology.vertex_ids[best]


# -- A5 (GL part) -------------------------------------------------------------------------------


@pytest.mark.parametrize("level", [1, 2])
def test_a5_drag_100_steps_has_no_structural_rebuild(window, level):
    reset_window(window)
    select_view(window, VIEW_BOTH, level)
    window.on_draw()
    scene = window.scene
    view = scene.views[level]
    rm = view.render_mesh
    before_counters = dict(rm.benchmark_counters)
    before_ids = dict(rm.resource_ids())
    control_before = dict(scene.control_rm.benchmark_counters)

    index, vid = front_vertex(window)
    for step in range(100):
        window.drag_vertex_by(vid, 1.5, 0.75)
        if step % 10 == 0:
            window.on_draw()
    window.on_draw()

    after = dict(rm.benchmark_counters)
    assert after.get("structural_rebuilds", 0) == before_counters.get("structural_rebuilds", 0)
    assert after.get("topology_updates", 0) == before_counters.get("topology_updates", 0)
    assert after.get("mesh_rebuilds", 0) == before_counters.get("mesh_rebuilds", 0)
    assert dict(rm.resource_ids()) == before_ids
    assert after["vertex_updates"] > before_counters.get("vertex_updates", 0), "the drag must really have updated vertices"
    assert gl_error() == 0
    # the control RenderMesh was not rebuilt either
    assert scene.control_rm.benchmark_counters.get("structural_rebuilds", 0) == control_before.get("structural_rebuilds", 0)

    # the displayed surface equals a full recomputation, in the lab mesh as well
    full = view.derived.apply_full(scene.control_positions)
    assert all(abs(a - b) <= 1e-12 for p, q in zip(view.positions, full) for a, b in zip(p, q))
    for d, vid_d in enumerate(view.vertex_ids):
        assert tuple(view.mesh.vertex_position(vid_d)) == tuple(view.positions[d])
    assert 0 < len(view.derived.inverse[index])


def test_a5_local_drag_touches_only_the_inverse_set(window):
    reset_window(window)
    select_view(window, VIEW_BOTH, 2)
    window.on_draw()
    scene = window.scene
    view = scene.views[2]
    index, vid = front_vertex(window)
    before = list(view.positions)
    window.drag_vertex_by(vid, 4.0, 3.0)
    changed = {d for d in range(len(before)) if view.positions[d] != before[d]}
    assert changed == set(view.derived.inverse[index])
    assert len(changed) < 0.1 * len(before)


# -- A6 -----------------------------------------------------------------------------------------


def test_a6_control_mesh_untouched_by_builds_and_switches(window):
    reset_window(window)
    mesh = window.scene.control_mesh
    before = copy.deepcopy(mesh.export_state())
    steps = [key._2, key.V, key._3, key.X, key.B, key.B, key._1, key.V, key.X, key.V, key.B, key.B]
    for symbol in steps:
        window.on_key_press(symbol, 0)
        window.on_draw()
    assert gl_error() == 0
    assert mesh.export_state() == before
    assert repr(mesh.export_state()) == repr(before)  # bit-identical floats, not just ==


def test_a6_drag_path_changes_only_the_dragged_vertex(window):
    reset_window(window)
    select_view(window, VIEW_BOTH, 1)
    mesh = window.scene.control_mesh
    before = copy.deepcopy(mesh.export_state())
    index, vid = front_vertex(window)
    window.drag_vertex_by(vid, 10.0, 5.0)
    after = mesh.export_state()
    assert after["edges"] == before["edges"] and after["faces"] == before["faces"]
    assert after["vertex_id_counter"] == before["vertex_id_counter"]
    moved = [v for v in after["vertices"] if after["vertices"][v] != before["vertices"][v]]
    assert moved == [int(vid)]
    assert after["vertices"][int(vid)] != before["vertices"][int(vid)]


def test_a6_derived_mesh_is_not_a_scene_and_has_own_ids(window):
    reset_window(window)
    select_view(window, VIEW_BOTH, 1)
    view = window.scene.views[1]
    assert view.mesh is not window.scene.control_mesh
    assert len(view.vertex_ids) == view.derived.n_verts


# -- views / A/B / depth --------------------------------------------------------------------------


def test_views_render_differently_and_ab_equals_cage_view(window):
    reset_window(window)
    cage = render(window, VIEW_CAGE)
    both = render(window, VIEW_BOTH, 2)
    iso = render(window, VIEW_ISO, 2)
    background = bytes(cage[:4])
    assert sum(1 for i in range(0, len(cage), 4) if cage[i:i + 4] != background) > 3000, "mesh must be visible"
    assert changed_pixels(cage, both) > 500
    assert changed_pixels(cage, iso) > 500
    assert changed_pixels(both, iso) > 200

    # A/B shows exactly the V-CAGE image, independent of the chosen view and level
    window.state.view = VIEW_BOTH
    window.state.request_level(2)
    window.on_key_press(key.B, 0)
    assert window.state.ab_active
    window.switch_to()
    window.draw_scene()
    ab = read_rgba()
    window.on_key_press(key.B, 0)
    assert ab == cage
    assert gl_error() == 0


def test_cage_depth_toggle_changes_the_picture_in_v_both(window):
    reset_window(window)
    tested = render(window, VIEW_BOTH, 1, depth=True)
    always = render(window, VIEW_BOTH, 1, depth=False)
    assert changed_pixels(tested, always) > 50  # cage parts behind the surface appear / disappear


def test_line_overlay_subclass_leaves_production_alone():
    from viewport.gl_line_overlay import GLLineOverlay

    assert GLLineOverlay.LAYERS != LabLineOverlay.LAYERS
    assert GLLineOverlay.NO_DEPTH_LAYERS == frozenset({"tool_preview"})
    overlay = LabLineOverlay()
    assert overlay.NO_DEPTH_LAYERS == frozenset()
    overlay.cage_depth_test = False
    assert overlay.NO_DEPTH_LAYERS == frozenset({"cage"})
    assert LabLineOverlay.LAYER_STYLES["cage"][0] != LabLineOverlay.LAYER_STYLES["iso"][0]


# -- events: hover / grab / drag / orbit ----------------------------------------------------------------


def test_events_hover_grab_drag_release(window):
    reset_window(window)
    scene = window.scene
    index, vid = front_vertex(window)
    sx, sy = scene.camera.project_to_screen(scene.control_positions[index], window.width, window.height)

    window.on_mouse_motion(sx + 2, sy - 1, 0, 0)
    assert window._hover_vertex == vid

    window.on_mouse_press(sx, sy, mouse.LEFT, 0)
    assert window._drag_vertex == vid
    window.on_mouse_drag(sx + 20, sy + 10, 20, 10, mouse.LEFT, 0)
    nx, ny = scene.camera.project_to_screen(scene.control_positions[index], window.width, window.height)
    assert abs((nx - sx) - 20) < 0.5 and abs((ny - sy) - 10) < 0.5
    assert window.state.last_drag_ms is not None and window.state.last_drag_ms > 0
    window.on_mouse_release(sx + 20, sy + 10, mouse.LEFT, 0)
    assert window._drag_vertex is None
    assert gl_error() == 0


def test_alt_drag_orbits_and_does_not_move_a_vertex(window):
    reset_window(window)
    scene = window.scene
    positions = list(scene.control_positions)
    index, vid = front_vertex(window)
    sx, sy = scene.camera.project_to_screen(scene.control_positions[index], window.width, window.height)
    yaw = scene.camera.yaw
    window.on_mouse_press(sx, sy, mouse.LEFT, key.MOD_ALT)
    assert window._drag_vertex is None
    window.on_mouse_drag(sx + 30, sy, 30, 0, mouse.LEFT, key.MOD_ALT)
    window.on_mouse_release(sx + 30, sy, mouse.LEFT, key.MOD_ALT)
    assert scene.camera.yaw != yaw
    assert scene.control_positions == positions
    scene.camera.orbit(yaw - scene.camera.yaw, 0.0)  # put the camera back for later tests
    window._camera_changed()


def test_drag_in_v_cage_updates_the_control_view(window):
    reset_window(window)
    window.state.view = VIEW_CAGE
    window._apply_surface_request()
    index, vid = front_vertex(window)
    before = render(window, VIEW_CAGE)
    window.drag_vertex_by(vid, 30.0, 0.0)
    after = render(window, VIEW_CAGE)
    assert changed_pixels(before, after) > 20
    assert gl_error() == 0


def test_stale_level_is_refreshed_on_switch(window):
    reset_window(window)
    select_view(window, VIEW_BOTH, 2)  # builds level 2
    select_view(window, VIEW_BOTH, 1)  # builds level 1, displayed
    scene = window.scene
    assert not scene.views[2].stale
    index, vid = front_vertex(window)
    window.drag_vertex_by(vid, 12.0, 6.0)  # level 2 is not displayed -> stale
    assert scene.views[2].stale and not scene.views[1].stale

    window.on_key_press(key._2, 0)
    assert not scene.views[2].stale
    view = scene.views[2]
    full = view.derived.apply_full(scene.control_positions)
    assert all(abs(a - b) <= 1e-12 for p, q in zip(view.positions, full) for a, b in zip(p, q))
    window.on_draw()
    assert gl_error() == 0


def test_drag_in_v_cage_marks_built_levels_stale_and_v_both_follows(window):
    reset_window(window)
    select_view(window, VIEW_BOTH, 1)
    scene = window.scene
    window.state.view = VIEW_CAGE
    window._apply_surface_request()
    index, vid = front_vertex(window)
    window.drag_vertex_by(vid, 8.0, 8.0)
    assert scene.views[1].stale
    window.on_key_press(key.V, 0)  # -> V-BOTH, refreshes level 1
    assert not scene.views[1].stale
    full = scene.views[1].derived.apply_full(scene.control_positions)
    assert all(abs(a - b) <= 1e-12 for p, q in zip(scene.views[1].positions, full) for a, b in zip(p, q))


# -- A9 (GL part) / HUD ------------------------------------------------------------------------------------


def test_a9_scene_refuses_level_3_of_man_with_shoes_and_builds_level_2(window):
    from subdivision_lab.lab_state import MAX_DERIVED_FACES

    window.switch_to()
    scene = lsc.LabScene("man_with_shoes_basemesh", aspect=WIDTH / HEIGHT)
    try:
        before = scene.surface.built_levels
        with pytest.raises(lsc.LevelRefusedError):
            scene.ensure_level(3)
        assert scene.surface.built_levels == before == (0,)  # no partial state
        assert scene.views == {}

        view, ms, did_work = scene.ensure_level(2)
        assert did_work and ms > 0
        assert len(view.derived.faces) == 14_816 <= MAX_DERIVED_FACES
        assert view.derived.n_verts == 14_818
        assert gl_error() == 0
    finally:
        scene.release()


def test_hud_carries_gl_strings(window):
    assert window.state.gl_version not in ("", "?") and window.state.gl_renderer not in ("", "?")
    text = "\n".join(line.text for line in window.state.hud_lines(10.0))
    assert window.state.gl_version in text and window.state.gl_renderer in text


def test_hud_draw_does_not_leak_state_into_the_next_frame(window):
    reset_window(window)
    select_view(window, VIEW_BOTH, 1)
    window.switch_to()
    window.on_draw()
    first = read_rgba()
    window.state.hud_visible = False
    window.on_draw()
    without_hud = read_rgba()
    window.state.hud_visible = True
    window.on_draw()
    second = read_rgba()
    assert changed_pixels(first, without_hud) > 50  # the HUD really draws
    assert second == first


def test_f9_bench_path_runs_in_the_window_and_leaves_the_scene_alone(window, capsys):
    reset_window(window)
    scene = window.scene
    positions = list(scene.control_positions)
    views_before = set(scene.views)
    # the F9 key runs the full plan (minutes); this calls the same method with a tiny plan
    report = window.run_bench(runs=2, plan=(("subd_cube", (1,)),), budget_s=5.0)
    out = capsys.readouterr().out
    assert "Bench startet" in out and "Subdivision-Lab — Messung" in out
    assert "unlabeled" in report and "headless" in report  # hidden test window is labeled as such
    assert window.state.note and "Bench fertig" in window.state.note
    assert scene.control_positions == positions and set(scene.views) == views_before
    assert gl_error() == 0


def test_hud_surface_counts_stay_while_ab_shows_the_cage(window):
    reset_window(window)
    window.state.set_derived_counts(None)
    select_view(window, VIEW_BOTH, 1)
    counts = window.state.derived_counts
    assert counts == (1298, 1296)
    window.on_key_press(key.B, 0)  # A/B on: the cage is shown, the built level is still the selected one
    assert window.state.ab_active and window.state.derived_counts == counts
    window.on_key_press(key.B, 0)
    assert window.state.derived_counts == counts
