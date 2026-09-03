"""Experimentelle Topologie-Werkzeuge für den V1-Viewport."""

from __future__ import annotations

from dataclasses import dataclass

from mirai_bastel_core import EdgeId, FaceId, Mesh

from .loop_ring import edge_loop, edge_ring, LoopRingError


class TopologyToolError(ValueError):
    pass


class _SnapshotCommand:
    """Experimenteller History-Adapter über Mesh export/load_state.

    Erweitert um optionale Selection-Restoration: before_selection und
    after_selection sind Diktionäre mit {'mode': SelectionMode, 'vertices': set,
    'edges': set, 'faces': set}. Bei undo/redo wird die zugehörige Selection
    nach der Mesh-Restoration wiederhergestellt.
    """

    def __init__(self, mesh, before: dict, after: dict, description: str, on_restore=None,
                 selection=None, before_selection=None, after_selection=None):
        self._mesh = mesh
        self._before = before
        self._after = after
        self.description = description
        self._on_restore = on_restore
        self._selection = selection
        self._before_selection = before_selection
        self._after_selection = after_selection

    def undo(self) -> None:
        self._mesh.load_state(self._before)
        self._restore_selection(self._before_selection)
        if self._on_restore:
            self._on_restore()

    def redo(self) -> None:
        self._mesh.load_state(self._after)
        self._restore_selection(self._after_selection)
        if self._on_restore:
            self._on_restore()

    def _restore_selection(self, sel_state) -> None:
        """Restauriert Selection aus einem gespeicherten Zustand.

        Ungültige IDs (z.B. nach Undo nicht mehr existierende Faces) werden
        gefiltert, damit _rebuild_geometry() nicht mit KeyError abstürzt.
        """
        if sel_state is None or self._selection is None:
            return
        from mirai_bastel_core import SelectionMode
        self._selection.clear()
        self._selection.mode = sel_state['mode']
        if sel_state['mode'] == SelectionMode.VERTEX:
            valid = {vid for vid in sel_state['vertices'] if self._mesh.is_valid_vertex(vid)}
            self._selection.set(valid)
        elif sel_state['mode'] == SelectionMode.EDGE:
            valid = {eid for eid in sel_state['edges'] if self._mesh.is_valid_edge(eid)}
            self._selection.set(valid)
        elif sel_state['mode'] == SelectionMode.FACE:
            valid = {fid for fid in sel_state['faces'] if self._mesh.is_valid_face(fid)}
            self._selection.set(valid)


def _push_snapshot(scene, before: dict, description: str, on_restore=None) -> None:
    after = scene.mesh.export_state()
    if before == after:
        raise TopologyToolError("Die Operation hat keine Topologieänderung erzeugt.")
    scene.history.push(_SnapshotCommand(scene.mesh, before, after, description, on_restore))


def split_selected_edge(scene, edge_id, *, on_restore=None):
    mesh = scene.mesh
    before = mesh.export_state()
    result = mesh.split_edge(edge_id)
    _push_snapshot(scene, before, "Split Edge", on_restore)
    return result


def collapse_selected_edge(scene, edge_id, *, on_restore=None):
    mesh = scene.mesh
    before = mesh.export_state()
    result = mesh.collapse_edge(edge_id)
    _push_snapshot(scene, before, "Collapse Edge", on_restore)
    return result


def _common_face_for_vertices(mesh, vertex_ids):
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        if all(v in boundary for v in vertex_ids):
            return fid
    return None


def connect_selected_vertices(scene, vertex_ids, *, on_restore=None):
    if len(vertex_ids) < 2:
        raise TopologyToolError("Connect Vertices benötigt mindestens 2 Vertices.")

    mesh = scene.mesh
    selected = sorted(vertex_ids, key=int)
    before = mesh.export_state()
    created = []

    # Experimentelle Multi-Semantik: deterministische Kette in ID-Reihenfolge.
    for v_a, v_b in zip(selected, selected[1:]):
        if not mesh.is_valid_vertex(v_a) or not mesh.is_valid_vertex(v_b):
            continue
        if any(set(mesh.edge_vertices(eid)) == {v_a, v_b} for eid in mesh.all_edge_ids()):
            continue
        face_id = _common_face_for_vertices(mesh, (v_a, v_b))
        if face_id is None:
            if not created:
                raise TopologyToolError("Mindestens zwei aufeinanderfolgende Vertices benötigen eine gemeinsame Face.")
            break
        edge_id, _, _ = mesh.connect_vertices(face_id, v_a, v_b)
        created.append(edge_id)

    if not created:
        raise TopologyToolError("Keine neue Verbindung möglich.")

    _push_snapshot(scene, before, "Connect Vertices", on_restore)
    return created


