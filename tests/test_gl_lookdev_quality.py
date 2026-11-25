"""AD-040 LD-3a in the real GL path (§10.1): Hoch without refinement is the AD-039 frame pixel for pixel (G-1), the
frame signature changes for every input of `_render_lookdev` and for nothing else (G-6), the GL state after a frame of
each configuration (G-8), `shadow_updates` while a caster is dragged (G-9), the precompiled union (G-10), the capture in
each state (G-11), the Worklight creating nothing (G-13), and the GPU timer (§4.1).

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_lookdev_quality.py -q`."""

from __future__ import annotations

import dataclasses

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from tests.test_gl_lookdev_shadow import (BOX, SIZE, _box, _full_state, _ground, _state, _viewport,  # noqa: E402,F401
                                          gl_window, head_app)
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport import lookdev_features  # noqa: E402
from viewport import lookdev_optics as lo  # noqa: E402
from viewport import lookdev_quality as lq  # noqa: E402
from viewport.lookdev_pass import LookDraw  # noqa: E402

ALL = lo.LookdevEffects(area_diffuse=True, soft_shadow=True)


def _tick(gl_window, app, dt: float = 0.0) -> np.ndarray:
    """One app frame as `main.py` draws it (tick, clear, render) at `dt`; the frame's pixels (row 0 = bottom)."""
    from pyglet import gl

    gl_window.switch_to()
    app.update_viewport(dt)
    return _draw(gl_window, app)


