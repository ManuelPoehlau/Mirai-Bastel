"""P1c in a real GL context (needs pyglet and a display; `xvfb-run -a` in a container): the limbus GLSL against
`limbus_model`, L0 = P1b pixel for pixel, the band's effect per level, the asymmetry and colour-source switches,
GL state, and a small probe run."""

from __future__ import annotations

import json

import numpy as np
import pytest

from lookdev_gpu_probe import cube_math as cm
from lookdev_gpu_probe import probe_gl_caps as pg
from lookdev_eye_lab import cornea_optics as co
from lookdev_eye_lab import gl_lab, iris_fit, iris_source, lab_scene
from lookdev_eye_lab import limbus_gl as lg, limbus_model as lm, limbus_parity as lp
from lookdev_eye_lab import refraction_gl as rg
from lookdev_eye_lab._paths import CACHE_DIR

W, H = 320, 240


@pytest.fixture(scope="module")
def gl_context():
    import pyglet
    from pyglet import gl

    window = pyglet.window.Window(width=32, height=32, visible=False)
    window.switch_to()
    yield gl
    window.close()


@pytest.mark.parametrize("case", lp.cases(), ids=lambda c: c.func)
def test_limbus_glsl_matches_the_python_model(gl_context, case):
    res = pg.Resources(gl_context)
    pp = lg.LimbusParityPass(gl_context, res, lp.PARAMS)
    try:
        err, bad, compared = lp.errors(case, pp.run(case.func, case.inputs))
        assert pg.drain_errors(gl_context) == []
    finally:
        pp.release()
        res.release_all()
    assert compared > 0.9 * len(case.inputs)
    assert bad == 0, f"{case.func}: max abs error {err:.3g}"


def _render(scene, target):
    target.bind()
    scene.renderer.frame(scene.viewport, target.width, target.height)
    target.unbind()
    return target.read_rgb()


def _view(scene, view):
    scene.apply_view(view, lab_scene.close_up_distance(W, H))
    scene.set_aspect(W, H)
    scene.camera_moved()


def _scenes(out_dir, technique="T-B"):
    refr = rg.build_scene(rg.RefractionState(show_references=False, technique=technique, refraction="V2"), out_dir,
                          CACHE_DIR, W, H)
    limb = lg.build_scene(lg.LimbusState(show_references=False, technique=technique), out_dir, CACHE_DIR, W, H)
    return refr, limb


@pytest.fixture
def scenes(gl_context, tmp_path):
    refr, limb = _scenes(tmp_path)
    target = gl_lab.Target(gl_context, limb.renderer.res, W, H)
    yield refr, limb, target
    target.release()
    limb.release()
    refr.release()


@pytest.mark.parametrize("technique", ["T-B", "T-C", "T-D"])
def test_l0_is_p1b_pixel_for_pixel(scenes, technique):
    refr, limb, target = scenes
    for refraction in ("V2", "V3"):
        for state in (refr.renderer.state, limb.renderer.state):
            state.technique, state.refraction = technique, refraction
        limb.renderer.state.limbus_level = "L0"
        for asym in (False, True):  # the asymmetry is inert at L0
            limb.renderer.state.asym = asym
            for view in ("front", "three_quarter"):
                _view(refr, view)
                _view(limb, view)
                assert np.array_equal(_render(refr, target), _render(limb, target)), (refraction, asym, view)


def _sclera_band_masks(camera):
    """Pixels whose ray hits the sclera (not through the cornea) inside the band (u 0.1 .. 0.8 mm) and well outside it
    (u > 2 mm)."""
    eye, d = co.camera_rays(camera, W, H)
    hit, t = co.sphere_entry(eye, d, np.zeros(3), 1.0)
    p = eye + t[..., None] * d
    sclera = hit & (p[..., 2] < co.GEOMETRY.limbus_z)
    u = lm.sclera_u(p) / lm.MM
    return sclera & (u > 0.1) & (u < 0.8), sclera & (u > 2.0)


def test_levels_change_the_band_and_leave_the_sclera_beyond_it(scenes):
    _refr, limb, target = scenes
    state = limb.renderer.state
    _view(limb, "front")
    images = {}
    for level in lm.LEVELS:
        state.limbus_level = level
        images[level] = _render(limb, target).astype(int)
    band, beyond = _sclera_band_masks(limb.camera)
    assert band.sum() > 200 and beyond.sum() > 1000
    lum = {k: img.mean(axis=-1) for k, img in images.items()}
    # L1 darkens the sclera band toward the (dark) limbal colour; the sclera beyond the band is unchanged (<= 1 LSB).
    assert lum["L1"][band].mean() < lum["L0"][band].mean() - 10
    for level in ("L1", "L2", "L3"):
        assert np.abs(images[level][beyond] - images["L0"][beyond]).max() <= 1, level
    # Each level adds something of its own in the band.
    for a, b in (("L1", "L2"), ("L2", "L3")):
        assert np.any(images[a][band] != images[b][band]), (a, b)


