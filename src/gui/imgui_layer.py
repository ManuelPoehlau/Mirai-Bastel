"""Dear ImGui (imgui-bundle) im Production-Fenster (AD-030, Manu 2026-11-07, `PROVISIONAL`).

`install_handlers(..., gui=layer)` ruft `layer.attach()` (Eingabe über `window.push_handlers`, oben auf dem Stack) und
`layer.draw()` am Ende von `on_draw`, unter einem offenen Menü. Imports von imgui und pyglet.gl sind lazy (Muster
`hud.py`), damit Tests ohne GL und ohne imgui laufen.

Eingabe: `InputGate` entscheidet pro Ereignis, wer es bekommt (Kriterium 1). Zeichnen: nach dem Viewport und der HUD,
mit Sicherung und Wiederherstellung des GL-Zustands (Kriterium 2).
"""

from __future__ import annotations

import time
from typing import Callable

from . import outliner_model as om
from .input_gate import InputGate, rect_hit
from .menus import ATTACH_ENTRIES, attach_request

#: pyglet-Modifier-Bits (pyglet.window.key.MOD_*), hier lokal, damit der Modul-Import ohne pyglet geht.
_MOD_SHIFT, _MOD_CTRL, _MOD_ALT = 1, 2, 4


def modifiers_from_pyglet(bits: int) -> frozenset[str]:
    return frozenset(
        name for name, bit in (("shift", _MOD_SHIFT), ("ctrl", _MOD_CTRL), ("alt", _MOD_ALT)) if bits & bit
    )


GL_STATE_NAMES = (
    "depth_test", "blend", "cull_face", "scissor_test", "blend_src", "blend_dst", "program", "vao", "array_buffer",
    "active_texture", "viewport", "depth_mask", "polygon_mode",
)


def snapshot_gl_state() -> dict:
    """Der GL-Zustand, den ein Overlay typischerweise leckt (Kriterium 2). Für den Vergleich vor/nach dem Layer."""
    from pyglet import gl

    def geti(name, count=1):
        buf = (gl.GLint * count)()
        gl.glGetIntegerv(name, buf)
        return buf[0] if count == 1 else tuple(buf)

    return {
        "depth_test": bool(gl.glIsEnabled(gl.GL_DEPTH_TEST)),
        "blend": bool(gl.glIsEnabled(gl.GL_BLEND)),
        "cull_face": bool(gl.glIsEnabled(gl.GL_CULL_FACE)),
        "scissor_test": bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST)),
        "blend_src": geti(gl.GL_BLEND_SRC_RGB),
        "blend_dst": geti(gl.GL_BLEND_DST_RGB),
        "program": geti(gl.GL_CURRENT_PROGRAM),
        "vao": geti(gl.GL_VERTEX_ARRAY_BINDING),
        "array_buffer": geti(gl.GL_ARRAY_BUFFER_BINDING),
        "active_texture": geti(gl.GL_ACTIVE_TEXTURE),
        "viewport": geti(gl.GL_VIEWPORT, 4),
        "depth_mask": geti(gl.GL_DEPTH_WRITEMASK),
        "polygon_mode": geti(gl.GL_POLYGON_MODE, 2),
    }


def restore_gl_state(state: dict) -> None:
    from pyglet import gl

    for flag, cap in (
        ("depth_test", gl.GL_DEPTH_TEST), ("blend", gl.GL_BLEND), ("cull_face", gl.GL_CULL_FACE),
        ("scissor_test", gl.GL_SCISSOR_TEST),
    ):
        (gl.glEnable if state[flag] else gl.glDisable)(cap)
    gl.glBlendFunc(state["blend_src"], state["blend_dst"])
    gl.glUseProgram(state["program"])
    gl.glBindVertexArray(state["vao"])
    gl.glBindBuffer(gl.GL_ARRAY_BUFFER, state["array_buffer"])
    gl.glActiveTexture(state["active_texture"])
    gl.glViewport(*state["viewport"])
    gl.glDepthMask(state["depth_mask"])
    gl.glPolygonMode(gl.GL_FRONT_AND_BACK, state["polygon_mode"][0])


