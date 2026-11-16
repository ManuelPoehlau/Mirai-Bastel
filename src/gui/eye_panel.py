"""The compact eye panel "Auge" (AD-033 §6; Eye LookDev phase 2, Manu 2026-11-16 I-2) and the Eye Lab window (I-1).

The panel is the "Auge" button in the toggle bar, closed by default. It holds eyes on / off, preview and quality, gaze
mode and pad, pupil, look preset and "open in Eye Lab". The Eye Lab window (`EyeLabPanel`, drawn while
`Application.eye_lab_open`) holds every other value: anatomy, limbus, refraction, reflection, gaze focus, iris image,
framing, isolation and saving presets. Every control calls the `Application` path of `gui.eye_model` with its
refusals. A slider previews live while it is held (`preview_eye`, no Undo) and commits on release (one Undo step per
change). No keys (D-L9).
"""

from __future__ import annotations

from . import eye_model as em
from viewport.eye_pass import REFLECTIONS, REFRACTIONS, TIERS

TIER_HINT = "Heute zeichnen beide Stufen gleich; ab Phase 3 lässt 'schnell' die neuen Zusatzterme weg."


class _Sliders:
    """Live-preview sliders shared by the panel and the lab: held -> `preview_eye`, released -> `set_eye`."""

    def __init__(self, imgui, app) -> None:
        self.imgui, self.app = imgui, app
        self.drag: dict = {}  # field -> value while a slider is held

    def slider(self, spec, field: str, label: str, lo: float, hi: float, fmt: str, width: float = 170.0) -> None:
        imgui, app = self.imgui, self.app
        value = self.drag.get(field, getattr(spec, field))
        imgui.set_next_item_width(width)
        changed, value = imgui.slider_float(label, float(value), lo, hi, fmt)
        if changed:
            self.drag[field] = value
            em.preview_value(app, field, float(value))
        self._release(field, value)

    def colour(self, spec, field: str, label: str) -> None:
        imgui, app = self.imgui, self.app
        value = self.drag.get(field, getattr(spec, field))
        changed, value = imgui.color_edit3(label, list(value))
        if changed:
            self.drag[field] = tuple(float(c) for c in value)
            em.preview_value(app, field, self.drag[field])
        self._release(field, value)

    def _release(self, field: str, value) -> None:
        imgui, app = self.imgui, self.app
        if imgui.is_item_deactivated_after_edit():
            held = self.drag.pop(field, value)
            em.set_value(app, field, tuple(float(c) for c in held) if isinstance(held, (list, tuple)) else float(held))
        elif imgui.is_item_deactivated() and self.drag.pop(field, None) is not None:
            em.end_preview(app)


class EyePanel:
    PAD_SIZE = (150.0, 96.0)  # the gaze pad in pixels (`PROVISIONAL`)

    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer
        self.sliders = _Sliders(imgui, app)
        self._presets: list[str] = []

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
        st = em.state(app)
        imgui.text_disabled("Ansicht (alle Augen, nicht gespeichert)")
        changed, on = imgui.checkbox("Augen zeigen", st.eyes_shown)
        if changed:
            app.set_eyes_shown(on)
        imgui.same_line()
        changed, on = imgui.checkbox("Vorschau", st.preview)
        if changed:
            em.set_view(app, preview=on)
        imgui.text_disabled("Qualität")
        for tier in TIERS:
            imgui.same_line()
            if imgui.radio_button(em.TIER_LABELS[tier], st.tier == tier):
                em.set_view(app, tier=tier)
            if imgui.is_item_hovered():
                imgui.set_tooltip(TIER_HINT)
        draw_gaze(imgui, app, st, self.PAD_SIZE)
        imgui.separator()
        imgui.text_disabled(st.header)
        if not st.has_eyes:
            return
        for field, label, lo, hi, fmt in em.PANEL_SLIDERS:
            self.sliders.slider(st.spec, field, label, lo, hi, fmt)
        imgui.set_next_item_width(170.0)
        if imgui.begin_combo("Look-Vorlage", "anwenden ..."):
            if imgui.is_window_appearing():
                self._presets = em.preset_names(app)
            for name in self._presets:
                if imgui.selectable(name, False)[0]:
                    app.apply_eye_preset(name)
            imgui.end_combo()
        if st.lab_open:
            if imgui.button("Eye Lab schließen"):
                app.close_eye_lab()
        elif imgui.button("Im Eye Lab öffnen"):
            app.open_eye_lab()


