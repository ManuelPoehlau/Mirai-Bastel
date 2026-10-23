"""Transform orientation World / Normal in the app (WP Toolbox Gaps C1, AD-012 "Normal in App").

The orientation decides what the axis constraints mean: in World, X/Y/Z (and the planes) are the world
axes; in Normal they are the frame of the selection, as in the Playground (`playground/gizmo.py::
gizmo_mode`). One selected face has a full frame (X = first edge of the face, Y = normal × X, Z = the
face normal, `_face_tangent_basis`); every other selection has only its averaged normal (Z). No
constraint stays free in both orientations (`PROVISIONAL`; the Playground moved along the normal there).

The frame is derived from the mesh as it is now (`SelectionNormals`), not from the viewport's derived
data, which follows only at the next draw: gizmo and gesture see the same, current frame. All vectors are
in the edit object's space; the gizmo maps them to world.
"""

from __future__ import annotations

from dataclasses import dataclass

from core import FaceId, Mesh, Selection, SelectionMode, VertexId
from viewport.derived import face_normal

from .interaction.tools.selection_helpers import selection_normal
from .interaction.tools.transform import _face_tangent_basis

WORLD = "world"
NORMAL = "normal"

Vec3 = tuple[float, float, float]

#: Constraints that need the tangents (a single selected face) in Normal space.
_TANGENT_CONSTRAINTS = frozenset({"x", "y", "xy", "yz", "xz"})


class SelectionNormals:
    """The part of `viewport.derived.DerivedGeometry` that `selection_normal` and `_face_tangent_basis`
    read (`face_normals`, `vertex_normals`, `vertex_to_faces`), computed now for the faces around the
    selection only."""

    def __init__(self, mesh: Mesh, selection: Selection) -> None:
        vertices: set[VertexId] = set(selection.vertices)
        for eid in selection.edges:
            vertices.update(mesh.edge_vertices(eid))
        faces: set[FaceId] = set(selection.faces)
        self.vertex_to_faces: dict[VertexId, set[FaceId]] = {}
        for vid in vertices:
            around = {f for e in mesh.vertex_edges(vid) for f in mesh.edge_faces(e)}
            self.vertex_to_faces[vid] = around
            faces |= around
        positions = {v: mesh.vertex_position(v) for f in faces for v in mesh.face_vertices(f)}
        self.face_normals: dict[FaceId, Vec3] = {
            f: face_normal(positions, mesh.face_vertices(f)) for f in faces
        }
        self.vertex_normals: dict[VertexId, Vec3] = {}
        for vid, around in self.vertex_to_faces.items():
            acc = (0.0, 0.0, 0.0)
            for f in around:
                n = self.face_normals[f]
                acc = (acc[0] + n[0], acc[1] + n[1], acc[2] + n[2])
            length = (acc[0] ** 2 + acc[1] ** 2 + acc[2] ** 2) ** 0.5
            self.vertex_normals[vid] = (0.0, 0.0, 0.0) if length < 1e-12 else (
                acc[0] / length, acc[1] / length, acc[2] / length
            )


@dataclass(frozen=True)
class NormalFrame:
    """The selection's frame: `normal` always, the tangents only for one selected face."""

    normal: Vec3
    tangent_x: Vec3 | None = None
    tangent_y: Vec3 | None = None

    @property
    def full(self) -> bool:
        return self.tangent_x is not None

    def axes(self) -> list[tuple[str, Vec3]]:
        """Gizmo axes `(name, direction)`, named like the world axes so a handle is a constraint."""
        if not self.full:
            return [("z", self.normal)]
        return [("x", self.tangent_x), ("y", self.tangent_y), ("z", self.normal)]

    def planes(self) -> list[tuple[str, Vec3, Vec3]]:
        if not self.full:
            return []
        return [
            ("xy", self.tangent_x, self.tangent_y),
            ("yz", self.tangent_y, self.normal),
            ("xz", self.tangent_x, self.normal),
        ]


def normal_frame(mesh: Mesh, selection: Selection, normals: SelectionNormals | None = None) -> NormalFrame | None:
    """The frame of the component selection, None when it has no usable normal (empty, mode `4`, or the
    normals cancel out)."""
    if selection.mode is SelectionMode.OBJECT:
        return None
    normals = normals or SelectionNormals(mesh, selection)
    normal = selection_normal(normals, mesh, selection, selection.mode)
    if normal == (0.0, 0.0, 0.0):
        return None
    if selection.mode is SelectionMode.FACE and len(selection.faces) == 1:
        try:
            n, tx, ty = _face_tangent_basis(mesh, selection, normals)
        except ValueError:
            return NormalFrame(normal)
        return NormalFrame(n, tx, ty)
    return NormalFrame(normal)


def normal_refusal(frame: NormalFrame | None, constraint: str, *, scale: bool) -> str | None:
    """Why a Normal-space gesture with `constraint` cannot begin, None when it can. Scale's tool needs
    the full frame for every axis (`ScaleTool`, AD-012 amendment)."""
    if frame is None:
        return "the selection has no normal"
    if frame.full:
        return None
    if scale:
        return "Scale along an axis in Normal space needs exactly one selected face"
    if constraint in _TANGENT_CONSTRAINTS:
        return f"{_label(constraint)} in Normal space needs exactly one selected face (Z = normal works for any selection)"
    return None


def _label(constraint: str) -> str:
    return constraint.upper() if len(constraint) == 1 else f"{constraint.upper()} plane"
