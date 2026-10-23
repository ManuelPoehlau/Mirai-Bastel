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

Edge-/Face-Auswahl (WP-06 B5b, E44/E45): `sync()` berechnet mit den Punkten
auch `line_layers` (gehoverte/selektierte Edges als Segmente) und
`face_layers` (gehoverte/selektierte Faces als Dreiecke) aus
`SelectionOverlay` neu — gleiche Dirty-Auslöser wie die Punkte. Ein
`face_overlay_type` (z. B. `GLTriangleOverlay`) bekommt die Dreiecke, die
Edge-Layer gehen an dasselbe `line_overlay` wie die Wire-Segmente.
Zeichenreihenfolge: Mesh → Wire → Faces → Edges → Tool-Linien → Zusatz-Overlays
(H1) → Punkte.

Tool-Layer (WP-06 B7, Knife-Session): `set_tool_overlay(points, segments)`
nimmt fertige Weltpositionen für `overlay.TOOL_LAYERS` entgegen (der
Viewport kennt kein Knife) und reicht sie sofort an Punkt- bzw. Linien-
Overlay weiter; sichtbar headless in `tool_point_layers`/`tool_line_layers`.
Gezeichnet werden sie nach den Selection-Layern (Linien: Pfad-Edges mit
Depth-Test, Preview ohne; Punkte wie alle Punkte ohne Depth-Test). AD-SYM-03
Slice 6c: `overlay.TOOL_SYMMETRY_LAYERS` (Spiegelseite, nicht geschnittener Teil,
abgelehntes Hover-Ziel) laufen über denselben Weg; der Viewport kennt auch dafür
weder Knife noch Symmetrie, nur Layer-Namen, Farben und Tiefenverhalten.

Zusatz-Overlays (WP-SYM-LAB-03 H1): `add_overlay(o)` hängt ein Overlay eines
Hosts an (z. B. die Marker des Symmetry Lab); der Viewport kennt weder seine
Layer noch seine Farben. Vertrag (Duck-Typing): `o.sync(mesh, selection)` läuft
in `sync()`, wenn seit dem letzten `sync()` Selektion/Hover, Vertex-Positionen
oder Topologie gemeldet wurden, beim ersten `sync()` nach `add_overlay` oder
wenn `o.dirty` gesetzt ist (das Overlay setzt `dirty` selbst zurück);
`o.draw(camera_uniforms)` läuft in `render()` nach den Tool-Linien und vor dem
Punkt-Overlay. Ohne Zusatz-Overlay ändert sich nichts.

Objekt-Einträge (AD-021 M1, §4.4 "Drawing"): `set_object_entry(key, mesh, base_color)`
zeichnet ein weiteres Mesh (ein anderes Objekt der Scene) als eigenen `RenderMesh` - ohne
`SelectionOverlay` und ohne Punkt-/Linien-/Flächen-Overlays, denn die Selection hält nackte
IDs des Edit-Objekts, die in einem anderen Mesh gleichlautende Elemente aufleuchten ließen
(AD-021 F-2, review R-5). `self.mesh` bleibt das Mesh des Edit-Objekts; nur dessen Eintrag
trägt die Overlays. Der Schlüssel ist für den Viewport opak (die App nimmt die ObjectId);
`base_color` (None = Standardfarbe) ist der einzige Look-Parameter. Gezeichnet nach dem Edit-Mesh,
mit `show_faces` wie dieses.

Platzierung (AD-021 M2-1, E-9): `set_model_matrix(m)` setzt die Objekt -> Welt-Matrix des
Edit-Objekts (None = Identität). Das Mesh bekommt sie als Uniform; alle Overlays des Edit-
Objekts (Punkte, Linien, Flächen, Tool-Layer, Zusatz-Overlays) zeichnen mit `view·model` statt
`view` - ihre Positionen bleiben Objektraum wie das Mesh, keine Overlay-Shader-Änderung. Jeder
Objekt-Eintrag hat seine eigene Matrix (`set_object_entry(..., model_matrix=)`).

Edit-Objekt wechseln (AD-021 M2-4, E-14): `set_edit_mesh(mesh, model_matrix)` baut den Eintrag
mit den Overlays für ein anderes Mesh neu auf; `self.mesh` ist danach dieses Mesh.

Referenz-Anzeige (AD-021 M2-0, §7.3): ein Eintrag mit `ignores_wireframe=True` wird auch im
Wireframe gezeichnet (RD-3); `alpha < 1` zeichnet ihn als Ghost (RD-1) - nach allen opaken
Einträgen, geblendet, ohne Depth-Write, damit das Edit-Objekt darin sichtbar bleibt.

