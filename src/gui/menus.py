"""Menüleiste (Datei), SPACE-Menü und Namensdialoge als ImGui (AD-030 §12, Manu 2026-11-07, `PROVISIONAL`).

Die Logik bleibt in den Modulen `SceneFiles`, `ObjFiles` und den Application-Methoden; hier steht nur die Anzeige.
`Services` bündelt, was `main.py` zuverlässig hat (Dateien, OBJ, Beispielszenen, Add-Mesh), damit dieses Modul weder
pyglet noch `examples/` kennt.

    Datei:  Neu | Öffnen > (Szenen) | Speichern (Strg+S) | Speichern unter... | Importieren > (OBJ) | Exportieren...
    SPACE:  Add + > (Grundkörper, Basehead, Baseman) | Textur an/aus | Szene laden (Shift+Klick: als Referenz)

„Speichern“ einer neuen Szene (noch keine Datei) fragt wie „Speichern unter“ nach dem Namen. Während ein Popup offen
ist, gehört dem Layer die ganze Maus (`popup_open`): ein Klick daneben schließt es, und er erreicht den Viewport nicht.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

#: Anzeigename -> Registry-Asset der beiden Basis-Körper im Add-Menü (`examples/loaders/assets.py`).
BASE_MESHES = (("Basehead", "head_basemesh"), ("Baseman", "man_with_shoes_basemesh"))


@dataclass
class Services:
    files: object  # SceneFiles
    obj_files: object  # ObjFiles
    primitives: Callable[[], tuple[str, ...]]
    add_primitive: Callable[[str], bool]
    add_base: Callable[[str], bool]  # Registry-Asset als neues, bearbeitbares Objekt
    scenes: Callable[[], tuple[str, ...]]  # `cube` + Registry-Assets
    load_scene: Callable[[str], bool]
    add_reference: Callable[[str], bool]
    zbrush: object | None = None  # ZBrushBridge


class Menus:
    def __init__(self, imgui, app, services: Services) -> None:
        self.imgui, self.app, self.sv = imgui, app, services
        self.popup_open = False
        self._request: str | None = None
        self._space_at = (0.0, 0.0)
        self.name_buf = ""
        self._focus = False
        self._close = False

    def close_all(self) -> None:
        self._close = True

    # -- Anforderungen (von Tasten und Menüpunkten; geöffnet wird im nächsten Frame an der richtigen Stelle) ------
    def open_space(self, x: float, y: float) -> None:
        """`x`, `y` in imgui-Koordinaten (oben links)."""
        self._space_at, self._request = (x, y), "space"

    def open_save_as(self) -> None:
        self.name_buf, self._focus, self._request = self.sv.files.suggested_name(), True, "save_as"

    def open_export(self) -> None:
        self.name_buf, self._focus, self._request = self.sv.obj_files.suggested_name(), True, "export"

    def save(self) -> None:
        """Strg+S / Datei > Speichern: in die aktuelle Datei, bei einer neuen Szene mit Namensdialog."""
        if self.sv.files.current is None:
            self.open_save_as()
        else:
            self.sv.files.save()

    # -- Leiste ------------------------------------------------------------------------------------------------
    def bar(self) -> tuple[float, float, float, float]:
        """Die Menüleiste am oberen Rand; gibt ihr Rechteck (x, y, w, h) zurück."""
        imgui, sv = self.imgui, self.sv
        rect = (0.0, 0.0, 0.0, 0.0)
        if imgui.begin_main_menu_bar():
            if imgui.begin_menu("Datei"):
                if imgui.menu_item("Neu", "", False)[0]:
                    sv.files.new()
                if imgui.begin_menu("Öffnen"):
                    files = sv.files.files()
                    for path in files:
                        if imgui.menu_item(_stem(path), "", False)[0]:
                            sv.files.load(path)
                    if not files:
                        imgui.text_disabled("(keine Szenen)")
                    imgui.end_menu()
                if imgui.menu_item("Speichern", "Strg+S", False)[0]:
                    self.save()
                if imgui.menu_item("Speichern unter...", "", False)[0]:
                    self.open_save_as()
                imgui.separator()
                if imgui.begin_menu("Importieren"):
                    files = sv.obj_files.files()
                    for path in files:
                        if imgui.menu_item(path.stem, "", False)[0]:
                            sv.obj_files.import_file(path)
                    if not files:
                        imgui.text_disabled("(keine OBJ-Dateien)")
                    imgui.end_menu()
                if imgui.menu_item("Exportieren...", "", False)[0]:
                    self.open_export()
                imgui.end_menu()
            size = imgui.get_window_size()
            rect = (0.0, 0.0, size.x, size.y)
            imgui.end_main_menu_bar()
        return rect

    # -- Popups (nach allen Fenstern aufrufen) -------------------------------------------------------------------
    def popups(self) -> None:
        imgui = self.imgui
        request, self._request = self._request, None
        if self._close:
            self._close = False
            imgui.internal.close_popup_to_level(0, True)
        if request == "space":
            imgui.open_popup("##space")
        elif request == "save_as":
            imgui.open_popup("Speichern unter")
        elif request == "export":
            imgui.open_popup("OBJ exportieren")
        self._space()
        files = self.sv.files
        self._name_dialog("Speichern unter", files.path_for, files.save_as)
        obj = self.sv.obj_files
        self._name_dialog("OBJ exportieren", obj.path_for, obj.export)
        self.popup_open = imgui.is_popup_open(
            "", imgui.PopupFlags_.any_popup_id | imgui.PopupFlags_.any_popup_level
        )

    def _space(self) -> None:
        imgui, sv, app = self.imgui, self.sv, self.app
        imgui.set_next_window_pos(imgui.ImVec2(*self._space_at), imgui.Cond_.appearing)
        if not imgui.begin_popup("##space"):
            return
        if imgui.begin_menu("Add +"):
            for name in sv.primitives():
                if imgui.menu_item(name, "", False)[0]:
                    sv.add_primitive(name)
            imgui.separator()
            for label, asset in BASE_MESHES:
                if imgui.menu_item(label, "", False)[0]:
                    sv.add_base(asset)
            imgui.end_menu()
        shows_texture = any(obj.texture is not None for obj in app.scene.objects.values())
        if shows_texture:
            on = app.display.show_texture
            if imgui.menu_item("Textur anzeigen", "", on)[0]:
                app.toggle_texture_display()
        imgui.separator()
        imgui.text_disabled("Szene laden (Shift+Klick: als Referenz)")
        for name in sv.scenes():
            if imgui.menu_item(name, "", False)[0]:
                (sv.add_reference if imgui.get_io().key_shift else sv.load_scene)(name)
        imgui.end_popup()

    def _name_dialog(self, title: str, path_for, commit) -> None:
        """Der Namensdialog (Speichern unter, OBJ exportieren): Enter oder OK übernimmt, Esc oder Abbrechen schließt."""
        imgui = self.imgui
        center = imgui.get_main_viewport().get_center()
        imgui.set_next_window_pos(center, imgui.Cond_.appearing, imgui.ImVec2(0.5, 0.5))
        opened = imgui.begin_popup_modal(
            title, None, imgui.WindowFlags_.always_auto_resize | imgui.WindowFlags_.no_saved_settings
        )
        if not (opened[0] if isinstance(opened, tuple) else opened):
            return
        if self._focus:
            imgui.set_keyboard_focus_here()
            self._focus = False
        imgui.text("Name")
        imgui.set_next_item_width(260)
        entered, self.name_buf = imgui.input_text(
            "##name", self.name_buf, imgui.InputTextFlags_.enter_returns_true | imgui.InputTextFlags_.auto_select_all
        )
        path = path_for(self.name_buf)
        if path is None:
            imgui.text_colored(imgui.ImVec4(1.0, 0.8, 0.43, 1.0), "Name fehlt")
        else:
            note = f"{path.name} (existiert, wird überschrieben)" if path.exists() else path.name
            imgui.text_disabled(note)
        if (imgui.button("OK") or entered) and path is not None:
            commit(self.name_buf)
            imgui.close_current_popup()
        imgui.same_line()
        if imgui.button("Abbrechen") or imgui.is_key_pressed(imgui.Key.escape, False):
            imgui.close_current_popup()
        imgui.end_popup()


def _stem(path) -> str:
    name = path.name
    return name[: -len(".mirai.json")] if name.endswith(".mirai.json") else path.stem