def test_asymmetry_only_affects_top_and_bottom(scenes):
    _refr, limb, target = scenes
    state = limb.renderer.state
    state.limbus_level = "L1"
    _view(limb, "front")
    off = _render(limb, target).astype(int)
    state.asym = True
    on = _render(limb, target).astype(int)
    change = np.abs(on - off).sum(axis=-1)
    from lookdev_eye_lab import eye_geometry as geo, probe_refraction

    cx, cy, _ = probe_refraction.project(limb.camera, (0.0, 0.0, geo.LIMBUS_Z), W, H)
    ys, xs = np.mgrid[0:H, 0:W]
    dx, dy = xs - cx, ys - cy
    top_bottom = np.abs(dy) > 2.0 * np.abs(dx)
    left_right = np.abs(dx) > 2.0 * np.abs(dy)
    assert change[top_bottom].sum() > 1000
    # The shift is A sin^2(azimuth): small but not zero near horizontal (sin^2 <= 0.2 in these sectors).
    assert change[left_right].mean() < 0.25 * change[top_bottom].mean()


def _custom(out_dir, edge_colour=(0.9, 0.1, 0.1)):
    size = 256
    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    y, x = np.meshgrid(c, c, indexing="ij")
    rho = np.hypot(x, y)
    rgb = np.empty((size, size, 3))
    rgb[...] = (0.3, 0.4, 0.5)
    rgb[(rho > 0.70) & (rho < 0.95)] = edge_colour
    rgb[rho < 0.2] = 0.01
    path = out_dir / iris_source.CUSTOM_NAME
    cm.write_png(path, rgb)
    return path


def test_colour_source_switch_uses_the_images_outer_ring(gl_context, tmp_path):
    custom = _custom(tmp_path)
    sidecar = tmp_path / iris_fit.SIDECAR_NAME
    sidecar.write_text(json.dumps({"pupil": 0.2, "limbus": 0.88, "hold_outer_color": True}), encoding="utf-8")
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (custom, sidecar)]
    limb = lg.build_scene(lg.LimbusState(show_references=False, technique="T-B", limbus_level="L1"), tmp_path,
                          CACHE_DIR, W, H)
    target = gl_lab.Target(gl_context, limb.renderer.res, W, H)
    try:
        r = limb.renderer
        assert r.image_colour is not None and "0.83-0.88" in r.image_note
        assert r.image_colour[0] > 0.6 and r.image_colour[1] < 0.05  # the red ring, linear light
        _view(limb, "front")
        band, _ = _sclera_band_masks(limb.camera)
        shader = _render(limb, target).astype(int)
        limb.renderer.state.colour_source = "image"
        image = _render(limb, target).astype(int)
        redness = lambda img: float(np.mean(img[band][:, 0] - img[band][:, 1]))  # noqa: E731
        assert redness(image) > redness(shader) + 10
        assert "image" in lg.describe(limb.renderer.state, r)[0]
        assert pg.drain_errors(gl_context) == []
    finally:
        target.release()
        limb.release()
    assert [(p.read_bytes(), p.stat().st_mtime_ns) for p in (custom, sidecar)] == before


def test_image_colour_falls_back_to_the_shader_colour(tmp_path):
    colour, note = lm.image_limbal_colour(tmp_path / "missing.png")
    assert colour is None and "not available" in note
    state = lg.LimbusState(colour_source="image", limbus_level="L1", technique="T-B")
    renderer = lg.LimbusRenderer.__new__(lg.LimbusRenderer)  # no GL needed for the colour choice
    renderer.state, renderer.image_colour, renderer.image_note = state, None, note
    assert renderer.limbal_albedo() == tuple(float(v) for v in lm.em.srgb_decode(lm.SHADER_COLOURS["P1b dark"]))
    assert "-> shader" in lg.describe(state, renderer)[0]


def test_limbus_passes_leave_the_gl_state_opaque_and_clean(scenes, gl_context):
    import ctypes

    gl = gl_context
    _refr, limb, target = scenes
    for level in ("L1", "L3"):
        limb.renderer.state.limbus_level = level
        _view(limb, "three_quarter")
        _render(limb, target)
        assert not gl.glIsEnabled(gl.GL_BLEND) and not gl.glIsEnabled(gl.GL_CULL_FACE)
        mask = gl.GLboolean()
        gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK, ctypes.byref(mask))
        assert mask.value
    assert pg.drain_errors(gl) == []


