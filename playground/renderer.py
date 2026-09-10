"""PlaygroundRenderer — Adapter auf src.viewport.Viewport.

Dünne Fassade, die einen Production-Viewport hält und die Notifikations-API
nach außen freilegt. Das eigentliche Draw geschieht im PlaygroundWindow
(eigener Shader + pyglet VertexList), analog zum Integration Lab.

WP-AP-01: renderer.render() ruft viewport.sync() auf und delegiert
draw-Daten an das Window. Viewport.render() bleibt weiterhin No-Op
(kein eigener Entry-Point-Shader in Production).
"""

from __future__ import annotations

from playground._paths import ensure_paths

ensure_paths()

from viewport import Viewport  # noqa: E402  (Production-Viewport)
from viewport.resource_store import TraceStore  # noqa: E402


class PlaygroundRenderer:
    """Adapter auf src.viewport.Viewport.

    Hält eine Viewport-Instanz und exponiert die Notifikations-API
    für das Window/App-Layer. Der eigentliche Draw-Call liegt im Window
    (wie im Integration Lab), da Production-Viewport.render() noch kein
    eigenes GL-Backend hat.
    """

    def __init__(self, viewport: Viewport) -> None:
        self.viewport = viewport

    # -- Notifikations-API ----------------------------------------------------

    def notify_camera_changed(self, aspect: float | None = None) -> None:
        self.viewport.on_camera_changed(aspect=aspect)

    def notify_selection_changed(self) -> None:
        self.viewport.on_selection_changed()

    def notify_topology_changed(self) -> None:
        self.viewport.on_topology_changed()

    def notify_vertices_moved(self, vertex_ids: set) -> None:
        self.viewport.on_vertices_moved(vertex_ids)

    # -- Frame-Lifecycle -------------------------------------------------------

    def sync(self) -> None:
        """Verarbeitet alle Dirty-States (einmal pro Frame vor dem Draw)."""
        self.viewport.sync()

    def render(self, camera, width: int, height: int) -> None:
        """Sync + Production-Render (kein-op bis ein Entry-Point-Shader existiert).

        Das eigentliche Zeichnen passiert im PlaygroundWindow über
        einen eigenen Shader + VertexList (analog Integration Lab).
        """
        if height > 0:
            aspect = width / height
            self.viewport.render_mesh.aspect = aspect
        self.viewport.sync()
        self.viewport.render()
