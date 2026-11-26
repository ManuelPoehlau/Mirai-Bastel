"""The weight brush's arithmetic (AD-041 §3, slice 1): pure, headless, no window. Names `PROVISIONAL`.

**Footprint** (§3.1, `footprint`). A dab is a hit point `p` on the *shown* cage (posed / morphed: a `SurfacePositions`,
or the edit `Mesh` at rest; same IDs and topology). The candidates are the vertices within world radius `r` of `p`
(one NumPy distance pass over `VertexCloud`, the cage's positions); "connected only" (W-3, on by default) keeps those
reachable from the hit face's vertices over edges whose two ends are both candidates (a BFS limited to the candidates,
never the whole mesh - what separates the upper lip from the lower); "front only" (off by default) drops candidates
whose vertex normal faces away from the viewer. Coverage is `c(v) = paint.brush.falloff(|v - p| / r, hardness,
curve)`; a vertex with `c = 0` is not in the footprint.

**Stroke buffer** (§3.2, `BrushWeightStroke`). Per stroke and vertex a coverage `C ∈ [0, 1]` accumulates every dab as
`C <- C + (1 - C)·flow·c`, and the stroke's strength is `S = opacity·C` - the Paint Room's `PaintStroke` semantics
(AD-037 Phase 2: opacity caps what one stroke lays down, flow builds up where dabs overlap; the AD's "S capped at the
opacity" is realised this way, as `PaintStroke` does it). `C` after any set of dabs is `1 - Π(1 - flow·c_k)`, so it does
not depend on their order.

**Operations.** With `old` = the active bone's share at the vertex's *first touch* in the stroke (the press cache):
- Add: `x = old + S·(1 - old)`; Subtract: `x = old·(1 - S)`; Replace: `x = old + S·(value - old)` - all three are
  `soft_target(old, goal, S)` with goal 1 / 0 / value. The new value is `set_bone_weight(press value, bone, x)` (the
  AD-028 §3.4 write rule: raising scales the other shares, lowering gives to the parent or the object). The result is
  a function of the press values and `C` only: path-independent within the stroke; Esc = the caller's
  `rollback_change` restores exactly.
- Smooth works on the *current* values (iterative by nature, path-dependent within a stroke): per dab, for every
  footprint vertex `x = cur + c·flow·(avg_{u ∈ N(v)} cur(u) - cur)` (`N(v)` = its edge neighbours; all targets are
  computed before any is written), then `set_bone_weight(current value, bone, x)`.
- Only footprint vertices are read and written: a dab costs O(footprint) (`WeightStroke.step` iterates every pressed
  vertex, F-3).

**Mask** (and Hide, `services.mask_values`): a vertex with `m >= mask.FULL` keeps its value; a partial mask scales the
change by `1 - m` (`S·(1 - m)`, for Smooth `c·flow·(1 - m)`), as `_WeightsGesture._masked` does.

The stroke runs inside the caller's open recording (`Mesh.begin_change`): release = `end_change` (one History entry),
Esc = `rollback_change`. "Aufräumen" is `skin_weights.clean_weights`.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Optional

import numpy as np

from core import Mesh
from core.rig import Rig

from .mask import FULL as MASK_FULL
from .paint.brush import CURVE_ARRAYS, falloff
from .skin_weights import bone_share, parent_function, set_bone_weight, soft_target

OP_ADD = "add"
OP_SUBTRACT = "subtract"
OP_REPLACE = "replace"
OP_SMOOTH = "smooth"
OPERATIONS = (OP_ADD, OP_SUBTRACT, OP_REPLACE, OP_SMOOTH)
OPERATION_LABELS = {OP_ADD: "Add", OP_SUBTRACT: "Subtract", OP_REPLACE: "Replace", OP_SMOOTH: "Smooth"}

#: the goal of the press-value operations (Replace's is the settings' value)
_GOALS = {OP_ADD: 1.0, OP_SUBTRACT: 0.0}


@dataclass(frozen=True)
class WeightBrushSettings:
    """One stroke's brush (view state of the Weight Room, not saved, no Undo). `radius` is in world units (the room
    converts its percent step of the edit object's bounding radius). Defaults `PROVISIONAL`."""

    operation: str = OP_ADD
    radius: float = 1.0
    flow: float = 0.5
    opacity: float = 1.0
    hardness: float = 0.0
    curve: str = "smooth"
    #: Replace's target share
    value: float = 1.0
    #: W-3: only the part of the sphere connected to the hit face
    connected: bool = True
    #: W-3: drop vertices whose normal faces away from the viewer
    front_only: bool = False

    def __post_init__(self) -> None:
        if self.operation not in OPERATIONS:
            raise ValueError(f"unknown weight brush operation: {self.operation!r}")
        if self.curve not in CURVE_ARRAYS:
            raise ValueError(f"unknown falloff curve: {self.curve!r}")
        if not self.radius > 0.0:
            raise ValueError(f"a brush radius is > 0: {self.radius!r}")
        for name in ("flow", "opacity", "hardness", "value"):
            x = getattr(self, name)
            if not 0.0 <= x <= 1.0:
                raise ValueError(f"{name} lies in [0, 1]: {x!r}")


