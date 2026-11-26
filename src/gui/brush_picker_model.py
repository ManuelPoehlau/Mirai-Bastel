"""The brush picker's logic (AD-037 §14 Phase 4c; proposal 2026-11-25 §7; AD-030: headless, `brush_picker` draws).

The picker has two tabs, **Pinsel** (presets) and **Alphas**, each with a category filter (Alle, Favoriten, the
categories present), a search over name and category, and a grid of thumbnails, favourites first. Choosing a preset
sets the brush (`Application.select_paint_preset`); choosing an alpha sets the current brush's tip (the brush becomes
"geändert"). The brush row above the panel (`brush_row`) and the tip area (`tip_row`) are read here too.

**Thumbnails** (§6.6): `thumbnail_pixels` makes a `THUMB`² RGBA image (the alpha white on the panel's dark, fitted with
its aspect) from the library's alpha; a preset shows its tip's alpha (shaped by invert / contrast), the round tip its
falloff disc, a missing alpha a reddish disc. The GL textures are the panel's (made within a per-frame time budget,
`THUMB_BUDGET_S`, freed when the room closes). All values `PROVISIONAL`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from mirai.paint import library as lib
from mirai.paint.brush import BrushSettings, falloff

TAB_BRUSHES = "Pinsel"
TAB_ALPHAS = "Alphas"
TABS = (TAB_BRUSHES, TAB_ALPHAS)
ALL = "Alle"
FAVOURITES = "Favoriten"
#: the thumbnail's side and the brush row's preview (px)
THUMB = 64
PREVIEW = 32
#: thumbnails per grid row
COLUMNS = 5
#: `PROVISIONAL`: the time a frame may spend making thumbnails (the rest come in the next frames; §9 gate: the first
#: open <= 150 ms, no per-frame cost afterwards)
THUMB_BUDGET_S = 0.012
#: the panel's background behind a thumbnail and the paint colour of a thumbnail (RGB)
BACKGROUND = (34, 37, 46)
INK = (235, 238, 244)
MISSING_INK = (220, 110, 100)
NO_PRESET = "Eigener Pinsel"
MISSING = "Alpha fehlt"


@dataclass(frozen=True)
class PickerItem:
    kind: str  # "preset" | "alpha"
    id: str
    name: str
    category: str
    favourite: bool
    builtin: bool
    current: bool
    missing: bool = False

    @property
    def label(self) -> str:
        """The grid's caption: a favourite marked with "*" (the panel font has no star glyph)."""
        return ("* " if self.favourite else "") + self.name

    @property
    def tooltip(self) -> str:
        parts = [self.name, self.category, "eingebaut (nur lesen)" if self.builtin else "eigener"]
        if self.favourite:
            parts.append("Favorit")
        if self.missing:
            parts.append(MISSING + " - malt rund")
        return "\n".join(parts)


def matches(item: PickerItem, category: str, search: str) -> bool:
    if category == FAVOURITES and not item.favourite:
        return False
    if category not in (ALL, FAVOURITES) and item.category != category:
        return False
    needle = search.strip().lower()
    return not needle or needle in item.name.lower() or needle in item.category.lower()


def _ordered(items: list[PickerItem], category: str, search: str) -> tuple[PickerItem, ...]:
    shown = [item for item in items if matches(item, category, search)]
    return tuple(sorted(shown, key=lambda item: not item.favourite))  # stable: favourites first, else library order


def preset_items(app, category: str = ALL, search: str = "") -> tuple[PickerItem, ...]:
    library = app.paint_library
    current = app.paint_preset.id if app.paint_preset is not None else None
    items = [PickerItem("preset", p.id, p.name, p.category, library.favourite(p.id), p.builtin, p.id == current,
                        p.tip.alpha is not None and library.resolve(p.tip) is None) for p in library.presets()]
    return _ordered(items, category, search)


