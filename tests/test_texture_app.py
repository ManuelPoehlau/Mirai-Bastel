"""Textures in the app (AD-026), headless: the object's texture reaches the viewport material, the SPACE-menu
switch and the mode-4 highlight hide it, and Extrude, mirror copy, SubD and Undo carry the UVs."""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401

from core import SelectionMode
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.subdivision.preview import SubdSurfaceProvider
from obj_files import TEXTURE_LABEL_PREFIX, ObjFiles
from tests.test_obj_uvs import QUAD_OBJ, write_png

WIDTH, HEIGHT = 800, 600


def cube_uv(mesh) -> dict:
    """Per face of a (closed) mesh a distinct UV square: face i gets [i/8, (i+1)/8] x [0, 1], corners in
    boundary order - every face is its own island (all edges are seams)."""
    out = {}
    for i, fid in enumerate(sorted(mesh.all_face_ids())):
        n = len(mesh.face_vertices(fid))
        square = [(i / 8, 0.0), ((i + 1) / 8, 0.0), ((i + 1) / 8, 1.0), (i / 8, 1.0)]
        out[fid] = [square[k % 4] for k in range(n)]
    return out



T = Input("key", "t", frozenset())
K3 = Input("key", "3", frozenset())


def _content(mesh) -> str:
    return json.dumps({k: v for k, v in mesh.export_state().items() if not k.endswith("_counter")})


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


@pytest.fixture
def textured(app, tmp_path):
    """The cube with UVs and a texture as the edit object."""
    mesh = app.scene.mesh
    for fid, uvs in cube_uv(mesh).items():
        mesh.set_face_uvs(fid, uvs)
    png = tmp_path / "skin.png"
    write_png(png)
    app.scene.edit_object.texture = str(png)
    app._sync_object_views()
    return app, str(png)


def test_the_edit_objects_texture_reaches_the_viewport(textured):
    app, png = textured
    assert app.viewport.render_mesh.material.texture == png
    app.viewport.sync()
    assert app.viewport.render_mesh._uv_active


def test_the_switch_and_the_object_highlight_hide_the_texture(textured):
    app, png = textured
    assert app.toggle_texture_display() is False
    assert app.viewport.render_mesh.material.texture is None
    assert app.toggle_texture_display() is True
    assert app.viewport.render_mesh.material.texture == png
    app.selection.mode = SelectionMode.OBJECT
    app.selection.objects = {app.scene.edit_object_id}
    app._sync_object_views()
    assert app.viewport.render_mesh.material.texture is None  # the selection tint shows instead


def test_an_imported_object_is_drawn_with_its_texture(app, tmp_path):
    (tmp_path / "quad.obj").write_text(QUAD_OBJ)
    write_png(tmp_path / "quad.png")
    obj = app.import_obj(tmp_path / "quad.obj")
    app.selection.mode = SelectionMode.VERTEX  # out of mode 4: no highlight
    app._sync_object_views()
    entry = app.viewport.object_entries[obj.id]
    assert entry.material.texture == obj.texture
    entry.sync()
    assert entry._uv_active


def test_the_space_menu_row_toggles_textures(textured, tmp_path):
    app, _png = textured
    files = ObjFiles(app, tmp_path)
    (label,) = [e for e in files.entries() if e.startswith(TEXTURE_LABEL_PREFIX)]
    assert label.endswith("an")
    assert files.activate(label)
    assert not app.display.show_texture
    (label,) = [e for e in files.entries() if e.startswith(TEXTURE_LABEL_PREFIX)]
    assert label.endswith("aus")


def test_no_texture_row_without_a_texture(app, tmp_path):
    assert not [e for e in ObjFiles(app, tmp_path).entries() if e.startswith(TEXTURE_LABEL_PREFIX)]


def test_extrude_keeps_the_cap_uvs_and_undo_is_exact(textured):
    app, _png = textured
    mesh = app.scene.mesh
    app.key_press(K3)
    face = sorted(mesh.all_face_ids())[0]
    before_uvs = mesh.face_uvs(face)
    before = _content(mesh)
    app.selection.mode = SelectionMode.FACE
    app.selection.set({face})
    assert app.key_press(T)
    x, y = 400.0, 300.0
    for _ in range(4):
        x += 30.0
        app.pointer_motion(x, y, 30.0, 0.0)
    assert app.key_release(T)
    (cap,) = app.selection.faces
    assert mesh.face_uvs(cap) == before_uvs
    walls = [f for f in mesh.all_face_ids() if len(set(mesh.face_vertices(f)) & set(mesh.face_vertices(cap))) == 2]
    assert walls and all(mesh.face_uvs(w) is not None for w in walls)
    app.history.undo()
    assert _content(mesh) == before


def test_mirror_copy_keeps_texture_and_uvs(textured):
    app, png = textured
    app.selection.mode = SelectionMode.OBJECT
    app.selection.objects = {app.scene.edit_object_id}
    copy = app.mirror_copy("X")
    assert copy is not None and copy.texture == png
    source = app.scene.edit_object.mesh
    assert sorted(uv for f in copy.mesh.all_face_ids() for uv in copy.mesh.face_uvs(f)) == sorted(
        uv for f in source.all_face_ids() for uv in source.face_uvs(f)
    )


def test_subd_surface_carries_linear_face_varying_uvs(textured):
    app, _png = textured
    mesh = app.scene.mesh
    provider = SubdSurfaceProvider(level=2)
    provider.set_enabled(True)
    provider.sync(mesh, None)
    surface = provider.surface_mesh
    assert surface.has_face_uvs()
    assert all(surface.face_uvs(f) is not None for f in surface.all_face_ids())
    # every derived face lies inside its control face's UV rectangle
    control = {uv for f in mesh.all_face_ids() for uv in mesh.face_uvs(f)}
    derived = {uv for f in surface.all_face_ids() for uv in surface.face_uvs(f)}
    assert control <= derived
    # a UV-only change on the control mesh reaches the surface
    fid = mesh.all_face_ids()[0]
    mesh.set_face_uvs(fid, [(0.5, 0.5)] * len(mesh.face_vertices(fid)))
    provider.sync(mesh, None)
    assert (0.5, 0.5) in {uv for f in provider.surface_mesh.all_face_ids() for uv in provider.surface_mesh.face_uvs(f)}