class VertexCloud:
    """The shown cage's vertex positions as one (n, 3) array (row `i` = `ids[i]`), for the candidate query. Built once
    per stroke; `refresh()` re-reads the positions of a `SurfacePositions` (the posed surface moves while weights are
    painted), a plain `Mesh` keeps its rows (painting never moves rest positions)."""

    def __init__(self, surface) -> None:
        self.surface = surface
        self.ids: list = list(surface.all_vertex_ids())
        self.index: dict = {v: i for i, v in enumerate(self.ids)}
        self._slots = surface.table_slots(self.ids) if hasattr(surface, "table_slots") else None
        self.P = self._read()

    def _read(self) -> np.ndarray:
        if self._slots is not None:
            return np.array(self.surface.position_array()[self._slots], dtype=np.float64)
        n = len(self.ids)
        read = self.surface.vertex_position
        return np.fromiter((c for v in self.ids for c in read(v)), dtype=np.float64, count=3 * n).reshape(n, 3)

    def refresh(self) -> None:
        if self._slots is not None:
            self.P = self._read()

    def position(self, v) -> np.ndarray:
        return self.P[self.index[v]]


@dataclass(frozen=True)
class Footprint:
    """One dab's vertices and their coverage `c ∈ (0, 1]` (aligned)."""

    vertices: tuple
    coverage: np.ndarray

    def __len__(self) -> int:
        return len(self.vertices)


EMPTY_FOOTPRINT = Footprint((), np.zeros(0))


def _neighbours(surface, v) -> list:
    out = []
    for e in surface.vertex_edges(v):
        a, b = surface.edge_vertices(e)
        out.append(b if a == v else a)
    return out


def _vertex_normal(surface, cloud: VertexCloud, v) -> np.ndarray:
    """The unnormalised sum of the Newell normals of the faces around `v`, on the cloud's positions."""
    faces = {f for e in surface.vertex_edges(v) for f in surface.edge_faces(e)}
    n = np.zeros(3)
    for f in faces:
        P = np.array([cloud.position(u) for u in surface.face_vertices(f)])
        Q = np.roll(P, -1, axis=0)
        n += np.array([
            np.sum((P[:, 1] - Q[:, 1]) * (P[:, 2] + Q[:, 2])),
            np.sum((P[:, 2] - Q[:, 2]) * (P[:, 0] + Q[:, 0])),
            np.sum((P[:, 0] - Q[:, 0]) * (P[:, 1] + Q[:, 1])),
        ])
    return n


def footprint(cloud: VertexCloud, point: Sequence[float], settings: WeightBrushSettings, *,
              hit_face=None, toward_viewer: Optional[Sequence[float]] = None) -> Footprint:
    """The dab's footprint at `point` on `cloud.surface` (module docstring). `hit_face` = the face the ray hit (the seed
    of "connected only"; None = the candidate nearest to `point`). `toward_viewer` = the direction to the eye, needed
    for "front only" (ignored when that is off)."""
    p = np.asarray(point, dtype=np.float64)
    r = float(settings.radius)
    d2 = np.einsum("ij,ij->i", cloud.P - p, cloud.P - p)
    rows = np.flatnonzero(d2 < r * r)
    if rows.size == 0:
        return EMPTY_FOOTPRINT
    surface = cloud.surface
    if settings.connected:
        inside = {cloud.ids[i]: i for i in rows.tolist()}
        if hit_face is not None and surface.is_valid_face(hit_face):
            seeds = [v for v in surface.face_vertices(hit_face) if v in inside]
        else:
            seeds = [cloud.ids[int(rows[np.argmin(d2[rows])])]]
        reached = set(seeds)
        queue = deque(seeds)
        while queue:
            v = queue.popleft()
            for u in _neighbours(surface, v):
                if u in inside and u not in reached:
                    reached.add(u)
                    queue.append(u)
        rows = np.array(sorted(inside[v] for v in reached), dtype=np.int64)
        if rows.size == 0:
            return EMPTY_FOOTPRINT
    if settings.front_only and toward_viewer is not None:
        eye = np.asarray(toward_viewer, dtype=np.float64)
        keep = [i for i in rows.tolist() if float(_vertex_normal(surface, cloud, cloud.ids[i]) @ eye) >= 0.0]
        rows = np.array(keep, dtype=np.int64)
        if rows.size == 0:
            return EMPTY_FOOTPRINT
    c = falloff(np.sqrt(d2[rows]) / r, settings.hardness, settings.curve)
    hit = c > 0.0
    rows, c = rows[hit], c[hit]
    return Footprint(tuple(cloud.ids[i] for i in rows.tolist()), c)


