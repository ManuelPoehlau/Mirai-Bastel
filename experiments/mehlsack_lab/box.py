"""The segmented box of the creation phase (handoff E9) — pure data, no GL.

`BoxParams` is the value the mouse wheel edits (height, width, depth (Slice 2a E10; Slice 1
had width = depth), `h` height segments, `n` around segments per side — one `n` for
width and depth, A6); `box_positions_and_faces()` turns it into
raw positions + quad indices, `build_box_mesh()` into a `core.Mesh` through the
existing `mirai.scene_factory.mesh_from_positions_and_faces` (no new `src` factory).

Topology: side walls `n × h` quads per side, caps `n × n` quad grids, all quads,
closed, vertices shared. Winding is CCW seen from outside, the convention of
`mirai.scene_factory.create_cube` (outward normal via `(b - a) × (c - a)`).
Counts: `V = 4n(h + 1) + 2(n - 1)²`, `F = 4nh + 2n²`, `E = V + F - 2` (closed, genus 0).

The box is centred on the origin; width runs along x, depth along z. Corner vertices of
the caps have valence 3, so `loop_ring.py` stops horizontal loops on the rim there (its
rule, kept). `rim_vertex_cycles()` names the two rims (cap/wall boundaries) as closed
vertex cycles, so the lab can continue the rim loop around the corners (Slice 2a E15,
an explicit lab override in `targets.py`).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from core import Mesh
from mirai.scene_factory import mesh_from_positions_and_faces

Position = tuple[float, float, float]

#: PROVISIONAL clamps and steps (handoff E9: "h, n ∈ [1, 32]"; sizes in fixed steps, minimum > 0).
SEGMENTS_MIN = 1
SEGMENTS_MAX = 32
SIZE_STEP = 0.25
SIZE_MIN = 0.25
SIZE_MAX = 8.0
#: PROVISIONAL start: a 2 × 2 × 2 cube without extra divisions ("Enter" right away must work).
DEFAULT_HEIGHT = 2.0
DEFAULT_WIDTH = 2.0
DEFAULT_DEPTH = 2.0


def _clamp(value, lo, hi):
    return max(lo, min(hi, value))


@dataclass(frozen=True)
class BoxParams:
    height: float = DEFAULT_HEIGHT
    width: float = DEFAULT_WIDTH
    depth: float = DEFAULT_DEPTH
    #: height segments (horizontal loops shown to Manu = h - 1)
    h: int = 1
    #: around segments per side ("Unterteilung rundum")
    n: int = 1

    def __post_init__(self) -> None:
        if not (SEGMENTS_MIN <= self.h <= SEGMENTS_MAX and SEGMENTS_MIN <= self.n <= SEGMENTS_MAX):
            raise ValueError(f"segments out of range: h={self.h!r}, n={self.n!r}")
        if not all(SIZE_MIN <= v <= SIZE_MAX for v in (self.height, self.width, self.depth)):
            raise ValueError(f"size out of range: height={self.height!r}, width={self.width!r}, "
                             f"depth={self.depth!r}")

    # Sizes are kept on the step grid (k * SIZE_STEP), so repeated steps never drift.
    def _with_size_steps(self, name: str, steps: int) -> "BoxParams":
        value = round(getattr(self, name) / SIZE_STEP + steps) * SIZE_STEP
        return dataclasses.replace(self, **{name: _clamp(value, SIZE_MIN, SIZE_MAX)})

    def with_height_steps(self, steps: int) -> "BoxParams":
        return self._with_size_steps("height", steps)

    def with_width_steps(self, steps: int) -> "BoxParams":
        return self._with_size_steps("width", steps)

    def with_depth_steps(self, steps: int) -> "BoxParams":
        return self._with_size_steps("depth", steps)

    def with_h_steps(self, steps: int) -> "BoxParams":
        return dataclasses.replace(self, h=_clamp(self.h + steps, SEGMENTS_MIN, SEGMENTS_MAX))

    def with_n_steps(self, steps: int) -> "BoxParams":
        return dataclasses.replace(self, n=_clamp(self.n + steps, SEGMENTS_MIN, SEGMENTS_MAX))

    @property
    def loops(self) -> int:
        """Horizontal loops between the rims, as Manu counts them (`h - 1`)."""
        return self.h - 1

    def counts(self) -> tuple[int, int, int]:
        """`(V, E, F)` of the box this describes (closed formula, see module docstring)."""
        h, n = self.h, self.n
        v = 4 * n * (h + 1) + 2 * (n - 1) ** 2
        f = 4 * n * h + 2 * n * n
        return v, v + f - 2, f


def box_positions_and_faces(params: BoxParams) -> tuple[list[Position], list[tuple[int, int, int, int]]]:
    """Raw positions and quad indices of the box (see module docstring)."""
    h, n = params.h, params.n
    half_w = params.width / 2.0
    half_d = params.depth / 2.0
    half_h = params.height / 2.0

    def xz(i: int, k: int) -> tuple[float, float]:
        return (-half_w + params.width * i / n, -half_d + params.depth * k / n)

    # Perimeter of the (i, k) grid, 4n points: +x along k = 0, +z along i = n,
    # -x along k = n, -z along i = 0 (clockwise seen from +y).
    perimeter: list[tuple[int, int]] = (
        [(i, 0) for i in range(n)]
        + [(n, k) for k in range(n)]
        + [(i, n) for i in range(n, 0, -1)]
        + [(0, k) for k in range(n, 0, -1)]
    )
    ring = 4 * n
    positions: list[Position] = []
    for j in range(h + 1):
        y = -half_h + params.height * j / h
        for i, k in perimeter:
            x, z = xz(i, k)
            positions.append((x, y, z))

    def wall(t: int, j: int) -> int:
        return j * ring + (t % ring)

    perimeter_index = {ik: t for t, ik in enumerate(perimeter)}

    def cap_grid(j: int, y: float) -> dict[tuple[int, int], int]:
        grid: dict[tuple[int, int], int] = {}
        for i in range(n + 1):
            for k in range(n + 1):
                t = perimeter_index.get((i, k))
                if t is not None:
                    grid[(i, k)] = wall(t, j)
                else:
                    x, z = xz(i, k)
                    grid[(i, k)] = len(positions)
                    positions.append((x, y, z))
        return grid

    bottom = cap_grid(0, -half_h)
    top = cap_grid(h, half_h)

    faces: list[tuple[int, int, int, int]] = []
    for j in range(h):
        for t in range(ring):
            faces.append((wall(t, j), wall(t, j + 1), wall(t + 1, j + 1), wall(t + 1, j)))
    for i in range(n):
        for k in range(n):
            a, b, c, d = (i, k), (i + 1, k), (i + 1, k + 1), (i, k + 1)
            faces.append((top[a], top[d], top[c], top[b]))
            faces.append((bottom[a], bottom[b], bottom[c], bottom[d]))
    return positions, faces


def rim_vertex_cycles(params: BoxParams) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """`(bottom, top)`: the position indices of the two rims (the wall rows `j = 0` and
    `j = h`, where the caps meet the walls) in perimeter order, each a closed cycle of `4n`
    vertices. Indices refer to `box_positions_and_faces(params)[0]` (walls come first)."""
    ring = 4 * params.n
    return tuple(range(ring)), tuple(range(params.h * ring, (params.h + 1) * ring))


def build_box_mesh(params: BoxParams) -> Mesh:
    positions, faces = box_positions_and_faces(params)
    return mesh_from_positions_and_faces(positions, faces)


def box_rims(mesh: Mesh, params: BoxParams) -> tuple[tuple, ...]:
    """The two rims of a mesh fresh from `build_box_mesh(params)` as `VertexId` cycles.
    `mesh_from_positions_and_faces` adds the vertices in position order, so the `i`-th id of
    `all_vertex_ids()` is position `i` (checked: the counts must match)."""
    ids = mesh.all_vertex_ids()
    if len(ids) != params.counts()[0]:
        raise ValueError("mesh does not match the box parameters")
    return tuple(tuple(ids[i] for i in cycle) for cycle in rim_vertex_cycles(params))
