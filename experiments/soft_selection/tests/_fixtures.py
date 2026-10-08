"""Small meshes for the Soft Selection tests (built through the public Core API)."""

from __future__ import annotations

from functools import lru_cache

from core import Mesh, VertexId
from loaders.assets import asset_path
from mirai.scene_factory import build_core_scene_from_obj, mesh_from_positions_and_faces


def grid(n: int = 9, spacing: float = 1.0) -> tuple[Mesh, list[list[VertexId]]]:
    """n x n vertices in the XY plane (z = 0), quads; returns the mesh and ids[row][col]."""
    positions = [(c * spacing, r * spacing, 0.0) for r in range(n) for c in range(n)]
    faces = [
        (r * n + c, r * n + c + 1, (r + 1) * n + c + 1, (r + 1) * n + c)
        for r in range(n - 1)
        for c in range(n - 1)
    ]
    mesh = mesh_from_positions_and_faces(positions, faces)
    ids = mesh.all_vertex_ids()
    return mesh, [[ids[r * n + c] for c in range(n)] for r in range(n)]


#: Lip fixture geometry: half the gap between the two sheets, sheet length.
LIP_HALF_GAP = 0.05
LIP_LENGTH = 4


def lip() -> tuple[Mesh, VertexId, VertexId]:
    """Two sheets 0.1 apart in z, joined only at x = LIP_LENGTH (a folded strip, like
    upper and lower lip meeting at the mouth corner). Returns (mesh, upper, lower):
    `upper` sits on the upper sheet at x = 0, `lower` directly beneath it.
    Euclidean distance upper-lower = 0.1, edge-path distance = 2 * LIP_LENGTH + 0.1."""
    xs = list(range(LIP_LENGTH + 1))
    profile = [(x, LIP_HALF_GAP) for x in xs] + [(x, -LIP_HALF_GAP) for x in reversed(xs)]
    rows = 3
    positions = [(float(x), float(y), z) for y in range(rows) for (x, z) in profile]
    n = len(profile)
    faces = [
        (y * n + i, y * n + i + 1, (y + 1) * n + i + 1, (y + 1) * n + i)
        for y in range(rows - 1)
        for i in range(n - 1)
    ]
    mesh = mesh_from_positions_and_faces(positions, faces)
    ids = mesh.all_vertex_ids()
    middle = 1 * n  # row y = 1
    return mesh, ids[middle + 0], ids[middle + n - 1]


@lru_cache(maxsize=None)
def _head_state() -> dict:
    return build_core_scene_from_obj(asset_path("head_basemesh")).mesh.export_state()


def head() -> Mesh:
    """A fresh copy of the head asset (parsed once per test run)."""
    return Mesh.from_state(_head_state())
