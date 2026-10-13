"""Lab window: raw pyglet events → `LabState`; hover pick, direct drag, HUD, curve panel.

Raw pyglet events as in `src/main.py` (window before GL resources, camera deltas straight
to `OrbitCamera`); every key/wheel event goes through `LabState` (which resolves it with
`lab_bindings`), every mouse drag through `lab_bindings.resolve_drag`.

Hover (edit phase): `mirai.viewport.picking.pick_nearest_edge` (+ `PickCache`, occlusion
on — the box is drawn shaded) → `EditSession.target(edge, mode)` → signed influence →
bands and the optional surface preview (`P`, Slice 2a E14). While the cursor is over the
curve panel the last mesh hover is kept, so bands and preview show what a curve edit does.
After every position change (drag release, Undo/Redo, Nachführen, cancel) the pick cache
is invalidated and the hover re-picked (no stale hover, B6 crash class).

Selection (Slice 3): an LMB press outside the curve panel in the edit phase is undecided
(`lab_pointer.PointerPress`, threshold from AD-019) — released below the threshold it is a
selection click (Shift / Ctrl / Alt: add / remove / toggle), the hit picked at the release with
`mirai.viewport.picking.pick_component` in the active mode (same `PickCache`, occlusion on, as
the edge hover); past the threshold it is the drag (plain: Move, Alt: orbit) and the motion
events seen so far are replayed one by one. The drag's target is fixed at the press:
`LabState.gesture_target` — the selection when there is one and the press is over the mesh
(hovered edge or a face under the cursor), else the hover target (E26). While a press is
undecided, Esc / RMB / focus loss drop it (no click, no drag).

Hover (Slice 3b, Manu O13): by default `pick_component` in the active selection mode (the
component under the cursor, production hover look); in the `L` mode `pick_nearest_edge` and
its Loop/Ring as before. A click in the `L` mode selects the Loop/Ring of the edge under the
release; outside it, two clicks on the same handle within the lab's double-click window make
a double click (`lab_pointer.ClickSeries`), whose second click goes to
`LabState.double_click`. For Shift+L/R over a vertex/face hover the edge under the cursor is
picked once, on the key press.

Drag: LMB on a hovered target begins the signed soft Move; each motion event turns
`(dx, dy)` into a world delta on the image plane through the anchor seed with
`OrbitCamera.screen_delta_to_world` (as `MoveTool._on_update`), the state applies the
X/Y/Z mask. Release = commit, Esc / RMB = cancel. During the drag bands and preview show
the gesture's own weights.

Hold gestures (Slice 2b E16): the window keeps `LabState.hover_target` current, forwards
W/E/R presses and releases, and while a key is held turns every mouse motion into
`LabState.hold_motion()` (which maps pixels like `RotateTool`/`ScaleTool`/`MoveTool`). The
hover is frozen while armed. Losing focus cancels an armed hold (its release would never
arrive).

Curve panel (Slice 2a E11/E12): LMB picks a knot or handle (`CurvePanel.pick`, handles
first) and drags it by the cursor's motion; every motion re-applies the edit to the curve
as it was at the press, so a handle shrunk to fit grows back when the cursor returns.
Alt+LMB on a handle breaks the knot's alignment; a double click on a knot (or one of its
handles) restores aligned automatic handles.

pyglet's scroll event carries no modifiers, so the window tracks held Shift/Ctrl/Alt keys
itself (as `src/main.py` does for Shift/Ctrl) and clears them when it loses focus.

2D (HUD labels, curve panel shapes, help) is drawn after the meshes with pyglet's
default window projection (our `on_resize` returns nothing, so pyglet's own handler
still sets it).
"""

from __future__ import annotations

import time
from typing import Optional

import pyglet
from mirai.viewport.picking import pick_component, pick_face, pick_nearest_edge
from mirai.viewport.picking_cache import PickCache
from pyglet import shapes
from pyglet.window import key as _key
from pyglet.window import mouse as _mouse

