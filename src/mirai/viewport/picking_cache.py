"""Screen-space pick cache (WP-06 B8: picking speed + occlusion).

Every pointer move used to re-derive the camera basis (`eye()`/`basis()`,
several trig calls) and re-project every vertex from scratch inside
`pick_nearest_vertex`/`pick_nearest_edge`, and `knife_pick()` repeated that
work again for its own vertex/edge/face passes. `PickCache` computes each
vertex's screen position and each face's screen-space bounding box once per
camera/mesh state instead of once per element per pointer move; the pickers
in `picking.py` reuse the cached values for both the nearest-element search
and, when `occlusion=True`, as a cheap 2D pre-filter before the exact
ray-triangle occlusion test.

Opt-in only: every picker in `picking.py` keeps its exact old behaviour when
called without a `cache`. `Application` is the only owner of a `PickCache`
instance; the Playground's Knife call sites (window + Knife Face Cut Lab) share
it via `PlaygroundApp.pick_cache` (B8 wiring, 2026-09-29).

Invalidation: the owner calls `invalidate()` whenever the mesh changes (topology or vertex
positions) or the occlusion-relevant display state changes (show_faces). Since 2026-10-21 the
cache also watches the mesh's change journal (`core.Mesh.watch()`, AD-023) and patches only what
changed; see `PickCache`.
Camera changes need no explicit call: the cache signature already keys on
`camera.camera_revision`, which `OrbitCamera` bumps on every orbit/dolly/pan
itself, so an orbit/zoom/pan invalidates the cache automatically.

WP-VIEW-PERF-01 (Slice 1): `refresh()` projects through the camera's
`screen_projector(width, height)` when it has one (`OrbitCamera`,
`ObjectSpaceCamera`): the camera basis is computed once per refresh instead of
once per vertex, with values bit-identical to `project_to_screen`. And the
cache owns a vertex -> incident-faces map for the occlusion test
(`vertex_faces`), keyed on the mesh state only - rebuilt after `invalidate()`
or for another mesh, never because the camera moved.

WP-VIEW-PERF-01 (Slice 2): `face_grid()` buckets the face bboxes into a screen grid
(`FACE_GRID_CELL_PX` cells over the viewport), built lazily at most once per refresh state:
at once for a batch of tests (Box Select), and for single tests (hover, click, Knife, Paint)
only after `GRID_AFTER_SCANS` full scans in the same state - building it costs about as much
as that many scans, so the first pick after a camera change (one or two tests) does not pay
for it. The occlusion test then visits the faces of the point's cell instead of all faces
(`VIEWPORT_V02_ARCHITECTURE.md` §4.6: the "simple CPU spatial grid", camera-dependent like the
bboxes it is built from).
"""

from __future__ import annotations

import math

#: Edge length (px) of a `face_grid` cell (`PROVISIONAL`, engineering default from the Slice-2
#: measurement). A power of two, so `x * (1 / cell)` is exact and the cell of a point is the
#: exact floor - a face whose bbox contains the point is always in that point's cell.
FACE_GRID_CELL_PX = 16.0
#: Single occlusion tests that scan every face before one builds the grid (`PROVISIONAL`: the
#: build costs ~7 full scans on `gollum_20k`, so this bounds the waste either way to ~2x).
GRID_AFTER_SCANS = 8


#: A mesh change touching more than this share of the elements re-projects everything (`PROVISIONAL`).
PATCH_MAX_FRACTION = 0.25


def _bbox(vertex_screen: dict, boundary) -> tuple | None:
    points = [vertex_screen.get(vid) for vid in boundary]
    if not points or any(p is None for p in points):
        # A boundary vertex isn't projectable (behind the near
        # plane) - no cheap bbox; the occlusion test falls back to
        # testing this face exactly instead of pre-filtering it.
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


