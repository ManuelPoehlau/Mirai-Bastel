"""Small meshes and a helper context for the Soft Selection tests (WP-SOFT-01 S2a).

Same fixtures as `experiments/soft_selection/tests/_fixtures.py` (S1), rebuilt for
`tests/`: the S1 suite stays where it is, as the record, and is not imported from here.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import tests._bootstrap  # noqa: F401

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from core import HistoryStack, Mesh, OperationContext, Selection, SelectionMode, VertexId  # noqa: E402
from mirai.interaction.tools.selection_helpers import (  # noqa: E402
    _VertexSelectionView,
    resolve_selection_vertices,
)
from mirai.scene_factory import (  # noqa: E402
    build_core_scene_from_obj,
    mesh_from_positions_and_faces,
)
from mirai.soft_selection import compute_influence, primary_pivot  # noqa: E402

HEAD_OBJ = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"


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
    return build_core_scene_from_obj(HEAD_OBJ).mesh.export_state()


def head() -> Mesh:
    """A fresh copy of the head asset (parsed once per test run)."""
    return Mesh.from_state(_head_state())


def soft_context(
    mesh: Mesh,
    selection: Selection,
    history: HistoryStack,
    radius: float,
    metric: str = "euclidean",
    curve: str = "smooth",
    mode: SelectionMode | None = None,
    **params,
) -> OperationContext:
    """What the tools do at `begin()`: seeds from the selection, influence computed now
    (from the current = start positions), pivot from the seeds, the op sees a view of the
    influenced set. The caller's `selection` is only read."""
    seeds = resolve_selection_vertices(mesh, selection, selection.mode if mode is None else mode)
    influence = compute_influence(mesh, seeds, radius, metric=metric, curve=curve)
    full = {"influence": influence}
    if seeds:
        full["pivot"] = primary_pivot(mesh, seeds)
    full.update(params)
    return OperationContext(
        target=mesh,
        selection=_VertexSelectionView(set(influence)),
        history=history,
        params=full,
    )
