"""Transform Gizmo helpers — WP-AP-GIZMO-01/02.

`gizmo_mode` and `pick_gizmo_handle` are pure (no GL), callable from
headless tests.  Geometry helpers are thin math wrappers with zero GL
dependencies.
"""

from __future__ import annotations

import math

from core.selection import SelectionMode


# ---------------------------------------------------------------------------
# Shared data: world-space axis and plane handle definitions
# ---------------------------------------------------------------------------

GIZMO_SCALE: float = 0.18

WORLD_AXES: list[tuple[str, tuple[float, float, float]]] = [
    ("x", (1.0, 0.0, 0.0)),
    ("y", (0.0, 1.0, 0.0)),
    ("z", (0.0, 0.0, 1.0)),
]

WORLD_PLANES: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]] = [
    ("xy", (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ("xz", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ("yz", (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
]


# ---------------------------------------------------------------------------
# Mode classification (pure, unit-testable)
# ---------------------------------------------------------------------------

def gizmo_mode(selection, transform_space: str, axis_constraint: str | None) -> str:
    """Classify which gizmo appearance applies for the current tool state.

    Returns one of:
        'screen'        — no axis constraint; show a billboard ring
        'world'         — world-space axis/plane constraint active
        'normal_full'   — normal space, single FACE selection (full tangent frame)
        'normal_z_only' — normal space, any other selection (normal direction only)
    """
    if axis_constraint is None:
        return "screen"
    if transform_space == "world":
        return "world"
    # Normal space — full frame only for a single-face selection (AD-012 scope).
    if selection.mode == SelectionMode.FACE and len(selection.faces) == 1:
        return "normal_full"
    return "normal_z_only"


# ---------------------------------------------------------------------------
# Geometry helpers (no GL, pure math)
# ---------------------------------------------------------------------------

def screen_ring_positions(
    pivot: tuple[float, float, float],
    right: tuple[float, float, float],
    up: tuple[float, float, float],
    radius: float,
    segments: int = 32,
) -> list[float]:
    """Flat float list (x,y,z …) for a billboard circle drawn as GL_LINE_LOOP."""
    out: list[float] = []
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        c, s = math.cos(angle), math.sin(angle)
        out.extend([
            pivot[0] + radius * (c * right[0] + s * up[0]),
            pivot[1] + radius * (c * right[1] + s * up[1]),
            pivot[2] + radius * (c * right[2] + s * up[2]),
        ])
    return out


def axis_line_positions(
    pivot: tuple[float, float, float],
    direction: tuple[float, float, float],
    length: float,
) -> list[float]:
    """Two vertices (origin → tip) for GL_LINES."""
    return [
        pivot[0], pivot[1], pivot[2],
        pivot[0] + direction[0] * length,
        pivot[1] + direction[1] * length,
        pivot[2] + direction[2] * length,
    ]


def plane_indicator_positions(
    pivot: tuple[float, float, float],
    axis_a: tuple[float, float, float],
    axis_b: tuple[float, float, float],
    size: float,
) -> list[float]:
    """L-shaped plane bracket (4 vertices = 2 GL_LINES segments).

    Draws an L at the base of the two axes: one arm runs from the pivot offset
    along axis_a to the corner, the other from the same corner along axis_b.
    The visual result is the standard DCC plane-constraint bracket.
    """
    s = size * 0.35
    corner = (
        pivot[0] + axis_a[0] * s + axis_b[0] * s,
        pivot[1] + axis_a[1] * s + axis_b[1] * s,
        pivot[2] + axis_a[2] * s + axis_b[2] * s,
    )
    end_a = (
        pivot[0] + axis_a[0] * s * 2,
        pivot[1] + axis_a[1] * s * 2,
        pivot[2] + axis_a[2] * s * 2,
    )
    end_b = (
        pivot[0] + axis_b[0] * s * 2,
        pivot[1] + axis_b[1] * s * 2,
        pivot[2] + axis_b[2] * s * 2,
    )
    return [
        corner[0], corner[1], corner[2],
        end_a[0],  end_a[1],  end_a[2],
        corner[0], corner[1], corner[2],
        end_b[0],  end_b[1],  end_b[2],
    ]


# ---------------------------------------------------------------------------
# Hit testing (pure, no GL — mirrors picking.py::pick_nearest_vertex pattern)
# ---------------------------------------------------------------------------

def pick_gizmo_handle(
    camera,
    pivot: tuple[float, float, float],
    mode: str,
    transform_space: str,
    selection,
    mesh,
    derived_geometry,
    click_x: float,
    click_y: float,
    width: int,
    height: int,
    max_pixel_distance: float = 14.0,
) -> str | None:
    """Return the name of the gizmo handle nearest to (click_x, click_y), or None.

    Pure function: no GL calls, testable headless.  `mode` is the result of
    `gizmo_mode()` for the current state.  Axis handles are tested at their
    tip; plane handles at the L-bracket corner.
    """
    cam_eye = camera.eye()
    dist = math.sqrt(
        (pivot[0] - cam_eye[0]) ** 2
        + (pivot[1] - cam_eye[1]) ** 2
        + (pivot[2] - cam_eye[2]) ** 2
    )
    size = max(dist * GIZMO_SCALE, 1e-6)

    candidates: list[tuple[str, tuple[float, float, float]]] = []

    if mode == "world":
        for name, direction in WORLD_AXES:
            tip = (
                pivot[0] + direction[0] * size,
                pivot[1] + direction[1] * size,
                pivot[2] + direction[2] * size,
            )
            candidates.append((name, tip))
        s = size * 0.35
        for name, axis_a, axis_b in WORLD_PLANES:
            corner = (
                pivot[0] + axis_a[0] * s + axis_b[0] * s,
                pivot[1] + axis_a[1] * s + axis_b[1] * s,
                pivot[2] + axis_a[2] * s + axis_b[2] * s,
            )
            candidates.append((name, corner))

    elif mode == "normal_full":
        from mirai.interaction.tools.transform import _face_tangent_basis  # noqa: PLC0415
        try:
            normal, tangent_x, tangent_y = _face_tangent_basis(mesh, selection, derived_geometry)
        except (ValueError, AttributeError):
            return None
        for name, direction in [("x", tangent_x), ("y", tangent_y), ("z", normal)]:
            tip = (
                pivot[0] + direction[0] * size,
                pivot[1] + direction[1] * size,
                pivot[2] + direction[2] * size,
            )
            candidates.append((name, tip))

    elif mode == "normal_z_only":
        from mirai.interaction.tools.selection_helpers import selection_normal  # noqa: PLC0415
        normal = selection_normal(derived_geometry, mesh, selection, selection.mode)
        if any(v != 0.0 for v in normal):
            tip = (
                pivot[0] + normal[0] * size,
                pivot[1] + normal[1] * size,
                pivot[2] + normal[2] * size,
            )
            candidates.append(("z", tip))

    best_name = None
    best_dist = max_pixel_distance
    for name, pos3d in candidates:
        projected = camera.project_to_screen(pos3d, width, height)
        if projected is None:
            continue
        px, py = projected
        d = math.hypot(px - click_x, py - click_y)
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name
