"""Core → Production-Viewport Adapter (seit WP-IL-01, 2026-09-08).

Der Adapter bindet ein `src.core.Mesh` plus eine Core-`Selection` an den
Production-Viewport (`src.viewport.Viewport` → RenderMesh / ResourceStore /
SelectionOverlay, Gate 5/7) — und ersetzt damit die frühere V0.2-Experiment-
Verkabelung (V02Mesh + V0.2-RenderMesh), die als Duplikat der inzwischen
produktiven `src/viewport`-Architektur entfernt wurde (Audit §C).

Grundsätze (unverändert gegenüber dem ursprünglichen Lab):

- Core Mesh = Wahrheit; die Render-Darstellung ist abgeleitet.
- Triangulierung passiert an der Render-Grenze, niemals im Core oder im
  OBJ-Loader. Maßgeblich ist hier die Production-Ableitung
  (`viewport.derived.triangulate_face`, Fan — identisch zu
  `RenderMesh._rebuild_index_mapping`); das Lab-Experiment
  `adapters.triangulate` (Ear-Clipping, Superset für konkave N-gons) bleibt
  bewusst außerhalb dieses Pfads erhalten.
- Mutationen laufen IMMER zuerst gegen `src.core.Mesh`, danach folgt die
  Production-Notifikation (`on_vertices_moved` / `on_selection_changed` /
  `on_topology_changed` / `on_camera_changed`) und `sync()`.

Kamera-Pfad — kanonische WP-IL-01-Entscheidung:

    camera.orbit()/pan()/dolly()          [eine einzige Kamera-Instanz]
      → Viewport.on_camera_changed()      [Notifikation]
      → RenderMesh.mark_camera_dirty()    [Dirty-State]
      → sync() → camera_uniforms          [Ressource, Instrumentierung]

Der Draw-Feed des Harness (integration/lab_viewport.py) liest die Matrizen
direkt von derselben Kamera-Instanz (`build_view_matrix` /
`build_projection_matrix`). Beide Pfade lesen DENSELBEN Kamera-Zustand —
eine Zustands-Spaltung (historischer Dual-Path-Befund) ist damit
ausgeschlossen. Ein Rücklesen aus dem Store ist bewusst nicht implementiert:
`PygletStore` legt Uniforms als `position`-Attribut ab, und Multi-Attribut-
Rendering ist Production-seitig ein dokumentierter Non-Goal (künftiges
Entry-Point-Gate).
"""

from __future__ import annotations

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from core.ids import VertexId  # noqa: E402  (Production-Importpfad, wie src/mirai)
from core.mesh import Mesh, Position  # noqa: E402
from core.selection import Selection  # noqa: E402

from viewport import Viewport  # noqa: E402  (Production-Fassade, Gate 5/7)
from viewport.derived import triangulate_face  # noqa: E402
from viewport.resource_store import PygletStore, TraceStore  # noqa: E402,F401


class LabMaterialState:
    """Material-Harness-State (duck-typed `uniform_packet()` für RenderMesh).

    Entspricht der V0.2-Materialkategorie (8 floats: base_rgba +
    highlight_rgba). Production definiert bewusst keine konkrete Material-
    Klasse — dieser Lab-State füllt die Lücke ausschließlich für den Harness
    (Material-Uniform-Ressource + Counter), gezeichnet wird er nicht.
    """

    def __init__(self) -> None:
        self.base_color = (0.6, 0.7, 0.9, 1.0)
        self.highlight_color = (1.0, 0.4, 0.2, 1.0)

    def set_base_color(self, rgba) -> None:
        self.base_color = tuple(float(c) for c in rgba)

    def set_highlight_color(self, rgba) -> None:
        self.highlight_color = tuple(float(c) for c in rgba)

    def uniform_packet(self) -> list[float]:
        """Flaches 8-float-Paket (base_rgba + highlight_rgba)."""
        return list(self.base_color) + list(self.highlight_color)


