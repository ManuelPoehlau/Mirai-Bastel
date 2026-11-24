"""LookDev P3 S1 - the key's shadow map in the real GL path (AD-039 §4, T1-1 … T1-6): the footprint of a box on a
plane, no acne on a lit sphere, re-rendered only on a change (`KeyShadow.renders`, with the app's morph, pose, key and
studio setters), the shadow off is M1, the GL state as found, a missing depth texture turns the effect off; plus the GPU
parity of `ld_key_visibility` against `lookdev_optics.pcf_visibility` and of the `SHADOW` block against
`lookdev_optics.ld_key_shadowed`.

Needs a real GL context, in its own process: `xvfb-run -a python -m pytest tests/test_gl_lookdev_shadow.py -q`."""

from __future__ import annotations

import ctypes
import dataclasses
import math
import sys
from pathlib import Path

import tests._bootstrap  # noqa: F401

import numpy as np
import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from gui.imgui_layer import snapshot_gl_state  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport import lookdev_features  # noqa: E402
from viewport import lookdev_optics as lo  # noqa: E402
from viewport import lookdev_shaders as ls  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.lookdev_pass import LookDraw  # noqa: E402
from viewport.viewport import Viewport  # noqa: E402

SIZE = 192
GREY = LookDraw((0.5, 0.5, 0.5), roughness=1.0, specular=0.0)
FLAT = lo.Studio((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
OFF = lo.LookdevEffects(shadow=False, dual_lobe=False, thickness=False, cube=False,
                        regions=False)  # every P3 effect off: M1


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


# -- meshes -----------------------------------------------------------------------------------------------------------

def _face(mesh: Mesh, ids, outward) -> None:
    """A face whose Newell normal points along `outward` (the corners reversed otherwise)."""
    p = [np.asarray(mesh.vertex_position(v)) for v in ids]
    normal = sum(np.cross(p[i], p[(i + 1) % len(p)]) for i in range(len(p)))
    mesh.add_face(list(ids) if np.dot(normal, outward) > 0 else list(reversed(ids)))


def _box(lo_corner, hi_corner) -> Mesh:
    mesh = Mesh()
    lo_c, hi_c = np.asarray(lo_corner, float), np.asarray(hi_corner, float)
    corner = {}
    for i in (0, 1):
        for j in (0, 1):
            for k in (0, 1):
                corner[i, j, k] = mesh.add_vertex(tuple(float(v) for v in np.where([i, j, k], hi_c, lo_c)))
    for axis in range(3):
        for side in (0, 1):
            quad = []
            for a, b in ((0, 0), (0, 1), (1, 1), (1, 0)):
                index = [0, 0, 0]
                index[axis] = side
                index[(axis + 1) % 3], index[(axis + 2) % 3] = a, b
                quad.append(corner[tuple(index)])
            outward = np.zeros(3)
            outward[axis] = 1.0 if side else -1.0
            _face(mesh, quad, outward)
    return mesh


def _ground(half: float = 2.0, n: int = 8) -> Mesh:
    """A square in XZ at y = 0 facing +Y, n x n quads."""
    mesh = Mesh()
    ids = {(i, j): mesh.add_vertex((-half + 2 * half * i / n, 0.0, -half + 2 * half * j / n))
           for i in range(n + 1) for j in range(n + 1)}
    for i in range(n):
        for j in range(n):
            _face(mesh, [ids[i, j], ids[i, j + 1], ids[i + 1, j + 1], ids[i + 1, j]], (0.0, 1.0, 0.0))
    return mesh


def _sphere(radius: float = 0.8, rings: int = 24, segments: int = 40) -> Mesh:
    mesh = Mesh()
    top = mesh.add_vertex((0.0, radius, 0.0))
    bottom = mesh.add_vertex((0.0, -radius, 0.0))
    ring = []
    for r in range(1, rings):
        theta = math.pi * r / rings
        ring.append([mesh.add_vertex((radius * math.sin(theta) * math.cos(2 * math.pi * s / segments),
                                      radius * math.cos(theta),
                                      radius * math.sin(theta) * math.sin(2 * math.pi * s / segments)))
                     for s in range(segments)])

    def out(ids):
        return np.mean([mesh.vertex_position(v) for v in ids], axis=0)

    for s in range(segments):
        t = (s + 1) % segments
        cap = [top, ring[0][s], ring[0][t]]
        _face(mesh, cap, out(cap))
        cap = [bottom, ring[-1][t], ring[-1][s]]
        _face(mesh, cap, out(cap))
        for r in range(rings - 2):
            quad = [ring[r][s], ring[r + 1][s], ring[r + 1][t], ring[r][t]]
            _face(mesh, quad, out(quad))
    return mesh


# -- frames -----------------------------------------------------------------------------------------------------------

def _state(key_az=200.0, key_el=60.0, size=0.0, effects=None, **kw):
    values = dict(preset="test", studio=FLAT, key=lo.StudioLight(True, 1.0, key_az, key_el, 6500.0, size),
                  fill=lo.StudioLight(False), rim=lo.StudioLight(False), env_intensity=0.0,
                  background=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)), background_gradient=False)
    if effects is not None:
        values["effects"] = effects
    values.update(kw)
    return lo.LookdevState(**values)


def _viewport(gl_window, meshes: dict, camera) -> Viewport:
    gl_window.switch_to()
    viewport = Viewport(Mesh(), store_type=GLRenderStore)
    viewport.bind_camera(camera)
    viewport.on_camera_changed(aspect=1.0)
    for key, mesh in meshes.items():
        viewport.set_object_entry(key, mesh, (0.5, 0.5, 0.5), look=GREY)
    return viewport


def _frame(gl_window, viewport) -> np.ndarray:
    from pyglet import gl

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
    return np.frombuffer(bytes(buf), dtype=np.uint8).reshape(SIZE, SIZE, 3).astype(int)  # row 0 = bottom


def _release(viewport) -> None:
    for entry in list(viewport.object_entries):
        viewport.remove_object_entry(entry)
    if viewport._lookdev_pass is not None:
        viewport._lookdev_pass.release()


def _rays(viewport) -> tuple[np.ndarray, np.ndarray]:
    """Per pixel (row 0 = bottom) the camera ray's origin and unit direction in world space."""
    camera = viewport.render_mesh.store.uniform_data("camera_uniforms")
    view = np.asarray(camera[0:16], float).reshape(4, 4).T
    proj = np.asarray(camera[16:32], float).reshape(4, 4).T
    inverse = np.linalg.inv(proj @ view)
    ys, xs = np.mgrid[0:SIZE, 0:SIZE]
    ndc = np.stack([(xs + 0.5) / SIZE * 2 - 1, (ys + 0.5) / SIZE * 2 - 1], axis=-1)

    def unproject(z):
        p = np.concatenate([ndc, np.full(ndc.shape[:2] + (1,), z), np.ones(ndc.shape[:2] + (1,))], axis=-1) @ inverse.T
        return p[..., :3] / p[..., 3:]

    near, far = unproject(-1.0), unproject(1.0)
    d = far - near
    return near, d / np.linalg.norm(d, axis=-1, keepdims=True)


