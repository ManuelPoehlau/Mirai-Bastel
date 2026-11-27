"""The EXIF reader and the orientation (AD-042 §18.4, proposal §9 M2): synthetic JPEG headers written by the test (no
third-party photos in the repository), both byte orders, broken files, the eight orientations, the app wiring, the
suggestion and „Übernehmen“."""

from __future__ import annotations

import io
import struct

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from mirai import exif as E
from mirai.application import Application
from mirai.iris_import import encode_png


def _tiff(order: str, orientation: int | None = 6, focal: tuple[int, int] | None = (425, 100),
          focal35: int | None = 26) -> bytes:
    """A TIFF block: IFD0 (Orientation, ExifIFD pointer), the Exif IFD (FocalLength, FocalLengthIn35mmFilm)."""
    o = "<" if order == "II" else ">"
    entries0 = []
    if orientation is not None:
        entries0.append(struct.pack(o + "HHIHH", E.ORIENTATION, 3, 1, orientation, 0))
    exif_entries = []
    if focal is not None:
        exif_entries.append(("focal", focal))
    if focal35 is not None:
        exif_entries.append(("f35", focal35))
    n0 = len(entries0) + 1
    ifd0_size = 2 + 12 * n0 + 4
    exif_at = 8 + ifd0_size
    entries0.append(struct.pack(o + "HHII", E.EXIF_IFD, 4, 1, exif_at))
    exif_size = 2 + 12 * len(exif_entries) + 4
    data_at = exif_at + exif_size
    body, tail = [], b""
    for kind, value in exif_entries:
        if kind == "focal":
            body.append(struct.pack(o + "HHII", E.FOCAL_LENGTH, 5, 1, data_at + len(tail)))
            tail += struct.pack(o + "II", *value)
        else:
            body.append(struct.pack(o + "HHIHH", E.FOCAL_35MM, 3, 1, value, 0))
    head = order.encode() + struct.pack(o + "HI", 42, 8)
    ifd0 = struct.pack(o + "H", n0) + b"".join(entries0) + struct.pack(o + "I", 0)
    ifd1 = struct.pack(o + "H", len(body)) + b"".join(body) + struct.pack(o + "I", 0)
    return head + ifd0 + ifd1 + tail


def _jpeg(tiff: bytes, app0: bool = True) -> bytes:
    out = b"\xff\xd8"
    if app0:
        jfif = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        out += b"\xff\xe0" + struct.pack(">H", len(jfif) + 2) + jfif
    payload = b"Exif\x00\x00" + tiff
    out += b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    return out + b"\xff\xda\x00\x02" + b"\x00" * 16 + b"\xff\xd9"


@pytest.mark.parametrize("order", ["II", "MM"])
def test_orientation_and_focal_lengths_in_both_byte_orders(order):
    info = E.parse_jpeg(_jpeg(_tiff(order)))
    assert info == E.ExifInfo(orientation=6, focal_mm=4.25, focal_35mm=26.0) and info.swaps_sides
    assert E.parse_jpeg(_jpeg(_tiff(order), app0=False)) == info


def test_missing_and_unknown_values():
    assert E.parse_jpeg(_jpeg(_tiff("II", orientation=None, focal=None, focal35=None))) == E.ExifInfo()
    assert E.parse_jpeg(_jpeg(_tiff("II", focal35=0))).focal_35mm is None  # 0 = unknown (EXIF)
    assert E.parse_jpeg(_jpeg(_tiff("II", orientation=9))).orientation == 1
    assert E.parse_jpeg(_jpeg(_tiff("MM", focal=(5, 0)))).focal_mm is None  # a zero denominator


@pytest.mark.parametrize("data", [
    b"", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40, b"\xff\xd8", b"\xff\xd8\xff\xe1\x00",
    b"\xff\xd8\xff\xe1\x00\x10Exif\x00\x00II*\x00\xff\xff\xff\x7f",  # IFD0 offset beyond the block
    b"\xff\xd8\xff\xda\x00\x02\xff\xd9",  # pixels before any EXIF
])
def test_broken_or_foreign_files_give_the_defaults(data):
    assert E.parse_jpeg(data) == E.ExifInfo()


def test_a_truncated_exif_block_gives_the_defaults():
    full = _jpeg(_tiff("II"))
    for cut in range(4, len(full), 7):
        info = E.parse_jpeg(full[:cut])
        assert isinstance(info, E.ExifInfo)  # never raises


def test_read_exif_of_a_missing_file(tmp_path):
    assert E.read_exif(tmp_path / "gone.jpg") == E.ExifInfo()


