"""The brush library (AD-037 §14 Phase 4c; proposal 2026-11-25 §6): alphas, brush presets, favourites, the import.

**Where things live** (Manu 2026-11-25; proposal §6.1):
- **built in**, read-only, in the repo: the six 4a test alphas (`alpha.TEST_ALPHAS`, generated in memory), the starter
  alphas `assets/paint/alphas/<category>/<stem>.png` (written by `tools/make_starter_alphas.py --adopt` only for the
  categories Manu accepted on the contact sheet, P-22; names in `assets/paint/alphas/index.json`) and the presets
  `assets/paint/brushes/<slug>.json`;
- **the user's**, in `user_dir` (`~/.mirai_bastel/paint/`, set by `src/main.py`; nothing is written anywhere else):
  `alphas/<slug>_<hash12>.png` (normalised, an 8-bit greyscale PNG; its 64² thumbnail in `alphas/thumbs/`), `brushes/<slug>.json`, `library.json` (favourites, the user
  alphas' names and categories, "Größe behalten"). A PNG dropped into `alphas/` is picked up by the scan (category
  "Unsortiert", the name from the file name; normalised with the suggested source mode). Without a `user_dir` (tests,
  tools) the user's part is empty, saving is refused and favourites live in memory.
- **Scenes never reference alphas or presets**: a stroke is baked into layer pixels.

**Ids** (§6.2): `test/<stem>` (4a), `builtin:<category>/<stem>`, `user:<hash12>` - the hash is `alpha.pixel_hash` of the
normalised pixels, so the same image imported twice is one alpha. A brush keeps `{id, name, hash}` of its alpha
(`TipSettings.alpha`, `alpha_name`, `alpha_hash`); `resolve` looks it up **id -> hash -> name -> missing**. Missing: the
brush paints with the round tip, the panel says "Alpha fehlt: <name>", and the reference stays (saving keeps it).

**Presets** (§6.4): JSON `"format": "mirai.paint.brush/1"`, one file per preset, the `eye_presets` rules (a bad or
foreign file is skipped with its reason in `problems`, names are slugged, saves are atomic). A preset holds the tip
(alpha reference, invert, contrast, Kreismaske), the radius (P-20, as `radius_percent`), opacity, flow, hardness, curve
and the stroke dynamics - **never** the colour, the tool, the mirror or the layer (session state, P-25). Built-ins are
read-only (save as / duplicate only). **Deviations from §6.4's example:** the dynamics are the flat `StrokeDynamics`
fields (the example nested jitter and scatter); the import's source mode is not part of a tip (a stored alpha is
already grey: the mode is an import choice, §6.3) - invert and contrast are, applied when the alpha is read.

**Cache** (§6.6): decoded alphas (pixels + mips, also the invert / contrast variants) in an LRU capped at
`CACHE_BYTES` (64 MiB).

**Import** (§6.3, P-26): `open_import` reads an image and suggests the source mode (Alphakanal / Luminanz / Luminanz ×
Alphakanal) and invert; `import_pixels` makes the normalised grey (longest side clamped to `IMPORT_MAX` = 1024 px by a
box downsample, then invert and contrast), `ImportDraft.border_warning` flags a border that is not black (a visible
square edge); `PaintLibrary.import_alpha` writes it (or finds the same pixels already there).
"""

from __future__ import annotations

import dataclasses
import json
import math
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import alpha as alpha_api
from .brush import CONTRAST_RANGE, RADIUS_STEPS_PERCENT, BrushSettings, TipSettings
from .dynamics import StrokeDynamics

#: The thumbnail's side in px (the picker's grid, §6.6) and the folder of the user alphas' thumbnail files.
THUMB = 64
THUMB_DIR = "thumbs"
#: The repo's built-in assets (read-only).
BUILTIN_DIR = Path(__file__).resolve().parents[3] / "assets" / "paint"
#: The user's assets under the per-user state folder (`src/main.py`: `~/.mirai_bastel/paint/`).
USER_SUBDIR = "paint"
FORMAT = "mirai.paint.brush/1"
LIBRARY_FORMAT = "mirai.paint.library/1"
#: `PROVISIONAL` (§6.6): the alpha cache's cap in bytes (pixels and mips).
CACHE_BYTES = 64 * 1024 * 1024
#: P-22: the import's longest side in px (box downsample beyond it); smaller than `IMPORT_MIN` is refused.
IMPORT_MAX = 1024
IMPORT_MIN = 8
#: A border brighter than this mean (0..1) on the outermost pixel ring warns of a visible square edge (`PROVISIONAL`).
BORDER_WARN = 0.03

#: The starter categories (P-22): folder key -> label.
CATEGORIES = {
    "organisch": "Organisch",
    "adern": "Adern",
    "sprenkel": "Sprenkel",
    "schmutz": "Schmutz",
    "schaden": "Schaden",
    "oberflaeche": "Oberfläche",
    "formen": "Formen",
}
TEST_CATEGORY = "Test-Alphas (4a)"
UNSORTED = "Unsortiert"
#: The 4a test alphas' categories (they stay built in; the starter set joins them once adopted).
TEST_CATEGORIES = {"test/poren": "Organisch", "test/ader": "Adern", "test/kratzer": "Schaden", "test/fleck": "Schmutz",
                   "test/punkte": "Sprenkel", "test/quadrat": "Formen"}

