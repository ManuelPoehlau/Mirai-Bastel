"""A small EXIF reader for JPEG photos (AD-042 §18, M2; proposal §4.2): orientation and focal length, stdlib only.

Reads the APP1 "Exif" segment of a JPEG (in the spirit of the own PNG decoder): IFD0's Orientation (0x0112) and the
Exif IFD's FocalLength (0x920A) and FocalLengthIn35mmFilm (0xA405). Anything else in the file is skipped. A file that
is not a JPEG, has no EXIF or a broken one gives `ExifInfo()` (orientation 1, no focal length) - a photo must never fail
to load because of its metadata.

The focal length is only a **suggestion** for the panel; Manu confirms it („Übernehmen“). The orientation is applied
on load (`apply_orientation`): pyglet's decoders (PIL, WIC, GdkPixbuf) ignore it, so phone photos would load sideways.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

ORIENTATION, EXIF_IFD, FOCAL_LENGTH, FOCAL_35MM = 0x0112, 0x8769, 0x920A, 0xA405
_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
_HEAD_BYTES = 256 * 1024  # EXIF lives in the first APP1 segment (≤ 64 KiB); a margin for APP0 / ICC before it
_MAX_ENTRIES = 512


@dataclass(frozen=True)
class ExifInfo:
    orientation: int = 1  # 1 ... 8 (TIFF); 1 = as stored
    focal_mm: float | None = None  # the real focal length
    focal_35mm: float | None = None  # the 35 mm equivalent (what phones write)

    @property
    def swaps_sides(self) -> bool:
        """Orientations 5 ... 8 turn the picture by 90°: width and height swap."""
        return self.orientation in (5, 6, 7, 8)


def read_exif(path: str | Path) -> ExifInfo:
    """The EXIF of a file (only JPEGs have one here); `ExifInfo()` for anything unreadable."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(_HEAD_BYTES)
    except OSError:
        return ExifInfo()
    return parse_jpeg(head)


def parse_jpeg(data: bytes) -> ExifInfo:
    try:
        tiff = _exif_segment(data)
        return ExifInfo() if tiff is None else _parse_tiff(tiff)
    except (struct.error, ValueError, IndexError, ZeroDivisionError):
        return ExifInfo()


def _exif_segment(data: bytes) -> bytes | None:
    """The TIFF block of the first APP1 "Exif" segment, None when there is none before the image data."""
    if data[:2] != b"\xff\xd8":
        return None
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            return None
        marker = data[pos + 1]
        if marker == 0xFF:  # fill byte
            pos += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:  # markers without a length
            pos += 2
            continue
        if marker in (0xDA, 0xD9):  # start of scan / end of image: no EXIF before the pixels
            return None
        (length,) = struct.unpack(">H", data[pos + 2:pos + 4])
        if length < 2:
            return None
        body = data[pos + 4:pos + 2 + length]
        if marker == 0xE1 and body[:6] == b"Exif\x00\x00":
            return body[6:]
        pos += 2 + length
    return None


def _parse_tiff(tiff: bytes) -> ExifInfo:
    order = {b"II": "<", b"MM": ">"}.get(tiff[:2])
    if order is None or struct.unpack(order + "H", tiff[2:4])[0] != 42:
        return ExifInfo()
    (ifd0,) = struct.unpack(order + "I", tiff[4:8])
    tags0 = _ifd(tiff, order, ifd0)
    orientation = tags0.get(ORIENTATION)
    orientation = int(orientation) if isinstance(orientation, int) and 1 <= orientation <= 8 else 1
    focal = focal35 = None
    exif_ifd = tags0.get(EXIF_IFD)
    if isinstance(exif_ifd, int) and 8 <= exif_ifd < len(tiff):
        tags = _ifd(tiff, order, exif_ifd)
        value = tags.get(FOCAL_LENGTH)
        if isinstance(value, float) and 0.0 < value < 10_000.0:
            focal = value
        value = tags.get(FOCAL_35MM)
        if isinstance(value, int) and 0 < value < 10_000:  # 0 = unknown (the EXIF rule)
            focal35 = float(value)
    return ExifInfo(orientation, focal, focal35)


def _ifd(tiff: bytes, order: str, offset: int) -> dict[int, int | float]:
    """The first value of each SHORT / LONG / RATIONAL entry of the IFD at `offset` (the tags this reader needs)."""
    (count,) = struct.unpack(order + "H", tiff[offset:offset + 2])
    out: dict[int, int | float] = {}
    for i in range(min(count, _MAX_ENTRIES)):
        entry = tiff[offset + 2 + 12 * i: offset + 14 + 12 * i]
        if len(entry) < 12:
            break
        tag, kind, n = struct.unpack(order + "HHI", entry[:8])
        size = _TYPE_SIZE.get(kind, 0) * n
        if size == 0:
            continue
        if size <= 4:
            raw = entry[8:8 + size]
        else:
            (at,) = struct.unpack(order + "I", entry[8:12])
            raw = tiff[at:at + size]
            if len(raw) < size:
                continue
        if kind == 3:
            out[tag] = struct.unpack(order + "H", raw[:2])[0]
        elif kind == 4:
            out[tag] = struct.unpack(order + "I", raw[:4])[0]
        elif kind in (5, 10):
            num, den = struct.unpack(order + ("II" if kind == 5 else "ii"), raw[:8])
            if den != 0:
                out[tag] = num / den
    return out


def apply_orientation(rgba, orientation: int):
    """The pixels (top row first) as the photographer held the camera: the TIFF orientation 1 ... 8 undone.
    A contiguous copy, or the input itself for 1 (and any unknown value)."""
    import numpy as np

    if orientation == 2:
        out = rgba[:, ::-1]
    elif orientation == 3:
        out = rgba[::-1, ::-1]
    elif orientation == 4:
        out = rgba[::-1]
    elif orientation == 5:  # transpose
        out = np.transpose(rgba, (1, 0, 2))
    elif orientation == 6:  # stored turned 90° counter-clockwise: turn it clockwise
        out = np.rot90(rgba, k=-1)
    elif orientation == 7:  # transverse
        out = np.transpose(rgba, (1, 0, 2))[::-1, ::-1]
    elif orientation == 8:
        out = np.rot90(rgba, k=1)
    else:
        return rgba
    return np.ascontiguousarray(out)
