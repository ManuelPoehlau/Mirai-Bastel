"""Where the iris image comes from, for P1 and P1b alike (2026-11-14, Manu: "eine eigene Datei `out/iris_custom.png`").

- `out/iris_custom.png` exists and is a usable PNG -> that file is the iris texture.
- otherwise -> the procedural iris, written to `out/iris.png` (`eye_geometry.write_iris_png`).

The custom file is **only ever read**: nothing in the lab opens it for writing, renames, copies over or deletes it
(the procedural image has its own name, and `write_iris_png` refuses the custom name). Both scene builders
(`lab_scene.build_scene` for P1, `refraction_gl.build_scene` for P1b) call `choose()`, so both show the same source.

Two checks, both falling back to the procedural iris with a note instead of failing:
1. `inspect()` (GL-free): the PNG signature and IHDR - size, bit depth, colour type, interlace;
2. `confirm_loadable()` (needs the GL context the scene builder has anyway): the production texture loader
   (`GLRenderStore.texture`, pyglet's decoder) must turn it into a texture.

**How the image is mapped** (the same planar UVs as the procedural iris, `eye_geometry.iris_uv`): the image's square
spans the iris disc of radius `IRIS_RADIUS` (7.18 mm, the iris root), its centre is the pupil centre, its top is +Y
(up). Measured from the centre as a share of half the image width:
- pupil edge 26.8 % (r 1.92 mm; P1b's refraction treats rays inside this radius as the dark pupil, whatever the image
  shows there; P1 shows the image there),
- visible limbus 82 % (r 5.88 mm; beyond it the image is hidden behind the sclera / limbal tissue).
Non-square images are stretched to the square. The image is sRGB: P1's T-A shows it as it is (display-referred),
T-B ... T-D and P1b decode it to linear light. Alpha is ignored. The texture loader keys its cache by the file's
modification time, so a file replaced while the lab runs shows at the next frame (the choice custom / procedural itself
is made when the scene is built).
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from . import eye_geometry as geo

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

    def describe(self) -> str:
        return f"iris texture: {'CUSTOM' if self.custom else 'procedural'} {self.path.name} - {self.note}"


def inspect(path: Path) -> tuple[bool, str]:
    """(usable, description) from the PNG signature and IHDR alone; reads at most 33 bytes."""
    try:
        with open(path, "rb") as handle:  # read-only
            head = handle.read(33)
    except OSError as exc:
        return False, f"cannot be read ({exc.__class__.__name__})"
    if head[:8] != PNG_SIGNATURE:
        return False, "not a PNG (signature)"
    if len(head) < 33 or head[12:16] != b"IHDR":
        return False, "PNG without a valid IHDR"
    width, height, depth, colour, _compression, _filter, interlace = struct.unpack(">IIBBBBB", head[16:29])
    if width == 0 or height == 0:
        return False, "PNG with a zero size"
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
    """The custom image if `out_dir/iris_custom.png` exists and looks like a usable PNG, else the procedural one."""
    custom = Path(out_dir) / CUSTOM_NAME
    if not custom.exists():
        return procedural(out_dir)
    usable, text = inspect(custom)
    if not usable:
        return procedural(out_dir, text)
    return IrisSource(custom, True, f"{text}, sha1 {fingerprint(custom)}")


def confirm_loadable(source: IrisSource, out_dir: Path) -> IrisSource:
    """With a GL context: the custom image must load through the production texture loader; else the procedural
    iris (the loader prints its own error)."""
    if not source.custom:
        return source
    from viewport.gl_render_store import GLRenderStore

    if GLRenderStore.texture(str(source.path)) is None:
        return procedural(out_dir, "the texture loader could not decode it")
    return source
