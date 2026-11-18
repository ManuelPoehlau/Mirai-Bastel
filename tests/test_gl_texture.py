"""Textures in the real GL path (AD-026): a mesh with face-corner UVs and a material texture is drawn with
the image's colours, a face without UVs keeps the base colour, a UV seam shows, and without a texture the
draw is bit-identical to a mesh that never had UVs.

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_texture.py`); skips without."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from tests.test_obj_uvs import write_png  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.material import Material  # noqa: E402
from viewport.render_mesh import TRIANGLE_UVS, RenderMesh  # noqa: E402

SIZE = 160
RED, GREEN = (230, 20, 20), (20, 230, 20)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


@pytest.fixture(scope="module")
def texture(tmp_path_factory):
    """Left half red, right half green (8 x 2 pixels)."""
    import struct
    import zlib

    path = tmp_path_factory.mktemp("tex") / "halves.png"
    width, height = 8, 2
    row = b"\x00" + bytes(RED) * 4 + bytes(GREEN) * 4
    raw = row * height

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )
    return str(path)


def _plane(uvs: bool) -> Mesh:
    """2x2 planar quads facing +Z over [-1, 1]^2; UVs = the plane mapped onto [0, 1]^2."""
    mesh = Mesh()
    ids = {(i, j): mesh.add_vertex((i - 1.0, j - 1.0, 0.0)) for j in range(3) for i in range(3)}
    for j in range(2):
        for i in range(2):
            corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            mesh.add_face([ids[c] for c in corners], uvs=[(c[0] / 2, c[1] / 2) for c in corners] if uvs else None)
    return mesh


def _draw(gl_window, rm, camera) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, *gl_window.get_framebuffer_size())
    gl.glClearColor(0.0, 0.0, 0.0, 1.0)
    gl_window.clear()
    rm.sync()
    rm.render(camera)
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _pixel(pixels: bytes, x: int, y: int) -> tuple[int, int, int]:
    i = (y * SIZE + x) * 3
    return pixels[i], pixels[i + 1], pixels[i + 2]


def _build(gl_window, mesh, texture_path=None):
    gl_window.switch_to()
    rm = RenderMesh(mesh, store_type=GLRenderStore)
    camera = OrbitCamera(target=(0.0, 0.0, 0.0), distance=3.2, yaw=0.0, pitch=0.0)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=1.0)
    rm.bind_material(Material((0.72, 0.75, 0.82), texture=texture_path))
    rm.mark_material_dirty()
    rm.sync()
    return rm, camera


LEFT, RIGHT = SIZE // 2 - 20, SIZE // 2 + 20
LOW, HIGH = SIZE // 2 - 20, SIZE // 2 + 20


def _reddish(rgb) -> bool:
    return rgb[0] > rgb[1] + 40 and rgb[0] > rgb[2] + 40


def _greenish(rgb) -> bool:
    return rgb[1] > rgb[0] + 40 and rgb[1] > rgb[2] + 40


def test_the_texture_shows_on_its_uvs(gl_window, texture):
    mesh = _plane(uvs=True)
    rm, camera = _build(gl_window, mesh, texture)
    assert rm.store.has(TRIANGLE_UVS)
    pixels = _draw(gl_window, rm, camera)
    assert _reddish(_pixel(pixels, LEFT, LOW)) and _reddish(_pixel(pixels, LEFT, HIGH))
    assert _greenish(_pixel(pixels, RIGHT, LOW)) and _greenish(_pixel(pixels, RIGHT, HIGH))
    rm.store.release()


def test_a_uv_change_and_a_face_without_uvs(gl_window, texture):
    mesh = _plane(uvs=True)
    rm, camera = _build(gl_window, mesh, texture)
    plain_rm, _ = _build(gl_window, _plane(uvs=False))
    plain = _draw(gl_window, plain_rm, camera)
    lower_right = mesh.all_face_ids()[1]
    mesh.set_face_uvs(lower_right, [(0.1, 0.1)] * 4)  # the whole face reads the red half now
    upper_left = mesh.all_face_ids()[2]
    mesh.set_face_uvs(upper_left, None)
    rm.mark_topology_dirty()
    pixels = _draw(gl_window, rm, camera)
    assert _reddish(_pixel(pixels, RIGHT, LOW))
    assert _pixel(pixels, LEFT, HIGH) == _pixel(plain, LEFT, HIGH)  # base colour, as without UVs
    rm.store.release()
    plain_rm.store.release()


def test_without_texture_the_draw_is_the_untextured_one(gl_window, texture):
    rm, camera = _build(gl_window, _plane(uvs=True))
    assert not rm.store.has(TRIANGLE_UVS)
    plain_rm, _ = _build(gl_window, _plane(uvs=False))
    assert _draw(gl_window, rm, camera) == _draw(gl_window, plain_rm, camera)
    # switching the texture on and off again is a material change only
    rm.bind_material(Material((0.72, 0.75, 0.82), texture=texture))
    rm.mark_material_dirty()
    on = _draw(gl_window, rm, camera)
    rm.bind_material(Material((0.72, 0.75, 0.82)))
    rm.mark_material_dirty()
    off = _draw(gl_window, rm, camera)
    assert on != off and off == _draw(gl_window, plain_rm, camera)
    assert not rm.store.has(TRIANGLE_UVS)
    rm.store.release()
    plain_rm.store.release()


def test_an_unreadable_texture_falls_back_to_the_base_colour(gl_window, tmp_path):
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not a png")
    rm, camera = _build(gl_window, _plane(uvs=True), str(bad))
    plain_rm, _ = _build(gl_window, _plane(uvs=False))
    assert _draw(gl_window, rm, camera) == _draw(gl_window, plain_rm, camera)
    rm.store.release()
    plain_rm.store.release()


def test_a_texture_re_exported_under_the_same_name_shows_at_the_next_draw(gl_window, tmp_path):
    import os

    path = tmp_path / "skin.png"
    write_png(path, 4, 4, RED)
    rm, camera = _build(gl_window, _plane(uvs=True), str(path))
    assert _reddish(_pixel(_draw(gl_window, rm, camera), LEFT, LOW))
    write_png(path, 4, 4, GREEN)
    stat = os.stat(path)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))  # a later save, even within one clock tick
    assert _greenish(_pixel(_draw(gl_window, rm, camera), LEFT, LOW))
    rm.store.release()


# -- AD-037 Phase 1c: a live texture ---------------------------------------------------------------------------------


def _live(colour, size=8, mipmaps="deferred"):
    import numpy as np

    from viewport.live_texture import LiveTexture

    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[..., :3] = colour
    rgba[..., 3] = 255
    return LiveTexture(rgba, mipmaps=mipmaps)


@pytest.mark.parametrize("mipmaps", ["frame", "deferred", "none"])
def test_a_live_texture_shows_and_a_marked_box_is_uploaded_alone(gl_window, mipmaps):
    live = _live(RED, mipmaps=mipmaps)
    rm, camera = _build(gl_window, _plane(uvs=True), live)
    pixels = _draw(gl_window, rm, camera)
    assert _reddish(_pixel(pixels, LEFT, LOW)) and _reddish(_pixel(pixels, RIGHT, HIGH))
    assert live.uploads == 1 and live.uploaded_bytes == 8 * 8 * 4
    live.rgba[0:4, 4:8, :3] = GREEN  # rows 0-3 = v < 0.5 (the lower half), columns 4-7 = the right half
    live.mark(4, 0, 8, 4)
    live.finish()
    pixels = _draw(gl_window, rm, camera)
    assert _greenish(_pixel(pixels, RIGHT, LOW)) and _reddish(_pixel(pixels, RIGHT, HIGH))
    assert _reddish(_pixel(pixels, LEFT, LOW))
    assert live.uploads == 2 and live.uploaded_bytes == 8 * 8 * 4 + 4 * 4 * 4
    again = _draw(gl_window, rm, camera)
    assert live.uploads == 2 and again == pixels  # nothing marked: no upload, the same picture
    live.release()
    assert live.gl_name is None
    rm.store.release()


def test_a_live_texture_draws_like_the_same_image_from_a_file(gl_window, tmp_path):
    """The live path and the file path give the same picture for the same pixels (no mipmap difference at this size:
    both are magnified)."""
    import numpy as np

    from mirai.paint.files import encode_layer

    live = _live(RED)
    live.rgba[:, 4:, :3] = GREEN
    path = tmp_path / "same.png"
    path.write_bytes(encode_layer(live.rgba))
    file_rm, camera = _build(gl_window, _plane(uvs=True), str(path))
    live_rm, _ = _build(gl_window, _plane(uvs=True), live)
    from_file = np.frombuffer(_draw(gl_window, file_rm, camera), np.uint8).astype(int)
    from_live = np.frombuffer(_draw(gl_window, live_rm, camera), np.uint8).astype(int)
    assert np.abs(from_file - from_live).max() <= 1
    live.release()
    file_rm.store.release()
    live_rm.store.release()


def test_a_draw_without_a_live_texture_is_unchanged(gl_window, texture):
    """P-E: the path texture and the untextured draw are bit-identical with and without a live texture elsewhere."""
    rm, camera = _build(gl_window, _plane(uvs=True), texture)
    before = _draw(gl_window, rm, camera)
    live = _live(GREEN)
    other, _ = _build(gl_window, _plane(uvs=True), live)
    _draw(gl_window, other, camera)
    assert _draw(gl_window, rm, camera) == before
    live.release()
    other.store.release()
    rm.store.release()
