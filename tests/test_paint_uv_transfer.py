"""AD-037 Phase 3: the UV transfer (`mirai.paint.uv_transfer`), on a cube with six faces side by side in UV.

Pinned: texels of faces whose UVs stay are copied bit for bit; a face whose UVs move by whole texels carries its paint
exactly; a face that had no UVs gets transparent texels; the step is a `PaintLayersCommand` over every layer (Undo /
Redo exact); the result is seam-padded where it has paint. The Gollum-head case (ZBrush UV Master) is in
`tests/test_goz_bridge.py::test_a_uv_change_on_a_painted_object_moves_its_paint`.
"""

from __future__ import annotations

import numpy as np

import tests._bootstrap  # noqa: F401

from core import PaintLayer, PaintStack
from mirai.paint import uv_transfer
from mirai.paint.store import PaintStore
from mirai.paint.texel_map import TexelMap

from tests.test_paint_room import _app

SIZE = 96  # six 16-texel-wide faces


def _cube():
    app = _app()
    obj = app.scene.edit_object
    obj.paint = PaintStack(SIZE, SIZE, (PaintLayer("a", None), PaintLayer("b", None, visible=False)))
    rng = np.random.default_rng(11)
    store = PaintStore()
    texel_map = TexelMap(obj.mesh, SIZE, SIZE)
    for name in ("a", "b"):
        rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
        mapped = texel_map.mapped()
        rgba.reshape(-1, 4)[mapped] = rng.integers(1, 256, (mapped.size, 4), dtype=np.uint8)
        store.set_pixels(obj, name, rgba)
    return obj, store, texel_map


def _shifted(mesh, fid, du: float, dv: float):
    return tuple((u + du, v + dv) for u, v in mesh.face_uvs(fid))


def test_unchanged_faces_are_copied_exactly_and_a_moved_face_carries_its_paint():
    obj, store, old_map = _cube()
    mesh = obj.mesh
    faces = mesh.all_face_ids()
    moved = faces[2]
    old = store.pixels(obj, "a").copy()
    # faces 2 and 3 swap their UV squares: both move by exactly 16 texels
    new_uvs = {moved: _shifted(mesh, moved, 1 / 6, 0.0), faces[3]: _shifted(mesh, faces[3], -1 / 6, 0.0)}
    plan = uv_transfer.plan(mesh, new_uvs, SIZE, SIZE)
    out = uv_transfer.transfer(old, plan)
    kept = plan.keep
    assert kept.size and np.array_equal(out.reshape(-1, 4)[kept], old.reshape(-1, 4)[kept])
    width = SIZE // 6
    a = old[:, 2 * width:3 * width]
    b = old[:, 3 * width:4 * width]
    assert np.array_equal(out[:, 3 * width:4 * width], a)  # face 2's paint now in face 3's old square
    assert np.array_equal(out[:, 2 * width:3 * width], b)
    assert plan.move.size == 2 * width * SIZE and plan.faces == 2


def test_a_face_that_had_no_uvs_gets_transparent_texels():
    obj, store, _ = _cube()
    mesh = obj.mesh
    face = mesh.all_face_ids()[0]
    square = mesh.face_uvs(face)
    mesh.set_face_uvs(face, None)  # as if it had none before the change
    plan = uv_transfer.plan(mesh, {face: square}, SIZE, SIZE)
    out = uv_transfer.transfer(store.pixels(obj, "a"), plan)
    assert plan.move.size and not out.reshape(-1, 4)[plan.move].any()


def test_the_command_moves_every_layer_and_undoes_exactly():
    obj, store, _ = _cube()
    mesh = obj.mesh
    faces = mesh.all_face_ids()
    before = {name: store.pixels(obj, name).copy() for name in ("a", "b")}
    new_uvs = {faces[0]: _shifted(mesh, faces[0], 1 / 6, 0.0), faces[1]: _shifted(mesh, faces[1], -1 / 6, 0.0)}
    command = uv_transfer.transfer_command(store, obj, mesh, new_uvs, None, "ZBrush return")
    assert np.array_equal(store.pixels(obj, "a"), before["a"])  # not applied until redo
    command.redo()
    after = {name: store.pixels(obj, name).copy() for name in ("a", "b")}
    for name in ("a", "b"):  # the hidden layer moves as well
        assert not np.array_equal(after[name], before[name])
        assert store.is_dirty(obj, name)
    command.undo()
    for name in ("a", "b"):
        assert np.array_equal(store.pixels(obj, name), before[name])
    command.redo()
    for name in ("a", "b"):
        assert np.array_equal(store.pixels(obj, name), after[name])


def test_a_transfer_into_a_smaller_square_reads_bilinearly_and_pads_the_seam():
    obj, store, _ = _cube()
    mesh = obj.mesh
    face = mesh.all_face_ids()[1]
    rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
    rgba[..., :3], rgba[..., 3] = (200, 40, 10), 255  # one colour everywhere: any read gives it back
    store.set_pixels(obj, "a", rgba)
    small = tuple((u * 0.5 + 0.02, v * 0.5 + 0.25) for u, v in mesh.face_uvs(face))  # half size, off the grid
    plan = uv_transfer.plan(mesh, {face: small}, SIZE, SIZE)
    out = uv_transfer.transfer(rgba, plan)
    assert np.array_equal(out.reshape(-1, 4)[plan.move], np.tile(rgba[0, 0], (plan.move.size, 1)))
    mapped = np.zeros(SIZE * SIZE, bool)
    mapped[plan.map.mapped()] = True
    padded = (out.reshape(-1, 4)[:, 3] > 0) & ~mapped
    assert padded.any()  # the seam padding around the moved island


def test_a_saved_layer_is_not_copied_and_its_undo_reads_the_file(tmp_path):
    """Manu 2026-11-19 („beschleunige die Übernahme“): a layer equal to its file holds no compressed copy in the step -
    Undo reads the file again; the moved pixels go in uncompressed and are frozen only by the first Undo."""
    from mirai.paint import files
    from mirai.paint.store import LayerSnapshot, LivePixels

    obj, _, _ = _cube()
    store = PaintStore(loader=files.read_layer)
    rgba = np.zeros((SIZE, SIZE, 4), np.uint8)
    rgba[:, :SIZE // 2] = (10, 200, 30, 255)
    path = tmp_path / "a.png"
    path.write_bytes(files.encode_layer(rgba))
    obj.paint = PaintStack(SIZE, SIZE, (PaintLayer("a", str(path)),))
    assert np.array_equal(store.pixels(obj, "a"), rgba) and not store.is_dirty(obj, "a")
    mesh = obj.mesh
    faces = mesh.all_face_ids()
    new_uvs = {faces[0]: _shifted(mesh, faces[0], 3 / 6, 0.0), faces[3]: _shifted(mesh, faces[3], -3 / 6, 0.0)}
    command = uv_transfer.transfer_command(store, obj, mesh, new_uvs, None, "ZBrush return")
    assert command.pixels_before == {"a": None} and isinstance(command.pixels_after["a"], LivePixels)
    command.redo()
    moved = store.pixels(obj, "a").copy()
    assert not np.array_equal(moved, rgba) and store.is_dirty(obj, "a")
    command.undo()
    assert isinstance(command.pixels_after["a"], LayerSnapshot)
    assert np.array_equal(store.pixels(obj, "a"), rgba) and not store.is_dirty(obj, "a")  # read from the file
    command.redo()
    assert np.array_equal(store.pixels(obj, "a"), moved)
