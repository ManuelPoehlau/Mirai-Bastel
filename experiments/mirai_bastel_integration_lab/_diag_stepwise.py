"""Schrittweise Re-Integration des Mirai-Cube — eine Komponente pro Stufe.

Stufe 1 — Echter Mirai-Vertex-Buffer  (eig. Mesh-Daten, aber zeitbasierte Matrix)
Stufe 2 — Echte LabOrbitCamera-Matrix (zeitbasiert animiert, kein Maus-Input)
Stufe 3 — Camera.orbit() per Scheduler (simuliert Maus ohne tatsaechliche Events)
Stufe 4 — Maus-getriebenes orbit()    (echtes on_mouse_drag -> camera.orbit())

Jede Stufe laeuft 4 Sekunden, dann wechselt das Skript automatisch.
Konsole zeigt welche Stufe aktiv ist und ob u_view[0] sich aendert.

Aufruf:
    python experiments/mirai_bastel_integration_lab/_diag_stepwise.py
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

from scene.scene_objects import build_cube_scene        # noqa: E402
from adapters.core_to_render import (                    # noqa: E402
    CoreRenderBinding, LabPygletStore, flatten_render_mesh,
)
from lab_camera import LabOrbitCamera                   # noqa: E402

# ---------------------------------------------------------------------------
# Shader (identisch zum Lab)
# ---------------------------------------------------------------------------
_VERT = """
#version 330 core
in vec3 position;
in vec3 normal;
in vec3 color;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform vec4 u_base_color;
uniform vec3 u_light_dir;
out vec4 frag_color;
void main() {
    gl_Position = u_proj * u_view * vec4(position, 1.0);
    float ndl = max(dot(normal, u_light_dir), 0.0);
    vec3 shaded = color * mix(vec3(0.35), vec3(1.0), ndl);
    frag_color = vec4(shaded * u_base_color.rgb, 1.0);
}
"""
_FRAG = """
#version 330 core
in vec4 frag_color;
out vec4 out_color;
void main() { out_color = frag_color; }
"""

_STAGE_DURATION = 4.0   # Sekunden pro Stufe
_LOG_INTERVAL  = 30     # Frames zwischen Konsolenausgaben

_STAGE_LABELS = {
    1: "Echter Mirai-Vertex-Buffer  (zeitbasierte Matrix)",
    2: "Echte LabOrbitCamera-Matrix (zeitbasiert, kein Input)",
    3: "camera.orbit() per Scheduler (simulierter Maus-Drag)",
    4: "Maus-getriebenes orbit()     (echtes on_mouse_drag)",
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen (zeitbasierte Fallback-Matrizen)
# ---------------------------------------------------------------------------
def _proj(aspect, fovy_deg=45.0, near=0.1, far=100.0):
    f = 1.0 / math.tan(math.radians(fovy_deg) * 0.5)
    nf = 1.0 / (near - far)
    return [
        f/aspect, 0, 0,              0,
        0,        f, 0,              0,
        0,        0, (far+near)*nf, -1,
        0,        0, 2*far*near*nf,  0,
    ]


def _view_y_rot(t, dist=8.0):
    """Zeitbasierte Y-Rotation (Fallback fuer Stufen 1+2a)."""
    c, s = math.cos(t), math.sin(t)
    return [c, 0, s, 0, 0, 1, 0, 0, -s, 0, c, 0, 0, 0, -dist, 1]


# ---------------------------------------------------------------------------
# Haupt-Fenster
# ---------------------------------------------------------------------------
class _StepWindow(pyglet.window.Window):
    def __init__(self):
        super().__init__(
            640, 480,
            caption="Schrittweise Re-Integration (Esc=Ende)",
            resizable=False,
            vsync=True,
        )
        self.program = shader.ShaderProgram(
            shader.Shader(_VERT, "vertex"),
            shader.Shader(_FRAG, "fragment"),
        )

        # --- Echte Mirai-Komponenten ---------------------------------------
        self._cube_scene = build_cube_scene()
        self._binding = CoreRenderBinding(
            self._cube_scene.mesh,
            store_type=LabPygletStore,
        )
        buf = flatten_render_mesh(self._binding)
        # Vertex-Liste aus echten Mirai-Bufferdaten, aber in UNSEREM Shader
        self._mirai_vlist = self.program.vertex_list_indexed(
            buf["n"], gl.GL_TRIANGLES, buf["indices"],
            position=("f", buf["positions"]),
            normal=("f", buf["normals"]),
            color=("f", [1.0, 1.0, 1.0] * buf["n"]),
        )

        # Echte LabOrbitCamera
        self._camera = LabOrbitCamera(
            distance=8.0,
            yaw=math.radians(45.0),
            pitch=math.radians(25.0),
        )

        # Stage-Zustand
        self._stage = 1
        self._stage_t0 = time.perf_counter()
        self._t0 = time.perf_counter()
        self._frame = 0
        self._last_uview0 = None
        self._drag_button = None

        # Stufe 3: Scheduled orbit
        self._sched_active = False

        pyglet.clock.schedule_once(self._advance_stage, _STAGE_DURATION)
        self._print_stage_header()

    # -- Stage-Wechsel -------------------------------------------------------
    def _print_stage_header(self):
        print(f"\n{'='*60}", flush=True)
        print(f"STUFE {self._stage}: {_STAGE_LABELS[self._stage]}", flush=True)
        print(f"{'='*60}", flush=True)

    def _advance_stage(self, dt):
        if self._stage >= 4:
            print("\n[diag] Alle Stufen abgeschlossen. Fenster bleibt offen (Esc).", flush=True)
            return
        # Stufe 3-Scheduler deaktivieren wenn wir weiterschalten
        if self._stage == 3 and self._sched_active:
            pyglet.clock.unschedule(self._sched_orbit)
            self._sched_active = False
        self._stage += 1
        self._stage_t0 = time.perf_counter()
        self._print_stage_header()
        # Stufe 3: Scheduled orbit starten
        if self._stage == 3:
            pyglet.clock.schedule_interval(self._sched_orbit, 1/60)
            self._sched_active = True
        pyglet.clock.schedule_once(self._advance_stage, _STAGE_DURATION)

    def _sched_orbit(self, dt):
        """Stufe 3: orbit() ohne Maus, per Clock-Tick."""
        self._camera.orbit(0.012, 0.0)   # ~0.7 rad/s am Bildschirm

    # -- Render --------------------------------------------------------------
    def on_draw(self):
        t = time.perf_counter() - self._t0
        self._frame += 1
        log = (self._frame % _LOG_INTERVAL == 1)

        # --- View-Matrix je nach Stufe -------------------------------------
        if self._stage == 1:
            # Zeitbasierte Matrix, echte Mirai-Vertex-Daten
            view = _view_y_rot(t * 0.3)
        elif self._stage == 2:
            # Echte LabOrbitCamera, zeitbasiert animiert (yaw wechselt)
            self._camera.yaw = math.radians(45.0) + t * 0.3
            view = list(self._camera.build_view_matrix())
        elif self._stage == 3:
            # orbit() kommt vom Scheduler (_sched_orbit), camera hat Live-State
            view = list(self._camera.build_view_matrix())
        else:  # Stufe 4
            # view kommt aus on_mouse_drag (camera.orbit wird dort gesetzt)
            view = list(self._camera.build_view_matrix())

        proj = _proj(self.width / self.height)

        # Aenderungs-Check
        uview0 = round(view[0], 4)
        changed = (self._last_uview0 is not None and uview0 != self._last_uview0)
        self._last_uview0 = uview0

        if log:
            print(
                f"  [S{self._stage} F{self._frame:5d}] "
                f"u_view[0]={uview0:+.4f}  "
                f"{'VERAENDERT ✓' if changed else 'gleich wie letztes Mal'}",
                flush=True,
            )

        # --- GL zeichnen --------------------------------------------------
        gl.glClearColor(0.08, 0.08, 0.12, 1.0)
        self.clear()
        gl.glEnable(gl.GL_DEPTH_TEST)

        self.program.use()
        self.program["u_view"]       = view
        self.program["u_proj"]       = proj
        inv = 1.0 / math.sqrt(3.0)
        self.program["u_light_dir"]  = (inv, inv, inv)
        self.program["u_base_color"] = [0.35, 0.55, 0.85, 1.0]

        self._mirai_vlist.draw(gl.GL_TRIANGLES)
        self.program.stop()
        return pyglet.event.EVENT_HANDLED

    # -- Maus (Stufe 4) ------------------------------------------------------
    def on_mouse_press(self, x, y, button, modifiers):
        self._drag_button = button
        self.activate()

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self._stage == 4 and self._drag_button is not None:
            self._camera.orbit(dx * 0.005, dy * 0.005)
            print(
                f"  [S4] mouse_drag dx={dx} dy={dy}  "
                f"yaw={math.degrees(self._camera.yaw):.1f}°  "
                f"u_view[0]={round(self._camera.build_view_matrix()[0], 4):+.4f}",
                flush=True,
            )
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x, y, button, modifiers):
        self._drag_button = None
        return pyglet.event.EVENT_HANDLED

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.ESCAPE:
            self.close()
        return pyglet.event.EVENT_HANDLED


def main():
    win = _StepWindow()
    win.set_visible(True)
    pyglet.app.run()
    print(f"\n[diag] Ende — {win._frame} Frames total", flush=True)


if __name__ == "__main__":
    main()
