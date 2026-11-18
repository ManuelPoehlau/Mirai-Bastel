"""Das Bone- und Skin-Panel (Bone tool 01, 2026-11-17, AD-028 Nachtrag; Layout `PROVISIONAL`, Manu: „ein provisorisches Layout
reicht“; keine Taste: Knopf „Bone“ in der Leiste).

Oben das Kettenwerkzeug („Kette starten“ als Kind des aktuellen Knochens oder als neue Wurzel; läuft es, „Kette beenden“ =
Esc) und das Einrasten an Pivots und Knochenenden. Darunter der aktuelle Knochen: Auswahl (Liste, davor / danach), Name, Parent
(mit Zyklus-Sperre), Kopf und Spitze als Zahlen (Welt), Roll in Grad, Ausblenden, Löschen. Zahlen und Namen gelten beim
Verlassen des Felds (Enter oder Klick daneben): ein Undo-Schritt je Änderung; nur in der Ruhe-Pose (AD-028 §7). Unten das
Skinning: Gewichte aus der Gruppe mit Breite, Gewicht setzen mit Wert (Auswahl, mit Soft das Soft-Feld), Gewichtsansicht.
Jeder Knopf ruft denselben `Application`-Weg wie die Taste bzw. das Werkzeug, mit denselben Ablehnungen; das Panel hält
keinen Dokumentzustand (nur die Eingabepuffer der Felder und die Regler-Startwerte).
"""

from __future__ import annotations

from . import bone_model as bm

_CURRENT = (1.0, 0.8, 0.43, 1.0)  # wie das Edit-Objekt im Outliner
_PLAIN = (0.88, 0.9, 0.94, 1.0)
_FIELD_WIDTH = 78.0
AXIS_HINTS = {
    "free": "Die Spitze folgt dem Cursor (Einrasten und Mesh wie bisher)",
    "x": "Spitze auf der X-Achse durch den Kopf; die Länge bestimmt der Cursor",
    "y": "Spitze auf der Y-Achse durch den Kopf; die Länge bestimmt der Cursor",
    "z": "Spitze auf der Z-Achse durch den Kopf; die Länge bestimmt der Cursor",
    "object": "Spitze auf der Achse des gewählten Objekts durch seinen Pivot (lokale +Z; bei Augen die Blickachse); "
              "ohne Auswahl das Objekt, an dessen Pivot der Kopf sitzt. Die Länge bestimmt der Cursor",
}
_AXES = ("x", "y", "z")


