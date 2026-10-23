"""Viewport shading in the real GL path (AD-018 addendum 2026-10-15).

- No visible triangulation: the same non-planar quad grid, triangulated along the one or the
  other diagonal, must look the same in Smooth (bilinear quad normals) and in Flat (one normal per
  polygon). The control case - the same store with the face data switched off, i.e. the old
  per-triangle shading - must differ, so the test can see the problem it guards against.
- Worklight (light_rig, promoted from the Shading Lab): "Heute" reproduces the old single light,
  every preset changes the image, and a light change is draw state only (no upload, same
  VertexList).
- Specular / gloss (`viewport.material`, 2026-10-23): the shader's highlight equals the Python
  reference, strength and glossiness change the image, Flat keeps one colour per polygon, and a
  finish change is a material update only (same VertexList, no geometry upload).

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_shading.py`); skips without.
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from viewport.gl_render_store import DEFAULT_BASE_COLOR, GLRenderStore  # noqa: E402
from viewport.light_rig import (  # noqa: E402
    PRESET_HEUTE,
    PRESET_ORDER,
    PRESET_RAITT,
    PRESETS,
    resolve,
    shade,
)
from viewport.material import DEFAULT_FINISH, MATTE_FINISH, Material, SurfaceFinish  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402

SIZE = 160
BACKGROUND = (0.0, 0.0, 0.0)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _grid(rotate: bool, lift: float = 0.8) -> Mesh:
    """2x2 quads in the XY plane, centre vertex lifted: four non-planar quads with varying vertex
    normals. `rotate` starts every face one corner later, so the fan uses the other diagonal."""
    mesh = Mesh()
    ids = {}
    for j in range(3):
        for i in range(3):
            z = lift if (i, j) == (1, 1) else 0.0
            ids[i, j] = mesh.add_vertex((i - 1.0, j - 1.0, z))
    for j in range(2):
        for i in range(2):
            face = [ids[i, j], ids[i + 1, j], ids[i + 1, j + 1], ids[i, j + 1]]
            mesh.add_face(face[1:] + face[:1] if rotate else face)
    return mesh


def _build(gl_window, mesh: Mesh):
    gl_window.switch_to()
    rm = RenderMesh(mesh, store_type=GLRenderStore)
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=1.0)
    rm.sync()
    return rm, camera


def _draw(gl_window, rm: RenderMesh, camera) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, *gl_window.get_framebuffer_size())
    gl.glClearColor(*BACKGROUND, 1.0)
    gl_window.clear()
    rm.render(camera)
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _render(
    gl_window, mesh: Mesh, *, flat: bool, face_data: bool = True, light=None, finish=None
) -> bytes:
    rm, camera = _build(gl_window, mesh)
    if finish is not None:
        rm.bind_material(Material(DEFAULT_BASE_COLOR, finish))
        rm.mark_material_dirty()
        rm.sync()
    rm.store.set_draw_style(flat=flat, polygon_offset=False)
    if light is not None:
        rm.store.set_light_uniforms(light)
    if not face_data:
        rm.store._flush_face_data = lambda: False  # the old per-triangle path
    pixels = _draw(gl_window, rm, camera)
    rm.store.release()
    return pixels


def _diff(a: bytes, b: bytes) -> tuple[int, int]:
    """(max channel difference, pixels differing by more than 2 levels)."""
    diffs = [abs(x - y) for x, y in zip(a, b)]
    pixels = sum(1 for i in range(0, len(diffs), 3) if max(diffs[i:i + 3]) > 2)
    return max(diffs), pixels


def _covered(pixels: bytes) -> int:
    return sum(1 for i in range(0, len(pixels), 3) if any(pixels[i:i + 3]))


# -- no visible triangles ------------------------------------------------------------------


@pytest.mark.parametrize("flat", [False, True], ids=["smooth", "flat"])
def test_shading_does_not_depend_on_the_triangulation_diagonal(gl_window, flat):
    a = _render(gl_window, _grid(rotate=False), flat=flat)
    b = _render(gl_window, _grid(rotate=True), flat=flat)
    assert _covered(a) > SIZE * SIZE // 4  # the grid is on screen, facing the camera
    _max, differing = _diff(a, b)
    # Only the depth of the lifted surface differs between the two triangulations; a handful of
    # pixels along the silhouette/diagonal may round differently.
    assert differing <= 40, differing


@pytest.mark.parametrize("flat", [False, True], ids=["smooth", "flat"])
def test_per_triangle_shading_shows_the_diagonal(gl_window, flat):
    """Control: without face data the two triangulations really look different."""
    a = _render(gl_window, _grid(rotate=False), flat=flat, face_data=False)
    b = _render(gl_window, _grid(rotate=True), flat=flat, face_data=False)
    _max, differing = _diff(a, b)
    assert differing > 400, differing


def _max_neighbour_jump(pixels: bytes) -> int:
    jump = 0
    for y in range(SIZE):
        for x in range(SIZE - 1):
            i = (y * SIZE + x) * 3
            a, b = pixels[i:i + 3], pixels[i + 3:i + 6]
            if any(a) and any(b):
                jump = max(jump, max(abs(p - q) for p, q in zip(a, b)))
    return jump


def test_smooth_has_no_seams_between_bent_quads(gl_window):
    """Neighbouring quads agree on their shared edge: no colour step anywhere on the surface
    (one shading plane per quad would leave seams on bent quads)."""
    for lift in (0.8, 1.2):
        assert _max_neighbour_jump(_render(gl_window, _grid(False, lift), flat=False)) <= 3


def test_flat_is_one_colour_per_polygon(gl_window):
    pixels = _render(gl_window, _grid(rotate=False), flat=True)
    colours = {pixels[i:i + 3] for i in range(0, len(pixels), 3) if any(pixels[i:i + 3])}
    # Four quads; anti-aliasing is off, so edge pixels belong to one of them.
    assert len(colours) <= 4, len(colours)


# -- worklight ------------------------------------------------------------------------------


def _flat_quad() -> Mesh:
    mesh = Mesh()
    ids = [mesh.add_vertex(p) for p in ((-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0))]
    mesh.add_face(ids)
    return mesh


def test_heute_reproduces_the_old_single_light(gl_window):
    """With the matte finish (no highlight) - the look before 2026-10-23."""
    pixels = _render(gl_window, _flat_quad(), flat=False, finish=MATTE_FINISH)
    centre = (SIZE // 2 * SIZE + SIZE // 2) * 3
    expected = shade((0.0, 0.0, 1.0), resolve(PRESETS[PRESET_HEUTE]), DEFAULT_BASE_COLOR)
    # The pre-2026-10-15 shader: mix(base * 0.35, base, N·L) with L = normalize(0.4, 0.6, 0.7).
    length = (0.4 ** 2 + 0.6 ** 2 + 0.7 ** 2) ** 0.5
    old = tuple(c * (0.35 + 0.65 * 0.7 / length) for c in DEFAULT_BASE_COLOR)
    for got, want, was in zip(pixels[centre:centre + 3], expected, old):
        assert abs(got - round(want * 255)) <= 1
        assert abs(got - round(was * 255)) <= 1


def test_every_preset_changes_the_image(gl_window):
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0)
    images = {
        name: _render(gl_window, _grid(rotate=False), flat=False,
                      light=resolve(PRESETS[name], camera))
        for name in PRESET_ORDER
    }
    for name in PRESET_ORDER:
        if name != PRESET_HEUTE:
            assert _diff(images[name], images[PRESET_HEUTE])[1] > 100, name


def test_light_change_is_draw_state_only(gl_window):
    rm, camera = _build(gl_window, _grid(rotate=False))
    _draw(gl_window, rm, camera)
    vlist = rm.store.vertex_list()
    ids = rm.resource_ids()
    counters = dict(rm.benchmark_counters)
    uploaded = rm.stats.uploaded_bytes
    for name in PRESET_ORDER:
        rm.store.set_light_uniforms(resolve(PRESETS[name], camera))
        _draw(gl_window, rm, camera)
    assert rm.store.vertex_list() is vlist
    assert rm.resource_ids() == ids
    assert dict(rm.benchmark_counters) == counters
    assert rm.stats.uploaded_bytes == uploaded
    rm.store.release()


def test_moving_a_vertex_patches_the_face_data(gl_window):
    """After a move the patched store draws exactly what a fresh build of the moved mesh draws."""
    mesh = _grid(rotate=False, lift=0.0)
    rm, camera = _build(gl_window, mesh)
    _draw(gl_window, rm, camera)  # first full upload
    centre = mesh.all_vertex_ids()[4]
    mesh.set_vertex_position(centre, (0.0, 0.0, 0.35))
    rm.mark_vertices_dirty({centre})
    rm.sync()
    assert rm.store._face_dirty["face_shading"]  # row ranges, not a full re-upload
    patched = _draw(gl_window, rm, camera)
    rm.store.release()

    fresh = _render(gl_window, _grid(rotate=False, lift=0.35), flat=False)
    assert _diff(patched, fresh) == (0, 0)


# -- specular / gloss (viewport.material) -------------------------------------------------------


def _centre(pixels: bytes) -> bytes:
    i = (SIZE // 2 * SIZE + SIZE // 2) * 3
    return pixels[i:i + 3]


@pytest.mark.parametrize(
    "finish",
    [DEFAULT_FINISH, SurfaceFinish(specular=1.0, glossiness=0.25), SurfaceFinish(specular=0.6, glossiness=0.0)],
    ids=["default", "strong-broad", "broadest"],
)
def test_shader_highlight_matches_the_reference(gl_window, finish):
    """Centre of a quad facing the camera: N = V = +Z (eye on the axis), light "Heute" (world)."""
    pixels = _render(gl_window, _flat_quad(), flat=False, finish=finish)
    expected = shade((0.0, 0.0, 1.0), resolve(PRESETS[PRESET_HEUTE]), DEFAULT_BASE_COLOR,
                     view_dir=(0.0, 0.0, 1.0), finish=finish)
    for got, want in zip(_centre(pixels), expected):
        assert abs(got - round(min(want, 1.0) * 255)) <= 1


def test_specular_strength_and_glossiness_change_the_image(gl_window):
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0)
    light = resolve(PRESETS[PRESET_RAITT], camera)
    mesh = lambda: _grid(rotate=False, lift=0.8)  # noqa: E731 - curved enough for a highlight
    matte = _render(gl_window, mesh(), flat=False, light=light, finish=MATTE_FINISH)
    default = _render(gl_window, mesh(), flat=False, light=light, finish=DEFAULT_FINISH)
    strong = _render(gl_window, mesh(), flat=False, light=light, finish=DEFAULT_FINISH.with_(specular=0.8))
    glossy = _render(gl_window, mesh(), flat=False, light=light, finish=DEFAULT_FINISH.with_(glossiness=0.9))
    assert _diff(default, matte)[1] > 50
    assert _diff(strong, default)[1] > 50
    assert _diff(glossy, default)[1] > 50
    # the highlight only adds light: no pixel gets darker than the matte image
    assert all(d >= m for d, m in zip(strong, matte))
    # a tighter highlight lights fewer pixels noticeably
    lit = lambda img: sum(  # noqa: E731
        1 for i in range(0, len(img), 3) if max(img[i:i + 3]) - max(matte[i:i + 3]) > 6
    )
    assert lit(_render(gl_window, mesh(), flat=False, light=light, finish=SurfaceFinish(0.8, 0.9))) < lit(
        _render(gl_window, mesh(), flat=False, light=light, finish=SurfaceFinish(0.8, 0.1))
    )


def test_flat_with_specular_stays_one_colour_per_polygon(gl_window):
    """Flat uses the face normal and a non-local viewer for the highlight too."""
    finish = SurfaceFinish(specular=0.6, glossiness=0.3)
    pixels = _render(gl_window, _grid(rotate=False), flat=True, finish=finish)
    matte = _render(gl_window, _grid(rotate=False), flat=True, finish=MATTE_FINISH)
    assert _diff(pixels, matte)[1] > 50
    colours = {pixels[i:i + 3] for i in range(0, len(pixels), 3) if any(pixels[i:i + 3])}
    assert len(colours) <= 4, len(colours)
    other = _render(gl_window, _grid(rotate=True), flat=True, finish=finish)
    assert _diff(pixels, other)[1] <= 40  # still independent of the triangulation diagonal


def test_smooth_with_specular_has_no_triangulation_diagonal(gl_window):
    finish = SurfaceFinish(specular=0.8, glossiness=0.4)
    a = _render(gl_window, _grid(rotate=False), flat=False, finish=finish)
    b = _render(gl_window, _grid(rotate=True), flat=False, finish=finish)
    assert _diff(a, b)[1] <= 40


def test_finish_change_is_a_material_update_only(gl_window):
    rm, camera = _build(gl_window, _grid(rotate=False))
    rm.bind_material(Material(DEFAULT_BASE_COLOR, DEFAULT_FINISH))
    rm.mark_material_dirty()
    rm.sync()
    first = _draw(gl_window, rm, camera)
    vlist = rm.store.vertex_list()
    ids = {k: v for k, v in rm.resource_ids().items() if k != "material_uniforms"}
    counters = dict(rm.benchmark_counters)
    rm.bind_material(Material(DEFAULT_BASE_COLOR, SurfaceFinish(specular=0.9, glossiness=0.1)))
    rm.mark_material_dirty()
    rm.sync()
    second = _draw(gl_window, rm, camera)
    assert _diff(first, second)[1] > 50
    assert rm.store.vertex_list() is vlist
    assert {k: v for k, v in rm.resource_ids().items() if k != "material_uniforms"} == ids
    now = rm.benchmark_counters
    assert now["material_updates"] == counters["material_updates"] + 1
    for name in ("structural_rebuilds", "topology_updates", "vertex_updates", "geometry_uploads"):
        assert now.get(name, 0) == counters.get(name, 0), name
    assert not rm.store._face_dirty  # no face-data re-upload pending
    rm.store.release()
