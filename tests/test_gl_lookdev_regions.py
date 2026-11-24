"""LookDev P3 S6 - region materials in the real GL path (AD-039 §9 / §22): a plane with two overlapping regions draws
three materials (the object's, each region's; the later region wins on the overlap), on the cage and on the SubD
surface (its faces mapped through `face_parent`); the effect off draws one material per object, pixel for pixel, and
frees the slot buffer; a slot outside the slots draws the object's material (`lookdev_optics.region_slot`); the albedo
source per slot; the GL state as found (unit 12); too few texture units turn the regions off with a status line; the
Worklight keeps no slot buffer.

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_lookdev_regions.py -q`."""

from __future__ import annotations

import dataclasses

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from mirai.iris_import import encode_png  # noqa: E402
from mirai.subdivision.preview import SubdSurfaceProvider  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport import lookdev_features  # noqa: E402
from viewport import lookdev_optics as lo  # noqa: E402
from viewport import lookdev_shaders as ls  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.lookdev_pass import LookDraw  # noqa: E402
from viewport.render_mesh import TRIANGLE_MATERIALS  # noqa: E402
from viewport.viewport import Viewport  # noqa: E402

SIZE = 128
HALF = 2.0
FLAT = lo.Studio((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
REGIONS_ONLY = lo.LookdevEffects(shadow=False, eye_shadow=False, dual_lobe=False, thickness=False, cube=False,
                                 regions=True, maps=False)
NO_REGIONS = dataclasses.replace(REGIONS_ONLY, regions=False)
GREY = LookDraw((0.5, 0.5, 0.5), roughness=0.6, specular=0.5)
RED = LookDraw((0.85, 0.15, 0.1), roughness=0.3, specular=0.7, wrap_rgb=(0.4, 0.2, 0.1))
BLUE = LookDraw((0.1, 0.2, 0.85), roughness=0.9, specular=0.2)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _plane(n: int = 4) -> Mesh:
    """A square in XZ at y = 0 facing +Y, n x n quads, with UVs."""
    mesh = Mesh()
    ids = {(i, j): mesh.add_vertex((-HALF + 2 * HALF * i / n, 0.0, -HALF + 2 * HALF * j / n))
           for i in range(n + 1) for j in range(n + 1)}
    for i in range(n):
        for j in range(n):
            face = [ids[i, j], ids[i, j + 1], ids[i + 1, j + 1], ids[i + 1, j]]
            p = [np.asarray(mesh.vertex_position(v)) for v in face]
            if np.cross(p[1] - p[0], p[2] - p[0])[1] < 0:
                face.reverse()
            mesh.add_face(face)
    for fid in mesh.all_face_ids():
        corners = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        mesh.set_face_uvs(fid, [((x + HALF) / (2 * HALF), (z + HALF) / (2 * HALF)) for x, _y, z in corners])
    return mesh


def _halves(mesh: Mesh) -> tuple[frozenset, frozenset]:
    """The faces with x < 0 (region A) and with z < 0 (region B): they overlap in one quadrant."""
    def centre(f):
        return np.mean([mesh.vertex_position(v) for v in mesh.face_vertices(f)], axis=0)
    faces = mesh.all_face_ids()
    return (frozenset(f for f in faces if centre(f)[0] < 0), frozenset(f for f in faces if centre(f)[2] < 0))


def _state(effects=REGIONS_ONLY, **kw):
    values = dict(preset="test", studio=FLAT, key=lo.StudioLight(True, 1.0, 20.0, 50.0, 6500.0, 0.0),
                  fill=lo.StudioLight(True, 0.4, -60.0, 20.0, 5000.0, 0.0), rim=lo.StudioLight(False),
                  env_intensity=0.3, background=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), background_gradient=False,
                  effects=effects)
    values.update(kw)
    return lo.LookdevState(**values)


def _viewport(gl_window, mesh: Mesh, subd: bool = False) -> Viewport:
    gl_window.switch_to()
    viewport = Viewport(mesh, store_type=GLRenderStore)
    viewport.bind_camera(OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=1.45))
    viewport.on_camera_changed(aspect=1.0)
    if subd:
        provider = SubdSurfaceProvider(level=1)
        provider.set_enabled(True)
        viewport.set_surface_provider(provider)
    return viewport


def _frame(gl_window, viewport, look: LookDraw, state) -> np.ndarray:
    from pyglet import gl

    viewport.set_edit_look(look)
    viewport.set_shading("lookdev", state)
    gl_window.switch_to()
    gl.glViewport(0, 0, SIZE, SIZE)
    gl.glClearColor(0.0, 0.0, 0.0, 1.0)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    viewport.sync()
    viewport.render()
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return np.frombuffer(bytes(buf), dtype=np.uint8).reshape(SIZE, SIZE, 3).astype(int)


def _release(viewport) -> None:
    viewport.set_surface_provider(None)
    if viewport._lookdev_pass is not None:
        viewport._lookdev_pass.release()