def _draw(gl_window, app) -> np.ndarray:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, SIZE, SIZE)
    gl.glClearColor(0.0, 0.0, 0.0, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    app.viewport.render()
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return np.frombuffer(bytes(buf), dtype=np.uint8).reshape(SIZE, SIZE, 3).astype(int)


def _open(gl_window, app, effects=ALL, **quality) -> None:
    for name in lo.LookdevEffects.names():
        app.set_lookdev_effect(name, getattr(effects, name))
    if quality:
        app.set_lookdev_quality(**quality)
    assert app.open_lookdev()
    for _ in range(4):
        _tick(gl_window, app)
    assert app.viewport.shading == "lookdev" and not app.lookdev.preparing


def _settle(gl_window, app, until=lq.CONVERGED) -> np.ndarray:
    for _ in range(40):
        frame = _tick(gl_window, app, 0.1)
        if app.lookdev_activity == until:
            return frame
    raise AssertionError(app.lookdev_activity)


# -- G-1: refinement off, Hoch = the AD-039 frame ----------------------------------------------------------------------

@pytest.mark.parametrize("preset", ["Portrait", "Dramatic"])
@pytest.mark.parametrize("surface", ["cage", "subd1"])
def test_hoch_without_refinement_draws_the_ad039_frame_pixel_for_pixel(gl_window, head_app, preset, surface):
    """Q3: with „In Ruhe verfeinern“ off and the tier at Hoch (here Auto, which starts at Hoch) the room's frame is the
    frame of the AD-039 path (no configuration: `set_lookdev_config(None)`), in each activity state - every effect on,
    S8 and S9 included."""
    app = head_app
    assert app.subdivision.set_view("off" if surface == "cage" else "cage")
    app.set_lookdev_studio_preset(preset)
    _open(gl_window, app)
    if surface == "subd1":  # the posed SubD 1 surface is drawn
        faces = len(list(app.viewport.surface_render_mesh.mesh.all_face_ids()))
        assert faces > len(list(app.scene.mesh.all_face_ids()))
    frames = {}
    for state in (lq.INTERACTIVE, lq.CONVERGED):
        if state == lq.CONVERGED:
            _settle(gl_window, app)
        else:
            app.jaw(12.0)
            _tick(gl_window, app)
            assert app.lookdev_activity == lq.INTERACTIVE
        config = app.viewport.lookdev_config
        assert config == lq.RenderConfig(app.viewport.lookdev_effects(wanted=False), 1024, "every", 64)
        assert config.effects.soft_shadow and config.effects.area_diffuse
        with_config = _draw(gl_window, app)
        app.viewport.set_lookdev_config(None)
        frames[state] = _draw(gl_window, app)
        assert np.array_equal(with_config, frames[state]), state
    assert frames[lq.INTERACTIVE].sum() > 0 and app.viewport.lookdev_pass.shadow_max is None
    assert app.viewport.lookdev_pass.cube_max is None


# -- G-6: the signature ------------------------------------------------------------------------------------------------

def _signature_viewport(gl_window):
    from mirai.eye_object import DEFAULT_EYE, cornea_triangles, shell_mesh
    from viewport.eye_pass import EyeDraw
    from viewport.live_texture import LiveTexture
    from viewport.material import DEFAULT_FINISH

    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    live = LiveTexture(np.zeros((8, 8, 4), np.uint8))
    region = LookDraw((0.8, 0.2, 0.2), roughness=0.4)
    look = LookDraw((0.5, 0.5, 0.5), albedo=live, roughness_map="r.png", regions=(region,),
                    region_faces=((0, 1),))
    viewport.set_object_entry("box", _box(*BOX), (0.5, 0.5, 0.5), look=look)
    grey = (0.6, 0.6, 0.6)
    eye_model = [0.4, 0, 0, 0, 0, 0.4, 0, 0, 0, 0, 0.4, 0, 0.5, 0.3, 0.6, 1.0]
    eye = EyeDraw(DEFAULT_EYE, None, grey, DEFAULT_FINISH, cornea_triangles())
    viewport.set_object_entry("eye", shell_mesh(DEFAULT_EYE), grey, model_matrix=eye_model, finish=DEFAULT_FINISH,
                              eye=eye)
    viewport.set_shading("lookdev", _state(effects=ALL))
    return viewport, live, look, eye, eye_model


def test_every_input_of_the_frame_changes_the_signature_and_nothing_else_does(gl_window):
    """AD-040 §3.1 / G-6: each input of `_render_lookdev` mutated in turn changes the signature; drawing a frame, a
    capture request, a status line and the overlays (wire, hover layers) do not."""
    from viewport.eye_pass import EyeDisplay

    viewport, live, look, eye, eye_model = _signature_viewport(gl_window)
    size, quality = (SIZE, SIZE), ("hoch", False, "hoch", "every")

    def sig(**kw):
        viewport.sync()
        return viewport.lookdev_signature(kw.get("size", size), kw.get("quality", quality))

    from tests.test_gl_lookdev_shadow import _frame

    _frame(gl_window, viewport)
    seen = [sig()]

    def changed(what, **kw):
        value = sig(**kw)
        assert value not in seen, what
        seen.append(value)

    state = viewport.lookdev_state
    camera = viewport.render_mesh.camera
    camera.orbit(0.2, 0.0)
    viewport.on_camera_changed(aspect=1.0)
    changed("camera")
    viewport.on_camera_changed(aspect=1.5)
    changed("projection (aspect)")
    changed("framebuffer size", size=(SIZE, SIZE + 1))
    box = viewport.object_entries["box"]
    vertex = next(iter(box.mesh.all_vertex_ids()))
    box.mesh.set_vertex_position(vertex, (0.0, 1.5, 0.0))
    box.mark_vertices_dirty({vertex})
    changed("mesh content (a pose / morph / sculpt step)")
    box.mark_topology_dirty()
    changed("mesh layout")
    viewport.set_object_entry("box", box.mesh, (0.5, 0.5, 0.5), look=look,
                              model_matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0.1, 0, 0, 1])
    changed("model matrix")
    viewport.set_shading("lookdev", dataclasses.replace(state, exposure=1.5))
    changed("studio value")
    viewport.set_shading("lookdev", dataclasses.replace(state, key=dataclasses.replace(state.key, azimuth=10.0)))
    changed("a light")
    viewport.set_shading("lookdev", dataclasses.replace(state, effects=dataclasses.replace(ALL, cube=False)))
    changed("an effect (drawn state)")
    viewport.set_lookdev_effects(dataclasses.replace(ALL, maps=False))
    changed("an effect (wanted)")
    for field, value in (("roughness", 0.2), ("base_color", (0.1, 0.2, 0.3)), ("roughness_map", "other.png"),
                         ("regions", (dataclasses.replace(look.regions[0], roughness=0.9),)),
                         ("region_faces", ((0, 2),))):
        look = dataclasses.replace(look, **{field: value})
        viewport.set_object_entry("box", box.mesh, (0.5, 0.5, 0.5), look=look,
                                  model_matrix=[1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0.1, 0, 0, 1])
        changed(f"LookDraw {field}")
    live.mark(0, 0, 2, 2)
    changed("paint revision")
    viewport.set_object_entry("eye", viewport.object_entries["eye"].mesh, (0.6, 0.6, 0.6),
                              model_matrix=[*eye_model[:12], 0.4, 0.3, 0.6, 1.0], finish=eye.finish, eye=eye)
    changed("eye model (gaze)")
    viewport.set_object_entry("eye", viewport.object_entries["eye"].mesh, (0.6, 0.6, 0.6),
                              model_matrix=[*eye_model[:12], 0.4, 0.3, 0.6, 1.0], finish=eye.finish,
                              eye=dataclasses.replace(eye, sclera_colour=(0.9, 0.8, 0.8)))
    changed("eye draw value")
    viewport.set_eye_display(tier="fast" if viewport.eye_display.tier == "full" else "full")
    changed("eye display")
    changed("quality settings", quality=("mittel", False, "hoch", "every"))
    viewport.lookdev_pass.features = lookdev_features.FeatureReport(cube_rgba16f=False)
    changed("feature report")
    viewport.show_faces = False
    changed("edit object shown")
    # nothing else: a frame, a capture, the overlays
    before = sig()
    viewport.request_capture(lambda rgba: None)
    _frame(gl_window, viewport)
    viewport.line_layers["hover"] = []
    viewport.face_layers = dict(getattr(viewport, "face_layers", {}))
    assert sig() == before
    _frame(gl_window, viewport)
    assert sig() == before
    for entry in list(viewport.object_entries):
        viewport.remove_object_entry(entry)
    viewport._lookdev_pass.release()
    viewport.eye_pass.release()
    assert isinstance(viewport.eye_display, EyeDisplay)


