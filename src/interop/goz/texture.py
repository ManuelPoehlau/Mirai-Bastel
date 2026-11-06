"""The texture a ZBrush return names, copied for Mirai (P3b, docs/WP_GOZ_P3_PLAN.md §4). Stdlib only.

E3 (reference PC, 2026-11-06): *Texture Map > New From Polypaint* then GoZ wrote `<Tool>_TXTR.tif` beside the `.GoZ`:
an uncompressed baseline TIFF, 2048 x 2048, RGB 8 bit, one strip. Sampled at the UVs it matches the polypaint when its
first row is v = 0, i.e. it is stored bottom-up (AD-026: "ZBrush stores textures upside down"). Mirai's viewport reads
images top-down like any OBJ texture, so the copy is flipped vertically and written as PNG. Any other file (another
TIFF layout, another format) is copied unchanged and reported, since its orientation is unknown.

The copy goes beside the saved scene, `<scene stem>_textures/`, else into Mirai's `goz/textures/` (Manu 2026-11-06):
ZBrush overwrites its own file at the next GoZ. The name carries the source's content hash, so the same image is
copied once.
"""

from __future__ import annotations

import hashlib
import re
import struct
import zlib
from pathlib import Path
from typing import Optional

_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 16: 8}


class TextureError(ValueError):
    """Not a TIFF this module decodes (the file is then copied unchanged)."""


def decode_tiff(data: bytes) -> tuple[int, int, int, list[bytes]]:
    """(width, height, channels, rows top row of the file first) of an uncompressed 8-bit RGB / RGBA TIFF."""
    if data[:4] not in (b"II*\0", b"MM\0*"):
        raise TextureError("not a TIFF")
    bo = "<" if data[:2] == b"II" else ">"
    (ifd,) = struct.unpack_from(bo + "I", data, 4)
    (count,) = struct.unpack_from(bo + "H", data, ifd)
    tags: dict[int, list[int]] = {}
    for i in range(count):
        tag, typ, n, raw = struct.unpack_from(bo + "HHI4s", data, ifd + 2 + 12 * i)
        size = _TYPE_SIZES.get(typ)
        if size is None or typ == 5:
            continue
        where = raw if size * n <= 4 else data[struct.unpack(bo + "I", raw)[0]:][: size * n]
        code = {1: "B", 2: "B", 3: "H", 4: "I", 16: "Q"}[typ]
        tags[tag] = list(struct.unpack_from(bo + code * n, where))
    width, height = tags[256][0], tags[257][0]
    channels = tags.get(277, [1])[0]
    if tags.get(259, [1])[0] != 1 or tags.get(262, [0])[0] != 2 or channels not in (3, 4):
        raise TextureError("compressed or not RGB")
    if any(b != 8 for b in tags.get(258, [8])) or tags.get(284, [1])[0] != 1:
        raise TextureError("not 8 bit chunky")
    pixels = b"".join(data[o:o + c] for o, c in zip(tags[273], tags[279]))
    stride = width * channels
    if len(pixels) < stride * height:
        raise TextureError("strips shorter than the image")
    return width, height, channels, [pixels[y * stride:(y + 1) * stride] for y in range(height)]


def encode_png(width: int, height: int, channels: int, rows: list[bytes]) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    header = struct.pack(">IIBBBBB", width, height, 8, 2 if channels == 3 else 6, 0, 0, 0)
    raw = b"".join(b"\0" + row for row in rows)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


def texture_dir(scene_path: Optional[str | Path], fallback: Path) -> Path:
    """`<scene stem>_textures/` beside a saved scene, else `fallback`."""
    if scene_path is None:
        return Path(fallback)
    scene = Path(scene_path)
    stem = scene.name.split(".mirai")[0] if ".mirai" in scene.name else scene.stem
    return scene.parent / f"{stem}_textures"


def copy_texture(source: str | Path, directory: Path, name: str) -> tuple[Path, Optional[str]]:
    """Copies ZBrush's texture into `directory` as `<name>_<hash>.png` (flipped, see module) or, when it cannot be
    decoded, unchanged under its own extension. Returns the copy and a note for the status line (None = fine)."""
    data = Path(source).read_bytes()
    digest = hashlib.sha256(data).hexdigest()[:10]
    stem = (re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "texture")[:40]
    directory.mkdir(parents=True, exist_ok=True)
    note = None
    try:
        width, height, channels, rows = decode_tiff(data)
        target = directory / f"{stem}_{digest}.png"
        payload = encode_png(width, height, channels, rows[::-1])
    except (TextureError, KeyError, IndexError, struct.error) as exc:
        target = directory / f"{stem}_{digest}{Path(source).suffix.lower() or '.img'}"
        payload = data
        note = f"texture copied unchanged ({exc}) - it may show upside down"
    if not target.exists():
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(payload)
        tmp.replace(target)
    return target, note