class PickCache:
    """Per (camera, mesh, viewport size) cache of projected screen positions
    and face screen-space bounding boxes. Refreshed lazily: `refresh()` is a
    cheap signature check when nothing changed since the last call.

    Mesh changes (2026-10-21, AD-023): the cache watches its mesh's change journal
    (`Mesh.watch()`); a refresh after a topology or position change re-projects only the
    touched vertices and the faces around them and patches `vertex_faces`, instead of the
    whole mesh. A camera / size / mesh switch still re-projects everything."""

    def __init__(self) -> None:
        self._signature: tuple | None = None
        self._generation: int = 0
        self.vertex_screen: dict = {}
        self.face_bbox: dict = {}
        self._faces_key: tuple | None = None
        self._vertex_faces: dict = {}
        self._grid_key: tuple | None = None
        self._grid: FaceGrid | None = None
        self._scans_key: tuple | None = None
        self._scans = 0
        self._watch = None
        self._project = None

    def invalidate(self) -> None:
        """Marks the cache for a check on the next `refresh()` call. Call this whenever
        the mesh (topology or vertex positions) or the occlusion-relevant
        display state (show_faces) changed since the last pick. What the mesh changed is
        read from its change journal and patched; a camera / size / mesh switch is in the
        signature and re-projects everything."""
        self._generation += 1

    def refresh(self, camera, mesh, width: int, height: int) -> None:
        """Recomputes the cached projections/bboxes if the camera, mesh,
        viewport size or an explicit `invalidate()` changed the signature
        since the last call, or the mesh changed (journal); otherwise a no-op."""
        signature = (
            id(mesh),
            id(camera),
            camera.camera_revision,
            width,
            height,
            self._generation,
        )
        watch = self._watch
        if watch is None or watch.mesh is not mesh:
            if watch is not None:
                watch.close()
            watch = self._watch = mesh.watch()
            self._signature = None
        if signature == self._signature and watch.peek().is_empty():
            return
        change = watch.take()
        old_signature = self._signature
        same_view = old_signature is not None and signature[:5] == old_signature[:5]
        self._signature = signature
        if same_view and self._patch(mesh, change, old_signature):
            return

        projector = getattr(camera, "screen_projector", None)
        if projector is not None:
            project = projector(width, height)
        else:
            def project(point):
                return camera.project_to_screen(point, width, height)
        self._project = project
        position = mesh.vertex_position
        vertex_screen = {vid: project(position(vid)) for vid in mesh.all_vertex_ids()}
        self.vertex_screen = vertex_screen

        face_vertices = mesh.face_vertices
        self.face_bbox = {fid: _bbox(vertex_screen, face_vertices(fid)) for fid in mesh.all_face_ids()}

    def _patch(self, mesh, change, old_signature) -> bool:
        """Re-projects what `change` touched (same camera, size and mesh), and moves the touched
        faces in the screen grid instead of dropping it. False = do it all."""
        grid = self._grid if self._grid_key == old_signature else None
        if change.is_empty():
            self._keep_grid(grid, old_signature)
            return True
        if len(change.vertices) + len(change.faces) > PATCH_MAX_FRACTION * (
            len(self.vertex_screen) + len(self.face_bbox)
        ):
            return False
        project = self._project
        vertex_screen, face_bbox = self.vertex_screen, self.face_bbox
        position = mesh.vertex_position
        is_valid_vertex, is_valid_face = mesh.is_valid_vertex, mesh.is_valid_face
        faces: set = set()
        for vid in change.vertices:
            if is_valid_vertex(vid):
                vertex_screen[vid] = project(position(vid))
                for eid in mesh.vertex_edges(vid):
                    faces.update(mesh.edge_faces(eid))
            else:
                vertex_screen.pop(vid, None)
        for fid in change.faces:
            if is_valid_face(fid):
                faces.add(fid)
            else:
                face_bbox.pop(fid, None)
        face_vertices = mesh.face_vertices
        for fid in change.faces:
            if not is_valid_face(fid) and grid is not None:
                grid.move(fid, None, alive=False)
        for fid in faces:
            box = face_bbox[fid] = _bbox(vertex_screen, face_vertices(fid))
            if grid is not None:
                grid.move(fid, box)
        self._keep_grid(grid, old_signature)
        return True

    def _keep_grid(self, grid, old_signature) -> None:
        if grid is not None:
            self._grid_key = self._signature
            if self._scans_key == old_signature:
                self._scans_key = self._signature

    def loose(self, mesh) -> tuple[set, set]:
        """(edges without a face, vertices without an edge) of `mesh` - the elements no face grid
        cell lists. One scan per mesh, then kept up to date from the journal."""
        self._sync_maps(mesh)
        if getattr(self, "_loose_mesh", None) is not mesh:
            self._loose_edges = {e for e in mesh.all_edge_ids() if not mesh.edge_faces(e)}
            self._loose_vertices = {v for v in mesh.all_vertex_ids() if not mesh.vertex_edges(v)}
            self._loose_mesh = mesh
        return self._loose_edges, self._loose_vertices

    def _patch_loose(self, mesh, change) -> None:
        if getattr(self, "_loose_mesh", None) is not mesh:
            return
        edges, vertices = self._loose_edges, self._loose_vertices
        touched_vertices = set(change.vertices)
        for eid, before in change.edges.items():
            if before is not None:
                touched_vertices.update(before[:2])
            if mesh.is_valid_edge(eid) and not mesh.edge_faces(eid):
                edges.add(eid)
                touched_vertices.update(mesh.edge_vertices(eid))
            else:
                edges.discard(eid)
        for vid in touched_vertices:
            if mesh.is_valid_vertex(vid) and not mesh.vertex_edges(vid):
                vertices.add(vid)
            else:
                vertices.discard(vid)

    def _patch_vertex_faces(self, mesh, change) -> None:
        if self._faces_key != id(mesh):
            return
        faces_of = self._vertex_faces
        vertices = set(change.vertices)
        for eid, before in change.edges.items():
            if before is not None:
                vertices.update(before[:2])
            if mesh.is_valid_edge(eid):
                vertices.update(mesh.edge_vertices(eid))
        for vid in vertices:
            if not mesh.is_valid_vertex(vid):
                faces_of.pop(vid, None)
                continue
            found: set = set()
            for eid in mesh.vertex_edges(vid):
                found.update(mesh.edge_faces(eid))
            faces_of[vid] = found

    def vertex_faces(self, mesh) -> dict:
        """vertex -> set of the faces on its edges (the faces the occlusion test excludes for
        that vertex: the union of `edge_faces` over `vertex_edges`, as the uncached test
        builds it). Independent of the camera: built once per mesh, then kept current from the
        mesh's change journal (2026-10-21; before, every `invalidate()` rebuilt it). Read-only
        for callers."""
        if self._sync_maps(mesh):
            faces: dict = {vid: set() for vid in mesh.all_vertex_ids()}
            for eid in mesh.all_edge_ids():
                edge_faces = mesh.edge_faces(eid)
                if not edge_faces:
                    continue
                for vid in mesh.edge_vertices(eid):
                    faces[vid].update(edge_faces)
            self._vertex_faces = faces
            self._faces_key = id(mesh)
        return self._vertex_faces

    def _sync_maps(self, mesh) -> bool:
        """Brings the camera-independent maps (`vertex_faces`, `loose`) up to date with `mesh`'s
        journal; True = `vertex_faces` must be built from scratch."""
        watch = getattr(self, "_maps_watch", None)
        if watch is None or watch.mesh is not mesh:
            if watch is not None:
                watch.close()
            self._maps_watch = mesh.watch()
            self._faces_key = None
            self._loose_mesh = None
            return True
        change = watch.take()
        if not change.is_empty():
            self._patch_vertex_faces(mesh, change)
            self._patch_loose(mesh, change)
        return self._faces_key != id(mesh)

    def face_grid(self, mesh, *, batch: bool = True) -> "FaceGrid | None":
        """The face bboxes of the last `refresh()` bucketed into screen cells, built once per
        refresh state: on the first call with `batch`, or on the `GRID_AFTER_SCANS + 1`-th call
        without it (until then None = scan every face). None as well if the last refresh was
        not for `mesh` (the bboxes would not cover its faces). Read-only for callers."""
        signature = self._signature
        if signature is None or signature[0] != id(mesh):
            return None
        if self._grid_key != signature:
            if not batch:
                if self._scans_key != signature:
                    self._scans_key = signature
                    self._scans = 0
                self._scans += 1
                if self._scans <= GRID_AFTER_SCANS:
                    return None
            self._grid = FaceGrid(self.face_bbox, signature[3], signature[4])
            self._grid_key = signature
        return self._grid


