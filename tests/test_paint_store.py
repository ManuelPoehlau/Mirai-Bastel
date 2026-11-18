"""AD-037 Phase 1d: the paint pixels (`mirai.paint.store`), one Undo step per stroke, Esc exact, the composite, and the
PNG persistence through the app's save / load (`mirai.paint.files`, `Application.save_scene_file`)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import HistoryStack, Mesh, ObjectId, PaintLayer, PaintStack, Scene, SceneObject
from mirai.paint import files
from mirai.paint.store import TILE, PaintError, PaintStackCommand, PaintStore, tiles_of

W = H = 128


def _obj(layers=("Paint 1",), size=(W, H)) -> SceneObject:
    obj = SceneObject(ObjectId(1), Mesh(), name="head")
    obj.paint = PaintStack(size[0], size[1], tuple(PaintLayer(name, None) for name in layers))
    return obj


def _dab(recorder, x0, y0, w, h, rgba) -> None:
    recorder.write_box(x0, y0, np.broadcast_to(np.asarray(rgba, np.uint8), (h, w, 4)).copy())


# -- store and strokes -----------------------------------------------------------------------------------------------


def test_a_new_layer_is_transparent_and_an_unknown_layer_or_object_is_refused():
    store, obj = PaintStore(), _obj()
    assert store.pixels(obj, "Paint 1").shape == (H, W, 4) and not store.pixels(obj, "Paint 1").any()
    with pytest.raises(PaintError):
        store.pixels(obj, "nope")
    with pytest.raises(PaintError):
        store.pixels(SceneObject(ObjectId(2), Mesh()), "Paint 1")


def test_a_stroke_is_one_undo_step_and_redo_restores_it_exactly():
    store, obj = PaintStore(), _obj()
    history = HistoryStack()
    recorder = store.begin_stroke(obj, "Paint 1")
    _dab(recorder, 10, 10, 30, 20, (255, 0, 0, 255))
    _dab(recorder, 30, 20, 50, 70, (0, 0, 255, 128))  # overlapping the first dab: its tile captured once
    after = store.pixels(obj, "Paint 1").copy()
    command = recorder.commit()
    assert command.before.keys() == set(tiles_of(10, 10, 80, 90))
    history.push(command)
    history.undo()
    assert not store.pixels(obj, "Paint 1").any()
    history.redo()
    assert np.array_equal(store.pixels(obj, "Paint 1"), after)
    history.undo()
    history.redo()
    assert np.array_equal(store.pixels(obj, "Paint 1"), after)
    assert 0 < command.stored_bytes() < 2 * len(command.before) * TILE * TILE * 4


def test_cancel_restores_every_touched_tile_exactly():
    store, obj = PaintStore(), _obj()
    first = store.begin_stroke(obj, "Paint 1")
    _dab(first, 0, 0, W, H, (9, 8, 7, 255))
    first.commit()
    before = store.pixels(obj, "Paint 1").copy()
    stroke = store.begin_stroke(obj, "Paint 1")
    _dab(stroke, 5, 5, 100, 3, (1, 2, 3, 4))
    texels = np.array([0, W * 70 + 3, W * H - 1])
    stroke.write_texels(texels, np.array([[100, 100, 100, 255]] * 3, np.uint8))
    stroke.cancel()
    assert np.array_equal(store.pixels(obj, "Paint 1"), before)
    with pytest.raises(PaintError):
        stroke.commit()


def test_a_stroke_that_touched_nothing_is_no_step():
    store, obj = PaintStore(), _obj()
    assert store.begin_stroke(obj, "Paint 1").commit() is None


def test_changed_tiles_and_dirty_follow_strokes_undo_and_saves():
    store, obj = PaintStore(), _obj()
    assert not store.is_dirty(obj, "Paint 1")
    recorder = store.begin_stroke(obj, "Paint 1")
    _dab(recorder, 70, 0, 4, 4, (1, 1, 1, 255))
    command = recorder.commit()
    assert store.take_changed(obj) == {(1, 0)} and store.take_changed(obj) == set()
    assert store.is_dirty(obj, "Paint 1")
    store.mark_saved(obj, "Paint 1", "/tmp/x.png")
    assert not store.is_dirty(obj, "Paint 1")
    command.undo()
    assert store.is_dirty(obj, "Paint 1") and store.take_changed(obj) == {(1, 0)}


def test_pixels_follow_the_instance_and_copy_object_takes_the_current_ones():
    store, obj = PaintStore(), _obj()
    recorder = store.begin_stroke(obj, "Paint 1")
    _dab(recorder, 0, 0, 8, 8, (50, 60, 70, 255))
    recorder.commit()
    twin = SceneObject(ObjectId(2), Mesh(), name="copy")
    twin.paint = obj.paint
    store.copy_object(obj, twin)
    assert np.array_equal(store.pixels(twin, "Paint 1"), store.pixels(obj, "Paint 1"))
    more = store.begin_stroke(twin, "Paint 1")
    _dab(more, 0, 0, 8, 8, (0, 0, 0, 0))
    more.commit()
    assert store.pixels(obj, "Paint 1")[0, 0, 0] == 50  # independent pixels
    store.clear()
    assert not store.pixels(obj, "Paint 1").any()


def test_a_layer_out_of_the_stack_keeps_its_pixels_for_the_undo_that_brings_it_back():
    store, obj = PaintStore(), _obj(("A", "B"))
    recorder = store.begin_stroke(obj, "B")
    _dab(recorder, 0, 0, 4, 4, (5, 5, 5, 255))
    recorder.commit()
    removed = PaintStackCommand(obj, obj.paint, PaintStack(W, H, (obj.paint.layers[0],)), "Delete layer")
    removed.redo()
    store.pixels(obj, "A")
    removed.undo()
    assert store.pixels(obj, "B")[0, 0, 0] == 5


def test_a_new_stack_size_starts_new_pixels():
    store, obj = PaintStore(), _obj()
    recorder = store.begin_stroke(obj, "Paint 1")
    _dab(recorder, 0, 0, 4, 4, (5, 5, 5, 255))
    recorder.commit()
    obj.paint = PaintStack(64, 64, obj.paint.layers)
    assert store.pixels(obj, "Paint 1").shape == (64, 64, 4) and not store.pixels(obj, "Paint 1").any()


# -- composite -------------------------------------------------------------------------------------------------------


def test_the_composite_blends_visible_layers_normal_with_opacity_over_the_base():
    store = PaintStore()
    obj = _obj(("A", "B"))
    obj.paint = PaintStack(W, H, (PaintLayer("A", None), PaintLayer("B", None, opacity=0.5)))
    a = store.begin_stroke(obj, "A")
    _dab(a, 0, 0, W, H, (255, 0, 0, 255))
    a.commit()
    b = store.begin_stroke(obj, "B")
    _dab(b, 0, 0, W // 2, H, (0, 0, 255, 255))
    b.commit()
    base = np.zeros((H, W, 4), np.uint8)
    base[..., 1] = 200
    out = store.composite(obj, base)
    assert tuple(out[0, 0]) == (128, 0, 128, 255)  # red under half-opaque blue
    assert tuple(out[0, W - 1]) == (255, 0, 0, 255)
    obj.paint = PaintStack(W, H, (PaintLayer("A", None, visible=False), obj.paint.layers[1]))
    assert tuple(store.composite(obj, (0.0, 1.0, 0.0))[0, W - 1]) == (0, 255, 0, 255)  # the base colour shows
    box = store.composite(obj, base, (64, 0, 128, 64))
    assert box.shape == (64, 64, 4) and np.array_equal(box, store.composite(obj, base)[0:64, 64:128])


# -- files and the app's save / load ---------------------------------------------------------------------------------


def test_layer_images_are_written_flipped_once_and_read_back(tmp_path):
    rgba = np.zeros((4, 4, 4), np.uint8)
    rgba[0, 0] = (255, 0, 0, 255)  # row 0 = v = 0: the bottom row of the PNG
    path = tmp_path / "layer.png"
    path.write_bytes(files.encode_layer(rgba))
    from mirai.iris_import import decode_png

    assert tuple(decode_png(path.read_bytes())[3, 0]) == (255, 0, 0, 255)
    assert np.array_equal(files.read_layer(str(path)), rgba)


def test_save_writes_layer_pngs_and_a_flat_image_and_load_brings_the_pixels_back(tmp_path):
    from mirai.application import Application

    app = Application()
    app.init_scene("cube")
    obj = app.scene.edit_object
    obj.paint = PaintStack(32, 32, (PaintLayer("Haut", None), PaintLayer("Leer", None)))
    recorder = app.paint.begin_stroke(obj, "Haut")
    _dab(recorder, 2, 3, 10, 5, (200, 10, 20, 255))
    app.history.push(recorder.commit())
    painted = app.paint.pixels(obj, "Haut").copy()
    scene_path = tmp_path / "kopf.mirai.json"
    assert app.save_scene_file(scene_path)
    folder = tmp_path / "kopf_textures"
    names = sorted(p.name for p in folder.iterdir())
    assert len(names) == 2 and any(n.startswith(f"{obj.name}_Haut_") for n in names)
    assert any("_paint_flat_" in n for n in names)
    raw = json.loads(scene_path.read_text(encoding="utf-8"))
    assert raw["version"] == 14
    stored = next(o["paint"] for o in raw["objects"] if o.get("paint"))
    assert stored["layers"][0]["image"].startswith("kopf_textures/")  # scene-relative
    assert stored["layers"][1]["image"] is None  # transparent: no file
    assert not app.paint.is_dirty(obj, "Haut") and obj.paint.layers[0].image == str(folder / Path(
        stored["layers"][0]["image"]).name)
    status = app.status_message
    assert "paint: 1 layer image written" in status and "flattened" in status

    again = Application()
    again.init_scene("file", scene_path=scene_path)
    loaded = again.scene.edit_object
    assert loaded.paint is not None and Path(loaded.paint.layers[0].image).is_absolute()
    assert np.array_equal(again.paint.pixels(loaded, "Haut"), painted)

    # a second save without changes writes nothing new and keeps the same paths
    before = sorted(p.name for p in folder.iterdir())
    assert again.save_scene_file(scene_path)
    assert sorted(p.name for p in folder.iterdir()) == before
    again_raw = json.loads(scene_path.read_text(encoding="utf-8"))
    assert next(o["paint"] for o in again_raw["objects"] if o.get("paint")) == stored


def test_an_undo_after_a_save_is_written_by_the_next_save(tmp_path):
    from mirai.application import Application

    app = Application()
    app.init_scene("cube")
    obj = app.scene.edit_object
    obj.paint = PaintStack(16, 16, (PaintLayer("Haut", None),))
    recorder = app.paint.begin_stroke(obj, "Haut")
    _dab(recorder, 0, 0, 16, 16, (1, 2, 3, 255))
    app.history.push(recorder.commit())
    path = tmp_path / "s.mirai.json"
    assert app.save_scene_file(path)
    app.history.undo()  # the pixels are transparent again
    assert app.save_scene_file(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["objects"][0]["paint"]["layers"][0]["image"] is None


def test_a_flat_image_composites_the_base_texture(tmp_path):
    obj = _obj(size=(8, 8))
    base = np.zeros((4, 4, 4), np.uint8)
    base[..., 2] = 255
    base[..., 3] = 255
    tex = tmp_path / "base.png"
    tex.write_bytes(files.encode_layer(base))
    obj.texture = str(tex)
    store = PaintStore()
    flat = files.flatten(store, obj)
    assert flat.shape == (8, 8, 4) and tuple(flat[0, 0]) == (0, 0, 255, 255)  # resampled to the stack size
    obj.texture = None
    assert flat.shape == files.flatten(store, obj).shape


def test_copies_keep_the_paint_and_the_current_pixels():
    from mirai.application import Application

    app = Application()
    app.init_scene("cube")
    obj = app.scene.edit_object
    obj.paint = PaintStack(16, 16, (PaintLayer("Haut", None),))
    recorder = app.paint.begin_stroke(obj, "Haut")
    _dab(recorder, 0, 0, 4, 4, (9, 9, 9, 255))
    app.history.push(recorder.commit())
    app._objects._duplicate([obj.id], "Duplicate")
    copies = [o for o in app.scene.objects.values() if o is not obj and o.paint is not None]
    assert len(copies) == 1 and copies[0].paint == obj.paint
    assert np.array_equal(app.paint.pixels(copies[0], "Haut"), app.paint.pixels(obj, "Haut"))


def test_an_unreadable_layer_image_loads_transparent_and_keeps_its_path(tmp_path):
    store = PaintStore(loader=files.read_layer)
    obj = _obj()
    obj.paint = PaintStack(W, H, (PaintLayer("Haut", str(tmp_path / "missing.png")),))
    assert not store.pixels(obj, "Haut").any()
    assert store.missing == {str(tmp_path / "missing.png")}
    assert not store.is_dirty(obj, "Haut") and store.source(obj, "Haut") == str(tmp_path / "missing.png")


def test_a_layer_image_of_the_wrong_size_is_refused(tmp_path):
    path = tmp_path / "small.png"
    path.write_bytes(files.encode_layer(np.zeros((4, 4, 4), np.uint8)))
    store = PaintStore(loader=files.read_layer)
    obj = _obj()
    obj.paint = PaintStack(W, H, (PaintLayer("Haut", str(path)),))
    with pytest.raises(PaintError):
        store.pixels(obj, "Haut")


def _paeth_png(rgba: np.ndarray) -> bytes:
    """A PNG (RGBA, 8 bit) whose every row uses the Paeth filter (what ZBrush-saved textures can carry)."""
    import struct
    import zlib

    h, w, _ = rgba.shape
    bpp, stride = 4, w * 4
    raw = bytearray()
    prev = bytes(stride)
    for y in range(h):
        line = rgba[y].tobytes()
        raw.append(4)
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], prev[i - bpp] if i >= bpp else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
            raw.append((line[i] - pred) & 0xFF)
        prev = line

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw))) + chunk(b"IEND", b""))


def test_a_paeth_png_is_read_right_and_never_through_the_slow_path_first(tmp_path):
    """AD-037 §10.8c (reference PC: Manu's ZBrush texture had Paeth rows, the own decoder took 6.5 s): `read_image`
    asks the system decoder first for such a file; the pixels are the same either way; a second read is cached."""
    from mirai.iris_import import SlowPNG, decode_png

    rgba = np.random.default_rng(4).integers(0, 255, (12, 10, 4), dtype=np.uint8)
    data = _paeth_png(rgba)
    assert np.array_equal(decode_png(data), rgba)
    with pytest.raises(SlowPNG):
        decode_png(data, slow=False)
    path = tmp_path / "paeth.png"
    path.write_bytes(data)
    files.clear_image_cache()
    out = files.read_image(str(path))
    assert np.array_equal(out, rgba) and files.last_read["decoder"].startswith("system")
    assert files.read_image(str(path)) is out and not out.flags.writeable
