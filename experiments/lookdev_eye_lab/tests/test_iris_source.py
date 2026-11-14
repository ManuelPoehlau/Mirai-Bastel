"""The iris texture source (headless): custom `out/iris_custom.png` if usable, else the procedural iris; the custom
file is never written."""

from __future__ import annotations

import os
import struct
import zlib

import pytest

from lookdev_gpu_probe import cube_math as cm
from lookdev_eye_lab import eye_geometry as geo
from lookdev_eye_lab import iris_source


def _snapshot(path):
    st = path.stat()
    return path.read_bytes(), st.st_mtime_ns, st.st_size


def _write_custom(out_dir, width=64, height=64):
    import numpy as np

    path = out_dir / iris_source.CUSTOM_NAME
    cm.write_png(path, np.full((height, width, 3), (0.9, 0.1, 0.1)))
    return path


def test_without_a_custom_file_the_procedural_iris_is_used(tmp_path):
    source = iris_source.choose(tmp_path)
    assert not source.custom and source.path == tmp_path / iris_source.PROCEDURAL_NAME and source.path.exists()
    assert not (tmp_path / iris_source.CUSTOM_NAME).exists()  # nothing is created under the custom name


def test_a_custom_png_is_used_and_left_untouched(tmp_path):
    custom = _write_custom(tmp_path, 48, 32)
    os.utime(custom, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
    before = _snapshot(custom)
    source = iris_source.choose(tmp_path)
    assert source.custom and source.path == custom
    assert "48x32" in source.note and "not square" in source.note and "sha1" in source.note
    assert _snapshot(custom) == before  # bytes, mtime and size unchanged
    assert "CUSTOM" in source.describe()


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _png(width=8, height=8, colour=2, idat=None, ihdr_kind=b"IHDR", crc_ok=True, iend=True) -> bytes:
    ihdr = _chunk(ihdr_kind, struct.pack(">IIBBBBB", width, height, 8, colour, 0, 0, 0))
    if idat is None:
        idat = zlib.compress(b"".join(b"\x00" + b"\x80" * (3 * width) for _ in range(height)))
    body = _chunk(b"IDAT", idat)
    if not crc_ok:
        body = body[:-1] + bytes([body[-1] ^ 0xFF])
    return iris_source.PNG_SIGNATURE + ihdr + body + (_chunk(b"IEND", b"") if iend else b"")


@pytest.mark.parametrize("content, reason", [
    (b"not a png at all", "signature"),
    (_png(ihdr_kind=b"IHDX"), "IHDR"),
    (_png(width=0), "zero size"),
    (_png(crc_ok=False), "CRC"),
    (_png(iend=False), "IEND"),
    (_png(idat=b"garbage"), "does not decompress"),  # the reference PC's Windows decoder accepted this one
    (_png(idat=zlib.compress(b"\x00" * 10)), "expected"),  # too little image data
    (_png(colour=3), "PLTE"),
    (_png()[:60], "truncated"),
])
def test_an_unusable_custom_file_falls_back_and_is_left_untouched(tmp_path, content, reason):
    custom = tmp_path / iris_source.CUSTOM_NAME
    custom.write_bytes(content)
    before = _snapshot(custom)
    source = iris_source.choose(tmp_path)
    assert not source.custom and reason in source.note
    assert _snapshot(custom) == before


def test_the_procedural_writer_refuses_the_custom_name(tmp_path):
    with pytest.raises(ValueError):
        geo.write_iris_png(tmp_path / iris_source.CUSTOM_NAME)


def test_mapping_shares_match_the_geometry():
    assert iris_source.PUPIL_SHARE == pytest.approx(0.268, abs=0.001)
    assert iris_source.LIMBUS_SHARE == pytest.approx(0.82, abs=0.005)


def test_inspect_reports_png_details(tmp_path):
    path = _write_custom(tmp_path, 16, 16)
    ok, text = iris_source.inspect(path)
    assert ok and text == "16x16, 8-bit RGB"


def test_inspect_accepts_interlaced_and_palette_pngs(tmp_path):
    path = tmp_path / "x.png"
    # Adam7, 5x3 RGB 8-bit: passes contribute 1+3, 1+3, 1+3, 1+3+1+3, ... bytes - computed by the same rule as pyglet.
    rows = []
    for x0, y0, dx, dy in iris_source._ADAM7:
        w = (5 - x0 + dx - 1) // dx if 5 > x0 else 0
        h = (3 - y0 + dy - 1) // dy if 3 > y0 else 0
        rows += [b"\x00" + b"\x10" * (3 * w)] * (h if w else 0)
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 5, 3, 8, 2, 0, 0, 1))
    path.write_bytes(iris_source.PNG_SIGNATURE + ihdr + _chunk(b"IDAT", zlib.compress(b"".join(rows)))
                     + _chunk(b"IEND", b""))
    ok, text = iris_source.inspect(path)
    assert ok and "interlaced" in text
    pal = (iris_source.PNG_SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 3, 0, 0, 0))
           + _chunk(b"PLTE", b"\x00\x00\x00\xff\xff\xff")
           + _chunk(b"IDAT", zlib.compress(b"".join(b"\x00" + b"\x01" * 4 for _ in range(4)))) + _chunk(b"IEND", b""))
    path.write_bytes(pal)
    assert iris_source.inspect(path) == (True, "4x4, 8-bit palette")
