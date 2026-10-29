"""OBJ UVs and texture (AD-026): the shared loader reads `vt` / `mtllib` / `usemtl` and finds the
texture; `Application.import_obj` brings both into the scene; the export writes `vt` back."""

from __future__ import annotations

import struct
import sys
import zlib

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES_DIR = _REPO_ROOT / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from loaders.obj_loader import ObjLoadError, find_texture, load_obj, parse_mtl_textures, parse_obj  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.obj_export import mesh_to_obj  # noqa: E402
from viewport.resource_store import TraceStore  # noqa: E402

QUAD_OBJ = """mtllib quad.mtl
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
v 2 0 0
v 2 1 0
vt 0 0
vt 0.5 0
vt 0.5 1
vt 0 1
vt 1 0 0
vt 1 1
usemtl Skin
f 1/1 2/2 3/3 4/4
f 2/2/1 5/5/1 6/6/1 3/3/1
"""


def write_png(path, width=2, height=2, rgb=(200, 40, 40)) -> None:
    """A valid, tiny RGB PNG (no imaging library needed)."""
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_parse_texcoords_and_materials():
    data = parse_obj(QUAD_OBJ)
    assert data.has_uvs
    assert data.texcoords[4] == (1.0, 0.0)  # a third (w) component is dropped
    assert data.face_texcoords == ((0, 1, 2, 3), (1, 4, 5, 2))
    assert data.face_uvs()[1] == ((0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0))
    assert data.mtllibs == ("quad.mtl",) and data.materials == ("Skin",)


def test_face_without_complete_uvs_has_none_and_files_without_vt_have_none():
    data = parse_obj("v 0 0 0\nv 1 0 0\nv 0 1 0\nv 1 1 0\nvt 0 0\nf 1/1 2 3\nf 2//1 4//1 3//1\n")
    assert not data.has_uvs and data.face_uvs() == [None, None]
    assert parse_obj("v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nvt 1 0\nvt 0 1\nf 1/-3 2/-2 3/-1\n").face_uvs() == [
        ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))
    ]
    with pytest.raises(ObjLoadError):
        parse_obj("v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nf 1/1 2/2 3/1\n")


def test_mtl_map_kd_with_options_and_spaces():
    text = "newmtl A\nKd 1 1 1\nmap_Kd -s 1 1 1 -o 0 0 0 -bm 1 my skin.png\nnewmtl B\nmap_Kd b.png\n"
    assert parse_mtl_textures(text) == {"A": "my skin.png", "B": "b.png"}


def test_find_texture_via_mtl_foreign_path_and_same_name(tmp_path):
    (tmp_path / "quad.obj").write_text(QUAD_OBJ)
    write_png(tmp_path / "skin_col.png")
    # ZBrush writes the path of the machine it ran on: only the file name is used then
    (tmp_path / "quad.mtl").write_text("newmtl Skin\nmap_Kd C:\\Users\\manu\\Desktop\\skin_col.png\n")
    data = load_obj(tmp_path / "quad.obj")
    assert find_texture(tmp_path / "quad.obj", data) == tmp_path / "skin_col.png"
    (tmp_path / "quad.mtl").unlink()
    assert find_texture(tmp_path / "quad.obj", data) is None
    write_png(tmp_path / "Quad.PNG")
    assert find_texture(tmp_path / "quad.obj", data) == tmp_path / "Quad.PNG"


def _app() -> Application:
    app = Application()
    app.init_scene("cube", store_type=TraceStore)
    return app


def test_import_obj_brings_uvs_and_texture_and_undo_removes_it(tmp_path):
    (tmp_path / "quad.obj").write_text(QUAD_OBJ)
    (tmp_path / "quad.mtl").write_text("newmtl Skin\nmap_Kd skin.png\n")
    write_png(tmp_path / "skin.png")
    app = _app()
    obj = app.import_obj(tmp_path / "quad.obj")
    assert obj.texture == str((tmp_path / "skin.png").resolve())
    mesh = obj.mesh
    assert mesh.has_face_uvs()
    first = mesh.all_face_ids()[0]
    assert mesh.face_uvs(first) == ((0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0))
    assert "texture skin.png" in app.status_message
    app.history.undo()
    assert obj.id not in app.scene.objects
    app.history.redo()
    assert app.scene.objects[obj.id].texture == obj.texture


def test_export_writes_vt_and_reimport_keeps_uvs(tmp_path):
    (tmp_path / "quad.obj").write_text(QUAD_OBJ)
    app = _app()
    obj = app.import_obj(tmp_path / "quad.obj")
    text = mesh_to_obj(obj.mesh, obj.name)
    assert text.count("\nvt ") == 6  # one vt per distinct value: the shared corners stay shared
    data = parse_obj(text)
    assert data.face_uvs() == [obj.mesh.face_uvs(f) for f in obj.mesh.all_face_ids()]


def test_scene_file_keeps_uvs_and_texture(tmp_path):
    from core import scene_from_json, scene_to_json

    (tmp_path / "quad.obj").write_text(QUAD_OBJ)
    write_png(tmp_path / "quad.png")
    app = _app()
    obj = app.import_obj(tmp_path / "quad.obj")
    text = scene_to_json(app.scene)
    loaded = scene_from_json(text)
    (copy,) = [o for o in loaded.objects.values() if o.name == obj.name]
    assert copy.texture == obj.texture
    assert [copy.mesh.face_uvs(f) for f in copy.mesh.all_face_ids()] == [
        obj.mesh.face_uvs(f) for f in obj.mesh.all_face_ids()
    ]
    assert '"version": 6' in text


def test_head_basemesh_loads_its_uvs():
    app = Application()
    app.init_scene("obj", obj_path=_EXAMPLES_DIR / "meshes" / "head_basemesh.obj", store_type=TraceStore)
    mesh = app.scene.mesh
    assert mesh.has_face_uvs()
    assert all(mesh.face_uvs(f) is not None for f in mesh.all_face_ids())
    assert app.scene.edit_object.texture is None  # its MTL names no map_Kd