def _hits_box(origin, direction, lo_c, hi_c) -> tuple[np.ndarray, np.ndarray]:
    """Slab test: (hit mask, entry distance)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / direction
        t0 = (np.asarray(lo_c) - origin) * inv
        t1 = (np.asarray(hi_c) - origin) * inv
    near = np.nanmax(np.minimum(t0, t1), axis=-1)
    far = np.nanmin(np.maximum(t0, t1), axis=-1)
    return (far >= np.maximum(near, 0.0)), near


def _grow(mask: np.ndarray, pixels: int = 1) -> np.ndarray:
    """`mask` grown by `pixels` (the rasterised silhouette's edge pixels belong to either side)."""
    out = mask.copy()
    for _ in range(pixels):
        grown = out.copy()
        grown[1:] |= out[:-1]
        grown[:-1] |= out[1:]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        out = grown
    return out


def _key_dir(state) -> np.ndarray:
    return lo.light_directions(state)[0]


# -- T1-1: the footprint ----------------------------------------------------------------------------------------------

BOX = ((-0.4, 0.6, -0.4), (0.4, 1.2, 0.4))
#: The penumbra band: a point within this distance (x its scale) of the footprint's edge, in 8 directions.
BAND = np.array([(math.cos(a), math.sin(a)) for a in np.arange(8) * math.pi / 4])


def test_a_box_shadows_the_plane_under_it_and_nothing_else(gl_window):
    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    lit = _state(effects=OFF)
    viewport.set_shading("lookdev", lit)
    without = _frame(gl_window, viewport)
    viewport.set_shading("lookdev", dataclasses.replace(lit, effects=lo.LookdevEffects()))
    with_shadow = _frame(gl_window, viewport)
    assert viewport.lookdev_pass.shadow.renders == 1

    origin, direction = _rays(viewport)
    on_box, entry = _hits_box(origin, direction, *BOX)
    top = on_box & (np.abs((origin + direction * entry[..., None])[..., 1] - BOX[1][1]) < 1e-6) & ~_grow(~on_box, 2)
    t = -origin[..., 1] / direction[..., 1]
    ground = (t > 0) & ~_grow(on_box)
    point = origin + direction * t[..., None]
    ground &= (np.abs(point[..., 0]) < 1.9) & (np.abs(point[..., 2]) < 1.9)
    key = _key_dir(lit)
    shaded, _ = _hits_box(point, np.broadcast_to(key, point.shape), *BOX)
    # a band of ~2 cm around the footprint's edge is the PCF penumbra: judged neither way
    band = np.zeros_like(shaded)
    for dx, dz in BAND * 0.03:
        moved, _ = _hits_box(point + np.array([dx, 0.0, dz]), np.broadcast_to(key, point.shape), *BOX)
        band |= moved != shaded
    inside = ground & shaded & ~band
    outside = ground & ~shaded & ~band
    assert inside.sum() > 300 and outside.sum() > 3000, (inside.sum(), outside.sum())
    darker = (without - with_shadow).max(axis=-1)
    assert (darker[inside] > 40).mean() > 0.99  # the plane under the box is dark
    assert (darker[outside] <= 1).mean() > 0.999  # the rest of the plane is lit as before
    # the box's lit top is not darkened by its own shadow (no acne); its sides face away from the key
    assert top.sum() > 200 and (np.abs(darker[top]) <= 1).mean() > 0.999
    # in the shadow the key is gone completely: the twin with visibility 0 (no environment, no fill) is black
    assert with_shadow[inside].max() <= 1
    _release(viewport)


def test_the_penumbra_widens_with_the_keys_softness(gl_window):
    """AD-039 §16.6: the key's size ("Weichheit") widens the shadow's edge; the core stays dark and the lit plane lit."""
    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    viewport.set_shading("lookdev", _state(effects=OFF))
    lit = _frame(gl_window, viewport).max(axis=-1)
    origin, direction = _rays(viewport)
    on_box, _ = _hits_box(origin, direction, *BOX)
    t = -origin[..., 1] / direction[..., 1]
    ground = (t > 0) & ~_grow(on_box, 2)
    partial = []
    for size in (0.0, 0.3, 1.0):
        viewport.set_shading("lookdev", _state(size=size))
        shaded = _frame(gl_window, viewport).max(axis=-1)
        fraction = np.where(lit > 0, shaded / np.maximum(lit, 1), 1.0)
        partial.append(int((ground & (fraction > 0.1) & (fraction < 0.9)).sum()))
        assert (ground & (fraction <= 0.1)).sum() > 100  # a dark core stays
    assert partial[0] < partial[1] < partial[2], partial
    assert partial[2] > 3 * partial[0], partial
    _release(viewport)


# -- T1-2: no acne on a lit sphere ------------------------------------------------------------------------------------

@pytest.mark.parametrize("key_el, size", [(60.0, 0.0), (20.0, 0.0), (60.0, 0.3), (20.0, 1.0)])
def test_a_lit_sphere_does_not_shadow_its_lit_half(gl_window, key_el, size):
    """No acne, also with a soft key (AD-039 §16.6: Manu 2026-11-22 „Weichheit wirkt noch sehr unsauber“ - the spread
    fetches dipped under the curved surface)."""
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.0, yaw=0.5, pitch=0.3)
    viewport = _viewport(gl_window, {"sphere": _sphere()}, camera)
    state = _state(key_az=30.0, key_el=key_el, size=size, effects=OFF)
    viewport.set_shading("lookdev", state)
    without = _frame(gl_window, viewport)
    viewport.set_shading("lookdev", dataclasses.replace(state, effects=lo.LookdevEffects()))
    with_shadow = _frame(gl_window, viewport)
    origin, direction = _rays(viewport)
    b = np.sum(origin * direction, -1)
    c = np.sum(origin * origin, -1) - 0.8 ** 2
    disc = b * b - c
    hit = disc > 0
    t = -b - np.sqrt(np.maximum(disc, 0.0))
    normal = (origin + direction * t[..., None]) / 0.8
    ndl = np.sum(normal * _key_dir(state), -1)
    lit = hit & (ndl > 0.1)
    assert lit.sum() > 2000
    darkened = (without - with_shadow).max(axis=-1) > 2
    assert darkened[lit].mean() <= 0.001, darkened[lit].sum()
    _release(viewport)


# -- AD-039 §16.7: the wrap in a cast shadow and past a convex terminator --------------------------------------------

WRAPPED = LookDraw((0.5, 0.5, 0.5), roughness=0.5, specular=0.5, wrap_rgb=(0.5, 0.3, 0.2))


def test_a_cast_shadow_at_a_grazing_key_keeps_the_wrap_and_the_highlight_dark(gl_window):
    """Manu, 2026-11-22: „in der Nase und um die Mundwinkel entstehen sehr helle Ränder um die Schatten“ - a cast
    shadow on a surface the key grazes (n.l < 0.3) let the wrap and the highlight through. The box's footprint on the
    plane under a 15° key is black (no fill, no environment)."""
    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    for key in ("ground", "box"):
        viewport.set_object_entry(key, viewport.object_entries[key].mesh, (0.5, 0.5, 0.5), look=WRAPPED)
    state = _state(key_el=15.0)
    viewport.set_shading("lookdev", state)
    pixels = _frame(gl_window, viewport).max(axis=-1)
    origin, direction = _rays(viewport)
    on_box, _ = _hits_box(origin, direction, *BOX)
    t = -origin[..., 1] / direction[..., 1]
    point = origin + direction * t[..., None]
    key = _key_dir(state)
    shaded, _ = _hits_box(point, np.broadcast_to(key, point.shape), *BOX)
    band = np.zeros_like(shaded)
    for dx, dz in BAND * 0.05:
        moved, _ = _hits_box(point + np.array([dx, 0.0, dz]), np.broadcast_to(key, point.shape), *BOX)
        band |= moved != shaded
    ground = (t > 0) & ~_grow(on_box, 2) & (np.abs(point[..., 0]) < 1.9) & (np.abs(point[..., 2]) < 1.9)
    inside, outside = ground & shaded & ~band, ground & ~shaded & ~band
    assert inside.sum() > 150 and outside.sum() > 3000
    assert np.percentile(pixels[inside], 99) <= 2, np.percentile(pixels[inside], 99)
    assert np.median(pixels[outside]) > 60  # the plane outside is lit (Lambert 0.26 + the wrap)
    _release(viewport)


