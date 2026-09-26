"""GL tests on `head_basemesh` at a fixed 480x360 hidden window.

T1 baseline identity, T2 zero upload, T3 controls act, T7 program isolation,
T8 GL health, plus HUD state isolation and capture (E14/E15).
Run headless (EGL) or under Xvfb, pattern `experiments/symmetry_lab/tests/`.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from ._pyglet_headless import import_pyglet, needs_headless

pyglet = import_pyglet()

from viewport.gl_render_store import GLRenderStore  # noqa: E402

from viewport_shading_lab import evidence as ev  # noqa: E402
from viewport_shading_lab._paths import EXPERIMENTS_DIR  # noqa: E402
from viewport_shading_lab.lab_controls import ROW_IDS, LabState  # noqa: E402
from viewport_shading_lab.lab_rig import PRESET_HEUTE, PRESET_ORDER, PRESET_RAITT, resolve  # noqa: E402
from viewport_shading_lab.lab_store import ShadingLabStore  # noqa: E402

#: T3: a change counts when at least this many pixels differ by >= 2 levels
#: (T1 shows rounding noise is <= 1 level). Smallest measured row step
#: (Fill Temperatur ±500 K on "Raitt 2:1") changes ~900 pixels by up to 4 levels.
CHANGED_PIXELS_MIN = 100
CHANGE_LEVEL = 2


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    win = ev.open_hidden_window(captures_dir=tmp_path_factory.mktemp("captures"))
    yield win
    win.close()


def render(window, state: LabState) -> bytes:
    window.switch_to()
    return ev.render_rgba(window, resolve(state.displayed_rig(), window.scene.camera))


def changed_pixels(a: bytes, b: bytes) -> int:
    count = 0
    for i in range(0, len(a), 4):
        if max(abs(a[i] - b[i]), abs(a[i + 1] - b[i + 1]), abs(a[i + 2] - b[i + 2])) >= CHANGE_LEVEL:
            count += 1
    return count


# -- T1 ---------------------------------------------------------------------------------


def test_t1_heute_reproduces_production(window):
    prod = ev.production_scene(window)
    lab = render(window, LabState(PRESET_HEUTE))
    window.switch_to()
    prod.draw()
    from viewport_shading_lab.lab_scene import read_rgba

    production = read_rgba(ev.EVIDENCE_WIDTH, ev.EVIDENCE_HEIGHT)
    background = bytes(production[:4])
    assert sum(1 for i in range(0, len(production), 4) if production[i:i + 4] != background) > 5000, \
        "mesh not visible — comparison would be meaningless"
    assert ev.max_channel_diff(lab, production) <= 1


# -- T2 ---------------------------------------------------------------------------------


def test_t2_zero_upload_across_all_controls(window):
    window.switch_to()
    window.state.apply_preset(PRESET_HEUTE)
    window.on_draw()
    before = ev.upload_snapshot(window)
    actions, distinct_rigs = ev.exercise_all_controls(window)
    after = ev.upload_snapshot(window)
    assert actions > 100
    assert distinct_rigs > 50, "workload must really change the drawn rig"
    assert after["resource_ids"] == before["resource_ids"]
    assert after["vertex_list_id"] == before["vertex_list_id"]
    assert after["counters"] == before["counters"]
    assert after["uploaded_bytes"] == before["uploaded_bytes"]
    assert after["resources"] == before["resources"]
    # The workload really changed what is drawn.
    assert window.state.rig != LabState().rig


# -- T3 ---------------------------------------------------------------------------------


@pytest.mark.parametrize("preset", PRESET_ORDER[1:])
def test_t3_presets_differ_from_heute(window, preset):
    assert changed_pixels(render(window, LabState(PRESET_HEUTE)), render(window, LabState(preset))) \
        >= CHANGED_PIXELS_MIN


@pytest.mark.parametrize("row_id", [r for r in ROW_IDS if r != "fill_coupled"])
def test_t3_every_row_step_changes_image(window, row_id):
    state = LabState(PRESET_RAITT)  # fill enabled
    if row_id in ("fill_azimuth", "fill_elevation"):
        state.step_row("fill_coupled", +1)
    before = render(window, state)
    # Wraps start at 0 (lower clamp): step up. Everything else: step up as well.
    state.step_row(row_id, +1)
    assert changed_pixels(before, render(window, state)) >= CHANGED_PIXELS_MIN


def test_t3_coupling_row_changes_image_when_angles_differ(window):
    state = LabState(PRESET_RAITT)
    state.step_row("fill_coupled", +1)  # free, same angles: no jump (documented)
    state.step_row("fill_azimuth", +1)
    before = render(window, state)
    state.step_row("fill_coupled", +1)  # coupled again
    assert changed_pixels(before, render(window, state)) >= CHANGED_PIXELS_MIN


def test_t3_light_drag_changes_image(window):
    from pyglet.window import mouse

    window.state.apply_preset(PRESET_RAITT)
    before = render(window, window.state)
    window.on_mouse_drag(100, 100, 30, 10, mouse.LEFT, 0)
    assert changed_pixels(before, render(window, window.state)) >= CHANGED_PIXELS_MIN


def test_camera_mode_light_follows_orbit_world_mode_does_not(window):
    """F1 switch is visible: in world space the lit side stays put relative
    to the object, in camera space the uniforms follow the camera."""
    cam = window.scene.camera
    state = LabState(PRESET_RAITT)
    before_cam = resolve(state.rig, cam)
    before_world = resolve(state.rig.with_(space="world"), cam)
    cam.orbit(0.6, 0.0)
    try:
        assert resolve(state.rig, cam)["u_key_dir"] != before_cam["u_key_dir"]
        assert resolve(state.rig.with_(space="world"), cam)["u_key_dir"] == before_world["u_key_dir"]
    finally:
        cam.orbit(-0.6, 0.0)


# -- T7 ---------------------------------------------------------------------------------


def test_t7_program_isolation_in_process(window):
    window.switch_to()
    production = GLRenderStore.program()
    lab = ShadingLabStore.program()
    assert lab is not production
    assert "_program" in ShadingLabStore.__dict__
    assert "u_key_dir" in lab.uniforms and "u_light_dir" not in lab.uniforms
    assert "u_light_dir" in production.uniforms


_ISOLATION_SCRIPT = textwrap.dedent(
    """
    import json, sys
    sys.path.insert(0, {experiments!r})
    from viewport_shading_lab._paths import ensure_paths
    ensure_paths()
    import pyglet
    if {headless!r}:
        pyglet.options["headless"] = True
    window = pyglet.window.Window(32, 32, visible=False)
    from viewport.gl_render_store import GLRenderStore
    production = GLRenderStore.program()          # production compiled FIRST
    from viewport_shading_lab.lab_store import ShadingLabStore
    lab = ShadingLabStore.program()
    print(json.dumps({{
        "same": lab is production,
        "lab_uniforms": sorted(lab.uniforms),
        "parent_cache_untouched": GLRenderStore._program is production,
    }}))
    """
)


def test_t7_program_isolation_production_compiled_first():
    script = _ISOLATION_SCRIPT.format(experiments=str(EXPERIMENTS_DIR), headless=needs_headless())
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["same"] is False
    assert report["parent_cache_untouched"] is True
    assert "u_key_dir" in report["lab_uniforms"]


# -- T8 ---------------------------------------------------------------------------------


def test_t8_no_gl_error_across_presets_with_hud(window):
    from pyglet import gl

    window.switch_to()
    while gl.glGetError():
        pass
    for name in PRESET_ORDER:
        window.state.apply_preset(name)
        for ab in (False, True):
            if window.state.ab_active != ab:
                window.state.toggle_ab()
            window.on_draw()
            assert gl.glGetError() == 0, name


# -- HUD / capture (E14, E15) ---------------------------------------------------------------


def test_hud_does_not_change_next_mesh_frame(window):
    window.switch_to()
    window.state.apply_preset(PRESET_RAITT)
    if not window.state.hud_visible:
        window.state.toggle_hud()
    first = render(window, window.state)
    window.on_draw()  # mesh + HUD
    assert len(window._hud_labels) > 10
    second = render(window, window.state)
    assert first == second


def test_hud_toggle(window):
    from pyglet.window import key

    visible = window.state.hud_visible
    window.on_key_press(key.H, 0)
    assert window.state.hud_visible is not visible
    window.on_key_press(key.H, 0)
    assert window.state.hud_visible is visible


def test_capture_writes_png_without_hud_and_sidecar(window):
    from pyglet.window import key

    window.switch_to()
    window.state.apply_preset(PRESET_RAITT)
    window.on_draw()  # HUD in the back buffer before capture
    png, sidecar = window.capture()
    assert png.exists() and png.stat().st_size > 1000
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["preset"] == PRESET_RAITT
    assert data["mesh"] == "head_basemesh"
    assert data["window_size"] == [ev.EVIDENCE_WIDTH, ev.EVIDENCE_HEIGHT]
    assert data["rig"]["key_azimuth"] == -45.0
    assert set(data["camera"]) >= {"yaw_deg", "pitch_deg", "distance"}
    assert "timestamp" in data

    image = pyglet.image.load(str(png)).get_image_data()
    captured = bytes(image.get_data("RGBA", image.width * 4))
    assert captured == render(window, window.state), "capture must equal the HUD-less mesh frame"

    window.on_key_press(key.P, 0)  # key path also writes a pair
    assert len(list(png.parent.glob("*.png"))) == 2
    assert len(list(png.parent.glob("*.json"))) == 2
