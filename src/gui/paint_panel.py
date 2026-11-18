"""The Paint Room panel (AD-037 §8 Phase 2): tool, colour, radius, opacity, flow, hardness, curve, mirror, resolution.

Drawn while `app.paint_room_open` (like the Eye Lab window); the logic is `gui.paint_model` (headless). Every value goes
through `Application.set_paint_brush` (view state: not saved, no Undo step).
"""

from __future__ import annotations

from mirai.paint.brush import RADIUS_STEPS_PERCENT

from . import paint_model as pm


class PaintPanel:
    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer

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
        imgui.set_next_item_width(170.0)
        changed, step = imgui.slider_int("Radius", brush.radius_step, 0, len(RADIUS_STEPS_PERCENT) - 1,
                                         pm.radius_label(brush.radius_step))
        if changed:
            app.set_paint_brush(radius_step=step)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Prozent des Objektradius (Welt, P-7); Shift+Rad im Viewport")
        for field, label, hint in (("opacity", "Deckkraft", "Alt+Rad im Viewport; baut sich in einem Strich nicht auf"),
                                   ("flow", "Fluss", "pro Tupfer; baut sich in einem Strich auf"),
                                   ("hardness", "Härte", "der volle Kern des Pinsels")):
            imgui.set_next_item_width(170.0)
            changed, value = imgui.slider_float(label, float(getattr(brush, field)) * 100.0, 0.0, 100.0, "%.0f %%")
            if changed:
                app.set_paint_brush(**{field: value / 100.0})
            if imgui.is_item_hovered():
                imgui.set_tooltip(hint)
        imgui.set_next_item_width(170.0)
        if imgui.begin_combo("Kurve", pm.curve_label(brush.curve)):
            for curve in pm.CURVES:
                if imgui.selectable(pm.curve_label(curve), curve == brush.curve)[0]:
                    app.set_paint_brush(curve=curve)
            imgui.end_combo()
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
        if imgui.button("Schließen"):
            app.close_paint_room()
