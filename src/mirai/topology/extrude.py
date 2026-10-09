"""Multi-Face-Extrude tool (AP-05; moved from the Playground in WP-06 Slice B9).

Moved (not copied) from `playground/topology_tools/extrude.py`: Production
(`mirai.application`, hold `T`) and the Playground (`playground/window.py`) share
this one implementation. The algorithm is unchanged. What changed is only the
Tool contract: parameterless `__init__`, context (`scene`, `camera`,
`face_ids`) through `begin(**params)`, `TopologyToolError` imported from
`connect_per_face` instead of defined a second time, and the read-only
`total_distance`/`vertex_ids` the Application needs.

Multi-Face-Extrude via Boundary-Edge-Regel: Jede Edge, die zu genau einer
selektierten Face gehört, ist eine Boundary-Edge und bekommt eine Seitenwand.
Edges zwischen zwei selektierten Faces sind intern — keine Wand.

Bei genau 1 selektierter Face ist jede ihrer Edges automatisch Boundary → das
Single-Face-Verhalten ist identisch zum bisherigen Verhalten (echter Refaktor,
keine Parallel-Implementierung).

Normale: pro zusammenhängender Komponente (nicht global) — verhindert, dass
entgegengesetzt orientierte Regionen eine Null-Summe erzeugen und in den
Z-Fallback rutschen. Die Distanz-Referenzachse bleibt global (bekannte,
akzeptierte Ungenauigkeit im entgegengesetzten Fall).

Lifecycle:
    activate()
    begin(scene, camera, face_ids, **_) → Snapshot + Topologie aufgebaut,
                                          Selection auf Result-Faces remapped
                                          (INTERACTING)
    update(dx, dy, w, h)*               → Extrusions-Distanz live
    commit()                            → MeshStateCommand → history.push(),
                                          returns frozenset[FaceId] (neue Caps)
    cancel()                            → mesh.load_state(before), Selection restore
    deactivate()

Symmetrie (AD-SYM-03 Slice 7): `begin(symmetric_plan=...)` nimmt optional ein Plan-Objekt
(`mirai.symmetric_extrude.SymmetricExtrudePlan`, duck-typed wie `KnifeTool`s `symmetric_commit`; dieses
Modul importiert nichts aus der Symmetrie). Der Plan liefert die Referenz-Normale für die Distanz
(`reference_normal`), platziert die Cap-Vertices spiegelbildlich (`place`), pflegt beim Commit Seam und
Delta (`finish`) und wählt die Selection danach (`residue`). Eine Ablehnung beim Commit erkennt das Tool
an `commit_refusal` auf der Exception: Commit zurückgenommen, keine History, `refusal` trägt den Text.
Ohne Plan ist das Verhalten unverändert.
"""

from __future__ import annotations

from typing import Any

from core import FaceId, VertexId
from core.operations.topology import MeshStateCommand
from core.selection import SelectionMode

from ..interaction.tool import Tool
from .connect_per_face import TopologyToolError


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


def _connected_components(
    face_ids: frozenset[FaceId], mesh
) -> list[frozenset[FaceId]]:
    """BFS über Adjazenz-Edges: liefert zusammenhängende Gruppen aus face_ids."""
    remaining = set(face_ids)
    components: list[frozenset[FaceId]] = []
    while remaining:
        start = next(iter(remaining))
        component: set[FaceId] = set()
        queue = [start]
        while queue:
            fid = queue.pop()
            if fid in component:
                continue
            component.add(fid)
            remaining.discard(fid)
            for eid in mesh.face_edges(fid):
                for neighbor in mesh.edge_faces(eid):
                    if neighbor in face_ids and neighbor not in component:
                        queue.append(neighbor)
        components.append(frozenset(component))
    return components