class BrushWeightStroke:
    """One brush stroke's weight writes (module docstring): the press value of a vertex is cached at its first touch,
    each dab reads and writes only its footprint. Runs inside the caller's open recording."""

    def __init__(self, mesh: Mesh, layer, bone: int, rig: Optional[Rig], settings: WeightBrushSettings) -> None:
        self.mesh = mesh
        self.layer = layer
        self.bone = int(bone)
        self.settings = settings
        self._parent_of = parent_function(rig)
        #: vertex -> its value at its first touch in this stroke
        self.press: dict = {}
        #: vertex -> accumulated coverage C (the stroke buffer)
        self.cover: dict = {}
        self.dabs = 0

    def press_share(self, v) -> float:
        return bone_share(self.press[v], self.bone)

    def strength(self, v) -> float:
        """`S = opacity·C` of `v` in this stroke (0 untouched)."""
        return self.settings.opacity * self.cover.get(v, 0.0)

    def dab(self, fp: Footprint, mask: Optional[Mapping] = None) -> tuple:
        """One dab over `fp` (`mask`: vertex -> protection in (0, 1], absent = 0). Returns the vertices written."""
        if not len(fp):
            return ()
        self.dabs += 1
        if self.settings.operation == OP_SMOOTH:
            return self._smooth(fp, mask or {})
        return self._press_op(fp, mask or {})

    def _press_op(self, fp: Footprint, mask: Mapping) -> tuple:
        mesh, layer, bone, settings = self.mesh, self.layer, self.bone, self.settings
        goal = settings.value if settings.operation == OP_REPLACE else _GOALS[settings.operation]
        flow, opacity = settings.flow, settings.opacity
        press, cover = self.press, self.cover
        written = []
        for v, c in zip(fp.vertices, fp.coverage.tolist()):
            m = mask.get(v, 0.0)
            if m >= MASK_FULL:
                continue
            value = press.get(v)
            if value is None:
                value = press[v] = mesh.layer_value(layer, v)
            C = cover.get(v, 0.0)
            C = cover[v] = C + (1.0 - C) * flow * c
            S = opacity * C * (1.0 - m)
            x = min(1.0, max(0.0, soft_target(bone_share(value, bone), goal, S)))
            new = set_bone_weight(value, bone, x, self._parent_of)
            if mesh.layer_value(layer, v) != new:
                mesh.set_layer_value(layer, v, new)
                written.append(v)
        return tuple(written)

    def _smooth(self, fp: Footprint, mask: Mapping) -> tuple:
        mesh, layer, bone, flow = self.mesh, self.layer, self.bone, self.settings.flow
        current: dict = {}

        def value_of(u):
            value = current.get(u)
            if value is None:
                value = current[u] = mesh.layer_value(layer, u)
            return value

        plan = []
        for v, c in zip(fp.vertices, fp.coverage.tolist()):
            m = mask.get(v, 0.0)
            if m >= MASK_FULL:
                continue
            ring = _neighbours(mesh, v)
            if not ring:
                continue
            value = value_of(v)
            if v not in self.press:
                self.press[v] = value
            cur = bone_share(value, bone)
            avg = sum(bone_share(value_of(u), bone) for u in ring) / len(ring)
            x = min(1.0, max(0.0, cur + c * flow * (1.0 - m) * (avg - cur)))
            plan.append((v, value, x))
        written = []
        for v, value, x in plan:  # every target from the values before this dab (Jacobi)
            new = set_bone_weight(value, bone, x, self._parent_of)
            if value != new:
                mesh.set_layer_value(layer, v, new)
                written.append(v)
        return tuple(written)

