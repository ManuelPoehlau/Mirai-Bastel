"""Object-level mirror pairs: the pure maths (OBJECT_MIRROR_SYMMETRY_PROPOSAL §3, §5.3, §5.6).

World plane `n·x = d`, `H = I - 2nnᵀ`. A pair couples two placements by
`F: (t, R, s, c) -> (H t + 2d n, H R H, s, H c)`, an involution, so either object can drive. The
reflection itself lives in the partner's *mesh* (`mirror_mesh`: positions `H p`, face winding
reversed); every transform stays a proper rotation with `scale > 0` (AD-021 Q-4).

For an axis-aligned plane `H` only flips signs, so through the origin (`d = 0`) the partner is the
bit-exact mirror image (`to_world(B, H p) == H to_world(A, p)`); an offset plane is exact to float
rounding (§3). No Application, no Scene mutation: the commands are in `scene_objects`.
"""

from __future__ import annotations

from core import Mesh, MirrorPair, ObjectTransform, SceneObject

from .scene_factory import mesh_from_positions_and_faces

Vec3 = tuple[float, float, float]

#: PROVISIONAL (proposal §9 decision 7, agent default): the planes offered in v1 - the three world
#: axis planes through the origin. `MirrorPair` itself stores any unit normal and offset.
PLANES: dict[str, tuple[Vec3, float]] = {
    "X": ((1.0, 0.0, 0.0), 0.0),
    "Y": ((0.0, 1.0, 0.0), 0.0),
    "Z": ((0.0, 0.0, 1.0), 0.0),
}

#: PROVISIONAL: the largest placement difference (`pair_residual`) at which a pair still counts as
#: in sync. A pair driven by the gesture is exact (`d = 0`) or off by float rounding (1e-15).
SYNC_TOLERANCE = 1e-9


def reflection_matrix(normal: Vec3):
    """`H = I - 2nnᵀ`; for an axis normal its entries are exactly 0 and ±1."""
    return tuple(
        tuple((1.0 if i == j else 0.0) - 2.0 * normal[i] * normal[j] for j in range(3)) for i in range(3)
    )


def _apply(h, v: Vec3) -> Vec3:
    return tuple(h[i][0] * v[0] + h[i][1] * v[1] + h[i][2] * v[2] for i in range(3))  # type: ignore[return-value]


def _matmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def reflect_point(normal: Vec3, offset: float, p: Vec3) -> Vec3:
    """`S(p) = H p + 2d n`, the world reflection."""
    hp = _apply(reflection_matrix(normal), p)
    return tuple(hp[i] + 2.0 * offset * normal[i] for i in range(3))  # type: ignore[return-value]


def plane_label(normal: Vec3, offset: float) -> str:
    """`X = 0` for an axis plane, else the plane equation (status lines)."""
    for name, (axis, _) in PLANES.items():
        if tuple(normal) == axis:
            return f"{name} = {offset:g}"
    return f"n·x = {offset:g} (n = {tuple(round(v, 4) for v in normal)})"


def mirror_transform(transform: ObjectTransform, normal: Vec3, offset: float) -> ObjectTransform:
    """The partner's `ObjectTransform`: `t' = H t + 2d n`, `R' = H R H`, `s' = s`. Stateless: the
    gesture calls it on the driver's current transform after every step, nothing accumulates."""
    h = reflection_matrix(normal)
    return ObjectTransform(
        translation=reflect_point(normal, offset, transform.translation),
        rotation=_matmul(_matmul(h, transform.rotation), h),
        scale=transform.scale,
    )


def mirror_pivot(pivot: Vec3, normal: Vec3) -> Vec3:
    """The partner's pivot `c' = H c` (object space: no plane offset)."""
    return _apply(reflection_matrix(normal), pivot)


def mirror_placement(obj: SceneObject, normal: Vec3, offset: float) -> tuple[ObjectTransform, Vec3]:
    """`F(obj)`: the transform and pivot a partner of `obj` has across the plane."""
    return mirror_transform(obj.transform, normal, offset), mirror_pivot(obj.pivot, normal)


def mirror_mesh(mesh: Mesh, normal: Vec3) -> Mesh:
    """A new, independent mesh with every position reflected about the object origin (`H p`) and
    every face's winding reversed, so outward stays outward. Built through the public Mesh API
    (`mesh_from_positions_and_faces`, `add_edge` for loose edges) with fresh dense ids and **no**
    symmetry definition (the copy's ids are its own; Shift+S is per mesh, proposal §5.2).

    Point layers (AD-025 §4.3 Phase 5: a frame change of a new mesh): every layer is copied in order,
    with its name and rule, through the same index map; a vector value maps like a position, `v -> H v`
    (bit-exact mirror for an axis plane: H holds only 0 and ±1)."""
    h = reflection_matrix(normal)
    vertex_ids = sorted(mesh.all_vertex_ids())
    index = {vid: i for i, vid in enumerate(vertex_ids)}
    positions = [_apply(h, mesh.vertex_position(vid)) for vid in vertex_ids]
    faces = []
    for fid in sorted(mesh.all_face_ids()):
        boundary = [index[vid] for vid in mesh.face_vertices(fid)]
        faces.append([boundary[0]] + boundary[:0:-1])
    mirrored = mesh_from_positions_and_faces(positions, faces)
    new_ids = sorted(mirrored.all_vertex_ids())
    for eid in sorted(mesh.all_edge_ids()):
        if not mesh.edge_faces(eid):
            a, b = mesh.edge_vertices(eid)
            mirrored.add_edge(new_ids[index[a]], new_ids[index[b]])
    for lid in mesh.point_layer_ids():
        new_lid = mirrored.add_point_layer(mesh.point_layer_info(lid))
        for vid, value in mesh.layer_items(lid):
            mirrored.set_layer_value(new_lid, new_ids[index[vid]], _apply(h, value))
    return mirrored


def pair_residual(a: SceneObject, b: SceneObject, pair: MirrorPair) -> float:
    """How far `b`'s placement is from `F(a)`: the largest absolute difference over translation,
    rotation entries, scale and pivot. 0.0 for an exact pair; compared with `SYNC_TOLERANCE`."""
    transform, pivot = mirror_placement(a, pair.normal, pair.offset)
    actual = b.transform
    diffs = [abs(x - y) for x, y in zip(transform.translation, actual.translation)]
    diffs += [abs(x - y) for row, other in zip(transform.rotation, actual.rotation) for x, y in zip(row, other)]
    diffs.append(abs(transform.scale - actual.scale))
    diffs += [abs(x - y) for x, y in zip(pivot, b.pivot)]
    return max(diffs)


def in_sync(a: SceneObject, b: SceneObject, pair: MirrorPair) -> bool:
    return pair_residual(a, b, pair) <= SYNC_TOLERANCE
