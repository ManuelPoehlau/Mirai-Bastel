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

Display (WP-06 B5a, E36-E40): `set_display(show_faces, show_edges, flat)` ist
die schlichte Setter-API — der Viewport kennt kein `DisplayState` (das lebt
in `src.mirai`). Flat Shading und Polygon-Offset reicht er per Duck-Typing an
den Store weiter (`set_draw_style`, nur `GLRenderStore`). Edges sind ein
eigenes Linien-Overlay: `sync()` berechnet `edge_segments` neu, wenn Vertices
bewegt wurden oder die Topologie sich geändert hat — und nur, solange Edges
sichtbar sind (Zähler `line_overlay_rebuilds`). Ein `line_overlay_type`
(z. B. `GLLineOverlay`) bekommt sie und zeichnet sie in `render()` zwischen
Mesh und Punkten.

Kein Fenster-/Event-Loop-Code hier (siehe Paket-Docstring in `__init__.py`).
"""

from __future__ import annotations

from core import Mesh, Selection, VertexId

from .overlay import SelectionOverlay
from .render_mesh import RenderMesh
from .resource_store import ResourceStore, TraceStore
from .wireframe import edge_segments


class Viewport:
    """Dünne Integrationsfassade für den Viewport v0.2."""

    def __init__(
        self,
        mesh: Mesh,
        selection: Selection | None = None,
        store_type: type[ResourceStore] = TraceStore,
        point_overlay_type: type | None = None,
        line_overlay_type: type | None = None,
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
        self.line_overlay = (
            line_overlay_type() if line_overlay_type is not None else None
        )
        self.edge_segments: list = []
        self._edges_dirty = True
        # Startzustand = DisplayState-Default (Shaded, kein Overlay).
        self.show_faces = True
        self.show_edges = False
        self.flat = False

    # -- Display (WP-06 B5a, E36) ----------------------------------------------

    def set_display(self, show_faces: bool, show_edges: bool, flat: bool) -> None:
        """Setzt, was gezeichnet wird. Kein Rebuild der Base-Geometrie; die
        Edge-Segmente folgen beim nächsten `sync()`, falls sie veraltet sind."""
        self.show_faces = bool(show_faces)
        self.show_edges = bool(show_edges)
        self.flat = bool(flat)
        set_draw_style = getattr(self.render_mesh.store, "set_draw_style", None)
        if set_draw_style is not None:
            set_draw_style(
                flat=self.flat, polygon_offset=self.show_faces and self.show_edges
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
        if vertex_ids:
            self._points_dirty = True
            self._edges_dirty = True

    def on_topology_changed(self) -> None:
        self.render_mesh.mark_topology_dirty()
        self._points_dirty = True
        self._edges_dirty = True

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
        if self.show_edges and self._edges_dirty:
            self._sync_edges()

    def _sync_points(self) -> None:
        self.point_positions = self.overlay.point_layers(self.mesh)
        if self.point_overlay is not None:
            for layer, positions in self.point_positions.items():
                self.point_overlay.set_points(layer, positions)
        self._points_dirty = False

    def _sync_edges(self) -> None:
        # E39: voller Neuaufbau pro dirty Frame (für B5a akzeptiert).
        self.edge_segments = edge_segments(self.mesh)
        if self.line_overlay is not None:
            self.line_overlay.set_segments(self.edge_segments)
        self.render_mesh.stats.count("line_overlay_rebuilds")
        self._edges_dirty = False

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
        # Reihenfolge (E40): Faces, Edges, Punkte.
        if self.show_faces:
            self.render_mesh.render(self.render_mesh.camera)
        if self.line_overlay is None and self.point_overlay is None:
            return None
        # Dieselbe Matrix-Quelle wie die `camera_uniforms` des Mesh
        # (gebundene Kamera + synchronisierter Aspect) - kein zweiter
        # Kamera-Matrix-Pfad (WP-06 B2b, E17).
        camera_uniforms = self.render_mesh._camera_uniforms()
        if self.line_overlay is not None and self.show_edges:
            self.line_overlay.draw(camera_uniforms)
        if self.point_overlay is not None:
            self.point_overlay.draw(camera_uniforms)

    # -- Zugriff für Tests/Diagnose -------------------------------------------

    @property
    def benchmark_counters(self) -> dict:
        return self.render_mesh.benchmark_counters

    def resource_ids(self) -> dict[str, int]:
        return self.render_mesh.resource_ids()
