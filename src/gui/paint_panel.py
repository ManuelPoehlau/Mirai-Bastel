"""The Paint Room panel (AD-037 §8 Phase 2): tool, colour, radius, opacity, flow, hardness, curve, mirror, resolution;
Phase 3: the layers; Phase 4a (§12): the tip (round or a test alpha), spacing, angle and the Kreismaske.

Drawn while `app.paint_room_open` (like the Eye Lab window); the logic is `gui.paint_model` (headless). Every brush value
goes through `Application.set_paint_brush` (view state: not saved, no Undo step); every layer change is one Undo step
(`Application.add_paint_layer` ...). The layer opacity slider previews while it is held and makes its step on release.
"""

from __future__ import annotations

import dataclasses

from mirai.paint.brush import RADIUS_STEPS_PERCENT

from . import paint_model as pm


class PaintPanel:
    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer
        #: the rename field's text while it is edited, by layer name
        self.rename_buf: dict[str, str] = {}
        #: the held opacity slider's value (layer name, value)
        self.held_opacity: tuple[str, float] | None = None

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
        st = pm.state(app)
        brush = st.brush
        imgui.text_disabled(f"{st.header} - {st.surface}")
        for tool in pm.TOOLS:
            if imgui.radio_button(pm.tool_label(tool), brush.tool == tool):
                app.set_paint_brush(tool=tool)
            imgui.same_line()
        imgui.new_line()
        changed, colour = imgui.color_edit3("Farbe", list(brush.colour))
        if changed:
            app.set_paint_brush(colour=tuple(float(c) for c in colour))
        self._tip(st)
        imgui.set_next_item_width(170.0)
        changed, step = imgui.slider_int("Radius", brush.radius_step, 0, len(RADIUS_STEPS_PERCENT) - 1,
                                         pm.radius_label(brush.radius_step))
        if changed:
            app.set_paint_brush(radius_step=step)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Prozent des Objektradius (Welt, P-7); Shift+Rad im Viewport")
        round_falloff = brush.tip.round or brush.tip.kreismaske
        for field, label, hint in (("opacity", "Deckkraft", "Alt+Rad im Viewport; baut sich in einem Strich nicht auf"),
                                   ("flow", "Fluss", "pro Stempel; baut sich in einem Strich auf"),
                                   ("hardness", "Härte", "der volle Kern des Pinsels")):
            if field == "hardness" and not round_falloff:
                continue  # an alpha defines its own shape (P-19); hardness and curve shape only the Kreismaske
            imgui.set_next_item_width(170.0)
            changed, value = imgui.slider_float(label, float(getattr(brush, field)) * 100.0, 0.0, 100.0, "%.0f %%")
            if changed:
                app.set_paint_brush(**{field: value / 100.0})
            if imgui.is_item_hovered():
                imgui.set_tooltip(hint)
        if round_falloff:
            imgui.set_next_item_width(170.0)
            if imgui.begin_combo("Kurve", pm.curve_label(brush.curve)):
                for curve in pm.CURVES:
                    if imgui.selectable(pm.curve_label(curve), curve == brush.curve)[0]:
                        app.set_paint_brush(curve=curve)
                imgui.end_combo()
        lo, hi = pm.SPACING_PERCENT
        imgui.set_next_item_width(170.0)
        changed, value = imgui.slider_float("Abstand", brush.dynamics.spacing * 100.0, lo, hi, "%.0f %%",
                                            imgui.SliderFlags_.logarithmic)
        if changed:
            app.set_paint_brush(dynamics=dataclasses.replace(brush.dynamics, spacing=min(max(value, lo), hi) / 100.0))
        if imgui.is_item_hovered():
            imgui.set_tooltip("Abstand der Stempel entlang des Strichs, in % des Stempeldurchmessers (Weltmaß, P-18)")
        if st.mirror_plane is not None:
            changed, on = imgui.checkbox(f"Spiegeln ({st.mirror_plane}-Ebene)", brush.mirror)
            if changed:
                app.set_paint_brush(mirror=on)
        else:
            imgui.text_disabled("Spiegeln: keine Symmetrie-Ebene (Shift+S)")
        imgui.separator()
        if st.resolution_fixed:
            imgui.text_disabled(f"Auflösung {st.resolution}² (steht seit dem ersten Strich)")
        else:
            imgui.text_disabled("Auflösung der neuen Bemalung")
            for size in st.resolutions:
                imgui.same_line()
                if imgui.radio_button(f"{size}²", st.resolution == size):
                    app.set_paint_resolution(size)
        self._layers(st)
        imgui.separator()
        if imgui.button("Schließen"):
            app.close_paint_room()

    def _tip(self, st: pm.PaintPanelState) -> None:
        """The tip chooser (4a: a plain combo over the test alphas) and, with an alpha, its angle and Kreismaske."""
        imgui, app = self.imgui, self.app
        brush = st.brush
        imgui.set_next_item_width(170.0)
        if imgui.begin_combo("Spitze", st.tip_label):
            for alpha, label in st.tips:
                if imgui.selectable(label, alpha == brush.tip.alpha)[0] and alpha != brush.tip.alpha:
                    app.set_paint_tip(alpha)
            imgui.end_combo()
        if imgui.is_item_hovered():
            imgui.set_tooltip("Rund = der weiche Pinsel; die anderen sind Test-Alphas (Phase 4a): Strich folgen")
        if brush.tip.round:
            return
        imgui.set_next_item_width(170.0)
        changed, angle = imgui.slider_float("Winkel", float(brush.dynamics.angle), -180.0, 180.0, "%.0f°")
        if changed:
            app.set_paint_brush(dynamics=dataclasses.replace(brush.dynamics, angle=min(max(angle, -180.0), 180.0)))
        if imgui.is_item_hovered():
            imgui.set_tooltip("Drehung des Alphas gegen die Strichrichtung")
        changed, on = imgui.checkbox("Kreismaske", brush.tip.kreismaske)
        if changed:
            app.set_paint_brush(tip=dataclasses.replace(brush.tip, kreismaske=on))
        if imgui.is_item_hovered():
            imgui.set_tooltip("Das Alpha zusätzlich mit der runden Abnahme (Härte, Kurve) maskieren - aus: das Alpha "
                              "bestimmt seine Form selbst")

    def _layers(self, st: pm.PaintPanelState) -> None:
        imgui, app = self.imgui, self.app
        imgui.separator()
        imgui.text("Ebenen")
        if not st.layers:
            imgui.text_disabled(pm.NO_LAYERS)
            return
        for row in st.layers:
            imgui.push_id(f"layer {row.name}")
            changed, on = imgui.checkbox("##shown", row.visible)
            if changed:
                app.set_paint_layer(row.name, visible=on)
            if imgui.is_item_hovered():
                imgui.set_tooltip("Ebene zeigen / ausblenden")
            imgui.same_line()
            if imgui.selectable(row.label, row.active)[0] and not row.active:
                app.set_paint_active_layer(row.name)
            imgui.pop_id()
        active = next(row for row in st.layers if row.active)
        imgui.push_id(f"active {active.name}")
        self._rename(active)
        held = self.held_opacity
        value = held[1] if held is not None and held[0] == active.name else active.opacity
        imgui.set_next_item_width(170.0)
        changed, value = imgui.slider_float("Ebenen-Deckkraft", float(value) * 100.0, 0.0, 100.0, "%.0f %%")
        if changed:
            self.held_opacity = (active.name, value / 100.0)
            app.preview_paint_layer(active.name, opacity=value / 100.0)
        if imgui.is_item_deactivated_after_edit():
            name, opacity = self.held_opacity or (active.name, value / 100.0)
            self.held_opacity = None
            app.set_paint_layer(name, opacity=opacity)
        elif imgui.is_item_deactivated() and self.held_opacity is not None:
            self.held_opacity = None
            app.end_paint_layer_preview()
        imgui.set_next_item_width(170.0)
        if imgui.begin_combo("Mischmodus", pm.blend_label(active.blend)):
            for blend in pm.BLENDS:
                if imgui.selectable(pm.blend_label(blend), blend == active.blend)[0] and blend != active.blend:
                    app.set_paint_layer(active.name, blend=blend)
            imgui.end_combo()
        imgui.pop_id()
        name = active.name
        for i, (label, enabled, action, hint) in enumerate((
                ("Neu", st.can_add, app.add_paint_layer, "neue leere Ebene über der aktiven"),
                ("Hoch", st.can_up, lambda: app.move_paint_layer(name, 1), "eine Stufe nach oben"),
                ("Runter", st.can_down, lambda: app.move_paint_layer(name, -1), "eine Stufe nach unten"),
                ("Zusammenführen", st.can_merge, lambda: app.merge_paint_layer_down(name),
                 "in die Ebene darunter (beide sichtbar, gleicher Mischmodus)"),
                ("Leeren", not st.stroking, lambda: app.clear_paint_layer(name), "die Ebene durchsichtig machen"),
                ("Löschen", st.can_delete, lambda: app.delete_paint_layer(name), "die Ebene entfernen"))):
            if i not in (0, 3):
                imgui.same_line()
            imgui.begin_disabled(not enabled)
            if imgui.button(label):
                action()
            imgui.end_disabled()
            if imgui.is_item_hovered():
                imgui.set_tooltip(hint)

    def _rename(self, active: pm.LayerRow) -> None:
        imgui, app = self.imgui, self.app
        imgui.set_next_item_width(170.0)
        changed, text = imgui.input_text("Name", self.rename_buf.get(active.name, active.name))
        if changed:
            self.rename_buf[active.name] = text
        if imgui.is_item_deactivated_after_edit():
            text = self.rename_buf.pop(active.name, text)
            if text.strip() and text.strip() != active.name:
                app.rename_paint_layer(active.name, text)
        elif imgui.is_item_deactivated():
            self.rename_buf.pop(active.name, None)  # Esc: dropped