class EyeLabPanel:
    """The Eye Lab window: every eye value with live preview, close-up framing, isolation, quality, presets."""

    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer
        self.sliders = _Sliders(imgui, app)
        self.image_buf = ""
        self.preset_buf = ""

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
        st = em.state(app)
        imgui.text_disabled(st.header)
        if imgui.button("Frontal einrahmen"):
            app.frame_eye(frontal=True)
        imgui.same_line()
        if imgui.button("Einrahmen"):
            app.frame_eye()
        changed, on = imgui.checkbox("Nur Augen + Kopf", st.isolate)
        if changed:
            app.set_eye_isolate(on)
        imgui.same_line()
        imgui.text_disabled("Qualität")
        for tier in TIERS:
            imgui.same_line()
            if imgui.radio_button(em.TIER_LABELS[tier] + "##lab", st.tier == tier):
                em.set_view(app, tier=tier)
            if imgui.is_item_hovered():
                imgui.set_tooltip(TIER_HINT)
        imgui.text_disabled("Optik (alle Augen, nicht gespeichert)")
        for refraction in REFRACTIONS:
            if imgui.radio_button(refraction, st.refraction == refraction):
                em.set_view(app, refraction=refraction)
            imgui.same_line()
        for reflection in REFLECTIONS:
            if imgui.radio_button(em.REFLECTION_LABELS[reflection], st.reflection == reflection):
                em.set_view(app, reflection=reflection)
            imgui.same_line()
        imgui.new_line()
        lo, hi = em.GAZE_FOCUS_RANGE
        imgui.set_next_item_width(170.0)
        changed, focus = imgui.slider_float("Blick: Fokus-Abstand (Augenradien)", float(st.gaze_focus), lo, hi, "%.0f",
                                            imgui.SliderFlags_.logarithmic)
        if changed:
            em.set_gaze(app, focus=focus)
        if not st.has_eyes:
            if imgui.button("Schließen"):
                app.close_eye_lab()
            return
        spec = st.spec
        imgui.separator()
        imgui.text_disabled("Anatomie")
        for field, label, lo, hi, fmt in em.PANEL_SLIDERS + em.ANATOMY_SLIDERS:
            self.sliders.slider(spec, field, label, lo, hi, fmt)
        imgui.separator()
        imgui.text_disabled("Limbus")
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
        self.sliders.colour(spec, "limbal_colour", "Limbusfarbe")
        changed, on = imgui.checkbox("Asymmetrie oben/unten", spec.asymmetry)
        if changed:
            em.set_value(app, "asymmetry", on)
        for field, label, lo, hi, fmt in em.SLIDERS:
            self.sliders.slider(spec, field, label, lo, hi, fmt)
        imgui.separator()
        imgui.text_disabled(st.image_text)
        imgui.set_next_item_width(220.0)
        _, self.image_buf = imgui.input_text("##iris", self.image_buf)
        imgui.same_line()
        if imgui.small_button("Iris-Bild laden"):
            app.set_eye_iris_image(self.image_buf.strip().strip('"') or None)
        if st.eyes[0].texture is not None:
            if imgui.small_button("Bild entfernen"):
                app.set_eye_iris_image(None)
        imgui.separator()
        imgui.set_next_item_width(170.0)
        _, self.preset_buf = imgui.input_text_with_hint("##preset", "Name der Vorlage", self.preset_buf)
        imgui.same_line()
        if imgui.small_button("Als Look-Vorlage speichern"):
            app.save_eye_preset(self.preset_buf)
        if imgui.button("Schließen"):
            app.close_eye_lab()


def draw_gaze(imgui, app, st: em.EyePanelState, pad_size: tuple[float, float]) -> None:
    """Where every eye looks (`mirai.eye_gaze`): the mode and the gaze pad (drag: the eyes look there, as seen facing
    them; double click: straight ahead). View state, applied live. The focus distance is in the Eye Lab."""
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
    width, height = pad_size
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
