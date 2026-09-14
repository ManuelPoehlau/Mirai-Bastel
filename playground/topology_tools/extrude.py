"""AP-05 — Baseline Extrude Tool (Playground).

Single-Face-Extrude, 1:1 nach V1-Prototyp, aber gegen Production-`src/core`
statt gegen den V1-Core-Fork.

Lifecycle:
    activate()
    begin(face_id=...)        → Snapshot + Topologie aufgebaut, Selection
                                 auf Result-Face remapped (INTERACTING)
    update(dx, dy, w, h)*     → Extrusions-Distanz live
    commit()                  → MeshStateCommand → history.push(), returns new FaceId
    cancel()                  → mesh.load_state(before), Selection restore
    deactivate()
"""

from __future__ import annotations

from typing import Any

from core import FaceId, VertexId
from core.operations.topology import MeshStateCommand
from core.selection import SelectionMode
from mirai.interaction.tool import Tool


class TopologyToolError(ValueError):
    pass


def _compute_face_normal(
    mesh, boundary: list[VertexId]
) -> tuple[float, float, float]:
    """Newell-Normale für eine beliebige planare Face."""
    nx, ny, nz = 0.0, 0.0, 0.0
    n = len(boundary)
    for i in range(n):
        curr = mesh.vertex_position(boundary[i])
        nxt = mesh.vertex_position(boundary[(i + 1) % n])
        nx += (curr[1] - nxt[1]) * (curr[2] + nxt[2])
        ny += (curr[2] - nxt[2]) * (curr[0] + nxt[0])
        nz += (curr[0] - nxt[0]) * (curr[1] + nxt[1])
    length = (nx * nx + ny * ny + nz * nz) ** 0.5
    if length < 1e-12:
        return (0.0, 0.0, 1.0)
    return (nx / length, ny / length, nz / length)


