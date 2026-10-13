"""Edit phase, headless: hover influence, the signed drag, Nachführen, Undo/Redo (E4, E6, E7).

One `EditSession` per committed box. It owns the mesh, its `HistoryStack`, the
Loop/Ring finder (topology is fixed for the whole edit phase) and a distance cache.
No GL, no pyglet, no camera: the window turns mouse motion into world deltas and
hands them in.

Gesture: `begin_drag(target, radius, metric, curve)` computes the signed influence from
the current (= start) positions and begins a `SignedSoftMoveOperation`; `drag_step(delta)`
updates it; `commit()` / `cancel()` end it. Influence never enters a `Selection`; one
gesture = one History entry.

Nachführen (E7 b, `retune()`): after a committed gesture, a curve/radius/metric change
re-evaluates the **last gesture** from its start snapshot as `start + w' · Δ_total` and
**replaces** its History entry — with the public `HistoryStack` API only: `undo()` puts the
mesh back to the pre-gesture state (exact, from the command's start positions), the new
weights are measured there, and either `redo()` restores the old entry (weights unchanged
→ no change at all) or a fresh one-step gesture with the new weights is committed, whose
`push()` drops the old entry from the redo branch. History length stays the same; one
Undo restores the pre-gesture mesh. Nachführen ends with the next gesture, Undo/Redo, a
toggle of Nachführen, or a new box (`end_retune()`).

`token` names the current mesh state for the distance cache; it changes with every
position change and returns to the pre-gesture token after a cancel or an undo inside
`retune()`, so curve edits reuse the measured distances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from core import HistoryStack, Mesh, OperationContext
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.soft_selection.settings import world_radius_for

from .signed_influence import DistanceCache
from .signed_ops import SignedSoftMoveOperation, VertexView
from .targets import Target, TargetFinder

Position = tuple[float, float, float]
Curve = Callable[[float], float]


@dataclass
class Drag:
    operation: SignedSoftMoveOperation
    target: Target
    weights: dict
    start_token: int
    radius: float
    metric: str
    curve: Curve
    #: Sum of the deltas handed to `update()` so far (what Nachführen re-applies in one step).
    total: Position = (0.0, 0.0, 0.0)
    steps: int = 0


@dataclass
class LastGesture:
    """The committed gesture Nachführen may still re-evaluate."""

    seeds: frozenset
    total: Position
    weights: dict
    radius: float
    metric: str
    curve: Curve
    pre_token: int
    post_token: int
    retunes: int = field(default=0)


class EditSession:
    def __init__(self, mesh: Mesh) -> None:
        self.mesh = mesh
        self.history = HistoryStack()
        self.finder = TargetFinder(mesh)
        _center, self.bounding_radius = mesh_center_and_radius(mesh)
        self.cache = DistanceCache()
        self.token = 0
        self._tokens = 0
        self.drag: Optional[Drag] = None
        self.last: Optional[LastGesture] = None
        #: Vertices whose positions the last cancel / Nachführen changed (None = unknown, e.g.
        #: after Undo/Redo); the window marks exactly these dirty.
        self.last_changed: Optional[set] = None

    # -- helpers -----------------------------------------------------------------------

    def _new_token(self) -> int:
        self._tokens += 1
        self.token = self._tokens
        return self.token

    def world_radius(self, radius_step: int) -> float:
        """Radius in world units for a step of `RADIUS_STEPS_PERCENT` (% of the box's
        bounding radius at Enter; AD-020 E5)."""
        return world_radius_for(self.bounding_radius, radius_step)

    def target(self, edge, mode: str) -> Target:
        return self.finder.target(edge, mode)

    def influence(self, seeds, radius: float, metric: str, curve: Curve) -> dict:
        """Signed influence on the current positions (preview and `begin_drag`)."""
        return self.cache.influence(self.mesh, seeds, radius, metric, curve, self.token)

    @property
    def dragging(self) -> bool:
        return self.drag is not None

    @property
    def can_retune(self) -> bool:
        return self.last is not None

    # -- gesture -------------------------------------------------------------------------

    def begin_drag(self, target: Target, radius: float, metric: str, curve: Curve) -> dict:
        if self.drag is not None:
            raise RuntimeError("a drag is already running")
        self.end_retune()
        weights = self.influence(target.seeds, radius, metric, curve)
        operation = SignedSoftMoveOperation(OperationContext(
            target=self.mesh, selection=VertexView(set(weights)), history=self.history,
            params={"influence": weights},
        ))
        operation.begin()
        self.drag = Drag(operation, target, weights, self.token, radius, metric, curve)
        return weights

    def drag_step(self, delta: Position) -> None:
        drag = self.drag
        if drag is None:
            raise RuntimeError("drag_step() without a running drag")
        delta = (float(delta[0]), float(delta[1]), float(delta[2]))
        drag.operation.update(delta=delta)
        t = drag.total
        drag.total = (t[0] + delta[0], t[1] + delta[1], t[2] + delta[2])
        drag.steps += 1
        self._new_token()

    def commit(self):
        """Ends the drag; returns the History command (None if nothing moved)."""
        drag = self.drag
        if drag is None:
            raise RuntimeError("commit() without a running drag")
        self.drag = None
        command = drag.operation.commit()
        if command is None:
            self.token = drag.start_token  # end == start, positions untouched
            return None
        self.last = LastGesture(
            seeds=drag.target.seeds, total=drag.total, weights=drag.weights,
            radius=drag.radius, metric=drag.metric, curve=drag.curve,
            pre_token=drag.start_token, post_token=self.token,
        )
        return command

    def cancel(self) -> None:
        drag = self.drag
        if drag is None:
            raise RuntimeError("cancel() without a running drag")
        self.drag = None
        drag.operation.cancel()  # exact restore of the start snapshot, no History
        self.token = drag.start_token
        self.last_changed = set(drag.weights)

    # -- Nachführen (E7 b) -----------------------------------------------------------------

    def end_retune(self) -> None:
        self.last = None

    def retune(self, radius: float, metric: str, curve: Curve) -> bool:
        """Re-evaluates the last gesture with new settings (see module docstring).
        Returns True if the mesh changed."""
        last = self.last
        if last is None or self.drag is not None:
            return False
        if radius == last.radius and metric == last.metric and curve == last.curve:
            return False
        self.history.undo()  # pre-gesture state, exact
        self.token = last.pre_token
        weights = self.influence(last.seeds, radius, metric, curve)
        if weights == last.weights:
            self.history.redo()
            self.token = last.post_token
            last.radius, last.metric, last.curve = radius, metric, curve
            return False
        operation = SignedSoftMoveOperation(OperationContext(
            target=self.mesh, selection=VertexView(set(weights)), history=self.history,
            params={"influence": weights},
        ))
        operation.begin()
        operation.update(delta=last.total)
        command = operation.commit()
        if command is None:  # cannot happen while the seeds move by Δ_total; stay consistent
            self.last = None
            self.last_changed = set(last.weights) | set(weights)
            return True
        self.last_changed = set(last.weights) | set(weights)
        last.weights = weights
        last.radius, last.metric, last.curve = radius, metric, curve
        last.post_token = self._new_token()
        last.retunes += 1
        return True

    # -- Undo / Redo -------------------------------------------------------------------------

    def undo(self) -> bool:
        if self.drag is not None or not self.history.can_undo():
            return False
        self.end_retune()
        self.history.undo()
        self._new_token()
        self.last_changed = None
        return True

    def redo(self) -> bool:
        if self.drag is not None or not self.history.can_redo():
            return False
        self.end_retune()
        self.history.redo()
        self._new_token()
        self.last_changed = None
        return True
