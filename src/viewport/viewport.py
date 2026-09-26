"""Viewport — Fassade, die RenderMesh + Overlay + Camera-Bindung zu einer
einzigen Integrationsstelle für `src.mirai`/Entry-Points zusammenfasst.

Diese Klasse ist bewusst dünn: Sie enthält KEINE eigene Update-Logik
(das lebt in `RenderMesh`/`DerivedGeometry`/`SelectionOverlay`), sondern nur
Verdrahtung + einen stabilen Aufrufpfad:

    viewport.on_vertices_moved({vid, ...})   # nach einer Core-Operation
    viewport.on_topology_changed()           # nach add_face/split_edge/...
    viewport.on_selection_changed()          # nach selection.set(...)/toggle(...)
    viewport.on_camera_changed()             # nach camera.orbit()/pan()/dolly()
    viewport.sync()                          # einmal pro Frame vor dem Draw
    viewport.render()                        # Draw-Call (nur mit GL-Backend sinnvoll)

Punkt-Overlay (WP-06 B2b, AD-018 §7 Addendum): `sync()` berechnet die
Weltpositionen der Punkt-Layer (`SelectionOverlay.point_layers()`) neu, wenn
sich Selektion/Hover, Vertex-Positionen oder Topologie geändert haben, und
hält sie in `point_positions` (auch headless beobachtbar). Ist ein
`point_overlay_type` übergeben (z. B. `GLPointOverlay`), werden sie dorthin
weitergereicht und in `render()` nach dem Mesh gezeichnet. Das Base-Mesh
wird dabei nie neu aufgebaut.

Kein Fenster-/Event-Loop-Code hier (siehe Paket-Docstring in `__init__.py`).
"""

from __future__ import annotations

from core import Mesh, Selection, VertexId

from .overlay import SelectionOverlay
from .render_mesh import RenderMesh
from .resource_store import ResourceStore, TraceStore


class Viewport:
    """Dünne Integrationsfassade für den Viewport v0.2."""

    def __init__(
        self,
        mesh: Mesh,
        selection: Selection | None = None,
        store_type: type[ResourceStore] = TraceStore,
        point_overlay_type: type | None = None,
    ) -> None:
        self.mesh = mesh
        self.selection = selection if selection is not None else Selection()
        self.overlay = SelectionOverlay(self.selection)
        self.render_mesh = RenderMesh(
            mesh, overlay=self.overlay, store_type=store_type
        )
        # Optional (None = headless/TraceStore: es entsteht kein GL-Objekt).
        self.point_overlay = (
            point_overlay_type() if point_overlay_type is not None else None
        )
        self.point_positions: dict[str, list[tuple[float, float, float]]] = {}
        self._points_dirty = True

    # -- Kamera-Bindung (duck-typed, siehe Paket-Docstring) ------------------

    def bind_camera(self, camera) -> None:
        self.render_mesh.bind_camera(camera)
        # Initiale Kamera-Uniforms sofort bereitstellen (nicht erst nach
        # dem ersten on_camera_changed()).
        self.render_mesh.mark_camera_dirty()

    def bind_material(self, material) -> None:
        self.render_mesh.bind_material(material)
        self.render_mesh.mark_material_dirty()

    # -- Notifikations-API (aufgerufen von src.mirai nach Core-Mutationen) --

    def on_vertices_moved(self, vertex_ids: set[VertexId]) -> None:
        self.render_mesh.mark_vertices_dirty(vertex_ids)
        if vertex_ids:
            self._points_dirty = True

    def on_topology_changed(self) -> None:
        self.render_mesh.mark_topology_dirty()
        self._points_dirty = True

    def on_selection_changed(self) -> None:
        self.render_mesh.mark_selection_dirty()
        self._points_dirty = True

    def on_material_changed(self) -> None:
        self.render_mesh.mark_material_dirty()

    def on_camera_changed(self, aspect: float | None = None) -> None:
        self.render_mesh.mark_camera_dirty(aspect=aspect)

    # -- Frame-Lifecycle -----------------------------------------------------

    def sync(self) -> None:
        """Verarbeitet alle seit dem letzten `sync()` markierten Änderungen.
        Muss vor `render()` aufgerufen werden (typischerweise 1x pro Frame)."""
        self.render_mesh.sync()
        if self._points_dirty:
            self._sync_points()

    def _sync_points(self) -> None:
        self.point_positions = self.overlay.point_layers(self.mesh)
        if self.point_overlay is not None:
            for layer, positions in self.point_positions.items():
                self.point_overlay.set_points(layer, positions)
        self._points_dirty = False

    def render(self) -> None:
        """Issue Draw-Call (AD-018 §4.3): delegiert an
        `RenderMesh.render(camera)`, mit der bereits über `bind_camera()`
        gebundenen Kamera. No-Op, solange kein GL-Backend (z.B. `GLRenderStore`)
        gebunden ist oder noch keine Kamera gebunden wurde - siehe
        `RenderMesh.render()`/`resource_store.PygletStore`.

        Bleibt bewusst ohne eigenes Kamera-Argument (wie `sync()`), damit
        `src.mirai`/Entry-Points einen stabilen No-Arg-Aufrufpfad behalten;
        die Kamera-Instanz lebt weiterhin ausschließlich in `RenderMesh`
        (Duck-Typing-Bindung, siehe Paket-Docstring)."""
        if self.render_mesh.camera is None:
            return None
        self.render_mesh.render(self.render_mesh.camera)
        if self.point_overlay is not None:
            # Dieselbe Matrix-Quelle wie die `camera_uniforms` des Mesh
            # (gebundene Kamera + synchronisierter Aspect) - kein zweiter
            # Kamera-Matrix-Pfad (WP-06 B2b, E17).
            self.point_overlay.draw(self.render_mesh._camera_uniforms())

    # -- Zugriff für Tests/Diagnose -------------------------------------------

    @property
    def benchmark_counters(self) -> dict:
        return self.render_mesh.benchmark_counters

    def resource_ids(self) -> dict[str, int]:
        return self.render_mesh.resource_ids()