def test_the_wrap_past_a_convex_terminator_is_not_cut(gl_window):
    """A sphere with a wide wrap: past the terminator (n.l in [-0.2, 0]) the wrap's light stays as without the shadow
    (the convex surface's own shadow is left behind by the lifted lookup), while the lit half is untouched."""
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.0, yaw=1.2, pitch=0.2)
    viewport = _viewport(gl_window, {"sphere": _sphere()}, camera)
    viewport.set_object_entry("sphere", viewport.object_entries["sphere"].mesh, (0.5, 0.5, 0.5), look=WRAPPED)
    state = _state(key_az=30.0, key_el=20.0, effects=OFF)
    viewport.set_shading("lookdev", state)
    without = _frame(gl_window, viewport).astype(float)
    viewport.set_shading("lookdev", dataclasses.replace(state, effects=lo.LookdevEffects()))
    with_shadow = _frame(gl_window, viewport).astype(float)
    origin, direction = _rays(viewport)
    b = np.sum(origin * direction, -1)
    c = np.sum(origin * origin, -1) - 0.8 ** 2
    hit = b * b - c > 0
    t = -b - np.sqrt(np.maximum(b * b - c, 0.0))
    ndl = np.sum((origin + direction * t[..., None]) / 0.8 * _key_dir(state), -1)
    past = _grow(~hit, 2)
    past = hit & ~past & (ndl > -0.2) & (ndl < 0.0)
    assert past.sum() > 150 and (without[past].max(-1) > 20).mean() > 0.9  # the wrap lights it
    kept = with_shadow[past].sum(-1) / np.maximum(without[past].sum(-1), 1.0)
    assert np.median(kept) > 0.95 and (kept > 0.8).mean() > 0.97, (np.median(kept), (kept > 0.8).mean())
    _release(viewport)


# -- T1-3: re-rendered only on a change ---------------------------------------------------------------------------

def test_the_map_renders_once_and_not_for_the_camera_the_exposure_or_a_capture(gl_window):
    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    state = _state()
    viewport.set_shading("lookdev", state)
    _frame(gl_window, viewport)
    shadow = viewport.lookdev_pass.shadow
    assert shadow.renders == 1
    _frame(gl_window, viewport)
    assert shadow.renders == 1
    camera.orbit(0.4, 0.1)
    viewport.on_camera_changed(aspect=1.0)
    _frame(gl_window, viewport)
    viewport.set_shading("lookdev", dataclasses.replace(state, exposure=1.0, key=dataclasses.replace(
        state.key, intensity=2.0, kelvin=4000.0)))
    _frame(gl_window, viewport)
    viewport.request_capture(lambda rgba: None)
    _frame(gl_window, viewport)  # two mesh draws in one frame
    assert shadow.renders == 1
    # the key's softness is the map's effective resolution: a size that keeps it renders nothing, one that moves it
    # renders once
    state = dataclasses.replace(state, key=dataclasses.replace(state.key, size=0.5))
    viewport.set_shading("lookdev", state)
    _frame(gl_window, viewport)
    _frame(gl_window, viewport)
    assert shadow.renders == 2 and shadow._resolution == lo.shadow_resolution(0.5)
    tiny = 1e-4
    assert lo.shadow_resolution(0.5 + tiny) == shadow._resolution
    viewport.set_shading("lookdev", dataclasses.replace(state, key=dataclasses.replace(state.key, size=0.5 + tiny)))
    _frame(gl_window, viewport)
    assert shadow.renders == 2
    viewport.set_shading("lookdev", state)
    viewport.set_shading("lookdev", dataclasses.replace(state, key=dataclasses.replace(state.key, azimuth=50.0)))
    _frame(gl_window, viewport)
    assert shadow.renders == 3
    viewport.set_shading("lookdev", dataclasses.replace(state, rotation=20.0))
    _frame(gl_window, viewport)
    assert shadow.renders == 4
    # a geometry change of a caster (a vertex moved, as a pose or morph step arrives: a content revision)
    box = viewport.object_entries["box"]
    mesh = box.mesh
    vertex = next(iter(mesh.all_vertex_ids()))
    sphere_before = shadow._sphere
    mesh.set_vertex_position(vertex, tuple(c * 1.01 for c in mesh.vertex_position(vertex)))
    box.mark_vertices_dirty({vertex})
    _frame(gl_window, viewport)
    assert shadow.renders == 5
    assert shadow._sphere == sphere_before  # the frustum follows layouts, not every step (no swimming)
    _release(viewport)


_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
HEAD = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"


@pytest.fixture
def head_app(gl_window):
    if str(_EXAMPLES_DIR) not in sys.path:
        sys.path.insert(0, str(_EXAMPLES_DIR))
    from mirai.application import Application
    from tests.test_gl_morph_picking import _open_mouth
    from tests.test_gl_posed_picking import _GL, _jaw, _smooth_bind
    from tests.test_skin_stage import _rig

    gl_window.switch_to()
    app = Application()
    app.init_scene("obj", obj_path=HEAD, **_GL)
    app.set_viewport_size(SIZE, SIZE)
    app.frame_scene()
    app._camera_changed()
    _smooth_bind(app.scene.mesh)
    app.scene.rig = _rig(app.scene.mesh)
    app.lid = _open_mouth(app.scene.mesh)
    app.set_morph_weight(30, app.lid)
    _jaw(app, 10.0)
    app.update_viewport(0.0)
    app.jaw = lambda degrees: _jaw(app, degrees)
    yield app
    if app.lookdev_open:
        app.close_lookdev()


def _app_frame(gl_window, app) -> None:
    from pyglet import gl

    gl_window.switch_to()
    app.update_viewport(0.0)
    gl.glViewport(0, 0, SIZE, SIZE)
    gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
    app.viewport.render()
    gl.glFinish()
    assert gl.glGetError() == gl.GL_NO_ERROR


def _open(gl_window, app) -> None:
    assert app.open_lookdev()
    for _ in range(4):
        _app_frame(gl_window, app)
    assert app.viewport.shading == "lookdev"


