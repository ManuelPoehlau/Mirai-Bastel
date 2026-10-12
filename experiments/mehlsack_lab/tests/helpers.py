"""Shared test helpers (no GL)."""

from __future__ import annotations

from mehlsack_lab.box import BoxParams, build_box_mesh
from mehlsack_lab.targets import TargetFinder


def positions(mesh) -> dict:
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def box(h: int = 4, n: int = 3, height: float = 2.0, width: float = 2.0):
    return build_box_mesh(BoxParams(height=height, width=width, h=h, n=n))


def horizontal_edge(mesh, y: float, tol: float = 1e-9):
    """An edge whose two ends both lie at height `y` and differ in x (a wall edge of the
    horizontal row at `y`, not on a box corner column)."""
    for eid in mesh.all_edge_ids():
        a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
        if abs(a[1] - y) < tol and abs(b[1] - y) < tol:
            if abs(abs(a[2]) - abs(b[2])) < tol and abs(a[0] - b[0]) > tol:
                return eid
    raise LookupError(f"no horizontal edge at y={y}")


def mid_target(mesh, mode: str = "loop", y: float = 0.0):
    finder = TargetFinder(mesh)
    return finder, finder.target(horizontal_edge(mesh, y), mode)
