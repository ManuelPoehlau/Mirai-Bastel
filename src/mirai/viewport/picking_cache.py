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

Invalidation is explicit, not automatic mesh-content hashing — `core.Mesh`
is frozen (AD-001/ADR-001) and exposes no revision counter to read cheaply.
The owner calls `invalidate()` whenever the mesh changes (topology or vertex
positions) or the occlusion-relevant display state changes (show_faces).
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


class PickCache:
    """Per (camera, mesh, viewport size) cache of projected screen positions
    and face screen-space bounding boxes. Refreshed lazily: `refresh()` is a
    cheap signature check when nothing changed since the last call."""

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

    def invalidate(self) -> None:
        """Forces a refresh on the next `refresh()` call. Call this whenever
        the mesh (topology or vertex positions) or the occlusion-relevant
        display state (show_faces) changed since the last pick."""
        self._generation += 1

    def refresh(self, camera, mesh, width: int, height: int) -> None:
        """Recomputes the cached projections/bboxes if the camera, mesh,
        viewport size or an explicit `invalidate()` changed the signature
        since the last call; otherwise a no-op."""
        signature = (
            id(mesh),
            id(camera),
            camera.camera_revision,
            width,
            height,
            self._generation,
        )
        if signature == self._signature:
            return
        self._signature = signature

        projector = getattr(camera, "screen_projector", None)
        if projector is not None:
            project = projector(width, height)
        else:
            def project(point):
                return camera.project_to_screen(point, width, height)
        position = mesh.vertex_position
        vertex_screen = {vid: project(position(vid)) for vid in mesh.all_vertex_ids()}
        self.vertex_screen = vertex_screen

        face_bbox = {}
        for fid in mesh.all_face_ids():
            points = [vertex_screen.get(vid) for vid in mesh.face_vertices(fid)]
            if not points or any(p is None for p in points):
                # A boundary vertex isn't projectable (behind the near
                # plane) - no cheap bbox; the occlusion test falls back to
                # testing this face exactly instead of pre-filtering it.
                face_bbox[fid] = None
                continue
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            face_bbox[fid] = (min(xs), min(ys), max(xs), max(ys))
        self.face_bbox = face_bbox

    def vertex_faces(self, mesh) -> dict:
        """vertex -> set of the faces on its edges (the faces the occlusion test excludes for
        that vertex: the union of `edge_faces` over `vertex_edges`, as the uncached test
        builds it). Built lazily once per mesh state (`id(mesh)` + `invalidate()`
        generation), independent of the camera. Read-only for callers."""
        key = (id(mesh), self._generation)
        if key != self._faces_key:
            faces: dict = {vid: set() for vid in mesh.all_vertex_ids()}
            for eid in mesh.all_edge_ids():
                edge_faces = mesh.edge_faces(eid)
                if not edge_faces:
                    continue
                for vid in mesh.edge_vertices(eid):
                    faces[vid].update(edge_faces)
            self._vertex_faces = faces
            self._faces_key = key
        return self._vertex_faces

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
                continue
            for row in range(y0, y1 + 1):
                base = row * cols
                for col in range(x0, x1 + 1):
                    cells[base + col].append(fid)
        self._inv = inv
        self._cols, self._rows = cols, rows
        self._cells = cells
        self.unbounded = unbounded

    def faces_at(self, x: float, y: float) -> list | None:
        """The faces to test for screen point `(x, y)`: its cell's faces plus `unbounded`, or
        None if the point lies outside the grid."""
        col = math.floor(x * self._inv)
        row = math.floor(y * self._inv)
        if col < 0 or row < 0 or col >= self._cols or row >= self._rows:
            return None
        faces = self._cells[row * self._cols + col]
        return faces + self.unbounded if self.unbounded else faces