def test_in_the_app_a_morph_weight_a_pose_step_and_the_key_re_render_and_the_camera_does_not(gl_window, head_app):
    app = head_app
    _open(gl_window, app)
    shadow = app.viewport.lookdev_pass.shadow
    assert shadow is not None and shadow.ready
    count = shadow.renders
    _app_frame(gl_window, app)
    assert shadow.renders == count  # a still frame
    app.camera.set_view(0.6, 0.3)
    app._camera_changed()
    _app_frame(gl_window, app)
    app.set_lookdev_studio(exposure=1.0)
    _app_frame(gl_window, app)
    app.set_lookdev_light("key", intensity=2.0, kelvin=4000.0)
    _app_frame(gl_window, app)
    app.viewport.request_capture(lambda rgba: None)
    _app_frame(gl_window, app)
    assert shadow.renders == count  # orbit, exposure, key intensity / colour, capture: +0
    sphere = shadow._sphere
    for step, change in enumerate((lambda: app.set_morph_weight(60, app.lid), lambda: app.jaw(14.0),
                                   lambda: app.set_lookdev_light("key", azimuth=20.0),
                                   lambda: app.set_lookdev_light("key", size=0.6),
                                   lambda: app.set_lookdev_studio(rotation=15.0)), start=1):
        change()
        _app_frame(gl_window, app)
        assert shadow.renders == count + step, step
        _app_frame(gl_window, app)
        assert shadow.renders == count + step, step  # once per change
    assert shadow._sphere == sphere  # a morph weight or a pose step does not move the frustum
    app.set_lookdev_studio(follow_camera=True)
    _app_frame(gl_window, app)
    count = shadow.renders
    app.camera.set_view(0.2, 0.1)
    app._camera_changed()
    _app_frame(gl_window, app)
    assert shadow.renders == count + 1  # "Licht folgt Kamera": the camera turns the key


# -- T1-4: the shadow off is M1 -----------------------------------------------------------------------------------

def test_the_shadow_off_draws_m1_and_creates_nothing(gl_window):
    from tests.test_lookdev_shaders import PINNED_SKIN_SOURCES_SHA256, skin_sources_digest

    assert skin_sources_digest() == (12, PINNED_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=False) == (12, PINNED_SKIN_SOURCES_SHA256)
    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    viewport.set_shading("lookdev", _state(effects=OFF))
    off = _frame(gl_window, viewport)
    passes = viewport.lookdev_pass
    assert passes.shadow is None and passes.features is None  # nothing made, nothing probed
    assert set(passes.programs) == {(False, True, False, False, False)}
    # the program is M1's: built from the pinned sources (the M1 call without the new argument)
    locations = {"position": GLRenderStore.program().attributes["position"]["location"],
                 "normal": GLRenderStore.program().attributes["normal"]["location"]}
    from pyglet.graphics.shader import Shader, ShaderProgram

    m1 = ShaderProgram(*(Shader(src, kind) for src, kind in ls.skin_sources(locations, False, True)))
    passes.programs[(False, True, False, False, False)].delete()
    passes.programs[(False, True, False, False, False)] = m1
    assert np.array_equal(_frame(gl_window, viewport), off)
    # with the shadow on and nothing between the key and the surfaces, the shadow changes no pixel
    viewport.set_shading("lookdev", _state(key_az=0.0, key_el=89.0, effects=lo.LookdevEffects()))
    viewport.remove_object_entry("box")
    on = _frame(gl_window, viewport)
    viewport.set_shading("lookdev", _state(key_az=0.0, key_el=89.0, effects=OFF))
    assert np.array_equal(_frame(gl_window, viewport), on)
    _release(viewport)


# -- AD-039 S3: the dual lobe off is S1, on it changes the highlight --------------------------------------------------

def test_the_dual_lobe_off_draws_s1_and_on_changes_the_highlight(gl_window):
    """AD-039 §6: with the shadow on and the dual lobe off, the frame is S1's - the program built by S1's call
    (`skin_sources(..., shadow)`, without the new argument) draws the same pixels; with the dual lobe on, a material
    with a highlight changes on a sphere (a sharper peak, a broader tail)."""
    from pyglet.graphics.shader import Shader, ShaderProgram

    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    s1 = lo.LookdevEffects(dual_lobe=False, thickness=False, cube=False)
    state = _state(key_az=120.0, key_el=40.0, size=0.1, effects=s1)
    viewport.set_shading("lookdev", state)
    plain_off = _frame(gl_window, viewport)  # GREY: specular 0
    passes = viewport.lookdev_pass
    assert set(passes.programs) == {(False, True, True, False, False)}
    locations = {"position": GLRenderStore.program().attributes["position"]["location"],
                 "normal": GLRenderStore.program().attributes["normal"]["location"]}
    s1_program = ShaderProgram(*(Shader(src, kind) for src, kind in ls.skin_sources(locations, False, True, True)))
    passes.programs[(False, True, True, False, False)].delete()
    passes.programs[(False, True, True, False, False)] = s1_program
    assert np.array_equal(_frame(gl_window, viewport), plain_off)
    _release(viewport)
    viewport = _viewport(gl_window, {"sphere": _sphere()}, OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.0))
    glossy = LookDraw((0.5, 0.5, 0.5), roughness=0.35, specular=1.0)
    viewport.set_object_entry("sphere", viewport.object_entries["sphere"].mesh, (0.5, 0.5, 0.5), look=glossy)
    viewport.set_shading("lookdev", _state(key_az=30.0, key_el=30.0, effects=s1))
    off = _frame(gl_window, viewport)
    viewport.set_shading("lookdev", _state(key_az=30.0, key_el=30.0,
                                           effects=lo.LookdevEffects(thickness=False, cube=False)))
    on = _frame(gl_window, viewport)
    assert (False, True, True, True, False) in viewport.lookdev_pass.programs
    changed = np.abs(on - off).max(axis=-1) > 2
    assert changed.sum() > 50, changed.sum()
    _release(viewport)


# -- AD-039 S4: the key's light through thin parts --------------------------------------------------------------------

SLAB = ((-1.1, -0.5, -0.01), (-0.1, 0.5, 0.01))   # 0.02 thick along the key
BLOCK = ((0.1, -0.5, -0.4), (1.1, 0.5, 0.4))      # 0.8 thick
BACKLIT = LookDraw((0.7, 0.6, 0.5), roughness=0.6, specular=0.0, backscatter=1.0, backscatter_color=(1.0, 1.0, 1.0))


def _flat_box(lo_corner, hi_corner, without=None) -> Mesh:
    """A box of six separate quads (4 vertices each): every face keeps its own normal - `_box` shares its 8 corners,
    so its vertex normals bend toward the corners. `without` = (axis, side): that face left out (an opening)."""
    mesh = Mesh()
    lo_c, hi_c = np.asarray(lo_corner, float), np.asarray(hi_corner, float)
    for axis in range(3):
        for side in (0, 1):
            if (axis, side) == without:
                continue
            quad = []
            for a, b in ((0, 0), (0, 1), (1, 1), (1, 0)):
                index = [0, 0, 0]
                index[axis] = side
                index[(axis + 1) % 3], index[(axis + 2) % 3] = a, b
                quad.append(mesh.add_vertex(tuple(float(v) for v in np.where(index, hi_c, lo_c))))
            outward = np.zeros(3)
            outward[axis] = 1.0 if side else -1.0
            _face(mesh, quad, outward)
    return mesh


def _backlit(gl_window, effects):
    """A thin slab and a thick block side by side, seen face-on from +Z, the key straight behind them (azimuth 180°):
    their visible faces get no direct key light, only the backscatter."""
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=4.5, yaw=0.0, pitch=0.0)
    viewport = _viewport(gl_window, {"slab": _flat_box(*SLAB), "block": _flat_box(*BLOCK)}, camera)
    for key in ("slab", "block"):
        viewport.set_object_entry(key, viewport.object_entries[key].mesh, (0.5, 0.5, 0.5), look=BACKLIT)
    viewport.set_shading("lookdev", _state(key_az=180.0, key_el=0.0, effects=effects))
    return viewport