from . import lab_bindings as lb
from . import lab_state as ls
from .box import build_box_mesh
from .curve_panel import KNOT, CurvePanel, DoubleClick, Element, element_position, move_element
from .lab_pointer import ClickSeries, PointerPress
from .lab_selection import component_target
from .lab_scene import LabScene, gl_info_strings
from .signed_curve import DEFAULT_KNOTS_X, FIRST, LAST

HUD_FONT = ("Consolas", "DejaVu Sans Mono", "Courier New", "monospace")
HUD_FONT_SIZE = 11
HUD_LINE_HEIGHT = 18
HUD_MARGIN = 12
HUD_COLORS = {
    "title": (255, 255, 255, 255),
    "normal": (205, 210, 220, 255),
    "active": (255, 214, 90, 255),
    "inactive": (130, 132, 142, 255),
    "warning": (255, 110, 90, 255),
}
#: Dark translucent backdrop: grey HUD text must stay readable over the light box faces.
HUD_BACKDROP = (8, 9, 14, 170)
FRAME_TEXT_INTERVAL_S = 0.25
ORBIT_RADIANS_PER_PIXEL = 0.005
#: Same as the production edge pick default (`pick_nearest_edge`).
PICK_RADIUS_PX = 9.0

# Curve panel look (PROVISIONAL).
PANEL_BG = (18, 20, 28, 225)
PANEL_WARM = (120, 55, 30, 90)
PANEL_COOL = (30, 60, 130, 90)
PANEL_BORDER = (90, 94, 110, 255)
PANEL_GRID = (70, 74, 88, 255)
PANEL_ZERO = (235, 235, 240, 255)
PANEL_CURVE = (255, 214, 90, 255)
PANEL_POINT = (255, 255, 255, 255)
PANEL_POINT_ACTIVE = (255, 120, 80, 255)
PANEL_FIXED = (140, 142, 150, 255)
PANEL_HANDLE = (120, 200, 255, 255)
PANEL_HANDLE_LINE = (120, 160, 200, 200)

_BUTTON_NAMES = ((_mouse.LEFT, "LEFT"), (_mouse.RIGHT, "RIGHT"), (_mouse.MIDDLE, "MIDDLE"))
_MODIFIER_NAMES = ((_key.MOD_SHIFT, "shift"), (_key.MOD_CTRL, "ctrl"), (_key.MOD_ALT, "alt"))
_MODIFIER_KEYS = {
    _key.LSHIFT: "shift", _key.RSHIFT: "shift",
    _key.LCTRL: "ctrl", _key.RCTRL: "ctrl",
    _key.LALT: "alt", _key.RALT: "alt",
}

DRAG_MESH = "mesh"
DRAG_PANEL = "panel"
DRAG_CANCELLED = "cancelled"
DRAG_PENDING = "pending"   # LMB press, click or drag not yet decided (Slice 3 E24)
DRAG_CAMERA = "camera"     # an undecided Alt+LMB press that became an orbit


def button_names(buttons: int) -> frozenset:
    return frozenset(name for bit, name in _BUTTON_NAMES if buttons & bit)


def modifier_names(modifiers: int) -> frozenset:
    return frozenset(name for bit, name in _MODIFIER_NAMES if modifiers & bit)


