"""Das Panel „Kamera“ (AD-042 §8.2; Layout `PROVISIONAL`): Likeness-Kameras der Sitzung, Objektiv, Foto, Ansicht.

Rechte Spalte (wie „Bone“ und „Auge“), Knopf „Kamera [+]“ in der Leiste. Die Logik (Zeilen, Bereiche, Freigaben) steht
in `likeness_model`; das Panel zeichnet nur und ruft `Application` - es hält keinen Zustand außer dem Auf/Zu von „Mehr“.
Regler wirken sofort (kein Undo); die Kameras werden mit der Szene gespeichert (Q-LC-3, `view.likeness`).
"""

from __future__ import annotations

from mirai.viewport import lens as lens_math

from . import likeness_model as lm
from .file_browser_model import ALL_FILTER, IMAGE_FILTER

_CURRENT = (1.0, 0.8, 0.43, 1.0)  # wie das Edit-Objekt im Outliner
_PLAIN = (0.88, 0.9, 0.94, 1.0)


class LikenessPanel:
    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer
        self.more = False  # „Mehr“ auf/zu: reiner Panel-Zustand

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
        st = lm.state(app)
        self._cameras(st)
        if not st.has_camera:
            imgui.text_disabled(lm.HINT_SESSION)
            return
        self._lens(st)
        self._photo(st)
        self._view(st)
        changed, self.more = imgui.checkbox(lm.MORE, self.more)
        self.layer._remember("likeness_more", 0)
        imgui.text_disabled(lm.HINT_FOCAL)
        imgui.text_disabled(lm.HINT_SESSION)

    def _cameras(self, st: lm.PanelState) -> None:
        imgui, app, layer = self.imgui, self.app, self.layer
        imgui.separator_text("Kameras")
        for row in st.rows:
            imgui.push_id(f"cam{row.index}")
            color = imgui.ImVec4(*(_CURRENT if row.active else _PLAIN))
            if imgui.small_button(row.look_label):
                lm.toggle_row(app, row.index)
            layer._remember("likeness_look", row.index)
            imgui.same_line()
            if imgui.small_button(lm.DELETE):
                app.delete_likeness_camera(row.index)
                imgui.pop_id()
                break
            imgui.same_line()
            label = f"{row.name}  ◉" if row.viewing else row.name
            outcome = layer._name_cell(("c", row.index), label, row.name, row.active, color)
            if outcome == "click":
                app.set_active_likeness_camera(row.index)
            elif isinstance(outcome, tuple):
                app.rename_likeness_camera(row.index, outcome[1])
            imgui.pop_id()
        if imgui.button(lm.NEW):
            app.new_likeness_camera()
        layer._remember("likeness_new", 0)

    def _lens(self, st: lm.PanelState) -> None:
        imgui, app = self.imgui, self.app
        lens, index = st.lens, app.likeness.active
        imgui.separator_text("Objektiv")
        lo, hi = lm.FOCAL_RANGE
        changed, value = imgui.slider_float("Brennweite (mm)", lens.focal_mm, lo, hi, "%.1f",
                                            imgui.SliderFlags_.logarithmic)
        if changed:
            app.set_likeness_lens(index, focal_mm=value)
        for i, mm in enumerate(lm.FOCAL_BUTTONS):
            if i:
                imgui.same_line()
            if imgui.small_button(str(mm)):
                app.set_likeness_lens(index, focal_mm=float(mm))
            self.layer._remember("likeness_focal", mm)
        if imgui.begin_combo("Sensor", lens.sensor_label):
            for key in lens_math.SENSOR_KEYS:
                if imgui.selectable(lm.SENSOR_LABELS[key], key == lens.sensor)[0]:
                    app.set_likeness_lens(index, sensor=key)
            imgui.end_combo()
        if self.more:
            if imgui.begin_combo("Einpassen", lm.FIT_LABELS[lens.fit]):
                for fit in lens_math.FITS:
                    if imgui.selectable(lm.FIT_LABELS[fit], fit == lens.fit)[0]:
                        app.set_likeness_lens(index, fit=fit)
                imgui.end_combo()
            changed, w = imgui.input_float("Breite (mm)", lens.sensor_w_mm, 0.0, 0.0, "%.2f",
                                           imgui.InputTextFlags_.enter_returns_true)
            if changed:
                app.set_likeness_lens(index, sensor_w_mm=w)
            changed, h = imgui.input_float("Höhe (mm)", lens.sensor_h_mm, 0.0, 0.0, "%.2f",
                                           imgui.InputTextFlags_.enter_returns_true)
            if changed:
                app.set_likeness_lens(index, sensor_h_mm=h)
            changed, near = imgui.input_float("Clip nah", lens.clip_near, 0.0, 0.0, "%.3f",
                                              imgui.InputTextFlags_.enter_returns_true)
            if changed:
                app.set_likeness_clip(index, near=near)
            changed, far = imgui.input_float("Clip fern", lens.clip_far, 0.0, 0.0, "%.1f",
                                             imgui.InputTextFlags_.enter_returns_true)
            if changed:
                app.set_likeness_clip(index, far=far)
            changed, rand = imgui.slider_float("Rand", st.overscan, *lm.OVERSCAN_RANGE, "%.2f")
            if changed:
                app.set_likeness_view(overscan=rand)

    def _photo(self, st: lm.PanelState) -> None:
        imgui, app = self.imgui, self.app
        photo, index = st.photo, app.likeness.active
        imgui.separator_text("Foto")
        imgui.begin_disabled(photo.pending)
        if imgui.button(lm.LOAD):
            self.browse(index)
        imgui.end_disabled()
        imgui.same_line()
        changed, on = imgui.checkbox(lm.SHOW, st.photo_shown)
        if changed:
            app.set_likeness_view(photo_shown=on)
        changed, value = imgui.slider_float("Deckkraft", st.photo_opacity, 0.0, 1.0, "%.2f")
        if changed:
            app.set_likeness_view(photo_opacity=value)
        imgui.text_disabled(photo.line)
        if self.more and photo.loaded:
            if imgui.small_button(lm.TURN):
                app.turn_likeness_photo(index)
            imgui.same_line()
            if imgui.small_button(lm.REMOVE):
                app.remove_likeness_photo(index)

    def _view(self, st: lm.PanelState) -> None:
        imgui, app = self.imgui, self.app
        imgui.separator_text("Ansicht")
        changed, on = imgui.checkbox(lm.FIX, st.fixed)
        if changed:
            app.set_likeness_fixed(app.likeness.active, on)
        self.layer._remember("likeness_fix", 0)
        if imgui.is_item_hovered():
            imgui.set_tooltip(lm.FIX_HINT)
        imgui.text_disabled(f"Abstand {st.distance_line}")
        imgui.text_disabled(f"Bildwinkel {st.angles_line}")

    def browse(self, index: int) -> None:
        """„Laden …“: the file browser for the photo; the pick loads it in two steps (status line first)."""
        menus = getattr(self.layer, "menus", None)
        if menus is None:
            self.app.set_status("Datei-Browser: nicht verfügbar")
            return
        menus.browser.request("image", "Foto wählen", (IMAGE_FILTER, ALL_FILTER),
                              lambda path: self.app.load_likeness_photo(index, path))