# -- G-8: the GL state per configuration -------------------------------------------------------------------------------

@pytest.mark.parametrize("config", [
    lq.RenderConfig(ALL, 1024, "every", 64), lq.RenderConfig(ALL, 2048, "every", 256),
    lq.RenderConfig(dataclasses.replace(ALL, soft_shadow=False), 1024, "frozen", 64),
    lq.resolve("entwurf", ALL)], ids=["hoch", "maximal", "mittel-frozen", "entwurf"])
def test_a_frame_of_each_configuration_leaves_the_gl_state_as_found(gl_window, config):
    """I-4 / G-8: both maps, both cubes - no FBO bound, units 0-8 as found (6-8 unbound), unit 0 active."""
    from pyglet import gl

    from mirai.eye_object import DEFAULT_EYE, cornea_triangles, shell_mesh
    from tests.test_gl_lookdev_shadow import _frame
    from viewport.eye_pass import EyeDraw
    from viewport.material import DEFAULT_FINISH

    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    grey = (0.6, 0.6, 0.6)
    eye_model = [0.4, 0, 0, 0, 0, 0.4, 0, 0, 0, 0, 0.4, 0, 0.5, 0.3, 0.6, 1.0]
    viewport.set_object_entry("eye", shell_mesh(DEFAULT_EYE), grey, model_matrix=eye_model, finish=DEFAULT_FINISH,
                              eye=EyeDraw(DEFAULT_EYE, None, grey, DEFAULT_FINISH, cornea_triangles()))
    viewport.set_eye_display(tier="full")
    state = _state(effects=ALL, studio=lo.EYE_STUDIO, env_intensity=1.0)
    viewport.set_shading("lookdev", state)
    viewport.set_lookdev_config(config)
    viewport.lookdev_timing = True
    _frame(gl_window, viewport)  # compiles, creates the configuration's map and cube
    passes = viewport.lookdev_pass
    if config.shadow_size == 2048 and config.effects.shadow:
        assert passes.shadow_max is not None and passes.shadow_max.ready and passes.shadow is None
    if config.cube_samples == 256:
        assert passes.cube_max is not None and passes.cube_max.ready and passes.cube_max.samples == 256
    for change in range(2):
        viewport.set_shading("lookdev", dataclasses.replace(state, rotation=10.0 * (change + 1)))
        gl.glUseProgram(0)
        gl.glEnable(gl.GL_SCISSOR_TEST)
        gl.glPolygonOffset(0.5, 0.25)
        before = _full_state()
        _frame(gl_window, viewport)
        after = _full_state()
        assert after == before
        assert after["draw_fbo"] == 0 and after["read_fbo"] == 0 and after["active_texture"] == gl.GL_TEXTURE0
        for unit in (6, 7):
            assert after[f"unit{unit}"] == (0, 0, 0)
        gl.glActiveTexture(gl.GL_TEXTURE0 + 8)
        cube = gl.GLint()
        gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_CUBE_MAP, cube)
        gl.glActiveTexture(gl.GL_TEXTURE0)
        assert cube.value == 0
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glPolygonOffset(0.0, 0.0)
    for entry in list(viewport.object_entries):
        viewport.remove_object_entry(entry)
    passes.release()
    assert passes.shadow_max is None and passes.cube_max is None and passes.gpu_timer is None
    viewport.eye_pass.release()