def _with_regions(base: LookDraw, *regions) -> LookDraw:
    return dataclasses.replace(base, regions=tuple(r for r, _ in regions), region_faces=tuple(f for _, f in regions))


def _matches(image, reference) -> np.ndarray:
    return np.abs(image - reference).max(axis=2) <= 1


def _drawn(viewport):
    return viewport.surface_render_mesh or viewport.render_mesh


# -- two regions, three materials ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("subd", [False, True], ids=["cage", "subd"])
def test_two_regions_draw_their_materials_and_the_later_wins_on_the_overlap(gl_window, subd):
    mesh = _plane()
    a, b = _halves(mesh)
    viewport = _viewport(gl_window, mesh, subd)
    grey, red, blue = (_frame(gl_window, viewport, look, _state()) for look in (GREY, RED, BLUE))
    lit = grey.sum(axis=2) > 0
    assert lit.mean() > 0.5
    assert not (_matches(grey, red) & lit).any() and not (_matches(red, blue) & lit).any()
    image = _frame(gl_window, viewport, _with_regions(GREY, (RED, a), (BLUE, b)), _state())
    rm = _drawn(viewport)
    assert rm.store.has(TRIANGLE_MATERIALS) and set(rm.triangle_material_slots.values()) == {1, 2}
    if subd:
        # through `face_parent`: the 8 + 8 control faces of A and B (4 shared) x 4 derived faces each
        assert rm is not viewport.render_mesh and len(rm.triangle_material_slots) == 4 * 12
    is_grey, is_red, is_blue = (_matches(image, ref) & lit for ref in (grey, red, blue))
    assert (is_grey | is_red | is_blue)[lit].mean() > 0.97  # every lit pixel is one of the three (edges blend)
    quarter = lit.sum() / 4
    assert abs(is_grey.sum() - quarter) < 0.1 * quarter and abs(is_red.sum() - quarter) < 0.1 * quarter
    assert abs(is_blue.sum() - 2 * quarter) < 0.1 * quarter  # region B and the overlap
    # a region with the object's own material = the object's frame, pixel for pixel (every slot value reaches GL)
    every = frozenset(mesh.all_face_ids())
    assert np.array_equal(_frame(gl_window, viewport, _with_regions(GREY, (GREY, every)), _state()), grey)
    assert np.array_equal(_frame(gl_window, viewport, _with_regions(GREY, (RED, every)), _state()), red)
    swapped = _frame(gl_window, viewport, _with_regions(GREY, (BLUE, b), (RED, a)), _state())
    red2 = (_matches(swapped, red) & lit).sum()
    assert abs(red2 - 2 * quarter) < 0.1 * quarter  # now A wins the overlap
    _release(viewport)


def test_the_effect_off_draws_one_material_and_frees_the_slots(gl_window):
    mesh = _plane()
    a, b = _halves(mesh)
    viewport = _viewport(gl_window, mesh)
    grey = _frame(gl_window, viewport, GREY, _state(NO_REGIONS))
    keys_before = set(viewport.lookdev_pass.programs)
    looked = _with_regions(GREY, (RED, a), (BLUE, b))
    assert np.array_equal(_frame(gl_window, viewport, looked, _state(NO_REGIONS)), grey)
    assert not viewport.render_mesh.store.has(TRIANGLE_MATERIALS) and not viewport.render_mesh.triangle_material_slots
    assert set(viewport.lookdev_pass.programs) == keys_before and all(len(k) < 10 for k in keys_before)
    _frame(gl_window, viewport, looked, _state())
    assert viewport.render_mesh.store.has(TRIANGLE_MATERIALS)
    assert [k for k in viewport.lookdev_pass.programs if len(k) == 10] == [
        (False, True, False, False, False, False, False, False, False, True)]
    # off again: the slots go, the frame is the one-material frame again
    assert np.array_equal(_frame(gl_window, viewport, looked, _state(NO_REGIONS)), grey)
    assert not viewport.render_mesh.store.has(TRIANGLE_MATERIALS)
    # a look without regions with the effect on: nothing allocated, the 5-value key
    assert np.array_equal(_frame(gl_window, viewport, GREY, _state()), grey)
    assert not viewport.render_mesh.store.has(TRIANGLE_MATERIALS)
    _release(viewport)


def test_a_slot_outside_the_slots_draws_the_object_s_material(gl_window):
    """The `REGIONS` block's clamp (twin `lookdev_optics.region_slot`): a stale slot 7 is slot 0."""
    mesh = _plane()
    a, _b = _halves(mesh)
    viewport = _viewport(gl_window, mesh)
    grey = _frame(gl_window, viewport, GREY, _state())
    look = _with_regions(GREY, (RED, a))
    _frame(gl_window, viewport, look, _state())
    viewport.render_mesh.set_triangle_material_slots({f: 7 for f in mesh.all_face_ids()})
    viewport._material_slot_keys[viewport.render_mesh] = (look.region_faces, id(mesh), None)  # keep the stale slots
    assert lo.region_slot([7.0], ls.REGION_SLOTS - 1).tolist() == [0]
    assert np.abs(_frame(gl_window, viewport, look, _state()) - grey).max() <= 1
    _release(viewport)