# ---------------------------------------------------------------------------
# Connect Edges — topology-aware (docs/research/topology/CONNECT_EDGES_SPEC.md)
#
# Drei klar getrennte Phasen:
#   1. Analyze/Validate: Auswahl pruefen, topologische Gruppen und saemtliche
#      gueltigen Connections bestimmen. Reiner Lesezugriff - das Mesh wird
#      hier NICHT veraendert.
#   2. Plan: vollstaendiger deterministischer Operationsplan. Jede Connection
#      wird VOR der Mutation bewiesen (Dry-Run auf einem Clone des Mesh).
#      Keine Connection kann erst waehrend der Mutation als ungueltig erkannt
#      werden.
#   3. Apply/Commit: Plan auf dem echten Mesh ausfuehren (Midpoint-Zuordnungen
#      bleiben erhalten), dann genau EINEN History-Snapshot committen. Bei
#      jedem Konstruktionsfehler wird der exakte Vorher-Zustand wiederhergestellt
#      (Atomizitaet).
#
# Gruppierung/Reihenfolge beruht ausschliesslich auf Topologie/Geometrie:
#   - kind "f" (Face-Verbindung): zwei ausgewaehlte Edges liegen in einer
#     gemeinsamen Quad-Face gegenueber -> Mittelpunkte via connect_vertices().
#   - kind "v" (Ketten-Verbindung): zwei Edges teilen einen regulären
#     Innen-Vertex ohne gemeinsame Face -> freie Kante via add_edge().
# Numerische Edge-IDs und Selection-Einfuege-Reihenfolge haben keinerlei
# Einfluss auf Gruppierung oder Ergebnis.
#
# Scope: reguläre kompatible Quad-Topologie (Ketten, Ringe). Boundary-, Non-
# Quad-, Mixed-Valence- und Non-Manifold-Faelle werden explizit abgelehnt.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SplitStep:
    """Teilt eine ausgewaehlte Kante am Mittelpunkt (split_edge)."""

    edge_id: EdgeId


@dataclass(frozen=True)
class _FaceConnectStep:
    """Verbindet die Mittelpunkte zweier gegenueberliegender Kanten durch die
    gemeinsame Quad-Face (connect_vertices)."""

    face_id: FaceId
    edge_a: EdgeId
    edge_b: EdgeId


@dataclass(frozen=True)
class _FreeConnectStep:
    """Erzeugt eine freie Kante zwischen den Mittelpunkten zweier kanten-
    benachbarter Kettenglieder (add_edge)."""

    edge_a: EdgeId
    edge_b: EdgeId


def _edge_midpoint(mesh, edge_id) -> tuple:
    """Mittelpunkt-Position einer Kante (read-only, fuer deterministische,
    ID-unabhaengige Reihenfolge)."""
    v0, v1 = mesh.edge_vertices(edge_id)
    p0, p1 = mesh.vertex_position(v0), mesh.vertex_position(v1)
    return tuple((a + b) / 2.0 for a, b in zip(p0, p1))


def _shared_vertex(mesh, edge_a, edge_b):
    """Gemeinsamer Endpunkt zweier Kanten, falls vorhanden."""
    v0a, v1a = mesh.edge_vertices(edge_a)
    v0b, v1b = mesh.edge_vertices(edge_b)
    common = {v0a, v1a} & {v0b, v1b}
    if len(common) == 1:
        return next(iter(common))
    return None


def _is_regular_interior_vertex(mesh, vertex_id):
    """True, wenn der Vertex ein regulärer Innen-Vertex der Quad-Topologie
    ist: alle incidenten Kanten haben genau 2 quadratische Nachbar-Faces.

    Ketten-Verbindungen (Kante "durch" den geteilten Vertex) sind nur an
    solchen Vertices definiert. Boundary-/Mixed-Valence-Vertices liegen
    ausserhalb des aktuellen Scope."""
    incident = mesh.vertex_edges(vertex_id)
    if len(incident) < 4:
        return False
    for eid in incident:
        faces = mesh.edge_faces(eid)
        if len(faces) != 2:
            return False
        for fid in faces:
            if len(mesh.face_vertices(fid)) != 4:
                return False
    return True