Worklight (Shading Lab, in die App übernommen 2026-10-15): `set_light(rig)` setzt ein
`light_rig.LightRig`; `render()` löst es pro Frame mit der gebundenen Kamera auf
(`light_uniforms()`) und reicht die Uniforms per Duck-Typing (`set_light_uniforms`, nur
`GLRenderStore`) an das Edit-Mesh und alle Objekt-Einträge. Start: "Raitt 2:1", Kamera.
Glanz (2026-10-23, `material.py`): `set_surface_finish(finish)` legt Specular/Glossiness in jedes
Material, das der Viewport bindet (Edit-Mesh, Ersatzfläche, Objekt-Einträge) - ein Material-Update,
keine Geometrie.

Ersatzfläche (AD-013 Addendum H7, 2026-10-16): `set_surface_provider(p)` lässt einen Host
die Flächen des Edit-Mesh durch ein eigenes, daraus abgeleitetes Mesh ersetzen (z. B. die
Subdivision-Vorschau des SubD Lab); der Viewport kennt kein Verfahren. Vertrag (Duck-Typing):
`p.sync(mesh, selection) -> set[VertexId]` läuft in `sync()` bei denselben Auslösern wie die
Zusatz-Overlays (H1) und gibt die bewegten Vertices von `p.surface_mesh` zurück; `p.surface_mesh`
(ein `core.Mesh` oder None = aus) ist danach das zu zeichnende Mesh - ein anderes Objekt als
beim letzten `sync()` heißt neu aufbauen. Der Viewport besitzt dafür einen `RenderMesh` ohne
`SelectionOverlay` mit Kamera, Material, Licht, Flat/Smooth und Matrix des Edit-Mesh und zeichnet
ihn bei `show_faces` an dessen Stelle. Wire, Auswahl, Tool- und Zusatz-Overlays bleiben auf dem
Edit-Mesh (dem Käfig), Picking ist nicht betroffen. Kamera-Änderungen erreichen die Fläche in
jedem `sync()` wie die Objekt-Einträge, ohne den Provider zu fragen. Ohne Provider ändert sich nichts.
Optional (2026-10-23, SubD in Production): `p.surface_topology_changed` True nach `p.sync(...)` heißt
"dasselbe Mesh-Objekt, Topologie in place geändert" - der Viewport markiert dann die Topologie des
Flächen-RenderMesh (inkrementeller Abgleich über das Journal, AD-023) statt nur bewegter Vertices.

H7-E (2026-10-17, Morph Lab): Ersatzfläche auch für **Objekt-Einträge**. Optional liest der Viewport nach
`p.sync(...)` `p.entry_surfaces` (`dict[key, Mesh]`, `key` wie bei `set_object_entry`) und `p.entry_moved`
(`dict[key, set[VertexId]]`, bewegte Vertices je Mesh; fehlt ein Key, gilt "neu aufgebaut/unverändert"). Für jeden
Key mit vorhandenem Eintrag zeichnet der Viewport an dessen Stelle einen eigenen `RenderMesh` des Ersatz-Meshes mit
Kamera, Material, Matrix, Alpha und Flat/Smooth des Eintrags (jeden Frame nachgeführt); ein Key ohne Eintrag oder ein
Eintrag ohne Ersatz wird wie bisher gezeichnet. Fehlt das Attribut, ändert sich nichts.

