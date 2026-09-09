"""Integrations-Viewport: pyglet-Fenster, das alle Lab-Objekte darstellt.

Reiner Harness-Code des Integration Labs — KEIN Production-Viewport. Seit
WP-IL-01 (2026-09-08) nutzt er die Production-Render-Architektur
(`src.viewport.Viewport` → RenderMesh + ResourceStore + SelectionOverlay,
Gate 5/7) über `CoreRenderBinding` und die Production-Kamera
(`src.mirai.viewport.camera.OrbitCamera` als `LabOrbitCamera`-Subklasse).

Bewusst weiterhin Harness (Audit §E): echtes pyglet-Fenster, GL-Kontext,
eigener Shader + eigene Draw-Vlists (Production hat noch keinen Entry-Point
und `Viewport.render()` ist ein No-Op), HUD/Instrumentierung. Der Draw-Feed
liest die Matrizen direkt von derselben Kamera-Instanz, die über
`bind_camera` am Production-Viewport hängt — ein kanonischer Kamera-Pfad,
keine Zustands-Spaltung (siehe adapters/core_to_render.py).

Interaktion (Ziel: End-to-End-Test aus der Task):
    LMB ziehen        Orbit          (Camera-Kanal: nur Uniforms)
    Shift+LMB / MMB   Pan
    Mausrad           Zoom
    LMB-Klick         Vertex auswählen (nur Selection-/Highlight-Kanal)
    M                 selektierten Vertex bewegen
                      → ZUERST src.core.Mesh, dann Render-Partial-Update
    1 / 2             Objekt auswählen (Cube <-> Head Basemesh) + Frame
    R                 Kamera auf aktives Objekt rahmen
    S                 Report/Statistik (aktueller Stand)
    Esc / Q           Beenden
"""

from __future__ import annotations

import math
import time

import pyglet
from pyglet import gl
from pyglet.graphics import shader
from pyglet.window import key as _key

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from adapters.core_to_render import (  # noqa: E402
    CoreRenderBinding,
    LabPygletStore,
    flatten_render_mesh,
)
from adapters.obj_to_core import frame_camera_on_bounds  # noqa: E402
from adapters.picking import pick_vertex  # noqa: E402
from lab_camera import LabOrbitCamera  # noqa: E402
from scene.scene import LabObject, LabScene  # noqa: E402