class ExtrudeTool(Tool):
    """Interaktives Single-Face-Extrude-Tool für den Artist Playground.

    Adaptiert aus experiments/mirai_bastel_viewport_V1/viewport/extrude_tool.py,
    aber gegen src/core (nicht den V1-Fork) und mit MeshStateCommand statt
    V1-eigenem _SnapshotCommand.
    """

    def __init__(self, scene, camera) -> None:
        super().__init__()
        self._scene = scene
        self._camera = camera
        self._face_id: FaceId | None = None
        self._normal: tuple[float, float, float] | None = None
        self._boundary: list[VertexId] = []
        self._original_positions: dict[VertexId, tuple] = {}
        self._new_vertex_ids: list[VertexId] = []
        self._new_face_id: FaceId | None = None
        self._before_state: dict | None = None
        self._before_sel_mode: SelectionMode | None = None
        self._before_sel_faces: frozenset = frozenset()
        self._total_distance: float = 0.0

    @property
    def new_face_id(self) -> FaceId | None:
        return self._new_face_id

    # -- Tool hooks ----------------------------------------------------------

    def _on_begin(self, face_id: FaceId, **_: Any) -> None:
        mesh = self._scene.mesh

        if not mesh.is_valid_face(face_id):
            raise TopologyToolError(f"Ungültige Face: {face_id!r}")

        boundary = mesh.face_vertices(face_id)
        if len(boundary) < 3:
            raise TopologyToolError("Face benötigt mindestens 3 Vertices.")

        # Snapshot vor jeder Mutation
        self._before_state = mesh.export_state()
        sel = self._scene.selection
        self._before_sel_mode = sel.mode
        self._before_sel_faces = frozenset(sel.faces)

        self._face_id = face_id
        self._boundary = boundary
        self._normal = _compute_face_normal(mesh, boundary)
        self._original_positions = {
            vid: mesh.vertex_position(vid) for vid in boundary
        }
        self._total_distance = 0.0

        # Neue Vertices an Original-Positionen (distance = 0)
        self._new_vertex_ids = []
        for vid in boundary:
            new_vid = mesh.add_vertex(mesh.vertex_position(vid))
            self._new_vertex_ids.append(new_vid)

        # Side-Faces: [v_curr, v_next, v_next_new, v_curr_new]
        n = len(boundary)
        for i in range(n):
            v_curr = boundary[i]
            v_next = boundary[(i + 1) % n]
            v_curr_new = self._new_vertex_ids[i]
            v_next_new = self._new_vertex_ids[(i + 1) % n]
            mesh.add_face([v_curr, v_next, v_next_new, v_curr_new])

        # Result-Face (gleiche Winding-Richtung)
        self._new_face_id = mesh.add_face(list(self._new_vertex_ids))

        # Original-Face entfernen
        mesh.remove_face(face_id)

        # Selection-Sync: Im Playground-Fall ist die extrudierte Face genau
        # die selektierte Face — remove_face() macht ihre ID ungültig. Ohne
        # Remap stürzt der nächste Selection-VBO-Rebuild im Window mit
        # KeyError ab (build_selection_data → mesh.face_vertices() auf einer
        # toten ID). Die selektierte Face wird auf die neue Result-Face
        # umgemappt — konsistent mit _on_commit(), das dieselbe Face
        # selektiert.
        if sel.mode is SelectionMode.FACE and face_id in sel.faces:
            sel.remove({face_id})
            if self._new_face_id is not None:
                sel.add({self._new_face_id})

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        if self._normal is None or not self._new_vertex_ids:
            return

        mesh = self._scene.mesh
        anchor = self._face_center_original()
        world_delta = self._camera.screen_delta_to_world(
            anchor, dx, dy, width, height
        )
        nx, ny, nz = self._normal
        distance_delta = world_delta[0] * nx + world_delta[1] * ny + world_delta[2] * nz
        self._total_distance += distance_delta

        for i, vid in enumerate(self._new_vertex_ids):
            orig = self._original_positions[self._boundary[i]]
            mesh.set_vertex_position(vid, (
                orig[0] + nx * self._total_distance,
                orig[1] + ny * self._total_distance,
                orig[2] + nz * self._total_distance,
            ))

    def _on_commit(self) -> FaceId | None:
        mesh = self._scene.mesh
        after = mesh.export_state()
        self._scene.history.push(
            MeshStateCommand(
                mesh=mesh,
                before_state=self._before_state,
                after_state=after,
                description="Extrude",
            )
        )
        sel = self._scene.selection
        sel.clear()
        sel.mode = SelectionMode.FACE
        if self._new_face_id is not None and mesh.is_valid_face(self._new_face_id):
            sel.set({self._new_face_id})
        return self._new_face_id

    def _on_cancel(self) -> None:
        if self._before_state is not None:
            self._scene.mesh.load_state(self._before_state)
        sel = self._scene.selection
        sel.clear()
        if self._before_sel_mode is not None:
            sel.mode = self._before_sel_mode
        # Nur gültige Face-IDs zurücksetzen (nach load_state sind alte IDs wieder valide)
        mesh = self._scene.mesh
        valid = {fid for fid in self._before_sel_faces if mesh.is_valid_face(fid)}
        if valid:
            sel.set(valid)

    def _on_deactivate(self) -> None:
        self._face_id = None
        self._normal = None
        self._boundary = []
        self._original_positions = {}
        self._new_vertex_ids = []
        self._new_face_id = None
        self._before_state = None
        self._before_sel_mode = None
        self._before_sel_faces = frozenset()
        self._total_distance = 0.0

    # -- Intern --------------------------------------------------------------

    def _face_center_original(self) -> tuple[float, float, float]:
        positions = [self._original_positions[vid] for vid in self._boundary]
        n = len(positions)
        return (
            sum(p[0] for p in positions) / n,
            sum(p[1] for p in positions) / n,
            sum(p[2] for p in positions) / n,
        )
