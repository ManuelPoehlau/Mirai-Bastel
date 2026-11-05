"""Strict reader and minimal writer of the GoZ binary format, as far as E1 needs it (README §2.1, §5).

Written from the format facts of the official GoZ SDK 2022.0 (`GoZ_Binary.h`, PDF II.3); no SDK or GoB code is copied.

- File: a 32-byte header (`GoZb` + 28 bytes of text), then blocks; each block starts with a 16-byte header
  `uint32 tag, uint32 size (incl. header), uint32 count, float32 modifier`, little-endian.
- The reader **fails closed** (`GozFormatError`): bad magic, a block header or block running past the end of the
  file, a block smaller than its count requires, a face index outside the point list, a missing END block, or bytes
  after it. A block *larger* than its count requires is read and recorded as an anomaly (the SDK reader allows it).
  Unknown tags are recorded and skipped by their size.
- END: 16 bytes, tag 0. The SDK writer stores size 0 there, the format text says "16 bytes"; both are accepted.
- The writer writes only what E1 sends: MESH, FLAGS, POINT_LIST (float32), FACE4_LIST_FORMAT_1 (triangle = 4th index
  -1), END. Polygons with more than four corners are refused (n-gons are "not yet supported" in GoZ).
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

MAGIC = b"GoZb"
FILE_HEADER_SIZE = 32
BLOCK_HEADER = struct.Struct("<IIIf")

TAG_END_OF_FILE = 0
TAG_MESH = 1
TAG_MATERIAL = 2
TAG_FLAGS = 5001
TAG_SUBDIV = 5002
TAG_POINT_LIST = 10001
TAG_DPOINT_LIST = 10002
TAG_FACE4_FORMAT_1 = 20001
TAG_FACE4_FORMAT_2 = 20002
TAG_FACE3_LIST = 20003
TAG_UV4_LIST = 25001
TAG_UV3_LIST = 25002
TAG_MASK8_LIST = 30001
TAG_MASK16_LIST = 30002
TAG_MRGB_LIST = 35001
TAG_GROUPS_LIST = 40001
TAG_CREASE_LIST = 40002
TAG_TEXTURE_MAP_PATH = 45001
TAG_NORMAL_MAP_PATH = 50001
TAG_DISPLACEMENT_MAP_PATH = 55001

TAG_NAMES = {
    TAG_END_OF_FILE: "END_OF_FILE",
    TAG_MESH: "MESH",
    TAG_MATERIAL: "MATERIAL",
    TAG_FLAGS: "FLAGS",
    TAG_SUBDIV: "SUBDIV",
    TAG_POINT_LIST: "POINT_LIST",
    TAG_DPOINT_LIST: "DPOINT_LIST",
    TAG_FACE4_FORMAT_1: "FACE4_LIST_FORMAT_1",
    TAG_FACE4_FORMAT_2: "FACE4_LIST_FORMAT_2",
    TAG_FACE3_LIST: "FACE3_LIST",
    TAG_UV4_LIST: "UV4_LIST",
    TAG_UV3_LIST: "UV3_LIST",
    TAG_MASK8_LIST: "MASK8_LIST",
    TAG_MASK16_LIST: "MASK16_LIST",
    TAG_MRGB_LIST: "MRGB_LIST",
    TAG_GROUPS_LIST: "GROUPS_LIST",
    TAG_CREASE_LIST: "CREASE_LIST",
    TAG_TEXTURE_MAP_PATH: "TEXTURE_MAP_PATH",
    TAG_NORMAL_MAP_PATH: "NORMAL_MAP_PATH",
    TAG_DISPLACEMENT_MAP_PATH: "DISPLACEMENT_MAP_PATH",
}

#: Bytes per item of the fixed-size blocks (the format's data sizes per count).
ITEM_SIZES = {
    TAG_FLAGS: 4,  # count is 1
    TAG_SUBDIV: 16,
    TAG_POINT_LIST: 12,
    TAG_DPOINT_LIST: 24,
    TAG_FACE4_FORMAT_1: 16,
    TAG_FACE4_FORMAT_2: 16,
    TAG_FACE3_LIST: 12,
    TAG_UV4_LIST: 32,
    TAG_UV3_LIST: 24,
    TAG_MASK8_LIST: 1,
    TAG_MASK16_LIST: 2,
    TAG_MRGB_LIST: 4,
    TAG_GROUPS_LIST: 2,
    TAG_CREASE_LIST: 1,
}
STRING_TAGS = frozenset(
    {TAG_MESH, TAG_MATERIAL, TAG_TEXTURE_MAP_PATH, TAG_NORMAL_MAP_PATH, TAG_DISPLACEMENT_MAP_PATH}
)
FACE_TAGS = frozenset({TAG_FACE4_FORMAT_1, TAG_FACE4_FORMAT_2, TAG_FACE3_LIST})

FLAG_NAMES = {
    1: "VERTEX_FLIP_X",
    2: "VERTEX_FLIP_Y",
    4: "VERTEX_FLIP_Z",
    8: "VERTEX_SWITCH_YZ",
    256: "POLY_FLIP_NORMALS",
    512: "UV_FLIP_U",
    1024: "UV_FLIP_V",
    2048: "IMAGE_FLIP_V",
}

#: Header text of files the probe writes (the SDK writer: "GoZb" + text, NUL-padded, byte 31 = 0).
PROBE_HEADER_TEXT = b" 1.0 Mirai E1 GoZ probe"

Point = tuple[float, float, float]
Face = tuple[int, ...]


class GozFormatError(ValueError):
    """The file is not a complete, well-formed GoZ file (the reader fails closed)."""


@dataclass(frozen=True)
class Block:
    tag: int
    offset: int
    size: int
    count: int
    modifier: float

    @property
    def name(self) -> str:
        return TAG_NAMES.get(self.tag, f"UNKNOWN_{self.tag}")


@dataclass
class GozFile:
    header_text: bytes
    blocks: list[Block] = field(default_factory=list)
    name: Optional[str] = None
    material: Optional[str] = None
    flags: Optional[int] = None
    subdiv: list[tuple[int, int, int, int]] = field(default_factory=list)
    points: list[Point] = field(default_factory=list)
    face_tag: Optional[int] = None
    faces: list[Face] = field(default_factory=list)
    strings: dict[str, str] = field(default_factory=dict)
    anomalies: list[str] = field(default_factory=list)
    end_size_field: Optional[int] = None

    def flag_names(self) -> list[str]:
        if not self.flags:
            return []
        names = [n for bit, n in FLAG_NAMES.items() if self.flags & bit]
        rest = self.flags & ~sum(FLAG_NAMES)
        return names + ([f"UNKNOWN_BITS_0x{rest:x}"] if rest else [])

    def face_type_counts(self) -> dict[str, int]:
        tris = sum(1 for f in self.faces if len(f) == 3)
        return {"tri": tris, "quad": len(self.faces) - tris}


def _string(payload: bytes) -> str:
    raw = payload.split(b"\0", 1)[0]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _decode_faces(tag: int, count: int, data: bytes) -> list[Face]:
    if tag == TAG_FACE3_LIST:
        values = struct.unpack_from(f"<{3 * count}i", data)
        return [tuple(values[3 * i: 3 * i + 3]) for i in range(count)]
    values = struct.unpack_from(f"<{4 * count}i", data)
    faces = []
    for i in range(count):
        a, b, c, d = values[4 * i: 4 * i + 4]
        if tag == TAG_FACE4_FORMAT_1:
            faces.append((a, b, c) if d == -1 else (a, b, c, d))
        else:  # format 2: a triangle repeats its 3rd index
            faces.append((a, b, c) if d == c else (a, b, c, d))
    return faces


def parse_goz(data: bytes) -> GozFile:
    if len(data) < FILE_HEADER_SIZE:
        raise GozFormatError(f"file has {len(data)} bytes, shorter than the 32-byte header")
    if data[:4].lower() != MAGIC.lower():
        raise GozFormatError(f"bad magic {data[:4]!r} (expected b'GoZb')")
    goz = GozFile(header_text=data[4:FILE_HEADER_SIZE])
    offset = FILE_HEADER_SIZE
    ended = False
    while offset < len(data):
        if offset + BLOCK_HEADER.size > len(data):
            raise GozFormatError(f"truncated block header at offset {offset}")
        tag, size, count, modifier = BLOCK_HEADER.unpack_from(data, offset)
        if tag == TAG_END_OF_FILE:
            goz.blocks.append(Block(tag, offset, size, count, modifier))
            goz.end_size_field = size
            if size not in (0, BLOCK_HEADER.size):
                goz.anomalies.append(f"END block size field {size} (expected 0 or 16)")
            offset += BLOCK_HEADER.size
            ended = True
            break
        if size < BLOCK_HEADER.size:
            raise GozFormatError(f"block {TAG_NAMES.get(tag, tag)} at offset {offset} has size {size} < 16")
        if offset + size > len(data):
            raise GozFormatError(
                f"block {TAG_NAMES.get(tag, tag)} at offset {offset} (size {size}) runs past the end of the file "
                f"({len(data)} bytes)"
            )
        block = Block(tag, offset, size, count, modifier)
        goz.blocks.append(block)
        payload = data[offset + BLOCK_HEADER.size: offset + size]
        if tag in ITEM_SIZES:
            needed = ITEM_SIZES[tag] * (1 if tag == TAG_FLAGS else count)
            if len(payload) < needed:
                raise GozFormatError(
                    f"block {block.name} at offset {offset}: {len(payload)} payload bytes, count {count} needs {needed}"
                )
            if len(payload) > needed:
                goz.anomalies.append(f"block {block.name}: {len(payload) - needed} bytes beyond its count")
            payload = payload[:needed]
        if tag == TAG_MESH:
            goz.name = _string(payload)
        elif tag == TAG_MATERIAL:
            goz.material = _string(payload)
        elif tag in STRING_TAGS:
            goz.strings[block.name] = _string(payload)
        elif tag == TAG_FLAGS:
            (goz.flags,) = struct.unpack_from("<I", payload)
        elif tag == TAG_SUBDIV:
            values = struct.unpack_from(f"<{4 * count}I", payload)
            goz.subdiv = [tuple(values[4 * i: 4 * i + 4]) for i in range(count)]
        elif tag == TAG_POINT_LIST:
            if goz.points:
                goz.anomalies.append("second POINT_LIST block (the later one is used)")
            values = struct.unpack_from(f"<{3 * count}f", payload)
            goz.points = [tuple(values[3 * i: 3 * i + 3]) for i in range(count)]
        elif tag in FACE_TAGS:
            if goz.faces:
                goz.anomalies.append("second face block (the later one is used)")
            goz.face_tag = tag
            goz.faces = _decode_faces(tag, count, payload)
        elif tag not in TAG_NAMES:
            goz.anomalies.append(f"unknown tag {tag} (size {size}, count {count}) skipped")
        offset += size
    if not ended:
        raise GozFormatError("no END_OF_FILE block")
    if offset != len(data):
        raise GozFormatError(f"{len(data) - offset} bytes after the END_OF_FILE block")
    n = len(goz.points)
    for i, face in enumerate(goz.faces):
        if len(set(face)) != len(face):
            goz.anomalies.append(f"face {i} repeats a vertex: {face}")
        for v in face:
            if not 0 <= v < n:
                raise GozFormatError(f"face {i} index {v} outside the {n} points")
    return goz


def read_goz(path: str | os.PathLike) -> GozFile:
    return parse_goz(Path(path).read_bytes())


def _block(tag: int, count: int, payload: bytes, modifier: float = 0.0) -> bytes:
    return BLOCK_HEADER.pack(tag, BLOCK_HEADER.size + len(payload), count, modifier) + payload


def _string_payload(text: str) -> bytes:
    raw = text.encode("utf-8") + b"\0"
    return raw + b"\0" * (-len(raw) % 4)


#: The 32-byte header ZBrush 2022.0.8 writes (observed in the E1 captures, 2026-11-05).
ZBRUSH_HEADER = b"GoZb 1.0 ZBrush GoZ Binary......"
#: What ZBrush 2022.0.8 writes for an untouched mesh (observed): white polypaint with material byte 1, nothing masked,
#: polygroup 0, no creases.
ZBRUSH_DEFAULT_MRGB = b"\xff\xff\xff\x01"
ZBRUSH_DEFAULT_MASK16 = b"\xff\xff"

#: Writer styles (README §6 T5): "sdk" = the SDK's minimal file; "gozmesh" = the same with the name prefixed
#: `GoZMesh_` as ZBrush writes it; "zbrush" = byte layout of ZBrush's own files: its header text, the prefix, and the
#: MRGB / MASK16 / GROUPS / CREASE blocks with ZBrush's default values, in ZBrush's order.
STYLES = ("sdk", "gozmesh", "zbrush")


def encode_goz(
    name: str,
    points: Sequence[Sequence[float]],
    faces: Sequence[Sequence[int]],
    *,
    flags: int = 0,
    style: str = "sdk",
    header_text: bytes = PROBE_HEADER_TEXT,
) -> bytes:
    """MESH, FLAGS, POINT_LIST (float32), FACE4_LIST_FORMAT_1, (ZBrush's default attribute blocks), END.
    `name` is used as given for "sdk"; "gozmesh" and "zbrush" add the `GoZMesh_` prefix unless it is there."""
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}")
    n = len(points)
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
    if style != "sdk" and not name.startswith("GoZMesh_"):
        name = "GoZMesh_" + name
    if style == "zbrush":
        head = ZBRUSH_HEADER
    else:
        head = MAGIC + header_text[:27].ljust(28, b"\0")
        head = head[:31] + b"\0"
    point_payload = struct.pack(f"<{3 * n}f", *(float(c) for p in points for c in p))
    parts = [
        head,
        _block(TAG_MESH, 1, _string_payload(name)),
        _block(TAG_FLAGS, 1, struct.pack("<I", flags)),
        _block(TAG_POINT_LIST, n, point_payload),
        _block(TAG_FACE4_FORMAT_1, len(faces), struct.pack(f"<{len(face_values)}i", *face_values)),
    ]
    if style == "zbrush":
        parts += [
            _block(TAG_MRGB_LIST, n, ZBRUSH_DEFAULT_MRGB * n),
            _block(TAG_MASK16_LIST, n, ZBRUSH_DEFAULT_MASK16 * n),
            _block(TAG_GROUPS_LIST, len(faces), b"\0\0" * len(faces)),
            _block(TAG_CREASE_LIST, len(faces), b"\0" * len(faces)),
        ]
    parts.append(BLOCK_HEADER.pack(TAG_END_OF_FILE, 0, 0, 0.0))
    return b"".join(parts)


def as_float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def dump(goz: GozFile, *, head: int = 5) -> str:
    lines = [f"header text: {goz.header_text!r}", "blocks:"]
    for b in goz.blocks:
        lines.append(f"  @{b.offset:>8}  tag {b.tag:>6} {b.name:<22} size {b.size:>9}  count {b.count:>7}  modifier {b.modifier!r}")
    lines.append(f"mesh name: {goz.name!r}")
    if goz.material is not None:
        lines.append(f"material: {goz.material!r}")
    lines.append(f"flags: {goz.flags!r} {goz.flag_names()}")
    if goz.subdiv:
        lines.append("subdiv (levels, current level, dynamic sharp, dynamic smooth): " + ", ".join(map(str, goz.subdiv)))
    for key, value in goz.strings.items():
        lines.append(f"{key}: {value!r}")
    lines.append(
        f"points: {len(goz.points)}  faces: {len(goz.faces)} ({TAG_NAMES.get(goz.face_tag, goz.face_tag)}) "
        f"{goz.face_type_counts()}"
    )
    if goz.points:
        lo = [min(p[i] for p in goz.points) for i in range(3)]
        hi = [max(p[i] for p in goz.points) for i in range(3)]
        lines.append(f"bbox min {tuple(lo)} max {tuple(hi)} extent {tuple(h - l for l, h in zip(lo, hi))}")
        lines.append(f"first points: {goz.points[:head]}")
        lines.append(f"last points: {goz.points[-head:]}")
    if goz.faces:
        lines.append(f"first faces: {goz.faces[:head]}")
        lines.append(f"last faces: {goz.faces[-head:]}")
    lines.append("anomalies: " + ("; ".join(goz.anomalies) if goz.anomalies else "none"))
    return "\n".join(lines) + "\n"
