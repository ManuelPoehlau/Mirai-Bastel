"""O2 face-data layout in the real GL path (AD-018 addendum 2026-11-11): the same image as before, pixel for pixel.

Since O2 the fragment shader reads a face's corner positions and normals from the VertexList's own buffers (through
the corner slots in `face_corners`) instead of from a 36-float copy per face. Oracle: the pre-O2 shader and rows,
frozen in `tests/gl_pre_o2_shading.py`, drawn through the same `GLRenderStore.draw` on the same driver. Every scene must
give byte-identical pixels: Smooth (bilinear quads) and Flat (one normal per polygon), perspective and ortho, quads,
triangles and n-gons, region tints, an object placement, specular, after moves (patched normal rows), after topology
patches (free rows, non-compact slots), with hidden faces, and on a VertexList that does not start at vertex 0 of its
pyglet domain (`u_vertex_base`).

Needs a real GL context (`xvfb-run -a python -m pytest tests/test_gl_face_data_layout.py`); skips without.
"""

from __future__ import annotations

import math

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Mesh  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402
from tests.gl_pre_o2_shading import PreO2Store  # noqa: E402
from viewport.gl_render_store import DEFAULT_BASE_COLOR, GLRenderStore  # noqa: E402
from viewport.light_rig import PRESET_RAITT, PRESETS, resolve  # noqa: E402
from viewport.material import DEFAULT_FINISH, Material  # noqa: E402
from viewport.render_mesh import FACE_CORNERS, FACE_NORMALS, RenderMesh  # noqa: E402

SIZE = 192


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=SIZE, height=SIZE, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


# -- meshes -------------------------------------------------------------------------------------------------------


def _wavy_grid(n: int = 6, amp: float = 0.35) -> Mesh:
    """n x n bent quads over [-1, 1]^2."""
    mesh = Mesh()
    ids = {}
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = -1.0 + 2.0 * i / n, -1.0 + 2.0 * j / n
            ids[i, j] = mesh.add_vertex((x, y, amp * math.sin(2.1 * x + 0.4) * math.cos(1.7 * y - 0.3)))
    for j in range(n):
        for i in range(n):
            mesh.add_face([ids[i, j], ids[i + 1, j], ids[i + 1, j + 1], ids[i, j + 1]])
    return mesh


def _mixed() -> Mesh:
    """Quads, triangles, a pentagon and a hexagon, none of them planar."""
    mesh = Mesh()

    def v(x, y):
        return mesh.add_vertex((x, y, 0.25 * math.sin(3.0 * x) + 0.2 * math.cos(2.0 * y)))

    a, b, c, d, e = v(-1.0, -1.0), v(0.0, -1.0), v(1.0, -1.0), v(-1.0, 0.0), v(0.1, 0.05)
    f, g, h, i = v(1.0, 0.0), v(-1.0, 1.0), v(0.0, 1.0), v(1.0, 1.0)
    mesh.add_face([a, b, e, d])  # quad
    mesh.add_face([b, c, e])  # triangle
    mesh.add_face([c, f, e])  # triangle
    mesh.add_face([d, e, h, g])  # quad
    p1, p2 = v(1.4, 0.4), v(1.3, 1.1)
    mesh.add_face([e, f, p1, p2, i])  # pentagon
    q1, q2, q3 = v(-1.5, -0.4), v(-1.8, 0.3), v(-1.5, 0.9)
    mesh.add_face([a, d, g, q3, q2, q1])  # hexagon (winding as its neighbours)
    return mesh


def _head() -> Mesh:
    from tests.soft_selection_fixtures import HEAD_OBJ  # puts `examples/` (the OBJ loader) on the path

    from loaders.obj_loader import load_obj
    from mirai.scene_factory import mesh_from_positions_and_faces

    data = load_obj(HEAD_OBJ)
    return mesh_from_positions_and_faces(data.vertices, data.faces)


# -- drawing -------------------------------------------------------------------------------------------------------


def _camera(mesh: Mesh, ortho: bool, yaw: float = math.radians(20), pitch: float = math.radians(15)) -> OrbitCamera:
    pts = [mesh.vertex_position(v) for v in mesh.all_vertex_ids()]
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    centre = tuple((lo[k] + hi[k]) / 2 for k in range(3))
    radius = max(math.dist(lo, hi) / 2, 1e-3)
    return OrbitCamera(target=centre, distance=2.4 * radius, yaw=yaw, pitch=pitch, ortho=ortho)