# -- G-9: the key map while a caster is dragged ------------------------------------------------------------------------

def _drag(gl_window, app, frames: int) -> None:
    for i in range(frames):
        app.set_morph_weight(30 + 3 * (i % 7) + 1, app.lid, quiet=True)
        _tick(gl_window, app, 1 / 60)
        assert app.lookdev_activity == lq.INTERACTIVE


@pytest.mark.parametrize("policy, renders", [("every", 8), ("every_2nd", 4), ("frozen", 0)])
def test_the_key_map_while_a_caster_is_dragged(gl_window, head_app, policy, renders):
    """§2.2 / G-9: „frozen“ keeps the map through a drag and renders it once in the first Settling frame; „every_2nd“
    renders every second frame; „every“ every frame (today)."""
    app = head_app
    _open(gl_window, app, lo.LookdevEffects(), tier="hoch", drag_updates=policy)
    shadow = app.viewport.lookdev_pass.shadow
    assert shadow is not None and shadow.ready
    count = shadow.renders
    _drag(gl_window, app, 8)
    assert shadow.renders - count == renders, (policy, shadow.renders - count)
    lagging = shadow._postponed > 0
    assert lagging == (policy == "frozen") or policy == "every_2nd"
    count = shadow.renders
    _tick(gl_window, app, 1 / 60)  # quiet: Settling, the map brought up to date if it lagged
    assert app.lookdev_activity == lq.SETTLING
    assert shadow.renders - count == (1 if lagging else 0)
    count = shadow.renders
    _tick(gl_window, app, 1 / 60)
    assert shadow.renders == count


def test_entwurf_draws_no_shadow_and_a_tier_change_compiles_nothing(gl_window, head_app):
    """G-10: entering with Auto and refinement compiles the union of every configuration; switching the tier, the
    refinement's idle tier and Auto's steps afterwards compile nothing (the program caches unchanged)."""
    app = head_app
    _open(gl_window, app, ALL, tier="auto", refine=True, idle_tier="maximal")
    passes, eyes = app.viewport.lookdev_pass, app.viewport.eye_pass
    skin_keys, eye_keys = set(passes.programs), set(eyes.programs)
    wanted, _ = app.viewport._lookdev_programs()
    assert set(wanted) <= skin_keys
    assert any(len(k) == 12 and k[-1] for k in skin_keys)  # S9 (idle) compiled
    assert any(not k[2] for k in skin_keys)  # Entwurf (no shadow) compiled
    for tier in ("entwurf", "mittel", "hoch", "auto"):
        assert app.set_lookdev_quality(tier=tier)
        assert not app.lookdev.preparing
        _tick(gl_window, app)
    app.lookdev.auto.tier = "entwurf"  # Auto stepping down
    frame = _tick(gl_window, app)
    assert not app.viewport.lookdev_config.effects.shadow and frame.sum() > 0
    _settle(gl_window, app)
    assert set(passes.programs) == skin_keys and set(eyes.programs) == eye_keys


