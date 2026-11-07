"""The scene rig: bones with a rest frame in world space (AD-028 §3.1, CORE_V1_FREEZE §7.1 2026-11-02).

Data only, like `MirrorPair` / `ObjectMaterial`: the Core holds an immutable, validated value so the
history can keep a before / after value (a rig command) and the file can be validated; every
behaviour - the pose, the evaluation, the commands - lives in `src/mirai` (`mirai.skinning`). Names
`PROVISIONAL`.

- `Bone` (frozen): `id` (`BoneId`), `name` (non-empty, unique in the rig), `parent` (`BoneId` or None),
  `head` / `tail` (finite, `|tail - head| > 1e-9`), `roll` (radians, finite), `hidden` (outliner eye, 2026-11-07:
  not drawn / not picked; saved only when True, so a file without hidden bones is unchanged).
- `Rig` (frozen): `bones` in ascending `BoneId` order and `bone_id_counter`; validated on
  construction (ids below the counter and unique, parents exist, no cycle, names unique). Pure
  updates return a new value; a new bone takes the counter's id (never reused, AD-001).
- **Space:** rig space = world space (no rig transform yet; identity = today's behaviour).
- **Rest frame** (`rest_frame`, one deterministic rule, AD-028 §3.1): `y = unit(tail - head)`;
  `x0 = unit(X - (X·y)·y)` with `X` the world X axis, or the world Z axis when `|X·y| > 1 - 1e-6`;
  `x` = `x0` turned by `roll` about `y` (right-hand rule); `z = x × y`. `R = [x y z]` (columns),
  returned as rows like `ObjectTransform.rotation`; `h = head`.
- The bind pose is the bones' rest frames plus the bound meshes' rest shape (AD-028 §3.2): no bind
  matrix per object.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, replace

from .ids import BoneId

Vec3 = tuple[float, float, float]
Mat3 = tuple[Vec3, Vec3, Vec3]

#: A bone shorter than this is degenerate (AD-028 §3.1).
MIN_BONE_LENGTH = 1e-9
#: |X·y| above this uses the world Z axis as the reference for the bone's X (AD-028 §3.1).
PARALLEL_LIMIT = 1.0 - 1e-6


def _vec3(values: Iterable[float], what: str) -> Vec3:
    try:
        vec = tuple(float(v) for v in values)
    except (TypeError, ValueError):
        raise ValueError(f"{what} muss drei endliche Zahlen haben: {values!r}") from None
    if len(vec) != 3 or not all(math.isfinite(v) for v in vec):
        raise ValueError(f"{what} muss drei endliche Zahlen haben: {vec!r}")
    return vec  # type: ignore[return-value]


def _require_bone_id(value: object, what: str) -> BoneId:
    # IDs are ints: VertexId(0) == BoneId(0). A bone id is never derived from another id, hence the type.
    if not isinstance(value, BoneId):
        raise TypeError(f"{what}: erwartet eine BoneId, nicht {value!r}")
    if int(value) < 0:
        raise ValueError(f"{what}: BoneId negativ: {int(value)}")
    return value


@dataclass(frozen=True)
class Bone:
    id: BoneId
    name: str
    parent: BoneId | None
    head: Vec3
    tail: Vec3
    roll: float = 0.0
    hidden: bool = False

    def __post_init__(self) -> None:
        _require_bone_id(self.id, "Bone.id")
        if not isinstance(self.hidden, bool):
            raise TypeError(f"Bone.hidden ist ein bool: {self.hidden!r}")
        if self.parent is not None:
            _require_bone_id(self.parent, "Bone.parent")
            if self.parent == self.id:
                raise ValueError(f"Knochen {int(self.id)} ist sein eigener Elternknochen")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Ein Knochen braucht einen nicht leeren Namen")
        head = _vec3(self.head, "head")
        tail = _vec3(self.tail, "tail")
        if math.dist(head, tail) <= MIN_BONE_LENGTH:
            raise ValueError(f"Knochen {self.name!r} ist degeneriert (Kopf = Spitze)")
        if isinstance(self.roll, bool):
            raise TypeError("roll ist eine Zahl")
        roll = float(self.roll)
        if not math.isfinite(roll):
            raise ValueError(f"roll muss endlich sein: {self.roll!r}")
        object.__setattr__(self, "head", head)
        object.__setattr__(self, "tail", tail)
        object.__setattr__(self, "roll", roll)

    @property
    def length(self) -> float:
        return math.dist(self.head, self.tail)

    def to_dict(self) -> dict:
        raw = {
            "id": int(self.id),
            "name": self.name,
            "parent": None if self.parent is None else int(self.parent),
            "head": list(self.head),
            "tail": list(self.tail),
            "roll": self.roll,
        }
        if self.hidden:
            raw["hidden"] = True  # fehlt = sichtbar (wie `hidden` beim Objekt, Dateiversion 8)
        return raw

    @classmethod
    def from_dict(cls, raw: dict) -> "Bone":
        parent = raw["parent"]
        return cls(
            id=BoneId(_int(raw["id"], "id")),
            name=raw["name"],
            parent=None if parent is None else BoneId(_int(parent, "parent")),
            head=raw["head"],
            tail=raw["tail"],
            roll=raw["roll"],
            hidden=_flag(raw.get("hidden", False), "hidden"),
        )


def _flag(value: object, what: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{what} muss true oder false sein: {value!r}")
    return value


def _int(value: object, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} muss eine ganze Zahl sein: {value!r}")
    return int(value)


@dataclass(frozen=True)
class Rig:
    """The scene's bones (module docstring). `bones` is a tuple in ascending id order."""

    bones: tuple[Bone, ...] = ()
    bone_id_counter: int = 0

    def __post_init__(self) -> None:
        bones = tuple(self.bones)
        counter = _int(self.bone_id_counter, "bone_id_counter")
        ids = set()
        names = set()
        for bone in bones:
            if not isinstance(bone, Bone):
                raise TypeError(f"Rig.bones: erwartet Bone, nicht {bone!r}")
            if bone.id in ids:
                raise ValueError(f"BoneId doppelt: {int(bone.id)}")
            if int(bone.id) >= counter:
                raise ValueError(f"BoneId {int(bone.id)} liegt nicht unter bone_id_counter {counter}")
            if bone.name in names:
                raise ValueError(f"Knochenname doppelt: {bone.name!r}")
            ids.add(bone.id)
            names.add(bone.name)
        if [int(b.id) for b in bones] != sorted(int(b.id) for b in bones):
            raise ValueError("Rig.bones muss nach BoneId aufsteigend geordnet sein")
        parents = {b.id: b.parent for b in bones}
        for bone in bones:
            if bone.parent is not None and bone.parent not in ids:
                raise ValueError(f"Knochen {bone.name!r}: unbekannter Elternknochen {int(bone.parent)}")
        for bone in bones:
            seen = {bone.id}
            p = bone.parent
            while p is not None:
                if p in seen:
                    raise ValueError(f"Zyklus in der Knochenhierarchie bei {bone.name!r}")
                seen.add(p)
                p = parents[p]
        object.__setattr__(self, "bones", bones)
        object.__setattr__(self, "bone_id_counter", counter)

    # -- reading --------------------------------------------------------------------------------

    def bone(self, bone_id: BoneId) -> Bone:
        for bone in self.bones:
            if bone.id == bone_id:
                return bone
        raise KeyError(f"Unbekannter Knochen {bone_id!r}")

    def has_bone(self, bone_id: BoneId) -> bool:
        return any(bone.id == bone_id for bone in self.bones)

    def bone_ids(self) -> list[BoneId]:
        return [bone.id for bone in self.bones]

    def children(self, bone_id: BoneId) -> tuple[BoneId, ...]:
        return tuple(bone.id for bone in self.bones if bone.parent == bone_id)

    def ancestors(self, bone_id: BoneId) -> tuple[BoneId, ...]:
        """The parent chain of a bone, nearest first."""
        out = []
        p = self.bone(bone_id).parent
        while p is not None:
            out.append(p)
            p = self.bone(p).parent
        return tuple(out)

    def topological_order(self) -> tuple[BoneId, ...]:
        """Every bone after its parent; among siblings ascending id (deterministic)."""
        order: list[BoneId] = []
        placed: set = set()
        remaining = list(self.bones)
        while remaining:
            rest = []
            for bone in remaining:
                if bone.parent is None or bone.parent in placed:
                    order.append(bone.id)
                    placed.add(bone.id)
                else:
                    rest.append(bone)
            remaining = rest
        return tuple(order)

    @property
    def next_bone_id(self) -> BoneId:
        return BoneId(self.bone_id_counter)

    # -- pure updates ---------------------------------------------------------------------------

    def with_new_bone(
        self, name: str, head: Iterable[float], tail: Iterable[float], *, parent: BoneId | None = None,
        roll: float = 0.0,
    ) -> tuple["Rig", BoneId]:
        """A new rig with one more bone under the next id (never reused), and that id."""
        bone = Bone(self.next_bone_id, name, parent, tuple(head), tuple(tail), roll)  # type: ignore[arg-type]
        return Rig(self.bones + (bone,), self.bone_id_counter + 1), bone.id

    def with_bone(self, bone: Bone) -> "Rig":
        """A new rig with `bone` replacing the bone of the same id (rename, re-parent, roll).
        A new id goes through `with_new_bone`: an absent id below the counter would be a reused one."""
        if not self.has_bone(bone.id):
            raise KeyError(f"Unbekannter Knochen {bone.id!r} (neue Knochen: with_new_bone)")
        return Rig(tuple(bone if b.id == bone.id else b for b in self.bones), self.bone_id_counter)

    def with_name(self, bone_id: BoneId, name: str) -> "Rig":
        b = self.bone(bone_id)
        return self.with_bone(replace(b, name=name))

    def with_hidden(self, bone_ids: Iterable[BoneId], hidden: bool) -> "Rig":
        """A new rig whose named bones have `hidden` (unknown ids: `KeyError`)."""
        ids = set(bone_ids)
        for bone_id in ids:
            self.bone(bone_id)
        return Rig(tuple(replace(b, hidden=hidden) if b.id in ids else b for b in self.bones), self.bone_id_counter)

    def hidden_ids(self) -> frozenset:
        return frozenset(b.id for b in self.bones if b.hidden)

    def without_bone(self, bone_id: BoneId) -> "Rig":
        """A new rig without the bone; its children are re-parented to its parent with their rest
        frames unchanged (AD-028 §3.4). The counter stays (the id is never reused)."""
        gone = self.bone(bone_id)
        bones = tuple(
            replace(b, parent=gone.parent) if b.parent == bone_id else b
            for b in self.bones
            if b.id != bone_id
        )
        return Rig(bones, self.bone_id_counter)

    # -- file -----------------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """`{"bone_id_counter": n, "bones": [...]}`, bones in id order (AD-028 §3.6)."""
        return {"bone_id_counter": self.bone_id_counter, "bones": [b.to_dict() for b in self.bones]}

    @classmethod
    def from_dict(cls, raw: dict) -> "Rig":
        """Validates through `Rig` / `Bone`; anything invalid raises ValueError (or TypeError)."""
        if not isinstance(raw, dict):
            raise ValueError(f"rig muss ein Objekt sein: {raw!r}")
        try:
            bones = tuple(Bone.from_dict(b) for b in raw["bones"])
            return cls(bones, _int(raw["bone_id_counter"], "bone_id_counter"))
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"Ungültiges rig: {exc!r}") from None


