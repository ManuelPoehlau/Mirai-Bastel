"""Edit phase, headless: hover influence, the signed gestures, Nachführen, Undo/Redo
(E4, E6, E7; Slice 2b E19/E21).

One `EditSession` per committed box. It owns the mesh, its `HistoryStack`, the
Loop/Ring finder (topology is fixed for the whole edit phase) and a distance cache.
No GL, no pyglet, no camera: the window/state turn mouse motion into a world delta, an
angle step or a factor step and hand them in.

Gesture: `begin_gesture(kind, target, radius, metric, curve, ...)` computes the signed
influence from the current (= start) positions and begins the signed op of that kind
(`move`, `rotate`, `scale`); `step(...)` updates it; `commit()` / `cancel()` end it.
Rotate and Scale get `pivot = primary_pivot(mesh, seeds)` at `begin`, Rotate a fixed axis,
Scale a fixed formula (and world axes, no basis). Influence never enters a `Selection`;
one gesture = one History entry. `begin_drag` / `drag_step` are the Move shorthands of
Slice 1.

What a gesture accumulates (`total`) is what Nachführen replays in one step:
Move the summed delta, Rotate the summed angle (one axis), Scale the product of the
factor steps (`F`, per axis).

Nachführen (E7 b, extended to Rotate/Scale by E21, `retune()`): after a committed
gesture, a curve/radius/metric (and for Scale: formula) change re-evaluates the **last
gesture** from its start snapshot with the stored total (and axis, pivot, formula) and
**replaces** its History entry — with the public `HistoryStack` API only: `undo()` puts the
mesh back to the pre-gesture state (exact, from the command's start positions), the new
weights are measured there, and either `redo()` restores the old entry (nothing that
matters changed) or a fresh one-step gesture is committed, whose `push()` drops the old
entry from the redo branch. History length stays the same; one Undo restores the
pre-gesture mesh. Nachführen ends with the next gesture, Undo/Redo, a toggle of
Nachführen, or a new box (`end_retune()`).

`token` names the current mesh state for the distance cache; it changes with every
position change and returns to the pre-gesture token after a cancel or an undo inside
`retune()`, so curve edits reuse the measured distances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core import HistoryStack, Mesh, OperationContext
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.soft_selection import primary_pivot
from mirai.soft_selection.settings import world_radius_for

from .signed_influence import DistanceCache
from .signed_ops import (
    SignedSoftMoveOperation,
    SignedSoftRotateOperation,
    SignedSoftScaleOperation,
    VertexView,
)
from .targets import Target, TargetFinder

Position = tuple[float, float, float]
Curve = Callable[[float], float]

MOVE = "move"
ROTATE = "rotate"
SCALE = "scale"
KINDS = (MOVE, ROTATE, SCALE)
KIND_LABELS = {MOVE: "Move", ROTATE: "Rotate", SCALE: "Scale"}
_OPS = {MOVE: SignedSoftMoveOperation, ROTATE: SignedSoftRotateOperation, SCALE: SignedSoftScaleOperation}
_IDENTITY = {MOVE: (0.0, 0.0, 0.0), ROTATE: 0.0, SCALE: (1.0, 1.0, 1.0)}


@dataclass
class Drag:
    """The running gesture (any kind; the name is Slice 1's)."""

    kind: str
    operation: Any
    target: Target
    weights: dict
    start_token: int
    radius: float
    metric: str
    curve: Curve
    pivot: Optional[Position] = None
    axis: Optional[Position] = None
    formula: Optional[str] = None
    #: Accumulated amount (module docstring): delta / angle / factor.
    total: Any = (0.0, 0.0, 0.0)
    steps: int = 0


@dataclass
class LastGesture:
    """The committed gesture Nachführen may still re-evaluate."""

    kind: str
    seeds: frozenset
    total: Any
    weights: dict
    radius: float
    metric: str
    curve: Curve
    pre_token: int
    post_token: int
    pivot: Optional[Position] = None
    axis: Optional[Position] = None
    formula: Optional[str] = None
    retunes: int = field(default=0)


class EditSession:
    def __init__(self, mesh: Mesh, rims=()) -> None:
        self.mesh = mesh
        self.history = HistoryStack()
        #: `rims`: the box's rim cycles (`box.box_rims`) for the rim-loop override (E15).
        self.finder = TargetFinder(mesh, rims)
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
        """Signed influence on the current positions (preview and `begin_gesture`)."""
        return self.cache.influence(self.mesh, seeds, radius, metric, curve, self.token)

    @property
    def dragging(self) -> bool:
        return self.drag is not None

    @property
    def can_retune(self) -> bool:
        return self.last is not None

    def _operation(self, kind: str, weights: dict, pivot, formula):
        params: dict = {"influence": weights}
        if kind != MOVE:
            params["pivot"] = pivot
        if kind == SCALE:
            params["scale_formula"] = formula
        operation = _OPS[kind](OperationContext(
            target=self.mesh, selection=VertexView(set(weights)), history=self.history, params=params,
        ))
        operation.begin()
        return operation

    @staticmethod
    def _feed(kind: str, operation, amount, axis) -> None:
        if kind == MOVE:
            operation.update(delta=amount)
        elif kind == ROTATE:
            operation.update(axis=axis, angle=amount)
        else:
            operation.update(factor=amount)

    # -- gesture -------------------------------------------------------------------------

    def begin_gesture(self, kind: str, target: Target, radius: float, metric: str, curve: Curve,
                      axis: Optional[Position] = None, formula: str = "linear") -> dict:
        """Starts a gesture of `kind`; Rotate needs the (fixed) `axis`, Scale uses `formula`."""
        if self.drag is not None:
            raise RuntimeError("a gesture is already running")
        if kind not in KINDS:
            raise ValueError(f"unknown gesture kind {kind!r}")
        if kind == ROTATE and axis is None:
            raise ValueError("a rotate gesture needs its axis")
        self.end_retune()
        weights = self.influence(target.seeds, radius, metric, curve)
        pivot = primary_pivot(self.mesh, target.seeds) if kind != MOVE else None
        operation = self._operation(kind, weights, pivot, formula)
        self.drag = Drag(kind, operation, target, weights, self.token, radius, metric, curve,
                         pivot=pivot, axis=tuple(axis) if axis is not None else None,
                         formula=formula if kind == SCALE else None, total=_IDENTITY[kind])
        return weights

    def begin_drag(self, target: Target, radius: float, metric: str, curve: Curve) -> dict:
        """Slice 1 shorthand: a Move gesture."""
        return self.begin_gesture(MOVE, target, radius, metric, curve)

    def step(self, amount) -> None:
        """One update of the running gesture: a delta (Move), an angle step (Rotate) or a
        factor step per axis (Scale)."""
        drag = self.drag
        if drag is None:
            raise RuntimeError("step() without a running gesture")
        if drag.kind == ROTATE:
            amount = float(amount)
            self._feed(ROTATE, drag.operation, amount, drag.axis)
            drag.total = drag.total + amount
        else:
            amount = (float(amount[0]), float(amount[1]), float(amount[2]))
            self._feed(drag.kind, drag.operation, amount, None)
            t = drag.total
            if drag.kind == MOVE:
                drag.total = (t[0] + amount[0], t[1] + amount[1], t[2] + amount[2])
            else:
                drag.total = (t[0] * amount[0], t[1] * amount[1], t[2] * amount[2])
        drag.steps += 1
        self._new_token()

    def drag_step(self, delta: Position) -> None:
        """Slice 1 name of `step` (Move)."""
        self.step(delta)

    def commit(self):
        """Ends the gesture; returns the History command (None if nothing moved)."""
        drag = self.drag
        if drag is None:
            raise RuntimeError("commit() without a running gesture")
        self.drag = None
        command = drag.operation.commit()
        if command is None:
            self.token = drag.start_token  # end == start, positions untouched
            return None
        self.last = LastGesture(
            kind=drag.kind, seeds=drag.target.seeds, total=drag.total, weights=drag.weights,
            radius=drag.radius, metric=drag.metric, curve=drag.curve,
            pre_token=drag.start_token, post_token=self.token,
            pivot=drag.pivot, axis=drag.axis, formula=drag.formula,
        )
        return command

    def cancel(self) -> None:
        drag = self.drag
        if drag is None:
            raise RuntimeError("cancel() without a running gesture")
        self.drag = None
        drag.operation.cancel()  # exact restore of the start snapshot, no History
        self.token = drag.start_token
        self.last_changed = set(drag.weights)

    # -- Nachführen (E7 b, E21) ----------------------------------------------------------------

    def end_retune(self) -> None:
        self.last = None

    def retune(self, radius: float, metric: str, curve: Curve, formula: Optional[str] = None) -> bool:
        """Re-evaluates the last gesture with new settings (see module docstring). `formula`
        only matters for a Scale gesture (None = keep its own). Returns True if the mesh changed."""
        last = self.last
        if last is None or self.drag is not None:
            return False
        formula = last.formula if (last.kind != SCALE or formula is None) else formula
        if (radius == last.radius and metric == last.metric and curve == last.curve
                and formula == last.formula):
            return False
        self.history.undo()  # pre-gesture state, exact
        self.token = last.pre_token
        weights = self.influence(last.seeds, radius, metric, curve)
        if weights == last.weights and formula == last.formula:
            self.history.redo()
            self.token = last.post_token
            last.radius, last.metric, last.curve = radius, metric, curve
            return False
        operation = self._operation(last.kind, weights, last.pivot, formula)
        self._feed(last.kind, operation, last.total, last.axis)
        command = operation.commit()
        self.last_changed = set(last.weights) | set(weights)
        if command is None:  # cannot happen while the seeds move by the total; stay consistent
            self.last = None
            return True
        last.weights = weights
        last.radius, last.metric, last.curve, last.formula = radius, metric, curve, formula
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
