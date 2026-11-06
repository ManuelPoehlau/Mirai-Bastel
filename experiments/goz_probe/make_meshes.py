"""Writes the E1 test meshes A, B, C (README §3) as `meshes/<id>.obj` plus `meshes/<id>.sent.json`.

All three go through Mirai's Core `Mesh` and Mirai's own OBJ writer (`mirai.obj_export.mesh_to_obj`, vertex-ID order,
world space = object space here), so the OBJ is exactly what Mirai's "OBJ exportieren" would write. The sidecar holds
the values sent (float64 positions, faces as dense 0-based indices in face-ID order, and the index <-> ID maps).
Deterministic: two runs write identical bytes. Reads `src/` and `examples/` only.

    python -I experiments/goz_probe/make_meshes.py [--out DIR]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from goz_probe._paths import EXAMPLES_DIR, ensure_paths  # noqa: E402

ensure_paths()

import argparse  # noqa: E402

from core import Mesh  # noqa: E402

from goz_probe.probe_common import DEFAULT_MESHES, write_json_atomic, write_text_atomic  # noqa: E402

#: Mesh A, the axis tripod: (min corner, max corner) of the three boxes - arm X, arm Y, arm Z (README §3).
TRIPOD_BOXES = (
    ((0.20, 0.10, 0.05), (1.20, 0.20, 0.15)),
    ((0.20, 0.25, 0.05), (0.30, 0.85, 0.15)),
    ((0.20, 0.10, 0.20), (0.30, 0.20, 0.50)),
)
#: Box corners are indexed 4·xi + 2·yi + zi (xi, yi, zi in {0 = min, 1 = max}); faces wound counter-clockwise seen from
#: outside: -X, +X, -Y, +Y, -Z, +Z.
BOX_FACES = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))

MESH_NAMES = {"A": "E1_A_tripod", "B": "E1_B_mirai_sphere", "C": "E1_C_head"}


def tripod_mesh() -> Mesh:
    mesh = Mesh()
    for lo, hi in TRIPOD_BOXES:
        ids = [
            mesh.add_vertex((hi[0] if xi else lo[0], hi[1] if yi else lo[1], hi[2] if zi else lo[2]))
            for xi in (0, 1) for yi in (0, 1) for zi in (0, 1)
        ]
        for face in BOX_FACES:
            mesh.add_face([ids[i] for i in face])
    return mesh


def mirai_sphere_mesh() -> Mesh:
    """Mirai's `sphere` primitive with the four quads around one vertex deleted (`Mesh.delete_faces`): that vertex and
    its edges go too, so vertex and face IDs have gaps, as in a mesh edited in Mirai. The vertex: the one with the
    smallest |y|, then the largest x, then the smallest id, among those with exactly four faces, all quads."""
    from mirai.scene_factory import PRIMITIVES

    mesh = PRIMITIVES["sphere"]()
    faces_of: dict = {}
    for fid in mesh.all_face_ids():
        for vid in mesh.face_vertices(fid):
            faces_of.setdefault(vid, []).append(fid)
    candidates = [
        vid for vid, fids in faces_of.items() if len(fids) == 4 and all(len(mesh.face_vertices(f)) == 4 for f in fids)
    ]
    vid = min(candidates, key=lambda v: (abs(mesh.vertex_position(v)[1]), -mesh.vertex_position(v)[0], int(v)))
    mesh.delete_faces(sorted(faces_of[vid]))
    assert not mesh.is_valid_vertex(vid)
    return mesh


def head_mesh() -> Mesh:
    from loaders.obj_loader import load_obj
    from mirai.scene_factory import mesh_from_obj_data

    return mesh_from_obj_data(load_obj(EXAMPLES_DIR / "meshes" / "head_basemesh.obj"))


BUILDERS = {"A": tripod_mesh, "B": mirai_sphere_mesh, "C": head_mesh}


def bump_offsets(positions) -> list[list[float]]:
    """E3 (morph target): a deterministic bump around the point with the largest z (Mirai frame): offset along +z of
    0.15 x extent x w^2, w = 1 - distance / (0.3 x extent), zero outside."""
    extent = max(max(p[c] for p in positions) - min(p[c] for p in positions) for c in range(3))
    tip = max(positions, key=lambda p: (p[2], p[1], p[0]))
    radius = 0.3 * extent
    out = []
    for p in positions:
        w = max(0.0, 1.0 - sum((a - b) ** 2 for a, b in zip(p, tip)) ** 0.5 / radius)
        out.append([0.0, 0.0, 0.15 * extent * w * w])
    return out


def sidecar(mesh_id: str, mesh: Mesh) -> dict:
    vertex_ids = mesh.all_vertex_ids()
    index = {vid: i for i, vid in enumerate(vertex_ids)}
    face_ids = mesh.all_face_ids()
    extra: dict = {}
    if mesh.has_face_uvs():  # E3: the corner UVs as Mirai holds them (= the OBJ's vt), None for a face without
        extra["uvs"] = [None if mesh.face_uvs(f) is None else [list(uv) for uv in mesh.face_uvs(f)] for f in face_ids]
    if mesh_id == "C":
        extra["target_bump"] = bump_offsets([mesh.vertex_position(v) for v in vertex_ids])
    return {
        **extra,
        "id": mesh_id,
        "name": MESH_NAMES[mesh_id],
        "positions": [list(mesh.vertex_position(v)) for v in vertex_ids],
        "faces": [[index[v] for v in mesh.face_vertices(f)] for f in face_ids],
        "vertex_ids": [int(v) for v in vertex_ids],
        "face_ids": [int(f) for f in face_ids],
        "note": "positions in Mirai's frame (Y up), float64; GoZ files carry them as float32",
    }


def write_meshes(out: Path, ids=("A", "B", "C")) -> list[Path]:
    from mirai.obj_export import mesh_to_obj

    written = []
    for mesh_id in ids:
        mesh = BUILDERS[mesh_id]()
        name = MESH_NAMES[mesh_id]
        obj = out / f"{mesh_id}.obj"
        write_text_atomic(obj, mesh_to_obj(mesh, name))
        car = sidecar(mesh_id, mesh)
        write_json_atomic(out / f"{mesh_id}.sent.json", car)
        written.append(obj)
        if "target_bump" in car:  # E3: the target shape as Mirai's OBJ export would write it (for a ZBrush layer import)
            for vid, d in zip(mesh.all_vertex_ids(), car["target_bump"]):
                p = mesh.vertex_position(vid)
                mesh.set_vertex_position(vid, (p[0] + d[0], p[1] + d[1], p[2] + d[2]))
            write_text_atomic(out / f"{mesh_id}_bump.obj", mesh_to_obj(mesh, name + "_bump"))
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_MESHES)
    args = parser.parse_args(argv)
    for path in write_meshes(args.out):
        print(f"wrote {path} (+ {path.stem}.sent.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
