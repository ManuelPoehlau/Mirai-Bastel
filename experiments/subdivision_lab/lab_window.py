"""Lab window: navigation, control-vertex drag, view/level switching, text HUD.

Raw pyglet events as in `src/main.py` (window before GL resources, camera
deltas straight to `OrbitCamera`); every event is resolved through
`lab_bindings` (the one visible table) into `LabState` / `LabScene` calls.
Precedent: `experiments/viewport_shading_lab/lab_window.py` (rebuilt, not imported).

Drag (handoff §3.5): the nearest control vertex under the cursor is picked with
`mirai.viewport.picking.pick_nearest_vertex` (+ `PickCache`; `occlusion` only
when the control mesh is what is drawn, i.e. V-CAGE — the derived surface has
no picking, D7, so in V-BOTH/V-ISO every control vertex is grabbable, visible
or not). LMB-drag moves it in the camera's screen plane via
`OrbitCamera.screen_delta_to_world`. Every drag event runs the whole update
(`LabScene.move_control_vertex`: control mesh → `apply_local` → derived mesh →
`mark_vertices_dirty` → `sync()` → lines); no structural rebuild.

HUD: `pyglet.text.Label`s in one batch, drawn after the meshes. The mesh draw
sets its own program, depth test and culling on every call, so HUD labels do
not leak state into the next frame.
"""

from __future__ import annotations

import time
from typing import Optional

import pyglet
from mirai.viewport import vecmath
from mirai.viewport.picking import pick_nearest_vertex
from mirai.viewport.picking_cache import PickCache
from pyglet.window import key as _key
from pyglet.window import mouse as _mouse

from . import lab_bindings as lb
from .lab_scene import LabScene, gl_info_strings
from .lab_state import FRAME_EMA, VIEW_CAGE, LabState

HUD_FONT = ("Consolas", "DejaVu Sans Mono", "Courier New", "monospace")
HUD_FONT_SIZE = 11
HUD_LINE_HEIGHT = 18
HUD_MARGIN = 12
HUD_COLORS = {
    "title": (255, 255, 255, 255),
    "normal": (205, 210, 220, 255),
    "active": (255, 214, 90, 255),
    "inactive": (110, 112, 122, 255),
    "warning": (255, 110, 90, 255),
}
FRAME_TEXT_INTERVAL_S = 0.25
ORBIT_RADIANS_PER_PIXEL = 0.005
#: Same pick radius as the production vertex pick (`pick_nearest_vertex` default).
PICK_RADIUS_PX = 14.0

_BUTTON_NAMES = ((_mouse.LEFT, "LEFT"), (_mouse.RIGHT, "RIGHT"), (_mouse.MIDDLE, "MIDDLE"))
_MODIFIER_NAMES = ((_key.MOD_SHIFT, "shift"), (_key.MOD_CTRL, "ctrl"), (_key.MOD_ALT, "alt"))
_LEVEL_ACTIONS = {lb.LEVEL_1: 1, lb.LEVEL_2: 2, lb.LEVEL_3: 3}


def button_names(buttons: int) -> frozenset:
    return frozenset(name for bit, name in _BUTTON_NAMES if buttons & bit)


def modifier_names(modifiers: int) -> frozenset:
    return frozenset(name for bit, name in _MODIFIER_NAMES if modifiers & bit)


