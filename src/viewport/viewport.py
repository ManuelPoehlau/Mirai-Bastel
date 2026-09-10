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
    ) -> None:
        self.mesh = mesh
        self.selection = selection if selection is not None else Selection()
        self.overlay = SelectionOverlay(self.selection)
        self.render_mesh = RenderMesh(
            mesh, overlay=self.overlay, store_type=store_type
        )

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

    def on_topology_changed(self) -> None:
        self.render_mesh.mark_topology_dirty()

    def on_selection_changed(self) -> None:
        self.render_mesh.mark_selection_dirty()

    def on_material_changed(self) -> None:
        self.render_mesh.mark_material_dirty()

    def on_camera_changed(self, aspect: float | None = None) -> None:
        self.render_mesh.mark_camera_dirty(aspect=aspect)

    # -- Frame-Lifecycle -----------------------------------------------------

    def sync(self) -> None:
        """Verarbeitet alle seit dem letzten `sync()` markierten Änderungen.
        Muss vor `render()` aufgerufen werden (typischerweise 1x pro Frame)."""
        self.render_mesh.sync()

    def render(self) -> None:
        """Issue Draw-Call. No-Op, solange kein GL-Backend (PygletStore)
        gebunden ist - siehe `resource_store.PygletStore`."""
        # Gate 5 Scope: Der eigentliche Draw-Call (glDrawElements o.ä.) ist
        # Teil des Entry-Points/Window-Adapters (nicht Teil dieses Gates,
        # siehe VIEWPORT_V02_ARCHITECTURE.md §1 "Non-Goals" / Gate-Planung
        # Task 3.9/3.10-Verschiebung). Diese Methode existiert als stabiler
        # Aufrufpunkt für einen künftigen Renderer.
        return None

    # -- Zugriff für Tests/Diagnose -------------------------------------------

    @property
    def benchmark_counters(self) -> dict:
        return self.render_mesh.benchmark_counters

    def resource_ids(self) -> dict[str, int]:
        return self.render_mesh.resource_ids()
