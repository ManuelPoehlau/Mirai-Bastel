"""P1b in a real GL context (needs pyglet and a display; `xvfb-run -a` in a container): the refraction GLSL against
`cornea_optics`, V1 = P1 pixel for pixel, the GPU's ray classes = the CPU model's, the opaque cornea pass's depth /
blending / order, the front-view magnification, and a small probe run."""

from __future__ import annotations

import numpy as np
import pytest

from lookdev_gpu_probe import probe_gl_caps as pg
from lookdev_eye_lab import cornea_optics as co
from lookdev_eye_lab import gl_lab, lab_scene
from lookdev_eye_lab import lab_state as ls
from lookdev_eye_lab import probe_refraction, refraction_gl as rg, refraction_parity as rp
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


@pytest.fixture(scope="module")
def parity_pass(gl_context):
    res = pg.Resources(gl_context)
    pp = rg.RefractionParityPass(gl_context, res)
    yield pp
    pp.release()
    res.release_all()
    assert res.leaks() == []


@pytest.mark.parametrize("case", rp.cases(), ids=lambda c: c.func)
def test_refraction_glsl_matches_the_python_model(parity_pass, case):
    err, bad, compared = case.errors(parity_pass.run(case.func, case.inputs))
    assert pg.drain_errors(parity_pass.gl) == []
    assert compared > 0.9 * len(case.inputs)  # the stability filter must not hide most rays
    assert bad == 0, f"{case.func}: max abs error {err:.3g}"


@pytest.fixture
def scenes(gl_context, tmp_path):
    p1 = lab_scene.build_scene(ls.LabState(show_references=False), tmp_path, CACHE_DIR, W, H)
    state = rg.RefractionState(show_references=False, technique="T-B")
    refr = rg.build_scene(state, tmp_path, CACHE_DIR, W, H)
    target = gl_lab.Target(gl_context, refr.renderer.res, W, H)
    yield p1, refr, target
    target.release()
    refr.release()
    p1.release()


def _render(scene, target):
    target.bind()
    scene.renderer.frame(scene.viewport, target.width, target.height)
    target.unbind()
    return target.read_rgb()


def _view(scene, view):
    scene.apply_view(view, lab_scene.close_up_distance(W, H))
    scene.set_aspect(W, H)
    scene.camera_moved()


@pytest.mark.parametrize("technique", ["T-A", "T-B", "T-D"])
def test_v1_is_p1_pixel_for_pixel(scenes, technique):
    p1, refr, target = scenes
    for cornea in ls.CORNEAS:
        p1.renderer.state.technique = refr.renderer.state.technique = technique
        p1.renderer.state.cornea = refr.renderer.state.cornea = cornea
        refr.renderer.state.refraction = "V1"
        for view in ("front", "three_quarter"):
            _view(p1, view)
            _view(refr, view)
            assert np.array_equal(_render(p1, target), _render(refr, target)), (technique, cornea, view)
    # T-A has no refraction: V2 / V3 draw P1's T-A as well.
    p1.renderer.state.technique = refr.renderer.state.technique = "T-A"
    refr.renderer.state.refraction = "V3"
    assert np.array_equal(_render(p1, target), _render(refr, target))


def _gl_kinds(img):
    kinds = np.full(img.shape[:2], -1)
    for kind, colour in ((co.IRIS, (255, 0, 0)), (co.PUPIL, (0, 255, 0)), (co.LIMBUS, (0, 0, 255))):
        kinds[np.all(img.astype(int) == colour, axis=-1)] = kind
    return kinds


@pytest.mark.parametrize("variant", ["V2", "V3"])
def test_gpu_ray_classes_equal_the_cpu_model_and_the_pupil_is_magnified(scenes, variant):
    _p1, refr, target = scenes
    state = refr.renderer.state
    state.refraction = variant
    refr.renderer.debug_kind = True
    try:
        for view in ("front", "three_quarter"):
            _view(refr, view)
            gl = _gl_kinds(_render(refr, target))
            eye, d = co.camera_rays(refr.camera, W, H)
            cpu = np.where(co.sclera_occludes(eye, d), co.MISS, co.trace(eye, d, variant).kind)
            both = (gl >= 0) & (cpu != co.MISS)
            assert both.sum() > 1000 and np.mean(gl[both] == cpu[both]) > 0.999, view
            if view == "front":
                straight = np.sum(co.trace(eye, d, "V1").kind == co.PUPIL)
                assert 1.10 < np.sqrt(np.sum(gl == co.PUPIL) / straight) < 1.25  # the pupil looks larger
    finally:
        refr.renderer.debug_kind = False


