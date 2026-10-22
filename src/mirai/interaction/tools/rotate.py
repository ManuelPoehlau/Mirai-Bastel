"""RotateTool: modal-interaktives Rotate-Tool auf RotateOperation (src/core).

Pfad:

    Command.Rotate
        ↓
    RotateTool
        ↓
    RotateOperation (src/core, per ADR-001 promoviert)
        ↓
    Mesh / History

begin(vertex_ids=..., space=None, pivot=None):

    space=None         → Blickachse der Kamera im begin()-Moment
                         (Screen-Plane-Rotation); während der Interaktion fix.
    space="x"/"y"/"z"  → Weltachse durch den Pivot (Achsen-Constraint).
    space="xy"/"yz"/"xz" → Rotation in dieser Ebene (AD-009) = Rotation um die
                         Flächennormale (Ebene XY → Achse Z, usw.). Anders als
                         bei Move/Scale ist das KEINE Maske, sondern weiterhin
                         eine einzelne Richtung — eine Rotation hat immer genau
                         eine Achse, auch wenn sie als "Ebene" benannt wird.
    space="normal"     → Rotation um die aus der Selection abgeleitete Normal.
    space=Vec3         → beliebige Richtung durch den Pivot.

Gizmo-Gesten (`begin(gizmo={"mode", "press"})`, sonst unveraendert):

    "dial"      Ring-Handle, wie Blenders Dial: Cursor (Press und aktuell) werden per Ray auf die
                Ebene (Pivot, Achse) gelegt; der Winkel zwischen beiden um die Achse ist die Drehung
                (Mehrfach-Umdrehungen werden mitgezaehlt). Der Greifpunkt folgt dem Cursor, und nahe
                am Pivot dreht ein Pixel mehr Grad. Steht die Ebene (fast) kantenparallel zur Sicht,
                gilt fuer die ganze Geste stattdessen der Versatz entlang der Bildschirm-Tangente.
    "trackball" Mitte: der Mausversatz seit Start (phi) dreht um `up*phi.x - right*phi.y` der beim
                Start eingefrorenen Kamera, Winkel = |phi| * RADIANS_PER_PIXEL (wie Blenders Trackball).

Geste (V1): horizontales Ziehen rotiert; der Zielwinkel wird aus der
KUMULIERTEN Pixel-Distanz berechnet und als inkrementeller Schritt an die
Operation übergeben — das Ergebnis ist unabhängig davon, wie das Fenster
die Drag-Events chunkt.
"""

from __future__ import annotations

import math
from typing import Any

from core import OperationContext, RotateOperation
from core.operations.transform import rotation_keeps_plane

from ...viewport import vecmath as v
from ...viewport.camera import ray_plane_point
from ...soft_selection import SoftRotateOperation
from .transform import TransformTool, _resolve_space, object_axis

VEC3 = tuple[float, float, float]

#: Dial: ab dieser |cos| zwischen Sehstrahl und Achse ist die Ringebene zu flach fuer den Ray-Schnitt.
DIAL_GRAZING_COS = 0.12


def _quat_from_axis_angle(axis: VEC3, angle: float):
    s = math.sin(angle / 2.0)
    return (math.cos(angle / 2.0), axis[0] * s, axis[1] * s, axis[2] * s)


def _quat_mul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def _quat_to_axis_angle(q) -> tuple[VEC3, float]:
    w, x, y, z = q
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-12:
        return (0.0, 0.0, 1.0), 0.0
    return (x / n, y / n, z / n), 2.0 * math.atan2(n, w)


def _resolve_axis(axis, derived_geometry=None, mesh=None, selection=None):
    """Backward compatibility wrapper for _resolve_space (axis → space parameter).

    Deprecated: Use _resolve_space() directly.
    """
    if axis is None:
        raise ValueError("axis=None ist hier nicht gültig.")
    if not isinstance(axis, str):
        # Vector passed directly
        return tuple(axis)
    return _resolve_space(
        axis,
        derived_geometry=derived_geometry,
        mesh=mesh,
        selection=selection,
        for_rotation=True,
    )