class ImguiLayer:
    """Das Panel-System. `attach()` einmal nach `install_handlers`; `open_panel` schaltet den Outliner (kein Key:
    ein kleiner Knopf links oben, der Layer belegt keine Taste, Manus Freigabe fehlt)."""

    PANEL_POS = (12.0, 60.0)
    PANEL_SIZE = (280.0, 360.0)

    def __init__(self, window, app, guard_gl: bool = True, open_panel: bool = True,
                 blocked: Callable[[], bool] | None = None, services=None) -> None:
        """`blocked()`: True, solange etwas Modales (ein Menü) die Eingabe hat; das Panel fängt dann nichts.
        `services` (`gui.menus.Services`): schaltet Menüleiste, SPACE-Menü und GoZ-Panel ein; ohne bleibt es der Outliner."""
        self.window, self.app = window, app
        self.services = services
        self.menus = None
        self.goz = None
        self.goz_open = False
        self.morph = None  # AD-030 §13: das Morph-Panel (Knopf „Morph“, Standard offen)
        self.morph_open = True
        self.popup_open = False  # ein Menü/Dialog des Layers ist offen: ihm gehört die ganze Maus (letzter Frame)

        self._blocked = blocked or (lambda: False)
        self.guard_gl = guard_gl
        self.open_panel = open_panel
        self.collapsed: set = set()  # reiner Ansichtszustand des Panels (kein Dokumentzustand)
        self.collapsed_bones: set = set()
        self.skeleton_open = True
        self.editing: tuple | None = None  # ("o"|"b", id): die Zeile im Umbenennen (Doppelklick)
        self.edit_buf = ""
        self._edit_focus = False
        self.filter_text = ""
        self.panel_rects: list[tuple] = []  # imgui-Koordinaten (oben links) des letzten Frames
        self.frame_ms: list[float] = []
        self.last_note = ""
        self.item_rects: dict = {}  # ("eye"|"row"|"filter", id) -> (x, y, w, h), nur für Tests und Messung
        self._ctx = None
        self._renderer = None
        self._attached = False
        self.gate = InputGate(self._over_panel, self._keyboard_wanted)

    # -- Aufbau ----------------------------------------------------------------------------------------------
    def _ensure(self) -> None:
        if self._ctx is not None:
            return
        from imgui_bundle import imgui

        self._imgui = imgui
        self._ctx = imgui.create_context()
        io = imgui.get_io()
        io.set_ini_filename("")  # keine imgui.ini im Repo
        self._keys = _key_map(imgui)
        # C++-Renderer von imgui-bundle (kein PyOpenGL): er nutzt den aktuellen GL-Kontext, also pyglets.
        imgui.backends.opengl3_init("#version 330")
        self._last_time = time.perf_counter()
        self._style()
        self._dpi_scale()
        from .morph_panel import MorphPanel

        self.morph = MorphPanel(imgui, self.app, self)
        if self.services is not None:
            from .goz_panel import GozPanel
            from .menus import Menus

            self.menus = Menus(imgui, self.app, self.services)
            if self.services.zbrush is not None:
                self.goz = GozPanel(imgui, self.services.zbrush)

    def _dpi_scale(self) -> None:
        w, _ = self.window.get_size()
        fw, _ = self.window.get_framebuffer_size()
        st = self._imgui.get_style()
        if hasattr(st, 'font_scale_dpi') and fw > w:
            st.font_scale_dpi = fw / w  # HiDPI: ungeprüft auf echter HiDPI-Hardware (Artist-Frage)

    def _style(self) -> None:
        imgui = self._imgui
        imgui.style_colors_dark()
        st = imgui.get_style()
        st.window_rounding = 4.0
        st.frame_rounding = 3.0
        st.window_border_size = 0.0
        c = imgui.Col_
        v = lambda r, g, b, a=255: imgui.ImVec4(r / 255, g / 255, b / 255, a / 255)  # noqa: E731
        st.set_color_(c.window_bg, v(18, 20, 26, 215))  # HUD `_BG`
        st.set_color_(c.title_bg, v(18, 20, 26, 230))
        st.set_color_(c.title_bg_active, v(28, 32, 42, 240))
        st.set_color_(c.header, v(60, 80, 110, 160))
        st.set_color_(c.header_hovered, v(70, 95, 130, 200))
        st.set_color_(c.header_active, v(80, 110, 150, 230))
        st.set_color_(c.text, v(225, 230, 240))  # HUD `_VALUE`

    def attach(self, blocked: Callable[[], bool] | None = None) -> None:
        """Eingabe-Handler oben auf den Stack (laufen vor denen aus `install_handlers`)."""
        if self._attached:
            return
        self._attached = True
        if blocked is not None:
            self._blocked = blocked
        w = self.window
        w.push_handlers(
            on_mouse_press=self.on_mouse_press, on_mouse_release=self.on_mouse_release,
            on_mouse_drag=self.on_mouse_drag, on_mouse_motion=self.on_mouse_motion,
            on_mouse_scroll=self.on_mouse_scroll, on_key_press=self.on_key_press,
            on_key_release=self.on_key_release, on_text=self.on_text, on_text_motion=self.on_text_motion,
        )

    def close(self) -> None:
        """Baut Renderer und Kontext ab (nötig, wenn ein Prozess mehrere Fenster nacheinander baut, z.B. Tests)."""
        if self._ctx is None:
            return
        self.window.switch_to()
        self._imgui.backends.opengl3_shutdown()
        self._imgui.destroy_context(self._ctx)
        self._ctx = None

    # -- Eingabe -----------------------------------------------------------------------------------------------
    def _gesture_running(self) -> bool:
        """Eine Geste von `Application` (W/E/R/T gehalten, Knife, Maus-Geste) hat Vorrang: das Panel fängt dann keine Maus,
        sonst stockt Move/Rotate/Scale und der Cursor-Wrap, sobald der Zeiger über das Panel läuft."""
        app = self.app
        return app.interaction_owner is not None or app.pointer.active

    def _over_panel(self, x: float, y: float) -> bool:
        if self._gesture_running() or self._blocked():
            return False
        if self.popup_open:
            return True
        return any(rect_hit(r, x, self.window.height - y) for r in self.panel_rects)

    def _keyboard_wanted(self) -> bool:
        return self._ctx is not None and self._imgui.get_io().want_text_input

    def _feed_mods(self, bits: int) -> None:
        io = self._imgui.get_io()
        mods = modifiers_from_pyglet(bits)
        io.add_key_event(self._imgui.Key.mod_shift, "shift" in mods)
        io.add_key_event(self._imgui.Key.mod_ctrl, "ctrl" in mods)
        io.add_key_event(self._imgui.Key.mod_alt, "alt" in mods)

    def _pos(self, x, y) -> None:
        self._imgui.get_io().add_mouse_pos_event(float(x), self.window.height - float(y))

    def _mouse_button(self, button: int, down: bool) -> None:
        index = {1: 0, 4: 1, 2: 2}.get(button, 0)  # pyglet: LEFT=1, MIDDLE=2, RIGHT=4
        self._imgui.get_io().add_mouse_button_event(index, down)

    def _key(self, symbol: int, down: bool) -> None:
        key = self._keys.get(symbol)
        if key is not None:
            self._imgui.get_io().add_key_event(key, down)

    def on_mouse_motion(self, x, y, dx, dy):
        if self._ctx is None:
            return
        was = self.gate.hovering_panel
        self._pos(x, y)
        if self.gate.motion(x, y):
            if not was:
                self.app.pointer_leave()  # kein Hover-Pick unter dem Panel
            return True

    def on_mouse_press(self, x, y, button, modifiers):
        if self._ctx is None:
            return
        self._pos(x, y)
        self._feed_mods(modifiers)
        if self.gate.press(button, x, y):
            self._mouse_button(button, True)
            return True

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self._ctx is None:
            return
        self._pos(x, y)
        down = tuple(b for b in (1, 2, 4) if buttons & b)
        if self.gate.drag(down):
            return True

    def on_mouse_release(self, x, y, button, modifiers):
        if self._ctx is None:
            return
        self._pos(x, y)
        if self.gate.release(button):
            self._mouse_button(button, False)
            return True

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        if self._ctx is None:
            return
        if self.gate.scroll(x, y):
            self._imgui.get_io().add_mouse_wheel_event(scroll_x, scroll_y)
            return True

    def on_key_press(self, symbol, modifiers):
        if self._ctx is None:
            return
        self._feed_mods(modifiers)
        if self.gate.key_press(symbol):
            self._key(symbol, True)
            return True

    def on_key_release(self, symbol, modifiers):
        if self._ctx is None:
            return
        if self.gate.key_release(symbol):
            self._key(symbol, False)
            return True

    def on_text(self, text):
        if self._ctx is not None and self._keyboard_wanted():
            [self._imgui.get_io().add_input_character(ord(ch)) for ch in text]
            return True

    def on_text_motion(self, motion):
        # Pfeile/Pos1/Ende im Textfeld laufen als Key-Events (on_key_press); hier nur schlucken, solange es aktiv ist.
        if self._ctx is not None and self._keyboard_wanted():
            return True

    # -- Menüs von außen (`main.py`) ---------------------------------------------------------------------------
    @property
    def has_menus(self) -> bool:
        return self.services is not None

    def open_space_menu(self, x: float, y: float) -> None:
        """SPACE: das Menü am Cursor (pyglet-Koordinaten, y nach oben)."""
        if self.services is not None:
            self._ensure()
            self.menus.open_space(float(x), self.window.height - float(y))

    def save(self) -> None:
        """Strg+S: speichern, bei einer neuen Szene mit Namensdialog."""
        self._ensure()
        self.menus.save()

    def popup_key(self) -> None:
        """Esc oder SPACE bei offenem Popup: alle Menüs und Dialoge des Layers schließen (im nächsten Frame)."""
        if self.menus is not None:
            self.menus.close_all()

    # -- Zeichnen ----------------------------------------------------------------------------------------------
    def draw(self) -> None:
        self._ensure()
        t0 = time.perf_counter()
        before = snapshot_gl_state() if self.guard_gl else None
        imgui = self._imgui
        io = imgui.get_io()
        now = time.perf_counter()
        io.delta_time = max(now - self._last_time, 1e-4)
        self._last_time = now
        w, h = self.window.get_size()
        fw, fh = self.window.get_framebuffer_size()
        io.display_size = imgui.ImVec2(w, h)
        io.display_framebuffer_scale = imgui.ImVec2(fw / max(w, 1), fh / max(h, 1))
        imgui.backends.opengl3_new_frame()
        imgui.new_frame()
        self._build()
        imgui.render()
        imgui.backends.opengl3_render_draw_data(imgui.get_draw_data())
        if before is not None:
            restore_gl_state(before)
        self.frame_ms.append((time.perf_counter() - t0) * 1000.0)

    def _build(self) -> None:
        imgui = self._imgui
        rects: list[tuple] = []
        bar_h = 0.0
        if self.menus is not None:
            bar = self.menus.bar()
            rects.append(bar)
            bar_h = bar[3]
        imgui.set_next_window_pos(imgui.ImVec2(8, bar_h + 6), imgui.Cond_.always)
        flags = (imgui.WindowFlags_.no_decoration | imgui.WindowFlags_.no_background
                 | imgui.WindowFlags_.always_auto_resize | imgui.WindowFlags_.no_move
                 | imgui.WindowFlags_.no_saved_settings | imgui.WindowFlags_.no_nav)
        imgui.begin("##toggle", None, flags)
        if imgui.small_button("Outliner " + ("[-]" if self.open_panel else "[+]")):
            self.open_panel = not self.open_panel
        if self.goz is not None:
            imgui.same_line()
            if imgui.small_button("GoZ " + ("[-]" if self.goz_open else "[+]")):
                self.goz_open = not self.goz_open
        if self.morph is not None:
            imgui.same_line()
            if imgui.small_button("Morph " + ("[-]" if self.morph_open else "[+]")):
                self.morph_open = not self.morph_open
            self._remember("toggle", "morph")
        pos, size = imgui.get_window_pos(), imgui.get_window_size()
        rects.append((pos.x, pos.y, size.x, size.y))
        imgui.end()
        # Getrennte Rechtecke (Leiste, Knöpfe, Panels): was dazwischen liegt, gehört dem Viewport.
        if self.open_panel:
            imgui.set_next_window_pos(imgui.ImVec2(*self.PANEL_POS), imgui.Cond_.first_use_ever)
            imgui.set_next_window_size(imgui.ImVec2(*self.PANEL_SIZE), imgui.Cond_.first_use_ever)
            imgui.set_next_window_size_constraints(imgui.ImVec2(200, 120), imgui.ImVec2(600, 900))
            imgui.begin("Outliner", None, imgui.WindowFlags_.no_collapse | imgui.WindowFlags_.no_saved_settings
                        | imgui.WindowFlags_.no_nav)
            self._outliner()
            pos, size = imgui.get_window_pos(), imgui.get_window_size()
            imgui.end()
            rects.append((pos.x, pos.y, size.x, size.y))
        if self.goz is not None and self.goz_open:
            w = self.window.get_size()[0]
            imgui.set_next_window_pos(imgui.ImVec2(w - 250.0, self.PANEL_POS[1]), imgui.Cond_.first_use_ever)
            imgui.begin("GoZ", None, imgui.WindowFlags_.no_collapse | imgui.WindowFlags_.always_auto_resize
                        | imgui.WindowFlags_.no_saved_settings | imgui.WindowFlags_.no_nav)
            self.goz.draw()
            pos, size = imgui.get_window_pos(), imgui.get_window_size()
            imgui.end()
            rects.append((pos.x, pos.y, size.x, size.y))
        if self.morph is not None and self.morph_open:
            # links unter dem Outliner: eine Panel-Spalte, die Mitte bleibt Viewport
            below = self.PANEL_POS[1] + self.PANEL_SIZE[1] + 10.0
            imgui.set_next_window_pos(imgui.ImVec2(self.PANEL_POS[0], below), imgui.Cond_.first_use_ever)
            imgui.begin("Morph", None, imgui.WindowFlags_.no_collapse | imgui.WindowFlags_.always_auto_resize
                        | imgui.WindowFlags_.no_saved_settings | imgui.WindowFlags_.no_nav)
            self.morph.draw()
            pos, size = imgui.get_window_pos(), imgui.get_window_size()
            imgui.end()
            rects.append((pos.x, pos.y, size.x, size.y))
        self.panel_rects = rects
        if self.menus is not None:
            self.menus.popups()
            self.popup_open = self.menus.popup_open

    def _outliner(self) -> None:
        imgui = self._imgui
        app = self.app
        io = imgui.get_io()
        object_mode = app.selection.mode.name == "OBJECT"
        changed, self.filter_text = imgui.input_text_with_hint("##filter", "Filter", self.filter_text)
        self._remember("filter", 0)
        if not object_mode:
            imgui.text_colored(imgui.ImVec4(1.0, 0.8, 0.43, 1.0), "Auswählen nur in Modus 4 (Object)")
        needle = self.filter_text.strip().lower()
        listed = om.rows(app.scene, app.selection.objects, frozenset(self.collapsed))
        if needle:
            listed = [r for r in listed if needle in r.name.lower()]
        imgui.begin_child("##rows", imgui.ImVec2(0, -imgui.get_text_line_height_with_spacing()))
        mods = set()
        if io.key_shift:
            mods.add("shift")
        if io.key_ctrl:
            mods.add("ctrl")
        if io.key_alt:
            mods.add("alt")
        for row in listed:
            self._row(row, mods, object_mode)
        count = len(listed)
        skeleton = app._skeleton
        bones = om.bone_rows(skeleton.rig, skeleton.current_bone, skeleton.hidden, frozenset(self.collapsed_bones))
        if bones:
            count += self._skeleton_section(bones, needle)
        imgui.end_child()
        imgui.text_disabled(self.last_note or f"{count} Zeilen")

    def _skeleton_section(self, bones, needle: str) -> int:
        """Die Knochen unter einer eigenen Kopfzeile; das Auge der Kopfzeile blendet alle ein/aus."""
        imgui = self._imgui
        skeleton = self.app._skeleton
        everything = [r.bone_id for r in om.bone_rows(skeleton.rig, None)]
        all_hidden = all(b in skeleton.hidden for b in everything)
        imgui.push_id("skeleton")
        if self._eye_button(all_hidden, all_hidden, imgui.get_frame_height()):
            self.app.set_bones_hidden(everything, not all_hidden)
            self.last_note = self.app.status_message
        self._remember("eye", "skeleton")
        imgui.same_line()
        if imgui.small_button("[-]" if self.skeleton_open else "[+]"):
            self.skeleton_open = not self.skeleton_open
        imgui.same_line()
        imgui.text_colored(imgui.ImVec4(0.55, 0.7, 0.95, 1.0), f"Skeleton ({len(everything)})")
        imgui.pop_id()
        shown = 0
        if self.skeleton_open:
            for row in bones:
                if needle and needle not in row.name.lower():
                    continue
                self._bone_row(row)
                shown += 1
        return shown + 1

    def _bone_row(self, row) -> None:
        imgui = self._imgui
        imgui.push_id(f"b{int(row.bone_id)}")
        if self._eye_button(row.hidden, row.hidden, imgui.get_frame_height()):
            self.app.set_bones_hidden([row.bone_id], not row.hidden)
            self.last_note = self.app.status_message
        self._remember("bone_eye", row.bone_id)
        imgui.same_line()
        imgui.dummy(imgui.ImVec2(row.depth * 16.0 + 16.0, 1))
        imgui.same_line(0, 0)
        if row.has_children:
            if imgui.small_button("[+]" if row.bone_id in self.collapsed_bones else "[-]"):
                self.collapsed_bones.symmetric_difference_update({row.bone_id})
            imgui.same_line()
        col = imgui.ImVec4(0.55, 0.58, 0.65, 1.0) if row.hidden else imgui.ImVec4(0.88, 0.9, 0.94, 1.0)
        action = self._name_cell(("b", row.bone_id), row.name, row.name, row.current, col)
        self._remember("bone", row.bone_id)
        if action == "click":
            self.app.select_bone(row.bone_id)
            self.last_note = self.app.status_message
        elif isinstance(action, tuple):  # ("rename", text)
            self.app.rename_bone(row.bone_id, action[1])
            self.last_note = self.app.status_message
        imgui.pop_id()

    def _name_cell(self, ekey, label: str, current_name: str, selected: bool, color):
        """Der Name einer Zeile: Klick, Doppelklick = Umbenennen im Textfeld (Enter oder Klick daneben übernimmt, Esc
        verwirft). Rückgabe: "click", ("rename", Text) oder None."""
        imgui = self._imgui
        if self.editing == ekey:
            if self._edit_focus:
                imgui.set_keyboard_focus_here()
                self._edit_focus = False
                first = True
            else:
                first = False
            imgui.set_next_item_width(-1)
            flags = imgui.InputTextFlags_.enter_returns_true | imgui.InputTextFlags_.auto_select_all
            entered, self.edit_buf = imgui.input_text("##rename", self.edit_buf, flags)
            self._remember("rename", ekey[1])
            if imgui.is_key_pressed(imgui.Key.escape, False):
                self.editing = None
                return None
            if entered or (not first and imgui.is_item_deactivated()):
                self.editing = None
                return ("rename", self.edit_buf) if self.edit_buf != current_name else None
            return None
        imgui.push_style_color(imgui.Col_.text, color)
        clicked, _ = imgui.selectable(label, selected, imgui.SelectableFlags_.allow_overlap)
        imgui.pop_style_color()
        if imgui.is_item_hovered() and imgui.is_mouse_double_clicked(0):
            self.editing, self.edit_buf, self._edit_focus = ekey, current_name, True
            return None
        return "click" if clicked else None

    def _row(self, row, mods, object_mode: bool) -> None:
        imgui = self._imgui
        imgui.push_id(int(row.object_id))
        indent = row.depth * 16.0
        eye_w = imgui.get_frame_height()
        # Auge
        if self._eye_button(row.hidden, row.effectively_hidden, eye_w):
            self._eye(row)
        self._remember("eye", row.object_id)
        imgui.same_line()
        imgui.dummy(imgui.ImVec2(indent, 1))
        imgui.same_line(0, 0)
        if row.is_group:
            arrow = "[+]" if row.object_id in self.collapsed else "[-]"
            if imgui.small_button(arrow):
                self.collapsed.symmetric_difference_update({row.object_id})
            imgui.same_line()
        label = row.name + ("  (edit)" if row.is_edit else "")
        dim = row.effectively_hidden
        col = imgui.ImVec4(0.55, 0.58, 0.65, 1.0) if dim else (
            imgui.ImVec4(0.55, 0.7, 0.95, 1.0) if row.is_reference else (
                imgui.ImVec4(1.0, 0.8, 0.43, 1.0) if row.is_group else imgui.ImVec4(0.88, 0.9, 0.94, 1.0)))
        action = self._name_cell(("o", row.object_id), label, row.name, row.selected, col)
        self._remember("row", row.object_id)
        if action == "click" and object_mode:
            self._click(row, mods)
        elif isinstance(action, tuple):
            self.app.rename_object(row.object_id, action[1])
            self.last_note = self.app.status_message
        if imgui.begin_popup_context_item("##ctx"):  # Framework-Fähigkeit prüfen (Brief: nicht im Spike)
            imgui.text_disabled(f"{om.group_of(row)}: {row.name}")
            imgui.menu_item("Duplizieren (kommt als Panel-Aktion)", "", False, False)
            # AD-031 P2 (O-13): Attach wirkt auf die Auswahl, wie Mesh > Attach; nur an einer ausgewählten Zeile, die
            # nicht das Edit-Objekt ist (keine neue Auswahl-Logik).
            can_attach = object_mode and row.selected and not row.is_edit
            for label, take_look in ATTACH_ENTRIES:
                if imgui.menu_item(label, "", False, can_attach)[0]:
                    self._attach(take_look)
            imgui.end_popup()
        imgui.pop_id()

    def _remember(self, kind: str, key) -> None:
        a, b = self._imgui.get_item_rect_min(), self._imgui.get_item_rect_max()
        self.item_rects[(kind, key)] = (a.x, a.y, b.x - a.x, b.y - a.y)

    def _eye_button(self, hidden: bool, dim: bool, size: float) -> bool:
        imgui = self._imgui
        pressed = imgui.invisible_button("##eye", imgui.ImVec2(size, size))
        a, b = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        dl = imgui.get_window_draw_list()
        cx, cy = (a.x + b.x) / 2, (a.y + b.y) / 2
        r = size * 0.32
        hot = imgui.is_item_hovered()
        c = imgui.get_color_u32(imgui.ImVec4(0.38, 0.4, 0.45, 1) if (hidden or dim)
                                else imgui.ImVec4(0.9, 0.92, 0.96, 1) if hot else imgui.ImVec4(0.72, 0.76, 0.84, 1))
        dl.add_ellipse(imgui.ImVec2(cx, cy), imgui.ImVec2(r * 1.25, r * 0.8), c, 0.0, 20, 1.5)
        if not hidden:
            dl.add_circle_filled(imgui.ImVec2(cx, cy), r * 0.45, c)
        else:
            dl.add_line(imgui.ImVec2(cx - r, cy + r), imgui.ImVec2(cx + r, cy - r), c, 1.5)
        return pressed

    # -- Aktionen: ein Aufruf an Application, das Panel hält keinen Dokumentzustand ---------------------------------
    def _attach(self, take_look: bool) -> None:
        if self.menus is not None:
            self.menus.attach(take_look)  # mit dem O-5-Dialog
        else:
            attach_request(self.app, take_look)  # ohne Menüs: die Ablehnung (mit Anzahl) steht in der Statuszeile
        self.last_note = self.app.status_message

    def _click(self, row, mods) -> None:
        _, ids = om.click_selection(self.app.selection.objects, row.object_id, mods)
        self.app.select_objects(ids)  # wie ein Viewport-Klick in Modus 4; das Highlight zieht `update_viewport` nach
        self.last_note = f"Auswahl: {len(self.app.selection.objects)}"

    def _eye(self, row) -> None:
        plan = om.eye_plan(row)
        if not plan.ids:
            self.last_note = f"{row.name}: {plan.note}"
            return
        self.app.set_objects_hidden(plan.ids, plan.hide)
        self.last_note = self.app.status_message


