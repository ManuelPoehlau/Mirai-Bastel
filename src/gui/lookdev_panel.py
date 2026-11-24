"""The LookDev panel (AD-038 §7, proposal §3): Studio, Effekte (AD-039 §2.1), Licht, Material, Ansicht, Status.

Drawn while `app.lookdev_open` (like the Paint Room's window); the logic is `gui.lookdev_model` (headless). Every value
goes through `Application`. Studio and lights are view state (saved in `view.lookdev`, no Undo): a held slider changes
them at once (rotation, intensity and exposure are uniforms; no projection). The material is document data since LD-2
(AD-038 §18): a held slider or colour previews (`MaterialEdit.hold`), the release is one Undo step.
About 15 controls are visible; the tone curve, softness, "Licht folgt Kamera" and backscatter sit under "Mehr".
AD-039 S7: the material's maps sit under "Mehr" too - one row per map (file, „Laden …“ through the file browser,
„Entfernen“; one Undo step each), the normal map's strength (held = preview, release = one step) and its green
direction.
"""

from __future__ import annotations

from . import lookdev_model as lm
from .file_browser_model import ALL_FILTER, IMAGE_FILTER


class LookdevPanel:
    WIDTH = 170.0

    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer
        self.more = False
        self.edit = lm.MaterialEdit()

    def _slider(self, label: str, value: float, low: float, high: float, fmt: str = "%.2f"):
        imgui = self.imgui
        imgui.set_next_item_width(self.WIDTH)
        return imgui.slider_float(label, float(value), low, high, fmt)

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
        if self.edit.held and not imgui.is_any_item_active() and not imgui.is_mouse_down(0):
            self.edit.release(app)  # the held material control was let go: one Undo step
        st = lm.state(app)
        imgui.text_disabled(st.status)
        # -- Studio
        imgui.separator_text("Studio")
        imgui.set_next_item_width(self.WIDTH)
        if imgui.begin_combo("Vorlage", lm.preset_label(st)):
            for name in lm.STUDIO_PRESETS:
                if imgui.selectable(name, name == st.studio_preset)[0]:
                    app.set_lookdev_studio_preset(name)
            imgui.end_combo()
        changed, value = self._slider("Drehung", st.rotation, -180.0, 180.0, "%.0f°")
        if changed:
            app.set_lookdev_studio(rotation=value)
        changed, value = self._slider("Helligkeit", st.env_intensity, 0.0, 4.0)
        if changed:
            app.set_lookdev_studio(env_intensity=value)
        changed, value = self._slider("Belichtung", st.exposure, -4.0, 4.0, "%.1f EV")
        if changed:
            app.set_lookdev_studio(exposure=value)
        changed, gradient = imgui.checkbox("Verlauf", st.background_gradient)
        if changed:
            app.set_lookdev_studio(background_gradient=gradient)
        imgui.same_line()
        bottom, top = st.background
        changed, colour = imgui.color_edit3("Hintergrund", list(bottom), imgui.ColorEditFlags_.no_inputs)
        if changed:
            app.set_lookdev_studio(background=(tuple(colour), top))
        if st.background_gradient:
            imgui.same_line()
            changed, colour = imgui.color_edit3("oben", list(top), imgui.ColorEditFlags_.no_inputs)
            if changed:
                app.set_lookdev_studio(background=(bottom, tuple(colour)))
        # -- Effekte (AD-039 §2.1): one checkbox per built P3 effect; a greyed one says why in its tooltip
        imgui.separator_text(lm.EFFECTS_TITLE)
        for effect in st.effects:
            imgui.begin_disabled(not effect.available)
            changed, on = imgui.checkbox(effect.label, effect.on and effect.available)
            imgui.end_disabled()
            if changed:
                app.set_lookdev_effect(effect.name, on)
            if imgui.is_item_hovered(imgui.HoveredFlags_.allow_when_disabled):
                imgui.set_tooltip(effect.hint if effect.available else effect.reason)
        # -- Licht
        imgui.separator_text("Licht")
        for row in st.lights:
            imgui.push_id(row.name)
            changed, on = imgui.checkbox(row.label, row.on)
            if changed:
                app.set_lookdev_light(row.name, on=on)
            imgui.same_line()
            imgui.set_next_item_width(90.0)
            changed, value = imgui.slider_float("Stärke", float(row.intensity), 0.0, 4.0, "%.2f")
            if changed:
                app.set_lookdev_light(row.name, intensity=value)
            imgui.set_next_item_width(self.WIDTH)
            changed, angles = imgui.slider_float2("Richtung", [float(row.azimuth), float(row.elevation)], -180.0,
                                                  180.0, "%.0f°")
            if changed:
                app.set_lookdev_light(row.name, azimuth=angles[0], elevation=max(-90.0, min(90.0, angles[1])))
            imgui.set_next_item_width(self.WIDTH)
            changed, value = imgui.slider_float("Wärme", float(row.kelvin), 2500.0, 10000.0, "%.0f K")
            if changed:
                app.set_lookdev_light(row.name, kelvin=value)
            if self.more:
                changed, value = self._slider("Weichheit", row.size, 0.0, 1.0)
                if changed:
                    app.set_lookdev_light(row.name, size=value)
            imgui.pop_id()
        # -- Material
        imgui.separator_text("Material")
        row = st.material
        if row is None:
            imgui.text_disabled("kein Objekt")
        else:
            imgui.text_disabled(lm.targets_label(row))
        if row is not None and row.targets:
            imgui.set_next_item_width(self.WIDTH)
            if imgui.begin_combo("Material", lm.material_label(row)):
                for name in lm.MATERIAL_PRESETS:
                    if imgui.selectable(name, name == row.preset)[0]:
                        self.edit.drop(app)
                        app.set_lookdev_material(name)
                imgui.end_combo()
            if imgui.radio_button(row.albedo_label, row.albedo_source == "texture"):
                self.edit.drop(app)
                app.set_lookdev_material_values(albedo_source="texture")
            imgui.same_line()
            if imgui.radio_button("Farbe", row.albedo_source == "color"):
                self.edit.drop(app)
                app.set_lookdev_material_values(albedo_source="color")
            imgui.same_line()
            changed, colour = imgui.color_edit3("##farbe", list(row.base_color), imgui.ColorEditFlags_.no_inputs)
            if changed:
                self.edit.hold(app, base_color=tuple(colour))
            for field, label in (("roughness", "Rauheit"), ("specular", "Glanz"), ("wrap", "Weichheit")):
                changed, value = self._slider(label, getattr(row, field), 0.0, 1.0)
                if changed:
                    self.edit.hold(app, **{field: value})
            if self.more:
                changed, value = self._slider("Durchscheinen", row.backscatter, 0.0, 1.0)
                if changed:
                    self.edit.hold(app, backscatter=value)
                imgui.same_line()
                changed, colour = imgui.color_edit3("##durch", list(row.backscatter_color),
                                                    imgui.ColorEditFlags_.no_inputs)
                if changed:
                    self.edit.hold(app, backscatter_color=tuple(colour))
                self.draw_maps(row)
            imgui.begin_disabled(not row.has_look)
            if imgui.button(lm.RESET):
                self.edit.drop(app)
                app.reset_lookdev_material()
            imgui.end_disabled()
            if imgui.is_item_hovered():
                imgui.set_tooltip(lm.RESET_HINT)
        # -- Ansicht
        imgui.separator_text("Ansicht")
        for i, (name, (yaw, pitch)) in enumerate(lm.VIEWS.items()):
            if i:
                imgui.same_line()
            if imgui.button(name):
                app.frame_lookdev(yaw, pitch)
        changed, on = imgui.checkbox("Wire", st.wire)
        if changed:
            app.set_lookdev_wire(on)
        imgui.same_line()
        changed, on = imgui.checkbox("Augen: Vorschau", st.eye_preview)
        if changed:
            app.set_eye_display(preview=on)
        imgui.begin_disabled(st.preparing)
        if imgui.button(lm.SAVE_IMAGE):
            app.save_lookdev_image()
        imgui.end_disabled()
        if imgui.is_item_hovered():
            imgui.set_tooltip(lm.SAVE_IMAGE_HINT)
        # -- Mehr
        changed, self.more = imgui.checkbox("Mehr", self.more)
        if self.more:
            imgui.set_next_item_width(self.WIDTH)
            if imgui.begin_combo("Tonkurve", lm.TONE_LABELS[st.tone_curve]):
                for curve, label in lm.TONE_LABELS.items():
                    if imgui.selectable(label, curve == st.tone_curve)[0]:
                        app.set_lookdev_studio(tone_curve=curve)
                imgui.end_combo()
            changed, on = imgui.checkbox("Licht folgt Kamera", st.follow_camera)
            if changed:
                app.set_lookdev_studio(follow_camera=on)

    def browse_map(self, kind: str) -> None:
        """„Laden …“: the file browser (`gui.file_browser`) for a map image; the pick loads it (one Undo step)."""
        menus = getattr(self.layer, "menus", None)
        if menus is None:
            self.app.set_status("Datei-Browser: nicht verfügbar")
            return
        menus.browser.request("image", f"{lm.MAP_LABELS[kind]} wählen", (IMAGE_FILTER, ALL_FILTER),
                              lambda path: lm.load_map(self.app, kind, str(path)))

    def draw_maps(self, row: lm.MaterialRow) -> None:
        """AD-039 §10 (S7): the material's maps (`PROVISIONAL` layout)."""
        imgui, app = self.imgui, self.app
        imgui.text_disabled(lm.MAPS_TITLE)
        if imgui.is_item_hovered():
            imgui.set_tooltip(lm.MAPS_HINT)
        if row.no_uvs:
            imgui.text_disabled("Objekt ohne UVs: Maps werden nicht gezeigt")
        for map_row in row.maps:
            imgui.push_id(map_row.kind)
            imgui.text(f"{map_row.label}: {map_row.text}")
            if map_row.path is not None and imgui.is_item_hovered():
                imgui.set_tooltip(map_row.path)
            if imgui.small_button(lm.MAP_LOAD):
                self.edit.drop(app)
                self.browse_map(map_row.kind)
            if map_row.path is not None:
                imgui.same_line()
                if imgui.small_button(lm.MAP_REMOVE):
                    self.edit.drop(app)
                    lm.load_map(app, map_row.kind, None)
            if map_row.kind == "normal" and map_row.path is not None:
                changed, value = self._slider(lm.NORMAL_STRENGTH, row.normal_strength, 0.0, 2.0)
                if changed:
                    self.edit.hold(app, normal_strength=value)
                changed, on = imgui.checkbox(lm.NORMAL_GREEN_DOWN, row.normal_green_down)
                if changed:
                    self.edit.drop(app)
                    app.set_lookdev_material_values(normal_green_down=on)
            imgui.pop_id()
