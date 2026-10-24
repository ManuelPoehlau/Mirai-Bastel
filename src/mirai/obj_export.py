"""OBJ writer for the SPACE menu export (`Application.export_obj`): positions and face boundaries only.

Counterpart of `examples/loaders/obj_loader.py` (no UVs / normals, polygons kept as they are). Vertex
order is the mesh's vertex-id order, so a re-import keeps it.
"""

from __future__ import annotations

from typing import Callable

from core import Mesh

Position = tuple[float, float, float]


def mesh_to_obj(mesh: Mesh, name: str, transform: Callable[[Position], Position] | None = None) -> str:
    index = {}
    lines = [f"o {name.replace(' ', '_') or 'object'}"]
    for vertex_id in mesh.all_vertex_ids():
        index[vertex_id] = len(index) + 1
        x, y, z = mesh.vertex_position(vertex_id)
        if transform is not None:
            x, y, z = transform((x, y, z))
        lines.append(f"v {x:.9g} {y:.9g} {z:.9g}")
    for face_id in mesh.all_face_ids():
        lines.append("f " + " ".join(str(index[v]) for v in mesh.face_vertices(face_id)))
    return "\n".join(lines) + "\n"