def _front_pixels(viewport, lo_c, hi_c):
    """The pixels whose ray hits the box's front face (z = hi) well inside its rectangle."""
    origin, direction = _rays(viewport)
    t = (hi_c[2] - origin[..., 2]) / direction[..., 2]
    point = origin + direction * t[..., None]
    inner = ((point[..., 0] > lo_c[0] + 0.1) & (point[..., 0] < hi_c[0] - 0.1)
             & (point[..., 1] > lo_c[1] + 0.1) & (point[..., 1] < hi_c[1] - 0.1) & (t > 0))
    return np.nonzero(inner)


def test_the_thickness_lets_a_thin_slab_through_and_not_a_thick_block(gl_window):
    """AD-039 §7 (T4-1): the key straight behind - the slab's front face (0.02 behind the map's nearest surface)
    transmits `exp(-0.02 / THICKNESS_SCALE)`, the block's (0.8 behind) nothing; the pixels equal the twin
    `lookdev_output(ld_backscatter(..., transmission))`. With the thickness off both faces show M1's view-rim proxy,
    which is 0 face-on."""
    viewport = _backlit(gl_window, lo.LookdevEffects(cube=False))
    pixels = _frame(gl_window, viewport)
    assert (False, True, True, True, True) in viewport.lookdev_pass.programs
    frame = viewport.lookdev_frame()
    n = np.array([0.0, 0.0, 1.0])
    albedo = lo.srgb_decode(BACKLIT.base_color)
    for box, thickness in ((SLAB, 0.02), (BLOCK, 0.8)):
        ys, xs = _front_pixels(viewport, *box)
        assert len(ys) > 200, len(ys)
        transmission = np.full(len(ys), math.exp(-thickness / lo.THICKNESS_SCALE))
        linear = lo.ld_backscatter(albedo, np.broadcast_to(n, (len(ys), 3)), np.broadcast_to(n, (len(ys), 3)), frame,
                                   BACKLIT.backscatter, BACKLIT.backscatter_color, transmission)
        expected = lo.lookdev_output(linear) * 255
        assert np.abs(pixels[ys, xs] - expected).max() <= 2.5, (thickness, np.abs(pixels[ys, xs] - expected).max())
    slab_ys, slab_xs = _front_pixels(viewport, *SLAB)
    block_ys, block_xs = _front_pixels(viewport, *BLOCK)
    assert pixels[slab_ys, slab_xs].mean() > 60 and pixels[block_ys, block_xs].max() <= 2
    viewport.set_shading("lookdev", _state(key_az=180.0, key_el=0.0,
                                           effects=lo.LookdevEffects(thickness=False, cube=False)))
    off = _frame(gl_window, viewport)
    assert off[slab_ys, slab_xs].max() <= 2  # the proxy: (1 - n.v)^3 = 0 face-on
    _release(viewport)


def test_the_thickness_off_draws_s3_and_binds_nothing_on_unit_7(gl_window):
    """AD-039 §7 (T4-2): with the thickness off the program built by S3's call (`skin_sources(..., shadow,
    dual_lobe)`) draws the same pixels; the key in front of the faces leaves the thickness nothing to change; after the
    draw unit 7 has neither texture nor sampler."""
    from pyglet import gl
    from pyglet.graphics.shader import Shader, ShaderProgram

    viewport = _backlit(gl_window, lo.LookdevEffects(thickness=False, cube=False))
    viewport.set_shading("lookdev", _state(key_az=150.0, key_el=20.0,
                                           effects=lo.LookdevEffects(thickness=False, cube=False)))
    s3 = _frame(gl_window, viewport)
    passes = viewport.lookdev_pass
    key = (False, True, True, True, False)
    locations = {"position": GLRenderStore.program().attributes["position"]["location"],
                 "normal": GLRenderStore.program().attributes["normal"]["location"]}
    passes.programs[key].delete()
    passes.programs[key] = ShaderProgram(*(Shader(src, kind)
                                           for src, kind in ls.skin_sources(locations, False, True, True, True)))
    assert np.array_equal(_frame(gl_window, viewport), s3)
    # the key straight in front: no face the camera sees faces away from it - the thickness changes nothing
    viewport.set_shading("lookdev", _state(key_az=0.0, key_el=0.0,
                                           effects=lo.LookdevEffects(thickness=False, cube=False)))
    front_off = _frame(gl_window, viewport)
    viewport.set_shading("lookdev", _state(key_az=0.0, key_el=0.0, effects=lo.LookdevEffects(cube=False)))
    assert np.array_equal(_frame(gl_window, viewport), front_off)
    gl.glActiveTexture(gl.GL_TEXTURE0 + ls.SHADOW_RAW_UNIT)
    bound, sampler = gl.GLint(), gl.GLint()
    gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D, ctypes.byref(bound))
    gl.glGetIntegerv(gl.GL_SAMPLER_BINDING, ctypes.byref(sampler))
    gl.glActiveTexture(gl.GL_TEXTURE0)
    assert (bound.value, sampler.value) == (0, 0)
    assert passes.shadow._raw_sampler != 0  # made by the thickness frame, kept for the next
    _release(viewport)


def test_a_surface_reached_through_an_opening_is_not_lit_through(gl_window):
    """AD-039 §19.6 (Manu 2026-11-24: a hard red patch on Gollum's cheek; the polygons behind the eye were deleted, and
    the eyes do not cast): a block open on the key's side - the key, straight behind, enters through the opening and
    reaches the inside of the front face with no tissue in front of it, so the front face is the map's nearest
    surface. It gets no transmission (before the fix: all of it, a flat bright patch); the closed thin slab beside it
    still transmits exp(-0.02 / scale)."""
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=4.5, yaw=0.0, pitch=0.0)
    meshes = {"slab": _flat_box(*SLAB), "open": _flat_box(*BLOCK, without=(2, 0))}
    viewport = _viewport(gl_window, meshes, camera)
    for key in meshes:
        viewport.set_object_entry(key, viewport.object_entries[key].mesh, (0.5, 0.5, 0.5), look=BACKLIT)
    viewport.set_shading("lookdev", _state(key_az=180.0, key_el=0.0, effects=lo.LookdevEffects()))
    pixels = _frame(gl_window, viewport)
    ys, xs = _front_pixels(viewport, *BLOCK)
    assert len(ys) > 200 and pixels[ys, xs].max() <= 2, pixels[ys, xs].max()
    slab_ys, slab_xs = _front_pixels(viewport, *SLAB)
    assert pixels[slab_ys, slab_xs].mean() > 60
    _release(viewport)


def test_without_sampler_objects_the_thickness_is_off_with_a_status_line(gl_window, monkeypatch):
    """AD-039 §2.2 / §7 (T4-3): `sampler_objects` stubbed false - the frame equals the thickness-off frame, the status
    line once, the shadow stays on."""
    reference = _backlit(gl_window, lo.LookdevEffects(thickness=False, cube=False))
    want = _frame(gl_window, reference)
    _release(reference)
    monkeypatch.setitem(lookdev_features.CHECKS, "sampler_objects", lambda: False)
    viewport = _backlit(gl_window, lo.LookdevEffects(cube=False))
    assert np.array_equal(_frame(gl_window, viewport), want)
    effects = viewport.lookdev_effects()
    assert effects.shadow and not effects.thickness
    assert viewport.take_lookdev_notices() == ["LookDev: Durchleuchtung aus – Sampler-Objekte nicht verfügbar"]
    assert viewport.take_lookdev_notices() == []
    _release(viewport)


# -- T1-5: the GL state as found ------------------------------------------------------------------------------------