class FaceGrid:
    """Faces by screen cell: every face whose bbox overlaps a cell is listed in it (in mesh
    order), faces without a bbox (an unprojectable corner) in `unbounded`. Covers the viewport
    `[0, cols * cell) x [0, rows * cell)`; outside it `faces_at` returns None (the caller tests
    every face). For a point inside it, the faces whose bbox contains the point are a subset of
    `faces_at(point)` - the occlusion test skips every other face by that same bbox check."""

    def __init__(self, face_bbox: dict, width: int, height: int, cell: float = FACE_GRID_CELL_PX) -> None:
        inv = 1.0 / cell
        cols = max(1, int(math.ceil(width * inv)))
        rows = max(1, int(math.ceil(height * inv)))
        cells: list[list] = [[] for _ in range(cols * rows)]
        unbounded = []
        where: dict = {}
        floor = math.floor
        last_col, last_row = cols - 1, rows - 1
        for fid, bbox in face_bbox.items():
            if bbox is None:
                unbounded.append(fid)
                continue
            minx, miny, maxx, maxy = bbox
            x0 = floor(minx * inv)
            x1 = floor(maxx * inv)
            y0 = floor(miny * inv)
            y1 = floor(maxy * inv)
            if x1 < 0 or y1 < 0 or x0 > last_col or y0 > last_row:
                continue  # off the viewport: only points outside the grid can be in it
            x0, x1 = max(x0, 0), min(x1, last_col)
            y0, y1 = max(y0, 0), min(y1, last_row)
            if x0 == x1 and y0 == y1:
                cells[y0 * cols + x0].append(fid)
                where[fid] = [y0 * cols + x0]
                continue
            placed = []
            for row in range(y0, y1 + 1):
                base = row * cols
                for col in range(x0, x1 + 1):
                    cells[base + col].append(fid)
                    placed.append(base + col)
            where[fid] = placed
        self._inv = inv
        self._cols, self._rows = cols, rows
        self._cells = cells
        self.unbounded = unbounded
        self._unbounded_set = set(unbounded)
        self._where = where  # face -> the cells it is listed in (for `move`)

    def _cells_of(self, bbox):
        inv = self._inv
        minx, miny, maxx, maxy = bbox
        x0, x1 = math.floor(minx * inv), math.floor(maxx * inv)
        y0, y1 = math.floor(miny * inv), math.floor(maxy * inv)
        if x1 < 0 or y1 < 0 or x0 >= self._cols or y0 >= self._rows:
            return []
        x0, x1 = max(x0, 0), min(x1, self._cols - 1)
        y0, y1 = max(y0, 0), min(y1, self._rows - 1)
        return [row * self._cols + col for row in range(y0, y1 + 1) for col in range(x0, x1 + 1)]

    def move(self, fid, bbox, alive: bool = True) -> None:
        """Puts face `fid` into the cells of `bbox` (None = a face without a bbox: `unbounded`), or
        takes it out (`alive` False, a dead face). Keeps the grid valid across a mesh change instead
        of rebuilding it (2026-10-21)."""
        where = self._where.pop(fid, None)
        if where is not None:
            for cell in where:
                self._cells[cell].remove(fid)
        elif fid in self._unbounded_set:
            self._unbounded_set.discard(fid)
            self.unbounded.remove(fid)
        if not alive:
            return
        if bbox is None:
            self.unbounded.append(fid)
            self._unbounded_set.add(fid)
            return
        cells = self._cells_of(bbox)
        for cell in cells:
            self._cells[cell].append(fid)
        self._where[fid] = cells

    def faces_in_rect(self, x0: float, y0: float, x1: float, y1: float) -> set | None:
        """Every face whose bbox may overlap the rectangle (its cells' faces plus `unbounded`), or
        None if the rectangle is not inside the grid."""
        inv = self._inv
        c0, c1 = math.floor(x0 * inv), math.floor(x1 * inv)
        r0, r1 = math.floor(y0 * inv), math.floor(y1 * inv)
        if c0 < 0 or r0 < 0 or c1 >= self._cols or r1 >= self._rows:
            return None
        found = set(self.unbounded)
        cells, cols = self._cells, self._cols
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                found.update(cells[row * cols + col])
        return found

    def faces_at(self, x: float, y: float) -> list | None:
        """The faces to test for screen point `(x, y)`: its cell's faces plus `unbounded`, or
        None if the point lies outside the grid."""
        col = math.floor(x * self._inv)
        row = math.floor(y * self._inv)
        if col < 0 or row < 0 or col >= self._cols or row >= self._rows:
            return None
        faces = self._cells[row * self._cols + col]
        return faces + self.unbounded if self.unbounded else faces
