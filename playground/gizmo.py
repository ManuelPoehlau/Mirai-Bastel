"""Transform Gizmo helpers — WP-AP-GIZMO-01/02/04.

`gizmo_mode`, `pick_gizmo_handle`, and `hover_gizmo_handle` are pure
(no GL), callable from headless tests.  The geometry and the picking maths
are in `mirai.viewport.gizmo` (the app's gizmo, world frame only); this
module adds the Playground's normal-space frames on top.
"""

from __future__ import annotations

import math

from core.selection import SelectionMode


# Geometry, constants and the picking maths live in `mirai.viewport.gizmo` (moved there 2026-10-21 when the
# gizmo was promoted into the app); re-exported here under the names the Playground and its tests use.
from mirai.viewport.gizmo import (  # noqa: F401,E402
    GIZMO_SCALE,
    WORLD_AXES,
    WORLD_PLANES,
    arrow_cap_positions,
    axis_line_positions,
    axis_ring_positions,
    box_cap_positions,
    pick_handle,
    plane_indicator_positions,
    screen_ring_positions,
)


# ---------------------------------------------------------------------------
# Mode classification (pure, unit-testable)
# ---------------------------------------------------------------------------

def gizmo_mode(selection, transform_space: str, axis_constraint: str | None) -> str:
    """Classify which gizmo appearance applies for the current tool state.

    Returns one of:
        'world'         — world-space tripod; axis_constraint (if any) is
                          highlighted, but the full X/Y/Z + planes always show
        'normal_full'   — normal space, single FACE selection (full tangent frame)
        'normal_z_only' — normal space, any other selection (normal direction only)

    'screen' (billboard ring) is intentionally not reachable from here anymore —
    it was the default for axis_constraint=None, but the artist-facing default
    should be the tripod itself (so an axis is directly clickable without first
    setting a constraint via keyboard). The ring geometry/draw path is kept in
    this module and in window.py, unused for now — reserved as a likely default
    for Tweak later, a different interaction model this function doesn't govern.
    """
    if transform_space == "world":
        return "world"
    # Normal space — full frame only for a single-face selection (AD-012 scope).
    if selection.mode == SelectionMode.FACE and len(selection.faces) == 1:
        return "normal_full"
    return "normal_z_only"


# ---------------------------------------------------------------------------
# Hit testing (pure, no GL)
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
    max_pixel_distance: float = 16.0,
    current_tool: str = "move",
) -> str | None:
    """Return the name of the gizmo handle nearest to (click_x, click_y), or None.

    Pure function: no GL calls, testable headless.  `mode` is the result of `gizmo_mode()` for the current
    state; it chooses the frame (world axes + planes, or the normal-space axes), the picking itself is
    `mirai.viewport.gizmo.pick_handle`.
    """
    axes: list = []
    planes: list = []
    if mode == "world":
        axes, planes = WORLD_AXES, WORLD_PLANES
    elif mode == "normal_full":
        from mirai.interaction.tools.transform import _face_tangent_basis  # noqa: PLC0415
        try:
            normal, tangent_x, tangent_y = _face_tangent_basis(mesh, selection, derived_geometry)
        except (ValueError, AttributeError):
            return None
        axes = [("x", tangent_x), ("y", tangent_y), ("z", normal)]
    elif mode == "normal_z_only":
        from mirai.interaction.tools.selection_helpers import selection_normal  # noqa: PLC0415
        normal = selection_normal(derived_geometry, mesh, selection, selection.mode)
        if any(v != 0.0 for v in normal):
            axes = [("z", normal)]
    return pick_handle(
        camera, pivot, axes, planes, current_tool, click_x, click_y, width, height, max_pixel_distance
    )


def hover_gizmo_handle(
    camera,
    pivot: tuple[float, float, float],
    mode: str,
    transform_space: str,
    selection,
    mesh,
    derived_geometry,
    cursor_x: float,
    cursor_y: float,
    width: int,
    height: int,
    max_pixel_distance: float = 16.0,
    current_tool: str = "move",
) -> str | None:
    """Return the handle name nearest to the cursor for hover feedback, or None.

    Pure; separate entry point from pick_gizmo_handle so hover queries never
    accidentally arm a drag at the call site.
    """
    return pick_gizmo_handle(
        camera, pivot, mode, transform_space, selection, mesh, derived_geometry,
        cursor_x, cursor_y, width, height, max_pixel_distance, current_tool,
    )
