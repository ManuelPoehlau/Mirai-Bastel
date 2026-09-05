"""Minimale Vec3-Hilfsfunktionen auf reinen Tupeln.

Bewusst konsistent mit der `Position = tuple[float, float, float]`-
Konvention aus dem Core (siehe mirai_bastel_core/mesh.py) statt einer
eigenen Vektor-Klasse oder numpy/pyglet.math - das hält camera.py und
picking.py komplett dependency-frei und ohne GPU/Fenster testbar
(siehe tests/test_camera_picking.py).
"""

from __future__ import annotations

import math

Vec3 = tuple[float, float, float]


def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def normalize(a: Vec3) -> Vec3:
    l = length(a)
    if l < 1e-9:
        return (0.0, 0.0, 0.0)
    return scale(a, 1.0 / l)


def distance(a: Vec3, b: Vec3) -> float:
    return length(sub(a, b))
