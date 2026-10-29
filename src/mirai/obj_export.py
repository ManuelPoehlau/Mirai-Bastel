"""OBJ writer for the SPACE menu export (`Application.export_obj`): positions, face boundaries and,
when the mesh has them, the face-corner UVs (AD-026).

Counterpart of `examples/loaders/obj_loader.py` (no normals, polygons kept as they are). Vertex
order is the mesh's vertex-id order, so a re-import keeps it. UVs are written as `vt` records, one
per distinct (u, v) value in first-use order, so a corner shared by faces without a seam stays one
`vt` (what ZBrush and Blender expect); a face without UVs is written as `f v ...` alone.
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
    if not mesh.has_face_uvs():
        for face_id in mesh.all_face_ids():
            lines.append("f " + " ".join(str(index[v]) for v in mesh.face_vertices(face_id)))
        return "\n".join(lines) + "\n"
    uv_index: dict[tuple[float, float], int] = {}
    face_lines = []
    for face_id in mesh.all_face_ids():
        uvs = mesh.face_uvs(face_id)
        boundary = mesh.face_vertices(face_id)
        if uvs is None:
            face_lines.append("f " + " ".join(str(index[v]) for v in boundary))
            continue
        tokens = []
        for v, uv in zip(boundary, uvs):
            t = uv_index.get(uv)
            if t is None:
                t = uv_index[uv] = len(uv_index) + 1
                lines.append(f"vt {uv[0]:.9g} {uv[1]:.9g}")
            tokens.append(f"{index[v]}/{t}")
        face_lines.append("f " + " ".join(tokens))
    return "\n".join(lines + face_lines) + "\n"
