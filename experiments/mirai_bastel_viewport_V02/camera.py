"""Einfache Orbit-Kamera für das V0.2 Experiment.

Rein mathematisch, ohne Render-Abhängigkeit (wie im V1-Ansatz). Eine
Kamera-Änderung darf NIE Mesh-Renderdaten invalidieren — sie erzeugt nur
eine "matrices/uniforms"-Aktualisierung (im App/Render-Schritt gezählt).
"""
from __future__ import annotations

import math

Vec3 = tuple[float, float, float]


class OrbitCamera:
    def __init__(
        self,
        target: Vec3 = (0.0, 0.0, 0.0),
        distance: float = 8.0,
        yaw: float = math.radians(45.0),
        pitch: float = math.radians(25.0),
        fov_degrees: float = 50.0,
        near: float = 0.05,
        far: float = 200.0,
    ) -> None:
        self.target = target
        self.distance = distance
        self.yaw = yaw
        self.pitch = pitch
        self.fov_degrees = fov_degrees
        self.near = near
        self.far = far

    def eye(self) -> Vec3:
        cp = math.cos(self.pitch)
        return (
            self.target[0] + self.distance * cp * math.sin(self.yaw),
            self.target[1] + self.distance * math.sin(self.pitch),
            self.target[2] + self.distance * cp * math.cos(self.yaw),
        )

    def orbit(self, d_yaw: float, d_pitch: float) -> None:
        self.yaw += d_yaw
        max_pitch = math.radians(85.0)
        self.pitch = max(-max_pitch, min(max_pitch, self.pitch + d_pitch))

    def dolly(self, factor: float) -> None:
        self.distance = max(0.5, min(200.0, self.distance * factor))

    def pan(self, target: Vec3) -> None:
        self.target = target

    def build_view_matrix(self) -> list[float]:
        """Aufbaut die View-Matrix (Spalten-Hauptreihenfolge, GL-Konvention)."""
        eye = self.eye()
        forward = _normalize(_sub(self.target, eye))
        world_up = (0.0, 1.0, 0.0)
        right = _normalize(_cross(forward, world_up))
        up = _cross(right, forward)

        # Spalten-Hauptreihenfolge
        tx = -_dot(eye, right)
        ty = -_dot(eye, up)
        tz = -_dot(eye, forward)
        return [
            right[0], up[0], forward[0], 0.0,
            right[1], up[1], forward[1], 0.0,
            right[2], up[2], forward[2], 0.0,
            tx, ty, tz, 1.0,
        ]

    def build_projection_matrix(self, aspect: float) -> list[float]:
        half_h = math.tan(math.radians(self.fov_degrees) / 2.0)
        half_w = half_h * aspect
        m00 = 1.0 / half_w
        m11 = 1.0 / half_h
        m22 = -(self.far + self.near) / (self.far - self.near)
        m23 = -1.0
        m32 = -(2.0 * self.far * self.near) / (self.far - self.near)
        return [
            m00, 0.0, 0.0, 0.0,
            0.0, m11, 0.0, 0.0,
            0.0, 0.0, m22, m23,
            0.0, 0.0, m32, 0.0,
        ]


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _len(a: Vec3) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _normalize(a: Vec3) -> Vec3:
    l = _len(a)
    if l < 1e-12:
        return (0.0, 0.0, 0.0)
    return (a[0] / l, a[1] / l, a[2] / l)
