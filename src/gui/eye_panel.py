"""The eye panel (AD-033 §6): the view state of the eye preview and the selected eyes' values. Button "Auge" in the
toggle bar, closed by default. Every control calls the `Application` path of `gui.eye_model` with its refusals; a
slider applies on release (one Undo step per change, not one per drag frame). No keys (D-L9).
"""

from __future__ import annotations

from . import eye_model as em
from viewport.eye_pass import REFLECTIONS, REFRACTIONS


class EyePanel:
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