def _full_state() -> dict:
    from pyglet import gl

    def geti(name, count=1):
        buf = (gl.GLint * count)()
        gl.glGetIntegerv(name, buf)
        return buf[0] if count == 1 else tuple(buf)

    def getf(name):
        value = gl.GLfloat()
        gl.glGetFloatv(name, ctypes.byref(value))
        return value.value

    state = snapshot_gl_state()
    state.update(draw_fbo=geti(gl.GL_DRAW_FRAMEBUFFER_BINDING), read_fbo=geti(gl.GL_READ_FRAMEBUFFER_BINDING),
                 depth_func=geti(gl.GL_DEPTH_FUNC), offset_fill=bool(gl.glIsEnabled(gl.GL_POLYGON_OFFSET_FILL)),
                 offset=(getf(gl.GL_POLYGON_OFFSET_FACTOR), getf(gl.GL_POLYGON_OFFSET_UNITS)))
    active = geti(gl.GL_ACTIVE_TEXTURE)
    for unit in range(8):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        state[f"unit{unit}"] = (geti(gl.GL_TEXTURE_BINDING_2D), geti(gl.GL_TEXTURE_BINDING_BUFFER),
                                geti(gl.GL_SAMPLER_BINDING))
    gl.glActiveTexture(active)
    return state


def test_a_frame_that_renders_the_map_leaves_the_gl_state_as_found(gl_window):
    from pyglet import gl

    from mirai.eye_object import DEFAULT_EYE, cornea_triangles, shell_mesh
    from viewport.eye_pass import EyeDraw
    from viewport.material import DEFAULT_FINISH

    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    grey = (0.6, 0.6, 0.6)
    eye_model = [0.4, 0, 0, 0, 0, 0.4, 0, 0, 0, 0, 0.4, 0, 0.5, 0.3, 0.6, 1.0]
    viewport.set_object_entry("eye", shell_mesh(DEFAULT_EYE), grey, model_matrix=eye_model, finish=DEFAULT_FINISH,
                              eye=EyeDraw(DEFAULT_EYE, None, grey, DEFAULT_FINISH, cornea_triangles()))
    viewport.set_eye_display(tier="full")
    state = _state()
    viewport.set_shading("lookdev", state)
    _frame(gl_window, viewport)  # compiles
    for change in range(2):
        viewport.set_shading("lookdev", dataclasses.replace(state, rotation=10.0 * (change + 1)))
        gl.glUseProgram(0)
        gl.glEnable(gl.GL_SCISSOR_TEST)  # imgui's state between frames: a scissor box, an offset left by a draw
        gl.glPolygonOffset(0.5, 0.25)
        before = _full_state()
        renders = viewport.lookdev_pass.shadow.renders
        _frame(gl_window, viewport)
        assert viewport.lookdev_pass.shadow.renders == renders + 1  # this frame rendered the map
        assert _full_state() == before
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glPolygonOffset(0.0, 0.0)
    _release(viewport)
    viewport.eye_pass.release()


# -- T1-6: a missing depth texture ----------------------------------------------------------------------------------

def test_without_a_depth_texture_the_shadow_is_off_with_a_status_line(gl_window, monkeypatch):
    camera = OrbitCamera(target=(0.0, 0.2, 0.0), distance=5.5, yaw=0.3, pitch=0.75)
    reference = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    reference.set_shading("lookdev", _state(effects=lo.LookdevEffects(shadow=False)))  # the other effects stay on
    m1 = _frame(gl_window, reference)
    _release(reference)
    monkeypatch.setitem(lookdev_features.CHECKS, "depth_texture", lambda: False)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    viewport.set_shading("lookdev", _state())
    assert np.array_equal(_frame(gl_window, viewport), m1)
    passes = viewport.lookdev_pass
    assert passes.shadow is None and passes.features == lookdev_features.FeatureReport(depth_texture=False)
    assert not viewport.lookdev_effects().shadow
    assert viewport.take_lookdev_notices() == ["LookDev: Schatten aus – Tiefentextur nicht verfügbar"]
    assert viewport.take_lookdev_notices() == []  # once
    _frame(gl_window, viewport)
    assert viewport.take_lookdev_notices() == []  # not retried in the session
    _release(viewport)


def test_in_the_app_a_missing_depth_texture_shows_the_status_line_and_greys_the_effect(gl_window, head_app,
                                                                                        monkeypatch):
    from gui import lookdev_model as lm

    monkeypatch.setitem(lookdev_features.CHECKS, "depth_texture", lambda: False)
    app = head_app
    assert app.open_lookdev()
    statuses = []
    for _ in range(4):
        _app_frame(gl_window, app)
        statuses.append(app.status_message)
    assert "LookDev: Schatten aus – Tiefentextur nicht verfügbar" in statuses, statuses
    assert app.viewport.lookdev_pass.shadow is None
    row = lm.state(app).effects[0]
    assert row.name == "shadow" and row.on and not row.available and row.reason == "Tiefentextur fehlt"


def test_switching_the_shadow_on_compiles_behind_the_status_line_and_keeps_the_frame_before(gl_window, head_app):
    app = head_app
    app.set_lookdev_effect("shadow", False)
    _open(gl_window, app)
    passes = app.viewport.lookdev_pass
    assert passes.shadow is None and not any(k[2] for k in passes.programs)
    assert app.set_lookdev_effect("shadow", True)
    assert app.status_message == "LookDev: Shader werden vorbereitet …" and app.lookdev.preparing
    _app_frame(gl_window, app)  # the frame before, with the status line: still LookDev, nothing compiled in it
    assert app.viewport.shading == "lookdev" and not app.viewport.lookdev_state.effects.shadow
    assert not any(k[2] for k in passes.programs)
    _app_frame(gl_window, app)  # compiled, then drawn with the shadow
    assert any(k[2] for k in passes.programs) and app.viewport.lookdev_state.effects.shadow
    assert "Shader in" in app.status_message and passes.shadow is not None and passes.shadow.ready
    assert app.set_lookdev_effect("shadow", False)  # off needs no compile: at once
    assert not app.lookdev.preparing and not app.viewport.lookdev_state.effects.shadow


# -- parity of the GLSL against the NumPy twins -------------------------------------------------------------------

PARITY_BODY = """
uniform samplerBuffer u_inputs;
uniform int u_width;
uniform int u_count;
layout(location = 0) out vec4 out_value;
void main() {
    int i = int(gl_FragCoord.y) * u_width + int(gl_FragCoord.x);
    if (i >= u_count) { out_value = vec4(0.0); return; }
    vec4 a = texelFetch(u_inputs, 2 * i);
    vec4 b = texelFetch(u_inputs, 2 * i + 1);
    out_value = vec4(ld_shadow_pcf(a.xyz, b.xy), 0.0, 0.0, 1.0);
}
"""


