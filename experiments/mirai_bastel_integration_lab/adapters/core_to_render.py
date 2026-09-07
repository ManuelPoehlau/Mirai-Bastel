"""Core → V0.2 Render Adapter — der wichtigste neue Integrationsbaustein.

Der Adapter leitet aus einem `src.core.Mesh` eine Darstellung ab, die der
vorhandene V0.2-Renderer verwenden kann:

    src.core.Mesh (Wahrheit)
        ↓  build_render_mesh()
    V0.2-Render-Mesh (positions + triangles, adjazent)
        ↓  RenderMesh (DirtyState-Kategorien, ResourceStore)
    V0.2-Renderer / Lab-Viewport

Grundsätze:

- Core Mesh = Wahrheit; V0.2 Render Mesh = abgeleitete Darstellung.
- Die Polygon->Triangulierung passiert NUR hier (Render-Darstellung),
  niemals im OBJ Loader oder im Core.
- Der Adapter pflegt ein stabiles Mapping `VertexId <-> Render-Index`
  (Reihenfolge von `Mesh.all_vertex_ids()`, deterministisch).
- Mutationen laufen IMMER zuerst gegen `src.core.Mesh`
  (`set_vertex_position`), erst dann folgt der Render-Sync
  (`RenderMesh.move_vertex` + `sync()`).
"""

from __future__ import annotations

from _paths import ensure_paths  # noqa: E402

ensure_paths()

from src.core.ids import VertexId  # noqa: E402
from src.core.mesh import Mesh, Position  # noqa: E402

from experiments.mirai_bastel_viewport_V02.material import MaterialState  # noqa: E402
from experiments.mirai_bastel_viewport_V02.mesh import Mesh as V02Mesh  # noqa: E402
from experiments.mirai_bastel_viewport_V02.render_mesh import RenderMesh  # noqa: E402
from experiments.mirai_bastel_viewport_V02.renderer import TraceStore  # noqa: E402
from experiments.mirai_bastel_viewport_V02.selection import SelectionState  # noqa: E402

from adapters.triangulate import triangulate_polygon  # noqa: E402