class SubdLabWindow(pyglet.window.Window):
    def __init__(
        self,
        asset_name: str,
        width: int = 1280,
        height: int = 800,
        visible: bool = True,
        host_label: str = "unlabeled",
    ) -> None:
        # Window before GL resources: stores compile their shader and build their
        # VertexLists inside this window's context (see `src/main.py`).
        super().__init__(
            width=width, height=height, resizable=True, visible=visible,
            caption=f"Mirai — Subdivision-Mini-Lab ({asset_name})",
        )
        self.host_label = host_label
        self.scene = LabScene(asset_name, aspect=self._aspect())
        topology = self.scene.topology
        self.state = LabState(topology.face_sizes, len(topology.vertex_ids), host_label)
        version, renderer = gl_info_strings()
        self.state.set_gl_info(version, renderer)
        print(f"GL_VERSION:  {version}")
        print(f"GL_RENDERER: {renderer}")

        self._pick_cache = PickCache()
        self._hover_vertex = None
        self._drag_vertex = None
        self._hud_batch = pyglet.graphics.Batch()
        self._hud_labels: list[pyglet.text.Label] = []
        self._hud_revision = -1
        self._frame_ms: Optional[float] = None
        self._last_draw: Optional[float] = None
        self._last_frame_text = 0.0

    # -- helpers -----------------------------------------------------------------

    def _aspect(self) -> float:
        return self.width / self.height if self.height else 1.0

    def _camera_changed(self) -> None:
        self.scene.camera_changed(self._aspect())

    def displayed_level(self) -> Optional[int]:
        """Level of the derived surface being displayed, or None (control mesh)."""
        return self.state.level if self.state.needs_surface() else None

    def _apply_surface_request(self) -> None:
        """Makes sure what the current view needs exists (lazy, cached build);
        the HUD's surface counts always describe the selected level if built
        (also while A/B shows the cage)."""
        if self.state.needs_surface():
            _view, ms, did_work = self.scene.ensure_level(self.state.level)
            if did_work:
                self.state.record_build(ms)
        view = self.scene.views.get(self.state.level)
        self.state.set_derived_counts(None if view is None else (view.derived.n_verts, len(view.derived.faces)))

    def _pick(self, x: float, y: float):
        return pick_nearest_vertex(
            self.scene.camera, self.scene.control_mesh, x, y, self.width, self.height,
            PICK_RADIUS_PX, cache=self._pick_cache,
            occlusion=self.state.effective_view() == VIEW_CAGE,
        )

    def _set_hover(self, vertex_id) -> None:
        self._hover_vertex = vertex_id
        self.scene.set_hover(vertex_id)

    # -- pyglet events -------------------------------------------------------------

    def on_resize(self, width: int, height: int):
        # No EVENT_HANDLED: pyglet's default handler must still set the GL
        # viewport and the 2D projection the HUD labels use.
        self._camera_changed()
        self._hud_revision = -1

    def on_mouse_motion(self, x, y, dx, dy):
        if self._drag_vertex is None:
            self._set_hover(self._pick(x, y))

    def on_mouse_press(self, x, y, button, modifiers):
        if lb.resolve_drag(button_names(button), modifier_names(modifiers)) == lb.DRAG_VERTEX:
            vertex = self._pick(x, y)
            self._drag_vertex = vertex
            self._set_hover(vertex)

    def on_mouse_release(self, x, y, button, modifiers):
        if self._drag_vertex is not None:
            self._drag_vertex = None
            self._pick_cache.invalidate()
            self._set_hover(self._pick(x, y))

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        action = lb.resolve_drag(button_names(buttons), modifier_names(modifiers))
        camera = self.scene.camera
        if action == lb.ORBIT:
            camera.orbit(-dx * ORBIT_RADIANS_PER_PIXEL, -dy * ORBIT_RADIANS_PER_PIXEL)
            self._camera_changed()
        elif action == lb.PAN:
            camera.pan(dx, dy, self.width, self.height)
            self._camera_changed()
        elif action == lb.DRAG_VERTEX and self._drag_vertex is not None:
            self.drag_vertex_by(self._drag_vertex, dx, dy)

    def drag_vertex_by(self, vertex_id, dx: float, dy: float) -> float:
        """One drag event: moves `vertex_id` by a screen delta and updates the
        displayed surface. Returns the update time in ms (also in the HUD)."""
        scene = self.scene
        index = scene.surface.index_of_vertex(vertex_id)
        current = scene.control_positions[index]
        delta = scene.camera.screen_delta_to_world(current, dx, dy, self.width, self.height)
        ms = scene.move_control_vertex(vertex_id, vecmath.add(current, delta), self.displayed_level())
        self._pick_cache.invalidate()
        self.state.record_drag(ms)
        return ms

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        # pyglet reports no modifiers for scroll events.
        if scroll_y and lb.resolve_scroll(frozenset()) == lb.ZOOM:
            self.scene.camera.dolly(0.9 if scroll_y > 0 else 1.1)
            self._camera_changed()

    def on_key_press(self, symbol, modifiers):
        action = lb.resolve_key(_key.symbol_string(symbol), modifier_names(modifiers))
        if action is None:
            return None
        state = self.state
        if action in _LEVEL_ACTIONS:
            if state.request_level(_LEVEL_ACTIONS[action]):
                self._apply_surface_request()
        elif action == lb.CYCLE_VIEW:
            state.cycle_view()
            self._apply_surface_request()
        elif action == lb.TOGGLE_CAGE_DEPTH:
            state.toggle_cage_depth()
        elif action == lb.TOGGLE_AB:
            state.toggle_ab()
            self._apply_surface_request()
        elif action == lb.TOGGLE_HUD:
            state.toggle_hud()
        elif action == lb.BENCH:
            self.run_bench()
        elif action == lb.QUIT:
            self.close()
        return pyglet.event.EVENT_HANDLED

    def on_draw(self):
        now = time.perf_counter()
        if self._last_draw is not None:
            ms = (now - self._last_draw) * 1000.0
            self._frame_ms = ms if self._frame_ms is None else (
                self._frame_ms + FRAME_EMA * (ms - self._frame_ms))
        self._last_draw = now

        self.draw_scene()
        if self.state.hud_visible:
            self._update_hud(now)
            self._hud_batch.draw()

    def draw_scene(self) -> None:
        self.scene.draw(self.state.effective_view(), self.state.level, self.state.cage_depth_test)

    # -- bench (F9) ----------------------------------------------------------------------

    def run_bench(self, runs: Optional[int] = None, plan=None, budget_s: Optional[float] = None) -> str:
        """Runs `bench.run_bench` in this window's GL context (its own throw-away
        scenes; the lab's scene is untouched) and prints the report. Blocks the
        window — no events, no redraws — until it is done. Arguments default to
        the bench defaults (30 runs, head + man_with_shoes, levels 1-3)."""
        from . import bench

        self.switch_to()
        self.state.set_note("Bench läuft … (Fenster friert ein, Fortschritt in der Konsole)")
        print("Bench startet — das Fenster reagiert bis zum Ende nicht.", flush=True)
        result = bench.run_bench(
            self.host_label,
            runs=bench.DEFAULT_RUNS if runs is None else runs,
            plan=bench.DEFAULT_PLAN if plan is None else plan,
            window_mode=bench.MODE_VISIBLE if self.visible else bench.MODE_HIDDEN,
            width=self.width, height=self.height,
            budget_s=bench.DEFAULT_BUDGET_S if budget_s is None else budget_s,
        )
        report = result.format()
        print(report, flush=True)
        self.state.set_note("Bench fertig — Tabelle steht in der Konsole")
        return report

    # -- HUD -----------------------------------------------------------------------------------

    def _update_hud(self, now: float) -> None:
        frame_due = now - self._last_frame_text >= FRAME_TEXT_INTERVAL_S
        if self._hud_revision == self.state.revision and not frame_due:
            return
        self._hud_revision = self.state.revision
        self._last_frame_text = now
        lines = self.state.hud_lines(self._frame_ms)
        while len(self._hud_labels) < len(lines):
            self._hud_labels.append(pyglet.text.Label(
                "", font_name=HUD_FONT, font_size=HUD_FONT_SIZE,
                x=HUD_MARGIN, y=0, anchor_x="left", anchor_y="top",
                batch=self._hud_batch,
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