def _opposite_quad_face(mesh, edge_a, edge_b):
    """Gemeinsame Quad-Face, in der edge_a und edge_b gegenueberliegen."""
    for fid in set(mesh.edge_faces(edge_a)) & set(mesh.edge_faces(edge_b)):
        edges = mesh.face_edges(fid)
        if len(edges) != 4:
            continue
        ia, ib = edges.index(edge_a), edges.index(edge_b)
        if (ia - ib) % 4 == 2:
            return fid
    return None


def _build_adjacency(mesh, selected):
    """Nachbar-Graph der Auswahl auf Basis reiner Topologie.

    Zwei ausgewaehlte Kanten sind benachbart, wenn sie
    - in einer gemeinsamen Quad-Face gegenueberliegen (kind "f"), oder
    - denselben regulären Innen-Vertex teilen und KEINE Face teilen
      (kind "v").

    Die Rueckgabe ist ein Dict Kante -> {Nachbar: (kind, Payload)}.
    """
    adjacency = {eid: {} for eid in selected}
    edges = list(selected)
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            e1, e2 = edges[i], edges[j]
            shared = _shared_vertex(mesh, e1, e2)
            if shared is not None:
                common_faces = set(mesh.edge_faces(e1)) & set(mesh.edge_faces(e2))
                if not common_faces:
                    if not _is_regular_interior_vertex(mesh, shared):
                        raise TopologyToolError(
                            "Kanten-Kette über einen Boundary-/Mixed-Valence-Vertex "
                            "liegt außerhalb des Connect-Edges-Scope "
                            "(nur reguläre Quad-Topologie)."
                        )
                    adjacency[e1][e2] = ("v", shared)
                    adjacency[e2][e1] = ("v", shared)
                    continue
            face_id = _opposite_quad_face(mesh, e1, e2)
            if face_id is not None:
                adjacency[e1][e2] = ("f", face_id)
                adjacency[e2][e1] = ("f", face_id)
    return adjacency


def _order_component_edges(mesh, adjacency, comp):
    """Kanonische Reihenfolge einer Kette/eines Rings.

    Deterministisch und ID-unabhaengig: Start und Laufrichtung werden über
    Mittelpunkt-Positionen entschieden, nie über numerische Edge-IDs oder die
    Selection-Reihenfolge. Rueckgabe: (geordnete Kanten, is_cycle).
    """
    degrees = {eid: len(adjacency[eid]) for eid in comp}
    is_cycle = all(d == 2 for d in degrees.values())
    ends = [eid for eid in comp if degrees[eid] == 1]
    if not is_cycle and len(ends) != 2:
        raise TopologyToolError(
            "Verzweigte Auswahl liegt außerhalb des Connect-Edges-Scope "
            "(nur Ketten und Ringe in regulärer Quad-Topologie)."
        )

    if is_cycle:
        start = min(comp, key=lambda eid: _edge_midpoint(mesh, eid))
        n0, n1 = list(adjacency[start])
        nxt = n1 if _edge_midpoint(mesh, n1) < _edge_midpoint(mesh, n0) else n0
    else:
        start = min(ends, key=lambda eid: _edge_midpoint(mesh, eid))
        nxt = next(iter(adjacency[start]))

    ordered = [start]
    prev, cur = start, nxt
    while True:
        if is_cycle and cur == start:
            break
        ordered.append(cur)
        candidates = [n for n in adjacency[cur] if n != prev]
        if not candidates:
            break
        prev, cur = cur, candidates[0]
    return ordered, is_cycle


def _connection_step(adjacency, edge_a, edge_b):
    """Baut den konkreten Connect-Schritt für ein benachbartes Kantenpaar."""
    kind, payload = adjacency[edge_a][edge_b]
    if kind == "f":
        return _FaceConnectStep(face_id=payload, edge_a=edge_a, edge_b=edge_b)
    if kind == "v":
        return _FreeConnectStep(edge_a=edge_a, edge_b=edge_b)
    raise TopologyToolError("Interner Fehler: unbekannte Verbindungsart.")


