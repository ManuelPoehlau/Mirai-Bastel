"""The LookDev panel (AD-038 §7, proposal §3): Studio, Licht, Material, Ansicht, Status.

Drawn while `app.lookdev_open` (like the Paint Room's window); the logic is `gui.lookdev_model` (headless). Every value
goes through `Application` and is session state - not saved, no Undo (M1). A held slider shows its value at once (the
studio's rotation, intensity and exposure are uniforms; no projection), so preview and release are the same step here.
About 15 controls are visible; the tone curve, softness, "Licht folgt Kamera" and backscatter sit under "Mehr".
"""

from __future__ import annotations

from . import lookdev_model as lm


class LookdevPanel:
    WIDTH = 170.0

    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer
        self.more = False

    def _slider(self, label: str, value: float, low: float, high: float, fmt: str = "%.2f"):
        imgui = self.imgui
        imgui.set_next_item_width(self.WIDTH)
        return imgui.slider_float(label, float(value), low, high, fmt)

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
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
                        app.set_lookdev_material(name)
                imgui.end_combo()
            if imgui.radio_button(row.albedo_label, row.albedo_source == "texture"):
                app.set_lookdev_material_values(albedo_source="texture")
            imgui.same_line()
            if imgui.radio_button("Farbe", row.albedo_source == "color"):
                app.set_lookdev_material_values(albedo_source="color")
            imgui.same_line()
            changed, colour = imgui.color_edit3("##farbe", list(row.base_color), imgui.ColorEditFlags_.no_inputs)
            if changed:
                app.set_lookdev_material_values(base_color=tuple(colour))
            for field, label in (("roughness", "Rauheit"), ("specular", "Glanz"), ("wrap", "Weichheit")):
                changed, value = self._slider(label, getattr(row, field), 0.0, 1.0)
                if changed:
                    app.set_lookdev_material_values(**{field: value})
            if self.more:
                changed, value = self._slider("Durchscheinen", row.backscatter, 0.0, 1.0)
                if changed:
                    app.set_lookdev_material_values(backscatter=value)
                imgui.same_line()
                changed, colour = imgui.color_edit3("##durch", list(row.backscatter_color),
                                                    imgui.ColorEditFlags_.no_inputs)
                if changed:
                    app.set_lookdev_material_values(backscatter_color=tuple(colour))
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