#: Import source modes (P-26).
MODE_ALPHA = "alpha"
MODE_LUMINANCE = "luminance"
MODE_BOTH = "luminance_alpha"
MODES = (MODE_ALPHA, MODE_LUMINANCE, MODE_BOTH)
MODE_LABELS = {MODE_ALPHA: "Alphakanal", MODE_LUMINANCE: "Luminanz", MODE_BOTH: "Luminanz × Alphakanal"}

#: The room's brush at the start: the built-in "Runder Pinsel" (equal to `BrushSettings()`, pinned by a test).
DEFAULT_PRESET = "builtin:runder_pinsel"

_HASHED = re.compile(r"^(?P<slug>.*)_(?P<hash>[0-9a-f]{12})\.png$")


class LibraryError(ValueError):
    """An operation the library refuses (the message is the status line's reason)."""


def slug(name: str) -> str:
    """A safe file-name stem for a name ("Poren-Spray" -> "poren_spray"; umlauts spelled out)."""
    text = name.strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    stem = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if not stem:
        raise LibraryError("ein Name braucht Buchstaben oder Ziffern")
    return stem[:48]


#: zlib level of the alpha files (`PROVISIONAL`): an alpha is written once, at its import; level 6 put a 1024² noise
#: alpha at ~0.3 s [C] as RGBA, the grey file at level 3 is a quarter of the data.
PNG_LEVEL = 3


def encode_grey_png(grey: np.ndarray, level: int = PNG_LEVEL) -> bytes:
    """An 8-bit greyscale PNG (colour type 0, top row first, every row with the "Up" filter) - the alpha files; read
    back by `iris_import.decode_png` (grey -> R = G = B)."""
    import struct
    import zlib

    grey = np.ascontiguousarray(grey, dtype=np.uint8)
    h, w = grey.shape
    up = np.empty_like(grey)
    up[0] = grey[0]
    up[1:] = grey[1:] - grey[:-1]  # uint8 wraps modulo 256 as the filter wants
    raw = np.concatenate([np.full((h, 1), 2, np.uint8), up], axis=1).tobytes()

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

    header = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, level)) + chunk(b"IEND", b"")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


# -- alphas ------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AlphaEntry:
    """One alpha of the library (pixels are read on demand, `PaintLibrary.alpha`)."""

    id: str
    name: str
    category: str
    source: str  # "test" | "builtin" | "user"
    path: Path | None = None
    hash: str | None = None  # known without reading the pixels (user files carry it in their name)

    @property
    def builtin(self) -> bool:
        return self.source != "user"