def _pixels(gl_window, rm: RenderMesh, camera) -> bytes:
    from pyglet import gl

    gl_window.switch_to()
    gl.glViewport(0, 0, *gl_window.get_framebuffer_size())
    gl.glClearColor(0.0, 0.0, 0.0, 1.0)
    gl_window.clear()
    rm.render(camera)
    gl.glFinish()
    buf = (gl.GLubyte * (SIZE * SIZE * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, SIZE, SIZE, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _covered(pixels: bytes) -> int:
    return sum(1 for i in range(0, len(pixels), 3) if any(pixels[i:i + 3]))


def _differing(a: bytes, b: bytes) -> int:
    return sum(1 for i in range(0, len(a), 3) if a[i:i + 3] != b[i:i + 3])


def _pair(gl_window, mesh: Mesh):
    """The production `RenderMesh` and the pre-O2 oracle's, on the same mesh."""
    gl_window.switch_to()
    new = RenderMesh(mesh, store_type=GLRenderStore)
    old = RenderMesh(mesh, store_type=PreO2Store)
    old.store.source = old
    return new, old


def _compare(gl_window, mesh: Mesh, *, flat: bool, ortho: bool = False, setup=None, after=None, min_cover=0.15):
    """Draws `mesh` with both paths and returns (new pixels, old pixels). `setup(rm)` configures each RenderMesh
    before its first sync (material, tints, model matrix, hidden); `after(mesh)` edits the mesh after the first draw
    and returns how to mark it ("geometry" + vertex ids, or "topology")."""
    new, old = _pair(gl_window, mesh)
    camera = _camera(mesh, ortho)
    for rm in (new, old):
        rm.bind_camera(camera)
        rm.mark_camera_dirty(aspect=1.0)
        if setup is not None:
            setup(rm)
        rm.sync()
        rm.store.set_draw_style(flat=flat, polygon_offset=False)
        rm.store.set_light_uniforms(resolve(PRESETS[PRESET_RAITT], camera))
    _pixels(gl_window, new, camera)
    _pixels(gl_window, old, camera)
    if after is not None:
        kind, moved = after(mesh)
        for rm in (new, old):
            if kind == "topology":
                rm.mark_topology_dirty()
            else:
                rm.mark_vertices_dirty(moved)
            rm.sync()
    got, want = _pixels(gl_window, new, camera), _pixels(gl_window, old, camera)
    assert _covered(want) > min_cover * SIZE * SIZE
    for rm in (new, old):
        rm.store.release()
        rm._watch.close()
    return got, want


@pytest.mark.parametrize("ortho", [False, True], ids=["persp", "ortho"])
@pytest.mark.parametrize("flat", [False, True], ids=["smooth", "flat"])
def test_bent_quads_look_exactly_as_before(gl_window, flat, ortho):
    got, want = _compare(gl_window, _wavy_grid(), flat=flat, ortho=ortho)
    assert got == want, _differing(got, want)


@pytest.mark.parametrize("flat", [False, True], ids=["smooth", "flat"])
def test_triangles_and_ngons_look_exactly_as_before(gl_window, flat):
    got, want = _compare(gl_window, _mixed(), flat=flat, min_cover=0.1)
    assert got == want, _differing(got, want)


@pytest.mark.parametrize("flat", [False, True], ids=["smooth", "flat"])
def test_a_real_head_with_specular_and_a_placement_looks_exactly_as_before(gl_window, flat):
    def setup(rm):
        rm.bind_material(Material(DEFAULT_BASE_COLOR, DEFAULT_FINISH))
        rm.mark_material_dirty()
        c, s = math.cos(0.6), math.sin(0.6)
        k = 0.8  # rotation about y and a uniform scale (AD-021 Q-4)
        rm.set_model_matrix([k * c, 0.0, -k * s, 0.0, 0.0, k, 0.0, 0.0, k * s, 0.0, k * c, 0.0, 0.1, -0.05, 0.0, 1.0])

    got, want = _compare(gl_window, _head(), flat=flat, setup=setup, min_cover=0.05)
    assert got == want, _differing(got, want)


def test_region_tints_look_exactly_as_before(gl_window):
    def setup(rm):
        faces = rm.mesh.all_face_ids()
        rm.set_face_tints({f: (0.8, 0.4 + 0.01 * (k % 7), 0.3) for k, f in enumerate(faces[::3])})
        rm.store.set_region_tint(True)

    got, want = _compare(gl_window, _wavy_grid(), flat=False, setup=setup)
    assert got == want, _differing(got, want)


@pytest.mark.parametrize("flat", [False, True], ids=["smooth", "flat"])
def test_after_moves_the_patched_rows_look_exactly_as_before(gl_window, flat):
    """A deformation patches only the face normals (O2); the corners come from the patched vertex buffers."""

    def after(mesh):
        moved = set(mesh.all_vertex_ids()[::4])
        for v in moved:
            x, y, z = mesh.vertex_position(v)
            mesh.set_vertex_position(v, (x + 0.03, y, z + 0.2 * math.sin(5.0 * x)))
        return "geometry", moved

    got, want = _compare(gl_window, _head(), flat=flat, after=after, min_cover=0.05)
    assert got == want, _differing(got, want)


@pytest.mark.parametrize("flat", [False, True], ids=["smooth", "flat"])
def test_after_topology_patches_the_layout_looks_exactly_as_before(gl_window, flat, monkeypatch):
    """Patched (non-compact) slots and free rows: the corner slots address the right vertices."""
    import viewport.render_mesh as module

    monkeypatch.setattr(module, "INCREMENTAL_MIN_ELEMENTS", 0)
    monkeypatch.setattr(module, "SPARE_FRACTION", 0.5)

    def after(mesh):
        faces, edges = mesh.all_face_ids(), mesh.all_edge_ids()
        mesh.delete_faces([faces[7], faces[20]])
        mesh.split_edge(edges[30], 0.4)
        mesh.split_edge(edges[3], 0.6)
        v = mesh.all_vertex_ids()[10]
        x, y, z = mesh.vertex_position(v)
        mesh.set_vertex_position(v, (x, y, z + 0.3))
        return "topology", None

    got, want = _compare(gl_window, _wavy_grid(), flat=flat, after=after)
    assert got == want, _differing(got, want)


def test_hidden_faces_look_exactly_as_before(gl_window):
    def setup(rm):
        rm.set_hidden(faces=rm.mesh.all_face_ids()[5:14])

    got, want = _compare(gl_window, _wavy_grid(), flat=False, setup=setup)
    assert got == want, _differing(got, want)


def test_a_vertex_list_behind_another_one_in_the_same_domain(gl_window):
    """Every `GLRenderStore` VertexList of one program lives in one pyglet domain; the second one starts behind the
    first, so the shader must add `u_vertex_base` to a corner slot."""
    gl_window.switch_to()
    filler = RenderMesh(_wavy_grid(3), store_type=GLRenderStore)
    mesh = _wavy_grid()
    new, old = _pair(gl_window, mesh)
    try:
        assert new.store.vertex_list().start > 0
        assert new.store.vertex_list().domain is filler.store.vertex_list().domain
        camera = _camera(mesh, False)
        pixels = []
        for rm in (new, old):
            rm.bind_camera(camera)
            rm.mark_camera_dirty(aspect=1.0)
            rm.sync()
            rm.store.set_light_uniforms(resolve(PRESETS[PRESET_RAITT], camera))
            pixels.append(_pixels(gl_window, rm, camera))
        assert pixels[0] == pixels[1], _differing(*pixels)
        assert _covered(pixels[0]) > 0.15 * SIZE * SIZE
    finally:
        for rm in (filler, new, old):
            rm.store.release()


def test_a_move_uploads_face_normals_only(gl_window):
    """The GL store sees a deformation as positions, normals and the moved faces' normal rows - no corner data."""
    gl_window.switch_to()
    mesh = _head()
    rm = RenderMesh(mesh, store_type=GLRenderStore)
    camera = _camera(mesh, False)
    rm.bind_camera(camera)
    rm.mark_camera_dirty(aspect=1.0)
    rm.sync()
    _pixels(gl_window, rm, camera)
    before = {name: rm.store.resource(name).bytes_uploaded for name in (FACE_NORMALS, FACE_CORNERS)}
    moved = set(mesh.all_vertex_ids()[:30])
    for v in moved:
        x, y, z = mesh.vertex_position(v)
        mesh.set_vertex_position(v, (x, y + 0.02, z))
    rm.mark_vertices_dirty(moved)
    rm.sync()
    assert rm.store.resource(FACE_CORNERS).bytes_uploaded == before[FACE_CORNERS]
    assert rm.store.resource(FACE_NORMALS).bytes_uploaded > before[FACE_NORMALS]
    assert set(rm.store._face_dirty) == {FACE_NORMALS}
    _pixels(gl_window, rm, camera)
    rm.store.release()
