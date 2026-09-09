"""Event- und Matrix-Trace: Scheduled orbit vs. Maus-orbit.

Zwei Phasen (je 6 Sekunden):

Phase A (0-6 s)  — Scheduled orbit via pyglet.clock
  camera.orbit(0.012, 0) wird 60x/s aufgerufen ohne Maus-Input.
  Wenn u_view[0] sich hier veraendert: Rendering+Matrix-Pfad ist OK.
  Wenn er konstant bleibt: build_view_matrix() gibt trotz orbit() denselben Wert.

Phase B (6-12 s) — Maus-orbit (LMB halten + ziehen)
  Jeder Maus-Event wird BEDINGUNGSLOS geloggt.
  Zeigt ob on_mouse_press / on_mouse_drag ueberhaupt gefeuert werden.

Aufruf:
    python experiments/mirai_bastel_integration_lab/_diag_events.py

WICHTIG fuer Phase B: Maus ins Fenster, LMB gedrueckt halten und ziehen.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import pyglet
from pyglet import gl
from pyglet.graphics import shader

_THIS_DIR = Path(__file__).resolve().parent
_REPO = _THIS_DIR.parent.parent
for _p in (str(_THIS_DIR), str(_REPO), str(_REPO / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scene.scene_objects import build_cube_scene
from adapters.core_to_render import CoreRenderBinding, LabPygletStore, flatten_render_mesh
from lab_camera import LabOrbitCamera

_VERT = """
#version 330 core
in vec3 position; in vec3 normal; in vec3 color;
uniform mat4 u_view; uniform mat4 u_proj;
uniform vec4 u_base_color; uniform vec3 u_light_dir;
out vec4 frag_color;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    float ndl = max(dot(normal, u_light_dir), 0.0);
    frag_color = vec4(color * mix(vec3(0.35), vec3(1.0), ndl) * u_base_color.rgb, 1.0);
}
"""
_FRAG = """
#version 330 core
in vec4 frag_color; out vec4 out_color;
void main() { out_color = frag_color; }
"""


def _proj(aspect):
    f = 1.0 / math.tan(math.radians(45.0) * 0.5)
    nf = 1.0 / (0.1 - 100.0)
    return [f/aspect,0,0,0, 0,f,0,0, 0,0,(100+0.1)*nf,-1, 0,0,2*100*0.1*nf,0]


class _EventWindow(pyglet.window.Window):
    def __init__(self):
        super().__init__(640, 480,
                         caption="Event+Matrix Trace  [A=Scheduled | B=Maus-Drag] (Esc)",
                         resizable=False, vsync=True)
        self.program = shader.ShaderProgram(
            shader.Shader(_VERT, "vertex"), shader.Shader(_FRAG, "fragment"))

        cube = build_cube_scene()
        binding = CoreRenderBinding(cube.mesh, store_type=LabPygletStore)
        buf = flatten_render_mesh(binding)
        self.vlist = self.program.vertex_list_indexed(
            buf["n"], gl.GL_TRIANGLES, buf["indices"],
            position=("f", buf["positions"]),
            normal  =("f", buf["normals"]),
            color   =("f", [1.0, 1.0, 1.0] * buf["n"]),
        )

        self.camera = LabOrbitCamera(distance=8.0, yaw=0.5, pitch=0.4)
        self._phase = "A"
        self._frame = 0
        self._last_uview0 = None
        self._press_count = 0
        self._drag_count  = 0
        self._drag_btn    = None

        # Phase A: orbit per Scheduler
        pyglet.clock.schedule_interval(self._sched_orbit, 1/60)
        pyglet.clock.schedule_once(self._start_phase_b, 6.0)

        print("\n" + "="*60, flush=True)
        print("PHASE A: Scheduled orbit (6 s) — kein Maus-Input noetig", flush=True)
        print("  Erwartet: u_view[0] aendert sich jede Zeile", flush=True)
        print("="*60, flush=True)

    # -- Phase-Wechsel -------------------------------------------------------
    def _sched_orbit(self, dt):
        if self._phase == "A":
            self.camera.orbit(0.012, 0.0)

    def _start_phase_b(self, dt):
        self._phase = "B"
        self._last_uview0 = None   # Reset fuer sauberen Vergleich
        print("\n" + "="*60, flush=True)
        print("PHASE B: Maus-Drag (6 s) — BITTE LMB HALTEN + ZIEHEN", flush=True)
        print("  Erwartet: on_mouse_press + on_mouse_drag Prints erscheinen", flush=True)
        print("="*60, flush=True)
        pyglet.clock.schedule_once(self._end, 6.0)

    def _end(self, dt):
        print("\n" + "="*60, flush=True)
        print(f"ERGEBNIS:", flush=True)
        print(f"  Phase A — orbit-calls per Scheduler", flush=True)
        print(f"  Phase B — on_mouse_press gefeuert: {self._press_count}x", flush=True)
        print(f"  Phase B — on_mouse_drag  gefeuert: {self._drag_count}x", flush=True)
        print("="*60, flush=True)
        self.close()
        pyglet.app.exit()

    # -- Render --------------------------------------------------------------
    def on_draw(self):
        self._frame += 1
        view = list(self.camera.build_view_matrix())
        uview0 = round(view[0], 5)

        # Jede 20. Frame loggen
        if self._frame % 20 == 1:
            changed = (self._last_uview0 is not None and uview0 != self._last_uview0)
            marker = "VERAENDERT <<" if changed else "gleich"
            print(
                f"  [{self._phase} F{self._frame:5d}] u_view[0]={uview0:+.5f}  {marker}",
                flush=True,
            )
        self._last_uview0 = uview0

        gl.glClearColor(0.08, 0.08, 0.12, 1.0)
        self.clear()
        gl.glEnable(gl.GL_DEPTH_TEST)
        self.program.use()
        self.program["u_view"]       = view
        self.program["u_proj"]       = _proj(self.width / self.height)
        inv = 1.0 / math.sqrt(3.0)
        self.program["u_light_dir"]  = (inv, inv, inv)
        self.program["u_base_color"] = [0.35, 0.55, 0.85, 1.0]
        self.vlist.draw(gl.GL_TRIANGLES)
        self.program.stop()
        return pyglet.event.EVENT_HANDLED

    # -- Maus-Events (bedingungslos geloggt) ---------------------------------
    def on_mouse_press(self, x, y, button, modifiers):
        self._press_count += 1
        self._drag_btn = button
        print(
            f"  [MOUSE_PRESS] Phase={self._phase} button={button} xy=({x},{y}) "
            f"press_count={self._press_count}",
            flush=True,
        )
        self.activate()

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._drag_count += 1
        if self._phase == "B":
            self.camera.orbit(dx * 0.005, dy * 0.005)
        if self._drag_count <= 10 or self._drag_count % 20 == 0:
            print(
                f"  [MOUSE_DRAG]  Phase={self._phase} dx={dx:+3d} dy={dy:+3d} "
                f"btn={self._drag_btn} drag_count={self._drag_count} "
                f"u_view[0]={round(self.camera.build_view_matrix()[0],5):+.5f}",
                flush=True,
            )
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x, y, button, modifiers):
        print(f"  [MOUSE_REL]   Phase={self._phase} button={button}", flush=True)
        self._drag_btn = None

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.ESCAPE:
            self.close()
        return pyglet.event.EVENT_HANDLED


def main():
    win = _EventWindow()
    win.set_visible(True)
    win.activate()
    pyglet.app.run()


if __name__ == "__main__":
    main()
