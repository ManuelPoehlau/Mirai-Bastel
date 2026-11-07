"""Das Morph-Panel (AD-030 §13, Manu 2026-11-07): die Morph-Ziele des Edit-Objekts mit einem Regler pro Ziel.

Zeile: Name (Klick = aktuell wie Shift+N; Doppelklick = Umbenennen im Textfeld des Layers), Regler 0-100 % (Ziehen =
Gewicht live, Strg+Klick = Zahl tippen), `S` = Solo, „Bearbeiten“ = Tab für dieses Ziel („Zurück“ in der Ansicht). Oben
„+ Neues Ziel“ und „Alle 0 %“, unten „Löschen“ für das aktuelle Ziel. Ohne Ziele nur „+ Neues Ziel“. Jeder Knopf ruft
denselben `Application`-Weg wie die Taste, mit denselben Ablehnungen; das Panel hält keinen Dokumentzustand.
"""

from __future__ import annotations

from . import morph_model as mm

_CURRENT = (1.0, 0.8, 0.43, 1.0)  # wie das Edit-Objekt im Outliner
_PLAIN = (0.88, 0.9, 0.94, 1.0)
_SLIDER_WIDTH = 130.0


class MorphPanel:
    def __init__(self, imgui, app, layer) -> None:
        """`layer` (`ImguiLayer`): sein Textfeld zum Umbenennen (`_name_cell`, ein aktives Feld für alle Panels) und
        `_remember` (Rechtecke für Tests)."""
        self.imgui, self.app, self.layer = imgui, app, layer

    def draw(self) -> None:
        imgui, app = self.imgui, self.app
        st = mm.state(app)
        imgui.text_disabled(st.header)
        self._button("+ Neues Ziel", st.can_create, "new", 0, "nur an der Basis (Tab)" if st.view_open else None,
                     app.create_morph_target)
        if not st.has_targets:
            imgui.text_disabled("Keine Morph-Ziele (Strg+N)")
            return
        imgui.same_line()
        self._button("Alle 0 %", True, "zero", 0, None, app.zero_morph_weights)
        imgui.separator()
        flags = imgui.TableFlags_.sizing_fixed_fit | imgui.TableFlags_.no_saved_settings
        if imgui.begin_table("##targets", 4, flags):
            imgui.table_setup_column("name", imgui.TableColumnFlags_.width_stretch)
            imgui.table_setup_column("weight", imgui.TableColumnFlags_.width_fixed, _SLIDER_WIDTH)
            for row in st.rows:
                self._row(row, st)
            imgui.end_table()
        imgui.separator()
        current = st.current
        if current is not None:
            self._button(f"Löschen {current.name!r}", st.can_lifecycle, "delete", 0,
                         "nur an der Basis (Tab)" if st.view_open else None,
                         lambda: app.delete_morph_target(current.lid))
            imgui.same_line()
        imgui.text_disabled(st.count_text)

    def _row(self, row: mm.MorphRow, st: mm.MorphPanelState) -> None:
        imgui, app, layer = self.imgui, self.app, self.layer
        imgui.push_id(f"m{row.lid}")
        imgui.table_next_row()
        imgui.table_next_column()
        color = imgui.ImVec4(*(_CURRENT if row.current else _PLAIN))
        label = ("> " if row.current else "  ") + row.name
        if st.can_lifecycle:
            action = layer._name_cell(("m", row.lid), label, row.name, row.current, color)
        else:  # in der Ansicht kein Umbenennen (Basis only): nur Klick
            imgui.push_style_color(imgui.Col_.text, color)
            clicked, _ = imgui.selectable(label, row.current, imgui.SelectableFlags_.allow_overlap)
            imgui.pop_style_color()
            action = "click" if clicked else None
        layer._remember("morph_name", row.lid)
        if action == "click":
            app.select_morph_target(row.lid)
        elif isinstance(action, tuple):
            app.rename_morph_target(action[1], row.lid)
        imgui.table_next_column()
        imgui.set_next_item_width(_SLIDER_WIDTH)
        changed, value = imgui.slider_int("##w", row.weight, 0, 100, "%d %%")
        layer._remember("morph_weight", row.lid)
        if changed and value != row.weight:
            app.set_morph_weight(value, row.lid, quiet=True)
        if imgui.is_item_deactivated_after_edit():
            app.set_morph_weight(app_weight(app, row.lid), row.lid)  # eine Statuszeile beim Loslassen
        imgui.table_next_column()
        if row.solo:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.75, 0.55, 0.15, 1.0))
        if imgui.small_button("S"):
            app.solo_morph_target(row.lid)
        if row.solo:
            imgui.pop_style_color()
        layer._remember("morph_solo", row.lid)
        imgui.set_item_tooltip("Solo: nur dieses Ziel zeigen (nochmal: Gewichte wie vorher)")
        imgui.table_next_column()
        if row.editing:
            self._button("Zurück", True, "edit", row.lid, "zurück zur Basis (Tab)", app.leave_morph_target, small=True)
        else:
            def edit() -> None:
                app.select_morph_target(row.lid)
                app.edit_morph_target()

            if st.view_open:
                hint = "in der Ansicht wechselt ein Klick auf den Namen das Ziel"
            elif not st.can_edit:
                hint = "aus 1/2/3 (Punkte/Kanten/Flächen)"
            else:
                hint = "daneben bearbeiten (Tab)"
            self._button("Bearbeiten", st.can_edit and not st.view_open, "edit", row.lid, hint, edit, small=True)
        imgui.pop_id()

    def _button(self, label: str, enabled: bool, kind: str, key, hint, action, small: bool = False) -> None:
        imgui = self.imgui
        imgui.begin_disabled(not enabled)
        pressed = imgui.small_button(label) if small else imgui.button(label)
        imgui.end_disabled()
        self.layer._remember(f"morph_{kind}", key)
        if hint and imgui.is_item_hovered(imgui.HoveredFlags_.allow_when_disabled):
            imgui.set_tooltip(hint)
        if pressed and enabled:
            action()
            self.layer.last_note = self.app.status_message


def app_weight(app, lid) -> int:
    return next((w for l, _, w, _ in app.morph_target_rows() if l == lid), 0)
