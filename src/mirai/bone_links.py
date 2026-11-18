"""Rigid parts on the rig (AD-036 §4, §5): an object follows a bone through a link on the object (`SceneObject.bone`).

Pure math, no GL, no scene mutation. Names `PROVISIONAL`.

- **Drawn placement** (§4.2): a linked object is drawn with `S_b ∘ T` - `T` its placement (`ObjectTransform` about its
  pivot), `S_b` the bone's world skin transform (`skinning.skin_transforms`). `S_b` is rest-relative and *absent* for an
  unposed bone (F-1), so at rest the drawn placement is `T` itself (the same object, bit-exact): linking never moves an
  object and needs no stored offset; a rest edit of the bone leaves it untouched. A similarity times a similarity is a
  similarity, so the result is an ordinary `ObjectTransform` with the object's own pivot. A dead link (the rig lacks the
  bone) follows nothing.
- **Linked xor bound** (§4.1): an object is linked or has stored weights, not both - the commands refuse the other.
- **The eye guard** (§5.1): an eye links only to a bone whose head lies at the eyeball's centre (its local origin),
  within `EYE_HEAD_TOLERANCE` of its radius. That makes the bone the eye's *eye bone*.
- **Lid frame** (§5.2): the eye's placement carried by its eye bone's *parent* (the head): `P ∘ T`, never the eye's own
  turn - the eye pass's lid shading stays with the head.
- **Gaze as a pose source** (§5.2): in a pose the gaze replaces the eye bones' channels. `G` is the shortest rotation
  (Listing's law, as `eye_gaze.aimed_transform`) about the eye's head-carried centre `P(c)` from the head-carried
  forward `P·f` to the target, clamped relative to that forward; the channel is `L_b = B_b⁻¹ ∘ P⁻¹ ∘ G ∘ P ∘ B_b`, so
  that `S_b = P ∘ (B_b ∘ L_b ∘ B_b⁻¹) = G ∘ P` - the eyeball and its lid points see the same turn. The user's pose is
  never written: `shown_pose` returns a new pose for the skin stage and the links.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Optional

from core import BoneId, ObjectTransform, SceneObject
from core.operations.transform import SEAM_TOLERANCE
from core.rig import Rig, rest_frame

from . import eye_gaze, object_space
from .skinning import _I3, Affine, BonePose, _apply, _compose

Vec3 = tuple[float, float, float]

#: How far an eye bone's head may lie from the eyeball's centre, in eye radii (the object's scale; `PROVISIONAL`). The
#: bone tool's pivot snap places it to about 1e-12 (AD-028 addendum 2026-11-17).
EYE_HEAD_TOLERANCE = 1e-6


class Placed:
    """A stand-in for an object with another placement: `transform` given, `pivot` the object's. What `object_space`
    and `eye_gaze` read of an object (`transform`, `pivot`), so a drawn or head-carried placement goes through them."""

    __slots__ = ("obj", "transform")

    def __init__(self, obj: SceneObject, transform: ObjectTransform) -> None:
        self.obj = obj
        self.transform = transform

    @property
    def pivot(self) -> Vec3:
        return self.obj.pivot


class LivePlacement:
    """As `Placed`, but `transform` is read live through `resolve(obj)` - for the cached `ObjectSpaceCamera` of an
    object, whose `camera_revision` then follows the pose as it follows a placement change."""

    __slots__ = ("obj", "_resolve")

    def __init__(self, obj: SceneObject, resolve) -> None:
        self.obj = obj
        self._resolve = resolve

    @property
    def transform(self) -> ObjectTransform:
        return self._resolve(self.obj)

    @property
    def pivot(self) -> Vec3:
        return self.obj.pivot


# -- links ------------------------------------------------------------------------------------------------------------


def link_of(rig: Optional[Rig], obj: SceneObject) -> Optional[BoneId]:
    """The bone `obj` follows now: its link while the rig has that bone; None without a link or for a dead one."""
    bone = obj.bone
    if bone is None or rig is None or not rig.has_bone(bone):
        return None
    return bone


def follow(transform: ObjectTransform, pivot: Vec3, skin: Affine) -> ObjectTransform:
    """`S ∘ T` as an `ObjectTransform` about the same pivot: with `T(p) = s·R·(p − c) + c + t` and `S(x) = M·x + d`
    (`M = σ·Q`, `Q` a rotation), `S(T(p)) = σs·QR·(p − c) + M·(c + t) + d`."""
    m, d = skin
    sigma = math.sqrt(m[0][0] * m[0][0] + m[1][0] * m[1][0] + m[2][0] * m[2][0])
    q = tuple(tuple(m[i][j] / sigma for j in range(3)) for i in range(3))
    c, t = pivot, transform.translation
    mq = _apply(m, (c[0] + t[0], c[1] + t[1], c[2] + t[2]))
    translation = (mq[0] + d[0] - c[0], mq[1] + d[1] - c[1], mq[2] + d[2] - c[2])
    rotation = object_space.orthonormalize(object_space.matmul3(q, transform.rotation))
    return ObjectTransform(translation, rotation, sigma * transform.scale)


def drawn_transform(obj: SceneObject, rig: Optional[Rig], transforms: Mapping) -> ObjectTransform:
    """The placement `obj` is drawn with under the skin transforms `transforms` (`skin_transforms` of the shown pose):
    `S_b ∘ T` while its bone moves, else its own `transform` (the same object)."""
    bone = link_of(rig, obj)
    skin = None if bone is None else transforms.get(bone)
    if skin is None:
        return obj.transform
    return follow(obj.transform, obj.pivot, skin)


def head_carried(obj: SceneObject, rig: Optional[Rig], transforms: Mapping) -> ObjectTransform:
    """§5.2 the lid frame: an eye's placement carried by its eye bone's parent (`P ∘ T`), never by its own bone's turn;
    `T` itself for an object that is not linked, a root eye bone or an unposed parent."""
    bone = link_of(rig, obj)
    if bone is None:
        return obj.transform
    parent = rig.bone(bone).parent
    skin = None if parent is None else transforms.get(parent)
    if skin is None:
        return obj.transform
    return follow(obj.transform, obj.pivot, skin)


def bone_on_plane(bone, normal: Vec3, offset: float) -> bool:
    """Head and tail on the world plane `normal·x = offset` (AD-028 §8.4's seam tolerance, scaled by the bone's
    distance from the origin): a mirror copy keeps a link to such a bone (§4.4)."""
    scale = max(1.0, *(abs(c) for c in bone.head), *(abs(c) for c in bone.tail))
    tolerance = SEAM_TOLERANCE * scale
    return all(abs(sum(p[i] * normal[i] for i in range(3)) - offset) <= tolerance for p in (bone.head, bone.tail))


def eye_center(obj: SceneObject) -> Vec3:
    return object_space.to_world(obj, (0.0, 0.0, 0.0))


def eye_fits_bone(obj: SceneObject, rig: Rig, bone: BoneId) -> bool:
    """§5.1: the bone's head lies at the eyeball's centre (within `EYE_HEAD_TOLERANCE` eye radii)."""
    head = rig.bone(bone).head
    return math.dist(head, eye_center(obj)) <= EYE_HEAD_TOLERANCE * obj.transform.scale


# -- the gaze as a pose source --------------------------------------------------------------------------------------


def _inverse(a: Affine) -> Affine:
    """The inverse of a similarity `x -> M·x + c` (`M = σ·Q`): `M⁻¹ = Mᵀ / σ²`."""
    m, c = a
    s2 = m[0][0] * m[0][0] + m[1][0] * m[1][0] + m[2][0] * m[2][0]
    mi = tuple(tuple(m[j][i] / s2 for j in range(3)) for i in range(3))
    ci = _apply(mi, c)
    return mi, (-ci[0], -ci[1], -ci[2])


def _about(rotation, center: Vec3) -> Affine:
    """The rotation `rotation` about the point `center`."""
    rc = _apply(rotation, center)
    return rotation, (center[0] - rc[0], center[1] - rc[1], center[2] - rc[2])


def gaze_channel(
    obj: SceneObject, rig: Rig, bone: BoneId, parent_skin: Optional[Affine], target: Vec3,
    max_degrees: float = eye_gaze.MAX_GAZE_DEGREES,
) -> BonePose:
    """§5.2: the eye bone's local pose that turns the eye `obj` (head-carried by `parent_skin`, None = rest) to look at
    `target`: `L_b = B_b⁻¹ ∘ P⁻¹ ∘ G ∘ P ∘ B_b`. A target at the eye's centre is the rest channel."""
    carried = obj if parent_skin is None else Placed(obj, follow(obj.transform, obj.pivot, parent_skin))
    center = eye_center(carried)
    direction = eye_gaze._unit(eye_gaze._sub(target, center))
    if direction is None:
        return BonePose()
    turn = eye_gaze.swing(eye_gaze.rest_forward(carried), direction, math.radians(max_degrees))
    if turn == _I3:
        return BonePose()  # straight ahead: the bone at rest (no product with rounding noise)
    g = _about(turn, center)
    frame = rest_frame(rig.bone(bone))
    inner = g if parent_skin is None else _compose(_inverse(parent_skin), _compose(g, parent_skin))
    local = _compose(_inverse(frame), _compose(inner, frame))
    m, c = local
    rotation = object_space.orthonormalize(m)
    return BonePose(rotation=rotation, translation=c)


def gaze_bones(rig: Optional[Rig], eyes) -> dict:
    """BoneId -> the eye linked to it, for the drawn `eyes` with a live link (the first eye per bone)."""
    out: dict = {}
    for obj in eyes:
        bone = link_of(rig, obj)
        if bone is not None and bone not in out:
            out[bone] = obj
    return out
