"""Loop Slide — interaktives Position-Tool (AP-05).

Verschiebt alle Vertices eines Edge Loops entlang ihrer Slide-Kanten
(senkrecht zur Loop-Richtung). Reine Positionsänderung, keine Topologie-Mutation.

Lifecycle (analog ExtrudeTool):
    activate()
    begin(edge_ids: set[EdgeId])   → Snapshot + Slide-Vektoren berechnen
    update(dx, dy, w, h)*          → t akkumulieren, Positionen interpolieren
    commit()                       → MeshStateCommand → history.push()
    cancel()                       → mesh.load_state(before)
    deactivate()

Scope: geschlossene Edge Loops in regulärer Quad-Topologie (jeder Loop-Vertex
hat genau 2 Loop-Kanten und genau 2 Slide-Kanten). Wirft LoopSlideError sonst.
"""

from __future__ import annotations

from typing import Any

from core import EdgeId, VertexId
from core.operations.topology import MeshStateCommand
from mirai.interaction.tool import Tool


class LoopSlideError(ValueError):
    pass


class LoopSlideTool(Tool):
    """Interaktives Loop-Slide-Tool für den Artist Playground."""

    def __init__(self, scene, camera) -> None:
        super().__init__()
        self._scene = scene
        self._camera = camera
        self._before_state: dict | None = None
        # vid → (original_pos, neighbor_a_pos, neighbor_b_pos)
        self._slide_data: dict[VertexId, tuple] = {}
        self._total_t: float = 0.0

    def _on_begin(self, edge_ids: set[EdgeId], **_: Any) -> None:
        mesh = self._scene.mesh
        edge_set = set(edge_ids)

        if len(edge_set) < 2:
            raise LoopSlideError("Loop Slide benötigt mindestens 2 Edges.")
        for eid in edge_set:
            if not mesh.is_valid_edge(eid):
                raise LoopSlideError(f"Unbekannte Edge: {eid!r}")

        loop_verts: set[VertexId] = set()
        for eid in edge_set:
            v0, v1 = mesh.edge_vertices(eid)
            loop_verts.add(v0)
            loop_verts.add(v1)

        def _other(eid, vid):
            v0, v1 = mesh.edge_vertices(eid)
            return v1 if v0 == vid else v0

        slide_data: dict[VertexId, tuple] = {}
        for vid in loop_verts:
            incident = mesh.vertex_edges(vid)
            loop_here = [e for e in incident if e in edge_set]
            slide_edges = [e for e in incident if e not in edge_set]

            if len(loop_here) != 2:
                raise LoopSlideError(
                    f"Vertex {vid!r} hat {len(loop_here)} Loop-Kante(n) — "
                    "Loop Slide erfordert geschlossene Loops (genau 2 pro Vertex)."
                )
            if len(slide_edges) != 2:
                raise LoopSlideError(
                    f"Vertex {vid!r}: erwartet 2 Slide-Kanten, gefunden {len(slide_edges)}."
                )

            na = _other(slide_edges[0], vid)
            nb = _other(slide_edges[1], vid)
            slide_data[vid] = (
                mesh.vertex_position(vid),
                mesh.vertex_position(na),
                mesh.vertex_position(nb),
            )

        self._before_state = mesh.export_state()
        self._slide_data = slide_data
        self._total_t = 0.0

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        if not self._slide_data:
            return

        self._total_t += dx / width * 2.0
        self._total_t = max(-1.0, min(1.0, self._total_t))

        mesh = self._scene.mesh
        for vid, (orig, na_pos, nb_pos) in self._slide_data.items():
            if self._total_t >= 0.0:
                t = self._total_t
                target = na_pos
            else:
                t = -self._total_t
                target = nb_pos
            new_pos = tuple(orig[i] + t * (target[i] - orig[i]) for i in range(3))
            mesh.set_vertex_position(vid, new_pos)

    def _on_commit(self) -> None:
        mesh = self._scene.mesh
        after = mesh.export_state()
        self._scene.history.push(
            MeshStateCommand(
                mesh=mesh,
                before_state=self._before_state,
                after_state=after,
                description="Loop Slide",
            )
        )

    def _on_cancel(self) -> None:
        if self._before_state is not None:
            self._scene.mesh.load_state(self._before_state)

    def _on_deactivate(self) -> None:
        self._before_state = None
        self._slide_data = {}
        self._total_t = 0.0
