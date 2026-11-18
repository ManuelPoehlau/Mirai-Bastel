"""Der Datei-Browser als ImGui-Fenster (Manu 2026-11-18, `PROVISIONAL`): Öffnen, Importieren und Bild-Laden wählen die
Datei in einer Explorer-Ansicht des ganzen Systems statt aus „den letzten 10“ oder per getipptem Pfad. Der Zustand
liegt in `gui.file_browser_model` (headless getestet); hier steht nur die Anzeige.

    [<] [>] [^]  Dieser PC > C: > Users > ...   (jeder Teil ist ein Knopf)
    [Pfad (Enter) ........................]   [Suchen ...........]
    Orte       | Name              Geändert           Größe     (Klick auf die Kopfzeile sortiert)
    Home       | Meshes/
    Desktop    | kopf.obj          18.11.2026 09:12   2.1 MB      (Doppelklick: Ordner öffnen / Datei wählen)
    C:\\        |
    [Datei: kopf.obj ......]  [Dateityp v]  [ ] Versteckte   [Öffnen] [Abbrechen]

Ein Aufrufer ruft `request(...)` (Menüpunkt, Knopf neben einem Pfadfeld) und `draw()` jeden Frame (nach allen Fenstern,
wie die anderen Popups in `Menus.popups`). Gewählt: `on_pick(Path)`; der Ordner der Wahl wird je Zweck gemerkt
(`LastDirs`), der nächste Browser dieses Zwecks beginnt dort. Esc oder „Abbrechen“ ändert nichts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from .file_browser_model import (
    BrowserModel,
    Entry,
    FileFilter,
    LastDirs,
    Place,
    default_places,
    format_size,
    format_time,
    list_drives,
)

TITLE_ID = "###file_browser"
FOLDER_COLOUR = (0.95, 0.80, 0.45, 1.0)
WARN_COLOUR = (1.0, 0.8, 0.43, 1.0)
COLUMNS = ("name", "date", "size")  # Tabellenspalte -> Sortierschlüssel (`SORT_KEYS`)


class FileBrowser:
    def __init__(self, imgui, last_dirs: LastDirs | None = None, extra_places: tuple[tuple[str, Path], ...] = (),
                 drives: Callable[[], list[Path]] = list_drives) -> None:
        self.imgui = imgui
        self.last_dirs = last_dirs or LastDirs()
        self.extra_places = extra_places
        self.drives = drives
        self.model: BrowserModel | None = None
        self.places: list[Place] = []
        self._request: tuple | None = None
        self._purpose = ""
        self._title = ""
        self._on_pick: Callable[[Path], object] | None = None
        self._path_buf = ""
        self._name_buf = ""
        self._synced: tuple[Path | None, Path | None] = (None, None)
        self.is_open = False

    # -- Anforderung -------------------------------------------------------------------------------------------------
    def request(self, purpose: str, title: str, filters: tuple[FileFilter, ...], on_pick: Callable[[Path], object],
                default_dir: Path | None = None) -> None:
        """Öffnet den Browser im nächsten Frame. `purpose` (`scene`, `mesh`, `image`) wählt den gemerkten Startordner;
        `default_dir`, wenn es noch keinen gibt (oder es ihn nicht mehr gibt)."""
        self._request = (purpose, title, tuple(filters), on_pick, default_dir)

    def _open(self) -> None:
        purpose, title, filters, on_pick, default_dir = self._request
        self._request = None
        self._purpose, self._title, self._on_pick = purpose, title, on_pick
        self.places = default_places(extra=self.extra_places)
        self.model = BrowserModel(filters=filters, start=self.last_dirs.get(purpose, default_dir), drives=self.drives)
        self._synced = (None, None)
        self._name_buf = ""
        self.imgui.open_popup(TITLE_ID)
        self.is_open = True

    def pick(self, path: Path) -> None:
        """Die Wahl: Ordner merken, Rückruf, Fenster zu (der Rückruf meldet Fehler selbst in der Statuszeile)."""
        self.last_dirs.remember(self._purpose, path.parent)
        callback, self._on_pick = self._on_pick, None
        self.imgui.close_current_popup()
        self.is_open = False
        if callback is not None:
            callback(path)

    def cancel(self) -> None:
        self._on_pick = None
        self.imgui.close_current_popup()
        self.is_open = False

    # -- Zeichnen ----------------------------------------------------------------------------------------------------
    def draw(self) -> None:
        imgui = self.imgui
        if self._request is not None:
            self._open()
        if not self.is_open:
            return
        center = imgui.get_main_viewport().get_center()
        imgui.set_next_window_pos(center, imgui.Cond_.appearing, imgui.ImVec2(0.5, 0.5))
        imgui.set_next_window_size(imgui.ImVec2(820.0, 520.0), imgui.Cond_.appearing)
        imgui.push_style_color(imgui.Col_.popup_bg, imgui.ImVec4(0.075, 0.08, 0.10, 0.98))  # die Liste muss lesbar sein
        opened = imgui.begin_popup_modal(f"{self._title}{TITLE_ID}", None, imgui.WindowFlags_.no_saved_settings)
        imgui.pop_style_color()
        if not (opened[0] if isinstance(opened, tuple) else opened):
            if not imgui.is_popup_open(TITLE_ID):  # von außen geschlossen (z. B. `Menus.close_all`)
                self.is_open = False
            return
        model = self.model
        self._toolbar(model)
        self._address(model)
        footer = imgui.get_frame_height_with_spacing() * 2.2
        avail = imgui.get_content_region_avail()
        imgui.begin_child("##places", imgui.ImVec2(150.0, avail.y - footer), imgui.ChildFlags_.borders)
        self._places(model)
        imgui.end_child()
        imgui.same_line()
        imgui.begin_child("##files", imgui.ImVec2(0.0, avail.y - footer), imgui.ChildFlags_.borders)
        picked = self._files(model)
        imgui.end_child()
        picked = self._footer(model) or picked
        if model.error:
            imgui.text_colored(imgui.ImVec4(*WARN_COLOUR), model.error)
        if imgui.is_key_pressed(imgui.Key.escape, False) and not imgui.is_any_item_active():
            self.cancel()
        elif picked is not None:
            self.pick(picked)
        imgui.end_popup()

    def _toolbar(self, model: BrowserModel) -> None:
        imgui = self.imgui
        for ident, direction, enabled, action in (
            ("##back", imgui.Dir.left, model.can_back(), model.back),
            ("##forward", imgui.Dir.right, model.can_forward(), model.forward),
            ("##up", imgui.Dir.up, model.can_up(), model.up),
        ):
            imgui.begin_disabled(not enabled)
            if imgui.arrow_button(ident, direction):
                action()
            imgui.end_disabled()
            imgui.same_line()
        if imgui.small_button("Neu laden"):
            model.refresh()
        for label, path in model.breadcrumbs():
            imgui.same_line()
            imgui.text_disabled(">")
            imgui.same_line()
            if imgui.small_button(f"{label}##crumb{path}"):
                model.go(path)
                break  # die Liste der Teile ist veraltet

    def _address(self, model: BrowserModel) -> None:
        imgui = self.imgui
        here = (model.directory, model.selected)
        if here != self._synced:  # der Ordner oder die Wahl hat gewechselt: die Felder folgen
            if here[0] != self._synced[0]:
                self._path_buf = "" if model.directory is None else str(model.directory)
            if model.selected is not None:
                self._name_buf = model.selected.name
            self._synced = here
        imgui.set_next_item_width(imgui.get_content_region_avail().x - 230.0)
        entered, self._path_buf = imgui.input_text(
            "##path", self._path_buf, imgui.InputTextFlags_.enter_returns_true | imgui.InputTextFlags_.auto_select_all
        )
        if entered:
            self._submit(model, self._path_buf)
        imgui.same_line()
        imgui.set_next_item_width(220.0)
        _, model.query = imgui.input_text_with_hint("##query", "Suchen in diesem Ordner", model.query)

    def _submit(self, model: BrowserModel, text: str) -> Path | None:
        picked = model.submit(text)
        if picked is None:
            self._synced = (None, None)  # Feld neu füllen (aus dem neuen Ordner oder dem alten bei einem Fehler)
        return picked

    def _places(self, model: BrowserModel) -> None:
        imgui = self.imgui
        imgui.text_disabled("Orte")
        for place in self.places:
            if imgui.selectable(f"{place.label}##place", model.directory == place.path)[0]:
                model.go(place.path)
        imgui.separator()
        imgui.text_disabled("Laufwerke")
        for drive in self.drives():
            if imgui.selectable(f"{drive}##drive", model.directory == drive)[0]:
                model.go(drive)

    def _files(self, model: BrowserModel) -> Path | None:
        imgui = self.imgui
        flags = (imgui.TableFlags_.sortable | imgui.TableFlags_.resizable | imgui.TableFlags_.scroll_y
                 | imgui.TableFlags_.row_bg | imgui.TableFlags_.borders_inner_v)
        if not imgui.begin_table("##list", 3, flags):
            return None
        picked = None
        imgui.table_setup_column("Name", imgui.TableColumnFlags_.width_stretch | imgui.TableColumnFlags_.default_sort)
        imgui.table_setup_column("Geändert", imgui.TableColumnFlags_.width_fixed | imgui.TableColumnFlags_.prefer_sort_descending,
                                 125.0)
        imgui.table_setup_column("Größe", imgui.TableColumnFlags_.width_fixed, 70.0)
        imgui.table_setup_scroll_freeze(0, 1)
        imgui.table_headers_row()
        specs = imgui.table_get_sort_specs()
        if specs is not None and specs.specs_dirty and specs.specs_count > 0:
            spec = specs.get_specs(0)
            model.set_sort(COLUMNS[spec.column_index], spec.sort_direction == imgui.SortDirection.descending)
            specs.specs_dirty = False
        for entry in model.visible():
            picked = self._row(model, entry) or picked
        imgui.end_table()
        return picked

    def _row(self, model: BrowserModel, entry: Entry) -> Path | None:
        imgui = self.imgui
        picked = None
        imgui.table_next_row()
        imgui.table_next_column()
        if entry.is_dir:
            imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(*FOLDER_COLOUR))
        shown = entry.name if entry.drive else (entry.name + ("/" if entry.is_dir else ""))
        selected = not entry.is_dir and model.selected == entry.path
        clicked, _ = imgui.selectable(f"{shown}##{entry.path}", selected,
                                      imgui.SelectableFlags_.span_all_columns | imgui.SelectableFlags_.allow_double_click)
        if entry.is_dir:
            imgui.pop_style_color()
        if clicked:
            if imgui.is_mouse_double_clicked(0):
                picked = model.activate(entry)
            else:
                model.select(entry)
        if not entry.drive:
            imgui.table_next_column()
            imgui.text_disabled(format_time(entry.mtime))
            imgui.table_next_column()
            imgui.text_disabled("" if entry.is_dir else format_size(entry.size))
        return picked

    def _footer(self, model: BrowserModel) -> Path | None:
        imgui = self.imgui
        imgui.text("Datei")
        imgui.same_line()
        imgui.set_next_item_width(260.0)
        entered, self._name_buf = imgui.input_text(
            "##name", self._name_buf, imgui.InputTextFlags_.enter_returns_true | imgui.InputTextFlags_.auto_select_all
        )
        imgui.same_line()
        imgui.set_next_item_width(220.0)
        if imgui.begin_combo("##type", model.filter.label):
            for i, flt in enumerate(model.filters):
                if imgui.selectable(flt.label, i == model.filter_index)[0]:
                    model.filter_index = i
            imgui.end_combo()
        imgui.same_line()
        _, model.show_hidden = imgui.checkbox("Versteckte", model.show_hidden)
        imgui.same_line()
        picked = None
        ready = bool(self._name_buf.strip())
        imgui.begin_disabled(not ready)
        if imgui.button("Öffnen") or (entered and ready):
            picked = self._accept(model)
        imgui.end_disabled()
        imgui.same_line()
        if imgui.button("Abbrechen"):
            self.cancel()
        return picked

    def _accept(self, model: BrowserModel) -> Path | None:
        """„Öffnen“ / Enter im Namensfeld: die angeklickte Datei, sonst das Getippte (Name im Ordner, Pfad, Ordner)."""
        chosen = model.choice()
        if chosen is not None and chosen.name == self._name_buf.strip():
            return chosen
        return self._submit(model, self._name_buf)
