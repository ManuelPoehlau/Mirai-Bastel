"""Bisection: Welche v4.1-Aenderung hat den Display-Freeze behoben?

Startet nacheinander drei Varianten des Labs (je ~10 s):
  Var A — kein wglSwapIntervalEXT(1),  default interval,  kein draw()-Override
  Var B — MIT wglSwapIntervalEXT(1),   interval=0,        kein draw()-Override
  Var C — MIT wglSwapIntervalEXT(1),   default interval,  MIT draw()-Override

In jeder Variante: Cube orbitieren (LMB ziehen), Fenster schliesst automatisch.
Konsole gibt an welche Variante laeuft und ob Drag-Events gefeuert werden.

Hypothesen:
  Wenn Var A freeze  -> wglSwapIntervalEXT(1) war der Fix
  Wenn Var B freeze  -> interval=0 war der Fix
  Wenn Var C freeze  -> draw()-Override war der Fix
  Wenn alle gut      -> Kombination oder anderer Faktor

Aufruf:
    python experiments/mirai_bastel_integration_lab/_diag_bisect.py
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import pyglet
from pyglet import gl
from pyglet.graphics import shader
from pyglet.window import key as _key

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

_WINDOW_DURATION = 10.0   # Sekunden pro Variante


def _proj(aspect):
    f = 1.0 / math.tan(math.radians(45.0) * 0.5)
    nf = 1.0 / (0.1 - 100.0)
    return [f/aspect, 0, 0, 0,  0, f, 0, 0,  0, 0, (100+0.1)*nf, -1,  0, 0, 2*100*0.1*nf, 0]


# ---------------------------------------------------------------------------
# Fenster-Basisklasse (gleich fuer alle Varianten)
# ---------------------------------------------------------------------------
class _BisectWindow(pyglet.window.Window):
    def __init__(self, variant: str, use_vsync_ext: bool, use_draw_override: bool):
        super().__init__(
            640, 480,
            caption=f"Bisect {variant} — LMB ziehen dann beobachten (auto-close {_WINDOW_DURATION:.0f}s)",
            resizable=False,
            vsync=True,       # pyglet-Fenster vsync (Standard) — in allen Varianten gleich
        )
        self.variant = variant
        self._drag_count = 0
        self._drag_btn   = None
        self._frame      = 0

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
        self.camera = LabOrbitCamera(distance=8.0, yaw=math.radians(45), pitch=math.radians(25))

        # --- Varianten-spezifische Einstellungen ---------------------------
        if use_vsync_ext:
            try:
                from pyglet.gl import wgl_info, wglext_arb
                if wgl_info.have_extension("WGL_EXT_swap_control"):
                    wglext_arb.wglSwapIntervalEXT(1)
                    print(f"  [{variant}] wglSwapIntervalEXT(1) gesetzt", flush=True)
            except Exception as e:
                print(f"  [{variant}] wglSwapIntervalEXT nicht verfuegbar: {e}", flush=True)

        self._use_draw_override = use_draw_override

        self.activate()
        pyglet.clock.schedule_once(self._auto_close, _WINDOW_DURATION)

    def _auto_close(self, dt):
        print(f"\n  [{self.variant}] auto-close — Drag-Events in dieser Variante: {self._drag_count}", flush=True)
        self.close()
        pyglet.app.exit()

    # -- draw()-Override (Variante C) ----------------------------------------
    def draw(self, dt: float = 0.0) -> None:
        if self._use_draw_override:
            import ctypes
            self.switch_to()
            self.dispatch_event("on_draw")
            self.dispatch_event("on_refresh", dt)
            self.flip()
            # Genau wie in der alten v4.0: InvalidateRect auf _hwnd (nicht _view_hwnd)
            try:
                ctypes.windll.user32.InvalidateRect(self._hwnd, None, False)
            except Exception:
                pass
        else:
            super().draw(dt)

    # -- Render --------------------------------------------------------------
    def on_draw(self):
        self._frame += 1
        view = list(self.camera.build_view_matrix())

        if self._frame % 30 == 1:
            print(
                f"  [{self.variant} F{self._frame:5d}] u_view[0]={view[0]:+.4f}  "
                f"drags={self._drag_count}",
                flush=True,
            )

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

    # -- Maus ----------------------------------------------------------------
    def on_mouse_press(self, x, y, button, modifiers):
        self._drag_btn = button
        self.activate()

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._drag_count += 1
        self.camera.orbit(dx * 0.005, dy * 0.005)
        if self._drag_count <= 5 or self._drag_count % 15 == 0:
            print(
                f"  [{self.variant}] DRAG #{self._drag_count:3d} "
                f"dx={dx:+3d} u_view[0]={self.camera.build_view_matrix()[0]:+.4f}",
                flush=True,
            )
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x, y, button, modifiers):
        self._drag_btn = None

    def on_key_press(self, symbol, modifiers):
        if symbol == _key.ESCAPE:
            self.close()
            pyglet.app.exit()
        return pyglet.event.EVENT_HANDLED


# ---------------------------------------------------------------------------
# Varianten nacheinander starten
# ---------------------------------------------------------------------------
_VARIANTS = [
    # (label,  vsync_ext, draw_override, interval,     beschreibung)
    ("Var-A", False, False, 1/60,  "KEIN vsync_ext | default interval | KEIN draw()-Override"),
    ("Var-B", True,  False, 0,     "MIT  vsync_ext | interval=0       | KEIN draw()-Override"),
    ("Var-C", True,  False, 1/60,  "MIT  vsync_ext | default interval | MIT  draw()-Override"),
]


def main():
    for label, vsync_ext, draw_override, interval, desc in _VARIANTS:
        print(f"\n{'='*65}", flush=True)
        print(f"STARTE {label}: {desc}", flush=True)
        print(f"  -> LMB halten + ziehen, Fenster schliesst nach {_WINDOW_DURATION:.0f}s", flush=True)
        print(f"{'='*65}", flush=True)

        win = _BisectWindow(label, use_vsync_ext=vsync_ext, use_draw_override=draw_override)
        win.set_visible(True)
        # interval steuert die _redraw_windows-Frequenz
        pyglet.app.run(interval=interval)

    print("\n" + "="*65, flush=True)
    print("BISECTION ABGESCHLOSSEN", flush=True)
    print("Auswertung:", flush=True)
    print("  Var-A freeze? -> wglSwapIntervalEXT(1) war der Fix", flush=True)
    print("  Var-B freeze? -> interval=0 war der Fix", flush=True)
    print("  Var-C freeze? -> draw()-Override war der Fix", flush=True)
    print("="*65, flush=True)


if __name__ == "__main__":
    main()
