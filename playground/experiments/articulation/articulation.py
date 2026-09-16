"""EX-A — Temporary Articulation (H01).

Research question (CHARACTER_SYSTEMS_RESEARCH.md, Axis 6a; ROADMAP.md EX-A):
does temporary articulation help the artist detect topology problems
earlier while modeling?

This is deliberately NOT a rigging system:

- no bones, no persistent skeleton, no bone hierarchy
- no skinning weights are ever stored — the falloff weight is recomputed
  fresh on every update() call from the current pivot/radius
- topology never changes while articulated
- articulation is NEVER pushed to history. There is no commit(). The only
  two states a mesh can end up in are BENT (transient) and RESTORED
  (exact rest positions). This is why ArticulationState does not use the
  production `Tool` ABC (src/mirai/interaction/tool.py) — that contract's
  commit() is specifically for mutations that become permanent via
  MeshStateCommand. Articulation has nothing to commit.

Math reuse: `Transform` from
experiments/rigging-skinning-morphing/deformation.py is reused for the
rigid rotation-about-pivot itself (see docstring on
`_rotate_about_pivot`). `linear_blend_skinning` was evaluated for the
rest/articulated blend and NOT reused: its bone_weights API is built for
several named bones sharing one vertex_position input, which does not fit
a two-state (rest vs. pivot-rotated) falloff blend without passing an
already-centered position through both bones inconsistently. The blend
here is a direct, explicit weight interpolation between the two positions
instead — simpler to read for a two-state case, same underlying idea.

Workshop rig, not a general tool (per Experiment Brief §4): pivot, axis,
and radius are supplied by the caller (H02 determines them from the
press-point hit + a fixed radius rule) and are NOT re-estimated per
update() call — only the angle changes during the drag.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from deformation import Transform


class ArticulationError(ValueError):
    pass


def _falloff_weight(distance: float, radius: float) -> float:
    """Smoothstep falloff: 1.0 at the pivot, 0.0 at/beyond radius.

    Smoothstep rather than linear: a linear falloff has a visible slope
    discontinuity at the boundary, which reads as a crease — i.e. exactly
    the kind of deformation artifact that EX-A's Confound #1 warns can be
    mistaken for a topology problem. Smoothstep keeps the boundary C1.
    """
    if radius <= 0.0:
        return 0.0
    t = min(max(distance / radius, 0.0), 1.0)
    t = 1.0 - t
    return t * t * (3.0 - 2.0 * t)


def _rotation_matrix(axis: tuple, angle_rad: float) -> list[list[float]]:
    """Rodrigues' rotation matrix about a unit axis."""
    ax, ay, az = axis
    length = math.sqrt(ax * ax + ay * ay + az * az)
    if length < 1e-9:
        raise ArticulationError("Articulation axis must be non-zero.")
    ax, ay, az = ax / length, ay / length, az / length
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    t = 1.0 - c
    return [
        [t * ax * ax + c, t * ax * ay - s * az, t * ax * az + s * ay],
        [t * ax * ay + s * az, t * ay * ay + c, t * ay * az - s * ax],
        [t * ax * az - s * ay, t * ay * az + s * ax, t * az * az + c],
    ]


def _rotate_about_pivot(position: tuple, pivot: tuple, rotation: list) -> tuple:
    """Rotate `position` about `pivot` using a reused `Transform`.

    Transform.apply computes R*p + t. Centering position and pivot to the
    origin first, applying the pure rotation, then re-adding the pivot
    keeps the reused Transform semantics exactly as documented in
    deformation.py (rigid transform, no re-derivation of the math here).
    """
    centered = (position[0] - pivot[0], position[1] - pivot[1], position[2] - pivot[2])
    transform = Transform(translation=(0.0, 0.0, 0.0), rotation_matrix=rotation)
    rotated = transform.apply(centered)
    return (rotated[0] + pivot[0], rotated[1] + pivot[1], rotated[2] + pivot[2])


@dataclass
class ArticulationState:
    """One temporary bend gesture: begin -> update* -> restore.

    Instantiate fresh per gesture (per press). Reusing an instance across
    two separate gestures is not supported — call begin() again only after
    restore().
    """

    mesh: object
    pivot: tuple
    axis: tuple
    radius: float

    _rest_positions: dict = field(default_factory=dict, repr=False, init=False)
    _bent: bool = field(default=False, repr=False, init=False)

    def begin(self) -> None:
        if self._bent:
            raise ArticulationError("begin() called twice — restore() first.")
        if self.radius <= 0.0:
            raise ArticulationError("Articulation radius must be positive.")
        self._rest_positions = {
            vid: self.mesh.vertex_position(vid) for vid in self.mesh.all_vertex_ids()
        }
        self._bent = True

    def update(self, angle_rad: float) -> None:
        """Apply the bend for the given angle, relative to REST — not
        incrementally relative to the previous update(). Each call fully
        recomputes positions from `_rest_positions`, so repeated update()
        calls during one drag never accumulate error."""
        if not self._bent:
            raise ArticulationError("update() called before begin().")
        rotation = _rotation_matrix(self.axis, angle_rad)
        px, py, pz = self.pivot
        for vid, rest in self._rest_positions.items():
            dx, dy, dz = rest[0] - px, rest[1] - py, rest[2] - pz
            distance = math.sqrt(dx * dx + dy * dy + dz * dz)
            weight = _falloff_weight(distance, self.radius)
            if weight <= 0.0:
                new_pos = rest
            else:
                articulated = _rotate_about_pivot(rest, self.pivot, rotation)
                new_pos = tuple(
                    rest[i] + weight * (articulated[i] - rest[i]) for i in range(3)
                )
            self.mesh.set_vertex_position(vid, new_pos)

    def restore(self) -> None:
        """Return every affected vertex to its exact rest position.

        Exactness is structural, not approximate: restore() writes back
        the literal values captured in begin(), it does not invert the
        rotation. So restore() is exact regardless of how many update()
        calls happened or what angle they used.
        """
        if not self._bent:
            raise ArticulationError("restore() called before begin().")
        for vid, rest in self._rest_positions.items():
            self.mesh.set_vertex_position(vid, rest)
        self._bent = False

    def retarget(self, pivot: tuple, axis: tuple, radius: float) -> None:
        """Start a new gesture within the SAME session — no re-snapshot.

        Must only be called while a session is active (after begin(), before
        restore()). Does not touch `_rest_positions`. The next update() call
        computes the new gesture's pose fully from the existing rest snapshot,
        exactly as any update() call already does.
        """
        if not self._bent:
            raise ArticulationError("retarget() requires an active session — begin() first.")
        self.pivot, self.axis, self.radius = pivot, axis, radius

    @property
    def is_bent(self) -> bool:
        return self._bent
