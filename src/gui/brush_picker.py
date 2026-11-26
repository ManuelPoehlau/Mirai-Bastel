"""The brush picker popup and the alpha import card (AD-037 §14 Phase 4c; proposal 2026-11-25 §7; the logic is
`gui.brush_picker_model`).

- **Picker** (an ImGui popup, closed by Esc or a click outside): tabs Pinsel / Alphas; a category combo, a search field,
  "Größe behalten" (Pinsel tab); a grid of thumbnails, favourites first, a name tooltip; right-click: Favorit,
  Duplizieren, Umbenennen, Kategorie, Löschen (the user's own only). On the Alphas tab "Alpha importieren ..." opens the
  file browser (purpose `image`), then the import card.
- **Import card** (its own window: the file browser closed the popup): the live preview, the source mode (Alphakanal /
  Luminanz / Luminanz × Alphakanal, preselected, P-26), Invertieren, Kontrast, name, category, the border warning;
  "Importieren" writes it and sets it as the tip.
- **Textures** (§6.6): made from `thumbnail_pixels` within `THUMB_BUDGET_S` per frame (a button with the name until
  then), kept while the room is open, freed by `release` (the room closed). No GL: no textures, the names stay.
"""

from __future__ import annotations

import time

from mirai.paint import library as lib

from . import brush_picker_model as bm
from .file_browser_model import ALL_FILTER, IMAGE_FILTER

POPUP_ID = "Pinsel-Auswahl###brush_picker"
CARD_TITLE = "Alpha importieren###alpha_import"