class CoreVertexIndexMap:
    """Bidirektionales Mapping zwischen Core-`VertexId` und Render-Index.

    Der Render-Index IST der Listenindex in `V02Mesh.positions`/`triangles`.
    IDs der Core-Seite sind bewusst opak (AD-001); dieses Mapping ist der
    einzige legitime Ort, der die Konvertierung herstellt.
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

    # -- Render-Seite --------------------------------------------------------
    def render_index_to_core_int(self, index: int) -> int:
        return self._to_vertex[index]

    def __len__(self) -> int:
        return len(self._vertex_ids)


def build_render_mesh(core_mesh: Mesh) -> tuple[V02Mesh, CoreVertexIndexMap]:
    """Leitet aus einem `src.core.Mesh` ein V0.2-Render-Mesh ab.

    - `positions` in der Reihenfolge von `all_vertex_ids()`.
    - Jede Polygon-Face wird trianguliert (n-2 Dreiecke); Quad → 2 Tris.
    - Die V0.2-Adjazenz (`vertex_to_faces`) wird vom V0.2-Mesh selbst
      aufgebaut.
    """
    vertex_ids = core_mesh.all_vertex_ids()
    index_map = CoreVertexIndexMap(vertex_ids)
    positions: list[Position] = [core_mesh.vertex_position(vid) for vid in vertex_ids]

    triangles: list[tuple[int, int, int]] = []
    for fid in core_mesh.all_face_ids():
        boundary = core_mesh.face_vertices(fid)
        render_boundary = [index_map.index(v) for v in boundary]
        triangles.extend(triangulate_polygon(positions, render_boundary))

    return V02Mesh(positions, triangles), index_map


class CoreRenderBinding:
    """Ein Objekt (Core Scene/Mesh) + seine vollständige V0.2-Render-Seite.

    Diese Bindung ist die Stelle, an der Core-Änderungen in Render-Updates
    übersetzt werden — kategoriebewusst über das V0.2-DirtyState-System
    (camera / selection / material / geometry / topology).
    """

    def __init__(self, core_mesh: Mesh, store_type=TraceStore, camera=None) -> None:
        self.core_mesh = core_mesh
        self.render_mesh, self.index_map = build_render_mesh(core_mesh)
        self.render = RenderMesh(self.render_mesh, store_type=store_type)
        self.selection = SelectionState()
        self.material = MaterialState()
        self.material.set_base_color((0.62, 0.68, 0.75, 1.0))
        self.render.bind_selection(self.selection)
        self.render.bind_material(self.material)
        self.render.aspect = 1.0
        if camera is not None:
            self.render.bind_camera(camera)
        self.render.build()

    # -- Struktureller Rebuild (vorbereitet für einen späteren Topology-Test)
    def rebuild_from_core(self) -> None:
        """Baut die Render-Darstellung aus dem aktuellen Core-Mesh neu.

        Struktureller Rebuild (neue Ressourcen-IDs) — exakt das, was ein
        späterer Topology-Schritt braucht. Für den ersten Integrationstest
        bewusst NICHT interaktiv verdrahtet.
        """
        new_mesh, new_map = build_render_mesh(self.core_mesh)
        self.index_map = new_map
        self.render.apply_topology(new_mesh)
        self.render.sync()

    # -- Geometry-Update (Core zuerst!) -------------------------------------
    def move_vertex(self, vid: VertexId, new_position: Position) -> None:
        """Verschiebt einen Vertex: erst `src.core`, dann Render-Sync.

        Reihenfolge ist vertraglich:
        1. `core_mesh.set_vertex_position(vid, new_position)` — Domain-Wahrheit
        2. `render.move_vertex(index, new_position)` — V0.2-Geometry-Kanal
        3. `render.sync()` — Nur Positions-/Normalen-Partial-Updates
        """
        self.core_mesh.set_vertex_position(vid, new_position)
        self.render.move_vertex(self.index_map.index(vid), new_position)
        self.render.sync()

    def move_vertex_by(self, vid: VertexId, delta: Position) -> None:
        current = self.core_mesh.vertex_position(vid)
        self.move_vertex(
            vid,
            (current[0] + delta[0], current[1] + delta[1], current[2] + delta[2]),
        )

    # -- Selection-Update (nur Overlay-Ressource) ----------------------------
    def select_vertex(self, vid: VertexId) -> None:
        self.selection.set({self.index_map.index(vid)})
        self.render.apply_selection()
        self.render.sync()

    def clear_selection(self) -> None:
        self.selection.clear()
        self.render.apply_selection()
        self.render.sync()

    # -- Camera-Update (nur Uniforms) ---------------------------------------
    def apply_camera(self, aspect: float) -> None:
        self.render.apply_camera(aspect=aspect)
        self.render.sync()


def flatten_render_mesh(binding: CoreRenderBinding) -> dict:
    """Flache Buffer für den pyglet-/GPU-Aufbau (kompatibel V0.2-Demonstrator)."""

    def _flatten(values, width: int) -> list[float]:
        out: list[float] = []
        for v in values:
            out.extend(v)
        return out

    return {
        "n": len(binding.render_mesh.positions),
        "positions": _flatten(binding.render_mesh.positions, 3),
        "normals": _flatten(binding.render.derived.vertex_normals, 3),
        "indices": _flatten(binding.render_mesh.triangles, 3),
    }


def render_triangle_count(core_mesh: Mesh) -> int:
    """Anzahl der Render-Dreiecke (Triangulierung), ohne das Mesh zu bauen."""
    total = 0
    for fid in core_mesh.all_face_ids():
        n = len(core_mesh.face_vertices(fid))
        if n >= 3:
            total += n - 2
    return total