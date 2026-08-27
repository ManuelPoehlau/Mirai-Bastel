"""Experimentelle Topologie-Werkzeuge für den V1-Viewport."""

from __future__ import annotations


class TopologyToolError(ValueError):
    pass


class _SnapshotCommand:
    """Experimenteller History-Adapter über Mesh export/load_state."""

    def __init__(self, mesh, before: dict, after: dict, description: str, on_restore=None):
        self._mesh = mesh
        self._before = before
        self._after = after
        self.description = description
        self._on_restore = on_restore

    def undo(self) -> None:
        self._mesh.load_state(self._before)
        if self._on_restore:
            self._on_restore()

    def redo(self) -> None:
        self._mesh.load_state(self._after)
        if self._on_restore:
            self._on_restore()


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


def connect_selected_edges(scene, edge_ids, *, on_restore=None):
    """Experimentelles Connect Edges für 2+ Edges."""
    if len(edge_ids) < 2:
        raise TopologyToolError("Connect Edges benötigt mindestens 2 Edges.")

    mesh = scene.mesh
    selected = sorted(edge_ids, key=int)
    before = mesh.export_state()
    midpoints = []

    for eid in selected:
        if not mesh.is_valid_edge(eid):
            continue
        mid, _, _ = mesh.split_edge(eid)
        midpoints.append(mid)

    if len(midpoints) < 2:
        raise TopologyToolError("Weniger als 2 gültige Edges konnten verarbeitet werden.")

    created = []
    for v_a, v_b in zip(midpoints, midpoints[1:]):
        face_id = _common_face_for_vertices(mesh, (v_a, v_b))
        if face_id is None:
            if not created:
                raise TopologyToolError("Die erzeugten Edge-Mittelpunkte benötigen eine gemeinsame Face.")
            break
        edge_id, _, _ = mesh.connect_vertices(face_id, v_a, v_b)
        created.append(edge_id)

    if not created:
        raise TopologyToolError("Keine neue Verbindung zwischen den Edge-Mittelpunkten möglich.")

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
