"""The eye panel (AD-033 §6): the view state of the eye preview and the selected eyes' values. Button "Auge" in the
toggle bar, closed by default. The "Blick" section sets where every eye looks (`mirai.eye_gaze`). Every control calls the `Application` path of `gui.eye_model` with its refusals; a
slider applies on release (one Undo step per change, not one per drag frame). No keys (D-L9).
"""

from __future__ import annotations

from . import eye_model as em
from viewport.eye_pass import REFLECTIONS, REFRACTIONS


class EyePanel:
    PAD_SIZE = (150.0, 96.0)  # the gaze pad in pixels (`PROVISIONAL`)

    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer
        self.image_buf = ""
        self._drag: dict = {}  # field -> value while a slider is held

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
        st = em.state(app)
        imgui.text_disabled("Ansicht (alle Augen, nicht gespeichert)")
        changed, on = imgui.checkbox("Vorschau", st.preview)
        if changed:
            em.set_view(app, preview=on)
        imgui.same_line()
        for refraction in REFRACTIONS:
            if imgui.radio_button(refraction, st.refraction == refraction):
                em.set_view(app, refraction=refraction)
            imgui.same_line()
        imgui.new_line()
        for reflection in REFLECTIONS:
            if imgui.radio_button(em.REFLECTION_LABELS[reflection], st.reflection == reflection):
                em.set_view(app, reflection=reflection)
            imgui.same_line()
        imgui.new_line()
        self._draw_gaze(st)
        imgui.separator()
        imgui.text_disabled(st.header)
        if not st.has_eyes:
            return
        spec = st.spec
        imgui.set_next_item_width(170.0)
        if imgui.begin_combo("Limbus", em.LEVEL_LABELS[spec.limbus_level]):
            for level, label in enumerate(em.LEVEL_LABELS):
                if imgui.selectable(label, level == spec.limbus_level)[0]:
                    em.set_value(app, "limbus_level", level)
            imgui.end_combo()
        for source in em.COLOUR_SOURCES:
            label = "Farbe: Shader" if source == "shader" else "Farbe: Iris-Außenring"
            if imgui.radio_button(label, spec.colour_source == source):
                em.set_value(app, "colour_source", source)
            imgui.same_line()
        imgui.new_line()
        changed, colour = imgui.color_edit3("Limbusfarbe", list(spec.limbal_colour))
        if imgui.is_item_deactivated_after_edit():
            em.set_value(app, "limbal_colour", tuple(float(c) for c in colour))
        changed, on = imgui.checkbox("Asymmetrie oben/unten", spec.asymmetry)
        if changed:
            em.set_value(app, "asymmetry", on)
        for field, label, lo, hi, fmt in em.SLIDERS:
            value = self._drag.get(field, getattr(spec, field))
            imgui.set_next_item_width(170.0)
            changed, value = imgui.slider_float(label, float(value), lo, hi, fmt)
            if changed:
                self._drag[field] = value
            if imgui.is_item_deactivated_after_edit():
                em.set_value(app, field, float(self._drag.pop(field, value)))
        imgui.separator()
        imgui.text_disabled(st.image_text)
        imgui.set_next_item_width(220.0)
        _, self.image_buf = imgui.input_text("##iris", self.image_buf)
        imgui.same_line()
        if imgui.small_button("Iris-Bild laden"):
            app.set_eye_iris_image(self.image_buf.strip().strip('"') or None)
        if spec is not None and st.eyes[0].texture is not None:
            if imgui.small_button("Bild entfernen"):
                app.set_eye_iris_image(None)

    def _draw_gaze(self, st: em.EyePanelState) -> None:
        """Where every eye looks (`mirai.eye_gaze`): the mode, the gaze pad (drag: the eyes look there, as seen facing
        them; double click: straight ahead) and the focus distance. View state, applied live."""
        imgui, app = self.imgui, self.app
        imgui.separator()
        imgui.text_disabled("Blick (alle Augen, nicht gespeichert)")
        if not st.scene_eyes:
            imgui.text_disabled("Kein Auge in der Szene")
            return
        for i, (mode, label) in enumerate(em.GAZE_LABELS.items()):
            if i % 2:
                imgui.same_line()
            if imgui.radio_button(label, st.gaze_mode == mode):
                em.set_gaze(app, mode=mode)
        width, height = self.PAD_SIZE
        imgui.invisible_button("##gaze_pad", imgui.ImVec2(width, height))
        a, b = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        cx, cy = (a.x + b.x) / 2, (a.y + b.y) / 2
        if imgui.is_item_active():
            mouse = imgui.get_io().mouse_pos
            em.set_gaze_pad(app, (mouse.x - cx) / (width / 2), (cy - mouse.y) / (height / 2))
        elif imgui.is_item_hovered() and imgui.is_mouse_double_clicked(0):
            em.set_gaze_pad(app, 0.0, 0.0)
        dl = imgui.get_window_draw_list()
        frame = imgui.get_color_u32(imgui.ImVec4(0.38, 0.4, 0.45, 1))
        dl.add_rect(a, b, frame, 3.0)
        dl.add_line(imgui.ImVec2(cx, a.y), imgui.ImVec2(cx, b.y), frame)
        dl.add_line(imgui.ImVec2(a.x, cy), imgui.ImVec2(b.x, cy), frame)
        dot = em.state(app).gaze_dot  # after a drag this frame: the new point
        if dot is not None:
            colour = imgui.get_color_u32(imgui.ImVec4(0.9, 0.92, 0.96, 1))
            dl.add_circle_filled(imgui.ImVec2(cx + dot[0] * width / 2, cy - dot[1] * height / 2), 4.0, colour)
        imgui.same_line()
        imgui.text_disabled("Pad ziehen:\nBlick wie von\nvorn gesehen\n(Doppelklick:\ngeradeaus)")
        lo, hi = em.GAZE_FOCUS_RANGE
        imgui.set_next_item_width(170.0)
        changed, focus = imgui.slider_float("Fokus-Abstand (Augenradien)", float(st.gaze_focus), lo, hi, "%.0f",
                                            imgui.SliderFlags_.logarithmic)
        if changed:
            em.set_gaze(app, focus=focus)