def test_ray_class_map_and_v1_ignore_the_limbus_level(scenes):
    refr, limb, target = scenes
    limb.renderer.state.limbus_level = "L3"
    for scene in (refr, limb):
        _view(scene, "front")
    refr.renderer.debug_kind = limb.renderer.debug_kind = True
    try:
        assert np.array_equal(_render(refr, target), _render(limb, target))
    finally:
        refr.renderer.debug_kind = limb.renderer.debug_kind = False
    refr.renderer.state.refraction = limb.renderer.state.refraction = "V1"
    assert np.array_equal(_render(refr, target), _render(limb, target))


def test_small_limbus_probe_run_passes_every_check(gl_context, tmp_path):
    from lookdev_eye_lab import probe_limbus

    lines = probe_limbus.run(probe_limbus.quick_args(str(tmp_path)))
    text = "\n".join(lines)
    summary = lines[lines.index("Summary (raw verdicts - label them by machine in the results file):") + 1:]
    assert summary and all(line.split()[0] == "PASS" for line in summary), text
    for check in ("P limbus parity", "I L0 = P1b", "V every run", "R hygiene"):
        assert any(check in line for line in summary), check
    assert any(line.startswith("[C] continuity") for line in lines)
    assert (tmp_path / "limbus_sheet.png").exists()


def test_limbus_window_keys_and_frames(gl_context):
    import sys
    from pathlib import Path

    from pyglet.window import key

    lab = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(lab))
    try:
        import run_limbus
    finally:
        sys.path.remove(str(lab))
    window = run_limbus.LimbusWindow(run_limbus.build_parser().parse_args(["--size", "320", "240"]))
    try:
        for symbol in (key.Q, key.Q, key.Q, key.A, key.O, key.N, key.W, key.D, key.COMMA, key.PERIOD, key.F1):
            assert window.on_key_press(symbol, 0)
            window.on_draw()
        assert window.state.limbus_level == "L3" and window.state.asym
        assert pg.drain_errors(gl_context) == []
    finally:
        window.scene.release()
        window.window.close()


@pytest.mark.parametrize("level", ["L1", "L2", "L3"])
def test_asymmetry_has_no_seam_left_and_right(gl_context, tmp_path, level):
    """Regression (Manu, reference PC 2026-11-14): with the asymmetry on, a seam left and right, centred on the limbus
    edge, clearest in L1 / L2. Along an arc on the cornea just inside the visible iris edge (u -0.22 mm), the change the
    asymmetry makes must fade to 0 toward the horizontal with no jump, and stay in place at top and bottom."""
    import math

    from lookdev_eye_lab import probe_refraction

    w, h = 1024, 768
    limb = lg.build_scene(lg.LimbusState(show_references=False, technique="T-B", limbus_level=level), tmp_path,
                          CACHE_DIR, w, h)
    target = gl_lab.Target(gl_context, limb.renderer.res, w, h)
    try:
        limb.apply_view("front", lab_scene.close_up_distance(w, h))
        limb.set_aspect(w, h)
        limb.camera_moved()
        images = {}
        for asym in (False, True):
            limb.renderer.state.asym = asym
            target.bind()
            limb.renderer.frame(limb.viewport, w, h)
            target.unbind()
            images[asym] = target.read_rgb().astype(float) @ np.array([0.2126, 0.7152, 0.0722])
        deg = np.arange(-180.0, 180.0, 0.5)
        r = lm.RING_RADIUS - 0.22 * lm.MM
        z = float(co.GEOMETRY.anterior_z(r))
        px = [probe_refraction.project(limb.camera, (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), z),
                                       w, h)[:2] for a in deg]
        rows, cols = np.array([int(round(y)) for _, y in px]), np.array([int(round(x)) for x, _ in px])
        diff = np.abs(images[True][rows, cols] - images[False][rows, cols])
        on = images[True][rows, cols]

        def near(a):
            return diff[np.abs(((deg - a + 180.0) % 360.0) - 180.0) <= 3.0].max()

        assert near(0.0) <= 2.0 and near(180.0) <= 2.0  # nothing changes on the horizontal ...
        sector = np.abs(((deg + 180.0) % 180.0) - 90.0) >= 75.0  # ... nor within 15 degrees of it ...
        assert np.abs(np.diff(on))[sector[1:] & sector[:-1]].max() <= np.abs(np.diff(images[False][rows, cols])).max()
        assert diff[np.abs(deg - 90.0) <= 3.0].mean() > 5.0  # ... and the cover is there at the top
        assert pg.drain_errors(gl_context) == []
    finally:
        target.release()
        limb.release()