def _unit(v: Vec3) -> Vec3:
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n)


def rest_frame(bone: Bone) -> tuple[Mat3, Vec3]:
    """The bone's rest frame `(R, h)` (module docstring): `R` orthonormal with det +1, as rows
    (`R·v` = row·v), its columns the bone's X, Y (head -> tail) and Z axes in world space; `h` the
    head. Rig space = world space, so the rig is not a parameter yet."""
    h = bone.head
    y = _unit((bone.tail[0] - h[0], bone.tail[1] - h[1], bone.tail[2] - h[2]))
    ref = (1.0, 0.0, 0.0) if abs(y[0]) <= PARALLEL_LIMIT else (0.0, 0.0, 1.0)
    d = ref[0] * y[0] + ref[1] * y[1] + ref[2] * y[2]
    x0 = _unit((ref[0] - d * y[0], ref[1] - d * y[1], ref[2] - d * y[2]))
    if bone.roll:
        c, s = math.cos(bone.roll), math.sin(bone.roll)
        # y × x0 (Rodrigues with k·x0 = 0)
        yx = (y[1] * x0[2] - y[2] * x0[1], y[2] * x0[0] - y[0] * x0[2], y[0] * x0[1] - y[1] * x0[0])
        x = (c * x0[0] + s * yx[0], c * x0[1] + s * yx[1], c * x0[2] + s * yx[2])
    else:
        x = x0
    z = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
    rows = ((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2]))
    return rows, h