def test_each_slot_takes_its_own_albedo_source(gl_window, tmp_path):
    mesh = _plane()
    a, _b = _halves(mesh)
    image = np.zeros((8, 8, 4), np.uint8)
    image[..., :3] = (40, 200, 60)
    image[..., 3] = 255
    path = tmp_path / "albedo.png"
    path.write_bytes(encode_png(image))
    textured = dataclasses.replace(GREY, albedo=str(path))
    viewport = _viewport(gl_window, mesh)
    tex, red = _frame(gl_window, viewport, textured, _state()), _frame(gl_window, viewport, RED, _state())
    lit = tex.sum(axis=2) > 0
    both = _frame(gl_window, viewport, _with_regions(textured, (RED, a)), _state())
    half = lit.sum() / 2
    assert abs((_matches(both, tex) & lit).sum() - half) < 0.1 * half
    assert abs((_matches(both, red) & lit).sum() - half) < 0.1 * half
    # the region has the texture, the object its colour: the map is bound for the region alone
    red_tex = dataclasses.replace(RED, albedo=str(path))
    flipped = _frame(gl_window, viewport, _with_regions(GREY, (red_tex, a)), _state())
    grey, red_tex_ref = _frame(gl_window, viewport, GREY, _state()), _frame(gl_window, viewport, red_tex, _state())
    assert abs((_matches(flipped, grey) & lit).sum() - half) < 0.1 * half
    assert abs((_matches(flipped, red_tex_ref) & lit).sum() - half) < 0.1 * half
    _release(viewport)


# -- GL state, features, the Worklight ----------------------------------------------------------------------------------

def test_unit_12_is_unbound_after_the_frame(gl_window):
    import ctypes

    from pyglet import gl

    mesh = _plane()
    a, b = _halves(mesh)
    viewport = _viewport(gl_window, mesh)
    _frame(gl_window, viewport, _with_regions(GREY, (RED, a), (BLUE, b)), _state())
    bound = gl.GLint()
    for unit in (ls.UV_UNIT, ls.REGION_UNIT):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_BUFFER, ctypes.byref(bound))
        assert bound.value == 0, unit
    gl.glActiveTexture(gl.GL_TEXTURE0)
    active = gl.GLint()
    gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE, ctypes.byref(active))
    assert active.value == gl.GL_TEXTURE0
    _release(viewport)


def test_too_few_texture_units_turn_the_regions_off_with_a_status_line(gl_window, monkeypatch):
    mesh = _plane()
    a, b = _halves(mesh)
    viewport = _viewport(gl_window, mesh)
    grey = _frame(gl_window, viewport, GREY, _state())
    assert viewport.lookdev_pass.features is None  # no region drawn yet: nothing probed
    _release(viewport)
    monkeypatch.setitem(lookdev_features.CHECKS, "texture_units", lambda: False)
    viewport = _viewport(gl_window, mesh)
    image = _frame(gl_window, viewport, _with_regions(GREY, (RED, a), (BLUE, b)), _state())
    assert np.array_equal(image, grey)
    assert viewport.take_lookdev_notices() == ["LookDev: Maps und Region-Materialien aus – zu wenige Textureinheiten"]
    assert not viewport.render_mesh.store.has(TRIANGLE_MATERIALS)
    _release(viewport)
    monkeypatch.undo()
    assert lookdev_features.CHECKS["texture_units"]()  # llvmpipe has 32 fragment units


def test_the_worklight_keeps_no_slot_buffer(gl_window):
    mesh = _plane()
    a, b = _halves(mesh)
    viewport = _viewport(gl_window, mesh, subd=True)
    _frame(gl_window, viewport, _with_regions(GREY, (RED, a), (BLUE, b)), _state())
    assert _drawn(viewport).store.has(TRIANGLE_MATERIALS)
    viewport.set_edit_look(None)
    viewport.set_shading("worklight")
    for rm in (viewport.render_mesh, viewport.surface_render_mesh):
        assert not rm.store.has(TRIANGLE_MATERIALS) and not rm.triangle_material_slots
    _release(viewport)


def test_prepare_compiles_the_regions_program(gl_window):
    mesh = _plane()
    a, _b = _halves(mesh)
    viewport = _viewport(gl_window, mesh)
    viewport.set_edit_look(_with_regions(GREY, (RED, a)))
    viewport.set_shading("lookdev", _state())
    assert viewport.lookdev_prepare_needed()
    assert viewport.prepare_lookdev() == 1 and not viewport.lookdev_prepare_needed()
    assert [len(k) for k in viewport.lookdev_pass.programs] == [10]
    _release(viewport)