# -- refinement in the app ---------------------------------------------------------------------------------------------

def test_with_refinement_s9_appears_after_the_wait_and_leaves_on_a_change(gl_window, head_app):
    """F-R3 / §12.1 practical test: with „In Ruhe verfeinern“ (Maximal) the working frame has no S9; after 0.3 s the
    room draws S9 with the 2048² map and the 256-sample cube; an orbit returns to the working frame in that tick."""
    app = head_app
    _open(gl_window, app, ALL, tier="hoch", refine=True, idle_tier="maximal")
    app.jaw(12.0)
    working = _tick(gl_window, app)
    assert app.lookdev_activity == lq.INTERACTIVE and not app.viewport.lookdev_config.effects.soft_shadow
    passes = app.viewport.lookdev_pass
    assert passes.shadow_max is None and passes.cube_max is None
    _tick(gl_window, app, 0.1)
    assert app.lookdev_activity == lq.SETTLING
    _tick(gl_window, app, 0.1)
    _tick(gl_window, app, 0.1)
    assert app.lookdev_activity == lq.SETTLING
    refined = _tick(gl_window, app, 0.1)  # 0.3 s quiet
    assert app.lookdev_activity == lq.REFINE
    assert passes.shadow_max is not None and passes.shadow_max.ready and passes.cube_max.ready
    assert not np.array_equal(refined, working)
    assert app.lookdev_quality_status() == "Ruhe – Maximal"
    _tick(gl_window, app, 0.1)
    assert app.lookdev_activity == lq.CONVERGED
    renders = passes.shadow_max.renders
    for _ in range(3):
        _tick(gl_window, app, 0.1)
    assert passes.shadow_max.renders == renders and passes.cube_max.prefilters == 1  # nothing re-rendered at rest
    app.camera.orbit(0.0, 0.0)  # unchanged view: no change
    app.camera.set_view(app.camera.yaw + 0.05, app.camera.pitch)
    app._camera_changed()
    back = _tick(gl_window, app, 0.0)
    assert app.lookdev_activity == lq.INTERACTIVE and not app.viewport.lookdev_config.effects.soft_shadow
    assert back.sum() > 0


# -- G-11: the capture in each state -----------------------------------------------------------------------------------

def test_the_capture_saves_what_the_room_shows_in_each_state(gl_window, head_app):
    """§7 / G-11: Interactive saves the working configuration, Converged the idle one; the capture neither waits nor
    changes the state or the signature."""
    app = head_app
    _open(gl_window, app, ALL, tier="mittel", refine=True, idle_tier="maximal")
    images = {}
    app.jaw(12.0)
    for state in (lq.INTERACTIVE, lq.CONVERGED):
        if state == lq.CONVERGED:
            _settle(gl_window, app)
        else:
            app.update_viewport(0.0)
        assert app.lookdev_activity == state
        signature = app.viewport.lookdev_signature((app.viewport_width, app.viewport_height), app._quality_key())
        shown = _draw(gl_window, app)  # the frame the room shows in this state
        got = []
        app.viewport.request_capture(got.append)
        _draw(gl_window, app)
        assert len(got) == 1
        image = got[0][::-1, :, :3].astype(int)  # top row first -> row 0 = bottom
        assert np.array_equal(image, shown), state
        assert app.lookdev_activity == state
        assert app.viewport.lookdev_signature((app.viewport_width, app.viewport_height),
                                              app._quality_key()) == signature
        app.update_viewport(0.0)  # the capture is no change: Interactive settles, Converged stays
        assert app.lookdev_activity == (lq.SETTLING if state == lq.INTERACTIVE else lq.CONVERGED)
        images[state] = image
        app.lookdev.quality_frame = (state, app._quality_tier())
        assert app._capture_state_text() == ("interaktiv (Mittel)" if state == lq.INTERACTIVE else "Ruhe (Maximal)")
    assert not np.array_equal(images[lq.INTERACTIVE], images[lq.CONVERGED])


