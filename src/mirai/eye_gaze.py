"""Eye gaze (2026-11-16, `PROVISIONAL`): where the eyes look, as view state on top of each eye's own rotation.

An eye object looks down its local +Z (AD-033 §4.1) and its sclera centre is the local origin. Its own rotation is the
*rest* (primary) position. A gaze mode gives one world point all eyes look at; each eye turns about its own centre by
the shortest rotation from its rest direction to that point (Listing's law: no added roll), at most
`MAX_GAZE_DEGREES`. Both eyes aim at the same point, so they converge on a near target as real eyes do.

Modes: `rest` (the eyes' own rotation, drawn as before), `camera` (the camera's eye point: they look at you while
you orbit), `mouse` (the point under the cursor, `focus` eye radii in front of the eyes) and `target` (a fixed world
point, set by the panel's gaze pad or frozen from `mouse`).

View state only (like the eye preview, AD-033 §6): the document transforms never change, nothing is saved, no Undo.
Pure math, no GL.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import ObjectTransform, SceneObject

from . import object_space

Vec3 = tuple[float, float, float]

GAZE_MODES = ("rest", "camera", "mouse", "target")
#: How far an eye turns from its rest direction at most (`PROVISIONAL`; the human range is about 45-50 degrees). Keeps a
#: target behind the head from turning the eyes into the skull.
MAX_GAZE_DEGREES = 50.0
#: The focus distance in sclera radii (`PROVISIONAL`: 25 = 30 cm at the 12 mm reference eye) and its slider range.
DEFAULT_FOCUS = 25.0
FOCUS_RANGE = (3.0, 300.0)
#: The gaze pad's half extent in degrees (yaw, pitch).
PAD_DEGREES = (45.0, 35.0)

_EPS = 1e-12


@dataclass(frozen=True)
class GazeState:
    mode: str = "rest"
    focus: float = DEFAULT_FOCUS  # distance of the gaze point in front of the eyes, in sclera radii
    target: Vec3 | None = None  # the world point of mode `target`

    def __post_init__(self) -> None:
        if self.mode not in GAZE_MODES:
            raise ValueError(f"gaze mode: one of {GAZE_MODES}, got {self.mode!r}")
        focus = float(self.focus)
        if not (math.isfinite(focus) and FOCUS_RANGE[0] <= focus <= FOCUS_RANGE[1]):
            raise ValueError(f"focus: needs {FOCUS_RANGE[0]:g} .. {FOCUS_RANGE[1]:g} eye radii, got {self.focus!r}")
        object.__setattr__(self, "focus", focus)
        if self.target is not None:
            target = tuple(float(c) for c in self.target)
            if len(target) != 3 or not all(math.isfinite(c) for c in target):
                raise ValueError(f"target: expected a finite 3D point, got {self.target!r}")
            object.__setattr__(self, "target", target)


@dataclass(frozen=True)
class GazeFrame:
    """The eyes taken together: their mid point, the mean rest direction (`forward`), the mean rest up and `right` as
    seen from the front (facing the eyes), and the mean sclera radius in world units."""

    center: Vec3
    forward: Vec3
    up: Vec3
    right: Vec3
    radius: float


def _add(a, b) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(a, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a) -> Vec3 | None:
    n = _norm(a)
    return None if n < _EPS else _scale(a, 1.0 / n)


def _column(rotation, j: int) -> Vec3:
    return (rotation[0][j], rotation[1][j], rotation[2][j])


def eye_center(obj: SceneObject) -> Vec3:
    """The sclera centre in the world (the eye's local origin)."""
    return object_space.to_world(obj, (0.0, 0.0, 0.0))


def rest_forward(obj: SceneObject) -> Vec3:
    return _column(obj.transform.rotation, 2)


def swing(a: Vec3, b: Vec3, max_angle: float) -> tuple[tuple[float, ...], ...]:
    """The shortest rotation turning unit `a` toward unit `b`, by at most `max_angle` radians (rows)."""
    axis = _cross(a, b)
    sin, cos = _norm(axis), _dot(a, b)
    angle = math.atan2(sin, cos)
    if angle < 1e-9:
        return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    if sin < 1e-9:  # straight behind: any axis across `a` (the turn is clamped anyway)
        axis = _cross(a, (0.0, 1.0, 0.0) if abs(a[1]) < 0.9 else (1.0, 0.0, 0.0))
    return object_space.axis_angle_rotation(_unit(axis), min(angle, max_angle))


def aimed_transform(obj: SceneObject, target: Vec3, max_degrees: float = MAX_GAZE_DEGREES) -> ObjectTransform:
    """`obj`'s transform turned about the eye's centre so that its +Z points at `target` (clamped). The centre, the
    scale and the pivot stay; a target at the centre leaves the transform as it is."""
    t = obj.transform
    center = eye_center(obj)
    direction = _unit(_sub(target, center))
    if direction is None:
        return t
    turn = swing(rest_forward(obj), direction, math.radians(max_degrees))
    rotation = object_space.orthonormalize(object_space.matmul3(turn, t.rotation))
    # world(0) = translation + pivot - s * R * pivot (object_space.model_matrix) must stay `center`.
    c = obj.pivot
    rc = tuple(sum(rotation[i][k] * c[k] for k in range(3)) for i in range(3))
    translation = tuple(center[i] - c[i] + t.scale * rc[i] for i in range(3))
    return ObjectTransform(translation, rotation, t.scale)


def gaze_frame(eyes) -> GazeFrame | None:
    """The frame of `eyes` (scene objects with an `EyeSpec`); None without eyes."""
    eyes = list(eyes)
    if not eyes:
        return None
    n = float(len(eyes))
    center = _scale(_add_all(eye_center(obj) for obj in eyes), 1.0 / n)
    forward = _unit(_add_all(rest_forward(obj) for obj in eyes)) or rest_forward(eyes[0])
    up_sum = _add_all(_column(obj.transform.rotation, 1) for obj in eyes)
    up = _unit(_sub(up_sum, _scale(forward, _dot(up_sum, forward))))
    if up is None:
        up = _unit(_cross(forward, (1.0, 0.0, 0.0))) or (0.0, 0.0, 1.0)
    right = _cross(up, forward)  # facing the eyes: +x of the view when they look straight at you
    radius = sum(obj.transform.scale for obj in eyes) / n
    return GazeFrame(center, forward, up, right, radius)


def _add_all(vectors) -> Vec3:
    total = (0.0, 0.0, 0.0)
    for vec in vectors:
        total = _add(total, vec)
    return total


def pad_target(frame: GazeFrame, yaw_degrees: float, pitch_degrees: float, focus: float) -> Vec3:
    """The point `focus` eye radii from the eyes' mid point in the direction (yaw right, pitch up) of the frame."""
    yaw, pitch = math.radians(yaw_degrees), math.radians(pitch_degrees)
    flat = _add(_scale(frame.forward, math.cos(yaw)), _scale(frame.right, math.sin(yaw)))
    direction = _add(_scale(flat, math.cos(pitch)), _scale(frame.up, math.sin(pitch)))
    return _add(frame.center, _scale(direction, focus * frame.radius))


def pad_angles(frame: GazeFrame, target: Vec3) -> tuple[float, float] | None:
    """(yaw, pitch) in degrees of `target` seen from the eyes' mid point; None at the mid point."""
    direction = _unit(_sub(target, frame.center))
    if direction is None:
        return None
    yaw = math.degrees(math.atan2(_dot(direction, frame.right), _dot(direction, frame.forward)))
    pitch = math.degrees(math.asin(max(-1.0, min(1.0, _dot(direction, frame.up)))))
    return yaw, pitch


def mouse_target(camera, cursor: tuple[float, float], width: int, height: int, frame: GazeFrame,
                 focus: float) -> Vec3 | None:
    """The point under `cursor` on the plane facing the view `focus` eye radii in front of the eyes (in perspective at
    most half way to the camera, so the plane never lies behind it). None when the ray misses the plane."""
    origin, direction = camera.screen_to_ray(cursor[0], cursor[1], width, height)
    forward = camera.basis()[0]
    distance = focus * frame.radius
    if not camera.ortho:
        depth = _dot(_sub(frame.center, camera.eye()), forward)
        if depth > 0.0:
            distance = min(distance, 0.5 * depth)
    point = _sub(frame.center, _scale(forward, distance))
    denominator = _dot(direction, forward)
    if denominator < _EPS:
        return None
    t = _dot(_sub(point, origin), forward) / denominator
    if t <= 0.0:
        return None
    return _add(origin, _scale(direction, t))


def camera_target(camera) -> Vec3:
    return tuple(camera.eye())  # type: ignore[return-value]
