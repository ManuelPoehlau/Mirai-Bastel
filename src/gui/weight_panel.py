"""The Weight Room panel (AD-041 §7, slice 2; layout `PROVISIONAL`): the bones (the active one highlighted, a click makes a
bone current), the operation (Add / Subtract / Replace / Smooth, Replace's value), radius, strength, opacity, hardness,
curve, "nur zusammenhängend", "nur Vorderseite", the symmetry and Ruhe / Pose, "Aufräumen" with its threshold, and
"Raum schließen". While painting is refused the reason stands at the top.

Drawn while `app.weight_room_open` (like the Paint Room); the logic is `gui.weight_model` (headless). Every brush value goes
through `Application.set_weight_brush` (view state: not saved, no Undo step); "Aufräumen" is one Undo step.
"""

from __future__ import annotations

from mirai.paint.brush import RADIUS_STEPS_PERCENT
from mirai.skin_weights import CLEAN_THRESHOLD

from . import weight_model as wm

_CURRENT = (1.0, 0.8, 0.43, 1.0)  # wie das Edit-Objekt im Outliner
_PLAIN = (0.88, 0.9, 0.94, 1.0)
_WARN = (1.0, 0.62, 0.35, 1.0)
_WIDTH = 170.0


class WeightPanel:
    def __init__(self, imgui, app, layer) -> None:
        self.imgui, self.app, self.layer = imgui, app, layer
        self.threshold = CLEAN_THRESHOLD  # Regler „Schwelle“ (nur der Startwert des Reglers, kein Dokumentzustand)

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
        st = wm.state(app)
        if st.blocker is not None:
            imgui.push_text_wrap_pos(imgui.get_font_size() * 22.0)
            imgui.text_colored(imgui.ImVec4(*_WARN), f"Malen gesperrt: {st.blocker}")
            imgui.pop_text_wrap_pos()
        self._bones(st)
        imgui.separator()
        self._brush(st)
        imgui.separator()
        sym = st.symmetry_text
        if imgui.button(f"{sym}##sym"):
            wm.cycle_symmetry(app)
            self.layer.last_note = app.status_message
        if imgui.is_item_hovered():
            imgui.set_tooltip("Shift+S: aus -> X -> ...; ein Knochen auf der Ebene malt beide Seiten")
        imgui.same_line()
        if imgui.button("Pose##rest" if not st.posed else "Ruhe##rest"):
            wm.toggle_rest(app)
            self.layer.last_note = app.status_message
        if imgui.is_item_hovered():
            imgui.set_tooltip("Taste 6: Ruhe <-> letzte Pose; in der Pose bewegt sich das Mesh beim Malen mit")
        imgui.separator()
        imgui.set_next_item_width(110.0)
        changed, value = imgui.slider_float("Schwelle", self.threshold, wm.CLEAN_RANGE[0], wm.CLEAN_RANGE[1], "%.3f")
        self.layer._remember("weight_threshold", 0)
        if changed:
            self.threshold = value
        imgui.same_line()
        imgui.begin_disabled(st.stroking)
        pressed = imgui.button("Aufräumen")
        imgui.end_disabled()
        self.layer._remember("weight_clean", 0)
        if imgui.is_item_hovered(imgui.HoveredFlags_.allow_when_disabled):
            imgui.set_tooltip("Kleine Restanteile unter der Schwelle entfernen (alle Knochen, ein Strg+Z)")
        if pressed and not st.stroking:
            wm.clean(app, self.threshold)
            self.layer.last_note = app.status_message
        imgui.separator()
        if imgui.button("Raum schließen"):
            app.close_weight_room()

    def _bones(self, st: wm.WeightPanelState) -> None:
        imgui, app = self.imgui, self.app
        if not st.rows:
            imgui.text_disabled("Noch kein Knochen (Bone-Panel: Kette starten)")
            return
        imgui.text_disabled("Knochen (Strg+LMB: der stärkste am Punkt)")
        height = min(len(st.rows), 8) * imgui.get_text_line_height_with_spacing() + 6.0
        imgui.begin_child("##weight_bones", imgui.ImVec2(_WIDTH + 40.0, height))
        for row in st.rows:
            color = _CURRENT if row.current else _PLAIN
            imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(*color))
            label = ("    " * row.depth) + row.name + (" (aus)" if row.hidden else "") + f"##wb{int(row.id)}"
            clicked = imgui.selectable(label, row.current)[0]
            imgui.pop_style_color()
            self.layer._remember("weight_bone", int(row.id))
            if clicked and not row.current and not st.stroking:
                wm.choose_bone(app, row.id)
                self.layer.last_note = app.status_message
        imgui.end_child()

    def _brush(self, st: wm.WeightPanelState) -> None:
        imgui, app = self.imgui, self.app
        for op, label in wm.OPERATION_ROWS:
            if imgui.radio_button(f"{label}##op", st.operation == op):
                wm.set_operation(app, op)
            self.layer._remember("weight_op", op)
            if imgui.is_item_hovered():
                imgui.set_tooltip(wm.OPERATION_HINTS[op])
            imgui.same_line()
        imgui.new_line()
        if st.operation == "replace":
            imgui.set_next_item_width(_WIDTH)
            changed, value = imgui.slider_float("Wert", st.value, 0.0, 1.0, "%.2f")
            if changed:
                app.set_weight_brush(value=value)
        imgui.set_next_item_width(_WIDTH)
        changed, step = imgui.slider_int("Radius", st.radius_step, 0, len(RADIUS_STEPS_PERCENT) - 1, st.radius_label)
        if changed:
            app.set_weight_brush(radius_step=step)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Prozent des Objektradius; Shift+Rad im Viewport")
        for field, label, hint in (("flow", "Stärke", "pro Tupfer; baut sich im Strich auf (Alt+Rad im Viewport)"),
                                   ("opacity", "Deckkraft", "was ein Strich höchstens aufträgt"),
                                   ("hardness", "Härte", "der volle Kern des Pinsels")):
            imgui.set_next_item_width(_WIDTH)
            changed, value = imgui.slider_float(label, float(getattr(st, field)) * 100.0, 0.0, 100.0, "%.0f %%")
            if changed:
                app.set_weight_brush(**{field: value / 100.0})
            if imgui.is_item_hovered():
                imgui.set_tooltip(hint)
        imgui.set_next_item_width(_WIDTH)
        if imgui.begin_combo("Kurve", wm.curve_label(st.curve)):
            for curve in wm.CURVES:
                if imgui.selectable(wm.curve_label(curve), curve == st.curve)[0]:
                    app.set_weight_brush(curve=curve)
            imgui.end_combo()
        changed, on = imgui.checkbox("nur zusammenhängend", st.connected)
        if changed:
            app.set_weight_brush(connected=on)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Nur der Teil, der mit der getroffenen Fläche verbunden ist (Ober- / Unterlippe, Lider)")
        changed, on = imgui.checkbox("nur Vorderseite", st.front_only)
        if changed:
            app.set_weight_brush(front_only=on)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Punkte, deren Normale vom Betrachter weg zeigt, bleiben unberührt")