class RotateTool(TransformTool):
    """Modal-interaktives Rotate-Tool (Basis: TransformTool)."""

    # V1-Geste: Radiant pro Pixel horizontales Ziehen (~0.45°/px).
    RADIANS_PER_PIXEL = math.pi / 400.0

    def __init__(self) -> None:
        super().__init__()
        self._axis: VEC3 | None = None
        self._drag_pixels = 0.0
        self._applied_angle = 0.0
        self._gizmo: dict | None = None
        self._phi = (0.0, 0.0)
        self._quat_applied = (1.0, 0.0, 0.0, 0.0)

    @property
    def axis(self) -> VEC3:
        """Feste Rotationsachse dieser Interaktion (seit begin())."""
        return self._axis

    def _create_operation(self, context: OperationContext) -> RotateOperation:
        # Soft Selection (WP-SOFT-01 S2a): the base tool put the influence into the params.
        if "influence" in context.params:
            return SoftRotateOperation(context)
        return RotateOperation(context)

    def _on_begin(
        self, scene=None, camera=None, vertex_ids=None, space=None, axis=None, derived_geometry=None,
        gizmo: dict | None = None, **params: Any
    ) -> None:
        super()._on_begin(scene=scene, camera=camera, vertex_ids=vertex_ids, **params)
        # WP-03C: axis is now an explicit parameter (separate from space)
        # Backward compatibility: if only 'axis' is passed (old API), treat it as 'space'
        if space is None and axis is not None and not isinstance(axis, str):
            # axis passed as vector (old API) — treat as space
            space = axis
            axis = None
        elif space is None and axis is not None:
            # axis passed as string (could be old flat API like axis="normal"
            # or new axis="x" from space="normal", axis="x")
            # Let _resolve_space figure it out
            space = axis
            axis = None

        if space is None:
            # Default: Blickachse im begin()-Moment (Screen-Plane-Rotation).
            forward, _, _ = self._camera.basis()
            self._axis = forward
        elif isinstance(space, str):
            self._axis = _resolve_space(
                space,
                derived_geometry=derived_geometry,
                mesh=self._scene.mesh if self._scene else None,
                selection=self._scene.selection if self._scene else None,
                axis=axis,  # Pass through new axis parameter (WP-03C)
                for_rotation=True,
            )
            if space.lower() in ("x", "y", "z", "xy", "yz", "xz", "world"):
                # AD-021 M2-1 (E-8): eine Weltachse, im Objektraum eines platzierten Objekts.
                self._axis = object_axis(self._camera, self._axis)
        else:
            # space als Vektor übergeben
            self._axis = tuple(space)
        self._drag_pixels = 0.0
        self._applied_angle = 0.0
        self._seam_refusal_message = (
            "Rotation um diese Achse würde den Seam-Vertex von der Ebene lösen "
            "(nur Achse parallel zur Ebenennormale)"
        )
        self._gizmo = None
        if gizmo is not None and gizmo["mode"] == "trackball":
            # The axis changes every step: no seam vertex can keep its plane.
            self._refuse_if_seam_unsafe(lambda normal: False)
            _, right, up = self._camera.basis()
            self._gizmo = {"mode": "trackball", "right": right, "up": up}
            self._phi = (0.0, 0.0)
            self._quat_applied = (1.0, 0.0, 0.0, 0.0)
            return
        self._refuse_if_seam_unsafe(lambda normal: rotation_keeps_plane(self._axis, normal))
        if gizmo is not None and gizmo["mode"] == "dial":
            self._gizmo = self._dial_begin(tuple(gizmo["press"]))

    def _dial_begin(self, press: tuple[float, float]) -> dict:
        pivot = self._operation.pivot
        return {"mode": "dial", "press": press, "pivot": pivot, "grazing": None, "start": None,
                "last_delta": 0.0, "turns": 0}

    def _dial_target(self, x: float, y: float, width: int, height: int) -> float:
        """Total dial angle (rad, about `self._axis`) for the cursor at (x, y)."""
        g = self._gizmo
        pivot, axis = g["pivot"], self._axis
        if g["grazing"] is None:
            origin, direction = self._camera.screen_to_ray(*g["press"], width, height)
            g["grazing"] = abs(v.dot(direction, axis)) < DIAL_GRAZING_COS
            hit = None if g["grazing"] else ray_plane_point(origin, direction, pivot, axis)
            if hit is None or v.length(v.sub(hit, pivot)) < 1e-9:
                g["grazing"] = True
            else:
                g["start"] = v.sub(hit, pivot)
            if g["grazing"]:
                g["start"] = self._screen_tangent(pivot, g["press"], width, height)
        if g["grazing"]:
            tangent, radius_px = g["start"]
            return (((x - g["press"][0]) * tangent[0] + (y - g["press"][1]) * tangent[1]) / radius_px)
        origin, direction = self._camera.screen_to_ray(x, y, width, height)
        hit = ray_plane_point(origin, direction, pivot, axis)
        if hit is None:
            return g["last_delta"] + 2.0 * math.pi * g["turns"]
        rel = v.sub(hit, pivot)
        a = g["start"]
        delta = math.atan2(v.dot(axis, v.cross(a, rel)), v.dot(a, rel))
        # Count full turns: a sign flip while the previous delta was past a quarter turn means we wrapped.
        if g["last_delta"] > math.pi / 2 and delta < 0:
            g["turns"] += 1
        elif g["last_delta"] < -math.pi / 2 and delta > 0:
            g["turns"] -= 1
        g["last_delta"] = delta
        return delta + 2.0 * math.pi * g["turns"]

    def _screen_tangent(self, pivot, press, width, height):
        """(unit screen tangent at the press point, ring radius in px) for the grazing fallback; the sign
        follows the right-hand rotation about the axis as seen from the camera."""
        centre = self._camera.project_to_screen(pivot, width, height)
        cx, cy = centre if centre is not None else (width / 2.0, height / 2.0)
        rx, ry = press[0] - cx, press[1] - cy
        radius = max(math.hypot(rx, ry), 24.0)
        if math.hypot(rx, ry) < 1e-6:
            rx, ry = 1.0, 0.0
        n = math.hypot(rx, ry)
        tangent = (-ry / n, rx / n)  # counter-clockwise on screen
        forward, _, _ = self._camera.basis()
        if v.dot(self._axis, forward) > 0.0:  # axis points away from the viewer: ccw on screen = clockwise about it
            tangent = (-tangent[0], -tangent[1])
        return tangent, radius

    def _on_update(
        self, dx: float, dy: float, width: int, height: int, x: float | None = None, y: float | None = None
    ) -> None:
        g = self._gizmo
        if g is not None and g["mode"] == "trackball":
            self._phi = (self._phi[0] + dx, self._phi[1] + dy)
            right, up = g["right"], g["up"]
            axis = v.sub(v.scale(up, self._phi[0]), v.scale(right, self._phi[1]))
            n = v.length(axis)
            if n < 1e-12:
                return
            target = _quat_from_axis_angle(v.scale(axis, 1.0 / n), n * self.RADIANS_PER_PIXEL)
            w, qx, qy, qz = self._quat_applied
            step_q = _quat_mul(target, (w, -qx, -qy, -qz))
            step_axis, step_angle = _quat_to_axis_angle(step_q)
            if step_angle > math.pi:
                step_angle -= 2.0 * math.pi
            if abs(step_angle) > 1e-12:
                self._operation.update(axis=step_axis, angle=step_angle)
            self._quat_applied = target
            return
        if g is not None and g["mode"] == "dial" and x is not None and y is not None:
            target_angle = self._dial_target(x, y, width, height)
            step = target_angle - self._applied_angle
            if step != 0.0:
                self._operation.update(axis=self._axis, angle=step)
                self._applied_angle = target_angle
            return
        # Zielwinkel aus kumulierter Pixel-Distanz → inkrementeller Schritt.
        # Damit ist das Ergebnis unabhängig vom Event-Chunking des Fensters.
        self._drag_pixels += dx
        target_angle = self.RADIANS_PER_PIXEL * self._drag_pixels
        step = target_angle - self._applied_angle
        if step == 0.0:
            return
        self._operation.update(axis=self._axis, angle=step)
        self._applied_angle = target_angle