@pytest.mark.parametrize("scale", [1.0, 0.5])
def test_ld_shadow_pcf_matches_pcf_visibility(gl_window, scale):
    """A random 64² depth map uploaded as the compare texture, `scale` of it the rendered part (a soft key's effective
    resolution); `ld_shadow_pcf` at 4,096 map points with random receiver-plane slopes against the NumPy twin: inside,
    near the border (lit outside) and outside the depth range."""
    from pyglet import gl
    from pyglet.graphics.shader import Shader, ShaderProgram

    from viewport.gl_render_store import _register_sampler_buffer_uniform
    from viewport.lookdev_shadow import register_shadow_sampler_uniform

    gl_window.switch_to()
    _register_sampler_buffer_uniform()
    register_shadow_sampler_uniform()
    rng = np.random.default_rng(7)
    size, width, count = 64, 64, 4096
    depth = rng.uniform(0.2, 0.9, (size, size)).astype(np.float32)
    sp = np.concatenate([rng.uniform(0.0, 1.0, (count - 96, 3)), rng.uniform(-0.05, 0.05, (32, 3)) + [0.0, 0.5, 0.5],
                         rng.uniform(0.98, 1.06, (32, 3)), rng.uniform(0.0, 1.0, (32, 3)) * [1, 1, 0] + [0, 0, 1.02]])
    slopes = rng.uniform(-2.0, 2.0, (count, 2))
    expected = lo.pcf_visibility(depth.astype(np.float64), sp, scale, slopes)

    def gen(fn) -> int:
        ident = gl.GLuint()
        fn(1, ctypes.byref(ident))
        return ident.value

    texture, buffer, buf_tex, fbo, rbo, vao = (gen(gl.glGenTextures), gen(gl.glGenBuffers), gen(gl.glGenTextures),
                                               gen(gl.glGenFramebuffers), gen(gl.glGenRenderbuffers),
                                               gen(gl.glGenVertexArrays))
    gl.glActiveTexture(gl.GL_TEXTURE0 + ls.SHADOW_UNIT)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24, size, size, 0, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT,
                    depth.ctypes.data_as(ctypes.c_void_p))
    for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                        (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER),
                        (gl.GL_TEXTURE_COMPARE_MODE, gl.GL_COMPARE_REF_TO_TEXTURE),
                        (gl.GL_TEXTURE_COMPARE_FUNC, gl.GL_LEQUAL)):
        gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
    gl.glTexParameterfv(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_BORDER_COLOR, (gl.GLfloat * 4)(1.0, 1.0, 1.0, 1.0))
    data = np.zeros((count, 2, 4), np.float32)
    data[:, 0, :3], data[:, 1, :2] = sp, slopes
    gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, buffer)
    gl.glBufferData(gl.GL_TEXTURE_BUFFER, data.nbytes, data.ctypes.data_as(ctypes.c_void_p), gl.GL_STATIC_DRAW)
    gl.glActiveTexture(gl.GL_TEXTURE0 + 1)
    gl.glBindTexture(gl.GL_TEXTURE_BUFFER, buf_tex)
    gl.glTexBuffer(gl.GL_TEXTURE_BUFFER, gl.GL_RGBA32F, buffer)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    height = count // width
    gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, rbo)
    gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA32F, width, height)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_RENDERBUFFER, rbo)
    assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
    fragment = "#version 330 core\n" + ls.LD_SHADOW_SRC + PARITY_BODY
    program = ShaderProgram(Shader(ls.FULLSCREEN_VERTEX_SRC, "vertex"), Shader(fragment, "fragment"))
    program.use()
    program["u_inputs"] = 1
    program["u_width"] = width
    program["u_count"] = count
    program["u_ld_shadow"] = ls.SHADOW_UNIT
    program["u_ld_shadow_radius"] = 1.0 / size
    program["u_ld_shadow_scale"] = scale
    gl.glViewport(0, 0, width, height)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glBindVertexArray(vao)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
    out = np.zeros((height, width, 4), np.float32)
    gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_FLOAT, out.ctypes.data_as(ctypes.c_void_p))
    gl.glBindVertexArray(0)
    program.stop()
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glViewport(0, 0, SIZE, SIZE)
    for unit, target in ((ls.SHADOW_UNIT, gl.GL_TEXTURE_2D), (1, gl.GL_TEXTURE_BUFFER)):
        gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
        gl.glBindTexture(target, 0)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    got = out.reshape(-1, 4)[:count, 0]
    for ident, fn in ((fbo, gl.glDeleteFramebuffers), (rbo, gl.glDeleteRenderbuffers), (vao, gl.glDeleteVertexArrays),
                      (buffer, gl.glDeleteBuffers)):
        fn(1, ctypes.byref(gl.GLuint(ident)))
    for ident in (texture, buf_tex):
        gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(ident)))
    program.delete()
    assert gl.glGetError() == gl.GL_NO_ERROR
    # the hardware's bilinear weights carry a few bits of sub-texel precision: 1/9 of a weight step per fetch
    assert np.abs(got - expected).max() <= 0.02, np.abs(got - expected).max()
    assert np.abs(got - expected).mean() <= 0.003
    assert (got[-64:] == 1.0).all()  # outside the map's box: lit


@pytest.mark.parametrize("dual", [False, True])
def test_the_shadow_block_matches_ld_key_shadowed(gl_window, dual):
    """A plane half under a box, the key at 45°, a fill and SH9 from an environment, a wrap and a GGX highlight: the
    plane's colour in the full shadow and in the light equals `lookdev_output(ld_key_shadowed(...))` with visibility 0
    and 1 - the twin of the `SHADOW` block. The studio specular is the M1 lever off (`env_spec`), so the pixel is the
    twin exactly. AD-039 S3 (`dual`): the same with the `DUAL_LOBE` blocks (the key's dual highlight in shadow)."""
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=5.5, yaw=0.0, pitch=1.2)
    viewport = _viewport(gl_window, {"ground": _ground(), "box": _box(*BOX)}, camera)
    studio = lo.Studio((0.3, 0.3, 0.32), (0.2, 0.2, 0.2), (0.05, 0.05, 0.05))
    state = _state(key_az=90.0, key_el=45.0, studio=studio, env_intensity=0.6,
                   fill=lo.StudioLight(True, 0.4, -60.0, 30.0, 6500.0, 0.2),
                   effects=lo.LookdevEffects(dual_lobe=dual))
    look = LookDraw((0.6, 0.5, 0.4), roughness=0.5, specular=0.5, wrap_rgb=(0.2, 0.1, 0.05))
    for key in ("ground", "box"):
        viewport.set_object_entry(key, viewport.object_entries[key].mesh, (0.5, 0.5, 0.5), look=look)
    viewport.lookdev_pass.env_spec = False
    viewport.set_shading("lookdev", state)
    pixels = _frame(gl_window, viewport)
    origin, direction = _rays(viewport)
    on_box, _ = _hits_box(origin, direction, *BOX)
    on_box = _grow(on_box)
    t = -origin[..., 1] / direction[..., 1]
    point = origin + direction * t[..., None]
    key = _key_dir(state)
    shaded, _ = _hits_box(point, np.broadcast_to(key, point.shape), *BOX)
    band = np.zeros_like(shaded)
    for dx, dz in BAND * 0.06:
        moved, _ = _hits_box(point + np.array([dx, 0.0, dz]), np.broadcast_to(key, point.shape), *BOX)
        band |= moved != shaded
    frame = viewport.lookdev_frame()
    n = np.array([0.0, 1.0, 0.0])
    albedo = lo.srgb_decode(look.base_color)
    for want, visibility in ((True, 0.0), (False, 1.0)):
        mask = (t > 0) & ~on_box & (shaded == want) & ~band
        mask &= (np.abs(point[..., 0]) < 1.5) & (np.abs(point[..., 2]) < 1.5)
        ys, xs = np.nonzero(mask)
        assert len(ys) > 100, (want, len(ys))
        v = -direction[ys, xs]
        normals = np.broadcast_to(n, v.shape)
        linear = lo.ld_key_shadowed(albedo, normals, v, look.wrap_rgb, look.roughness, look.f0, frame,
                                    np.full(len(ys), visibility), dual=dual)
        expected = lo.lookdev_output(linear) * 255
        assert np.abs(pixels[ys, xs] - expected).max() <= 2.5, (want, np.abs(pixels[ys, xs] - expected).max())
    _release(viewport)


