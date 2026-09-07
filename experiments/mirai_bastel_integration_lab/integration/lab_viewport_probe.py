"""Runtime event probe for the Integration Lab.

TEMPORARY DIAGNOSTIC ARTIFACT — 2026-07-09.

This wrapper was used to prove the runtime event chain:
  run.py -> main() -> IntegrationLabWindow -> pyglet.app.run() -> on_draw/events.

Diagnosis result: the event chain works correctly. The probe is no longer needed
and is kept here only as a record of the diagnostic approach. Do NOT import this
module from run.py — use integration.lab_viewport directly.
"""
from __future__ import annotations

import math

import pyglet
from pyglet import gl

from . import lab_viewport as _lab


class ProbeIntegrationLabWindow(_lab.IntegrationLabWindow):
    """Existing Lab window plus a visible OS-event/runtime probe."""

    def __init__(self, lab_scene):
        self._event_counts = {
            "mouse_press": 0,
            "mouse_drag": 0,
            "mouse_release": 0,
            "mouse_scroll": 0,
            "key_press": 0,
        }
        self._last_event = "INIT"
        self._last_event_detail = "waiting for input"
        self._camera_snapshot = None
        super().__init__(lab_scene)
        self._camera_snapshot = self._camera_state()

    def _build_labels(self):
        super()._build_labels()
        self._hud_panel.opacity = 0
        self._status.color = (0, 0, 0, 0)
        self._hint.color = (0, 0, 0, 0)
        self._draw_counter = 0

        self._probe_panel = pyglet.shapes.Rectangle(
            x=4, y=4, width=700, height=286,
            color=(10, 14, 22), batch=None,
        )
        self._probe_panel.opacity = 215
        self._probe_label = pyglet.text.Label(
            "",
            x=12, y=282,
            anchor_y="top",
            font_name="Consolas",
            font_size=12,
            color=(235, 242, 250, 255),
            multiline=True,
            width=680,
        )

    def _camera_state(self):
        return (
            round(math.degrees(self.camera.yaw), 3),
            round(math.degrees(self.camera.pitch), 3),
            round(self.camera.distance, 3),
            tuple(round(v, 3) for v in self.camera.target),
        )

    def _record(self, name, detail):
        self._event_counts[name] += 1
        self._last_event = name
        self._last_event_detail = detail

    def on_mouse_press(self, x, y, button, modifiers):
        self._record("mouse_press", f"x={x} y={y} button={button} mod={modifiers}")
        return super().on_mouse_press(x, y, button, modifiers)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._record("mouse_drag", f"dx={dx} dy={dy} buttons={buttons} mod={modifiers}")
        result = super().on_mouse_drag(x, y, dx, dy, buttons, modifiers)
        after = self._camera_state()
        if after != self._camera_snapshot:
            self._last_event_detail += " | CAMERA CHANGED"
            self._camera_snapshot = after
        return result

    def on_mouse_release(self, x, y, button, modifiers):
        self._record("mouse_release", f"x={x} y={y} button={button} mod={modifiers}")
        return super().on_mouse_release(x, y, button, modifiers)

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self._record("mouse_scroll", f"x={x} y={y} sx={scroll_x} sy={scroll_y}")
        result = super().on_mouse_scroll(x, y, scroll_x, scroll_y)
        after = self._camera_state()
        if after != self._camera_snapshot:
            self._last_event_detail += " | CAMERA CHANGED"
            self._camera_snapshot = after
        return result

    def on_key_press(self, symbol, modifiers):
        self._record("key_press", f"symbol={symbol} mod={modifiers}")
        result = super().on_key_press(symbol, modifiers)
        after = self._camera_state()
        if after != self._camera_snapshot:
            self._last_event_detail += " | CAMERA CHANGED"
            self._camera_snapshot = after
        return result

    def _update_probe(self):
        c = self._event_counts
        view = self.active_view()
        picked = "-" if self._picked_vertex is None else str(self._picked_vertex)
        yaw, pitch, distance, target = self._camera_state()
        self._probe_label.text = (
            f"{_lab._STATUS_TITLE}\n"
            f"{_lab.LAB_VERSION}  |  EVENT PROBE\n"
            f"\nEVENTS\n"
            f"  mouse_press   = {c['mouse_press']}\n"
            f"  mouse_drag    = {c['mouse_drag']}\n"
            f"  mouse_release = {c['mouse_release']}\n"
            f"  mouse_scroll  = {c['mouse_scroll']}\n"
            f"  key_press     = {c['key_press']}\n"
            f"\nSTATE\n"
            f"  active        = {view.name}\n"
            f"  picked        = {picked}\n"
            f"  yaw/pitch     = {yaw:7.2f} / {pitch:7.2f}\n"
            f"  distance      = {distance:7.2f}\n"
            f"  target        = {target}\n"
            f"\nLAST EVENT\n"
            f"  {self._last_event}: {self._last_event_detail}\n"
            f"\nIf counters stay at 0: window/event dispatch is the problem.\n"
            f"If counters rise but state does not change: handler logic is the problem."
        )

    def on_draw(self):
        super().on_draw()
        self.program.stop()
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)

        self._update_probe()
        self._probe_panel.x = 4
        self._probe_panel.y = max(4, self.height - 292)
        self._probe_panel.width = min(700, max(300, self.width - 8))
        self._probe_label.x = 12
        self._probe_label.y = self.height - 12
        self._probe_panel.draw()
        self._probe_label.draw()


def main(*, selftest: bool = False):
    # The original main() resolves IntegrationLabWindow from its own module
    # globals. Swap only that class for this diagnostic run, then reuse the
    # original scene/setup/self-test code unchanged.
    _lab.IntegrationLabWindow = ProbeIntegrationLabWindow
    return _lab.main(selftest=selftest)
