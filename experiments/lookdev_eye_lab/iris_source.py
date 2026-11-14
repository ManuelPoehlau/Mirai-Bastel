"""Where the iris image comes from, for P1 and P1b alike (2026-11-14, Manu: "eine eigene Datei `out/iris_custom.png`").

- `out/iris_custom.png` exists and is a usable PNG -> that file is the iris texture.
- otherwise -> the procedural iris, written to `out/iris.png` (`eye_geometry.write_iris_png`).

The custom file is **only ever read**: nothing in the lab opens it for writing, renames, copies over or deletes it
(the procedural image has its own name, and `write_iris_png` refuses the custom name). Both scene builders
(`lab_scene.build_scene` for P1, `refraction_gl.build_scene` for P1b) call `choose()`, so both show the same source.

Two checks, both falling back to the procedural iris with a note instead of failing:
1. `inspect()` (GL-free, the same on every platform): signature, chunk CRCs, IHDR, PLTE / IEND, and the image data
   must inflate to the size IHDR implies;
2. `confirm_loadable()` (needs the GL context the scene builder has anyway): the production texture loader
   (`GLRenderStore.texture`, pyglet's decoder) must turn it into a texture.

**How the image is mapped** (the same planar UVs as the procedural iris, `eye_geometry.iris_uv`): the image's square
spans the iris disc of radius `IRIS_RADIUS` (7.18 mm, the iris root), its centre is the pupil centre, its top is +Y
(up). Measured from the centre as a share of half the image width:
- pupil edge 26.8 % (r 1.92 mm; P1b's refraction treats rays inside this radius as the dark pupil, whatever the image
  shows there; P1 shows the image there),
- visible limbus 82 % (r 5.88 mm; beyond it the image is hidden behind the sclera / limbal tissue).
Non-square images are stretched to the square. An optional `out/iris_custom.json` moves the custom image's own pupil
edge / iris edge onto these radii (`iris_fit`, radial remap). The image is sRGB: P1's T-A shows it as it is (display-referred),
T-B ... T-D and P1b decode it to linear light. Alpha is ignored. The texture loader keys its cache by the file's
modification time, so a file replaced while the lab runs shows at the next frame (the choice custom / procedural itself
is made when the scene is built).
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from . import eye_geometry as geo
from . import iris_fit

CUSTOM_NAME = "iris_custom.png"
PROCEDURAL_NAME = "iris.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_COLOUR_TYPES = {0: "grey", 2: "RGB", 3: "palette", 4: "grey+alpha", 6: "RGBA"}
#: Shares of half the image width (see the module docstring).
PUPIL_SHARE = geo.PUPIL_RADIUS / geo.IRIS_RADIUS
LIMBUS_SHARE = geo.LIMBUS_RADIUS / geo.IRIS_RADIUS


@dataclass(frozen=True)
class IrisSource:
    path: Path
    custom: bool
    note: str  # one line for the HUD / the probe header
    #: The radial fit from `out/iris_custom.json` (custom image only); None = the planar mapping above.
    fit: "iris_fit.IrisFit | None" = None
    fit_note: str = ""  # why a sidecar that exists was not used

    def describe(self) -> str:
        text = f"iris texture: {'CUSTOM' if self.custom else 'procedural'} {self.path.name} - {self.note}"
        if self.fit is not None:
            text += f"; {self.fit.describe()}"
        elif self.fit_note:
            text += f"; {iris_fit.SIDECAR_NAME} ignored: {self.fit_note}"
        return text


_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
_ADAM7 = ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))


def _expected_bytes(width: int, height: int, bits_per_pixel: int, interlaced: bool) -> int:
    """Length of the decompressed image data: one filter byte plus the packed pixels per row (per Adam7 pass)."""
    def rows(w: int, h: int) -> int:
        return 0 if w == 0 or h == 0 else h * (1 + (w * bits_per_pixel + 7) // 8)

    if not interlaced:
        return rows(width, height)
    return sum(rows((width - x0 + dx - 1) // dx if width > x0 else 0, (height - y0 + dy - 1) // dy if height > y0 else 0)
               for x0, y0, dx, dy in _ADAM7)


def inspect(path: Path) -> tuple[bool, str]:
    """(usable, description), checked by the lab itself so the verdict is the same on every platform (pyglet decodes
    PNGs with the OS's codec on Windows, which accepted a broken file in the reference-PC test of 2026-11-14): the
    signature, every chunk's CRC, IHDR first, PLTE for palette images, IEND, and the IDAT stream must inflate to
    exactly the size IHDR implies. Reads the file only."""
    try:
        data = Path(path).read_bytes()  # read-only
    except OSError as exc:
        return False, f"cannot be read ({exc.__class__.__name__})"
    if data[:8] != PNG_SIGNATURE:
        return False, "not a PNG (signature)"
    pos, chunks = 8, []
    while pos + 12 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + length]
        if len(body) != length or pos + 12 + length > len(data):
            return False, f"PNG truncated in chunk {kind!r}"
        (crc,) = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            return False, f"PNG chunk {kind.decode('latin-1')} has a wrong CRC"
        chunks.append((kind, body))
        pos += 12 + length
        if kind == b"IEND":
            break
    if not chunks or chunks[0][0] != b"IHDR" or len(chunks[0][1]) != 13:
        return False, "PNG without a valid IHDR"
    width, height, depth, colour, _compression, _filter, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    if width == 0 or height == 0:
        return False, "PNG with a zero size"
    if colour not in _CHANNELS or depth not in (1, 2, 4, 8, 16):
        return False, f"PNG with an unsupported format (colour type {colour}, {depth} bit)"
    kinds = [k for k, _ in chunks]
    if kinds[-1] != b"IEND":
        return False, "PNG without IEND (truncated)"
    if colour == 3 and b"PLTE" not in kinds:
        return False, "palette PNG without PLTE"
    try:
        pixels = zlib.decompress(b"".join(body for k, body in chunks if k == b"IDAT"))
    except zlib.error:
        return False, "PNG image data does not decompress"
    expected = _expected_bytes(width, height, depth * _CHANNELS[colour], bool(interlace))
    if len(pixels) != expected:
        return False, f"PNG image data has {len(pixels)} bytes, {expected} expected"
    kind = _COLOUR_TYPES.get(colour, f"colour type {colour}")
    text = f"{width}x{height}, {depth}-bit {kind}" + (", interlaced" if interlace else "")
    if width != height:
        text += " (not square: stretched onto the iris disc)"
    return True, text


def fingerprint(path: Path) -> str:
    """Short SHA-1 of the file's bytes, so a results file can name the exact image (read-only)."""
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()[:12]


def procedural(out_dir: Path, reason: str = "") -> IrisSource:
    path = geo.write_iris_png(Path(out_dir) / PROCEDURAL_NAME)
    note = f"{geo.IRIS_IMAGE_SIZE}x{geo.IRIS_IMAGE_SIZE} generated"
    if reason:
        note += f"; {CUSTOM_NAME} not used: {reason}"
    return IrisSource(path, False, note)


def choose(out_dir: Path) -> IrisSource:
    """The custom image if `out_dir/iris_custom.png` exists and looks like a usable PNG, else the procedural one. With
    the custom image, `out_dir/iris_custom.json` (if present and valid) adds the radial fit (`iris_fit`); the
    procedural iris never uses it."""
    custom = Path(out_dir) / CUSTOM_NAME
    if not custom.exists():
        return procedural(out_dir)
    usable, text = inspect(custom)
    if not usable:
        return procedural(out_dir, text)
    fit, fit_note = iris_fit.load(out_dir)  # read-only, like the image
    return IrisSource(custom, True, f"{text}, sha1 {fingerprint(custom)}", fit, fit_note)


def confirm_loadable(source: IrisSource, out_dir: Path) -> IrisSource:
    """With a GL context: the custom image must load through the production texture loader; else the procedural
    iris (the loader prints its own error)."""
    if not source.custom:
        return source
    from pyglet import gl

    from viewport.gl_render_store import GLRenderStore

    # Defensive: the probes check that the pixel-store state is left as found. pyglet's loader left the unpack
    # alignment unchanged in the container (RGB and RGBA, 2026-11-14); on Windows it decodes with the OS's codec,
    # which was not checked, so the value is put back either way.
    saved = gl.GLint()
    gl.glGetIntegerv(gl.GL_UNPACK_ALIGNMENT, saved)
    try:
        texture = GLRenderStore.texture(str(source.path))
    finally:
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, saved.value)
    if texture is None:
        return procedural(out_dir, "the texture loader could not decode it")
    return source