def alpha_items(app, category: str = ALL, search: str = "") -> tuple[PickerItem, ...]:
    library = app.paint_library
    current = library.resolve(app.paint_brush.tip)
    items = [PickerItem("alpha", e.id, e.name, e.category, library.favourite(e.id), e.builtin,
                        current is not None and e.id == current.id) for e in library.alphas()]
    return _ordered(items, category, search)


def categories(items: tuple[PickerItem, ...]) -> tuple[str, ...]:
    """The filter's rows: Alle, Favoriten, then each category present (in first-seen order)."""
    seen: list[str] = []
    for item in items:
        if item.category not in seen:
            seen.append(item.category)
    return (ALL, FAVOURITES, *seen)


def rows(items: tuple[PickerItem, ...], columns: int = COLUMNS) -> tuple[tuple[PickerItem, ...], ...]:
    return tuple(items[i:i + columns] for i in range(0, len(items), columns))


# -- the brush row and the tip area (proposal §7 areas 1 and 2) -----------------------------------------------------


@dataclass(frozen=True)
class BrushRow:
    name: str
    category: str
    favourite: bool
    changed: bool
    #: "Speichern" overwrites (a user preset); a built-in or no preset only "Speichern als"
    can_save: bool
    preset_id: str | None


def brush_row(app) -> BrushRow:
    preset = app.paint_preset
    if preset is None:
        return BrushRow(NO_PRESET, "", False, False, False, None)
    changed = app.paint_brush_changed
    return BrushRow(preset.name, preset.category, app.paint_library.favourite(preset.id), changed,
                    changed and not preset.builtin and app.paint_library.writable, preset.id)


@dataclass(frozen=True)
class TipRow:
    label: str
    alpha_id: str | None
    missing: bool
    invert: bool
    contrast: float
    kreismaske: bool

    @property
    def text(self) -> str:
        return f"{MISSING}: {self.label} (malt rund)" if self.missing else self.label


def tip_row(app) -> TipRow:
    tip = app.paint_brush.tip
    return TipRow(tip.label(), tip.alpha, app.paint_alpha_missing, tip.invert, tip.contrast, tip.kreismaske)


def brush_label(row: BrushRow) -> str:
    """The brush row's text: name, category, favourite, the "geändert" marker."""
    text = ("* " if row.favourite else "") + row.name
    if row.category:
        text += f"  ({row.category})"
    if row.changed:
        text += "  - geändert"
    return text


# -- thumbnails ----------------------------------------------------------------------------------------------------


def _paint(value: np.ndarray, ink=INK) -> np.ndarray:
    """(n, n) coverage in [0, 1] -> (n, n, 4) uint8 RGBA, the ink over the background, opaque."""
    v = np.clip(value, 0.0, 1.0)[..., None]
    rgb = np.asarray(BACKGROUND, np.float32) * (1.0 - v) + np.asarray(ink, np.float32) * v
    out = np.empty(value.shape + (4,), dtype=np.uint8)
    out[..., :3] = np.rint(rgb).astype(np.uint8)
    out[..., 3] = 255
    return out


def _grid(size: int) -> tuple[np.ndarray, np.ndarray]:
    c = (np.arange(size, dtype=np.float32) + 0.5) / size * 2.0 - 1.0  # -1 .. 1, pixel centres
    y, x = np.meshgrid(c, c, indexing="ij")
    return x, y


def alpha_thumbnail(image, size: int = THUMB) -> np.ndarray:
    """An `AlphaImage` fitted into `size`² with its aspect (`alpha.fitted`), painted."""
    from mirai.paint.alpha import fitted

    return _paint(fitted(image, size))


def round_thumbnail(brush: BrushSettings, size: int = THUMB, ink=INK) -> np.ndarray:
    """The round tip's falloff disc (hardness, curve)."""
    x, y = _grid(size)
    distance = np.hypot(x, y) / 0.94  # a small margin
    return _paint(falloff(distance, brush.hardness, brush.curve).astype(np.float32), ink)


