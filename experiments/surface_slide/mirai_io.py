"""Read-only bridge to the repository's assets: Mirai scenes (`core.serialization`) and OBJ files -> index arrays.

The only module of the prototype that imports from `src/` (the Core's public query API) and `examples/loaders`. It
never writes a mesh or a file.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
for _p in (REPO / "src", REPO / "examples"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

GOLLUM_CAGE = REPO / "scenes" / "Gollum_Head_01.mirai.json"
GOLLUM_HIRES = REPO / "examples" / "meshes" / "gollum.obj"
GOLLUM_87K = REPO / "experiments" / "drag_cost" / "fixtures" / "gollum_87k.obj"


@dataclass
class MeshArrays:
    name: str
    V: np.ndarray
    faces: list
    #: declared symmetry: (plane_point, plane_normal) or None, and the vertices on declared seam edges
    plane: tuple | None = None
    seam_vertices: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.intp))
    seam_edges: np.ndarray = field(default_factory=lambda: np.zeros((0, 2), dtype=np.intp))


def load_scene(path: Path) -> MeshArrays:
    """The edit mesh of a `.mirai.json` scene: positions, polygons and the declared symmetry (AD-SYM-01)."""
    from core.serialization import scene_from_json

    scene = scene_from_json(Path(path).read_text(encoding="utf-8"))
    mesh = scene.mesh
    vids = list(mesh.all_vertex_ids())
    index = {v: i for i, v in enumerate(vids)}
    V = np.array([mesh.vertex_position(v) for v in vids], dtype=np.float64)
    faces = [tuple(index[v] for v in mesh.face_vertices(f)) for f in mesh.all_face_ids()]
    plane = None
    seam_v: set[int] = set()
    seam_e: list[tuple[int, int]] = []
    definition = mesh.symmetry_definition
    if definition is not None:
        plane = (tuple(definition.plane_point), tuple(definition.plane_normal))
        for e in definition.seam_edges:
            if mesh.is_valid_edge(e):
                a, b = mesh.edge_vertices(e)
                seam_v.update((index[a], index[b]))
                seam_e.append((index[a], index[b]))
    return MeshArrays(Path(path).stem, V, faces, plane, np.array(sorted(seam_v), dtype=np.intp),
                      np.array(seam_e, dtype=np.intp).reshape(-1, 2))


def load_obj_arrays(path: Path) -> MeshArrays:
    from loaders.obj_loader import load_obj

    data = load_obj(path)
    return MeshArrays(Path(path).stem, np.array(data.vertices, dtype=np.float64), [tuple(f) for f in data.faces])


def gollum_cage() -> MeshArrays:
    return load_scene(GOLLUM_CAGE)


def gollum_hires() -> MeshArrays:
    return load_obj_arrays(GOLLUM_HIRES)


def gollum_87k() -> MeshArrays:
    return load_obj_arrays(GOLLUM_87K)
