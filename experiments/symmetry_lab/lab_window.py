"""SymmetryLabWindow — pyglet-Fenster: Events übersetzen, zeichnen, sonst nichts.

Input-Pfad: pyglet-Event → `mirai.pyglet_input` → `LabDispatcher` (löst über
`app.bindings` im Lab-Kontext auf). Nach jedem Event holt das Fenster die
gesammelten `Change`-Flags ab und baut VBOs/Overlays/Statuszeile neu auf.

Tastatur (Slice 3): `on_key_press` geht an den Dispatcher. Meldet er „nicht
behandelt" (z. B. ESC ohne scharfen oder laufenden Move), läuft das
pyglet-Standardverhalten — ESC schließt das Fenster wie in Slice 2.

Slice 4: `on_mouse_motion` reicht die Cursor-Position an
`dispatcher.motion()` (Hover-Ziel, E9) weiter.
"""

from __future__ import annotations

import pyglet
from pyglet import gl

from mirai.application import Application
from mirai.pyglet_input import key_from_pyglet, mouse_from_pyglet, wheel_from_pyglet
from mirai.symmetry import mirrored_selection

from .lab_dispatch import Change, LabDispatcher
from .lab_render import LabRenderer
from .lab_scene import load_asset_into
from .lab_status import status_text
from .lab_symmetry import symmetry_report


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
        self._status = pyglet.text.Label(
            "", x=10, y=10, font_size=11, color=(220, 220, 220, 255)
        )
        self._report = symmetry_report(app.scene.mesh)
        self._sync(Change.MESH | Change.SELECTION | Change.HOVER | Change.STATUS)

    def _sync(self, changes: Change) -> None:
        mesh = self.app.scene.mesh
        if Change.MESH in changes:
            self._report = symmetry_report(mesh)
            self.renderer.rebuild_mesh(mesh, self._report)
        if changes & (Change.MESH | Change.SELECTION):
            selected = self.app.scene.selection.vertices
            self.renderer.rebuild_highlight(
                mesh, selected, mirrored_selection(mesh, selected)
            )
        if changes & (Change.MESH | Change.HOVER):
            hovered = (
                {self.dispatcher.hover_vertex}
                if self.dispatcher.hover_vertex is not None
                else set()
            )
            self.renderer.rebuild_hover(mesh, hovered, mirrored_selection(mesh, hovered))
        if changes:
            self._status.text = status_text(
                self.app, self.asset_name, self.dispatcher, self._report
            )

    def _flush(self) -> None:
        self._sync(self.dispatcher.take_changes())

    # -- Events -------------------------------------------------------------

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        self.dispatcher.resize(width, height)

    def on_key_press(self, symbol: int, modifiers: int):
        handled = self.dispatcher.key(key_from_pyglet(symbol, modifiers))
        self._flush()
        if handled:
            return pyglet.event.EVENT_HANDLED
        return super().on_key_press(symbol, modifiers)

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        inp = mouse_from_pyglet(button, modifiers)
        if inp is not None:
            self.dispatcher.press(inp)
            self._flush()

    def on_mouse_drag(
        self, x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int
    ) -> None:
        self.dispatcher.drag(dx, dy)
        self._flush()

    def on_mouse_release(self, x: int, y: int, button: int, modifiers: int) -> None:
        inp = mouse_from_pyglet(button, modifiers)
        if inp is None:
            return
        self.dispatcher.release(inp.value, x, y)
        self._flush()

    def on_mouse_scroll(self, x: int, y: int, scroll_x: float, scroll_y: float) -> None:
        self.dispatcher.scroll(wheel_from_pyglet(scroll_y))

    def on_mouse_motion(self, x: int, y: int, dx: int, dy: int) -> None:
        self.dispatcher.motion(x, y)
        self._flush()

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
