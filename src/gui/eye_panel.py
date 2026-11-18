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
from . import iris_import_model as im
from .file_browser_model import ALL_FILTER, IMAGE_FILTER
from viewport.eye_pass import REFLECTIONS, REFRACTIONS, TIERS

TIER_HINT = "'schnell' zeichnet ohne Reflexe und Iris des Eye Labs (wie vor Phase 3), 'voll' mit ihnen."


class _Sliders:
    """Live-preview sliders shared by the panel and the lab: held -> `preview_eye`, released -> `set_eye`."""

    def __init__(self, imgui, app) -> None:
        self.imgui, self.app = imgui, app
        self.drag: dict = {}  # field -> value while a slider is held

    def slider(self, spec, field: str, label: str, lo: float, hi: float, fmt: str, width: float = 170.0) -> None:
        imgui, app = self.imgui, self.app
        value = self.drag.get(field, em.value(spec, field))
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
        self.sclera_buf = ""
        self.preset_buf = ""
        self.importer = IrisImportSection(imgui, app)

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
        self.draw_look(st)
        self.draw_iris(st)
        self.draw_sclera(st)
        imgui.separator()
        imgui.text_disabled(st.image_text)
        imgui.set_next_item_width(220.0)
        _, self.image_buf = imgui.input_text("##iris", self.image_buf)
        imgui.same_line()
        if imgui.small_button("Durchsuchen...##iris"):
            self.browse_image("Iris-Bild wählen", self.set_iris_path)
        imgui.same_line()
        if imgui.small_button("Iris-Bild laden"):
            app.set_eye_iris_image(self.image_buf.strip().strip('"') or None)
        if st.eyes[0].texture is not None:
            if imgui.small_button("Bild entfernen"):
                app.set_eye_iris_image(None)
        self.importer.draw(self.image_buf)
        imgui.separator()
        imgui.set_next_item_width(170.0)
        _, self.preset_buf = imgui.input_text_with_hint("##preset", "Name der Vorlage", self.preset_buf)
        imgui.same_line()
        if imgui.small_button("Als Look-Vorlage speichern"):
            app.save_eye_preset(self.preset_buf)
        if imgui.button("Schließen"):
            app.close_eye_lab()

    def browse_image(self, title: str, on_pick) -> None:
        """„Durchsuchen...“: der Datei-Browser (`gui.file_browser`) für ein Bild; ohne Menüs (kein `Services`) bleibt das
        Pfadfeld."""
        menus = getattr(self.layer, "menus", None)
        if menus is None:
            self.app.set_status("Datei-Browser: nicht verfügbar, Pfad ins Feld tippen")
            return
        menus.browser.request("image", title, (IMAGE_FILTER, ALL_FILTER), on_pick)

    def set_iris_path(self, path) -> None:
        """Gewähltes Iris-Bild: ins Feld; „Iris-Bild laden“ und „Iris importieren ...“ arbeiten damit weiter."""
        self.image_buf = str(path)

    def load_sclera_path(self, path) -> None:
        """Gewähltes Lederhaut-Bild: ins Feld und gleich laden (ein Undo-Schritt, wie „Lederhaut-Bild laden“)."""
        self.sclera_buf = str(path)
        em.set_sclera_image(self.app, self.sclera_buf)

    def draw_sclera(self, st: em.EyePanelState) -> None:
        """AD-035 M1: "Lederhaut" - the sclera's colour map (status, path field, load / remove; `PROVISIONAL` layout).
        Loading another image replaces the map; each action is one Undo step."""
        imgui, app = self.imgui, self.app
        imgui.separator()
        imgui.text_disabled("Lederhaut (Farbbild, gespeichert)")
        imgui.text(st.sclera_text)
        if st.sclera_path is not None and imgui.is_item_hovered():
            imgui.set_tooltip(st.sclera_path)
        imgui.set_next_item_width(220.0)
        _, self.sclera_buf = imgui.input_text("##sclera", self.sclera_buf)
        imgui.same_line()
        if imgui.small_button("Durchsuchen...##sclera"):
            self.browse_image("Lederhaut-Bild wählen", self.load_sclera_path)
        imgui.same_line()
        if imgui.small_button("Lederhaut-Bild laden"):
            em.set_sclera_image(app, self.sclera_buf)
        if st.sclera_path is not None:
            imgui.same_line()
            if imgui.small_button("Bild entfernen##sclera"):
                em.set_sclera_image(app, None)
        imgui.push_text_wrap_pos(imgui.get_cursor_pos_x() + 360.0)
        imgui.text_disabled(em.SCLERA_HINT)
        imgui.pop_text_wrap_pos()

    def draw_look(self, st: em.EyePanelState) -> None:
        """Phase 3: the reflections (`core.EyeLook`), live preview while held, one Undo step per release."""
        imgui, app = self.imgui, self.app
        spec = st.spec
        imgui.separator()
        imgui.text_disabled("Reflexe (Phase 3, gespeichert)")
        if st.tier != "full":
            imgui.text_colored(imgui.ImVec4(0.95, 0.75, 0.35, 1.0), em.LOOK_HINT)
        for field, label, lo, hi, fmt in em.LOOK_SLIDERS:
            self.sliders.slider(spec, field, label, lo, hi, fmt)
        imgui.text_disabled(f"Muster {em.value(spec, 'look.seed')}")
        imgui.same_line()
        if imgui.small_button("Neues Muster"):
            em.new_pattern(app)
        if spec.look is not None:
            imgui.same_line()
            if imgui.small_button("Reflexe zurücksetzen"):
                em.reset_look(app)

    def draw_iris(self, st: em.EyePanelState) -> None:
        """Phase 4: the iris (`core.EyeIris`): key through the cornea, relief, pupil edge; live preview while held."""
        imgui, app = self.imgui, self.app
        spec = st.spec
        imgui.separator()
        imgui.text_disabled("Iris (Phase 4, gespeichert)")
        if st.tier != "full":
            imgui.text_colored(imgui.ImVec4(0.95, 0.75, 0.35, 1.0), em.IRIS_HINT)
        for field, label, lo, hi, fmt in em.IRIS_SLIDERS:
            self.sliders.slider(spec, field, label, lo, hi, fmt)
        source = em.value(spec, "look.iris.relief_source")
        for key, label in em.RELIEF_SOURCE_LABELS.items():
            if imgui.radio_button(label, source == key):
                em.set_value(app, "look.iris.relief_source", key)
            imgui.same_line()
        imgui.new_line()
        if spec.look is not None and spec.look.iris is not None:
            if imgui.small_button("Iris zurücksetzen"):
                em.reset_iris(app)


