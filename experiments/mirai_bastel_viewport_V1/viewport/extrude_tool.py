"""Experimentelles Extrude-Tool für das Topology-Lab.

Single-Face-Extrude: Eine ausgewählte Face wird entlang ihrer Normale
extrudiert. Die Topologie wird live während der Interaktion aufgebaut,
Commit erzeugt genau einen History-Eintrag, Cancel stellt den
ursprünglichen Mesh-Zustand wieder her.

Lifecycle (governed by Tool base class):

    activate()  → Tool bereit (ACTIVE)
    begin(face_id) → Topologie aufgebaut, INTERACTING
    update(dx,dy,width,height)* → Extrusionsdistanz live
    commit()    → History-Eintrag, neue Face ausgewählt (ACTIVE)
    cancel()    → Mesh-Restore, keine History (ACTIVE)

Scope: exakt eine Face, polygonale Faces, Newell-Normale, kein Refactoring
des Production-Cores.
"""

from __future__ import annotations

from typing import Any

from mirai_bastel_core import FaceId, Mesh, VertexId

from . import vecmath as v
from .camera import OrbitCamera
from .tool import Tool
from .topology_tools import TopologyToolError, _SnapshotCommand


def _compute_face_normal(mesh: Mesh, boundary: list[VertexId]) -> v.Vec3:
    """Robuste Face-Normale über Newell's Methode.

    Funktioniert für beliebige planare Polygon-Faces (nicht nur Quads).
    Die Richtung folgt der Vertex-Reihenfolge der Face-Boundary (Winding).
    """
    nx, ny, nz = 0.0, 0.0, 0.0
    n = len(boundary)
    for i in range(n):
        curr = mesh.vertex_position(boundary[i])
        next_p = mesh.vertex_position(boundary[(i + 1) % n])
        nx += (curr[1] - next_p[1]) * (curr[2] + next_p[2])
        ny += (curr[2] - next_p[2]) * (curr[0] + next_p[0])
        nz += (curr[0] - next_p[0]) * (curr[1] + next_p[1])
    return v.normalize((nx, ny, nz))


class ExtrudeTool(Tool):
    """Interaktives Single-Face-Extrude-Tool.

    begin(face_id=...):
        - Validierung: exakt eine gültige Face
        - Mesh-Snapshot für Cancel
        - Newell-Normale berechnen
        - Neue Vertices (Anfang: distance=0), Side-Faces, Result-Face erzeugen

    update(dx, dy, width, height):
        - Pixel-Delta → Welt-Delta (Kamera-Projektion)
        - Welt-Delta auf Normale projizieren → kumulierte Distanz
        - Neue Vertex-Positions live setzen

    commit():
        - Ein History-Eintrag (Snapshot: before → after)
        - Liefert die neue Result-FaceId

    cancel():
        - Mesh-Snapshot wiederherstellen
    """

    def __init__(self, scene, camera: OrbitCamera) -> None:
        super().__init__()
        self._scene = scene
        self._camera = camera
        # Interaktionszustand
        self._face_id: FaceId | None = None
        self._normal: v.Vec3 | None = None
        self._boundary: list[VertexId] = []
        self._original_positions: dict[VertexId, v.Vec3] = {}
        self._new_vertex_ids: list[VertexId] = []
        self._new_face_id: FaceId | None = None
        self._before_state: dict | None = None
        self._total_distance: float = 0.0

    # -- Beobachtbarkeit für Tests/Integration ------------------------------

    @property
    def face_id(self) -> FaceId | None:
        return self._face_id

    @property
    def normal(self) -> v.Vec3 | None:
        return self._normal

    @property
    def new_face_id(self) -> FaceId | None:
        return self._new_face_id

    @property
    def new_vertex_ids(self) -> list[VertexId]:
        return list(self._new_vertex_ids)

    @property
    def total_distance(self) -> float:
        return self._total_distance

    # -- Hooks ---------------------------------------------------------------

    def _on_begin(self, face_id: FaceId, **params: Any) -> None:
        mesh = self._scene.mesh
        face_id = FaceId(face_id) if not isinstance(face_id, FaceId) else face_id

        if not mesh.is_valid_face(face_id):
            raise TopologyToolError(f"Ungültige Face: {face_id!r}")

        boundary = mesh.face_vertices(face_id)
        if len(boundary) < 3:
            raise TopologyToolError("Face benötigt mindestens 3 Vertices.")

        # Snapshot für Cancel (vor jeder Mutation)
        self._before_state = mesh.export_state()
        self._face_id = face_id
        self._boundary = boundary
        self._normal = _compute_face_normal(mesh, boundary)
        self._original_positions = {vid: mesh.vertex_position(vid) for vid in boundary}
        self._total_distance = 0.0

        # Neue Vertices erzeugen (anfangs an Original-Position, distance=0)
        self._new_vertex_ids = []
        for vid in boundary:
            pos = mesh.vertex_position(vid)
            new_vid = mesh.add_vertex(pos)
            self._new_vertex_ids.append(new_vid)

        # Side-Faces erzeugen: [v_curr, v_next, v_next_new, v_curr_new]
        n = len(boundary)
        for i in range(n):
            v_curr = boundary[i]
            v_next = boundary[(i + 1) % n]
            v_curr_new = self._new_vertex_ids[i]
            v_next_new = self._new_vertex_ids[(i + 1) % n]
            mesh.add_face([v_curr, v_next, v_next_new, v_curr_new])

        # Result-Face erzeugen (gleiche Winding-Richtung wie Original)
        self._new_face_id = mesh.add_face(list(self._new_vertex_ids))

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        if self._normal is None or not self._new_vertex_ids:
            return

        mesh = self._scene.mesh

        # Face-Center der Original-Face als Ankerpunkt für Kamera-Projektion
        anchor = self._face_center_original()

        # Pixel-Delta → Welt-Delta auf der Kamera-Bildebene
        world_delta = self._camera.screen_delta_to_world(
            anchor, dx, dy, width, height
        )

        # Welt-Delta auf Face-Normale projizieren → incrementelle Distanz
        distance_delta = v.dot(world_delta, self._normal)
        self._total_distance += distance_delta

        # Neue Vertex-Positions setzen: original + normal * total_distance
        for i, vid in enumerate(self._new_vertex_ids):
            orig = self._original_positions[self._boundary[i]]
            new_pos = tuple(
                orig[j] + self._normal[j] * self._total_distance for j in range(3)
            )
            mesh.set_vertex_position(vid, new_pos)

    def _on_commit(self) -> Any:
        mesh = self._scene.mesh
        after = mesh.export_state()

        if self._before_state == after:
            raise TopologyToolError("Extrude erzeugte keine Geometrieänderung.")

        command = _SnapshotCommand(
            mesh, self._before_state, after, "Extrude",
        )
        self._scene.history.push(command)
        return self._new_face_id

    def _on_cancel(self) -> None:
        if self._before_state is not None:
            self._scene.mesh.load_state(self._before_state)

    def _on_deactivate(self) -> None:
        self._face_id = None
        self._normal = None
        self._boundary = []
        self._original_positions = {}
        self._new_vertex_ids = []
        self._new_face_id = None
        self._before_state = None
        self._total_distance = 0.0

    # -- Interne Hilfsfunktionen ----------------------------------------------

    def _face_center_original(self) -> v.Vec3:
        """Mittelpunkt der Original-Face (unabhängig von der Extrusion)."""
        positions = [self._original_positions[vid] for vid in self._boundary]
        n = len(positions)
        return (
            sum(p[0] for p in positions) / n,
            sum(p[1] for p in positions) / n,
            sum(p[2] for p in positions) / n,
        )