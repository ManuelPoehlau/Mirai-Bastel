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

    PANEL_POS = (12.0, 40.0)
    PANEL_SIZE = (280.0, 360.0)

    def __init__(self, window, app, guard_gl: bool = True, open_panel: bool = True,
                 blocked: Callable[[], bool] | None = None) -> None:
        """`blocked()`: True, solange etwas Modales (ein Menü) die Eingabe hat; das Panel fängt dann nichts."""
        self.window, self.app = window, app
        self._blocked = blocked or (lambda: False)
        self.guard_gl = guard_gl
        self.open_panel = open_panel
        self.collapsed: set = set()  # reiner Ansichtszustand des Panels (kein Dokumentzustand)
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
        imgui.set_next_window_pos(imgui.ImVec2(8, 8), imgui.Cond_.always)
        flags = (imgui.WindowFlags_.no_decoration | imgui.WindowFlags_.no_background
                 | imgui.WindowFlags_.always_auto_resize | imgui.WindowFlags_.no_move
                 | imgui.WindowFlags_.no_saved_settings | imgui.WindowFlags_.no_nav)
        toggle_rect = None
        imgui.begin("##toggle", None, flags)
        if imgui.small_button("Outliner " + ("[-]" if self.open_panel else "[+]")):
            self.open_panel = not self.open_panel
        pos, size = imgui.get_window_pos(), imgui.get_window_size()
        toggle_rect = (pos.x, pos.y, size.x, size.y)
        imgui.end()
        if not self.open_panel:
            self.panel_rects = [toggle_rect]
            return
        imgui.set_next_window_pos(imgui.ImVec2(*self.PANEL_POS), imgui.Cond_.first_use_ever)
        imgui.set_next_window_size(imgui.ImVec2(*self.PANEL_SIZE), imgui.Cond_.first_use_ever)
        imgui.set_next_window_size_constraints(imgui.ImVec2(200, 120), imgui.ImVec2(600, 900))
        imgui.begin("Outliner", None, imgui.WindowFlags_.no_collapse | imgui.WindowFlags_.no_saved_settings
                    | imgui.WindowFlags_.no_nav)
        self._outliner()
        pos, size = imgui.get_window_pos(), imgui.get_window_size()
        imgui.end()
        # Zwei getrennte Rechtecke (Knopf, Panel): was dazwischen liegt, gehört dem Viewport.
        self.panel_rects = [toggle_rect, (pos.x, pos.y, size.x, size.y)]

    def _outliner(self) -> None:
        imgui = self._imgui
        app = self.app
        io = imgui.get_io()
        object_mode = app.selection.mode.name == "OBJECT"
        changed, self.filter_text = imgui.input_text_with_hint("##filter", "Filter (Textfeld-Test)", self.filter_text)
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
        imgui.end_child()
        imgui.text_disabled(self.last_note or f"{len(listed)} Zeilen")

    def _row(self, row, mods, object_mode: bool) -> None:
        imgui = self._imgui
        imgui.push_id(int(row.object_id))
        indent = row.depth * 16.0
        eye_w = imgui.get_frame_height()
        # Auge
        if self._eye_button(row, eye_w):
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
        imgui.push_style_color(imgui.Col_.text, col)
        clicked, _ = imgui.selectable(label, row.selected, imgui.SelectableFlags_.allow_overlap)
        imgui.pop_style_color()
        self._remember("row", row.object_id)
        if clicked and object_mode:
            self._click(row, mods)
        if imgui.begin_popup_context_item("##ctx"):  # Framework-Fähigkeit prüfen (Brief: nicht im Spike)
            imgui.text_disabled(f"{om.group_of(row)}: {row.name}")
            imgui.menu_item("Duplizieren (kommt als Panel-Aktion)", "", False, False)
            imgui.end_popup()
        imgui.pop_id()

    def _remember(self, kind: str, key) -> None:
        a, b = self._imgui.get_item_rect_min(), self._imgui.get_item_rect_max()
        self.item_rects[(kind, key)] = (a.x, a.y, b.x - a.x, b.y - a.y)

    def _eye_button(self, row, size: float) -> bool:
        imgui = self._imgui
        pressed = imgui.invisible_button("##eye", imgui.ImVec2(size, size))
        a, b = imgui.get_item_rect_min(), imgui.get_item_rect_max()
        dl = imgui.get_window_draw_list()
        cx, cy = (a.x + b.x) / 2, (a.y + b.y) / 2
        r = size * 0.32
        hot = imgui.is_item_hovered()
        hidden = row.hidden
        c = imgui.get_color_u32(imgui.ImVec4(0.38, 0.4, 0.45, 1) if (hidden or row.effectively_hidden)
                                else imgui.ImVec4(0.9, 0.92, 0.96, 1) if hot else imgui.ImVec4(0.72, 0.76, 0.84, 1))
        dl.add_ellipse(imgui.ImVec2(cx, cy), imgui.ImVec2(r * 1.25, r * 0.8), c, 0.0, 20, 1.5)
        if not hidden:
            dl.add_circle_filled(imgui.ImVec2(cx, cy), r * 0.45, c)
        else:
            dl.add_line(imgui.ImVec2(cx - r, cy + r), imgui.ImVec2(cx + r, cy - r), c, 1.5)
        return pressed

    # -- Aktionen: ein Aufruf an Application, das Panel hält keinen Dokumentzustand ---------------------------------
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