def _marked(h: int = 3, w: int = 5) -> np.ndarray:
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 0] = np.arange(w)[None, :] * 40
    rgba[..., 1] = np.arange(h)[:, None] * 60
    rgba[..., 3] = 255
    return rgba


def test_the_eight_orientations_against_pil():
    Image = pytest.importorskip("PIL.Image")
    ImageOps = pytest.importorskip("PIL.ImageOps")
    stored = _marked()
    for orientation in range(1, 9):
        img = Image.fromarray(stored, "RGBA")
        exif = img.getexif()
        exif[E.ORIENTATION] = orientation
        img.info["exif"] = exif.tobytes()
        want = np.asarray(ImageOps.exif_transpose(img))
        got = E.apply_orientation(stored, orientation)
        assert np.array_equal(got, want), orientation
        assert got.flags.c_contiguous


# -- the app ---------------------------------------------------------------------------------------------------------

@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(800, 600)
    return app


def _load(app, path) -> None:
    assert app.load_likeness_photo(0, path)
    for _ in range(3):
        app.update_viewport(0.0)


def test_the_app_orients_the_photo_and_suggests_the_focal_length(app, tmp_path, monkeypatch):
    stored = _marked(20, 30)
    path = tmp_path / "phone.png"
    path.write_bytes(encode_png(stored))
    monkeypatch.setattr(E, "read_exif", lambda _p: E.ExifInfo(orientation=6, focal_mm=4.25, focal_35mm=26.0))
    assert app.new_likeness_camera()
    _load(app, path)
    cam = app.likeness.cameras[0]
    assert np.array_equal(cam.photo.rgba, np.rot90(stored, k=-1)) and cam.photo.size == (20, 30)
    assert cam.photo.oriented and "nach EXIF ausgerichtet" in app.status_message and "26 mm KB" in app.status_message
    assert app.likeness_exif_suggestion(0) == (26.0, True)
    assert app.set_likeness_lens(0, sensor="aps_c", focal_mm=70.0)
    assert app.adopt_likeness_exif(0)
    lens = cam.lens
    assert (lens.focal_mm, lens.sensor, lens.fit) == (26.0, "equiv35", "diagonal")
    assert not app.adopt_likeness_exif(0)  # already the lens


def test_a_real_focal_length_sets_only_the_focal_length(app, tmp_path, monkeypatch):
    path = tmp_path / "dslr.png"
    path.write_bytes(encode_png(_marked(20, 30)))
    monkeypatch.setattr(E, "read_exif", lambda _p: E.ExifInfo(focal_mm=85.0))
    assert app.new_likeness_camera() and app.set_likeness_lens(0, sensor="full_frame")
    _load(app, path)
    assert app.likeness_exif_suggestion(0) == (85.0, False) and app.adopt_likeness_exif(0)
    assert app.likeness.cameras[0].lens.sensor == "full_frame" and "Sensor prüfen" in app.status_message


def test_no_suggestion_without_exif(app, tmp_path):
    path = tmp_path / "plain.png"
    path.write_bytes(encode_png(_marked(20, 30)))
    assert app.new_likeness_camera()
    _load(app, path)
    assert app.likeness_exif_suggestion(0) is None and not app.adopt_likeness_exif(0)
    assert "nennt keine Brennweite" in app.status_message


def test_a_real_jpeg_with_an_orientation(app, tmp_path):
    """The whole path with a real decoder (pyglet's, here PIL; on Windows WIC): the file's pixels come out as held."""
    Image = pytest.importorskip("PIL.Image")
    pytest.importorskip("pyglet")
    stored = np.zeros((32, 48, 3), np.uint8)
    stored[:, :24] = (250, 10, 10)  # left half red, right half blue - survives JPEG
    stored[:, 24:] = (10, 10, 250)
    img = Image.fromarray(stored, "RGB")
    exif = img.getexif()
    exif[E.ORIENTATION] = 6
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes(), quality=95)
    path = tmp_path / "phone.jpg"
    path.write_bytes(buf.getvalue())
    assert E.read_exif(path).orientation == 6
    assert app.new_likeness_camera()
    try:
        _load(app, path)
    except Exception as exc:  # pragma: no cover - no decoder / display
        pytest.skip(f"no image decoder: {exc}")
    photo = app.likeness.cameras[0].photo
    if photo is None:
        pytest.skip(f"no image decoder: {app.status_message}")
    assert photo.size == (32, 48)  # turned: portrait
    top, bottom = photo.rgba[4, 16, :3].astype(int), photo.rgba[-4, 16, :3].astype(int)
    assert top[0] > 200 and bottom[2] > 200  # the stored left (red) is the top after a clockwise turn