def test_save_lookdev_image_names_the_state(gl_window, head_app, tmp_path):
    app = head_app
    _open(gl_window, app, ALL, tier="hoch", refine=True, idle_tier="maximal")
    _settle(gl_window, app)
    assert app.save_lookdev_image(tmp_path / "x.png")
    _tick(gl_window, app, 0.1)
    assert (tmp_path / "x.png").exists()
    assert app.status_message.endswith("– Ruhe (Maximal)"), app.status_message
    assert app.lookdev_activity == lq.CONVERGED


# -- §4.1: the timer, G-13 ---------------------------------------------------------------------------------------------

def test_the_timer_measures_lookdev_frames_without_blocking_and_feeds_auto(gl_window, head_app):
    app = head_app
    _open(gl_window, app, lo.LookdevEffects(), tier="auto")
    timer = app.viewport.lookdev_pass.gpu_timer
    assert timer is not None
    for i in range(12):
        app.camera.set_view(app.camera.yaw + 0.01, app.camera.pitch)
        app._camera_changed()
        _tick(gl_window, app, 1 / 60)
    assert timer.measured > 0
    assert len(app.lookdev.auto._times) > 0 and app.lookdev.auto.tier == "hoch"
    assert app.lookdev_quality_status().startswith("Interaktiv – Hoch (Auto")


def test_the_timer_skips_a_frame_inside_another_query(gl_window, head_app):
    """A probe's own `GL_TIME_ELAPSED` around `Viewport.render()`: the room does not nest a query (no GL error)."""
    import ctypes

    from pyglet import gl

    app = head_app
    _open(gl_window, app, lo.LookdevEffects(), tier="auto")
    timer = app.viewport.lookdev_pass.gpu_timer
    skipped = timer.skipped
    query = gl.GLuint()
    gl.glGenQueries(1, ctypes.byref(query))
    app.update_viewport(1 / 60)
    gl.glBeginQuery(gl.GL_TIME_ELAPSED, query.value)
    _draw(gl_window, app)
    gl.glEndQuery(gl.GL_TIME_ELAPSED)
    assert gl.glGetError() == gl.GL_NO_ERROR and timer.skipped == skipped + 1
    gl.glDeleteQueries(1, ctypes.byref(query))


def test_without_a_timer_auto_holds_mittel_with_a_status(gl_window, head_app, monkeypatch):
    monkeypatch.setitem(lookdev_features.CHECKS, "timer_query", lambda: False)
    app = head_app
    _open(gl_window, app, lo.LookdevEffects(), tier="auto")
    _tick(gl_window, app)
    assert app.viewport.lookdev_pass.gpu_timer is None
    assert app.lookdev.auto.tier == "mittel"
    assert app.lookdev_quality_status() == "Interaktiv – Mittel (Auto aus – Zeitmessung nicht verfügbar)"
    app.close_lookdev()
    app.lookdev.auto.available = True  # the module-wide app is reused by later tests


def test_the_worklight_creates_no_timer_or_second_instance(gl_window, head_app):
    """Q4 / G-13: the Worklight frame before and after the room: no LookDev pass, timer, configuration or tracker."""
    app = head_app
    for _ in range(3):
        _tick(gl_window, app, 1 / 60)
    assert app.viewport._lookdev_pass is None and app.lookdev_activity is None
    assert app.viewport.lookdev_config is None and not app.viewport.lookdev_timing
    _open(gl_window, app, ALL, tier="hoch", refine=True, idle_tier="maximal")
    _settle(gl_window, app)
    passes = app.viewport.lookdev_pass
    assert passes.shadow_max is not None and passes.gpu_timer is not None
    app.close_lookdev()
    _tick(gl_window, app, 1 / 60)
    assert app.lookdev_activity is None and app.viewport.lookdev_config is None
    assert not app.viewport.lookdev_timing and app.viewport.shading == "worklight"
    timer = passes.gpu_timer
    measured = timer.measured + len(timer._pending)
    for _ in range(3):
        _tick(gl_window, app, 1 / 60)
    assert timer.measured + len(timer._pending) == measured  # nothing timed in the Worklight
