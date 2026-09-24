"""SymmetryLabWindow — pyglet-Fenster: Events übersetzen, zeichnen, sonst nichts.

Input-Pfad: pyglet-Event → `mirai.pyglet_input` → `LabDispatcher` (löst über
`app.bindings` im Lab-Kontext auf). Keine eigenen Tastatur-Bindings; ESC
schließt das Fenster über das pyglet-Standardverhalten (`on_key_press` wird
bewusst nicht überschrieben).
"""

from __future__ import annotations

import pyglet
from pyglet import gl

from mirai.application import Application
from mirai.pyglet_input import mouse_from_pyglet, wheel_from_pyglet

from .lab_dispatch import LabDispatcher
from .lab_render import LabRenderer
from .lab_scene import load_asset_into


class SymmetryLabWindow(pyglet.window.Window):
    def __init__(self, app: Application, asset_name: str) -> None:
        super().__init__(
            1280, 800,
            caption=f"Mirai-Bastel — Symmetry Lab [{asset_name}]",
            resizable=True,
            vsync=True,
        )
        self.app = app
        self.asset_name = asset_name
        self.dispatcher = LabDispatcher(app, self.width, self.height)
        # AD-010: Szene und VBOs erst jetzt, nachdem der GL-Kontext existiert.
        self.renderer = LabRenderer()
        load_asset_into(app, asset_name)
        self.renderer.rebuild_mesh(app.scene.mesh)
        self.renderer.rebuild_highlight(app.scene.mesh, app.scene.selection.vertices)
        self._status = pyglet.text.Label(
            "", x=10, y=10, font_size=11, color=(220, 220, 220, 255)
        )
        self._update_status()

    def _update_status(self) -> None:
        selected = sorted(self.app.scene.selection.vertices, key=int)
        picked = ", ".join(f"v{int(v)}" for v in selected) or "—"
        vertex_count = len(self.app.scene.mesh.all_vertex_ids())
        self._status.text = (
            f"{self.asset_name} | {vertex_count} V | Auswahl: {picked}"
        )

    # -- Events -------------------------------------------------------------

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        self.dispatcher.resize(width, height)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        inp = mouse_from_pyglet(button, modifiers)
        if inp is not None:
            self.dispatcher.press(inp)

    def on_mouse_drag(
        self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int
    ) -> None:
        self.dispatcher.drag(dx, dy)

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        inp = mouse_from_pyglet(button, modifiers)
        if inp is None:
            return
        if self.dispatcher.release(inp.value, x, y):
            self.renderer.rebuild_highlight(
                self.app.scene.mesh, self.app.scene.selection.vertices
            )
            self._update_status()

    def on_mouse_scroll(self, x: int, y: int, scroll_x: float, scroll_y: float) -> None:
        self.dispatcher.scroll(wheel_from_pyglet(scroll_y))

    def on_draw(self) -> None:
        if self.height == 0:
            return
        camera = self.app.camera
        self.renderer.draw(
            camera.build_view_matrix(),
            camera.build_projection_matrix(self.width / self.height),
        )
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        self._status.draw()