def _box_down(grey: np.ndarray, limit: int) -> np.ndarray:
    """`grey` (h, w) uint8 with its longest side at most `limit`: an integer box average (edges repeated)."""
    h, w = grey.shape
    f = math.ceil(max(h, w) / limit)
    if f <= 1:
        return grey
    ph, pw = -h % f, -w % f
    if ph or pw:
        grey = np.pad(grey, ((0, ph), (0, pw)), mode="edge")
    hh, ww = grey.shape[0] // f, grey.shape[1] // f
    sums = grey.reshape(hh, f, ww, f).astype(np.uint32).sum(axis=(1, 3))
    return ((sums + (f * f) // 2) // (f * f)).astype(np.uint8)


def reduce_rgba(rgba: np.ndarray, limit: int = IMPORT_MAX) -> np.ndarray:
    """`rgba` box-downsampled per channel to `limit` px on its longest side (the import's clamp, P-22). Luminance and
    the alpha channel are linear, so reducing before the source mode equals reducing after it up to rounding (and
    for "Luminanz × Alphakanal" up to the product's mixing inside a box)."""
    if max(rgba.shape[:2]) <= limit:
        return rgba
    return np.ascontiguousarray(np.stack([_box_down(np.ascontiguousarray(rgba[..., c]), limit) for c in range(4)],
                                         axis=-1))


def _luminance8(rgba: np.ndarray) -> np.ndarray:
    """Rec.709 luminance of the display values (P-16) as uint8, integer arithmetic (a 1024² image in a few ms)."""
    from ..iris_import import LUMA

    weights = np.rint(np.asarray(LUMA, dtype=np.float64) * 65536.0).astype(np.uint32)
    rgb = rgba[..., :3].astype(np.uint32)
    value = rgb[..., 0] * weights[0] + rgb[..., 1] * weights[1] + rgb[..., 2] * weights[2]
    return np.minimum((value + 32768) >> 16, 255).astype(np.uint8)


def source_grey(rgba: np.ndarray, mode: str) -> np.ndarray:
    """(h, w) uint8 grey of `rgba` by the source mode (P-26)."""
    if mode == MODE_ALPHA:
        return np.ascontiguousarray(rgba[..., 3])
    lum = _luminance8(rgba)
    if mode == MODE_LUMINANCE:
        return lum
    if mode == MODE_BOTH:
        return ((lum.astype(np.uint16) * rgba[..., 3] + 127) // 255).astype(np.uint8)
    raise LibraryError(f"Quelle eine von {MODES}, nicht {mode!r}")


def suggest(rgba: np.ndarray) -> tuple[str, bool]:
    """(source mode, invert) suggested for an image (P-26, only a suggestion): no alpha channel -> Luminanz; uniform
    RGB with a varying alpha -> Alphakanal; both varying -> Luminanz × Alphakanal; a bright border -> invert."""
    step = max(1, max(rgba.shape[:2]) // 256)  # a strided look is enough for the decision
    small = rgba[::step, ::step]
    alpha_varies = bool(small[..., 3].min() < 250)
    lum = _luminance8(small)
    if not alpha_varies:
        mode = MODE_LUMINANCE
    else:
        visible = small[..., 3] > 8
        rgb_varies = bool(visible.any() and np.ptp(lum[visible]) > 12)
        mode = MODE_BOTH if rgb_varies else MODE_ALPHA
    grey = source_grey(small, mode)
    ring = np.concatenate((grey[0], grey[-1], grey[:, 0], grey[:, -1])).astype(np.float64) / 255.0
    return mode, bool(ring.mean() > 0.5)


def import_pixels(rgba: np.ndarray, mode: str, invert: bool = False, contrast: float = 0.0,
                  limit: int = IMPORT_MAX) -> np.ndarray:
    """The normalised alpha of an image: the source mode's grey, box-downsampled to `limit`, then invert and contrast
    (`alpha.contrast_lut`). Refuses an image smaller than `IMPORT_MIN` px or one that paints nothing."""
    h, w = rgba.shape[:2]
    if min(h, w) < IMPORT_MIN:
        raise LibraryError(f"das Bild ist zu klein ({w} x {h} px, mindestens {IMPORT_MIN} px)")
    lo, hi = CONTRAST_RANGE
    if not lo <= contrast <= hi:
        raise LibraryError(f"Kontrast in [{lo}, {hi}]")
    grey = _box_down(source_grey(rgba, mode), limit)
    if invert or contrast:
        grey = alpha_api.contrast_lut(invert, contrast)[grey]
    if not grey.any():
        raise LibraryError("das Alpha ist leer (überall schwarz) - Quelle oder Invertieren ändern")
    return np.ascontiguousarray(grey)


def border_warning(grey: np.ndarray) -> bool:
    """The outermost pixel ring is not black (mean above `BORDER_WARN`): the stamp would show a square edge."""
    ring = np.concatenate((grey[0], grey[-1], grey[:, 0], grey[:, -1])).astype(np.float64) / 255.0
    return bool(ring.mean() > BORDER_WARN)


@dataclass
class ImportDraft:
    """The import card's state (§6.3): the image, the chosen mode, invert, contrast, name and category, and the
    suggestion it started from. `preview()` is the result as it would be imported."""

    path: Path
    rgba: np.ndarray
    mode: str
    invert: bool
    contrast: float
    name: str
    category: str = UNSORTED
    suggested: tuple[str, bool] = (MODE_LUMINANCE, False)
    _preview: tuple | None = field(default=None, repr=False)

    def preview(self) -> np.ndarray:
        key = (self.mode, self.invert, round(float(self.contrast), 4))
        if self._preview is None or self._preview[0] != key:
            self._preview = (key, import_pixels(self.rgba, self.mode, self.invert, self.contrast))
        return self._preview[1]

    @property
    def border_warning(self) -> bool:
        try:
            return border_warning(self.preview())
        except LibraryError:
            return False


def read_image_rgba(path: Path) -> np.ndarray:
    """(h, w, 4) uint8 RGBA of an image file: a PNG through the own decoder, else pyglet's (`iris_import.read_rgba`)."""
    from ..iris_import import decode_png, read_rgba

    data = path.read_bytes()
    try:
        return decode_png(data, slow=False)
    except ValueError:
        return read_rgba(path)


def open_import(path) -> tuple[ImportDraft | None, str]:
    """(draft, message): the image read and the source mode and invert suggested; None with the reason when it cannot
    be read or is too small."""
    path = Path(path)
    try:
        rgba = read_image_rgba(path)
    except (OSError, ValueError) as exc:
        return None, f"Alpha-Import: {path.name} nicht lesbar ({exc})"
    h, w = rgba.shape[:2]
    if min(h, w) < IMPORT_MIN:
        return None, f"Alpha-Import: {path.name} ist zu klein ({w} x {h} px, mindestens {IMPORT_MIN} px)"
    rgba = reduce_rgba(rgba)  # once: the card's live preview and the import work on <= IMPORT_MAX px
    mode, invert = suggest(rgba)
    name = re.sub(r"[_\-]+", " ", path.stem).strip() or "Alpha"
    draft = ImportDraft(path, rgba, mode, invert, 0.0, name[:40], UNSORTED, (mode, invert))
    note = f"Vorschlag: {MODE_LABELS[mode]}" + (", invertiert (heller Rand)" if invert else "")
    return draft, f"Alpha-Import: {path.name} ({w} x {h} px) - {note}"


# -- presets -----------------------------------------------------------------------------------------------------------

#: The `BrushSettings` fields a preset holds (P-20 radius yes; P-25 colour no; tool, mirror: session state).
PRESET_FIELDS = ("tip", "radius_step", "opacity", "flow", "hardness", "curve", "dynamics")
_TIP_KEYS = {"alpha", "invert", "contrast", "kreismaske"}
_DYNAMICS_KEYS = {f.name for f in dataclasses.fields(StrokeDynamics)}
_TOP_KEYS = {"format", "name", "category", "tip", "radius_percent", "opacity", "flow", "hardness", "curve", "dynamics"}


def _same_tip(a: TipSettings, b: TipSettings) -> bool:
    return (a.alpha, a.kreismaske, a.invert, a.contrast) == (b.alpha, b.kreismaske, b.invert, b.contrast)


def nearest_radius_step(percent: float) -> int:
    return min(range(len(RADIUS_STEPS_PERCENT)), key=lambda i: abs(RADIUS_STEPS_PERCENT[i] - float(percent)))


@dataclass(frozen=True)
class BrushPreset:
    id: str
    name: str
    category: str
    tip: TipSettings
    radius_step: int
    opacity: float
    flow: float
    hardness: float
    curve: str
    dynamics: StrokeDynamics
    builtin: bool = False
    path: Path | None = None

    @classmethod
    def from_brush(cls, id: str, name: str, category: str, brush: BrushSettings, builtin: bool = False,
                   path: Path | None = None) -> "BrushPreset":
        return cls(id, name, category, *(getattr(brush, f) for f in PRESET_FIELDS), builtin=builtin, path=path)

    def apply(self, brush: BrushSettings, keep_size: bool = False) -> BrushSettings:
        """`brush` with this preset's values; colour, tool and mirror stay (P-25), the radius too with `keep_size`."""
        values = {f: getattr(self, f) for f in PRESET_FIELDS}
        if keep_size:
            del values["radius_step"]
        return dataclasses.replace(brush, **values)

    def matches(self, brush: BrushSettings, keep_size: bool = False) -> bool:
        """`brush` paints as this preset (False: the panel's "geändert"); the radius is ignored with `keep_size`."""
        if not _same_tip(self.tip, brush.tip):
            return False
        if not keep_size and self.radius_step != brush.radius_step:
            return False
        return all(getattr(self, f) == getattr(brush, f) for f in ("opacity", "flow", "hardness", "curve", "dynamics"))

    def to_json(self) -> dict:
        tip = self.tip
        ref = None if tip.alpha is None else {"id": tip.alpha, "name": tip.alpha_name, "hash": tip.alpha_hash}
        return {
            "format": FORMAT, "name": self.name, "category": self.category,
            "tip": {"alpha": ref, "invert": tip.invert, "contrast": tip.contrast, "kreismaske": tip.kreismaske},
            "radius_percent": RADIUS_STEPS_PERCENT[self.radius_step], "opacity": self.opacity, "flow": self.flow,
            "hardness": self.hardness, "curve": self.curve, "dynamics": dataclasses.asdict(self.dynamics),
        }

    @classmethod
    def from_json(cls, raw: object, id_prefix: str, builtin: bool, path: Path | None) -> "BrushPreset":
        """A preset from its JSON (ValueError with the reason when it is not one)."""
        if not isinstance(raw, dict):
            raise ValueError("keine Pinsel-Datei (ein JSON-Objekt erwartet)")
        if raw.get("format") != FORMAT:
            raise ValueError(f"fremdes Format {raw.get('format')!r} (erwartet {FORMAT!r})")
        unknown = sorted(set(raw) - _TOP_KEYS)
        if unknown:
            raise ValueError(f"unbekannte Felder {unknown}")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("ohne Namen")
        category = raw.get("category", UNSORTED)
        if not isinstance(category, str):
            raise ValueError("die Kategorie ist kein Text")
        tip_raw = raw.get("tip") or {}
        if not isinstance(tip_raw, dict) or set(tip_raw) - _TIP_KEYS:
            raise ValueError(f"ungültige Spitze {tip_raw!r}")
        ref = tip_raw.get("alpha")
        if ref is not None and not (isinstance(ref, dict) and isinstance(ref.get("id"), str)):
            raise ValueError("der Alpha-Verweis braucht {\"id\", \"name\", \"hash\"}")
        tip = TipSettings(
            alpha=None if ref is None else ref["id"],
            kreismaske=bool(tip_raw.get("kreismaske", False)),
            invert=bool(tip_raw.get("invert", False)),
            contrast=float(tip_raw.get("contrast", 0.0)),
            alpha_name=None if ref is None else (ref.get("name") or None),
            alpha_hash=None if ref is None else (ref.get("hash") or None),
        )
        dyn_raw = raw.get("dynamics") or {}
        if not isinstance(dyn_raw, dict) or set(dyn_raw) - _DYNAMICS_KEYS:
            raise ValueError(f"unbekannte Strich-Felder {sorted(set(dyn_raw) - _DYNAMICS_KEYS)}")
        dynamics = StrokeDynamics(**dyn_raw)  # ValueError outside its ranges
        radius = raw.get("radius_percent", RADIUS_STEPS_PERCENT[BrushSettings().radius_step])
        if not isinstance(radius, (int, float)) or not math.isfinite(radius) or radius <= 0:
            raise ValueError(f"ungültiger Radius {radius!r}")
        defaults = BrushSettings()
        brush = BrushSettings(radius_step=nearest_radius_step(radius), opacity=raw.get("opacity", defaults.opacity),
                              flow=raw.get("flow", defaults.flow), hardness=raw.get("hardness", defaults.hardness),
                              curve=raw.get("curve", defaults.curve), tip=tip, dynamics=dynamics)  # ValueError
        name = name.strip()
        return cls.from_brush(f"{id_prefix}:{slug(name)}", name, category.strip() or UNSORTED, brush, builtin, path)


# -- the library -------------------------------------------------------------------------------------------------------


class PaintLibrary:
    """Built-in and user alphas and presets (module docstring). Scans lazily; `refresh` forgets the scans."""

    def __init__(self, user_dir: Path | None = None, builtin_dir: Path = BUILTIN_DIR,
                 cache_bytes: int = CACHE_BYTES) -> None:
        self.user_dir = None if user_dir is None else Path(user_dir)
        self.builtin_dir = Path(builtin_dir)
        self.cache_bytes = cache_bytes
        #: why files were skipped at the last scan ("<file>: <reason>")
        self.problems: list[str] = []
        self._alphas: dict[str, AlphaEntry] | None = None
        self._presets: dict[str, BrushPreset] | None = None
        self._meta: dict | None = None
        self._cache: OrderedDict[tuple, alpha_api.AlphaImage] = OrderedDict()
        self._cached_bytes = 0
        self._hashes: dict[str, str] = {}
        #: dropped user files' (id, pixels) by (path, mtime, size): a rescan does not decode them again
        self._dropped: dict[tuple, tuple[str, np.ndarray]] = {}
        #: thumbnails (THUMB² uint8 grey) by alpha id
        self._thumbs: dict[str, np.ndarray] = {}

    # -- scanning ------------------------------------------------------------------------------------------------

    def refresh(self) -> None:
        self._alphas = None
        self._presets = None
        self._meta = None
        self.problems = []

    @property
    def writable(self) -> bool:
        return self.user_dir is not None

    def _require_user(self) -> Path:
        if self.user_dir is None:
            raise LibraryError("kein Benutzerordner für Pinsel und Alphas (~/.mirai_bastel/paint/)")
        return self.user_dir

    def _scan_alphas(self) -> dict[str, AlphaEntry]:
        if self._alphas is not None:
            return self._alphas
        entries: dict[str, AlphaEntry] = {}
        for alpha_id, (name, _make) in alpha_api.TEST_ALPHAS.items():
            entries[alpha_id] = AlphaEntry(alpha_id, name, TEST_CATEGORIES.get(alpha_id, TEST_CATEGORY), "test")
        root = self.builtin_dir / "alphas"
        index = {}
        if (root / "index.json").is_file():
            try:
                index = json.loads((root / "index.json").read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                self.problems.append(f"alphas/index.json: {exc}")
        if root.is_dir():
            for path in sorted(root.glob("*/*.png")):
                key = f"{path.parent.name}/{path.stem}"
                meta = index.get(key, {}) if isinstance(index, dict) else {}
                name = meta.get("name") or path.stem.replace("_", " ").capitalize()
                category = CATEGORIES.get(path.parent.name, path.parent.name.capitalize())
                entries[f"builtin:{key}"] = AlphaEntry(f"builtin:{key}", name, category, "builtin", path,
                                                       meta.get("hash"))
        meta = self._library_meta()["alphas"]
        if self.user_dir is not None and (self.user_dir / "alphas").is_dir():
            for path in sorted((self.user_dir / "alphas").glob("*.png")):
                match = _HASHED.match(path.name)
                if match:
                    digest, stem = match.group("hash"), match.group("slug")
                else:
                    try:
                        digest = self._dropped_file(path)[0]
                    except (OSError, ValueError) as exc:
                        self.problems.append(f"alphas/{path.name}: {exc}")
                        continue
                    stem = path.stem
                alpha_id = f"user:{digest}"
                if alpha_id in entries:
                    continue  # the same pixels twice (a copy under another name): one alpha
                info = meta.get(alpha_id, {})
                name = info.get("name") or (re.sub(r"[_\-]+", " ", stem).strip() or "Alpha")
                entries[alpha_id] = AlphaEntry(alpha_id, name, info.get("category") or UNSORTED, "user", path, digest)
        self._alphas = entries
        return entries

    def _dropped_file(self, path: Path) -> tuple[str, np.ndarray]:
        """A PNG dropped into the user folder: normalised with the suggested mode (cached by path, mtime, size)."""
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        hit = self._dropped.get(key)
        if hit is None:
            rgba = read_image_rgba(path)
            mode, _invert = suggest(rgba)
            pixels = import_pixels(rgba, mode)
            hit = self._dropped[key] = (alpha_api.pixel_hash(pixels), pixels)
        return hit

    def alphas(self) -> list[AlphaEntry]:
        return list(self._scan_alphas().values())

    def alpha_entry(self, alpha_id: str | None) -> AlphaEntry | None:
        return None if alpha_id is None else self._scan_alphas().get(alpha_id)

    # -- pixels, the cache ----------------------------------------------------------------------------------------

    def pixels(self, entry: AlphaEntry) -> np.ndarray:
        """The entry's normalised uint8 grey (read, not cached: `alpha` caches the image)."""
        if entry.source == "test":
            return alpha_api.generated_alpha(entry.id).pixels
        assert entry.path is not None
        if entry.source == "user" and not _HASHED.match(entry.path.name):
            return self._dropped_file(entry.path)[1]
        rgba = read_image_rgba(entry.path)
        return np.ascontiguousarray(rgba[..., 0])  # a grey PNG (R = G = B)

    def hash_of(self, entry: AlphaEntry) -> str:
        if entry.hash is not None:
            return entry.hash
        digest = self._hashes.get(entry.id)
        if digest is None:
            digest = self._hashes[entry.id] = alpha_api.pixel_hash(self.pixels(entry))
        return digest

    def alpha(self, alpha_id: str | None, invert: bool = False, contrast: float = 0.0) -> alpha_api.AlphaImage | None:
        """The decoded alpha (with invert / contrast applied), cached (LRU by bytes); None when unknown or unreadable."""
        entry = self.alpha_entry(alpha_id)
        if entry is None:
            return None
        key = (entry.id, bool(invert), round(float(contrast), 4))
        image = self._cache.get(key)
        if image is not None:
            self._cache.move_to_end(key)
            return image
        base_key = (entry.id, False, 0.0)
        base = self._cache.get(base_key)
        if base is None:
            if entry.source == "test":
                base = alpha_api.generated_alpha(entry.id)
            else:
                try:
                    base = alpha_api.AlphaImage.from_pixels(entry.id, entry.name, self.pixels(entry))
                except (OSError, ValueError) as exc:
                    self.problems.append(f"{entry.name}: {exc}")
                    return None
            self._store(base_key, base)
        image = alpha_api.shaped(base, bool(invert), float(contrast))
        if image is not base:
            self._store(key, image)
        return image

    @staticmethod
    def _bytes(image: alpha_api.AlphaImage) -> int:
        return sum(level.nbytes for level in image.mips)

    def _store(self, key: tuple, image: alpha_api.AlphaImage) -> None:
        self._cache[key] = image
        self._cached_bytes += self._bytes(image)
        while self._cached_bytes > self.cache_bytes and len(self._cache) > 1:
            _key, old = self._cache.popitem(last=False)
            self._cached_bytes -= self._bytes(old)

    @property
    def cached_bytes(self) -> int:
        return self._cached_bytes

    def _forget(self, alpha_id: str) -> None:
        for key in [k for k in self._cache if k[0] == alpha_id]:
            self._cached_bytes -= self._bytes(self._cache.pop(key))
        self._hashes.pop(alpha_id, None)

    # -- thumbnails (§6.6) ----------------------------------------------------------------------------------------

    def _thumb_path(self, entry: AlphaEntry) -> Path | None:
        if entry.source != "user" or self.user_dir is None:
            return None
        return self.user_dir / "alphas" / THUMB_DIR / f"{self.hash_of(entry)}.png"

    @staticmethod
    def make_thumbnail(image: alpha_api.AlphaImage) -> np.ndarray:
        return np.clip(np.rint(alpha_api.fitted(image, THUMB) * 255.0), 0, 255).astype(np.uint8)

    def thumbnail(self, alpha_id: str) -> np.ndarray | None:
        """The alpha fitted into THUMB² (uint8 grey), without reading the full image when it can: a user alpha's
        thumbnail is a small file beside it (`alphas/thumbs/<hash>.png`, written at the import, else made once - a
        1024² PNG takes ~60 ms to decode [C], its thumbnail file < 1 ms); kept in memory. None: unknown/unreadable."""
        thumb = self._thumbs.get(alpha_id)
        if thumb is not None:
            return thumb
        entry = self.alpha_entry(alpha_id)
        if entry is None:
            return None
        path = self._thumb_path(entry)
        if path is not None and path.is_file():
            try:
                thumb = np.ascontiguousarray(read_image_rgba(path)[..., 0])
            except (OSError, ValueError):
                thumb = None
        if thumb is None or thumb.shape != (THUMB, THUMB):
            if entry.source == "test":
                image = alpha_api.generated_alpha(entry.id)
            else:
                try:
                    image = alpha_api.AlphaImage.from_pixels(entry.id, entry.name, self.pixels(entry))
                except (OSError, ValueError):
                    return None  # (not into the LRU: a thumbnail must not push the painting alphas out)
            thumb = self.make_thumbnail(image)
            if path is not None:
                self._write_thumb(path, thumb)
        self._thumbs[alpha_id] = thumb
        return thumb

    @staticmethod
    def _write_thumb(path: Path, thumb: np.ndarray) -> None:
        try:
            _atomic_write(path, encode_grey_png(thumb))
        except OSError:
            pass  # a thumbnail is derived data: made again next time

    # -- references --------------------------------------------------------------------------------------------------

    def resolve(self, tip: TipSettings) -> AlphaEntry | None:
        """The tip's alpha: by id, else by hash (the same pixels elsewhere), else by name; None = missing (or round)."""
        if tip.alpha is None:
            return None
        entries = self._scan_alphas()
        entry = entries.get(tip.alpha)
        if entry is not None:
            return entry
        if tip.alpha_hash:
            for candidate in entries.values():
                if candidate.hash == tip.alpha_hash:
                    return candidate
            for candidate in entries.values():
                if candidate.hash is None and self.hash_of(candidate) == tip.alpha_hash:
                    return candidate
        if tip.alpha_name:
            for candidate in entries.values():
                if candidate.name == tip.alpha_name:
                    return candidate
        return None

    def image_for(self, tip: TipSettings) -> alpha_api.AlphaImage | None:
        """What the tip paints with: its resolved alpha shaped by invert / contrast; None = the round tip (or missing)."""
        entry = self.resolve(tip)
        return None if entry is None else self.alpha(entry.id, tip.invert, tip.contrast)

    def tip(self, alpha_id: str | None, base: TipSettings | None = None) -> TipSettings:
        """A tip on `alpha_id` with its reference filled in (name, hash); the other values from `base`."""
        base = base or TipSettings()
        if alpha_id is None:
            return dataclasses.replace(base, alpha=None, alpha_name=None, alpha_hash=None)
        entry = self.alpha_entry(alpha_id)
        if entry is None:
            raise LibraryError(f"unbekanntes Alpha {alpha_id!r}")
        return dataclasses.replace(base, alpha=entry.id, alpha_name=entry.name, alpha_hash=self.hash_of(entry))

    # -- user alphas -------------------------------------------------------------------------------------------------

    def import_alpha(self, pixels: np.ndarray, name: str, category: str = UNSORTED) -> tuple[AlphaEntry, bool]:
        """Write a normalised alpha to the user folder; (entry, created). The same pixels already there: that alpha
        (created False, its name kept)."""
        root = self._require_user()
        pixels = np.ascontiguousarray(pixels, dtype=np.uint8)
        if pixels.ndim != 2 or min(pixels.shape) < IMPORT_MIN or max(pixels.shape) > IMPORT_MAX:
            raise LibraryError(f"kein normalisiertes Alpha ({pixels.shape})")
        digest = alpha_api.pixel_hash(pixels)
        alpha_id = f"user:{digest}"
        existing = self.alpha_entry(alpha_id)
        if existing is not None:
            return existing, False
        for entry in self._scan_alphas().values():  # the same pixels built in: that one
            if entry.builtin and self.hash_of(entry) == digest:
                return entry, False
        name = name.strip() or "Alpha"
        path = root / "alphas" / f"{slug(name)}_{digest}.png"
        _atomic_write(path, encode_grey_png(pixels))
        thumb = self.make_thumbnail(alpha_api.AlphaImage.from_pixels(alpha_id, name, pixels))
        self._write_thumb(root / "alphas" / THUMB_DIR / f"{digest}.png", thumb)
        self._thumbs[alpha_id] = thumb
        meta = self._library_meta()
        meta["alphas"][alpha_id] = {"name": name, "category": category.strip() or UNSORTED}
        self._write_meta()
        self._alphas = None
        return self.alpha_entry(alpha_id), True

    def _user_alpha(self, alpha_id: str) -> AlphaEntry:
        entry = self.alpha_entry(alpha_id)
        if entry is None:
            raise LibraryError(f"unbekanntes Alpha {alpha_id!r}")
        if entry.builtin:
            raise LibraryError(f"„{entry.name}“ ist eingebaut (nur lesen)")
        self._require_user()
        return entry

    def rename_alpha(self, alpha_id: str, name: str) -> AlphaEntry:
        entry = self._user_alpha(alpha_id)
        if not name.strip():
            raise LibraryError("ein Name braucht Buchstaben oder Ziffern")
        self._library_meta()["alphas"].setdefault(alpha_id, {})["name"] = name.strip()
        self._write_meta()
        self._alphas = None
        return self.alpha_entry(entry.id)

    def set_alpha_category(self, alpha_id: str, category: str) -> AlphaEntry:
        entry = self._user_alpha(alpha_id)
        self._library_meta()["alphas"].setdefault(alpha_id, {})["category"] = category.strip() or UNSORTED
        self._write_meta()
        self._alphas = None
        return self.alpha_entry(entry.id)

    def delete_alpha(self, alpha_id: str) -> None:
        """Remove a user alpha's file (presets that use it keep their reference and paint round: "Alpha fehlt")."""
        entry = self._user_alpha(alpha_id)
        assert entry.path is not None
        entry.path.unlink(missing_ok=True)
        if self.user_dir is not None and entry.hash is not None:
            (self.user_dir / "alphas" / THUMB_DIR / f"{entry.hash}.png").unlink(missing_ok=True)
        self._thumbs.pop(alpha_id, None)
        meta = self._library_meta()
        meta["alphas"].pop(alpha_id, None)
        if alpha_id in meta["favourites"]:
            meta["favourites"].remove(alpha_id)
        self._write_meta()
        self._forget(alpha_id)
        self._alphas = None

    # -- presets -----------------------------------------------------------------------------------------------------

    def _scan_presets(self) -> dict[str, BrushPreset]:
        if self._presets is not None:
            return self._presets
        presets: dict[str, BrushPreset] = {}
        names: set[str] = set()
        sources = [(self.builtin_dir / "brushes", "builtin", True)]
        if self.user_dir is not None:
            sources.append((self.user_dir / "brushes", "user", False))
        for directory, prefix, builtin in sources:
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.json")):
                where = f"brushes/{path.name}" if builtin else f"~/brushes/{path.name}"
                try:
                    preset = BrushPreset.from_json(json.loads(path.read_text(encoding="utf-8")), prefix, builtin, path)
                    if preset.name.lower() in names:
                        raise ValueError(f"der Name {preset.name!r} ist vergeben")
                except (OSError, ValueError, TypeError) as exc:  # json.JSONDecodeError is a ValueError
                    self.problems.append(f"{where}: {exc}")
                    continue
                if preset.id in presets:
                    self.problems.append(f"{where}: der Name {preset.name!r} ist vergeben")
                    continue
                names.add(preset.name.lower())
                presets[preset.id] = preset
        self._presets = presets
        return presets

    def presets(self) -> list[BrushPreset]:
        return list(self._scan_presets().values())

    def preset(self, preset_id: str | None) -> BrushPreset | None:
        return None if preset_id is None else self._scan_presets().get(preset_id)

    def _name_free(self, name: str, except_id: str | None = None) -> None:
        name = name.strip()
        if not name:
            raise LibraryError("ein Pinsel braucht einen Namen")
        stem = slug(name)
        for preset in self._scan_presets().values():
            if preset.id == except_id:
                continue
            if preset.name.lower() == name.lower() or (not preset.builtin and preset.id == f"user:{stem}"):
                raise LibraryError(f"der Name „{preset.name}“ ist vergeben")

    def _write_preset(self, preset: BrushPreset) -> BrushPreset:
        root = self._require_user()
        path = root / "brushes" / f"{slug(preset.name)}.json"
        preset = dataclasses.replace(preset, id=f"user:{slug(preset.name)}", builtin=False, path=path)
        _atomic_write(path, (json.dumps(preset.to_json(), indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        self._presets = None
        return preset

    def save_preset(self, preset_id: str, brush: BrushSettings) -> BrushPreset:
        """Overwrite a user preset with `brush`'s values (built-ins: refused - "Speichern als")."""
        preset = self.preset(preset_id)
        if preset is None:
            raise LibraryError(f"unbekannter Pinsel {preset_id!r}")
        if preset.builtin:
            raise LibraryError(f"„{preset.name}“ ist eingebaut - „Speichern als …“ legt eine eigene Kopie an")
        return self._write_preset(BrushPreset.from_brush(preset.id, preset.name, preset.category, brush))

    def save_preset_as(self, name: str, category: str, brush: BrushSettings) -> BrushPreset:
        self._require_user()
        self._name_free(name)
        return self._write_preset(BrushPreset.from_brush("", name.strip(), category.strip() or UNSORTED, brush))

    def free_name(self, name: str) -> str:
        """`name`, or "<name> 2", "<name> 3" … - the first one not taken."""
        candidate, n = name.strip(), 1
        while True:
            try:
                self._name_free(candidate)
                return candidate
            except LibraryError:
                n += 1
                candidate = f"{name.strip()} {n}"

    def duplicate_preset(self, preset_id: str) -> BrushPreset:
        preset = self.preset(preset_id)
        if preset is None:
            raise LibraryError(f"unbekannter Pinsel {preset_id!r}")
        self._require_user()
        copy = dataclasses.replace(preset, name=self.free_name(f"{preset.name} Kopie"))
        return self._write_preset(copy)

    def rename_preset(self, preset_id: str, name: str) -> BrushPreset:
        preset = self._user_preset(preset_id)
        self._name_free(name, except_id=preset.id)
        renamed = self._write_preset(dataclasses.replace(preset, name=name.strip()))
        if renamed.path != preset.path and preset.path is not None:
            preset.path.unlink(missing_ok=True)
        meta = self._library_meta()
        if preset.id in meta["favourites"] and renamed.id != preset.id:
            meta["favourites"][meta["favourites"].index(preset.id)] = renamed.id
            self._write_meta()
        self._presets = None
        return renamed

    def set_preset_category(self, preset_id: str, category: str) -> BrushPreset:
        preset = self._user_preset(preset_id)
        return self._write_preset(dataclasses.replace(preset, category=category.strip() or UNSORTED))

    def delete_preset(self, preset_id: str) -> None:
        preset = self._user_preset(preset_id)
        if preset.path is not None:
            preset.path.unlink(missing_ok=True)
        meta = self._library_meta()
        if preset_id in meta["favourites"]:
            meta["favourites"].remove(preset_id)
            self._write_meta()
        self._presets = None

    def _user_preset(self, preset_id: str) -> BrushPreset:
        preset = self.preset(preset_id)
        if preset is None:
            raise LibraryError(f"unbekannter Pinsel {preset_id!r}")
        if preset.builtin:
            raise LibraryError(f"„{preset.name}“ ist eingebaut (nur lesen)")
        self._require_user()
        return preset

    # -- favourites, view state ----------------------------------------------------------------------------------

    def _library_meta(self) -> dict:
        if self._meta is not None:
            return self._meta
        meta = {"favourites": [], "alphas": {}, "keep_size": False}
        path = None if self.user_dir is None else self.user_dir / "library.json"
        if path is not None and path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict) or raw.get("format") != LIBRARY_FORMAT:
                    raise ValueError(f"fremdes Format {raw.get('format') if isinstance(raw, dict) else raw!r}")
                if isinstance(raw.get("favourites"), list):
                    meta["favourites"] = [f for f in raw["favourites"] if isinstance(f, str)]
                if isinstance(raw.get("alphas"), dict):
                    meta["alphas"] = {k: v for k, v in raw["alphas"].items() if isinstance(v, dict)}
                meta["keep_size"] = bool(raw.get("keep_size", False))
            except (OSError, ValueError) as exc:
                self.problems.append(f"~/library.json: {exc} (neu angelegt beim nächsten Speichern)")
        self._meta = meta
        return meta

    def _write_meta(self) -> None:
        if self.user_dir is None:
            return
        meta = self._library_meta()
        data = {"format": LIBRARY_FORMAT, **meta}
        _atomic_write(self.user_dir / "library.json",
                      (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    def favourite(self, item_id: str) -> bool:
        return item_id in self._library_meta()["favourites"]

    def set_favourite(self, item_id: str, on: bool) -> None:
        favourites = self._library_meta()["favourites"]
        if on and item_id not in favourites:
            favourites.append(item_id)
        elif not on and item_id in favourites:
            favourites.remove(item_id)
        else:
            return
        self._write_meta()

    @property
    def keep_size(self) -> bool:
        return bool(self._library_meta()["keep_size"])

    def set_keep_size(self, on: bool) -> None:
        meta = self._library_meta()
        if meta["keep_size"] != bool(on):
            meta["keep_size"] = bool(on)
            self._write_meta()