Kein Fenster-/Event-Loop-Code hier (siehe Paket-Docstring in `__init__.py`).
"""

from __future__ import annotations

from core import Mesh, Selection, VertexId

from .gl_line_overlay import WIRE_LAYER
from .overlay import (
    HOVER_LAYER,
    SELECTED_LAYER,
    TOOL_ACTIVE_LAYER,
    TOOL_CLIPPED_LAYER,
    TOOL_LAYERS,
    TOOL_MIRROR_DIM_LAYER,
    TOOL_MIRROR_LAYER,
    TOOL_MIRROR_PREVIEW_LAYER,
    TOOL_PREVIEW_LAYER,
    TOOL_REFUSED_LAYER,
    SelectionOverlay,
)

#: Zeichenreihenfolge der Tool-Linien (später = oben): das, was nicht geschnitten wird, unter allem;
#: Pfad und Spiegelpfad (mit Depth-Test); dann alles ohne Depth-Test (Preview, Spiegel-Preview, gedimmte
#: Spiegelseite) und zuletzt die abgelehnte Vorschau.
_TOOL_LINE_DRAW_ORDER = (
    TOOL_CLIPPED_LAYER,
    TOOL_MIRROR_LAYER,
    TOOL_ACTIVE_LAYER,
    TOOL_MIRROR_DIM_LAYER,
    TOOL_MIRROR_PREVIEW_LAYER,
    TOOL_PREVIEW_LAYER,
    TOOL_REFUSED_LAYER,
)
#: Tool-Layer, deren Linien auf den Faces liegen (Depth-Test) und deshalb den Polygon-Offset brauchen.
_TOOL_DEPTH_TESTED_LINES = (TOOL_ACTIVE_LAYER, TOOL_MIRROR_LAYER, TOOL_CLIPPED_LAYER)
from .gl_render_store import DEFAULT_BASE_COLOR


def _mat4_mul(a: list[float], b: list[float]) -> list[float]:
    """a·b für spaltenweise 4x4-Matrizen (GL-Konvention wie die Kamera-Matrizen)."""
    out = [0.0] * 16
    for col in range(4):
        for row in range(4):
            out[col * 4 + row] = sum(a[k * 4 + row] * b[col * 4 + k] for k in range(4))
    return out
from .light_rig import DEFAULT_PRESET, PRESETS, SPACE_WORLD, LightRig, resolve
from .material import DEFAULT_FINISH, Material, SurfaceFinish
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
        face_overlay_type: type | None = None,
    ) -> None:
        self.mesh = mesh
        self.selection = selection if selection is not None else Selection()
        self.overlay = SelectionOverlay(self.selection)
        self._store_type = store_type
        self.render_mesh = RenderMesh(
            mesh, overlay=self.overlay, store_type=store_type
        )
        # AD-021 M1: Render-Einträge der anderen Objekte (Schlüssel -> RenderMesh), ohne Overlay.
        self.object_entries: dict = {}
        # AD-021 M2-0: je Eintrag (alpha, ignores_wireframe).
        self._entry_display: dict = {}
        # AD-021 M2-1: Objekt -> Welt des Edit-Objekts (None = Identität).
        self.model_matrix: list[float] | None = None
        # Optional (None = headless/TraceStore: es entsteht kein GL-Objekt).
        self.point_overlay = (
            point_overlay_type() if point_overlay_type is not None else None
        )
        self.point_positions: dict[str, list[tuple[float, float, float]]] = {}
        # Punkte, Edge- und Face-Highlight teilen sich die Dirty-Auslöser
        # (Selektion/Hover, Vertex-Move, Topologie).
        self._selection_overlays_dirty = True
        self.line_layers: dict[str, list] = {}
        self.face_overlay = (
            face_overlay_type() if face_overlay_type is not None else None
        )
        self.face_layers: dict[str, list] = {}
        self._edge_highlight = False
        self.line_overlay = (
            line_overlay_type() if line_overlay_type is not None else None
        )
        self.edge_segments: list = []
        self._edges_dirty = True
        self.tool_point_layers: dict[str, list] = {layer: [] for layer in TOOL_LAYERS}
        self.tool_line_layers: dict[str, list] = {layer: [] for layer in TOOL_LAYERS}
        # H1: Zusatz-Overlays eines Hosts; frisch angehängte syncen beim
        # nächsten `sync()` in jedem Fall.
        self.extra_overlays: list = []
        #: Counts the vertex-move / topology notifications (and edit-mesh switches): a host that caches
        #: something derived from the vertex positions (the gizmo pivot) re-derives when it changes.
        self.geometry_revision = 0
        self._extra_overlays_dirty = False
        # H7: Ersatzfläche eines Hosts und ihr RenderMesh (None = das Edit-Mesh wird gezeichnet).
        self.surface_provider = None
        self.surface_render_mesh: RenderMesh | None = None
        # H7-E: Ersatzflächen für Objekt-Einträge (Schlüssel wie `object_entries`).
        self.entry_surface_render_meshes: dict = {}
        # Startzustand = DisplayState-Default (Shaded, kein Overlay).
        self.show_faces = True
        self.show_edges = False
        self.flat = False
        # Worklight (light_rig): pro Frame in `render()` aufgelöst und an alle Stores gegeben.
        self.light_rig: LightRig = PRESETS[DEFAULT_PRESET]
        # Glanz (material.py): Teil jedes Materials, das der Viewport bindet.
        self.surface_finish: SurfaceFinish = DEFAULT_FINISH

    # -- Display (WP-06 B5a, E36) ----------------------------------------------

    def set_display(self, show_faces: bool, show_edges: bool, flat: bool) -> None:
        """Setzt, was gezeichnet wird. Kein Rebuild der Base-Geometrie; die
        Edge-Segmente folgen beim nächsten `sync()`, falls sie veraltet sind."""
        self.show_faces = bool(show_faces)
        self.show_edges = bool(show_edges)
        self.flat = bool(flat)
        self._apply_draw_style()

    def set_light(self, rig: LightRig) -> None:
        """Setzt das Worklight (`light_rig.LightRig`). Reiner Draw-Zustand: keine Ressource,
        kein Upload; im Bezugsraum Kamera folgt es der Kamera bei jedem `render()`."""
        self.light_rig = rig

    def set_surface_finish(self, finish: SurfaceFinish) -> bool:
        """Glanz aller Flächen (`material.SurfaceFinish`): ein Material-Update je RenderMesh
        (`material_updates`), keine Geometrie. True = geändert."""
        if finish == self.surface_finish:
            return False
        self.surface_finish = finish
        current = self.render_mesh.material
        color = current.color if current is not None else DEFAULT_BASE_COLOR
        self.bind_material(Material(color, finish))
        for entry in self.object_entries.values():
            if entry.material is not None:
                entry.bind_material(Material(entry.material.color, finish))
                entry.mark_material_dirty()
        # Ersatzflächen der Einträge übernehmen das neue Material in `_follow_entry`.
        return True

    def light_uniforms(self) -> dict:
        """Die Licht-Uniforms für die gebundene Kamera (headless beobachtbar). Eine Kamera ohne
        `basis()` kann kein Kamera-Licht tragen; dann steht das Licht in der Welt."""
        rig = self.light_rig
        camera = self.render_mesh.camera
        if getattr(camera, "basis", None) is None:
            rig = rig.with_(space=SPACE_WORLD)
        return resolve(rig, camera)

    # -- Objekt-Einträge (AD-021 M1) -------------------------------------------

    def set_object_entry(
        self,
        key,
        mesh: Mesh,
        base_color: tuple[float, float, float] | None = None,
        *,
        model_matrix: list[float] | None = None,
        alpha: float = 1.0,
        ignores_wireframe: bool = False,
    ) -> bool:
        """Legt den Eintrag `key` für `mesh` an oder aktualisiert Farbe, Matrix und Anzeige. Ein
        anderes Mesh unter demselben Schlüssel ersetzt den Eintrag. True = etwas hat sich
        geändert. Nie mit `SelectionOverlay` (Modul-Docstring)."""
        color = tuple(base_color) if base_color is not None else DEFAULT_BASE_COLOR
        display = (float(alpha), bool(ignores_wireframe))
        entry = self.object_entries.get(key)
        if entry is not None and entry.mesh is not mesh:
            self.remove_object_entry(key)
            entry = None
        changed = False
        if entry is None:
            entry = RenderMesh(mesh, overlay=None, store_type=self._store_type)
            camera = self.render_mesh.camera
            if camera is not None:
                entry.bind_camera(camera)
                entry.mark_camera_dirty(aspect=self.render_mesh.aspect)
            self.object_entries[key] = entry
            changed = True
        if self._entry_display.get(key) != display:
            self._entry_display[key] = display
            self._apply_entry_style(key, entry)
            changed = True
        if entry.model_matrix != (list(model_matrix) if model_matrix is not None else None):
            entry.set_model_matrix(model_matrix)
            changed = True
        if entry.material is None or entry.material.color != color:
            entry.bind_material(Material(color, self.surface_finish))
            entry.mark_material_dirty()
            changed = True
        return changed

    def remove_object_entry(self, key) -> bool:
        """Entfernt den Eintrag `key` und gibt seine GPU-Objekte frei. True = es gab ihn."""
        entry = self.object_entries.pop(key, None)
        self._entry_display.pop(key, None)
        self._release_entry_surface(key)
        if entry is None:
            return False
        release = getattr(entry.store, "release", None)
        if release is not None:
            release()
        return True

    def _apply_entry_style(self, key, entry: RenderMesh) -> None:
        set_draw_style = getattr(entry.store, "set_draw_style", None)
        if set_draw_style is not None:
            alpha, _ = self._entry_display.get(key, (1.0, False))
            # Auf Objekt-Einträgen liegen keine Linien: kein Polygon-Offset.
            set_draw_style(flat=self.flat, polygon_offset=False, alpha=alpha)
        rm = self.entry_surface_render_meshes.get(key)
        set_draw_style = getattr(rm.store, "set_draw_style", None) if rm is not None else None
        if set_draw_style is not None:
            alpha, _ = self._entry_display.get(key, (1.0, False))
            set_draw_style(flat=self.flat, polygon_offset=False, alpha=alpha)

    def entry_drawn(self, key) -> bool:
        """Wird der Eintrag im aktuellen Display-Modus gezeichnet (AD-021 M2-0, RD-3)?"""
        _, ignores_wireframe = self._entry_display.get(key, (1.0, False))
        return self.show_faces or ignores_wireframe

    def _entry_draw_order(self) -> list:
        """Opake Einträge zuerst, Ghosts danach (RD-1); innerhalb in Anhänge-Reihenfolge."""
        drawn = [key for key in self.object_entries if self.entry_drawn(key)]
        opaque = [k for k in drawn if self._entry_display.get(k, (1.0, False))[0] >= 1.0]
        ghosts = [k for k in drawn if self._entry_display.get(k, (1.0, False))[0] < 1.0]
        return opaque + ghosts

    # -- Platzierung des Edit-Objekts (AD-021 M2-1) ------------------------------

    def set_edit_mesh(self, mesh: Mesh, model_matrix: list[float] | None = None) -> None:
        """Ein anderes Mesh wird das bearbeitete (AD-021 M2-4, E-14): der Eintrag mit
        `SelectionOverlay` und allen Overlays wird für `mesh` neu aufgebaut (ein Rebuild - die
        alte GPU-Geometrie wird freigegeben), Kamera, Aspect, Material und Anzeige gehen mit;
        Auswahl-, Kanten- und Zusatz-Overlays lesen beim nächsten `sync()` `self.mesh`, die Tool-
        Layer werden geleert. Das bisherige Mesh zeichnet der Aufrufer, wenn er will, als
        Objekt-Eintrag (`set_object_entry`) - der Viewport weiß nichts von Objekten."""
        old = self.render_mesh
        release = getattr(old.store, "release", None)
        if release is not None:
            release()
        self.mesh = mesh
        self.geometry_revision += 1
        self.render_mesh = RenderMesh(mesh, overlay=self.overlay, store_type=self._store_type)
        if old.material is not None:
            self.render_mesh.bind_material(old.material)
            self.render_mesh.mark_material_dirty()
        if old.camera is not None:
            self.render_mesh.bind_camera(old.camera)
            self.render_mesh.mark_camera_dirty(aspect=old.aspect)
        self.model_matrix = None
        self.set_model_matrix(model_matrix)
        self._edge_highlight = False
        self._apply_draw_style()
        self.set_tool_overlay()
        self._selection_overlays_dirty = True
        self._edges_dirty = True
        self._extra_overlays_dirty = True

    def set_model_matrix(self, matrix: list[float] | None) -> None:
        """Objekt -> Welt des Edit-Objekts (None = Identität): Mesh-Uniform und `view·model`
        für alle Overlays (Modul-Docstring)."""
        self.model_matrix = list(matrix) if matrix is not None else None
        self.render_mesh.set_model_matrix(self.model_matrix)
        if self.surface_render_mesh is not None:
            self.surface_render_mesh.set_model_matrix(self.model_matrix)

    def overlay_camera_uniforms(self) -> list[float]:
        """Die Kamera-Uniforms der Overlays des Edit-Objekts: `view·model` + `proj`."""
        uniforms = self.render_mesh._camera_uniforms()
        if self.model_matrix is None:
            return uniforms
        return _mat4_mul(uniforms[:16], self.model_matrix) + list(uniforms[16:])

    # -- Zusatz-Overlays (WP-SYM-LAB-03 H1) ------------------------------------

    def add_overlay(self, overlay) -> None:
        """Hängt ein Host-Overlay an (Vertrag: Modul-Docstring). Gezeichnet
        wird in Anhänge-Reihenfolge."""
        self.extra_overlays.append(overlay)
        self._extra_overlays_dirty = True

    # -- Ersatzfläche (AD-013 H7) ---------------------------------------------

    def set_surface_provider(self, provider) -> None:
        """Setzt den Provider der Ersatzfläche (Vertrag: Modul-Docstring) oder entfernt ihn
        (None, gibt den RenderMesh frei). Er synct beim nächsten `sync()` in jedem Fall."""
        self.surface_provider = provider
        self._extra_overlays_dirty = True
        if provider is None:
            self._release_surface()

    def _release_surface(self) -> None:
        rm = self.surface_render_mesh
        self.surface_render_mesh = None
        if rm is not None:
            release = getattr(rm.store, "release", None)
            if release is not None:
                release()

    def _release_entry_surface(self, key) -> None:
        rm = self.entry_surface_render_meshes.pop(key, None)
        if rm is not None:
            release = getattr(rm.store, "release", None)
            if release is not None:
                release()

    def _sync_entry_surfaces(self, *, apply_moved: bool = True) -> None:
        """H7-E: legt die Ersatzflächen der Objekt-Einträge an, baut sie bei einem anderen Mesh neu
        auf und gibt sie frei, wo der Provider keine mehr nennt."""
        provider = self.surface_provider
        wanted = getattr(provider, "entry_surfaces", None) or {}
        moved = getattr(provider, "entry_moved", None) or {}
        for key in list(self.entry_surface_render_meshes):
            if key not in wanted or key not in self.object_entries:
                self._release_entry_surface(key)
        for key, mesh in wanted.items():
            entry = self.object_entries.get(key)
            if entry is None or mesh is None:
                continue
            rm = self.entry_surface_render_meshes.get(key)
            if rm is None or rm.mesh is not mesh:
                self._release_entry_surface(key)
                rm = RenderMesh(mesh, overlay=None, store_type=self._store_type)
                self.entry_surface_render_meshes[key] = rm
                self._follow_entry(key, entry, rm, rebuilt=True)
            elif apply_moved and moved.get(key):
                rm.mark_vertices_dirty(set(moved[key]))

    def _follow_entry(self, key, entry: RenderMesh, rm: RenderMesh, *, rebuilt: bool = False) -> None:
        """Hält die Ersatzfläche eines Eintrags mit dessen Kamera, Material, Matrix und Stil gleich."""
        if rebuilt or rm.camera is not entry.camera:
            if entry.camera is not None:
                rm.bind_camera(entry.camera)
            rm.mark_camera_dirty(aspect=entry.aspect)
        if entry.material is not None and rm.material is not entry.material:
            rm.bind_material(entry.material)
            rm.mark_material_dirty()
        if rm.model_matrix != entry.model_matrix:
            rm.set_model_matrix(entry.model_matrix)
        if rebuilt:
            self._apply_entry_style(key, entry)

    def _sync_surface(self) -> None:
        moved = self.surface_provider.sync(self.mesh, self.selection)
        self._sync_entry_surfaces()
        mesh = self.surface_provider.surface_mesh
        rm = self.surface_render_mesh
        if mesh is None:
            self._release_surface()
            return
        if rm is None or rm.mesh is not mesh:
            self._release_surface()
            rm = RenderMesh(mesh, overlay=None, store_type=self._store_type)
            self.surface_render_mesh = rm
            if self.render_mesh.camera is not None:
                rm.bind_camera(self.render_mesh.camera)
            rm.mark_camera_dirty(aspect=self.render_mesh.aspect)
            if self.render_mesh.material is not None:
                rm.bind_material(self.render_mesh.material)
                rm.mark_material_dirty()
            rm.set_model_matrix(self.model_matrix)
            self._apply_draw_style()
        elif getattr(self.surface_provider, "surface_topology_changed", False):
            # H7 (2026-10-23): dasselbe Mesh-Objekt, Topologie in place gepatcht - der RenderMesh
            # gleicht sie über sein Journal inkrementell ab (AD-023), statt neu aufzubauen.
            rm.mark_topology_dirty()
        elif moved:
            rm.mark_vertices_dirty(set(moved))
        rm.sync()

    # -- Tool-Layer (WP-06 B7) -------------------------------------------------

    def set_tool_overlay(self, points=None, segments=None) -> None:
        """Ersetzt die Tool-Layer (`TOOL_LAYERS`): `points`/`segments` sind
        `{layer: [...]}`; fehlende Layer bzw. `None` = leer. Reiner
        Overlay-Zustand - keine Base-Geometrie, kein Selection-Bezug."""
        points = points or {}
        segments = segments or {}
        for layer in TOOL_LAYERS:
            self.tool_point_layers[layer] = [tuple(p) for p in points.get(layer, ())]
            self.tool_line_layers[layer] = [tuple(s) for s in segments.get(layer, ())]
            if self.point_overlay is not None:
                self.point_overlay.set_points(layer, self.tool_point_layers[layer])
            if self.line_overlay is not None:
                self.line_overlay.set_segments(self.tool_line_layers[layer], layer=layer)
        self._update_edge_highlight()

    def _update_edge_highlight(self) -> None:
        # Pfad-Edges liegen wie das Edge-Highlight auf den Faces (Polygon-
        # Offset nötig); die Preview-Linie zeichnet ohne Depth-Test.
        edge_highlight = any(self.line_layers.values()) or any(
            self.tool_line_layers[layer] for layer in _TOOL_DEPTH_TESTED_LINES
        )
        if edge_highlight != self._edge_highlight:
            self._edge_highlight = edge_highlight
            self._apply_draw_style()

    def _apply_draw_style(self) -> None:
        # Polygon-Offset, sobald Linien auf den Faces liegen: Wire (E40) oder
        # ein Edge-Highlight (B5b) - ohne Offset z-fightet die 1-px-Linie mit
        # der Fläche und erscheint nur gestrichelt.
        set_draw_style = getattr(self.render_mesh.store, "set_draw_style", None)
        if set_draw_style is not None:
            set_draw_style(
                flat=self.flat,
                polygon_offset=self.show_faces
                and (self.show_edges or self._edge_highlight),
            )
        if self.surface_render_mesh is not None:
            set_draw_style = getattr(self.surface_render_mesh.store, "set_draw_style", None)
            if set_draw_style is not None:
                # Der Käfig-Wire liegt meist außerhalb dieser Fläche; wo er sie berührt (Ränder,
                # flache Stellen), hält derselbe Offset wie beim Edit-Mesh die Linien vorn.
                set_draw_style(
                    flat=self.flat,
                    polygon_offset=self.show_faces
                    and (self.show_edges or self._edge_highlight),
                )
        for key, entry in self.object_entries.items():
            self._apply_entry_style(key, entry)

    # -- Kamera-Bindung (duck-typed, siehe Paket-Docstring) ------------------

    def bind_camera(self, camera) -> None:
        self.render_mesh.bind_camera(camera)
        # Initiale Kamera-Uniforms sofort bereitstellen (nicht erst nach
        # dem ersten on_camera_changed()).
        self.render_mesh.mark_camera_dirty()
        for entry in self.object_entries.values():
            entry.bind_camera(camera)
            entry.mark_camera_dirty()
        for rm in self.entry_surface_render_meshes.values():
            rm.bind_camera(camera)
            rm.mark_camera_dirty()
        if self.surface_render_mesh is not None:
            self.surface_render_mesh.bind_camera(camera)
            self.surface_render_mesh.mark_camera_dirty()

    def bind_material(self, material) -> None:
        self.render_mesh.bind_material(material)
        self.render_mesh.mark_material_dirty()
        if self.surface_render_mesh is not None:
            self.surface_render_mesh.bind_material(material)
            self.surface_render_mesh.mark_material_dirty()

    def set_edit_base_color(self, base_color: tuple[float, float, float] | None) -> bool:
        """Grundfarbe des Edit-Mesh (und einer H7-Ersatzfläche); None = Standardfarbe. Für die
        sichtbare Objekt-Auswahl in Modus `4` (2026-10-16). Kein Rebuild; True = geändert."""
        color = tuple(base_color) if base_color is not None else DEFAULT_BASE_COLOR
        current = self.render_mesh.material
        if current is not None and tuple(current.color) == color:
            return False
        if current is None and color == DEFAULT_BASE_COLOR and self.surface_finish == DEFAULT_FINISH:
            return False
        self.bind_material(Material(color, self.surface_finish))
        return True

    # -- Notifikations-API (aufgerufen von src.mirai nach Core-Mutationen) --

    def on_vertices_moved(self, vertex_ids: set[VertexId]) -> None:
        self.render_mesh.mark_vertices_dirty(vertex_ids)
        if vertex_ids:
            self.geometry_revision += 1
            self._selection_overlays_dirty = True
            self._edges_dirty = True

    def on_topology_changed(self) -> None:
        self.geometry_revision += 1
        self.render_mesh.mark_topology_dirty()
        self._selection_overlays_dirty = True
        self._edges_dirty = True

    def on_selection_changed(self) -> None:
        self.render_mesh.mark_selection_dirty()
        self._selection_overlays_dirty = True

    def on_material_changed(self) -> None:
        self.render_mesh.mark_material_dirty()
        if self.surface_render_mesh is not None:
            self.surface_render_mesh.mark_material_dirty()

    def on_camera_changed(self, aspect: float | None = None) -> None:
        self.render_mesh.mark_camera_dirty(aspect=aspect)
        for entry in self.object_entries.values():
            entry.mark_camera_dirty(aspect=aspect)
        for rm in self.entry_surface_render_meshes.values():
            rm.mark_camera_dirty(aspect=aspect)
        if self.surface_render_mesh is not None:
            self.surface_render_mesh.mark_camera_dirty(aspect=aspect)

    # -- Frame-Lifecycle -----------------------------------------------------

    def sync(self) -> None:
        """Verarbeitet alle seit dem letzten `sync()` markierten Änderungen.
        Muss vor `render()` aufgerufen werden (typischerweise 1x pro Frame)."""
        self.render_mesh.sync()
        for entry in self.object_entries.values():
            entry.sync()
        # Selektion/Hover, Vertex-Move und Topologie setzen alle dieses Flag.
        changed = self._selection_overlays_dirty or self._extra_overlays_dirty
        if self._selection_overlays_dirty:
            self._sync_selection_overlays()
        provider = self.surface_provider
        if provider is not None and (changed or getattr(provider, "dirty", False)):
            self._sync_surface()
        elif self.surface_render_mesh is not None:
            # Kamera/Aspect (kein Provider-Auslöser) kommen wie bei den Objekt-Einträgen jeden Frame an.
            self.surface_render_mesh.sync()
        if provider is not None and getattr(provider, "entry_surfaces", None):
            # Ein Eintrag, der erst nach dem Provider-Sync entstand, bekommt seine Fläche ohne Auslöser.
            self._sync_entry_surfaces(apply_moved=False)
        for key, rm in self.entry_surface_render_meshes.items():
            self._follow_entry(key, self.object_entries[key], rm)
            rm.sync()
        if self.show_edges and self._edges_dirty:
            self._sync_edges()
        for overlay in self.extra_overlays:
            if changed or getattr(overlay, "dirty", False):
                overlay.sync(self.mesh, self.selection)
        self._extra_overlays_dirty = False

    def _sync_selection_overlays(self) -> None:
        self.point_positions = self.overlay.point_layers(self.mesh)
        if self.point_overlay is not None:
            for layer, positions in self.point_positions.items():
                self.point_overlay.set_points(layer, positions)
        self.line_layers = self.overlay.line_layers(self.mesh)
        if self.line_overlay is not None:
            for layer, segments in self.line_layers.items():
                self.line_overlay.set_segments(segments, layer=layer)
        self._update_edge_highlight()
        self.face_layers = self.overlay.face_layers(self.mesh)
        if self.face_overlay is not None:
            for layer, triangles in self.face_layers.items():
                self.face_overlay.set_triangles(layer, triangles)
        self._selection_overlays_dirty = False

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
        light = self.light_uniforms()
        surface = self.surface_render_mesh
        drawn = self.render_mesh if surface is None else surface
        for render_mesh in (drawn, *self.object_entries.values(), *self.entry_surface_render_meshes.values()):
            set_light_uniforms = getattr(render_mesh.store, "set_light_uniforms", None)
            if set_light_uniforms is not None:
                set_light_uniforms(light)
        # Reihenfolge (E40, E45, B7, H1): Mesh, Wire, Face-Highlight,
        # Edge-Highlight, Tool-Linien, Zusatz-Overlays, Punkte.
        if self.show_faces:
            drawn.render(self.render_mesh.camera)
        for key in self._entry_draw_order():
            # H7-E: die Ersatzfläche des Eintrags, wenn der Provider eine nennt.
            self.entry_surface_render_meshes.get(key, self.object_entries[key]).render(self.render_mesh.camera)
        if (
            self.line_overlay is None
            and self.face_overlay is None
            and self.point_overlay is None
            and not self.extra_overlays
        ):
            return None
        # Dieselbe Matrix-Quelle wie die `camera_uniforms` des Mesh
        # (gebundene Kamera + synchronisierter Aspect) - kein zweiter
        # Kamera-Matrix-Pfad (WP-06 B2b, E17).
        camera_uniforms = self.overlay_camera_uniforms()
        # Zusatz-Overlays mit `DRAW_UNDER_HIGHLIGHTS` (Soft-Shading, 2026-10-22) liegen unter Wire,
        # Auswahl- und Hover-Markierung, damit diese lesbar oben bleiben.
        for overlay in self.extra_overlays:
            if getattr(overlay, "DRAW_UNDER_HIGHLIGHTS", False):
                overlay.draw(camera_uniforms)
        if self.line_overlay is not None and self.show_edges:
            self.line_overlay.draw(camera_uniforms, layers=(WIRE_LAYER,))
        if self.face_overlay is not None and any(self.face_layers.values()):
            self.face_overlay.draw(camera_uniforms)
        if self.line_overlay is not None and any(self.line_layers.values()):
            self.line_overlay.draw(camera_uniforms, layers=(HOVER_LAYER, SELECTED_LAYER))
        if self.line_overlay is not None and any(self.tool_line_layers.values()):
            self.line_overlay.draw(camera_uniforms, layers=_TOOL_LINE_DRAW_ORDER)
        for overlay in self.extra_overlays:
            if not getattr(overlay, "DRAW_UNDER_HIGHLIGHTS", False):
                overlay.draw(camera_uniforms)
        if self.point_overlay is not None:
            self.point_overlay.draw(camera_uniforms)

    # -- GPU-Picking (AD-022 B2-out) --------------------------------------------

    def gpu_pick_mesh(self):
        """Der `RenderMesh` der Edit-Mesh, synchronisiert, wenn seine Buffer für ein GPU-Picking taugen
        (GL-Store, VertexList, Kamera) - sonst None (headless: CPU-Picker). Synchronisiert vorher alles
        Ausstehende, damit ein Pick direkt nach einer Operation oder einem Undo nie die Buffer des
        vorigen Mesh-Zustands liest (AD-022 §5, Hover-Reihenfolge)."""
        from .gpu_picker import GpuPicker

        rm = self.render_mesh
        dirty = rm.dirty
        if dirty.topology or dirty.geometry or dirty.camera or rm._model_dirty:
            rm.sync()
        return rm if GpuPicker.can_pick(rm) else None

    @property
    def gpu_picker(self):
        picker = getattr(self, "_gpu_picker", None)
        if picker is None:
            from .gpu_picker import GpuPicker

            picker = self._gpu_picker = GpuPicker()
        return picker

    # -- Zugriff für Tests/Diagnose -------------------------------------------

    @property
    def benchmark_counters(self) -> dict:
        return self.render_mesh.benchmark_counters

    def resource_ids(self) -> dict[str, int]:
        return self.render_mesh.resource_ids()