_IDENTITY = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)

THICKNESS_PARITY_BODY = """
uniform samplerBuffer u_inputs;
uniform int u_width;
uniform int u_count;
layout(location = 0) out vec4 out_value;
void main() {
    int i = int(gl_FragCoord.y) * u_width + int(gl_FragCoord.x);
    if (i >= u_count) { out_value = vec4(0.0); return; }
    vec3 sp = texelFetch(u_inputs, i).xyz;
    // the identity map matrix: the map point of p is p * 0.5 + 0.5
    out_value = vec4(ld_key_transmission(sp * 2.0 - 1.0), 0.0, 0.0, 1.0);
}
"""


@pytest.mark.parametrize("scale", [1.0, 0.5])
def test_ld_key_transmission_matches_key_transmission(gl_window, scale):
    """AD-039 §7 (twin): a smooth random 64² depth map uploaded as the shadow's compare texture and read raw on unit 7
    through `KeyShadow`'s sampler object (the production binding); `ld_key_transmission` at 4,096 map points against
    `lookdev_optics.key_transmission`: inside, at and in front of the surface (none: no tissue in front), outside the
    map (none)."""
    from pyglet import gl
    from pyglet.graphics.shader import Shader, ShaderProgram

    from viewport.gl_render_store import _register_sampler_buffer_uniform
    from viewport.lookdev_shadow import KeyShadow, register_shadow_sampler_uniform

    gl_window.switch_to()
    _register_sampler_buffer_uniform()
    register_shadow_sampler_uniform()
    rng = np.random.default_rng(11)
    size, width, count, depth_range = 64, 64, 4096, 0.3
    coarse = rng.uniform(0.3, 0.7, (9, 9))  # smooth: a 9 x 9 grid interpolated up to 64 x 64
    grid = np.linspace(0, 8, size)
    rows = np.array([np.interp(grid, np.arange(9), coarse[j]) for j in range(9)])
    depth = np.ascontiguousarray(np.array([np.interp(grid, np.arange(9), rows[:, i]) for i in range(size)]).T,
                                 dtype=np.float32)  # C order: the upload reads rows
    sp = rng.uniform(0.0, 1.0, (count, 3))
    sp[:, 2] = rng.uniform(0.25, 0.95, count)  # around the stored depths: in front of and behind the surface
    sp[-64:, 0] = rng.uniform(1.01, 1.2, 64)  # outside the map's box
    expected = lo.key_transmission(depth.astype(np.float64), sp, depth_range, scale)

    def gen(fn) -> int:
        ident = gl.GLuint()
        fn(1, ctypes.byref(ident))
        return ident.value

    texture, buffer, buf_tex, fbo, rbo, vao = (gen(gl.glGenTextures), gen(gl.glGenBuffers), gen(gl.glGenTextures),
                                               gen(gl.glGenFramebuffers), gen(gl.glGenRenderbuffers),
                                               gen(gl.glGenVertexArrays))
    gl.glActiveTexture(gl.GL_TEXTURE0 + ls.SHADOW_UNIT)
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
    gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_DEPTH_COMPONENT24, size, size, 0, gl.GL_DEPTH_COMPONENT, gl.GL_FLOAT,
                    depth.ctypes.data_as(ctypes.c_void_p))
    for name, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                        (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_BORDER), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_BORDER),
                        (gl.GL_TEXTURE_COMPARE_MODE, gl.GL_COMPARE_REF_TO_TEXTURE),
                        (gl.GL_TEXTURE_COMPARE_FUNC, gl.GL_LEQUAL)):
        gl.glTexParameteri(gl.GL_TEXTURE_2D, name, value)
    gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
    shadow = KeyShadow(size=size)
    shadow._targets = [(texture, 0)]  # the uploaded map stands in for a rendered one (bind_raw reads only this)
    shadow.bind_raw(ls.SHADOW_RAW_UNIT)
    data = np.zeros((count, 4), np.float32)
    data[:, :3] = sp
    gl.glBindBuffer(gl.GL_TEXTURE_BUFFER, buffer)
    gl.glBufferData(gl.GL_TEXTURE_BUFFER, data.nbytes, data.ctypes.data_as(ctypes.c_void_p), gl.GL_STATIC_DRAW)
    gl.glActiveTexture(gl.GL_TEXTURE0 + 1)
    gl.glBindTexture(gl.GL_TEXTURE_BUFFER, buf_tex)
    gl.glTexBuffer(gl.GL_TEXTURE_BUFFER, gl.GL_RGBA32F, buffer)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    height = count // width
    gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, rbo)
    gl.glRenderbufferStorage(gl.GL_RENDERBUFFER, gl.GL_RGBA32F, width, height)
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
    gl.glFramebufferRenderbuffer(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_RENDERBUFFER, rbo)
    assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
    fragment = "#version 330 core\n" + ls.LD_SHADOW_SRC + ls.LD_THICKNESS_SRC + THICKNESS_PARITY_BODY
    program = ShaderProgram(Shader(ls.FULLSCREEN_VERTEX_SRC, "vertex"), Shader(fragment, "fragment"))
    program.use()
    active = program.uniforms
    values = {"u_inputs": 1, "u_width": width, "u_count": count, "u_ld_shadow_depth": ls.SHADOW_RAW_UNIT,
              "u_ld_shadow_vp": _IDENTITY, "u_ld_shadow_offset": 0.0, "u_ld_shadow_scale": scale,
              "u_ld_shadow_range": depth_range}
    for name, value in values.items():
        if name in active:
            program[name] = value
    gl.glViewport(0, 0, width, height)
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glBindVertexArray(vao)
    gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
    out = np.zeros((height, width, 4), np.float32)
    gl.glReadPixels(0, 0, width, height, gl.GL_RGBA, gl.GL_FLOAT, out.ctypes.data_as(ctypes.c_void_p))
    gl.glBindVertexArray(0)
    program.stop()
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
    gl.glViewport(0, 0, SIZE, SIZE)
    KeyShadow.unbind_raw(ls.SHADOW_RAW_UNIT)
    gl.glActiveTexture(gl.GL_TEXTURE0 + 1)
    gl.glBindTexture(gl.GL_TEXTURE_BUFFER, 0)
    gl.glActiveTexture(gl.GL_TEXTURE0)
    got = out.reshape(-1, 4)[:count, 0]
    for ident, fn in ((fbo, gl.glDeleteFramebuffers), (rbo, gl.glDeleteRenderbuffers), (vao, gl.glDeleteVertexArrays),
                      (buffer, gl.glDeleteBuffers)):
        fn(1, ctypes.byref(gl.GLuint(ident)))
    shadow._targets = []
    shadow.release()
    for ident in (texture, buf_tex):
        gl.glDeleteTextures(1, ctypes.byref(gl.GLuint(ident)))
    program.delete()
    assert gl.glGetError() == gl.GL_NO_ERROR
    # the raw read ignores the texture's compare mode (the sampler object's NONE wins): else every value would be 0 or 1
    assert ((got > 0.05) & (got < 0.95)).sum() > 200
    # the hardware's bilinear weights carry a few bits of sub-texel precision (8 in the GL spec's minimum)
    assert np.abs(got - expected).max() <= 0.03, np.abs(got - expected).max()
    assert np.abs(got - expected).mean() <= 0.003
    assert (got[-64:] == 0.0).all()  # outside the map's box: no light passes