def test_opaque_cornea_pass_state_depth_and_order(scenes, gl_context):
    import ctypes

    gl = gl_context
    _p1, refr, target = scenes
    state = refr.renderer.state
    state.technique, state.refraction = "T-B", "V2"
    _view(refr, "front")
    base = _render(refr, target)
    assert not gl.glIsEnabled(gl.GL_BLEND)
    mask = gl.GLboolean()
    gl.glGetBooleanv(gl.GL_DEPTH_WRITEMASK, ctypes.byref(mask))
    assert mask.value
    # The depth at the cornea's centre is the anterior surface's, in front of the iris.
    col, row = W // 2, H // 2
    eye, d = co.camera_rays(refr.camera, W, H)
    tr = co.trace(eye, d[row:row + 1, col:col + 1], "V2")
    expected = probe_refraction.project(refr.camera, tr.entry[0, 0], W, H)[2]
    iris = probe_refraction.project(refr.camera, co.trace(eye, d[row:row + 1, col:col + 1], "V1").hit[0, 0], W, H)[2]
    value = np.zeros(1, dtype=np.float32)
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, target.fbo)
    gl.glReadPixels(col, H - 1 - row, 1, 1, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT, value.ctypes.data)
    gl.glBindFramebuffer(gl.GL_READ_FRAMEBUFFER, 0)
    assert abs(float(value[0]) - expected) < 1e-4 and float(value[0]) < iris
    # The iris mesh drawn under it changes nothing: depth test on, no blending.
    refr.renderer.keep_iris_mesh = True
    try:
        assert np.array_equal(_render(refr, target), base)
    finally:
        refr.renderer.keep_iris_mesh = False
    assert pg.drain_errors(gl) == []


def test_small_refraction_probe_run_passes_every_check(gl_context, tmp_path):
    lines = probe_refraction.run(probe_refraction.quick_args(str(tmp_path)))
    text = "\n".join(lines)
    summary = lines[lines.index("Summary (raw verdicts - label them by machine in the results file):") + 1:]
    assert summary and all(line.split()[0] == "PASS" for line in summary), text
    for check in ("P refraction parity", "K GPU ray classes", "D opaque cornea", "V every run", "R hygiene"):
        assert any(check in line for line in summary), check
    assert (tmp_path / "refraction_sheet.png").exists()


# -- the iris texture source (P1 and P1b) ----------------------------------------------------------------------------


def _red_custom(out_dir):
    from lookdev_gpu_probe import cube_math as cm

    from lookdev_eye_lab import iris_source

    path = out_dir / iris_source.CUSTOM_NAME
    cm.write_png(path, np.full((64, 64, 3), (0.9, 0.05, 0.05)))
    return path


def _iris_redness(img, camera):
    """Mean (R - G) over the pixels whose ray reaches the iris (straight, V1 geometry) - positive for a red iris."""
    eye, d = co.camera_rays(camera, W, H)
    mask = co.trace(eye, d, "V1").kind == co.IRIS
    pix = img[mask].astype(float)
    return float(np.mean(pix[:, 0] - pix[:, 1]))


def test_custom_iris_is_used_by_p1_and_p1b_and_never_changed(gl_context, tmp_path):
    custom = _red_custom(tmp_path)
    before = (custom.read_bytes(), custom.stat().st_mtime_ns)
    p1 = lab_scene.build_scene(ls.LabState(show_references=False, technique="T-B"), tmp_path, CACHE_DIR, W, H)
    refr = rg.build_scene(rg.RefractionState(show_references=False, technique="T-B", refraction="V2"), tmp_path,
                          CACHE_DIR, W, H)
    target = gl_lab.Target(gl_context, refr.renderer.res, W, H)
    try:
        assert p1.iris_source.custom and refr.iris_source.custom
        assert p1.iris_png == refr.iris_png == custom
        for scene in (p1, refr):
            _view(scene, "front")
            assert _iris_redness(_render(scene, target), scene.camera) > 60.0  # the blue-grey procedural iris is < 0
        assert pg.drain_errors(gl_context) == []
    finally:
        target.release()
        refr.release()
        p1.release()
    assert (custom.read_bytes(), custom.stat().st_mtime_ns) == before