class LabPygletStore(PygletStore):
    """Production-`PygletStore` mit vec3-ausgerichteter Allokation (Harness).

    Production `allocate()` legt Ressourcen als VertexList-Attribute über den
    pyglet-Default-Shader an (`position` = vec3) und rechnet
    `count = nbytes // 12`. Ressourcen, deren Float-Anzahl nicht durch 3
    teilbar ist (camera_uniforms = 32, material_uniforms = 8,
    highlight_flags = n_verts), würden abgeschnitten bzw. beim `update()`
    über die Kapazität hinaus schreiben — der Default-Shader kennt nur
    vec3/vec4-Attribute, und Multi-Attribut-Shader sind Production-seitig
    dokumentierter Non-Goal (künftiges Entry-Point-Gate).

    Diese Lab-Unterklasse rundet die Allokationsgröße auf Vielfache von 12
    Bytes auf (ceil), sodass jede Ressource vollständig in das vec3-Raster
    passt und in-place patchbar bleibt. Identitäten und Zähler
    (`resource_id`, `gpu_resource_creations`, `bytes_uploaded`) bleiben exakt
    die Production-Buchhaltung — `update()` wird unverändert geerbt.
    Reine Harness-Maßnahme, keine Production-Änderung.

    Live-Befund (WP-IL-01, echtes GL): `register_attribute_spec(name,
    "position", 1)` ist mit dem Default-Shader nicht verwendbar — pyglet
    erwartet für `position` stets `count * 3` floats (ValueError „Invalid
    data size"). Der Mechanismus ist erst mit einem eigenen 1-Komponenten-
    Shader sinnvoll nutzbar (dokumentiert für Gate 11).
    """

    def allocate(self, name: str, nbytes: int) -> None:
        aligned = -(-nbytes // 12) * 12  # ceil auf Vielfache von 12 (vec3)
        super().allocate(name, aligned)


class CoreVertexIndexMap:
    """Bidirektionales Mapping zwischen Core-`VertexId` und Render-Index.

    Konstruiert in `all_vertex_ids()`-Reihenfolge — exakt die Reihenfolge,
    die auch `RenderMesh._vertex_index` verwendet (Verträglichkeit wird in
    `tests/test_production_rebase.py` gegen `RenderMesh.vertex_index_of`
    geprüft). IDs der Core-Seite sind bewusst opak (AD-001).
    """

    def __init__(self, vertex_ids: list[VertexId]) -> None:
        self._vertex_ids: list[VertexId] = list(vertex_ids)
        self._to_index = {int(vid): i for i, vid in enumerate(self._vertex_ids)}
        self._to_vertex = {i: int(vid) for i, vid in enumerate(self._vertex_ids)}

    # -- Core-Seite ----------------------------------------------------------
    @property
    def vertex_ids(self) -> list[VertexId]:
        return list(self._vertex_ids)

    def index(self, vid: VertexId) -> int:
        return self._to_index[int(vid)]

    def vertex(self, index: int) -> VertexId:
        return self._vertex_ids[index]

    def __len__(self) -> int:
        return len(self._vertex_ids)


class CoreRenderBinding:
    """Dünne Fassade: `src.core.Mesh` + Core-`Selection` → `src.viewport.Viewport`.

    Übernimmt die frühere V0.2-Binding-Rolle, aber vollständig über die
    Production-Notifikations-API (`Viewport.on_*` + `sync()`), ohne eigene
    Render-Mesh-Kopie und ohne doppelte Selection-Buchhaltung.
    """

    def __init__(
        self,
        core_mesh: Mesh,
        store_type=TraceStore,
        camera=None,
        selection: Selection | None = None,
    ) -> None:
        self.core_mesh = core_mesh
        self.selection = selection if selection is not None else Selection()
        self.material = LabMaterialState()
        self.viewport = Viewport(
            core_mesh, selection=self.selection, store_type=store_type
        )
        self.render = self.viewport.render_mesh  # Production-RenderMesh
        self.index_map = CoreVertexIndexMap(core_mesh.all_vertex_ids())
        self.render.aspect = 1.0
        self.camera = None
        self.bind_material_state(self.material)
        if camera is not None:
            self.bind_camera(camera)

    # -- Verdrahtung ----------------------------------------------------------

    def bind_camera(self, camera) -> None:
        """Bindet DIE eine Kamera-Instanz (duck-typed) und legt initial
        `camera_uniforms` an (Viewport.bind_camera markiert camera dirty)."""
        self.camera = camera
        self.viewport.bind_camera(camera)
        self.viewport.sync()

    def bind_material_state(self, material) -> None:
        """Bindet einen duck-typed Material-State (uniform_packet()).

        Production-Grenze (für Gate 11 dokumentiert): `RenderMesh.
        _sync_material` nimmt die existierende Ressource an, ohne
        allocate-Fallback — mit `PygletStore` würde ein spätes Binding
        (nach dem Konstruktions-Build) beim `update()` einen KeyError
        werfen. Der Lab-Store allokiert daher defensiv vor (reine
        Harness-Maßnahme, keine Production-Änderung).
        """
        self.material = material
        self.viewport.bind_material(material)
        if not self.render.store.has("material_uniforms"):
            nbytes = len(material.uniform_packet()) * 4
            self.render.store.allocate("material_uniforms", nbytes)
        self.viewport.sync()

    # -- Kanonischer Kamera-Pfad (nur Uniforms) --------------------------------

    def apply_camera(self, aspect: float | None = None) -> None:
        """Kamera-Änderung dem Production-Pfad melden (nur camera_uniforms)."""
        if aspect is not None:
            self.render.aspect = aspect
        self.viewport.on_camera_changed(aspect=aspect)
        self.viewport.sync()

    # -- Geometry: Core zuerst, dann Production-Notifikation -------------------

    def move_vertex(self, vid: VertexId, new_position: Position) -> None:
        """Verschiebt einen Vertex: erst `src.core`, dann Render-Sync.

        Reihenfolge ist vertraglich:
        1. `core_mesh.set_vertex_position(vid, new_position)` — Domain-Wahrheit
        2. `viewport.on_vertices_moved({vid})` — Production-Geometry-Kanal
        3. `viewport.sync()` — Nur Positions-/Normalen-Partial-Updates
        """
        self.core_mesh.set_vertex_position(vid, new_position)
        self.viewport.on_vertices_moved({vid})
        self.viewport.sync()

    def move_vertex_by(self, vid: VertexId, delta: Position) -> None:
        current = self.core_mesh.vertex_position(vid)
        self.move_vertex(
            vid,
            (current[0] + delta[0], current[1] + delta[1], current[2] + delta[2]),
        )

    # -- Selection (eine Buchhaltung: Core) ------------------------------------

    def apply_selection(self) -> None:
        """Selection-Änderung dem Production-Pfad melden (nur Overlay)."""
        self.viewport.on_selection_changed()
        self.viewport.sync()

    def select_vertex(self, vid: VertexId) -> None:
        self.selection.set({vid})
        self.apply_selection()

    def clear_selection(self) -> None:
        self.selection.clear()
        self.apply_selection()

    # -- Material --------------------------------------------------------------

    def apply_material(self) -> None:
        self.viewport.on_material_changed()
        self.viewport.sync()

    # -- Topology (struktureller Rebuild, Production-Kanal) --------------------

    def rebuild_from_core(self) -> None:
        """Baut die Render-Darstellung aus dem aktuellen Core-Mesh neu
        (struktureller Rebuild über `on_topology_changed`)."""
        self.viewport.on_topology_changed()
        self.viewport.sync()
        self.index_map = CoreVertexIndexMap(self.core_mesh.all_vertex_ids())

    # -- Lese-API für Draw-Harness / HUD / Tests --------------------------------

    @property
    def positions(self) -> list[Position]:
        """Positionen in Flat-Index-Reihenfolge (live aus der Core-Mesh)."""
        return [self.core_mesh.vertex_position(v) for v in self.index_map.vertex_ids]

    @property
    def triangle_indices(self) -> list[tuple[int, int, int]]:
        """Dreiecke als Flat-Index-Tripel (Production-Fan-Ableitung)."""
        triangles: list[tuple[int, int, int]] = []
        for fid in self.core_mesh.all_face_ids():
            boundary = self.core_mesh.face_vertices(fid)
            for a, b, c in triangulate_face(boundary):
                triangles.append(
                    (
                        self.index_map.index(a),
                        self.index_map.index(b),
                        self.index_map.index(c),
                    )
                )
        return triangles

    @property
    def vertex_count(self) -> int:
        return len(self.index_map)

    @property
    def triangle_count(self) -> int:
        return len(self.triangle_indices)


def flatten_render_mesh(binding: CoreRenderBinding) -> dict:
    """Flache Buffer für den pyglet-/GPU-Aufbau (Draw-Harness des Lab).

    Liest ausschließlich Production-Daten: Positionen aus der Core-Mesh
    (Flat-Index-Reihenfolge), Normalen aus `RenderMesh.derived`,
    Dreiecke über die Production-Fan-Triangulierung (identische Ableitung
    wie `RenderMesh._rebuild_index_mapping`).
    """

    def _flatten(values, width: int) -> list[float]:
        out: list[float] = []
        for v in values:
            out.extend(v)
        return out

    normals = [
        binding.render.derived.vertex_normals[v]
        for v in binding.index_map.vertex_ids
    ]
    return {
        "n": binding.vertex_count,
        "positions": _flatten(binding.positions, 3),
        "normals": _flatten(normals, 3),
        "indices": [i for tri in binding.triangle_indices for i in tri],
    }


def render_triangle_count(core_mesh: Mesh) -> int:
    """Anzahl der Render-Dreiecke (Fan-Formel n-2), ohne das Mesh zu bauen."""
    total = 0
    for fid in core_mesh.all_face_ids():
        n = len(core_mesh.face_vertices(fid))
        if n >= 3:
            total += n - 2
    return total
