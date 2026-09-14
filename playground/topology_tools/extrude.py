"""AP-05 — Multi-Face-Extrude Tool (Playground).

Multi-Face-Extrude via Boundary-Edge-Regel: Jede Edge, die zu genau einer
selektierten Face gehört, ist eine Boundary-Edge und bekommt eine Seitenwand.
Edges zwischen zwei selektierten Faces sind intern — keine Wand.

Bei genau 1 selektierter Face ist jede ihrer Edges automatisch Boundary → das
Single-Face-Verhalten ist identisch zum bisherigen Verhalten (echter Refaktor,
keine Parallel-Implementierung).

Lifecycle:
    activate()
    begin(face_ids: set[FaceId], **_)   → Snapshot + Topologie aufgebaut,
                                          Selection auf Result-Faces remapped
                                          (INTERACTING)
    update(dx, dy, w, h)*               → Extrusions-Distanz live
    commit()                            → MeshStateCommand → history.push(),
                                          returns frozenset[FaceId] (neue Caps)
    cancel()                            → mesh.load_state(before), Selection restore
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
    """Interaktives Multi-Face-Extrude-Tool für den Artist Playground.

    Adaptiert aus experiments/mirai_bastel_viewport_V1/viewport/extrude_tool.py,
    aber gegen src/core (nicht den V1-Fork) und mit MeshStateCommand statt
    V1-eigenem _SnapshotCommand. Verallgemeinert auf beliebige Face-Mengen
    via Boundary-Edge-Regel.
    """

    def __init__(self, scene, camera) -> None:
        super().__init__()
        self._scene = scene
        self._camera = camera
        self._face_ids: frozenset[FaceId] = frozenset()
        self._normal: tuple[float, float, float] | None = None
        self._original_positions: dict[VertexId, tuple] = {}
        self._old_to_new: dict[VertexId, VertexId] = {}
        self._new_face_ids: frozenset[FaceId] = frozenset()
        self._before_state: dict | None = None
        self._before_sel_mode: SelectionMode | None = None
        self._before_sel_faces: frozenset = frozenset()
        self._total_distance: float = 0.0

    @property
    def new_face_ids(self) -> frozenset[FaceId]:
        return self._new_face_ids

    # -- Tool hooks ----------------------------------------------------------

    def _on_begin(self, face_ids: set[FaceId], **_: Any) -> None:
        mesh = self._scene.mesh
        face_ids_frozen = frozenset(face_ids)

        if not face_ids_frozen:
            raise TopologyToolError("Mindestens eine Face erforderlich.")
        for fid in face_ids_frozen:
            if not mesh.is_valid_face(fid):
                raise TopologyToolError(f"Ungültige Face: {fid!r}")
            if len(mesh.face_vertices(fid)) < 3:
                raise TopologyToolError("Face benötigt mindestens 3 Vertices.")

        # Snapshot vor jeder Mutation
        self._before_state = mesh.export_state()
        sel = self._scene.selection
        self._before_sel_mode = sel.mode
        self._before_sel_faces = frozenset(sel.faces)

        self._face_ids = face_ids_frozen

        # Gemittelte Normale über alle selektierten Faces
        nx, ny, nz = 0.0, 0.0, 0.0
        for fid in face_ids_frozen:
            fn = _compute_face_normal(mesh, mesh.face_vertices(fid))
            nx += fn[0]; ny += fn[1]; nz += fn[2]
        length = (nx * nx + ny * ny + nz * nz) ** 0.5
        self._normal = (nx / length, ny / length, nz / length) if length >= 1e-12 else (0.0, 0.0, 1.0)

        # Union aller Vertices aus allen selektierten Faces (keine Duplikate)
        all_vids: set[VertexId] = set()
        for fid in face_ids_frozen:
            all_vids.update(mesh.face_vertices(fid))

        self._original_positions = {vid: mesh.vertex_position(vid) for vid in all_vids}
        self._total_distance = 0.0

        # Ein neuer Vertex pro altem Vertex
        self._old_to_new = {}
        for vid in all_vids:
            self._old_to_new[vid] = mesh.add_vertex(mesh.vertex_position(vid))

        # Seitenwände: nur Boundary-Edges (genau 1 angrenzende Face in face_ids_frozen)
        for fid in face_ids_frozen:
            boundary = mesh.face_vertices(fid)
            edges = mesh.face_edges(fid)
            n = len(boundary)
            for i, eid in enumerate(edges):
                adj = mesh.edge_faces(eid)
                in_sel = sum(1 for f in adj if f in face_ids_frozen)
                if in_sel == 1:  # Boundary-Edge → Seitenwand
                    v_curr = boundary[i]
                    v_next = boundary[(i + 1) % n]
                    mesh.add_face([v_curr, v_next, self._old_to_new[v_next], self._old_to_new[v_curr]])

        # Cap-Faces: eine pro Original-Face, auf neue Vertices gemappt
        new_face_ids: set[FaceId] = set()
        for fid in face_ids_frozen:
            new_boundary = [self._old_to_new[vid] for vid in mesh.face_vertices(fid)]
            new_face_ids.add(mesh.add_face(new_boundary))

        # Original-Faces entfernen
        for fid in face_ids_frozen:
            mesh.remove_face(fid)

        self._new_face_ids = frozenset(new_face_ids)

        # Selection-Sync: Alle entfernten Faces aus Selection rauswerfen und
        # auf neue Cap-Faces remappen — verhindert tote FaceIds im VBO-Rebuild.
        if sel.mode is SelectionMode.FACE:
            dead = face_ids_frozen & frozenset(sel.faces)
            if dead:
                sel.remove(dead)
                valid_new = {fid for fid in self._new_face_ids if mesh.is_valid_face(fid)}
                if valid_new:
                    sel.add(valid_new)

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        if self._normal is None or not self._old_to_new:
            return

        mesh = self._scene.mesh
        anchor = self._face_center_original()
        world_delta = self._camera.screen_delta_to_world(
            anchor, dx, dy, width, height
        )
        nx, ny, nz = self._normal
        self._total_distance += world_delta[0] * nx + world_delta[1] * ny + world_delta[2] * nz

        for old_vid, new_vid in self._old_to_new.items():
            orig = self._original_positions[old_vid]
            mesh.set_vertex_position(new_vid, (
                orig[0] + nx * self._total_distance,
                orig[1] + ny * self._total_distance,
                orig[2] + nz * self._total_distance,
            ))

    def _on_commit(self) -> frozenset[FaceId]:
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
        valid = {fid for fid in self._new_face_ids if mesh.is_valid_face(fid)}
        if valid:
            sel.set(valid)
        return self._new_face_ids

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
        self._face_ids = frozenset()
        self._normal = None
        self._original_positions = {}
        self._old_to_new = {}
        self._new_face_ids = frozenset()
        self._before_state = None
        self._before_sel_mode = None
        self._before_sel_faces = frozenset()
        self._total_distance = 0.0

    # -- Intern --------------------------------------------------------------

    def _face_center_original(self) -> tuple[float, float, float]:
        positions = list(self._original_positions.values())
        n = len(positions)
        if n == 0:
            return (0.0, 0.0, 0.0)
        return (
            sum(p[0] for p in positions) / n,
            sum(p[1] for p in positions) / n,
            sum(p[2] for p in positions) / n,
        )