def test_undecodable_custom_iris_falls_back_to_the_procedural_one(gl_context, tmp_path):
    import struct
    import zlib

    from lookdev_eye_lab import iris_source

    custom = tmp_path / iris_source.CUSTOM_NAME
    ihdr = struct.pack(">IIBBBBB", 32, 32, 8, 2, 0, 0, 0)
    chunk = lambda kind, data: (struct.pack(">I", len(data)) + kind + data  # noqa: E731
                                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))
    custom.write_bytes(iris_source.PNG_SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"IDAT", b"garbage")
                       + chunk(b"IEND", b""))
    before = custom.read_bytes()
    scene = rg.build_scene(rg.RefractionState(show_references=False), tmp_path, CACHE_DIR, W, H)
    try:
        # Caught by the lab's own PNG check (`iris_source.inspect`), the same on every platform: pyglet's Windows
        # decoder accepted this file on the reference PC (2026-11-14), the Linux one rejects it.
        assert not scene.iris_source.custom and "does not decompress" in scene.iris_source.note
        assert scene.iris_png.name == iris_source.PROCEDURAL_NAME
    finally:
        scene.release()
    assert custom.read_bytes() == before


# -- the radial fit of the custom iris (`out/iris_custom.json`, `iris_fit`) ------------------------------------------


@pytest.mark.parametrize("target, outer", [("limbus", 1.0), ("angle", 1.0), ("limbus", 0.90), ("angle", 0.90)])
def test_iris_fit_glsl_matches_the_python_model(gl_context, target, outer):
    from lookdev_eye_lab import iris_fit

    fit = iris_fit.IrisFit(0.22, 0.90, target, outer)
    res = pg.Resources(gl_context)
    pp = rg.RefractionParityPass(gl_context, res, fit)
    try:
        case = rp.fit_case(fit)
        err, bad, compared = case.errors(pp.run(case.func, case.inputs))
        assert pg.drain_errors(gl_context) == []
        assert compared == len(case.inputs) and bad == 0, f"max abs error {err:.3g}"
    finally:
        pp.release()
        res.release_all()
    assert res.leaks() == []


#: Marker image (shares of half the image width): black pupil < 0.10, green ring 0.10-0.20 (starts at the image's
#: pupil edge), red 0.20-0.50, blue beyond the image's iris edge 0.50. Deliberately far from the lab's 0.268 / 0.819,
#: so fitted and planar differ everywhere.
MARKER_FIT = {"pupil": 0.10, "limbus": 0.50}
GREEN, RED, BLUE = 1, 0, 2


def _marker_custom(out_dir, size=512):
    from lookdev_gpu_probe import cube_math as cm

    from lookdev_eye_lab import iris_source

    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    y, x = np.meshgrid(c, c, indexing="ij")
    rho = np.hypot(x, y)
    rgb = np.empty((size, size, 3))
    rgb[...] = (0.05, 0.05, 0.9)
    rgb[rho < 0.50] = (0.9, 0.05, 0.05)
    rgb[rho < 0.20] = (0.05, 0.9, 0.05)
    rgb[rho < 0.10] = 0.01
    path = out_dir / iris_source.CUSTOM_NAME
    cm.write_png(path, rgb)
    return path


def _bands(img, camera, variant):
    """{expected channel: dominant-channel share} over iris pixels in lab-share bands away from the band edges."""
    eye, d = co.camera_rays(camera, W, H)
    tr = co.trace(eye, d, variant)
    iris = (tr.kind == co.IRIS) & ~co.sclera_occludes(eye, d)
    share = np.hypot(tr.hit[..., 0], tr.hit[..., 1]) / co.GEOMETRY.iris_radius
    dominant = np.argmax(img.astype(int), axis=-1)
    bright = img.max(axis=-1) > 20

    def score(lo, hi, channel):
        m = iris & (share > lo) & (share < hi)
        assert m.sum() > 40, (lo, hi, int(m.sum()))
        return float(np.mean((dominant[m] == channel) & bright[m]))

    return score


