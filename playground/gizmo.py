"""Transform Gizmo helpers — WP-AP-GIZMO-01 Phase 1 (draw-only).

`gizmo_mode` is the unit-testable pure function that drives which visual
representation the gizmo shows.  The geometry helpers below are thin math
wrappers with zero GL dependencies, callable from headless tests.
"""

from __future__ import annotations

import math

from core.selection import SelectionMode


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