class ExtrudeTool(Tool):
    """Interaktives Multi-Face-Extrude-Tool (Production und Artist Playground).

    Adaptiert aus experiments/mirai_bastel_viewport_V1/viewport/extrude_tool.py,
    aber gegen src/core (nicht den V1-Fork) und mit MeshStateCommand statt
    V1-eigenem _SnapshotCommand. Verallgemeinert auf beliebige Face-Mengen
    via Boundary-Edge-Regel.
    """

    def __init__(self) -> None:
        super().__init__()
        self._scene = None
        self._camera = None
        self._face_ids: frozenset[FaceId] = frozenset()
        self._normal: tuple[float, float, float] | None = None  # globale Referenz für Distanz-Skalar
        self._vertex_normal: dict[VertexId, tuple[float, float, float]] = {}  # pro Vertex: Komponenten-Normale
        self._original_positions: dict[VertexId, tuple] = {}
        self._old_to_new: dict[VertexId, VertexId] = {}
        self._new_face_ids: frozenset[FaceId] = frozenset()
        self._before_state: dict | None = None
        self._before_sel_mode: SelectionMode | None = None
        self._before_sel_faces: frozenset = frozenset()
        self._total_distance: float = 0.0
        self._symmetric = None  # optionaler Plan (siehe Modul-Docstring)
        self._refusal: str | None = None

    @property
    def refusal(self) -> str | None:
        """Text der Symmetrie-Ablehnung des letzten `commit()` (None = kein Commit abgelehnt); in diesem
        Fall wurde das Mesh exakt zurückgesetzt und kein History-Eintrag erzeugt."""
        return self._refusal

    @property
    def new_face_ids(self) -> frozenset[FaceId]:
        return self._new_face_ids

    @property
    def total_distance(self) -> float:
        """Signed distance along the reference normal so far (negative = pocket)."""
        return self._total_distance

    @property
    def vertex_ids(self) -> set[VertexId]:
        """The new (cap) vertices, i.e. the ones `update()` moves."""
        return set(self._old_to_new.values())

    # -- Tool hooks ----------------------------------------------------------

    def _on_begin(self, scene, camera, face_ids: set[FaceId], symmetric_plan=None, **_: Any) -> None:
        # Validation first: a refused begin must leave the mesh and the tool untouched.
        mesh = scene.mesh
        face_ids_frozen = frozenset(face_ids)

        if not face_ids_frozen:
            raise TopologyToolError("Mindestens eine Face erforderlich.")
        for fid in face_ids_frozen:
            if not mesh.is_valid_face(fid):
                raise TopologyToolError(f"Ungültige Face: {fid!r}")
            if len(mesh.face_vertices(fid)) < 3:
                raise TopologyToolError("Face benötigt mindestens 3 Vertices.")

        self._scene = scene
        self._camera = camera
        self._symmetric = symmetric_plan
        self._refusal = None

        # Snapshot vor jeder Mutation
        self._before_state = mesh.export_state()
        sel = self._scene.selection
        self._before_sel_mode = sel.mode
        self._before_sel_faces = frozenset(sel.faces)

        # A failure half-way (the Core refusing a face) must not leave half an
        # extrusion behind: the tool stays ACTIVE after a raising begin().
        try:
            self._build_extrusion(mesh, sel, face_ids_frozen)
        except BaseException:
            self._on_cancel()
            raise

    def _build_extrusion(self, mesh, sel, face_ids_frozen: frozenset[FaceId]) -> None:
        self._face_ids = face_ids_frozen

        # Globale Referenz-Normale (für Drag-Distanz-Projektion).
        # Bei entgegengesetzt orientierten Regionen kann die Summe ≈ 0 werden
        # → Fallback Z. Das ist bekannte, akzeptierte Ungenauigkeit: die Geometrie
        # bewegt sich trotzdem korrekt (via _vertex_normal), nur der Distanz-
        # Skalar ist im entgegengesetzten Fall unpräzise.
        nx, ny, nz = 0.0, 0.0, 0.0
        for fid in face_ids_frozen:
            fn = _compute_face_normal(mesh, mesh.face_vertices(fid))
            nx += fn[0]; ny += fn[1]; nz += fn[2]
        length = (nx * nx + ny * ny + nz * nz) ** 0.5
        self._normal = (nx / length, ny / length, nz / length) if length >= 1e-12 else (0.0, 0.0, 1.0)
        if self._symmetric is not None:
            # Gespiegelte Faces heben sich in der Summe auf: unter Symmetrie misst die Seite, auf der
            # gearbeitet wird (X5).
            self._normal = self._symmetric.reference_normal

        # Komponenten-Normale pro zusammenhängender Gruppe.
        # Jeder Vertex bekommt die Normale seiner Komponente. Corner-Case: ein
        # Vertex gehört zu zwei Komponenten über eine gemeinsame Ecke (keine Edge)
        # → letzter Schreibzugriff gewinnt (deterministisch, kommt am Würfel nicht vor).
        components = _connected_components(face_ids_frozen, mesh)
        self._vertex_normal = {}
        for comp in components:
            cnx, cny, cnz = 0.0, 0.0, 0.0
            for fid in comp:
                fn = _compute_face_normal(mesh, mesh.face_vertices(fid))
                cnx += fn[0]; cny += fn[1]; cnz += fn[2]
            clen = (cnx * cnx + cny * cny + cnz * cnz) ** 0.5
            cn = (cnx / clen, cny / clen, cnz / clen) if clen >= 1e-12 else (0.0, 0.0, 1.0)
            for fid in comp:
                for vid in mesh.face_vertices(fid):
                    self._vertex_normal[vid] = cn

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

        # Kanten der Original-Region merken, bevor die Faces verschwinden: nur
        # diese dürfen anschließend als Rest-Geometrie bereinigt werden.
        region_edges: set = set()
        for fid in face_ids_frozen:
            region_edges.update(mesh.face_edges(fid))

        # Original-Faces entfernen
        for fid in face_ids_frozen:
            mesh.remove_face(fid)

        self._prune_leftover_geometry(mesh, region_edges, all_vids)

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
        # Globale Referenz-Normale für den Distanz-Skalar (gemeinsam für alle Komponenten)
        gx, gy, gz = self._normal
        self._total_distance += world_delta[0] * gx + world_delta[1] * gy + world_delta[2] * gz

        placed = {}
        for old_vid in self._old_to_new:
            orig = self._original_positions[old_vid]
            vn = self._vertex_normal[old_vid]  # Komponenten-Normale dieses Vertex
            placed[old_vid] = (
                orig[0] + vn[0] * self._total_distance,
                orig[1] + vn[1] * self._total_distance,
                orig[2] + vn[2] * self._total_distance,
            )
        if self._symmetric is not None:
            placed = self._symmetric.place(placed)  # exakt gespiegelt, Seam-Vertices auf der Ebene (X4)
        for old_vid, new_vid in self._old_to_new.items():
            mesh.set_vertex_position(new_vid, placed[old_vid])

    def _on_commit(self) -> frozenset[FaceId] | None:
        mesh = self._scene.mesh
        if self._symmetric is not None:
            # Seam und Delta vor dem Export: der Endzustand (samt Seam-Definition) ist der History-Zustand.
            try:
                self._symmetric.finish(mesh, self._old_to_new)
            except Exception as exc:
                self._on_cancel()  # was auch schiefging: exakter Vorzustand, keine History
                if not getattr(exc, "commit_refusal", False):
                    raise
                self._refusal = str(exc)
                return None
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
        if self._symmetric is not None:
            valid = set(self._symmetric.residue(mesh, valid))  # Deckel auf den Arbeitsseiten (X8)
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
        self._scene = None
        self._camera = None
        self._face_ids = frozenset()
        self._normal = None
        self._vertex_normal = {}
        self._original_positions = {}
        self._old_to_new = {}
        self._new_face_ids = frozenset()
        self._before_state = None
        self._before_sel_mode = None
        self._before_sel_faces = frozenset()
        self._total_distance = 0.0
        self._symmetric = None
        self._refusal = None

    # -- Intern --------------------------------------------------------------

    @staticmethod
    def _prune_leftover_geometry(mesh, region_edges: set, region_vertices: set) -> None:
        """Entfernt die Rest-Geometrie der ursprünglichen Region.

        Mesh.remove_face() lässt freie Edges/Vertices bewusst stehen und der
        Core (eingefroren) hat keine remove_edge/remove_vertex-Primitive. Ohne
        Bereinigung blieben die *inneren* Edges (und innere Vertices) der Region
        als Wireframe ohne Fläche an der Originalposition zurück.

        Es werden ausschließlich Edges aus `region_edges` ohne Face und
        anschließend Vertices aus `region_vertices` ohne Edge entfernt — fremde
        freie Edges (Knife/Connect) bleiben unberührt. Umsetzung über den
        öffentlichen export_state()/load_state()-Weg; IDs übriger Elemente
        bleiben unverändert (AD-001), Allocator-Zähler laufen nur vorwärts.
        """
        orphan_edges = {e for e in region_edges if not mesh.edge_faces(e)}
        if not orphan_edges:
            return
        state = mesh.export_state()
        for eid in orphan_edges:
            del state["edges"][int(eid)]
        still_used = set()
        for edata in state["edges"].values():
            still_used.add(edata["v0"])
            still_used.add(edata["v1"])
        for boundary in state["faces"].values():
            still_used.update(int(v) for v in boundary)
        for vid in region_vertices:
            if int(vid) not in still_used:
                del state["vertices"][int(vid)]
        mesh.load_state(state)

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