class BonePanel:
    def __init__(self, imgui, app, layer) -> None:
        """`layer` (`ImguiLayer`): `_remember` (Rechtecke für Tests) und `last_note`."""
        self.imgui, self.app, self.layer = imgui, app, layer
        self.buf: dict = {}  # Eingabepuffer der Zahlen- und Textfelder: (Knochen, Feld[, Achse]) -> Wert, nur während der Eingabe
        self.falloff: float | None = None  # Regler „Breite“ (%), None = die Soft-Radius-Stufe
        self.weight = 1.0  # Regler „Wert“

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
        st = bm.state(app)
        self._chain(st)
        imgui.separator()
        if not st.has_bones:
            imgui.text_disabled("Noch kein Knochen: „Kette starten“ und im Viewport klicken")
        else:
            self._bone(st)
        imgui.separator()
        self._skin(st)

    # -- Kettenwerkzeug ---------------------------------------------------------------------------------------

    def _chain(self, st: bm.BonePanelState) -> None:
        imgui, app = self.imgui, self.app
        imgui.text_disabled("Bone-Kette (Klick = Kopf, dann je Klick eine Spitze; Esc beendet)")
        if st.chain_active:
            self._button("Kette beenden (Esc)", True, "chain_end", 0, None, app.end_bone_chain)
        else:
            blocker = st.chain_blocker
            under = f"Kind von {st.chain_parent_name!r}" if st.chain_parent_name is not None else "ohne Parent"
            self._button(f"Kette starten ({under})", blocker is None, "chain", 0, blocker,
                         lambda: app.start_bone_chain(False))
            if st.chain_parent_name is not None:
                imgui.same_line()
                self._button("Neue Wurzel", blocker is None, "chain_root", 0, blocker or "Kette ohne Parent starten",
                             lambda: app.start_bone_chain(True))
        imgui.text("Spitze:")
        for value, label in bm.AXIS_CHOICES:
            imgui.same_line()
            if imgui.radio_button(label + "##axis", st.chain_axis == value):
                bm.set_chain_axis(app, value)
            self.layer._remember("bone_axis", value)
            if imgui.is_item_hovered():
                imgui.set_tooltip(AXIS_HINTS[value])
        if st.chain_axis == "object":
            imgui.text_disabled(f"Objekt-Achse von: {st.axis_object!r}" if st.axis_object else
                                "Objekt-Achse: ein Objekt wählen (Modus 4, Outliner) oder am Pivot beginnen")
        changed, on = imgui.checkbox("Einrasten an Objekt-Pivot und Knochenenden", st.chain_snap)
        self.layer._remember("bone_snap", 0)
        if changed:
            app.bone_chain_snap = on
        if imgui.is_item_hovered():
            imgui.set_tooltip("Objekt-Pivot (Augapfelmitte, Zahn, ...) und Kopf / Spitze anderer Knochen; Shift = Punkt / Kante des Meshs")

    # -- aktueller Knochen --------------------------------------------------------------------------------------

    def _bone(self, st: bm.BonePanelState) -> None:
        imgui, app = self.imgui, self.app
        cur = st.current
        imgui.text_disabled(f"Aktueller Knochen · {st.count_text}")
        label = cur.name if cur is not None else "-"
        imgui.set_next_item_width(190.0)
        if imgui.begin_combo("##current", label):
            for row in st.rows:
                imgui.push_id(f"r{int(row.id)}")
                text = "  " * row.depth + row.name + ("  (aus)" if row.hidden else "")
                if imgui.selectable(text, row.current)[0]:
                    app.select_bone(row.id)
                imgui.pop_id()
            imgui.end_combo()
        self.layer._remember("bone_current", 0)
        imgui.same_line()
        if imgui.small_button("<"):
            bm.step_bone(app, -1)
        imgui.same_line()
        if imgui.small_button(">"):
            bm.step_bone(app, 1)
        if cur is None:
            return
        blocker = st.edit_blocker
        if blocker is not None:
            imgui.text_colored(imgui.ImVec4(1.0, 0.7, 0.3, 1.0), "Nur in der Ruhe-Pose editierbar")
            if imgui.is_item_hovered():
                imgui.set_tooltip(blocker)
        imgui.begin_disabled(blocker is not None)
        self._name(cur)
        self._parent(st, cur)
        self._vector("Kopf", "head", cur, cur.head, bm.set_head)
        self._vector("Spitze", "tail", cur, cur.tail, bm.set_tail)
        imgui.text_disabled(f"Länge {cur.length:.4f}")
        self._roll(cur)
        imgui.end_disabled()
        target = f" an {st.axis_object!r}" if st.axis_object else ""
        self._button(f"Ausrichten{target}", st.align_blocker is None, "align", 0,
                     st.align_blocker or "Richtung des Knochens = lokale +Z des gewählten Objekts (bei Augen die Blickachse); "
                     "Kopf, Länge und Roll bleiben (ein Undo-Schritt, nur in der Ruhe-Pose)",
                     lambda: bm.align_to_object_axis(app, cur.id))
        changed, hidden = imgui.checkbox("Ausgeblendet", cur.hidden)
        self.layer._remember("bone_hidden", 0)
        if changed:
            app.set_bones_hidden([cur.id], hidden)
            self.layer.last_note = app.status_message
        self._button(f"Knochen {cur.name!r} löschen", st.edit_blocker is None, "delete", 0,
                     blocker or "Gewichte gehen an den Parent; Strg+Z holt alles zurück",
                     lambda: app.delete_bone(cur.id))

    def _name(self, cur: bm.BoneDetail) -> None:
        imgui, app = self.imgui, self.app
        key = (int(cur.id), "name")
        imgui.set_next_item_width(190.0)
        changed, text = imgui.input_text("Name", self.buf.get(key, cur.name))
        self.layer._remember("bone_name", 0)
        if changed:
            self.buf[key] = text
        if imgui.is_item_deactivated_after_edit():
            app.rename_bone(cur.id, self.buf.pop(key, text))
            self.layer.last_note = app.status_message
        elif imgui.is_item_deactivated():
            self.buf.pop(key, None)  # Esc: verworfen

    def _parent(self, st: bm.BonePanelState, cur: bm.BoneDetail) -> None:
        imgui, app = self.imgui, self.app
        imgui.set_next_item_width(190.0)
        if imgui.begin_combo("Parent", cur.parent_name or "(keiner, Wurzel)"):
            for pid, name in st.parent_choices:
                imgui.push_id("none" if pid is None else f"p{int(pid)}")
                if imgui.selectable(name, pid == cur.parent)[0] and pid != cur.parent:
                    bm.set_parent(app, cur.id, pid)
                    self.layer.last_note = app.status_message
                imgui.pop_id()
            imgui.end_combo()
        self.layer._remember("bone_parent", 0)

    def _vector(self, label: str, field: str, cur: bm.BoneDetail, value: tuple, commit) -> None:
        """Drei Zahlenfelder; eine Komponente gilt beim Verlassen ihres Felds, die anderen bleiben exakt."""
        imgui, app = self.imgui, self.app
        edits: dict = {}
        imgui.text(f"{label:<7}")
        for i, axis in enumerate(_AXES):
            imgui.same_line()
            key = (int(cur.id), field, i)
            imgui.set_next_item_width(_FIELD_WIDTH)
            changed, number = imgui.input_float(f"##{field}{axis}", self.buf.get(key, value[i]), 0.0, 0.0, "%.4f")
            self.layer._remember(f"bone_{field}", i)
            if changed:
                self.buf[key] = number
            if imgui.is_item_deactivated_after_edit():
                edits[i] = self.buf.pop(key, number)
            elif imgui.is_item_deactivated():
                self.buf.pop(key, None)
        if edits:
            commit(app, cur.id, value, edits)
            self.layer.last_note = app.status_message

    def _roll(self, cur: bm.BoneDetail) -> None:
        imgui, app = self.imgui, self.app
        key = (int(cur.id), "roll")
        imgui.set_next_item_width(_FIELD_WIDTH)
        changed, degrees = imgui.input_float("Roll (Grad)", self.buf.get(key, cur.roll_degrees), 0.0, 0.0, "%.2f")
        self.layer._remember("bone_roll", 0)
        if changed:
            self.buf[key] = degrees
        if imgui.is_item_deactivated_after_edit():
            bm.set_roll_degrees(app, cur.id, cur.roll_degrees, self.buf.pop(key, degrees))
            self.layer.last_note = app.status_message
        elif imgui.is_item_deactivated():
            self.buf.pop(key, None)

    # -- Skinning -----------------------------------------------------------------------------------------------

    def _skin(self, st: bm.BonePanelState) -> None:
        imgui, app = self.imgui, self.app
        imgui.text_disabled("Skinning (aktueller Knochen)")
        enabled = st.can_weights
        group = f"Gruppe {st.group!r}" if st.group is not None else "keine Gruppe (Strg+G)"
        imgui.text(f"Gewichte aus {group}")
        imgui.set_next_item_width(130.0)
        start = st.falloff_percent if self.falloff is None else self.falloff
        changed, value = imgui.slider_float("Breite %", start, 0.0, 200.0, "%.0f %%")
        self.layer._remember("bone_falloff", 0)
        if changed:
            self.falloff = value
        imgui.same_line()
        self._button("Anwenden", enabled and st.group is not None, "falloff", 0,
                     "Gewichte des aktuellen Knochens aus der Gruppe, Falloff in % des Mesh-Radius (ein Undo-Schritt)",
                     lambda: app.weights_from_group_value(start))
        points = f"{st.selected_points} Punkt{'e' if st.selected_points != 1 else ''}" + (" (Soft)" if st.soft_on else "")
        imgui.set_next_item_width(130.0)
        changed, self.weight = imgui.slider_float("Wert", self.weight, 0.0, 1.0, "%.2f")
        self.layer._remember("bone_weight", 0)
        imgui.same_line()
        self._button(f"Auf Auswahl ({points})", enabled and st.selected_points > 0, "weight", 0,
                     "Gewicht des aktuellen Knochens auf der Auswahl (1/2/3), mit Soft auf dem Soft-Feld; ein Undo-Schritt",
                     lambda: app.set_weight_value(self.weight))
        changed, on = imgui.checkbox("Gewichtsansicht", st.weight_view)
        self.layer._remember("bone_weightview", 0)
        if changed:
            bm.toggle_weight_view(app)
            self.layer.last_note = app.status_message

    def _button(self, label: str, enabled: bool, kind: str, key, hint, action, small: bool = False) -> None:
        imgui = self.imgui
        imgui.begin_disabled(not enabled)
        pressed = imgui.small_button(label) if small else imgui.button(label)
        imgui.end_disabled()
        self.layer._remember(f"bone_{kind}", key)
        if hint and imgui.is_item_hovered(imgui.HoveredFlags_.allow_when_disabled):
            imgui.set_tooltip(hint)
        if pressed and enabled:
            action()
            self.layer.last_note = self.app.status_message
