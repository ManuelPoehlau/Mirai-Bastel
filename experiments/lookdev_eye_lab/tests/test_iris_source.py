"""The iris texture source (headless): custom `out/iris_custom.png` if usable, else the procedural iris; the custom
file is never written."""

from __future__ import annotations

import os
import struct

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


@pytest.mark.parametrize("content, reason", [
    (b"not a png at all", "signature"),
    (iris_source.PNG_SIGNATURE + b"\x00\x00\x00\x0dIHDX" + b"\x00" * 17, "IHDR"),
    (iris_source.PNG_SIGNATURE + struct.pack(">I", 13) + b"IHDR" + struct.pack(">IIBBBBB", 0, 8, 8, 2, 0, 0, 0)
     + b"\x00" * 4, "zero size"),
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