def _library_thumb(app, alpha_id: str, invert: bool = False, contrast: float = 0.0) -> np.ndarray | None:
    """The library's THUMB² thumbnail (no full decode), shaped by invert / contrast, painted."""
    thumb = app.paint_library.thumbnail(alpha_id)
    if thumb is None:
        return None
    if invert or contrast:
        from mirai.paint.alpha import contrast_lut

        thumb = contrast_lut(invert, contrast)[thumb]
    return _paint(thumb.astype(np.float32) / 255.0)


def thumbnail_pixels(app, item: PickerItem, size: int = THUMB) -> np.ndarray:
    library = app.paint_library
    if item.kind == "alpha":
        pixels = _library_thumb(app, item.id)
        return pixels if pixels is not None else round_thumbnail(BrushSettings(), size, MISSING_INK)
    preset = library.preset(item.id)
    if preset is None:
        return round_thumbnail(BrushSettings(), size, MISSING_INK)
    brush = preset.apply(BrushSettings())
    if brush.tip.round:
        return round_thumbnail(brush, size)
    entry = library.resolve(brush.tip)
    pixels = None if entry is None else _library_thumb(app, entry.id, brush.tip.invert, brush.tip.contrast)
    return pixels if pixels is not None else round_thumbnail(brush, size, MISSING_INK)


def current_thumbnail(app, size: int = PREVIEW) -> np.ndarray:
    """The brush row's preview: the current brush's tip as it paints now."""
    brush = app.paint_brush
    if brush.tip.round:
        return round_thumbnail(brush, size)
    image = app.paint_library.image_for(brush.tip)
    return alpha_thumbnail(image, size) if image is not None else round_thumbnail(brush, size, MISSING_INK)


def thumbnail_key(app, item: PickerItem) -> tuple:
    """What a thumbnail shows (a texture is remade when it changes): a preset by its tip and falloff values."""
    if item.kind == "alpha":
        entry = app.paint_library.alpha_entry(item.id)
        return ("alpha", item.id, None if entry is None else entry.path)
    preset = app.paint_library.preset(item.id)
    if preset is None:
        return ("preset", item.id)
    tip = preset.tip
    resolved = app.paint_library.resolve(tip)
    return ("preset", tip.alpha if resolved is None else resolved.id, tip.invert, tip.contrast,
            preset.hardness, preset.curve, resolved is None and tip.alpha is not None)


def current_key(app) -> tuple:
    brush = app.paint_brush
    tip = brush.tip
    resolved = None if tip.round else app.paint_library.resolve(tip)
    return ("current", None if resolved is None else resolved.id, tip.invert, tip.contrast, brush.hardness,
            brush.curve, not tip.round and resolved is None)


# -- the import card (proposal §6.3) --------------------------------------------------------------------------------

MODE_ROWS = tuple((mode, lib.MODE_LABELS[mode]) for mode in lib.MODES)
BORDER_WARNING = "Der Rand ist nicht schwarz: der Stempel zeigt eine eckige Kante (Invertieren? anderes Bild?)"


def import_note(draft: lib.ImportDraft) -> str:
    """The card's line under the preview: the result's size and the suggestion it started from."""
    try:
        h, w = draft.preview().shape
        size = f"{w} x {h} px"
    except lib.LibraryError as exc:
        return str(exc)
    mode, invert = draft.suggested
    return f"{size}, Vorschlag: {lib.MODE_LABELS[mode]}" + (", invertiert" if invert else "")


def import_preview_rgba(draft: lib.ImportDraft) -> np.ndarray | None:
    """The card's live preview as RGBA (white = paint), or None when the result is refused (empty)."""
    try:
        grey = draft.preview()
    except lib.LibraryError:
        return None
    return _paint(grey.astype(np.float32) / 255.0)


__all__ = ["ALL", "COLUMNS", "FAVOURITES", "PREVIEW", "TABS", "THUMB", "BrushRow", "PickerItem", "TipRow",
           "alpha_items", "alpha_thumbnail", "brush_label", "brush_row", "categories", "current_key",
           "current_thumbnail", "import_note", "import_preview_rgba", "matches", "preset_items", "round_thumbnail",
           "rows", "thumbnail_key", "thumbnail_pixels", "tip_row"]