def _plan_for_selected(mesh, selected):
    """Phase 1+2: vollstaendiger, deterministischer Operationsplan.

    Ausschliesslich Lesezugriff auf das Mesh. Wirft TopologyToolError bei
    jeder ungueltigen/incompatiblen Auswahl - das Mesh bleibt dabei unveraendert.
    """
    adjacency = _build_adjacency(mesh, selected)

    # Zusammenhängende topologische Gruppen (Connected Components).
    seen = set()
    components = []
    for eid in adjacency:
        if eid in seen:
            continue
        stack, comp = [eid], []
        seen.add(eid)
        while stack:
            cur = stack.pop()
            comp.append(cur)
            for nxt in adjacency[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        components.append(comp)

    for comp in components:
        if len(comp) < 2:
            raise TopologyToolError(
                "Mindestens eine ausgewählte Edge hat keine kompatible "
                "Partner-Edge – keine gültige Verbindung möglich."
            )

    # Deterministische Gruppenreihenfolge über Geometrie (ID-unabhaengig).
    components.sort(
        key=lambda component: tuple(
            min(_edge_midpoint(mesh, edge) for edge in component)
        )
    )

    split_order = []
    connection_groups = []
    for comp in components:
        ordered, is_cycle = _order_component_edges(mesh, adjacency, comp)
        split_order.extend(ordered)
        steps = [
            _connection_step(adjacency, ordered[i], ordered[i + 1])
            for i in range(len(ordered) - 1)
        ]
        if is_cycle:
            steps.append(_connection_step(adjacency, ordered[-1], ordered[0]))
        connection_groups.append(steps)

    connections = [step for group in connection_groups for step in group]
    if not connections:
        raise TopologyToolError("Keine gültige Verbindung in der Auswahl möglich.")

    return [_SplitStep(eid) for eid in split_order] + connections


def _execute_plan(mesh, steps):
    """Wendet den Plan auf `mesh` an (Phase 3, Apply).

    Midpoint-Zuordnungen bleiben erhalten: jede Verbindungskante referenziert
    exakt den Mittelpunkt ihrer Ausgangskante. Gibt die erzeugten Verbindungs-
    kanten zurück. Wirft bei Konstruktionsfehlern (z. B. bereits entfernte
    Face) - der Aufrufer stellt dann den Vorher-Zustand wieder her.
    """
    created = []
    midpoints = {}
    for step in steps:
        if isinstance(step, _SplitStep):
            mid, _, _ = mesh.split_edge(step.edge_id)
            midpoints[step.edge_id] = mid
        elif isinstance(step, _FaceConnectStep):
            m_a = midpoints[step.edge_a]
            m_b = midpoints[step.edge_b]
            edge_id, _, _ = mesh.connect_vertices(step.face_id, m_a, m_b)
            created.append(edge_id)
        elif isinstance(step, _FreeConnectStep):
            m_a = midpoints[step.edge_a]
            m_b = midpoints[step.edge_b]
            created.append(mesh.add_edge(m_a, m_b))
    return created


def _validate_plan_on_clone(before_state, steps):
    """Beweist die Anwendbarkeit des Plans, bevor das echte Mesh mutiert wird.

    Fuehrt exakt dieselbe Sequenz auf einem Clone des Ausgangszustands aus
    (Phase 2, Plan-Validierung). Schlaegt der Dry-Run fehl, ist der Plan
    ungueltig - das echte Mesh bleibt unveraendert (Spec: "Keine Connection
    darf erst während der Mutation als ungueltig erkannt werden").
    """
    clone = Mesh.from_state(before_state)
    try:
        _execute_plan(clone, steps)
    except Exception as exc:
        raise TopologyToolError(
            f"Operationsplan nicht auf gültige Topologie abbildbar: {exc}"
        ) from exc


def connect_selected_edges(scene, edge_ids, *, on_restore=None):
    """Connect Edges — topology-aware (docs/research/topology/CONNECT_EDGES_SPEC.md).

    Erzeugt neue Kanten zwischen den Mittelpunkten ausgewählter Edges.

    Drei klar getrennte Phasen (Analyze/Validate -> Plan -> Apply/Commit) und
    vollstaendige Atomizitaet: Bei jedem Validierungs- oder Konstruktionsfehler
    bleibt das Mesh exakt unveraendert. Midpoint-Zuordnungen bleiben erhalten
    (die erzeugten Verbindungskanten referenzieren exakt die neuen Mittelpunkte
    der Ausgangskanten). Es wird genau EIN History-Snapshot committet.

    Scope: reguläre kompatible Quad-Topologie (Ketten, Ringe, Paar von
    gegenueberliegenden Kanten). Boundary-/Non-Quad-/Mixed-Valence-/Non-
    Manifold-Konstellationen werden explizit abgelehnt.
    """
    selected = set(edge_ids)
    if len(selected) < 2:
        raise TopologyToolError("Connect Edges benötigt mindestens 2 Edges.")

    mesh = scene.mesh
    before = mesh.export_state()

    # Phase 1 - Analyze/Validate: Auswahl pruefen (read-only, Mesh bleibt unveraendert).
    for eid in selected:
        if not mesh.is_valid_edge(eid):
            raise TopologyToolError(f"Unbekannte Edge: {eid!r}")
        faces = mesh.edge_faces(eid)
        if len(faces) == 0:
            raise TopologyToolError(
                "Freie Edge ohne Faces liegt außerhalb des Connect-Edges-Scope."
            )
        if len(faces) > 2:
            raise TopologyToolError(
                "Non-Manifold-Topologie liegt außerhalb des Connect-Edges-Scope."
            )
        for fid in faces:
            if len(mesh.face_vertices(fid)) != 4:
                raise TopologyToolError(
                    "Nicht-Quadrat-Faces liegen außerhalb des Connect-Edges-Scope."
                )

    # Phase 2 - Plan: vollstaendiger, deterministischer Operationsplan.
    # Dry-Run auf einem Clone beweist jede Connection VOR der Mutation.
    steps = _plan_for_selected(mesh, selected)
    _validate_plan_on_clone(before, steps)

    # Phase 3 - Apply/Commit: Plan auf dem echten Mesh ausfuehren; bei jedem
    # Konstruktionsfehler wird der exakte Vorher-Zustand wiederhergestellt.
    try:
        created = _execute_plan(mesh, steps)
    except Exception as exc:
        mesh.load_state(before)
        raise TopologyToolError(
            f"Connect Edges fehlgeschlagen – Mesh unverändert: {exc}"
        ) from exc

    _push_snapshot(scene, before, "Connect Edges", on_restore)
    return created


def collapse_selected_edges(scene, edge_ids, *, on_restore=None):
    """Experimentelles Multi-Collapse für 2+ ausgewählte Edges."""
    if len(edge_ids) < 2:
        raise TopologyToolError("Collapse Edges benötigt mindestens 2 Edges.")

    mesh = scene.mesh
    before = mesh.export_state()
    survivors = []

    for eid in sorted(edge_ids, key=int):
        if not mesh.is_valid_edge(eid):
            continue
        survivors.append(mesh.collapse_edge(eid))

    if not survivors:
        raise TopologyToolError("Keine gültige Edge konnte kollabiert werden.")

    _push_snapshot(scene, before, "Collapse Edges", on_restore)
    return survivors


def collapse_selected_vertices(scene, vertex_ids, *, on_restore=None):
    """Experimentelles Multi-Collapse für 2+ ausgewählte Vertices."""
    if len(vertex_ids) < 2:
        raise TopologyToolError("Collapse Vertices benötigt mindestens 2 Vertices.")

    mesh = scene.mesh
    active = set(vertex_ids)
    before = mesh.export_state()
    survivors = []

    while len(active) > 1:
        candidate = None
        for eid in mesh.all_edge_ids():
            va, vb = mesh.edge_vertices(eid)
            if va in active and vb in active:
                candidate = eid
                break
        if candidate is None:
            break
        survivor = mesh.collapse_edge(candidate)
        active = {v for v in active if mesh.is_valid_vertex(v)}
        active.add(survivor)
        survivors.append(survivor)

    if not survivors:
        raise TopologyToolError("Keine Edge zwischen den ausgewählten Vertices gefunden.")

    _push_snapshot(scene, before, "Collapse Vertices", on_restore)
    return survivors


def select_edge_loop(scene, start_edge):
    """Wählt alle Edges eines Edge Loop aus (reine Selection, keine Mutation).

    Ausgehend von `start_edge` wird `edge_loop()` aufgerufen. Die resultierende
    Kantenmenge wird in `scene.selection` übernommen (Mode wird auf EDGE gesetzt).
    """
    mesh = scene.mesh
    if not mesh.is_valid_edge(start_edge):
        raise TopologyToolError(f"Unbekannte Edge: {start_edge!r}")
    try:
        traversal = edge_loop(mesh, start_edge)
    except LoopRingError as e:
        raise TopologyToolError(f"Edge Loop konnte nicht durchlaufen werden: {e}")
    return traversal.as_set(), traversal.closed


def select_edge_ring(scene, start_edge):
    """Wählt alle Edges eines Edge Ring aus (reine Selection, keine Mutation).

    Ausgehend von `start_edge` wird `edge_ring()` aufgerufen. Die resultierende
    Kantenmenge wird in `scene.selection` übernommen (Mode wird auf EDGE gesetzt).
    """
    mesh = scene.mesh
    if not mesh.is_valid_edge(start_edge):
        raise TopologyToolError(f"Unbekannte Edge: {start_edge!r}")
    try:
        traversal = edge_ring(mesh, start_edge)
    except LoopRingError as e:
        raise TopologyToolError(f"Edge Ring konnte nicht durchlaufen werden: {e}")
    return traversal.as_set(), traversal.closed
