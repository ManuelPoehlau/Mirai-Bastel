"""The LookDev material's image maps (AD-039 §10, S7; Manu 2026-11-24 Q-P3-2 „Map-Pfade“): what the app checks before
an image becomes a map and before the LookDev pass loads it. Stdlib only (no GL, no decoder): the size comes from the
file's header (`sclera_map.image_size`).

**The maps** (`core.LookMaps`) sit on the object's `LookMaterial` and use the object's UVs (the albedo's):
- `roughness`: a grey image (its red channel, linear) multiplying the material's roughness - white keeps it, black is
  mirror-smooth;
- `normal`: a tangent-space normal map (ZBrush / xNormal export), OpenGL convention (green up) unless the material says
  DirectX (`normal_green_down`); 128 is zero, `normal_strength` scales the tilt;
- `translucency`: a grey image multiplying the light through thin parts (S4's transmission, or M1's proxy without it).

**Size policy:** up to `MAX_SIZE` on either side; larger is refused when it is assigned, and an assigned file that has
grown beyond it is not drawn. A missing file keeps its path in the material (the scene round trip writes it back) and
draws without that map. In memory a path is absolute; the scene file stores it relative to the scene, and Save copies
it into `<scene>_textures/` (`texture_files`, the sclera map's rule).
"""

from __future__ import annotations

import os
from pathlib import Path

from core.scene import LOOK_MAP_FIELDS

from .sclera_map import FORMATS, MapCheck, image_size

#: The largest accepted side in pixels (`PROVISIONAL`): 4096² RGBA8 with mips is 85 MiB of graphics memory per map.
MAX_SIZE = 4096
#: Above this side a hint is shown (2048² with mips = 21 MiB; the reference PC has 512 MiB).
LARGE_SIZE = 2048
#: The panel's names (German, the panel's language).
LABELS = {"roughness": "Rauheit-Map", "normal": "Normal-Map", "translucency": "Durchscheinen-Map"}
KINDS = LOOK_MAP_FIELDS


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
    note = f"{width}×{height}: viel Grafikspeicher" if max(width, height) > LARGE_SIZE else ""
    return MapCheck(True, (width, height), "", note)


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
    """`path` when the LookDev pass may load it (it exists and passes `check`), else None (drawn without that map)."""
    return path if path is not None and cached_check(path).usable else None


def file_name(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def status_text(path: str | None) -> str:
    """The panel's text for one map: "keine", its file name, or why it is not drawn."""
    if path is None:
        return "keine"
    result = cached_check(path)
    if not result.usable:
        return f"{file_name(path)} ({result.problem})"
    return file_name(path) + (f" ({result.note})" if result.note else "")
