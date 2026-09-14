"""Connect Edges — topology-aware (Enablement-Port, AP-05).

1:1-Logik-Port aus experiments/mirai_bastel_viewport_V1/viewport/topology_tools.py
(Zeilen ~160-477) gegen Production-src/core. Adapter-Muster analog zu
topology_ops.py::split_selected_edge (Enablement-01).

Zwei Verbindungsarten:
  "kind f" — gegenüberliegende Kanten in einer gemeinsamen Quad-Face →
             connect_vertices() spaltet die Face.
  "kind v" — Kette über einen gemeinsamen regulären Innen-Vertex ohne
             gemeinsame Face → mesh.add_edge() erzeugt eine freie Kante
             zwischen den Mittelpunkten (erfordert src/core.add_edge(),
             seit AP-05-Core-Erweiterung verfügbar).
"""

from __future__ import annotations

from dataclasses import dataclass

from core import EdgeId, FaceId, Mesh
from core.operations.topology import MeshStateCommand


class TopologyToolError(ValueError):
    pass


@dataclass(frozen=True)
class _SplitStep:
    edge_id: EdgeId


@dataclass(frozen=True)
class _FaceConnectStep:
    face_id: FaceId
    edge_a: EdgeId
    edge_b: EdgeId


@dataclass(frozen=True)
class _FreeConnectStep:
    edge_a: EdgeId
    edge_b: EdgeId


def _edge_midpoint(mesh, edge_id) -> tuple:
    v0, v1 = mesh.edge_vertices(edge_id)
    p0, p1 = mesh.vertex_position(v0), mesh.vertex_position(v1)
    return tuple((a + b) / 2.0 for a, b in zip(p0, p1))


def _shared_vertex(mesh, edge_a, edge_b):
    v0a, v1a = mesh.edge_vertices(edge_a)
    v0b, v1b = mesh.edge_vertices(edge_b)
    common = {v0a, v1a} & {v0b, v1b}
    if len(common) == 1:
        return next(iter(common))
    return None


def _is_regular_interior_vertex(mesh, vertex_id) -> bool:
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
    for fid in set(mesh.edge_faces(edge_a)) & set(mesh.edge_faces(edge_b)):
        edges = mesh.face_edges(fid)
        if len(edges) != 4:
            continue
        ia, ib = edges.index(edge_a), edges.index(edge_b)
        if (ia - ib) % 4 == 2:
            return fid
    return None


def _build_adjacency(mesh, selected: set) -> dict:
    """Nachbar-Graph der Auswahl.

    Zwei Kanten sind benachbart, wenn sie:
    - in einer gemeinsamen Quad-Face gegenüberliegen (kind "f"), oder
    - denselben regulären Innen-Vertex teilen ohne gemeinsame Face (kind "v").
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


def _order_component_edges(mesh, adjacency: dict, comp: list) -> tuple[list, bool]:
    """Kanonische, deterministische Reihenfolge einer Kette/eines Rings."""
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


def _connection_step(adjacency: dict, edge_a, edge_b):
    kind, payload = adjacency[edge_a][edge_b]
    if kind == "f":
        return _FaceConnectStep(face_id=payload, edge_a=edge_a, edge_b=edge_b)
    if kind == "v":
        return _FreeConnectStep(edge_a=edge_a, edge_b=edge_b)
    raise TopologyToolError("Interner Fehler: unbekannte Verbindungsart.")


def _plan_for_selected(mesh, selected: set) -> list:
    adjacency = _build_adjacency(mesh, selected)

    seen: set = set()
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


def _execute_plan(mesh, steps: list) -> list:
    created = []
    midpoints: dict = {}
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
        else:
            raise TopologyToolError(
                f"Interner Fehler: unbekannter Plan-Schritt {type(step).__name__!r}."
            )
    return created


def _validate_plan_on_clone(before_state: dict, steps: list) -> None:
    clone = Mesh.from_state(before_state)
    try:
        _execute_plan(clone, steps)
    except Exception as exc:
        raise TopologyToolError(
            f"Operationsplan nicht auf gültige Topologie abbildbar: {exc}"
        ) from exc


def connect_selected_edges(scene, edge_ids: set[EdgeId]) -> list[EdgeId]:
    """Connect Edges — topology-aware.

    Erzeugt neue Kanten zwischen den Mittelpunkten ausgewählter Edges.
    Pusht genau einen MeshStateCommand auf scene.history (analog zu
    topology_ops.py::split_selected_edge).

    Scope: reguläre kompatible Quad-Topologie (Ketten, Ringe).
    Wirft TopologyToolError bei jeder ungültigen Auswahl — Mesh bleibt
    dann exakt unverändert.
    """
    selected = set(edge_ids)
    if len(selected) < 2:
        raise TopologyToolError("Connect Edges benötigt mindestens 2 Edges.")

    mesh = scene.mesh
    before = mesh.export_state()

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

    steps = _plan_for_selected(mesh, selected)
    _validate_plan_on_clone(before, steps)

    try:
        created = _execute_plan(mesh, steps)
    except Exception as exc:
        mesh.load_state(before)
        raise TopologyToolError(
            f"Connect Edges fehlgeschlagen – Mesh unverändert: {exc}"
        ) from exc

    after = mesh.export_state()
    scene.history.push(
        MeshStateCommand(
            mesh=mesh,
            before_state=before,
            after_state=after,
            description="Connect Edges",
        )
    )
    return created