class BrushPicker:
    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer
        self.tab = bm.TAB_BRUSHES
        self.category = {bm.TAB_BRUSHES: bm.ALL, bm.TAB_ALPHAS: bm.ALL}
        self.search = ""
        self.is_open = False
        self._request: str | None = None
        #: the tab the next frame selects (the popup opened on it)
        self._select_tab: str | None = None
        #: GL textures by their thumbnail key (`thumbnail_key`), kept while the room is open
        self.textures: dict[tuple, object] = {}
        #: slot -> the key its one texture shows now (`texture(..., slot=)`)
        self._slots: dict[str, tuple] = {}
        self._no_gl = False
        #: the context menu's text fields (rename / category) by item id
        self.edit_buf: dict[tuple[str, str], str] = {}
        #: the import card's draft and its preview texture
        self.draft: lib.ImportDraft | None = None
        self.card_rect: tuple | None = None
        self._preview = None
        self._preview_key = None
        self.message = ""
        #: (seconds, thumbnails made) of each frame that made thumbnails - the §9 gate's measurement
        self.thumb_frames: list[tuple[float, int]] = []
        self._frame_start = 0.0

    # -- textures ----------------------------------------------------------------------------------------------

    def _make_texture(self, rgba):
        if self._no_gl:
            return None
        try:
            from pyglet import image

            h, w = rgba.shape[:2]
            return image.ImageData(w, h, "RGBA", rgba[::-1].tobytes(), pitch=w * 4).get_texture()  # pyglet: bottom-up
        except Exception:  # no GL context (headless tests): names instead of pictures
            self._no_gl = True
            return None

    def texture(self, key: tuple, make, budgeted: bool = True, slot: str | None = None):
        """The texture for `key` (made from `make()` on first use; within the frame's budget when `budgeted`). A `slot`
        holds one texture that follows a changing key (the brush's preview while a slider moves): the old one is
        freed."""
        texture = self.textures.get(key)
        if texture is not None or self._no_gl:
            return texture
        if budgeted and time.perf_counter() - self._frame_start > bm.THUMB_BUDGET_S:
            return None
        texture = self._make_texture(make())
        if texture is not None:
            self.textures[key] = texture
            if slot is not None:
                old = self._slots.get(slot)
                if old is not None and old != key and old in self.textures:
                    try:
                        self.textures.pop(old).delete()
                    except Exception:
                        pass
                self._slots[slot] = key
        return texture

    def release(self) -> None:
        """Free every texture (the room closed); the card closes."""
        for texture in self.textures.values():
            try:
                texture.delete()
            except Exception:
                pass
        self.textures.clear()
        self._slots.clear()
        self._set_preview(None)
        self.draft = None
        self.card_rect = None
        self.is_open = False

    def _set_preview(self, rgba) -> None:
        if self._preview is not None:
            try:
                self._preview.delete()
            except Exception:
                pass
        self._preview = None if rgba is None else self._make_texture(rgba)

    # -- opening -----------------------------------------------------------------------------------------------

    def open(self, tab: str = bm.TAB_BRUSHES) -> None:
        self._request = tab

    def draw(self) -> None:
        """Called inside the Paint Room window every frame: the popup (when open) and the import card."""
        imgui = self.imgui
        self._frame_start = time.perf_counter()
        made_before = len(self.textures)
        if self._request is not None:
            self.tab = self._select_tab = self._request
            self._request = None
            imgui.open_popup(POPUP_ID)
        self.is_open = bool(imgui.begin_popup(POPUP_ID))
        if self.is_open:
            self._popup()
            imgui.end_popup()
        made = len(self.textures) - made_before
        if made > 0:
            self.thumb_frames.append((time.perf_counter() - self._frame_start, made))
        self._card()

    def _popup(self) -> None:
        imgui, app = self.imgui, self.app
        if imgui.begin_tab_bar("##picker_tabs"):
            for tab in bm.TABS:
                flags = imgui.TabItemFlags_.set_selected if self._request_tab_pending(tab) else 0
                opened, _ = imgui.begin_tab_item(tab, None, flags)
                if opened:
                    self.tab = tab
                    self._tab(tab)
                    imgui.end_tab_item()
            imgui.end_tab_bar()
        problems = app.paint_library.problems
        if problems:
            imgui.text_disabled(f"{len(problems)} Datei(en) übersprungen")
            if imgui.is_item_hovered():
                imgui.set_tooltip("\n".join(problems[-12:]))

    def _request_tab_pending(self, tab: str) -> bool:
        if self._select_tab == tab:
            self._select_tab = None
            return True
        return False

    def _tab(self, tab: str) -> None:
        imgui, app = self.imgui, self.app
        brushes = tab == bm.TAB_BRUSHES
        everything = bm.preset_items(app) if brushes else bm.alpha_items(app)
        category = self.category[tab]
        imgui.set_next_item_width(150.0)
        if imgui.begin_combo("##category", category):
            for row in bm.categories(everything):
                if imgui.selectable(row, row == category)[0]:
                    self.category[tab] = category = row
            imgui.end_combo()
        imgui.same_line()
        imgui.set_next_item_width(150.0)
        _, self.search = imgui.input_text_with_hint("##search", "Suchen", self.search)
        if brushes:
            imgui.same_line()
            changed, on = imgui.checkbox("Größe behalten", app.paint_library.keep_size)
            if changed:
                app.set_paint_keep_size(on)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Beim Wechseln den aktuellen Radius behalten (P-20)")
        else:
            imgui.same_line()
            imgui.begin_disabled(not app.paint_library.writable)
            if imgui.button("Alpha importieren ..."):
                self.browse()
            imgui.end_disabled()
        items = bm.preset_items(app, category, self.search) if brushes else bm.alpha_items(app, category, self.search)
        if not items:
            imgui.text_disabled("Nichts gefunden")
        for row in bm.rows(items):
            for i, item in enumerate(row):
                if i:
                    imgui.same_line()
                self._cell(item)

    def _cell(self, item: bm.PickerItem) -> None:
        imgui, app = self.imgui, self.app
        imgui.push_id(f"{item.kind}:{item.id}")
        imgui.begin_group()
        texture = self.texture(bm.thumbnail_key(app, item), lambda: bm.thumbnail_pixels(app, item))
        size = imgui.ImVec2(bm.THUMB, bm.THUMB)
        if item.current:  # the chosen one: its frame in the highlight colour (the thumbnail itself is opaque)
            imgui.push_style_color(imgui.Col_.button, imgui.get_color_u32(imgui.ImVec4(0.85, 0.65, 0.25, 1.0)))
        if texture is not None:
            clicked = imgui.image_button("##thumb", imgui.ImTextureRef(texture.id), size)
        else:
            clicked = imgui.button(item.name[:9] + "##thumb", imgui.ImVec2(bm.THUMB + 8, bm.THUMB + 8))
        if item.current:
            imgui.pop_style_color()
        if imgui.is_item_hovered():
            imgui.set_tooltip(item.tooltip)
        self._context(item)
        label = item.label if len(item.label) <= 11 else item.label[:10] + "."
        imgui.text_disabled(label) if not item.current else imgui.text(label)
        imgui.end_group()
        imgui.pop_id()
        if clicked:
            if item.kind == "preset":
                app.select_paint_preset(item.id)
                imgui.close_current_popup()
            else:
                app.set_paint_tip(item.id)

    def _context(self, item: bm.PickerItem) -> None:
        imgui, app = self.imgui, self.app
        if not imgui.begin_popup_context_item("##ctx"):
            return
        imgui.text_disabled(item.name)
        if imgui.menu_item("Favorit", "", item.favourite)[0]:
            app.set_paint_favourite(item.id, not item.favourite)
        writable = app.paint_library.writable
        if item.kind == "preset" and imgui.menu_item("Duplizieren", "", False, writable)[0]:
            app.duplicate_paint_preset(item.id)
        own = writable and not item.builtin
        for field, label in (("name", "Umbenennen"), ("category", "Kategorie")):
            imgui.begin_disabled(not own)
            key = (field, item.id)
            current = item.name if field == "name" else item.category
            imgui.set_next_item_width(160.0)
            entered, text = imgui.input_text(label, self.edit_buf.get(key, current),
                                             imgui.InputTextFlags_.enter_returns_true)
            self.edit_buf[key] = text
            imgui.end_disabled()
            if entered and own and text.strip() and text.strip() != current:
                self.edit_buf.pop(key, None)
                self._edit(item, field, text)
                imgui.close_current_popup()
        if imgui.menu_item("Löschen", "", False, own)[0]:
            if item.kind == "preset":
                app.delete_paint_preset(item.id)
            else:
                app.delete_paint_alpha(item.id)
        if item.builtin:
            imgui.text_disabled("eingebaut: nur lesen")
        imgui.end_popup()

    def _edit(self, item: bm.PickerItem, field: str, text: str) -> None:
        app = self.app
        if item.kind == "preset":
            (app.rename_paint_preset if field == "name" else app.set_paint_preset_category)(item.id, text)
        else:
            (app.rename_paint_alpha if field == "name" else app.set_paint_alpha_category)(item.id, text)

    # -- the import card ---------------------------------------------------------------------------------------

    def browse(self) -> None:
        """„Alpha importieren ...“: the file browser (purpose `image`); the pick opens the card."""
        menus = getattr(self.layer, "menus", None)
        if menus is None:
            self.app.set_status("Datei-Browser: nicht verfügbar")
            return
        menus.browser.request("image", "Alpha importieren", (IMAGE_FILTER, ALL_FILTER), self.open_card)

    def open_card(self, path) -> bool:
        draft, self.message = lib.open_import(path)
        self.app.set_status(self.message)
        self.draft = draft
        self._preview_key = None
        return draft is not None

    def _card(self) -> None:
        draft = self.draft
        if draft is None:
            self.card_rect = None
            return
        imgui = self.imgui
        imgui.set_next_window_pos(imgui.ImVec2(360.0, 80.0), imgui.Cond_.first_use_ever)
        _, keep = imgui.begin(CARD_TITLE, True, imgui.WindowFlags_.always_auto_resize
                              | imgui.WindowFlags_.no_saved_settings | imgui.WindowFlags_.no_collapse)
        self._card_body(draft)
        pos, size = imgui.get_window_pos(), imgui.get_window_size()
        self.card_rect = (pos.x, pos.y, size.x, size.y)
        imgui.end()
        if keep is False:
            self.close_card()

    def close_card(self) -> None:
        self.draft = None
        self.card_rect = None
        self._set_preview(None)

    def _card_body(self, draft: lib.ImportDraft) -> None:
        imgui, app = self.imgui, self.app
        key = (draft.mode, draft.invert, round(draft.contrast, 3), id(draft))
        if key != self._preview_key:
            self._preview_key = key
            self._set_preview(bm.import_preview_rgba(draft))
        h, w = draft.rgba.shape[:2]
        scale = 220.0 / max(w, h)
        if self._preview is not None:
            imgui.image(imgui.ImTextureRef(self._preview.id), imgui.ImVec2(w * scale, h * scale))
        imgui.text_disabled(bm.import_note(draft))
        if draft.border_warning:
            imgui.text_colored(imgui.ImVec4(0.95, 0.75, 0.35, 1.0), "Rand nicht schwarz")
            if imgui.is_item_hovered():
                imgui.set_tooltip(bm.BORDER_WARNING)
        for i, (mode, label) in enumerate(bm.MODE_ROWS):
            if i:
                imgui.same_line()
            if imgui.radio_button(label, draft.mode == mode):
                draft.mode = mode
        changed, on = imgui.checkbox("Invertieren", draft.invert)
        if changed:
            draft.invert = on
        imgui.set_next_item_width(170.0)
        changed, value = imgui.slider_float("Kontrast", float(draft.contrast), -1.0, 1.0, "%.2f")
        if changed:
            draft.contrast = float(value)
        imgui.set_next_item_width(170.0)
        _, draft.name = imgui.input_text("Name", draft.name)
        imgui.set_next_item_width(170.0)
        _, draft.category = imgui.input_text("Kategorie", draft.category)
        try:
            valid = draft.preview() is not None
        except lib.LibraryError:
            valid = False
        imgui.begin_disabled(not valid or not draft.name.strip())
        imported = imgui.button("Importieren") and app.import_paint_alpha(draft) is not None
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Abbrechen") or imported:
            self.close_card()
