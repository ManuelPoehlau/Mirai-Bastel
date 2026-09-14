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

        def _other_vertex(eid, vid):
            v0, v1 = mesh.edge_vertices(eid)
            return v1 if v0 == vid else v0

        # --- Schritt 1: Loop-Kanten zu geordnetem Zyklus (v_0..v_{n-1}) sortieren ---
        start_edge = next(iter(edge_set))
        v_start, _ = mesh.edge_vertices(start_edge)

        ordered_verts: list[VertexId] = []
        ordered_edges: list[EdgeId] = []
        cur_v = v_start
        cur_e = start_edge
        while True:
            incident = mesh.vertex_edges(cur_v)
            loop_here = [e for e in incident if e in edge_set]
            if len(loop_here) != 2:
                raise LoopSlideError(
                    f"Vertex {cur_v!r} hat {len(loop_here)} Loop-Kante(n) — "
                    "Loop Slide erfordert geschlossene Loops (genau 2 pro Vertex)."
                )
            ordered_verts.append(cur_v)
            ordered_edges.append(cur_e)
            next_v = _other_vertex(cur_e, cur_v)
            if next_v == v_start:
                break
            # Weiterlaufen über die andere Loop-Kante an next_v
            next_loop = [e for e in mesh.vertex_edges(next_v) if e in edge_set and e != cur_e]
            if len(next_loop) != 1:
                raise LoopSlideError(
                    f"Vertex {next_v!r}: kein eindeutiger Loop-Walk möglich."
                )
            cur_v = next_v
            cur_e = next_loop[0]

        n = len(ordered_verts)
        if n != len(edge_set):
            raise LoopSlideError("Loop ist nicht geschlossen oder enthält Verzweigungen.")

        # --- Schritt 2: konsistente Seiten-Zuordnung entlang des Zyklus ---
        na_map: dict[VertexId, VertexId] = {}

        face_current = mesh.edge_faces(ordered_edges[0])[0]
        start_face = face_current

        for i in range(n):
            v_i = ordered_verts[i]
            v_j = ordered_verts[(i + 1) % n]
            e_i = ordered_edges[i]

            face_verts = mesh.face_vertices(face_current)
            if len(face_verts) != 4:
                raise LoopSlideError("Loop Slide erfordert ausschließlich Quad-Faces.")

            # Die beiden "anderen" Einträge (nicht v_i, nicht v_j) im Face-Zyklus
            others = [v for v in face_verts if v != v_i and v != v_j]
            if len(others) != 2:
                raise LoopSlideError(
                    f"Face enthält unerwartete Vertices bei Edge {e_i!r}."
                )

            # Im Face-Zyklus: der Nachbar von v_i (nicht v_j) ist na(v_i),
            # der Nachbar von v_j (nicht v_i) ist na(v_j).
            idx_i = face_verts.index(v_i)
            idx_j = face_verts.index(v_j)
            # Nachbar von v_i im Face-Zyklus (Index ±1), der nicht v_j ist
            candidates_i = [
                face_verts[(idx_i - 1) % 4],
                face_verts[(idx_i + 1) % 4],
            ]
            na_i = next(v for v in candidates_i if v != v_j)
            candidates_j = [
                face_verts[(idx_j - 1) % 4],
                face_verts[(idx_j + 1) % 4],
            ]
            na_j = next(v for v in candidates_j if v != v_i)

            for vid, na_val in ((v_i, na_i), (v_j, na_j)):
                if vid in na_map and na_map[vid] != na_val:
                    raise LoopSlideError(
                        f"Inkonsistente Seiten-Zuordnung bei Vertex {vid!r} — "
                        "irreguläre Topologie außerhalb des Loop-Slide-Scope."
                    )
                na_map[vid] = na_val

            # Slide-Kante von v_j zu na_j; face_current für nächsten Schritt
            slide_edge_j = None
            for eid in mesh.vertex_edges(v_j):
                if set(mesh.edge_vertices(eid)) == {v_j, na_j}:
                    slide_edge_j = eid
                    break
            if slide_edge_j is None:
                raise LoopSlideError(
                    f"Slide-Kante zwischen {v_j!r} und {na_j!r} nicht gefunden."
                )
            next_faces = [f for f in mesh.edge_faces(slide_edge_j) if f != face_current]
            face_current = next_faces[0] if next_faces else face_current

        if face_current != start_face:
            raise LoopSlideError(
                "Loop ist nach vollständigem Umlauf nicht geschlossen — "
                "irreguläre oder nicht-manifold Topologie außerhalb des Scope."
            )

        # --- slide_data aufbauen: na aus na_map, nb = der andere Slide-Nachbar ---
        slide_data: dict[VertexId, tuple] = {}
        for vid, na_vid in na_map.items():
            incident = mesh.vertex_edges(vid)
            slide_edges = [e for e in incident if e not in edge_set]
            if len(slide_edges) != 2:
                raise LoopSlideError(
                    f"Vertex {vid!r}: erwartet 2 Slide-Kanten, gefunden {len(slide_edges)}."
                )
            nb_vid = next(
                _other_vertex(e, vid) for e in slide_edges
                if _other_vertex(e, vid) != na_vid
            )
            slide_data[vid] = (
                mesh.vertex_position(vid),
                mesh.vertex_position(na_vid),
                mesh.vertex_position(nb_vid),
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
