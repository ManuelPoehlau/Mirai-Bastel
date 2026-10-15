"""Objektraum <-> Welt für ein `SceneObject` (AD-021 M2-1, E-2/E-6/E-7, `PROVISIONAL`).

Mesh-Positionen sind Objektraum-Koordinaten; die Platzierung liegt am Objekt (AD-021 §4.3).
Kompositionsformel (E-2), `p` und `pivot` im Objektraum, `R` = `ObjectTransform.rotation`
(Zeilen, `R·v` = Zeile·v), `s` = gleichmäßiger Faktor > 0 (Q-4):

    world(p)  = translation + pivot + s · R · (p − pivot)
    object(w) = pivot + Rᵀ · (w − translation − pivot) / s

Eine Identitäts-Platzierung (`transform == IDENTITY_TRANSFORM`) ist für jede Funktion hier ein
exakter Durchgang, unabhängig vom Pivot - `pivot + (p − pivot)` wäre in Gleitkomma nicht
bitgleich zu `p`. Damit bleibt alles, was M0/M1 gebaut haben, bitgleich.

`ObjectSpaceCamera` (E-7, L-5 "im Tool-Layer, einmal"): ein Adapter mit genau der Kamera-
Schnittstelle, die Picking, Pick-Cache, Knife und die Transform-Tools lesen, der alles in den
Objektraum des Objekts umrechnet. Die Tools und die Core-Operationen bleiben unverändert und
rechnen weiter in Mesh-Koordinaten (§4.8: Symmetrie und Soft exakt im Objektraum).
Der Core bleibt unberührt: `ObjectTransform` ist dort reine Daten (CORE_V1_FREEZE).
"""

from __future__ import annotations

import math

from core import ObjectTransform, SceneObject
from core.scene import IDENTITY_TRANSFORM

Vec3 = tuple[float, float, float]


def is_identity(transform: ObjectTransform) -> bool:
    return transform == IDENTITY_TRANSFORM


def _rotate(rotation, v: Vec3) -> Vec3:
    return tuple(row[0] * v[0] + row[1] * v[1] + row[2] * v[2] for row in rotation)  # type: ignore[return-value]


def _rotate_back(rotation, v: Vec3) -> Vec3:
    """Rᵀ·v (die Inverse einer Rotation)."""
    return tuple(  # type: ignore[return-value]
        rotation[0][i] * v[0] + rotation[1][i] * v[1] + rotation[2][i] * v[2] for i in range(3)
    )


def to_world(obj: SceneObject, p: Vec3) -> Vec3:
    t = obj.transform
    if is_identity(t):
        return tuple(p)  # type: ignore[return-value]
    c = obj.pivot
    r = _rotate(t.rotation, (p[0] - c[0], p[1] - c[1], p[2] - c[2]))
    return tuple(t.translation[i] + c[i] + t.scale * r[i] for i in range(3))  # type: ignore[return-value]


def to_object(obj: SceneObject, w: Vec3) -> Vec3:
    t = obj.transform
    if is_identity(t):
        return tuple(w)  # type: ignore[return-value]
    c = obj.pivot
    rel = tuple(w[i] - t.translation[i] - c[i] for i in range(3))
    r = _rotate_back(t.rotation, rel)  # type: ignore[arg-type]
    return tuple(c[i] + r[i] / t.scale for i in range(3))  # type: ignore[return-value]


def delta_to_world(obj: SceneObject, d: Vec3) -> Vec3:
    """Eine Verschiebung (Differenz zweier Punkte): s·R·d."""
    t = obj.transform
    if is_identity(t):
        return tuple(d)  # type: ignore[return-value]
    r = _rotate(t.rotation, d)
    return tuple(t.scale * c for c in r)  # type: ignore[return-value]


def delta_to_object(obj: SceneObject, d: Vec3) -> Vec3:
    """Eine Verschiebung in den Objektraum: Rᵀ·d / s."""
    t = obj.transform
    if is_identity(t):
        return tuple(d)  # type: ignore[return-value]
    r = _rotate_back(t.rotation, d)
    return tuple(c / t.scale for c in r)  # type: ignore[return-value]


def axis_to_object(obj: SceneObject, a: Vec3) -> Vec3:
    """Eine Richtung (Achse, Normale) in den Objektraum: Rᵀ·a - Länge bleibt (ohne s)."""
    t = obj.transform
    if is_identity(t):
        return tuple(a)  # type: ignore[return-value]
    return _rotate_back(t.rotation, a)


def axis_to_world(obj: SceneObject, a: Vec3) -> Vec3:
    t = obj.transform
    if is_identity(t):
        return tuple(a)  # type: ignore[return-value]
    return _rotate(t.rotation, a)


def model_matrix(obj: SceneObject) -> list[float] | None:
    """4x4 Objekt -> Welt, spaltenweise wie `OrbitCamera.build_view_matrix` (GL); None = Identität."""
    t = obj.transform
    if is_identity(t):
        return None
    s, rot, c = t.scale, t.rotation, obj.pivot
    rc = _rotate(rot, c)
    translation = [t.translation[i] + c[i] - s * rc[i] for i in range(3)]
    m = [0.0] * 16
    for col in range(3):
        for row in range(3):
            m[col * 4 + row] = s * rot[row][col]
    m[12], m[13], m[14] = translation
    m[15] = 1.0
    return m


