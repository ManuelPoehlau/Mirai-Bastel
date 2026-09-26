"""Lab window: navigation, rig controls, text HUD and capture (handoff E13–E16).

Raw pyglet events as in `src/main.py` (window before GL resources, camera
deltas straight to `OrbitCamera`); every event is resolved through
`lab_bindings` (the one visible table) into `LabState` calls.

Per frame the only Python work is `resolve(rig, camera)` (a few trig calls)
plus uniform setting — no per-vertex work, no buffer upload (§7 constraints).

HUD (E14): `pyglet.text.Label`s in one batch, drawn after the mesh. The
mesh draw sets its own program, depth test and culling on every call, so the
HUD cannot leak state into the next frame (`tests/test_lab_window_gl.py`).
Capture (E15) redraws the mesh without HUD into the back buffer, reads it
back and writes PNG + JSON sidecar.
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pyglet
from pyglet.window import key as _key
from pyglet.window import mouse as _mouse

from . import lab_bindings as lb
from ._paths import CAPTURES_DIR
from .lab_controls import LabState
from .lab_rig import resolve
from .lab_scene import build_scene, save_color_buffer_png
from .lab_store import ShadingLabStore

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
#: Frame-time smoothing (exponential moving average) and HUD refresh for it.
FRAME_EMA = 0.1
FRAME_TEXT_INTERVAL_S = 0.25

ORBIT_RADIANS_PER_PIXEL = 0.005

_BUTTON_NAMES = ((_mouse.LEFT, "LEFT"), (_mouse.RIGHT, "RIGHT"), (_mouse.MIDDLE, "MIDDLE"))
_MODIFIER_NAMES = ((_key.MOD_SHIFT, "shift"), (_key.MOD_CTRL, "ctrl"), (_key.MOD_ALT, "alt"))


def button_names(buttons: int) -> frozenset:
    return frozenset(name for bit, name in _BUTTON_NAMES if buttons & bit)


def modifier_names(modifiers: int) -> frozenset:
    return frozenset(name for bit, name in _MODIFIER_NAMES if modifiers & bit)


class ShadingLabWindow(pyglet.window.Window):
    def __init__(
        self,
        asset_name: str,
        width: int = 1280,
        height: int = 800,
        visible: bool = True,
        captures_dir: Optional[Path] = None,
    ) -> None:
        # Window before GL resources: the store compiles its shader and builds
        # its VertexList inside this window's context (see `src/main.py`).
        super().__init__(
            width=width, height=height, resizable=True, visible=visible,
            caption=f"Mirai — Viewport Shading Lab ({asset_name})",
        )
        self.scene = build_scene(asset_name, ShadingLabStore, aspect=self._aspect())
        self.state = LabState()
        self.captures_dir = Path(captures_dir) if captures_dir is not None else CAPTURES_DIR

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

    def rig_uniforms(self) -> dict:
        """Resolved rig for this frame (camera-space directions follow the camera)."""
        return resolve(self.state.displayed_rig(), self.scene.camera)

    def draw_mesh(self) -> None:
        self.scene.draw(self.rig_uniforms())

    # -- pyglet events -------------------------------------------------------------

    def on_resize(self, width: int, height: int):
        # No EVENT_HANDLED: pyglet's default handler must still set the GL
        # viewport and the 2D projection the HUD labels use.
        self._camera_changed()
        self._hud_revision = -1

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        action = lb.resolve_drag(button_names(buttons), modifier_names(modifiers))
        if action == lb.ORBIT:
            self.scene.camera.orbit(-dx * ORBIT_RADIANS_PER_PIXEL, -dy * ORBIT_RADIANS_PER_PIXEL)
            self._camera_changed()
        elif action == lb.PAN:
            self.scene.camera.pan(dx, dy, self.width, self.height)
            self._camera_changed()
        elif action == lb.DRAG_LIGHT:
            self.state.drag_light(dx, dy)

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        # pyglet reports no modifiers for scroll events.
        if scroll_y and lb.resolve_scroll(frozenset()) == lb.ZOOM:
            self.scene.camera.dolly(0.9 if scroll_y > 0 else 1.1)
            self._camera_changed()

    def on_key_press(self, symbol, modifiers):
        mods = modifier_names(modifiers)
        action = lb.resolve_key(_key.symbol_string(symbol), mods)
        if action is None:
            return None
        state = self.state
        if action == lb.ROW_PREV:
            state.select_row(-1)
        elif action == lb.ROW_NEXT:
            state.select_row(+1)
        elif action in (lb.VALUE_DEC, lb.VALUE_INC):
            state.step_active(-1 if action == lb.VALUE_DEC else +1, fine="shift" in mods)
        elif action in (lb.PRESET_1, lb.PRESET_2, lb.PRESET_3, lb.PRESET_4):
            state.apply_preset_index(int(action[-1]) - 1)
        elif action == lb.TOGGLE_AB:
            state.toggle_ab()
        elif action == lb.TOGGLE_HUD:
            state.toggle_hud()
        elif action == lb.CAPTURE:
            png, _sidecar = self.capture()
            print(f"Aufnahme: {png}")
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

        self.draw_mesh()
        if self.state.hud_visible:
            self._update_hud(now)
            self._hud_batch.draw()

    # -- HUD (E14) --------------------------------------------------------------------

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

    # -- capture (E15) ----------------------------------------------------------------

    def capture(self) -> tuple[Path, Path]:
        """Viewport PNG without HUD + JSON sidecar into `captures_dir`."""
        self.switch_to()
        uniforms = self.rig_uniforms()
        self.scene.draw(uniforms)

        self.captures_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now()
        slug = "".join(c if c.isalnum() else "_" for c in self.state.displayed_name()).strip("_")
        base = f"capture_{stamp:%Y%m%d_%H%M%S}_{slug}"
        png = self.captures_dir / f"{base}.png"
        counter = 1
        while png.exists():
            counter += 1
            png = self.captures_dir / f"{base}_{counter}.png"
        sidecar = png.with_suffix(".json")

        save_color_buffer_png(str(png))
        camera = self.scene.camera
        fb_width, fb_height = self.get_framebuffer_size()
        payload = {
            "timestamp": stamp.isoformat(timespec="seconds"),
            "mesh": self.scene.asset_name,
            "window_size": [self.width, self.height],
            "framebuffer_size": [fb_width, fb_height],
            "preset": self.state.displayed_name(),
            "ab_vergleich_aktiv": self.state.ab_active,
            "rig": self.state.displayed_rig().to_dict(),
            "rig_bearbeitet": self.state.rig.to_dict(),
            "rig_uniforms": {k: (list(v) if isinstance(v, tuple) else v) for k, v in uniforms.items()},
            "camera": {
                "yaw_deg": math.degrees(camera.yaw),
                "pitch_deg": math.degrees(camera.pitch),
                "distance": camera.distance,
                "target": list(camera.target),
            },
        }
        sidecar.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return png, sidecar

