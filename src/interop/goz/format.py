"""The GoZ binary format, as far as P1 needs it (AD-029 §2; facts: `experiments/goz_probe/README.md` §2.1, §10a).

Written from the format description of the official GoZ SDK 2022.0 (`GoZ_Binary.h`, PDF II.3); no SDK or GoB code is
copied. Stdlib only, so ZBrush's helper process can use it.

- File: a 32-byte header (`GoZb` + 28 bytes of text), then blocks; each block starts with a 16-byte header
  `uint32 tag, uint32 size (incl. header), uint32 count, float32 modifier`, little-endian.
- The reader **fails closed** (`GozFormatError`): bad magic, a block header or block running past the end of the file,
  a block smaller than its count requires, a face index outside the points, a degenerate face, a non-finite point, a
  missing point or face block, a missing END block or bytes after it, a GROUPS block whose count is not the face
  count. Unknown tags and attribute blocks the bridge does not use (MRGB, MASK16, CREASE, UVs, map paths) are skipped by
  their size.
- GROUPS (tag 40001, P2a): one `uint16` polygroup id per face, no padding (ZBrush 2022.0.8: size 16 + 2 x faces).
- The writer writes MESH, FLAGS (0), POINT_LIST (float32), FACE4_LIST_FORMAT_1 (triangle = 4th index -1), optionally
  GROUPS, END with size field 0 (as the SDK writer stores it). ZBrush 2022.0.8 accepts this minimal file (E1 T5.2,
  `--style sdk`) and keeps the sent group ids per face (E2, 2026-11-05). N-gons are refused: GoZ carries triangles and
  quads only ("not yet supported" in the SDK).
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Optional, Sequence

MAGIC = b"GoZb"
FILE_HEADER_SIZE = 32
HEADER_TEXT = b" 1.0 Mirai GoZ"
BLOCK_HEADER = struct.Struct("<IIIf")

TAG_END_OF_FILE = 0
TAG_MESH = 1
TAG_FLAGS = 5001
TAG_SUBDIV = 5002
TAG_POINT_LIST = 10001
TAG_FACE4_FORMAT_1 = 20001
TAG_FACE4_FORMAT_2 = 20002
TAG_FACE3_LIST = 20003
TAG_GROUPS_LIST = 40001

_ITEM_SIZES = {TAG_FLAGS: 4, TAG_SUBDIV: 16, TAG_POINT_LIST: 12, TAG_FACE4_FORMAT_1: 16, TAG_FACE4_FORMAT_2: 16,
               TAG_FACE3_LIST: 12, TAG_GROUPS_LIST: 2}
_FACE_TAGS = (TAG_FACE4_FORMAT_1, TAG_FACE4_FORMAT_2, TAG_FACE3_LIST)

Point = tuple[float, float, float]
Face = tuple[int, ...]


class GozFormatError(ValueError):
    """Not a complete, well-formed GoZ file (the reader fails closed)."""


@dataclass(frozen=True)
class GozMesh:
    """One SubTool: float32 points (as Python floats) and triangle / quad faces as point indices."""

    name: str
    points: tuple[Point, ...]
    faces: tuple[Face, ...]
    flags: int = 0
    has_subdiv_block: bool = False
    #: one polygroup id per face (GROUPS block), None = the file has none
    groups: Optional[tuple[int, ...]] = None


def _string(payload: bytes) -> str:
    raw = payload.split(b"\0", 1)[0]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _faces(tag: int, count: int, payload: bytes) -> list[Face]:
    if tag == TAG_FACE3_LIST:
        values = struct.unpack_from(f"<{3 * count}i", payload)
        return [tuple(values[3 * i: 3 * i + 3]) for i in range(count)]
    values = struct.unpack_from(f"<{4 * count}i", payload)
    out = []
    for i in range(count):
        a, b, c, d = values[4 * i: 4 * i + 4]
        triangle = d == -1 if tag == TAG_FACE4_FORMAT_1 else d == c  # format 2 repeats the 3rd index
        out.append((a, b, c) if triangle else (a, b, c, d))
    return out


def parse_goz(data: bytes) -> GozMesh:
    if len(data) < FILE_HEADER_SIZE:
        raise GozFormatError(f"{len(data)} bytes, shorter than the 32-byte header")
    if data[:4].lower() != MAGIC.lower():
        raise GozFormatError(f"bad magic {data[:4]!r}")
    name, flags, points, faces, subdiv, groups = "", 0, None, None, False, None
    offset, ended = FILE_HEADER_SIZE, False
    while offset < len(data):
        if offset + BLOCK_HEADER.size > len(data):
            raise GozFormatError(f"truncated block header at offset {offset}")
        tag, size, count, _modifier = BLOCK_HEADER.unpack_from(data, offset)
        if tag == TAG_END_OF_FILE:
            offset += BLOCK_HEADER.size
            ended = True
            break
        if size < BLOCK_HEADER.size or offset + size > len(data):
            raise GozFormatError(f"block {tag} at offset {offset} (size {size}) does not fit the file")
        payload = data[offset + BLOCK_HEADER.size: offset + size]
        if tag in _ITEM_SIZES:
            needed = _ITEM_SIZES[tag] * (1 if tag == TAG_FLAGS else count)
            if len(payload) < needed:
                raise GozFormatError(f"block {tag} at offset {offset}: {len(payload)} bytes, count {count} needs {needed}")
            payload = payload[:needed]
        if tag == TAG_MESH:
            name = _string(payload)
        elif tag == TAG_FLAGS:
            (flags,) = struct.unpack_from("<I", payload)
        elif tag == TAG_SUBDIV:
            subdiv = True
        elif tag == TAG_POINT_LIST:
            if points is not None:
                raise GozFormatError("two point blocks")
            values = struct.unpack_from(f"<{3 * count}f", payload)
            points = [tuple(values[3 * i: 3 * i + 3]) for i in range(count)]
        elif tag in _FACE_TAGS:
            if faces is not None:
                raise GozFormatError("two face blocks")
            faces = _faces(tag, count, payload)
        elif tag == TAG_GROUPS_LIST:
            if groups is not None:
                raise GozFormatError("two groups blocks")
            groups = struct.unpack_from(f"<{count}H", payload)
        offset += size
    if not ended:
        raise GozFormatError("no END_OF_FILE block")
    if offset != len(data):
        raise GozFormatError(f"{len(data) - offset} bytes after the END_OF_FILE block")
    if points is None or faces is None:
        raise GozFormatError("no point block" if points is None else "no face block")
    for i, p in enumerate(points):
        if not all(math.isfinite(c) for c in p):
            raise GozFormatError(f"point {i} is not finite: {p}")
    n = len(points)
    for i, face in enumerate(faces):
        if len(set(face)) != len(face):
            raise GozFormatError(f"face {i} repeats a point: {face}")
        for v in face:
            if not 0 <= v < n:
                raise GozFormatError(f"face {i} index {v} outside the {n} points")
    if groups is not None and len(groups) != len(faces):
        raise GozFormatError(f"groups block holds {len(groups)} ids for {len(faces)} faces")
    return GozMesh(name, tuple(points), tuple(faces), flags, subdiv, groups)


def as_float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def encode_goz(name: str, points: Sequence[Sequence[float]], faces: Sequence[Sequence[int]],
               groups: Optional[Sequence[int]] = None) -> bytes:
    n = len(points)
    if groups is not None and (len(groups) != len(faces) or not all(0 <= int(g) <= 0xFFFF for g in groups)):
        raise ValueError("groups: one 16-bit id per face")
    face_values: list[int] = []
    for i, face in enumerate(faces):
        if len(face) not in (3, 4):
            raise ValueError(f"face {i} has {len(face)} corners: GoZ carries triangles and quads only")
        for v in face:
            if not 0 <= int(v) < n:
                raise ValueError(f"face {i} index {v} outside the {n} points")
        face_values.extend(int(v) for v in face)
        if len(face) == 3:
            face_values.append(-1)
    raw_name = name.encode("utf-8") + b"\0"
    raw_name += b"\0" * (-len(raw_name) % 4)

    def block(tag: int, count: int, payload: bytes) -> bytes:
        return BLOCK_HEADER.pack(tag, BLOCK_HEADER.size + len(payload), count, 0.0) + payload

    return b"".join((
        MAGIC + HEADER_TEXT[:27].ljust(28, b"\0"),
        block(TAG_MESH, 1, raw_name),
        block(TAG_FLAGS, 1, struct.pack("<I", 0)),
        block(TAG_POINT_LIST, n, struct.pack(f"<{3 * n}f", *(float(c) for p in points for c in p))),
        block(TAG_FACE4_FORMAT_1, len(faces), struct.pack(f"<{len(face_values)}i", *face_values)),
        b"" if groups is None else block(TAG_GROUPS_LIST, len(faces), struct.pack(f"<{len(faces)}H", *map(int, groups))),
        BLOCK_HEADER.pack(TAG_END_OF_FILE, 0, 0, 0.0),
    ))
