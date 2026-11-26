"""The Weight Room's heatmap (AD-041 §5, slice 2): the active bone's share per vertex, as arrays. Headless; the GL sink
is `soft_selection.gl_shading.GLSoftShadingOverlay` (`set_heat`). Names and look `PROVISIONAL`.

**What it holds.** For one (mesh, skin layer, bone): the rows (`ids`, row `i` = vertex `ids[i]`, the mesh's
`all_vertex_ids()` order), the fan triangles of every shown face as row triples (`tris`, the triangulation every
renderer uses, `viewport.derived.triangulate_mesh_face`; hidden faces left out), the share per row and its colour
(`soft_selection.shading.weight_colors`: opaque, grey at 0, blue -> red above). Every face is drawn, also where the
share is 0 - the heatmap shows "nothing" as well as "a little" (W-4).

**Incremental** (§5 "Updates"): a `Mesh.watch()` names the `(layer, vertex)` keys a dab wrote; `refresh()` recomputes
the share and colour of those rows only and remembers them for the sink's partial upload (`take_color_rows`). A whole
layer write, a layer added or removed, another bone or layer: every row once. A topology change (an Undo past a
modelling step) rebuilds rows and triangles. Rest positions are re-read only after the watch saw vertices move.

**Positions** (`positions(cage)`): the shown cage when there is one (`SurfacePositions`, posed or morphed: one gather
over its table), else the edit mesh's rest positions. The heatmap sits where the window draws the surface.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from viewport.derived import triangulate_mesh_face

from .skin_weights import bone_share
from .skinning import skin_layer
from .soft_selection.shading import weight_colors

_NO_TRIS = np.zeros((0, 3), dtype=np.uint32)


class WeightHeat:
    """The heatmap of one (mesh, layer, bone) (module docstring). `show` sets the target; `refresh` follows the mesh."""

    def __init__(self) -> None:
        self.mesh = None
        self.layer = None
        self.bone = None
        self.hidden: frozenset = frozenset()
        self._watch = None
        self.ids: list = []
        self.index: dict = {}
        self.tris: np.ndarray = _NO_TRIS
        #: the face of every triangle (the room's ray hit names it: "connected only" seeds from it)
        self.tri_face: np.ndarray = np.zeros(0, dtype=np.int64)
        self.shares: np.ndarray = np.zeros(0)
        self.colors: np.ndarray = np.zeros((0, 4), dtype=np.float32)
        #: bumped when rows or triangles were rebuilt (the sink re-uploads everything)
        self.topology_revision = 0
        #: bumped when the rest positions moved (the sink re-reads them without a cage)
        self.position_revision = 0
        self._rest: Optional[np.ndarray] = None
        #: rows whose colour changed since the last `take_color_rows` (None = all)
        self._color_rows: Optional[set] = None
        #: diagnostics (tests, probe): whole recomputes and single rows recomputed
        self.full_computes = 0
        self.row_updates = 0

    # -- the target ------------------------------------------------------------------------------------------------

    def show(self, mesh, layer, bone, hidden_faces=frozenset()) -> None:
        """The mesh, its skin layer (None = none yet: every share 0) and the bone (None = none: every share 0) shown;
        `hidden_faces` are not drawn. Cheap when nothing changed (called once per frame)."""
        hidden = frozenset(hidden_faces)
        if mesh is not self.mesh:
            self.close()
            self.mesh = mesh
            self._watch = mesh.watch()
            self.hidden = hidden
            self.layer, self.bone = layer, bone
            self._rebuild()
            return
        if hidden != self.hidden:
            self.hidden = hidden
            self._triangles()
            self.topology_revision += 1
        if (layer, bone) != (self.layer, self.bone):
            self.layer, self.bone = layer, bone
            self._all_shares()

    def close(self) -> None:
        if self._watch is not None:
            self._watch.close()
        self._watch = None
        self.mesh = None
        self._rest = None

    # -- following the mesh ----------------------------------------------------------------------------------------

    def pending(self) -> bool:
        """The mesh changed since the last `refresh` in a way the heatmap shows (no work is done)."""
        if self._watch is None:
            return False
        change = self._watch.peek()
        return bool(change.vertices or change.edges or change.faces or change.layers_touched)

    def refresh(self) -> bool:
        """Takes the mesh's changes since the last call (module docstring). True = rows, colours or positions changed."""
        if self._watch is None:
            return False
        change = self._watch.take()
        if change.is_empty():
            return False
        mesh = self.mesh
        if change.edges or change.faces or any(
                (v in self.index) != mesh.is_valid_vertex(v) for v in change.vertices):
            self._rebuild()
            return True
        changed = False
        if change.vertices:
            self._rest = None
            self.position_revision += 1
            changed = True
        if not change.layers_touched:
            return changed
        layer = skin_layer(mesh)
        if layer != self.layer:
            self.layer = layer  # the layer came (the first stroke) or went (its Undo)
            self._all_shares()
            return True
        if self.layer is None:
            return changed
        if self.layer in change.layer_whole:
            self._all_shares()
            return True
        keys = change.layer_values.get(self.layer) if self.layer is not None else None
        if keys:
            self._rows(keys)
            changed = True
        return changed

    def take_color_rows(self) -> Optional[list]:
        """The rows whose colour changed since the last call, ascending (None = all of them); then none are pending."""
        rows, self._color_rows = self._color_rows, set()
        return None if rows is None else sorted(rows)

    # -- positions -------------------------------------------------------------------------------------------------

    def positions(self, cage=None) -> np.ndarray:
        """`(n, 3)` float32 positions of the rows: the shown cage's (a `SurfacePositions` with the mesh's IDs), else the
        rest positions (cached until the watch saw them move)."""
        if cage is not None and hasattr(cage, "table_slots"):
            try:
                return np.asarray(cage.position_array()[cage.table_slots(self.ids)], dtype=np.float32)
            except KeyError:
                pass  # the cage is behind the mesh's topology for this frame: the rest shape
        if self._rest is None:
            read = self.mesh.vertex_position
            n = len(self.ids)
            self._rest = np.fromiter((c for v in self.ids for c in read(v)), dtype=np.float32,
                                     count=3 * n).reshape(n, 3)
        return self._rest

    # -- internals -------------------------------------------------------------------------------------------------

    def _rebuild(self) -> None:
        mesh = self.mesh
        self.ids = list(mesh.all_vertex_ids())
        self.index = {v: i for i, v in enumerate(self.ids)}
        self._rest = None
        self.layer = skin_layer(mesh)
        self._triangles()
        self.topology_revision += 1
        self._all_shares()

    def _triangles(self) -> None:
        mesh, index, hidden = self.mesh, self.index, self.hidden
        rows, faces = [], []
        for f in mesh.all_face_ids():
            if f in hidden:
                continue
            for tri in triangulate_mesh_face(mesh, f):
                rows.extend(index[v] for v in tri)
                faces.append(int(f))
        self.tris = np.array(rows, dtype=np.uint32).reshape(-1, 3) if rows else _NO_TRIS
        self.tri_face = np.array(faces, dtype=np.int64)

    def _all_shares(self) -> None:
        shares = np.zeros(len(self.ids))
        if self.layer is not None and self.bone is not None:
            index, bone = self.index, self.bone
            for v, value in self.mesh.layer_items(self.layer):
                i = index.get(v)
                if i is not None:
                    shares[i] = bone_share(value, bone)
        self.shares = shares
        self.colors = weight_colors(shares)
        self._color_rows = None
        self.full_computes += 1

    def _rows(self, vertices) -> None:
        mesh, layer, bone, index = self.mesh, self.layer, self.bone, self.index
        rows = [index[v] for v in vertices if v in index]
        if not rows or bone is None:
            return
        shares = np.fromiter((bone_share(mesh.layer_value(layer, self.ids[i]), bone) for i in rows),
                             dtype=np.float64, count=len(rows))
        rows_a = np.asarray(rows, dtype=np.int64)
        self.shares[rows_a] = shares
        self.colors[rows_a] = weight_colors(shares)
        if self._color_rows is not None:
            self._color_rows.update(rows)
        self.row_updates += len(rows)