class IrisImportSection:
    """Eye LookDev phase 5: "Iris importieren" in the Eye Lab - the source's kind, the two landmark circles over the
    image (drag a centre or an edge, or type the values), the options and "Importieren" (`gui.iris_import_model`). The
    draft is UI state; only "Importieren" changes the document (one Undo step)."""

    VIEW = 320.0  # the image view's longer side in pixels (`PROVISIONAL`)
    PUPIL_COLOUR = (0.35, 0.85, 0.95, 1.0)
    IRIS_COLOUR = (0.98, 0.82, 0.30, 1.0)
    WARN = (0.95, 0.75, 0.35, 1.0)

    def __init__(self, imgui, app) -> None:
        self.imgui, self.app = imgui, app
        self.draft: im.ImportDraft | None = None
        self.message = ""
        self._texture = None  # the source as a GL texture for the view (pyglet), made when a draft opens
        self._grab: tuple[str, str] | None = None

    def _set_texture(self, draft: im.ImportDraft | None) -> None:
        if self._texture is not None:
            self._texture.delete()
            self._texture = None
        if draft is None:
            return
        try:
            from pyglet import image

            w, h = draft.size
            rows = draft.rgba[::-1].tobytes()  # pyglet: bottom-up
            self._texture = image.ImageData(w, h, "RGBA", rows, pitch=w * 4).get_texture()
        except Exception as exc:  # no GL here: the circles are still set by value
            self._texture, self.message = None, f"Vorschau nicht verfügbar ({exc.__class__.__name__})"

    def draw(self, path_text: str) -> None:
        imgui = self.imgui
        if self.draft is None:
            if imgui.small_button("Iris importieren ..."):
                draft, self.message = im.open_draft(path_text)
                if draft is not None:
                    self.draft = draft
                    self._set_texture(draft)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Bild aus dem Feld oben öffnen: Quelle angeben, Pupillen- und Irisrand setzen,\n"
                                  "dann importieren (die Kopie liegt neben der Szene).")
            if self.message:
                imgui.text_colored(imgui.ImVec4(*self.WARN), self.message)
            return
        self._draw_draft()

    def _draw_draft(self) -> None:
        imgui, app = self.imgui, self.app
        draft = self.draft
        imgui.separator()
        imgui.text_disabled("Iris importieren (Phase 5)")
        imgui.text_disabled(draft.summary)
        for kind, label in im.KIND_LABELS.items():
            if imgui.radio_button(label, draft.kind == kind):
                draft = im.with_options(draft, kind=kind)
            imgui.same_line()
        imgui.new_line()
        if draft.kind == "photo":
            changed, on = imgui.checkbox("Brechung herausrechnen (frontales Foto)", draft.correct)
            if changed:
                draft = im.with_options(draft, correct=on)
        if draft.kind == "flat" or not draft.correct:
            changed, on = imgui.checkbox("Randfarbe halten", draft.hold_outer_color)
            if changed:
                draft = im.with_options(draft, hold_outer_color=on)
        if draft.has_alpha:
            changed, on = imgui.checkbox("Alpha behalten (eigene Höhe)", draft.keep_alpha)
            if changed:
                draft = im.with_options(draft, keep_alpha=on)
        else:
            imgui.text_disabled("Höhe: aus der Helligkeit, in den Alphakanal der Kopie")
        draft = self._draw_view(draft)
        for name, label in (("pupil", "Pupille"), ("iris", "Iris")):
            c = getattr(draft.marks, name)
            values = [c.x, c.y, c.r]
            imgui.set_next_item_width(220.0)
            changed, values = imgui.drag_float3(f"{label} x / y / r", values, 0.25, 0.0, 0.0, "%.1f")
            if changed:
                draft = im.set_circle(draft, name, x=values[0], y=values[1], r=values[2])
        if draft.problem:
            imgui.text_colored(imgui.ImVec4(*self.WARN), draft.problem)
        if draft.hint:
            imgui.text_colored(imgui.ImVec4(*self.WARN), draft.hint)
        if imgui.small_button("Neu schätzen"):
            draft = im.reestimate(draft)
        imgui.same_line()
        if not draft.problem and imgui.button("Importieren"):
            im.run_import(app, draft)
        imgui.same_line()
        if imgui.small_button("Abbrechen"):
            self.draft = None
            self._set_texture(None)
            return
        self.draft = draft

    def _draw_view(self, draft: im.ImportDraft) -> im.ImportDraft:
        """The source image with both circles; a centre handle moves its circle, an edge handle (or the line) sets
        its radius."""
        imgui = self.imgui
        w, h = draft.size
        scale = self.VIEW / max(w, h)
        size = imgui.ImVec2(w * scale, h * scale)
        origin = imgui.get_cursor_screen_pos()
        if self._texture is not None:
            imgui.image(imgui.ImTextureRef(self._texture.id), size)
            imgui.set_cursor_screen_pos(origin)
        imgui.invisible_button("##iris_view", size)
        mouse = imgui.get_io().mouse_pos
        x, y = (mouse.x - origin.x) / scale, (mouse.y - origin.y) / scale
        if imgui.is_item_activated():
            self._grab = im.pick_handle(draft.marks, x, y, 8.0 / scale)
        if imgui.is_item_active() and self._grab is not None:
            draft = im.drag_handle(draft, self._grab, x, y)
        if imgui.is_item_deactivated() and self._grab is not None:
            draft, self._grab = im.checked(draft), None
        dl = imgui.get_window_draw_list()
        if self._texture is None:
            dl.add_rect(origin, imgui.ImVec2(origin.x + size.x, origin.y + size.y),
                        imgui.get_color_u32(imgui.ImVec4(0.38, 0.4, 0.45, 1)))
        for name, colour in (("pupil", self.PUPIL_COLOUR), ("iris", self.IRIS_COLOUR)):
            c = getattr(draft.marks, name)
            u32 = imgui.get_color_u32(imgui.ImVec4(*colour))
            centre = imgui.ImVec2(origin.x + c.x * scale, origin.y + c.y * scale)
            dl.add_circle(centre, c.r * scale, u32, 96, 1.5)
            dl.add_circle_filled(centre, 3.5, u32)
            dl.add_circle_filled(imgui.ImVec2(centre.x + c.r * scale, centre.y), 4.5, u32)
        return draft


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
