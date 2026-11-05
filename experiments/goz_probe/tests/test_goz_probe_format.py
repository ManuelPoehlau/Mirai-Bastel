"""The strict GoZ reader and the minimal writer (README §2.1): round trip and fail-closed cases."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from goz_probe import goz_probe_format as fmt

QUAD_AND_TRI = ([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (0.5, 0.5, 1.0)],
                [(0, 1, 2, 3), (0, 1, 4)])


def _encoded(name="E1_T"):
    return fmt.encode_goz(name, *QUAD_AND_TRI)


def test_round_trip_and_layout():
    data = _encoded()
    assert data[:4] == b"GoZb" and data[31:32] == b"\0"
    goz = fmt.parse_goz(data)
    assert goz.name == "E1_T" and goz.flags == 0 and goz.anomalies == []
    assert goz.points == [tuple(p) for p in QUAD_AND_TRI[0]]
    assert goz.faces == [(0, 1, 2, 3), (0, 1, 4)]
    assert [b.tag for b in goz.blocks] == [fmt.TAG_MESH, fmt.TAG_FLAGS, fmt.TAG_POINT_LIST, fmt.TAG_FACE4_FORMAT_1, 0]
    assert goz.end_size_field == 0  # as the SDK writer stores it
    # the triangle's 4th index is -1 (FACE4 format 1)
    face_block = goz.blocks[3]
    assert struct.unpack_from("<8i", data, face_block.offset + 16)[4:] == (0, 1, 4, -1)
    # name: string + NUL, padded to 4 bytes; points and faces start on 4-byte boundaries
    assert goz.blocks[0].size == 16 + 8
    assert all(b.offset % 4 == 0 for b in goz.blocks)


def test_end_block_of_size_16_is_accepted():
    data = _encoded()
    data = data[:-16] + struct.pack("<IIIf", 0, 16, 0, 0.0)
    assert fmt.parse_goz(data).end_size_field == 16


def test_points_are_float32():
    goz = fmt.parse_goz(fmt.encode_goz("x", [(0.1, 0.2, 0.3), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)]))
    assert goz.points[0] == tuple(fmt.as_float32(v) for v in (0.1, 0.2, 0.3))


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda d: d[:-10], "truncated block header"),
        (lambda d: b"GoZx" + d[4:], "bad magic"),
        (lambda d: d + b"\0\0\0\0", "after the END_OF_FILE"),
        (lambda d: d[:-16], "no END_OF_FILE"),
        (lambda d: d[:20], "shorter than the 32-byte header"),
    ],
)
def test_fails_closed(mutate, message):
    with pytest.raises(fmt.GozFormatError, match=message):
        fmt.parse_goz(mutate(_encoded()))


def _patch_header(data: bytes, block_index: int, *, size=None, count=None) -> bytes:
    goz = fmt.parse_goz(data)
    b = goz.blocks[block_index]
    tag, old_size, old_count, mod = struct.unpack_from("<IIIf", data, b.offset)
    head = struct.pack("<IIIf", tag, old_size if size is None else size, old_count if count is None else count, mod)
    return data[: b.offset] + head + data[b.offset + 16:]


def test_count_larger_than_payload_fails():
    with pytest.raises(fmt.GozFormatError, match="needs"):
        fmt.parse_goz(_patch_header(_encoded(), 2, count=6))


def test_block_past_end_fails():
    with pytest.raises(fmt.GozFormatError, match="runs past the end"):
        fmt.parse_goz(_patch_header(_encoded(), 2, size=10_000))


def test_face_index_outside_points_fails():
    data = fmt.encode_goz("x", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    goz = fmt.parse_goz(data)
    off = goz.blocks[3].offset + 16
    bad = data[:off] + struct.pack("<i", 7) + data[off + 4:]
    with pytest.raises(fmt.GozFormatError, match="outside the 3 points"):
        fmt.parse_goz(bad)


def test_unknown_block_is_recorded_and_skipped_and_padding_is_an_anomaly():
    data = _encoded()
    end = len(data) - 16
    unknown = struct.pack("<IIIf", 75001, 24, 2, 0.0) + b"\x01" * 8
    goz = fmt.parse_goz(data[:end] + unknown + data[end:])
    assert any("unknown tag 75001" in a for a in goz.anomalies)
    assert goz.faces == [(0, 1, 2, 3), (0, 1, 4)]
    flags = fmt.parse_goz(_patch_header(_encoded(), 1, size=24)[:56 + 20] + b"\0" * 4 + _encoded()[56 + 20:])
    assert any("beyond its count" in a for a in flags.anomalies)


def test_other_face_formats_and_subdiv_decode():
    pts = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    body = (
        struct.pack("<IIIf", fmt.TAG_SUBDIV, 32, 1, 0.0) + struct.pack("<4I", 2, 1, 0, 0)
        + struct.pack("<IIIf", fmt.TAG_POINT_LIST, 16 + 36, 3, 0.0) + pts
        + struct.pack("<IIIf", fmt.TAG_FACE4_FORMAT_2, 32, 1, 0.0) + struct.pack("<4i", 0, 1, 2, 2)
        + struct.pack("<IIIf", 0, 0, 0, 0.0)
    )
    goz = fmt.parse_goz(b"GoZb" + b"\0" * 28 + body)
    assert goz.subdiv == [(2, 1, 0, 0)] and goz.faces == [(0, 1, 2)]
    body3 = (
        struct.pack("<IIIf", fmt.TAG_POINT_LIST, 16 + 36, 3, 0.0) + pts
        + struct.pack("<IIIf", fmt.TAG_FACE3_LIST, 28, 1, 0.0) + struct.pack("<3i", 2, 1, 0)
        + struct.pack("<IIIf", 0, 0, 0, 0.0)
    )
    assert fmt.parse_goz(b"GoZb" + b"\0" * 28 + body3).faces == [(2, 1, 0)]


def test_writer_refuses_ngons_and_bad_indices():
    with pytest.raises(ValueError, match="triangles and quads only"):
        fmt.encode_goz("x", [(0, 0, 0)] * 5, [(0, 1, 2, 3, 4)])
    with pytest.raises(ValueError, match="outside"):
        fmt.encode_goz("x", [(0, 0, 0)] * 3, [(0, 1, 3)])


def test_flag_names_and_dump():
    goz = fmt.parse_goz(fmt.encode_goz("x", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], flags=2 | 4 | 1024))
    assert goz.flag_names() == ["VERTEX_FLIP_Y", "VERTEX_FLIP_Z", "UV_FLIP_V"]
    text = fmt.dump(goz)
    assert "FACE4_LIST_FORMAT_1" in text and "anomalies: none" in text


FIXTURE = Path(__file__).parent / "fixtures" / "zbrush2022_0_8_obj_import_A.GoZ"


def test_zbrush_style_reproduces_a_zbrush_file_byte_for_byte():
    """The fixture is ZBrush 2022.0.8's own GoZ of mesh A (E1 T2, reference PC, 2026-11-05)."""
    data = FIXTURE.read_bytes()
    goz = fmt.parse_goz(data)
    assert goz.name == "GoZMesh_A" and goz.header_text == fmt.ZBRUSH_HEADER[4:]
    assert [b.tag for b in goz.blocks] == [1, 5001, 10001, 20001, 35001, 30002, 40001, 40002, 0]
    assert fmt.encode_goz("A", goz.points, goz.faces, style="zbrush") == data
    assert fmt.encode_goz("GoZMesh_A", goz.points, goz.faces, style="zbrush") == data  # prefix not doubled
    assert fmt.parse_goz(fmt.encode_goz("A", goz.points, goz.faces, style="gozmesh")).name == "GoZMesh_A"
    assert fmt.parse_goz(fmt.encode_goz("A", goz.points, goz.faces)).name == "A"
    with pytest.raises(ValueError, match="unknown style"):
        fmt.encode_goz("A", goz.points, goz.faces, style="x")