@pytest.mark.parametrize("with_sidecar", [True, False])
def test_marker_image_lands_on_the_geometric_pupil_edge_in_p1_and_p1b(gl_context, tmp_path, with_sidecar):
    import json

    from lookdev_eye_lab import iris_fit

    custom = _marker_custom(tmp_path)
    sidecar = tmp_path / iris_fit.SIDECAR_NAME
    if with_sidecar:
        sidecar.write_text(json.dumps(MARKER_FIT), encoding="utf-8")
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (custom, sidecar) if p.exists()]
    p1 = lab_scene.build_scene(ls.LabState(show_references=False, technique="T-B"), tmp_path, CACHE_DIR, W, H)
    refr = rg.build_scene(rg.RefractionState(show_references=False, technique="T-B", refraction="V2"), tmp_path,
                          CACHE_DIR, W, H)
    target = gl_lab.Target(gl_context, refr.renderer.res, W, H)
    lp, lt = iris_fit.LAB_PUPIL_SHARE, iris_fit.TARGETS[iris_fit.DEFAULT_TARGET]
    # Lab shares of the marker's band edges (image 0.20 -> lab), fitted or planar.
    green_end = lp + (0.20 - 0.10) / (0.50 - 0.10) * (lt - lp) if with_sidecar else 0.20
    try:
        assert (p1.iris_source.fit is not None) == with_sidecar == (refr.iris_source.fit is not None)
        for scene, variant in ((p1, "V1"), (refr, "V2")):
            _view(scene, "front")
            score = _bands(_render(scene, target), scene.camera, variant)
            if with_sidecar:
                # The image's pupil edge (its green ring starts there) is the geometric pupil edge: the iris begins
                # green right outside the pupil, no black image pupil on the iris; then red out to the limbus.
                assert score(lp + 0.005, green_end - 0.02, GREEN) > 0.95, variant
                assert score(green_end + 0.02, 0.74, RED) > 0.95, variant
            else:
                # Planar: the lab's iris starts at 0.268, already past the image's green ring (0.10-0.20); red to
                # 0.50, blue beyond.
                assert score(lp + 0.005, 0.48, RED) > 0.95, variant
                assert score(0.52, 0.74, BLUE) > 0.95, variant
        assert pg.drain_errors(gl_context) == []
    finally:
        target.release()
        refr.release()
        p1.release()
    assert [(p.read_bytes(), p.stat().st_mtime_ns) for p in (custom, sidecar) if p.exists()] == before


@pytest.mark.parametrize("hold", [True, False])
def test_hold_outer_color_fills_p1s_parallax_band(gl_context, tmp_path, hold):
    """P1 sees the iris past the sclera opening (share 0.819) out to ~0.85 in the close-up; with the hold the marker's
    red iris colour continues there, without it the image's blue background shows (Manu's "A+H", 2026-11-14)."""
    import json

    from lookdev_eye_lab import iris_fit

    custom = _marker_custom(tmp_path)
    (tmp_path / iris_fit.SIDECAR_NAME).write_text(
        json.dumps({"pupil": 0.10, "limbus": 0.48, "hold_outer_color": hold}), encoding="utf-8")
    p1 = lab_scene.build_scene(ls.LabState(show_references=False, technique="T-B"), tmp_path, CACHE_DIR, W, H)
    target = gl_lab.Target(gl_context, p1.renderer.res, W, H)
    try:
        assert p1.iris_source.fit.hold == hold
        _view(p1, "front")
        score = _bands(_render(p1, target), p1.camera, "V1")
        lt = iris_fit.TARGETS["limbus"]
        assert score(lt + 0.008, 0.86, RED if hold else BLUE) > 0.9
        assert pg.drain_errors(gl_context) == []
    finally:
        target.release()
        p1.release()
    assert custom.exists()