class MehlsackLabWindow(pyglet.window.Window):
    def __init__(self, width: int = 1280, height: int = 800, visible: bool = True, box=None) -> None:
        # Window before GL resources: stores compile their shader and build their
        # VertexLists inside this window's context (see `src/main.py`).
        super().__init__(width=width, height=height, resizable=True, visible=visible,
                         caption="Mirai — Mehlsack Lab (Slice 3: Auswahl)")
        self.state = ls.LabState(box)
        self.scene = LabScene(self._aspect(), selection=self.state.selection)
        self.scene.show_mesh(build_box_mesh(self.state.box), frame="always")
        self.panel = CurvePanel()

        version, renderer = gl_info_strings()
        self.state.gl_version, self.state.gl_renderer = version, renderer
        print(f"GL_VERSION:  {version}")
        print(f"GL_RENDERER: {renderer}")

        self._held: dict[int, str] = {}
        self._cursor: Optional[tuple[float, float]] = None
        self._pick_cache = PickCache()
        #: What the hover pick hit (an edge in the L mode, else a handle of the active mode) and
        #: the (L mode, selection mode) it was picked for.
        self._hover_hit = None
        self._hover_key = None
        self._clicks = ClickSeries()
        self._drag_mode: Optional[str] = None
        self._press: Optional[PointerPress] = None
        self._press_target = None
        self._press_mods = frozenset()
        self._panel_element: Optional[Element] = None
        #: Panel drag: the curve at the press, the element's grab offset, Alt held.
        self._panel_start = None
        self._panel_offset = (0.0, 0.0)
        self._panel_break = False
        self._double_click = DoubleClick()

        self._hud_batch = pyglet.graphics.Batch()
        self._hud_labels: list[pyglet.text.Label] = []
        self._hud_backdrop = None
        self._hud_revision = -1
        self._panel_batch = pyglet.graphics.Batch()
        self._panel_items: list = []
        self._panel_key = None
        self._help_batch = pyglet.graphics.Batch()
        self._help_items: list = []
        self._help_key = None
        self._frame_ms: Optional[float] = None
        self._last_draw: Optional[float] = None
        self._last_frame_text = 0.0

    # -- helpers -----------------------------------------------------------------------------

    def _aspect(self) -> float:
        return self.width / self.height if self.height else 1.0

    def _camera_changed(self) -> None:
        self.scene.camera_changed(self._aspect())

    def held_modifiers(self) -> frozenset:
        return frozenset(self._held.values())

    @property
    def editing(self) -> bool:
        return self.state.phase == lb.PHASE_EDIT

    def _in_panel(self, x: float, y: float) -> bool:
        return self.editing and self.panel.contains(x, y)

    # -- hover -------------------------------------------------------------------------------

    def update_hover(self, x: float, y: float, force: bool = False) -> None:
        """Picks the edge under (x, y) and pushes its Loop/Ring + bands into the scene."""
        if not self.editing or self.state.dragging or self.state.armed:
            return
        started = time.perf_counter()
        state = self.state
        session = state.session
        if state.loop_mode:
            hit = pick_nearest_edge(
                self.scene.camera, session.mesh, x, y, self.width, self.height, PICK_RADIUS_PX,
                cache=self._pick_cache, occlusion=True,
            )
        else:
            hit = pick_component(
                self.scene.camera, session.mesh, state.selection.mode, x, y, self.width, self.height,
                cache=self._pick_cache, occlusion=True,
            )
        key = (state.loop_mode, state.selection.mode, type(hit), hit)
        if key == self._hover_key and not force:
            return
        self._hover_hit, self._hover_key = hit, key
        self.refresh_target()
        self.state.hover_ms = (time.perf_counter() - started) * 1000.0
        self.state.revision += 1

    def refresh_target(self) -> None:
        """Recomputes the target of the hovered edge (mode may have changed), the active target
        (the selection's, else the hover's — E26) and its bands."""
        session = self.state.session
        if self.state.armed:
            return  # the held key's target is frozen
        if not self.editing or session is None:
            self.state.hover_target = None
            self.scene.set_target(None, {})
            return
        state = self.state
        hit = self._hover_hit
        if self._hover_key is None or self._hover_key[:2] != (state.loop_mode, state.selection.mode):
            hit = None  # picked for another mode: wait for the re-pick
        if state.loop_mode:
            hover = None if hit is None else session.target(hit, state.mode)
            state.selection.hovered = None
        else:
            hover = component_target(session.mesh, state.selection.mode, hit)
            state.selection.hovered = hit if hover is not None else None
        state.hover_target = hover
        target = self.state.active_target
        self.scene.set_target(target, self.state.preview_weights(target), hover=hover)

    def repick(self) -> None:
        """After a position change: no stale pick data, no stale hover."""
        self._pick_cache.invalidate()
        if self._cursor is not None and not self.panel.contains(*self._cursor):
            self.update_hover(*self._cursor, force=True)
        else:
            self.refresh_target()

    # -- outcome of a state change ---------------------------------------------------------------

    def handle(self, out: ls.Outcome) -> None:
        if ls.QUIT in out:
            self.close()
            return
        for _ in range(abs(out.zoom_steps)):
            self.scene.camera.dolly(0.9 if out.zoom_steps > 0 else 1.1)
        if out.zoom_steps:
            self._camera_changed()
        state = self.state
        if ls.SELECTION_CHANGED in out:
            self.scene.selection_changed()
        if ls.PHASE_CHANGED in out:
            self._hover_hit = self._hover_key = None
            self._clicks.reset()
            self._pick_cache = PickCache()
            if self.editing:
                self.scene.show_mesh(state.session.mesh, frame="none")
            else:
                self.scene.show_mesh(build_box_mesh(state.box), frame="grow")
        elif ls.BOX_CHANGED in out:
            self.scene.show_mesh(build_box_mesh(state.box), frame="grow")
        self.scene.bands.visible = state.bands_visible
        self.scene.preview.visible = state.preview_visible
        if ls.MESH_CHANGED in out:
            self.scene.positions_changed(out.changed)
            self.repick()
        elif ls.REPICK in out:
            self.repick()
        elif ls.PREVIEW_CHANGED in out:
            if self._cursor is not None and self.editing and not self.panel.contains(*self._cursor):
                self.update_hover(*self._cursor, force=True)
            else:
                self.refresh_target()  # cursor over the panel: keep the hovered edge

    # -- pyglet events -----------------------------------------------------------------------------

    def on_resize(self, width: int, height: int):
        # No EVENT_HANDLED: pyglet's default handler must still set the GL viewport and the
        # 2D projection the HUD uses.
        self._camera_changed()
        self._pick_cache.invalidate()
        self._hud_revision = -1
        self._help_key = None

    def on_deactivate(self):
        # A modifier (or a held W/E/R) released while another window has focus sends no
        # release here.
        self._held.clear()
        if self._drag_mode == DRAG_PENDING:
            self._drop_press()
        if self.state.armed:
            self.handle(self.state.cancel_drag())

    def on_mouse_motion(self, x, y, dx, dy):
        self._cursor = (x, y)
        if self.state.armed:
            self.hold_motion(dx, dy)
            return
        if self.editing and not self.panel.contains(x, y):
            self.update_hover(x, y)

    def hold_motion(self, dx: float, dy: float) -> None:
        state = self.state
        out = state.hold_motion(dx, dy, self.width, self.height, self.scene.camera)
        if ls.GESTURE_BEGAN in out:
            self.scene.set_target(state.hold.target, state.session.drag.weights)
        if ls.MESH_CHANGED in out:
            self.scene.positions_changed(out.changed)
            self._pick_cache.invalidate()

    def on_mouse_leave(self, x, y):
        self._cursor = None

    def on_mouse_press(self, x, y, button, modifiers):
        self._cursor = (x, y)
        name = button_names(button)
        state = self.state
        if state.armed:
            # While W/E/R is held only RMB means something: cancel.
            if len(name) == 1 and lb.resolve_press_during_drag(state.phase, next(iter(name))) == lb.CANCEL_PRESS:
                self.handle(state.cancel_drag())
            return
        if self._drag_mode in (DRAG_MESH, DRAG_PENDING, DRAG_CAMERA):
            if len(name) == 1 and lb.resolve_press_during_drag(state.phase, next(iter(name))) == lb.CANCEL_PRESS:
                if self._drag_mode == DRAG_MESH:
                    self.handle(state.cancel_drag())
                elif self._drag_mode == DRAG_PENDING:
                    self._drop_press()
                self._drag_mode = DRAG_CANCELLED
            return
        mods = modifier_names(modifiers)
        in_panel = self._in_panel(x, y)
        action = lb.resolve_drag(state.phase, name, mods, in_panel)
        click = None if in_panel or len(name) != 1 else lb.resolve_click(state.phase, next(iter(name)), mods)
        if click is not None:
            self._press = PointerPress(click, action)
            self._press_mods = mods
            over_mesh = state.selection_target is not None and self._over_mesh(x, y)
            self._press_target = state.gesture_target(over_mesh) if action == lb.DRAG_TARGET else None
            self._drag_mode = DRAG_PENDING
            state.pointer_pending = True
        elif action in (lb.CURVE_POINT, lb.CURVE_BREAK):
            element = self.panel.pick(x, y, state.curve)
            knot = self._double_click.press(element, x, y, time.perf_counter())
            if knot is not None and lb.resolve_double_click(state.phase, mods, in_panel) == lb.CURVE_RESET:
                self.handle(state.set_curve(state.curve.with_auto_handles(knot)))
                self._drag_mode = DRAG_CANCELLED  # the rest of this press does nothing
                return
            self._drag_mode = DRAG_PANEL
            self._panel_element = element
            self._panel_start = state.curve
            self._panel_break = action == lb.CURVE_BREAK
            if element is not None:
                cx, cy = self.panel.to_curve(x, y)
                ex, ey = element_position(state.curve, element)
                self._panel_offset = (ex - cx, ey - cy)

    def _over_mesh(self, x: float, y: float) -> bool:
        """E26 "pressed over the mesh": a hovered component/edge or a face under the cursor."""
        if self._hover_hit is not None:
            return True
        return pick_face(self.scene.camera, self.state.session.mesh, x, y, self.width, self.height,
                         cache=self._pick_cache) is not None

    def _drop_press(self) -> None:
        """An undecided LMB press ends without click and without drag."""
        self._press = None
        self._press_target = None
        self._drag_mode = DRAG_CANCELLED
        self.state.pointer_pending = False

    def _press_motion(self, dx: float, dy: float) -> None:
        """Motion of an undecided (or just decided) LMB press (module docstring)."""
        press = self._press
        decided = press.dragging
        steps = press.motion(dx, dy)
        if press.dragging and not decided:
            self.state.pointer_pending = False
            if press.drag_action == lb.ORBIT:
                self._drag_mode = DRAG_CAMERA
            elif press.drag_action == lb.DRAG_TARGET and self._press_target is not None:
                target = self._press_target
                weights = self.state.begin_drag(target)
                self.scene.set_target(target, weights)
                self._drag_mode = DRAG_MESH
            else:
                self._drag_mode = DRAG_CANCELLED  # dragged off nothing: as before, nothing
            self._press = None
        for step_dx, step_dy in steps:
            self._drag_step(step_dx, step_dy)

    def _drag_step(self, dx: float, dy: float) -> None:
        if self._drag_mode == DRAG_MESH:
            if self.state.dragging:
                self.drag_by(dx, dy)
        elif self._drag_mode == DRAG_CAMERA:
            self.scene.camera.orbit(-dx * ORBIT_RADIANS_PER_PIXEL, -dy * ORBIT_RADIANS_PER_PIXEL)
            self._camera_changed()

    def select_at(self, command: str, x: float, y: float, modifiers=frozenset()) -> None:
        """A selection click at (x, y): the handle under the cursor in the active mode (E23), in
        the L mode the Loop/Ring of the edge under it (Slice 3b); a double click goes to
        `LabState.double_click`."""
        state = self.state
        mesh = state.session.mesh
        if state.loop_mode:
            edge = pick_nearest_edge(self.scene.camera, mesh, x, y, self.width, self.height, PICK_RADIUS_PX,
                                     cache=self._pick_cache, occlusion=True)
            self._clicks.reset()
            self.handle(state.click_loop(command, None if edge is None else state.session.target(edge, state.mode)))
            return
        hit = pick_component(
            self.scene.camera, mesh, state.selection.mode, x, y, self.width, self.height,
            cache=self._pick_cache, occlusion=True,
        )
        if self._clicks.click(command, hit, x, y, time.perf_counter()):
            action = lb.resolve_double_click(state.phase, modifiers, in_panel=False)
            self.handle(state.double_click(action, command, hit))
        else:
            self.handle(state.click(command, hit))

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._cursor = (x, y)
        mode = self._drag_mode
        if mode == DRAG_PENDING:
            self._press_motion(dx, dy)
            return
        if mode == DRAG_CAMERA:
            self._drag_step(dx, dy)
            return
        if mode == DRAG_MESH:
            if self.state.dragging:
                self.drag_by(dx, dy)
            return
        if mode == DRAG_PANEL:
            self._drag_panel(x, y)
            return
        if mode == DRAG_CANCELLED:
            return
        action = lb.resolve_drag(self.state.phase, button_names(buttons), modifier_names(modifiers),
                                 self._in_panel(x, y))
        camera = self.scene.camera
        if action == lb.ORBIT:
            camera.orbit(-dx * ORBIT_RADIANS_PER_PIXEL, -dy * ORBIT_RADIANS_PER_PIXEL)
            self._camera_changed()
        elif action == lb.PAN:
            camera.pan(dx, dy, self.width, self.height)
            self._camera_changed()

    def on_mouse_release(self, x, y, button, modifiers):
        self._cursor = (x, y)
        if not button & _mouse.LEFT:
            return
        mode, self._drag_mode = self._drag_mode, None
        self._panel_element = None
        self._panel_start = None
        if mode == DRAG_PENDING:
            press, self._press, self._press_target = self._press, None, None
            self.state.pointer_pending = False
            click = press.release()
            if click is not None and self.state.session is not None:
                self.select_at(click, x, y, self._press_mods)
        elif mode == DRAG_MESH:
            self.handle(self.state.end_drag())
        elif mode == DRAG_CANCELLED:
            self.repick()

    def drag_by(self, dx: float, dy: float) -> float:
        """One drag event: screen delta → world delta at the anchor seed → masked → op.
        Returns the step time in ms (also in the HUD)."""
        started = time.perf_counter()
        state = self.state
        session = state.session
        anchor = session.mesh.vertex_position(session.drag.target.anchor)
        delta = self.scene.camera.screen_delta_to_world(anchor, dx, dy, self.width, self.height)
        state.drag_step(delta)
        self.scene.positions_changed(session.drag.weights)
        self._pick_cache.invalidate()
        ms = (time.perf_counter() - started) * 1000.0
        state.drag_ms = ms
        state.revision += 1
        return ms

    def _drag_panel(self, x: float, y: float) -> None:
        element = self._panel_element
        if element is None or self._panel_start is None:
            return
        cx, cy = self.panel.to_curve(x, y)
        ox, oy = self._panel_offset
        curve = move_element(self._panel_start, element, cx + ox, cy + oy, self._panel_break)
        if curve.shape == self._panel_start.shape and not self._panel_break:
            curve = self._panel_start  # back where it started: keep the preset name
        self.handle(self.state.set_curve(curve))

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.handle(self.state.wheel(scroll_x, scroll_y, self.held_modifiers()))

    def on_key_press(self, symbol, modifiers):
        if symbol in _MODIFIER_KEYS:
            self._held[symbol] = _MODIFIER_KEYS[symbol]
        if symbol == _key.ESCAPE and self._drag_mode == DRAG_PENDING:
            self._drop_press()  # Esc drops an undecided press (it would quit otherwise)
            self.repick()
            return pyglet.event.EVENT_HANDLED
        name, mods = _key.symbol_string(symbol), modifier_names(modifiers)
        state = self.state
        if (self.editing and self._cursor is not None
                and lb.resolve_key(state.phase, name, mods) in (lb.LOOP_SELECT, lb.RING_SELECT)
                and (state.hover_target is None or state.hover_target.edge is None)):
            # Vertex/Face hover: Shift+L/R need the edge under the cursor (picked once, here).
            state.edge_under_cursor = pick_nearest_edge(
                self.scene.camera, state.session.mesh, *self._cursor, self.width, self.height, PICK_RADIUS_PX,
                cache=self._pick_cache, occlusion=True,
            )
        self.handle(state.key(name, mods))
        state.edge_under_cursor = None
        # Always handled: pyglet's default handler would close the window on Esc, but Esc
        # cancels a running drag first.
        return pyglet.event.EVENT_HANDLED

    def on_key_release(self, symbol, modifiers):
        self._held.pop(symbol, None)
        self.handle(self.state.key_release(_key.symbol_string(symbol)))
        return pyglet.event.EVENT_HANDLED

    # -- draw ------------------------------------------------------------------------------------------

    def on_draw(self):
        now = time.perf_counter()
        if self._last_draw is not None:
            ms = (now - self._last_draw) * 1000.0
            self._frame_ms = ms if self._frame_ms is None else (
                self._frame_ms + ls.FRAME_EMA * (ms - self._frame_ms))
        self._last_draw = now
        self.scene.draw()
        self.draw_2d(now)

    def draw_2d(self, now: Optional[float] = None) -> None:
        from pyglet import gl

        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self._update_hud(time.perf_counter() if now is None else now)
        self._hud_batch.draw()
        if self.editing:
            self._update_panel()
            self._panel_batch.draw()
        if self.state.help_visible:
            self._update_help()
            self._help_batch.draw()

    # -- HUD ---------------------------------------------------------------------------------------------

    def _update_hud(self, now: float) -> None:
        frame_due = now - self._last_frame_text >= FRAME_TEXT_INTERVAL_S
        if self._hud_revision == self.state.revision and not frame_due:
            return
        self._hud_revision = self.state.revision
        self._last_frame_text = now
        lines = self.state.hud_lines(self._frame_ms)
        if self._hud_backdrop is None:
            self._hud_backdrop = shapes.Rectangle(0, 0, 1, 1, color=HUD_BACKDROP, batch=self._hud_batch,
                                                  group=pyglet.graphics.Group(order=0))
        while len(self._hud_labels) < len(lines):
            self._hud_labels.append(pyglet.text.Label(
                "", font_name=HUD_FONT, font_size=HUD_FONT_SIZE, x=HUD_MARGIN, y=0,
                anchor_x="left", anchor_y="top", batch=self._hud_batch,
                group=pyglet.graphics.Group(order=1),
            ))
        for index, label in enumerate(self._hud_labels):
            if index < len(lines):
                line = lines[index]
                if label.text != line.text:
                    label.text = line.text
                color = HUD_COLORS[line.style]
                if tuple(label.color) != color:
                    label.color = color
                label.y = self.height - HUD_MARGIN - index * HUD_LINE_HEIGHT
                label.visible = True
            else:
                label.visible = False
        widest = max((label.content_width for label in self._hud_labels[:len(lines)]), default=0)
        backdrop = self._hud_backdrop
        backdrop.x, backdrop.width = HUD_MARGIN - 6, widest + 12
        backdrop.height = len(lines) * HUD_LINE_HEIGHT + 8
        backdrop.y = self.height - HUD_MARGIN - backdrop.height + 6

    # -- curve panel ----------------------------------------------------------------------------------------

    def _update_panel(self) -> None:
        curve = self.state.curve
        key = (curve.key, curve.preset, self._panel_element)
        if key == self._panel_key:
            return
        self._panel_key = key
        for item in self._panel_items:
            item.delete()
        batch = self._panel_batch
        p = self.panel
        x0, y0, x1, y1 = p.plot
        zero = p.zero_y()
        items: list = [
            shapes.Rectangle(p.x, p.y, p.width, p.height, color=PANEL_BG, batch=batch),
            shapes.Rectangle(x0, zero, x1 - x0, y1 - zero, color=PANEL_WARM, batch=batch),
            shapes.Rectangle(x0, y0, x1 - x0, zero - y0, color=PANEL_COOL, batch=batch),
        ]
        for a, b in (((p.x, p.y), (p.x + p.width, p.y)), ((p.x + p.width, p.y), (p.x + p.width, p.y + p.height)),
                     ((p.x + p.width, p.y + p.height), (p.x, p.y + p.height)), ((p.x, p.y + p.height), (p.x, p.y))):
            items.append(shapes.Line(*a, *b, thickness=1, color=PANEL_BORDER, batch=batch))
        for cx in DEFAULT_KNOTS_X[1:-1]:
            sx = p.to_screen(cx, 0.0)[0]
            items.append(shapes.Line(sx, y0, sx, y1, thickness=1, color=PANEL_GRID, batch=batch))
        items.append(shapes.Line(x0, zero, x1, zero, thickness=2, color=PANEL_ZERO, batch=batch))
        poly = p.polyline(curve)
        for a, b in zip(poly, poly[1:]):
            items.append(shapes.Line(*a, *b, thickness=2, color=PANEL_CURVE, batch=batch))
        active = self._panel_element
        for element, (kx, ky), (hx, hy) in p.handle_lines(curve):
            items.append(shapes.Line(kx, ky, hx, hy, thickness=1, color=PANEL_HANDLE_LINE, batch=batch))
            color = PANEL_POINT_ACTIVE if element == active else PANEL_HANDLE
            items.append(shapes.Rectangle(hx - 3, hy - 3, 6, 6, color=color, batch=batch))
        for index, (sx, sy) in enumerate(p.knot_points(curve)):
            fixed = index in (FIRST, LAST)
            is_active = active is not None and active.kind == KNOT and active.index == index
            color = PANEL_FIXED if fixed else (PANEL_POINT_ACTIVE if is_active else PANEL_POINT)
            if fixed or curve.aligned[index]:
                items.append(shapes.Circle(sx, sy, 3 if fixed else 5, color=color, batch=batch))
            else:  # corner (broken handles): a diamond
                items.append(shapes.Polygon((sx, sy - 6), (sx + 6, sy), (sx, sy + 6), (sx - 6, sy),
                                            color=color, batch=batch))
        for text, ty in (("+1", y1), ("0", zero), ("−1", y0)):
            items.append(pyglet.text.Label(text, font_name=HUD_FONT, font_size=8, x=p.x + 3, y=ty,
                                           anchor_x="left", anchor_y="center", color=(200, 200, 210, 255),
                                           batch=batch))
        items.append(pyglet.text.Label(
            f"Kurve: {curve.label}   (Seed ← d/r → Radius)", font_name=HUD_FONT, font_size=8,
            x=p.x + 4, y=p.y + p.height - 4, anchor_x="left", anchor_y="top",
            color=(220, 220, 230, 255), batch=batch))
        self._panel_items = items

    # -- help -----------------------------------------------------------------------------------------------------

    def _update_help(self) -> None:
        key = (self.state.phase, self.width, self.height)
        if key == self._help_key:
            return
        self._help_key = key
        for item in self._help_items:
            item.delete()
        lines = self.state.help_lines()
        width = min(self.width - 40, 1100)
        height = min(self.height - 40, 30 + len(lines) * 17)
        x, y = (self.width - width) / 2, (self.height - height) / 2
        batch = self._help_batch
        self._help_items = [
            shapes.Rectangle(x, y, width, height, color=(10, 12, 18, 235), batch=batch),
            pyglet.text.Label("\n".join(lines), font_name=HUD_FONT, font_size=10, x=x + 14,
                              y=y + height - 12, width=width - 28, multiline=True,
                              anchor_x="left", anchor_y="top", color=(225, 228, 235, 255), batch=batch),
        ]
