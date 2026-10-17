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
"""

from __future__ import annotations


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
