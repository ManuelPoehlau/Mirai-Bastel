"""The sclera's colour map (AD-035 M1, Manu 2026-11-17): what the app checks before an image becomes an eye's map and
before the eye pass loads it. Stdlib only (no GL, no decoder): the size is read from the file's header.

**The image** is the eye seen from the front (the limbus-anchored front disc, S-1): centre = the cornea's centre
(eye-local +Z), right = +X, up = +Y, the limbus on the circle at `LIMBUS_SHARE` of half the image width, the image's
inscribed circle 130° from the front pole (`viewport.eye_optics.SCLERA_RIM_DEG`; beyond it the rim colour is held,
S-13). An opaque RGB colour image (alpha is ignored, S-6) that replaces the material's base colour while it is usable
(S-7). Template and a synthetic test map: `docs/research/eye_sclera_assets_2026-11-17/`.

**Size policy (S-8):** 1024² recommended; up to `MAX_SIZE` on either side is accepted; a larger image is refused when
it is assigned, and an assigned file that has grown beyond it (replaced on disk) is not drawn - never loaded silently.
A missing file keeps its path in the eye (the scene round trip writes it back) and the eye draws its base colour.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from pathlib import Path

#: The limbus's radius in the image, a share of half its width (AD-035 §3, S-1).
LIMBUS_SHARE = 0.25
#: Recommended / default authoring size (S-8).
RECOMMENDED_SIZE = 1024
#: The largest accepted side in pixels (S-8; 2048² RGBA8 with mips = 21.3 MiB of the reference PC's 512 MiB).
MAX_SIZE = 2048
#: The formats whose size the header reader knows (the GL loader, pyglet, reads them on every platform).
FORMATS = ("PNG", "JPEG", "BMP")
#: The persistent authoring hint (Eye Lab).
HINT = ("Bild = Auge von vorn (Mitte = Hornhautmitte, rechts = +X, oben = +Y); Limbus auf 1/4 der halben Bildbreite, "
        "Bildrand = 130°. 1024² empfohlen, höchstens 2048². Vorlage: docs/research/eye_sclera_assets_2026-11-17/")


@dataclass(frozen=True)
class MapCheck:
    """One file's state: `usable` = it exists, is a readable PNG / JPEG / BMP header and within the size policy."""

    usable: bool
    size: tuple[int, int] | None
    problem: str  # "" when usable; else "nicht gefunden" / "zu groß ..." / "unbekanntes Format"
    note: str = ""  # a hint that does not block (not square, not the recommended size)


def image_size(path: str | Path) -> tuple[str, int, int] | None:
    """(format, width, height) from the file's header, or None when it is not a PNG / JPEG / BMP this reader knows.
    `OSError` when the file cannot be read."""
    with open(path, "rb") as fh:
        head = fh.read(32)
        if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
            width, height = struct.unpack(">II", head[16:24])
            return "PNG", width, height
        if head[:2] == b"BM" and len(head) >= 26:
            width, height = struct.unpack("<ii", head[18:26])
            return "BMP", abs(width), abs(height)
        if head[:2] == b"\xff\xd8":
            return _jpeg_size(fh)
    return None


def _jpeg_size(fh) -> tuple[str, int, int] | None:
    fh.seek(2)
    while True:
        byte = fh.read(1)
        while byte and byte != b"\xff":
            byte = fh.read(1)
        while byte == b"\xff":
            byte = fh.read(1)
        if not byte:
            return None
        marker = byte[0]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            continue  # markers without a length
        length_bytes = fh.read(2)
        if len(length_bytes) < 2:
            return None
        length = struct.unpack(">H", length_bytes)[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):  # a start of frame
            frame = fh.read(5)
            if len(frame) < 5:
                return None
            height, width = struct.unpack(">HH", frame[1:5])
            return "JPEG", width, height
        fh.seek(length - 2, os.SEEK_CUR)


def check(path: str | Path) -> MapCheck:
    """The size policy for `path` (no decode)."""
    try:
        found = image_size(path)
    except OSError:
        return MapCheck(False, None, "nicht gefunden")
    if found is None:
        return MapCheck(False, None, f"unbekanntes Format ({'/'.join(FORMATS)} erwartet)")
    _fmt, width, height = found
    if width <= 0 or height <= 0:
        return MapCheck(False, None, "leeres Bild")
    if max(width, height) > MAX_SIZE:
        return MapCheck(False, (width, height), f"zu groß: {width}×{height}, höchstens {MAX_SIZE}×{MAX_SIZE}")
    notes = []
    if width != height:
        notes.append(f"nicht quadratisch ({width}×{height}): die Scheibe wird verzerrt")
    elif width != RECOMMENDED_SIZE:
        notes.append(f"{width}×{height} (empfohlen {RECOMMENDED_SIZE}×{RECOMMENDED_SIZE})")
    return MapCheck(True, (width, height), "", "; ".join(notes))


_CACHE: dict[tuple, MapCheck] = {}


def cached_check(path: str) -> MapCheck:
    """`check` cached per file state (path, modification time, size): a view sync or a GUI frame costs one `stat`."""
    try:
        stat = os.stat(path)
    except OSError:
        return MapCheck(False, None, "nicht gefunden")
    key = (path, stat.st_mtime_ns, stat.st_size)
    result = _CACHE.get(key)
    if result is None:
        for old in [k for k in _CACHE if k[0] == path]:
            del _CACHE[old]
        result = _CACHE[key] = check(path)
    return result


def drawable(path: str | None) -> str | None:
    """`path` when the eye pass may load it (it exists and passes `check`), else None (the eye draws its base colour)."""
    return path if path is not None and cached_check(path).usable else None


def status_text(path: str | None) -> str:
    """The Eye Lab's status line for an eye's map."""
    if path is None:
        return "Lederhaut: Grundfarbe (kein Bild)"
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    result = cached_check(path)
    if not result.usable:
        return f"Lederhaut: {name} ({result.problem}) - Grundfarbe"
    return f"Lederhaut: {name}" + (f" ({result.note})" if result.note else "")