def _key_map(imgui) -> dict:
    """pyglet-Keysymbol -> imgui.Key, nur was Textfeld und Panel brauchen (Navigation per Tastatur ist aus)."""
    from pyglet.window import key as k

    m = {
        k.TAB: imgui.Key.tab, k.BACKSPACE: imgui.Key.backspace, k.RETURN: imgui.Key.enter,
        k.ESCAPE: imgui.Key.escape, k.DELETE: imgui.Key.delete, k.LEFT: imgui.Key.left_arrow,
        k.RIGHT: imgui.Key.right_arrow, k.UP: imgui.Key.up_arrow, k.DOWN: imgui.Key.down_arrow,
        k.HOME: imgui.Key.home, k.END: imgui.Key.end, k.PAGEUP: imgui.Key.page_up, k.PAGEDOWN: imgui.Key.page_down,
        k.LCTRL: imgui.Key.left_ctrl, k.RCTRL: imgui.Key.right_ctrl, k.LSHIFT: imgui.Key.left_shift,
        k.RSHIFT: imgui.Key.right_shift, k.LALT: imgui.Key.left_alt, k.RALT: imgui.Key.right_alt,
    }
    for ch in "abcdefghijklmnopqrstuvwxyz":
        m[getattr(k, ch.upper())] = getattr(imgui.Key, ch)  # Ctrl+A/C/V/X im Textfeld
    return m