# Shader-Quellen identisch zum V0.2-Demonstrator (Wiederverwendung).
_VERT_SRC = """
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

_FRAG_SRC = """
#version 330 core
in vec4 frag_color;
out vec4 out_color;
void main() {
    out_color = frag_color;
}
"""

# Versionstag: erscheint im Fenstertitel, im HUD und im Konsolen-Banner.
# Damit ist jederzeit nachpruefbar, WELCHER Code-Stand ausgefuehrt wird
# (Befund 2026-07-09: Aenderungen schienen am Endgeraet nicht anzukommen).
LAB_VERSION = "v4.0-wpil01 (2026-09-08)"

# HUD-Konstanten auf Modulebene (headless testbar, siehe tests/test_hud.py).
_STATUS_TITLE = "INTEGRATION LAB — LIVE-INSTRUMENTIERUNG"
_HINT_TEXT = (
    "LMB ziehen=Orbit  Shift+LMB/MMB=Pan  Rad=Zoom  Klick=Vertex\n"
    "M=Move(+Y)  1/2=Objekt+Frame  R=Frame  S=Report  Esc=Ende"
)


def _flatten(values, width: int) -> list[float]:
    out: list[float] = []
    for v in values:
        out.extend(v)
    return out


class _ObjectView:
    """Render-Ansicht eines Lab-Objekts: Binding + GPU-Buffer + Overlay."""

    def __init__(self, name: str, binding: CoreRenderBinding) -> None:
        self.name = name
        self.binding = binding
        self.vlist = None
        self.hl_vlist = None

    @property
    def render(self):
        return self.binding.render


class IntegrationLabWindow(pyglet.window.Window):
    def __init__(self, lab_scene: LabScene) -> None:
        # pyglet 2.1 auf Windows erstellt ohne explizite Config keinen Depth-Puffer.
        # Das fuehrt zu unsichtbaren Flächen trotz glEnable(GL_DEPTH_TEST).
        # Dieser Fix ist additiv im Integration-Lab - V0.2 bleibt unberührt.
        from pyglet import gl
        config = gl.Config(depth_size=24, stencil_size=8)
        super().__init__(
            1280, 800,
            caption=f"Mirai-Bastel — Integration Lab / Test Studio [{LAB_VERSION}]",
            resizable=True, vsync=True,
            config=config,
        )
        self.lab = lab_scene
        self.camera = LabOrbitCamera(
            distance=8.0, yaw=math.radians(45.0), pitch=math.radians(28.0)
        )
        self.program = shader.ShaderProgram(
            shader.Shader(_VERT_SRC, "vertex"), shader.Shader(_FRAG_SRC, "fragment")
        )

        self.objects: list[_ObjectView] = []
        self._obj_by_name = {}
        for obj in self.lab.objects:
            self._add_object(obj)
        self._focus_camera(self.lab.active.name)

        self._drag_button = None
        self._drag_moved = 0.0
        self._picked_vertex = None

        self._frame_t0 = time.perf_counter()
        self._fps_ema = 0.0
        self._fps = 0.0

        # pyglet 2.x registriert Methoden-Overrides NICHT automatisch im
        # Event-Stack. Ohne push_handlers() bleibt der Stack leer und die
        # on_mouse_*/on_key_press-Handler werden nie dispatched.
        self.push_handlers(self)

        # _allow_dispatch_event=False bedeutet: Events landen nur in
        # _event_queue, werden aber niemals dispatched. Ohne diese
        # Einstellung reagiert das Fenster nicht auf Maus/Tastatur.
        self._allow_dispatch_event = True

        self._build_labels()

    # -- Aufbau --------------------------------------------------------------
    def _add_object(self, obj: LabObject) -> None:
        binding = CoreRenderBinding(
            obj.scene.mesh,
            store_type=LabPygletStore,
            camera=self.camera,
            selection=obj.scene.selection,
        )
        binding.render.aspect = self.width / self.height
        binding.material.set_base_color(obj.base_color)
        binding.apply_material()
        view = _ObjectView(obj.name, binding)
        self._build_mesh_vbo(view)
        self.objects.append(view)
        self._obj_by_name[obj.name] = obj

    def _build_mesh_vbo(self, view: _ObjectView) -> None:
        buf = flatten_render_mesh(view.binding)
        colors = [1.0, 1.0, 1.0] * buf["n"]
        view.vlist = self.program.vertex_list_indexed(
            buf["n"], gl.GL_TRIANGLES, buf["indices"],
            position=("f", buf["positions"]),
            normal=("f", buf["normals"]),
            color=("f", colors),
        )

    @staticmethod
    def _highlight_color(name: str) -> tuple[float, float, float]:
        if name == "Cube":
            return (1.0, 0.35, 0.35)
        return (1.0, 0.55, 0.25)

    def _refresh_highlight(self, view: _ObjectView) -> None:
        if view.hl_vlist is not None:
            view.hl_vlist.delete()
            view.hl_vlist = None
        sel = sorted(view.binding.selection.vertices)  # Core-Selection: VertexIds
        if not sel:
            return
        positions = _flatten(
            [view.binding.core_mesh.vertex_position(v) for v in sel], 3
        )
        rgb = self._highlight_color(view.name)
        view.hl_vlist = self.program.vertex_list(
            len(sel), gl.GL_POINTS,
            position=("f", positions), color=("f", list(rgb) * len(sel)),
        )

    def _build_labels(self) -> None:
        # Dunkles Panel hinter dem Status: ohne Kontrastfläche war der Text
        # über hellem Mesh kaum lesbar ("kaum lesbare Schrift"-Befund).
        self._hud_panel = pyglet.shapes.Rectangle(
            x=4, y=self.height - 20, width=652, height=12,
            color=(10, 14, 22), batch=None,
        )
        self._hud_panel.opacity = 190
        self._status = pyglet.text.Label(
            "", x=10, y=self.height - 16, anchor_y="top",
            font_name="Consolas", font_size=13, color=(235, 242, 250, 255),
            multiline=True, width=640,
        )
        self._hint = pyglet.text.Label(
            _HINT_TEXT,
            x=10, y=6, font_name="Consolas", font_size=12,
            color=(200, 214, 230, 255),
        )

    def _update_hud_panel(self) -> None:
        """Panel-Groesse an den aktuellen Status-Text anpassen."""
        content_h = getattr(self._status, "content_height", 300) or 300
        self._hud_panel.x = 4
        self._hud_panel.y = max(0, self.height - 16 - content_h - 8)
        self._hud_panel.width = 652
        self._hud_panel.height = min(content_h + 16, self.height - 24)

    def active_view(self) -> _ObjectView:
        return self.objects[self.lab.active_index]

    def _focus_camera(self, name: str) -> None:
        obj = self.lab.select_by_name(name)
        frame_camera_on_bounds(self.camera, obj.mesh, margin=1.4)
        self._push_camera()

    def _push_camera(self) -> None:
        if self.height == 0:
            return  # pyglet 2.1 Windows: transientes on_resize mit height=0 beim Start
        aspect = self.width / self.height
        for view in self.objects:
            view.binding.apply_camera(aspect)

    # -- Events --------------------------------------------------------------
    def on_resize(self, width: int, height: int) -> None:
        gl.glViewport(0, 0, max(1, width), max(1, height))
        if height == 0:
            return pyglet.event.EVENT_HANDLED  # pyglet 2.1: transientes Resize während Init
        self._push_camera()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        self._drag_button = button
        self._drag_moved = 0.0

    def on_mouse_drag(self, x: int, y: int, dx: int, dy: int, buttons: int,
                      modifiers: int) -> None:  # noqa: PLR0913
        self._drag_moved += abs(dx) + abs(dy)
        from pyglet.window import mouse as _m
        if self._drag_button == _m.LEFT and not (modifiers & _key.MOD_SHIFT):
            self.camera.orbit(dx * 0.005, dy * 0.005)
            self._push_camera()
        elif self._drag_button == _m.MIDDLE or (
                self._drag_button == _m.LEFT and modifiers & _key.MOD_SHIFT):
            self.camera.pan(dx, dy, self.width, self.height)
            self._push_camera()
        return pyglet.event.EVENT_HANDLED

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        from pyglet.window import mouse as _m
        if button == _m.LEFT and self._drag_moved < 5.0:
            self._handle_click_selection(x, y, modifiers)
        self._drag_button = None
        return pyglet.event.EVENT_HANDLED

    def on_mouse_scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        self.camera.dolly(0.9 if scroll_y > 0 else 1.1)
        self._push_camera()
        return pyglet.event.EVENT_HANDLED

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        from pyglet.window import key as _k
        if symbol == _k._1:
            self._focus_camera(self.lab.objects[0].name)
        elif symbol == _k._2:
            self._focus_camera(self.lab.objects[1].name)
        elif symbol in (_k.F, _k.R):
            self._focus_camera(self.lab.active.name)
        elif symbol == _k.M:
            self._move_picked_vertex()
        elif symbol == _k.S:
            self._report()
        elif symbol in (_k.ESCAPE, _k.Q):
            self.close()
        return pyglet.event.EVENT_HANDLED

    # -- Selection / Move (Kern des End-to-End-Tests) -------------------------
    def _handle_click_selection(self, x: int, y: int, modifiers: int) -> None:
        """Eine Buchhaltung: Core-Selection (VertexIds). Die Render-Seite wird
        nur über den Production-Pfad benachrichtigt (apply_selection →
        on_selection_changed → sync → highlight_flags-Ressource)."""
        active = self.lab.active
        view = self.active_view()
        picked = pick_vertex(
            self.camera, active.mesh, x, y, self.width, self.height
        )
        if picked is not None:
            if modifiers & _key.MOD_SHIFT:
                active.scene.selection.toggle(picked)
            else:
                active.scene.selection.set({picked})
            self._picked_vertex = picked
        else:
            active.scene.selection.clear()
            self._picked_vertex = None
        view.binding.apply_selection()
        self._refresh_highlight(view)

    def _move_picked_vertex(self) -> None:
        """Move: ZUERST src.core.Mesh verändern, dann Production-Notifikation
        (`on_vertices_moved` → sync → Positions-/Normalen-Partial-Updates im
        Store), zuletzt der Harness-eigene Vlist-Patch für den sofortigen
        Draw (siehe Modul-Doc: eigener Draw-Pfad bleibt bewusst Harness)."""
        view = self.active_view()
        if self._picked_vertex is None:
            return
        vid = self._picked_vertex
        mesh = view.binding.core_mesh
        if not mesh.is_valid_vertex(vid):
            self._picked_vertex = None
            return
        index = view.binding.index_map.index(vid)
        # 1-Ring über die Production-Derived-Data (Adjazenz, positionsunabhängig)
        _, neighborhood = view.render.derived.affected_neighborhood(mesh, {vid})
        view.binding.move_vertex_by(vid, (0.0, 0.35, 0.0))
        pos_buf = view.vlist.domain.attrib_name_buffers["position"]
        nrm_buf = view.vlist.domain.attrib_name_buffers["normal"]
        pos_buf.set_region(index, 1, list(mesh.vertex_position(vid)))
        for nvid in sorted(neighborhood):
            nrm_buf.set_region(
                view.binding.index_map.index(nvid),
                1,
                list(view.render.derived.vertex_normals[nvid]),
            )
        self._refresh_highlight(view)
# -- Zeichnung ------------------------------------------------------------
    def on_draw(self) -> None:
        now = time.perf_counter()
        dt = now - self._frame_t0
        self._frame_t0 = now
        if dt > 0.0:
            inst = 1.0 / dt
            self._fps_ema = self._fps_ema * 0.9 + inst * 0.1
            self._fps = self._fps_ema

        self.clear()
        self.program.use()
        self.program["u_view"] = self.camera.build_view_matrix()
        self.program["u_proj"] = self.camera.build_projection_matrix(
            self.width / self.height
        )
        inv = 1.0 / math.sqrt(3.0)
        self.program["u_light_dir"] = (inv, inv, inv)
        for view in self.objects:
            obj = self._obj_by_name[view.name]
            self.program["u_base_color"] = list(obj.base_color)
            if view.vlist is not None:
                gl.glEnable(gl.GL_DEPTH_TEST)
                # Bewusst KEIN Back-Face-Culling: Die OBJ-/Cube-Face-Windings
                # sind nicht einheitlich CCW; Culling würde Teile (oder alles)
                # ausblenden (V1-Viewport rendert ebenfalls ohne Culling).
                view.vlist.draw(gl.GL_TRIANGLES)
            if view.hl_vlist is not None:
                gl.glPointSize(10.0)
                gl.glDepthMask(gl.GL_FALSE)
                view.hl_vlist.draw(gl.GL_POINTS)
                gl.glPointSize(1.0)
                gl.glDepthMask(gl.GL_TRUE)
        # HUD immer OHNE Depth-Test zeichnen: Nach dem 3D-Pass ist der
        # Depth-Test noch aktiv (wird erst im Highlight-Zweig deaktiviert).
        # Zoomt man nah heran, liegt die Mesh-Depth vor der HUD-Text-Depth
        # (~0.5) und verdeckt den kompletten Text -> "HUD unsichtbar".
        # (Laufzeit-Probe 2026-07-09: _draw_status laeuft fehlerfrei und
        # Text-Pixel landen im Framebuffer, werden aber bei nahem Zoom vom
        # Mesh verdeckt.) Der Depth-Test wird im naechsten Frame vom
        # 3D-Pass wieder aktiviert.
        gl.glDisable(gl.GL_DEPTH_TEST)
        # Custom Shader deaktivieren, bevor pyglet's eigene
        # Shapes/Text-Rendering läuft. Sonst bleibt der Lab-Shader aktiv
        # und pyglet.text.Label produziert unsichtbare Fragmente.
        self.program.stop()
        self._update_hud_panel()
        self._hud_panel.draw()
        self._draw_status()
        self._hint.draw()
        return pyglet.event.EVENT_HANDLED

    def _draw_status(self) -> None:
        view = self.active_view()
        counters = dict(view.render.stats.counters)
        ids = view.render.store.resource_ids()
        names = (
            "mesh_rebuilds", "structural_rebuilds", "partial_updates",
            "vertex_updates", "geometry_uploads", "bounds_recalculations",
            "camera_updates", "selection_updates", "topology_updates",
            "gpu_resource_creations",
        )
        markers = [
            f"{'[' if i == self.lab.active_index else ' '} {o} "
            f"{']' if i == self.lab.active_index else ' '}"
            for i, o in enumerate(self.lab.names())
        ]
        lines = [
            f"{_STATUS_TITLE} {LAB_VERSION} (aktiv: {view.name})",
            f"FPS ~ {self._fps:5.1f} | Vertices "
            f"{view.binding.vertex_count} | Triangles "
            f"{view.binding.triangle_count}",
            "",
        ]
        for n in names:
            lines.append(f"{n:24s} = {counters.get(n, 0)}")
        lines.append("")
        lines.append("Ressourcen-IDs:")
        for name in sorted(ids):
            lines.append(f"  {name:20s} = {ids[name]}")
        lines.append("")
        lines.append("Objekte: " + " | ".join(markers))
        self._status.text = "\n".join(lines)
        self._status.draw()

    def _report(self) -> None:
        view = self.active_view()
        print("=" * 70)
        print(f"INTEGRATION LAB REPORT — {view.name}")
        print("=" * 70)
        print(f"FPS ~ {self._fps:.1f}")
        print(f"Vertex: {view.binding.vertex_count}  "
              f"Triangles: {view.binding.triangle_count}")
        print("Counter:", dict(view.render.stats.counters))
        print("Resources:", view.render.store.resource_ids())


def main(selftest: bool = False) -> int:
    """Starte das Lab.

    Ohne Argumente: interaktives Fenster bis Esc/Q.

    Mit ``selftest=True`` (run.py ``--selftest``): rendert ~1,2 s, misst
    Pixel der echten Pipeline (Mesh + HUD-Bereiche), druckt PASS/FAIL und
    schliesst automatisch — eindeutiger Sichtbarkeits-Nachweis ueber den
    normalen run.py-Einstieg.
    """
    import platform

    # Konsolen-Banner: Wenn diese Zeilen NICHT erscheinen, wird nicht
    # diese Datei ausgefuehrt (veraltete Run-Config / falscher Einstieg).
    print(f"[integration-lab {LAB_VERSION}] start")
    print(f"[integration-lab] modul:  {__file__}")
    print(
        f"[integration-lab] python: {platform.python_version()}"
        f" | pyglet: {pyglet.version}"
    )

    from scene.scene_objects import build_lab_scene
    lab = build_lab_scene()
    window = IntegrationLabWindow(lab)

    if not selftest:
        pyglet.app.run()
        return 0

    # -- Selbsttest: Pixel-Messung der echten Pipeline -----------------------
    w, h = window.width, window.height
    buf = (gl.GLubyte * (w * h * 3))()
    result = [1]

    def _region_nonblack(x0: int, x1: int, y0: int, y1: int) -> int:
        n = 0
        for y in range(y0, y1):
            base = y * w
            for x in range(x0, x1):
                i = (base + x) * 3
                if buf[i] or buf[i + 1] or buf[i + 2]:
                    n += 1
        return n

    def _measure_and_close(_dt) -> None:
        gl.glFinish()
        gl.glReadPixels(0, 0, w, h, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
        total = _region_nonblack(0, w, 0, h)
        hud_px = _region_nonblack(0, min(680, w), h - 240, h)   # Panel oben links
        hint_px = _region_nonblack(0, min(680, w), 0, 44)       # Hinweistext unten
        print(f"[selftest] nonblack gesamt  : {total}/{w * h}")
        print(f"[selftest] HUD oben links   : {hud_px} Panel-/Text-Pixel")
        print(f"[selftest] Hinweistext unten: {hint_px} Text-Pixel")
        ok = total > w * h * 0.02 and hud_px > 2000 and hint_px > 200
        print(f"[selftest] => {'PASS' if ok else 'FAIL'}")
        result[0] = 0 if ok else 1
        window.close()
        pyglet.app.exit()

    pyglet.clock.schedule_once(_measure_and_close, 1.2)
    pyglet.app.run()
    return result[0]