def world_center_and_radius(obj: SceneObject, center: Vec3, radius: float) -> tuple[Vec3, float]:
    """Bounds-Kugel aus dem Objektraum in die Welt (gleichmäßige Skalierung: Radius · s)."""
    return to_world(obj, center), radius * obj.transform.scale


class ObjectSpaceCamera:
    """Die Kamera, wie sie im Objektraum von `obj` aussieht (AD-021 M2-1, E-7).

    Genau die Schnittstelle, die die Komponentenpfade lesen (grep 2026-10-15: `project_to_screen`,
    `screen_to_ray`, `eye`, `basis`, `screen_delta_to_world`, `camera_revision`, `target`);
    alles andere fehlt absichtlich, damit ein neuer Konsument laut scheitert statt still in
    Welt zu rechnen. Liest Kamera und Transform live: ein Transform-Wechsel braucht keinen
    neuen Adapter. `camera_revision` ändert sich mit beiden, damit ein `PickCache` nach einem
    Objekt-Transform nicht stale bleibt.

    `screen_to_ray` liefert eine normierte Objektraum-Richtung; ein Trefferparameter `t` ist
    dann in Objekteinheiten (Welt-`t` = `t · scale`, `pick_object`).
    """

    def __init__(self, camera, obj: SceneObject) -> None:
        self.camera = camera
        self.obj = obj

    @property
    def scale(self) -> float:
        return self.obj.transform.scale

    @property
    def camera_revision(self):
        return (self.camera.camera_revision, self.obj.transform, self.obj.pivot)

    @property
    def target(self) -> Vec3:
        return to_object(self.obj, tuple(self.camera.target))

    def eye(self) -> Vec3:
        return to_object(self.obj, self.camera.eye())

    def basis(self) -> tuple[Vec3, Vec3, Vec3]:
        return tuple(axis_to_object(self.obj, a) for a in self.camera.basis())  # type: ignore[return-value]

    def project_to_screen(self, point: Vec3, width: int, height: int):
        return self.camera.project_to_screen(to_world(self.obj, point), width, height)

    def screen_to_ray(self, sx: float, sy: float, width: int, height: int) -> tuple[Vec3, Vec3]:
        origin, direction = self.camera.screen_to_ray(sx, sy, width, height)
        d = axis_to_object(self.obj, direction)
        length = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
        return to_object(self.obj, origin), (d[0] / length, d[1] / length, d[2] / length)

    def screen_delta_to_world(self, point: Vec3, dx: float, dy: float, width: int, height: int) -> Vec3:
        """Name wie an `OrbitCamera`; liefert hier ein **Objektraum**-Delta für `point` (Objektraum)."""
        world = self.camera.screen_delta_to_world(to_world(self.obj, point), dx, dy, width, height)
        return delta_to_object(self.obj, world)

    # -- für die Constraints der Transform-Tools (E-8) --------------------------------

    def axis_to_object(self, a: Vec3) -> Vec3:
        return axis_to_object(self.obj, a)

    def delta_to_world(self, d: Vec3) -> Vec3:
        return delta_to_world(self.obj, d)

    def delta_to_object(self, d: Vec3) -> Vec3:
        return delta_to_object(self.obj, d)


# -- AD-021 M2-2 (E-11): Rotationen der Objekt-Geste ----------------------------------------


def axis_angle_rotation(axis: Vec3, angle: float):
    """Rotationsmatrix (Zeilen) um die normierte `axis` um `angle` (Rechte-Hand-Regel wie
    `core.operations.transform`: q' = q·cos + (k×q)·sin + k·(k·q)·(1−cos)). `angle == 0` ist
    exakt die Identität."""
    x, y, z = axis
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return (
        (c + t * x * x, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, c + t * y * y, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, c + t * z * z),
    )


def matmul3(a, b):
    """a·b für 3×3-Matrizen in Zeilen."""
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3)
    )


def orthonormalize(rotation):
    """Gram-Schmidt über die Zeilen, dritte Zeile als Kreuzprodukt (det +1): ein Produkt vieler
    Rotationen bleibt so innerhalb von `ROTATION_TOLERANCE` und `ObjectTransform` scheitert nie
    an Rundungsdrift (E-11)."""

    def unit(v):
        n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
        return (v[0] / n, v[1] / n, v[2] / n)

    r0 = unit(rotation[0])
    d = sum(rotation[1][i] * r0[i] for i in range(3))
    r1 = unit(tuple(rotation[1][i] - d * r0[i] for i in range(3)))
    r2 = (
        r0[1] * r1[2] - r0[2] * r1[1],
        r0[2] * r1[0] - r0[0] * r1[2],
        r0[0] * r1[1] - r0[1] * r1[0],
    )
    return (r0, r1, r2)
