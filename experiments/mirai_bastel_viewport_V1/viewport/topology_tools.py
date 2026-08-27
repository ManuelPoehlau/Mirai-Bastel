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
    if len(vertex_ids) != 2:
        raise TopologyToolError("Connect Vertices benötigt genau 2 ausgewählte Vertices.")

    v_a, v_b = tuple(vertex_ids)
    mesh = scene.mesh
    if v_a == v_b:
        raise TopologyToolError("Connect Vertices benötigt zwei verschiedene Vertices.")

    face_id = _common_face_for_vertices(mesh, (v_a, v_b))
    if face_id is None:
        raise TopologyToolError("Die beiden Vertices müssen auf einer gemeinsamen Face liegen.")

    if any(set(mesh.edge_vertices(eid)) == {v_a, v_b} for eid in mesh.all_edge_ids()):
        raise TopologyToolError("Zwischen den beiden Vertices existiert bereits eine Edge.")

    before = mesh.export_state()
    result = mesh.connect_vertices(face_id, v_a, v_b)
    _push_snapshot(scene, before, "Connect Vertices", on_restore)
    return result


def connect_selected_edges(scene, edge_ids, *, on_restore=None):
    """Connect Edges für zwei Edges auf einer gemeinsamen Face.

    Die vorhandenen Core-Primitives werden bewusst kombiniert: beide Edges
    werden am Mittelpunkt geteilt, anschließend werden die beiden neuen
    Vertices innerhalb der gemeinsamen Face verbunden.
    """
    if len(edge_ids) != 2:
        raise TopologyToolError("Connect Edges benötigt genau 2 ausgewählte Edges.")

    first, second = tuple(edge_ids)
    mesh = scene.mesh
    if first == second:
        raise TopologyToolError("Connect Edges benötigt zwei verschiedene Edges.")

    common_faces = set(mesh.edge_faces(first)) & set(mesh.edge_faces(second))
    if not common_faces:
        raise TopologyToolError("Die beiden Edges müssen eine gemeinsame Face haben.")

    face_id = next(iter(common_faces))
    before = mesh.export_state()

    midpoint_a, _, _ = mesh.split_edge(first)
    midpoint_b, _, _ = mesh.split_edge(second)
    mesh.connect_vertices(face_id, midpoint_a, midpoint_b)

    _push_snapshot(scene, before, "Connect Edges", on_restore)
    return midpoint_a, midpoint_b
