"""Transform Gizmo: handle geometry, picking and draw primitives (promoted 2026-10-21, Manu: "Gizmo nach src/").

Moved (not copied) from `playground/gizmo.py` (WP-AP-GIZMO-01/04; the Playground was removed 2026-10-24). Pure screen / world maths, no GL and no `Application`: `Application` owns the state (pivot,
current tool, constraint, hover, the gesture), `viewport.gl_gizmo_overlay` draws what `draw_items` returns.

Artist decision AD-016 D3 (2026-09-21): the gizmo is an *entry point*. A click on a handle only sets the axis
constraint (like X / Y / Z); click + drag also runs the current tool along it and the LMB release commits; a hit on
a handle takes priority over a selection click, a miss falls through. In the app this is wired in
`Application.pointer_press` / `_gizmo_step`; the frame is the world axes or, in Normal orientation (`K`, WP Toolbox
Gaps C1), the selection's frame from `Application._gizmo_frame`.

Handles (names = the constraint spaces of `Application`): `x`, `y`, `z` (axes; rings when the tool is Rotate),
`xy`, `xz`, `yz` (plane brackets; not for Rotate), `center` (white circle at the pivot, every tool: no constraint -
free Move, Rotate trackball, uniform Scale) and `screen` (Rotate only: the outer camera-facing ring, rotation about
the view axis). Look and sizes are `PROVISIONAL` (Playground values, "needs playtest").

2026-10-28 (Manu A4/A5, E3/E5, `PROVISIONAL`): smaller, with three session sizes (`GIZMO_SIZES`, the caller passes
`scale`; still a fraction of the eye distance, so constant on screen while zooming); the centre circle is picked over
its whole filled disc (`center_pick_radius_px`), not just near the pivot point; rings are picked along their segments
(no gaps between samples on a large ring); a hovered handle that is also the active constraint gets its own state
(`LINE_WIDTH_ACTIVE_HOVER` + the hover colour), so the hover shows on every handle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Vec3 = tuple[float, float, float]

#: Session gizmo sizes (2026-10-28, Manu A4 "smaller than today", `PROVISIONAL`): a fraction of the pivot's distance
#: to the eye (constant on-screen size). Until 2026-10-28 the only size was 0.18; at the 50 degree field of view the
#: axis length is about this fraction / 0.47 of half the viewport height (M ~ 21 %, ~115 px at 1080 px).
GIZMO_SIZES: dict[str, float] = {"S": 0.07, "M": 0.10, "L": 0.13}
GIZMO_SIZE_DEFAULT: str = "M"
GIZMO_SCALE: float = GIZMO_SIZES[GIZMO_SIZE_DEFAULT]
CAP_SIZE_RATIO: float = 0.12
#: Click radius around a handle's projected line / ring / point, in window pixels.
PICK_RADIUS_PX: float = 16.0

WORLD_AXES: list[tuple[str, Vec3]] = [
    ("x", (1.0, 0.0, 0.0)),
    ("y", (0.0, 1.0, 0.0)),
    ("z", (0.0, 0.0, 1.0)),
]

WORLD_PLANES: list[tuple[str, Vec3, Vec3]] = [
    ("xy", (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ("xz", (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ("yz", (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
]

LINE_WIDTH_DEFAULT = 2.0
LINE_WIDTH_HOVER = 3.0
LINE_WIDTH_ACTIVE = 4.0
#: Hover on the handle that is already the active constraint (E5): thicker than active, in the hover colour.
LINE_WIDTH_ACTIVE_HOVER = 5.5
#: Hover colour = the base colour this far towards white (a plain gain hardly shows on saturated red / blue).
HOVER_LIGHTEN = 0.45
COLOR_X = (0.9, 0.15, 0.15, 1.0)
COLOR_Y = (0.15, 0.85, 0.15, 1.0)
COLOR_Z = (0.15, 0.35, 0.9, 1.0)
COLOR_SCREEN = (0.75, 0.75, 0.75, 1.0)
COLOR_PLANES = {
    "xy": (0.75, 0.75, 0.15, 1.0),
    "xz": (0.75, 0.15, 0.75, 1.0),
    "yz": (0.15, 0.75, 0.75, 1.0),
}
COLOR_CENTER = (1.0, 1.0, 1.0, 1.0)
#: The centre circle is white already, so its hover is a warm tint instead of lighter.
COLOR_CENTER_HOVER = (1.0, 0.82, 0.35, 1.0)
#: Radius of the centre circle / of the outer `screen` ring, as a fraction of the gizmo size.
CENTER_RING_RATIO: float = 0.1
SCREEN_RING_RATIO: float = 1.1
#: The centre circle's filled pick disc reaches this far beyond its outline, and is never smaller than the minimum.
CENTER_PICK_MARGIN_PX: float = 4.0
CENTER_PICK_MIN_PX: float = 10.0
_AXIS_COLORS = {"x": COLOR_X, "y": COLOR_Y, "z": COLOR_Z}

TOOLS = ("move", "rotate", "scale")


# ---------------------------------------------------------------------------
# Geometry (no GL)
# ---------------------------------------------------------------------------

def gizmo_size(camera, pivot: Vec3, scale: float = GIZMO_SCALE) -> float:
    """World size of the gizmo at `pivot` (distance to the eye x `scale`, one of `GIZMO_SIZES`)."""
    eye = camera.eye()
    dist = math.sqrt((pivot[0] - eye[0]) ** 2 + (pivot[1] - eye[1]) ** 2 + (pivot[2] - eye[2]) ** 2)
    return max(dist * scale, 1e-6)


def screen_ring_positions(pivot: Vec3, right: Vec3, up: Vec3, radius: float, segments: int = 32) -> list[float]:
    """Flat float list (x,y,z ...) for a billboard circle drawn as a line loop."""
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


def axis_line_positions(pivot: Vec3, direction: Vec3, length: float) -> list[float]:
    """Two vertices (origin -> tip) for a line."""
    return [
        pivot[0], pivot[1], pivot[2],
        pivot[0] + direction[0] * length,
        pivot[1] + direction[1] * length,
        pivot[2] + direction[2] * length,
    ]


def plane_indicator_positions(pivot: Vec3, axis_a: Vec3, axis_b: Vec3, size: float) -> list[float]:
    """L-shaped plane bracket (4 vertices = 2 line segments): one arm runs from the pivot offset along
    `axis_a` to the corner, the other from the same corner along `axis_b` - the usual plane-constraint bracket."""
    s = size * 0.35
    corner = (
        pivot[0] + axis_a[0] * s + axis_b[0] * s,
        pivot[1] + axis_a[1] * s + axis_b[1] * s,
        pivot[2] + axis_a[2] * s + axis_b[2] * s,
    )
    end_a = (pivot[0] + axis_a[0] * s * 2, pivot[1] + axis_a[1] * s * 2, pivot[2] + axis_a[2] * s * 2)
    end_b = (pivot[0] + axis_b[0] * s * 2, pivot[1] + axis_b[1] * s * 2, pivot[2] + axis_b[2] * s * 2)
    return [
        corner[0], corner[1], corner[2], end_a[0], end_a[1], end_a[2],
        corner[0], corner[1], corner[2], end_b[0], end_b[1], end_b[2],
    ]


def _perp_basis(direction: Vec3) -> tuple[Vec3, Vec3]:
    """Two orthonormal vectors perpendicular to `direction` (right, up)."""
    dx, dy, dz = direction
    if abs(dx) <= abs(dy) and abs(dx) <= abs(dz):
        ref = (1.0, 0.0, 0.0)
    elif abs(dy) <= abs(dz):
        ref = (0.0, 1.0, 0.0)
    else:
        ref = (0.0, 0.0, 1.0)
    dot = ref[0] * dx + ref[1] * dy + ref[2] * dz
    r = (ref[0] - dot * dx, ref[1] - dot * dy, ref[2] - dot * dz)
    rlen = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
    r = (r[0] / rlen, r[1] / rlen, r[2] / rlen)
    u = (dy * r[2] - dz * r[1], dz * r[0] - dx * r[2], dx * r[1] - dy * r[0])
    return r, u


def axis_ring_positions(pivot: Vec3, axis_direction: Vec3, radius: float, segments: int = 32) -> list[float]:
    """A ring in the plane perpendicular to `axis_direction` (line loop)."""
    right, up = _perp_basis(axis_direction)
    return screen_ring_positions(pivot, right, up, radius, segments)


def arrow_cap_positions(tip: Vec3, direction: Vec3, cap_size: float) -> list[float]:
    """Line pairs: four wing lines forming an arrowhead at `tip` pointing along `direction`."""
    right, up = _perp_basis(direction)
    back = cap_size * 0.7
    wing = cap_size * 0.35
    out: list[float] = []
    for px, py, pz in [right, up, (-right[0], -right[1], -right[2]), (-up[0], -up[1], -up[2])]:
        end = (
            tip[0] - direction[0] * back + px * wing,
            tip[1] - direction[1] * back + py * wing,
            tip[2] - direction[2] * back + pz * wing,
        )
        out.extend([tip[0], tip[1], tip[2], end[0], end[1], end[2]])
    return out


def box_cap_positions(tip: Vec3, direction: Vec3, cap_size: float) -> list[float]:
    """Line pairs: the four edges of a small square at `tip`, perpendicular to `direction`."""
    right, up = _perp_basis(direction)
    h = cap_size * 0.5
    corners = [
        (tip[0] + right[0]*h + up[0]*h, tip[1] + right[1]*h + up[1]*h, tip[2] + right[2]*h + up[2]*h),
        (tip[0] - right[0]*h + up[0]*h, tip[1] - right[1]*h + up[1]*h, tip[2] - right[2]*h + up[2]*h),
        (tip[0] - right[0]*h - up[0]*h, tip[1] - right[1]*h - up[1]*h, tip[2] - right[2]*h - up[2]*h),
        (tip[0] + right[0]*h - up[0]*h, tip[1] + right[1]*h - up[1]*h, tip[2] + right[2]*h - up[2]*h),
    ]
    out: list[float] = []
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        out.extend([a[0], a[1], a[2], b[0], b[1], b[2]])
    return out


def center_ring_positions(pivot: Vec3, right: Vec3, up: Vec3, size: float) -> list[float]:
    """The small billboard circle of the `center` handle (line loop)."""
    return screen_ring_positions(pivot, right, up, size * CENTER_RING_RATIO)


# ---------------------------------------------------------------------------
# Picking (pure; mirrors picking.py's screen-space pattern)
# ---------------------------------------------------------------------------

def pick_handle(
    camera,
    pivot: Vec3,
    axes,
    planes,
    tool: str,
    click_x: float,
    click_y: float,
    width: int,
    height: int,
    max_pixel_distance: float = PICK_RADIUS_PX,
    free_handles: bool = True,
    scale: float = GIZMO_SCALE,
) -> str | None:
    """The handle nearest to (click_x, click_y) within `max_pixel_distance`, or None.

    `axes` are `(name, direction)` pairs, `planes` `(name, axis_a, axis_b)` triples (the caller passes the frame:
    world axes and planes in the app). Axis and plane-bracket handles are picked along their whole projected
    segment (a click anywhere on the line counts, not only at the tip); rings along their projected segments.
    The `center` owns its filled disc (`center_pick_radius_px`): inside it nothing else is picked, so the axis
    lines and edge-on rings that cross the pivot never steal it. `planes` is ignored for Rotate; `screen` (the outer
    camera-facing ring) exists for Rotate only. `free_handles=False` is the Playground's older set: `center` for
    Scale only, no `screen` ring.
    """
    size = gizmo_size(camera, pivot, scale)

    def _seg_dist(p1, p2) -> float:
        s1 = camera.project_to_screen(p1, width, height)
        s2 = camera.project_to_screen(p2, width, height)
        if s1 is None or s2 is None:
            return float("inf")
        ax, ay = s1
        bx, by = s2
        dx, dy = bx - ax, by - ay
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return math.hypot(ax - click_x, ay - click_y)
        t = max(0.0, min(1.0, ((click_x - ax) * dx + (click_y - ay) * dy) / len_sq))
        return math.hypot(ax + t * dx - click_x, ay + t * dy - click_y)

    if free_handles or tool == "scale":
        center = camera.project_to_screen(pivot, width, height)
        if center is not None and math.hypot(center[0] - click_x, center[1] - click_y) <= center_pick_radius_px(
            camera, pivot, width, height, scale
        ):
            return "center"

    seg_candidates: list[tuple[str, tuple, tuple]] = []

    def add_ring(name: str, ring: list[float]) -> None:
        points = [(ring[i], ring[i + 1], ring[i + 2]) for i in range(0, len(ring), 3)]
        for i, p in enumerate(points):
            seg_candidates.append((name, p, points[(i + 1) % len(points)]))

    for name, direction in axes:
        if tool == "rotate":
            add_ring(name, axis_ring_positions(pivot, direction, size))
        else:
            tip = (pivot[0] + direction[0] * size, pivot[1] + direction[1] * size, pivot[2] + direction[2] * size)
            seg_candidates.append((name, pivot, tip))

    if tool != "rotate":
        for name, axis_a, axis_b in planes:
            s = size * 0.35
            corner = tuple(pivot[i] + axis_a[i] * s + axis_b[i] * s for i in range(3))
            end_a = tuple(pivot[i] + axis_a[i] * s * 2 for i in range(3))
            end_b = tuple(pivot[i] + axis_b[i] * s * 2 for i in range(3))
            seg_candidates.append((name, corner, end_a))
            seg_candidates.append((name, corner, end_b))

    if free_handles and tool == "rotate":
        _, right, up = camera.basis()
        add_ring("screen", screen_ring_positions(pivot, right, up, size * SCREEN_RING_RATIO))

    best_name = None
    best_dist = max_pixel_distance
    for name, p1, p2 in seg_candidates:
        d = _seg_dist(p1, p2)
        if d < best_dist:
            best_dist = d
            best_name = name
    return best_name


def center_pick_radius_px(camera, pivot: Vec3, width: int, height: int, scale: float = GIZMO_SCALE) -> float:
    """Radius in pixels of the centre circle's filled pick disc: its projected outline plus a margin, at least
    `CENTER_PICK_MIN_PX` (a far or small gizmo keeps a hittable centre)."""
    size = gizmo_size(camera, pivot, scale)
    _, right, _ = camera.basis()
    radius = size * CENTER_RING_RATIO
    edge = (pivot[0] + right[0] * radius, pivot[1] + right[1] * radius, pivot[2] + right[2] * radius)
    c = camera.project_to_screen(pivot, width, height)
    e = camera.project_to_screen(edge, width, height)
    ring_px = math.hypot(e[0] - c[0], e[1] - c[1]) if c is not None and e is not None else 0.0
    return max(ring_px + CENTER_PICK_MARGIN_PX, CENTER_PICK_MIN_PX)


# ---------------------------------------------------------------------------
# Draw primitives
# ---------------------------------------------------------------------------

def hover_color(base):
    """The hover colour of a handle: `base` lightened towards white; the white centre gets its warm tint."""
    if base == COLOR_CENTER:
        return COLOR_CENTER_HOVER
    r, g, b, a = base
    k = HOVER_LIGHTEN
    return (r + (1.0 - r) * k, g + (1.0 - g) * k, b + (1.0 - b) * k, a)


@dataclass(frozen=True)
class DrawItem:
    """One line primitive of the gizmo: flat world positions, rgba, `"lines"` (pairs) or `"loop"`, line width."""

    positions: tuple[float, ...]
    color: tuple[float, float, float, float]
    primitive: str
    width: float


def draw_items(
    camera,
    pivot: Vec3,
    tool: str,
    constraint: str | None,
    hover: str | None,
    axes=WORLD_AXES,
    planes=WORLD_PLANES,
    scale: float = GIZMO_SCALE,
) -> list[DrawItem]:
    """The gizmo for `tool` at `pivot`: four states per handle - default, hover (thicker, lighter), active
    (= the current `constraint`, thickest, base colour) and hover on the active handle (thicker still, in the
    hover colour; until 2026-10-28 active hid the hover, E5). Tool-specific shapes: Move = line + arrowhead,
    Rotate = ring per axis plus the camera-facing `screen` ring, Scale = line + box cap; every tool has the
    `center` circle."""
    size = gizmo_size(camera, pivot, scale)
    cap = size * CAP_SIZE_RATIO
    items: list[DrawItem] = []

    def width(name: str) -> float:
        if constraint == name:
            return LINE_WIDTH_ACTIVE_HOVER if hover == name else LINE_WIDTH_ACTIVE
        if hover == name:
            return LINE_WIDTH_HOVER
        return LINE_WIDTH_DEFAULT

    def color(base, name: str):
        if hover != name:
            return base
        return hover_color(base)

    def add(positions, base, name, primitive):
        items.append(DrawItem(tuple(positions), color(base, name), primitive, width(name)))

    for name, direction in axes:
        base = _AXIS_COLORS.get(name, COLOR_SCREEN)
        if tool == "rotate":
            add(axis_ring_positions(pivot, direction, size), base, name, "loop")
            continue
        tip = (pivot[0] + direction[0] * size, pivot[1] + direction[1] * size, pivot[2] + direction[2] * size)
        add(axis_line_positions(pivot, direction, size), base, name, "lines")
        if tool == "move":
            add(arrow_cap_positions(tip, direction, cap), base, name, "lines")
        elif tool == "scale":
            add(box_cap_positions(tip, direction, cap), base, name, "lines")

    _, right, up = camera.basis()
    if tool == "rotate":
        add(screen_ring_positions(pivot, right, up, size * SCREEN_RING_RATIO), COLOR_SCREEN, "screen", "loop")
    else:
        for name, axis_a, axis_b in planes:
            add(plane_indicator_positions(pivot, axis_a, axis_b, size), COLOR_PLANES[name], name, "lines")
    add(center_ring_positions(pivot, right, up, size), COLOR_CENTER, "center", "loop")
    return items


# ---------------------------------------------------------------------------
# Working Pivot marker (2026-10-28, `mirai.pivot`; look `PROVISIONAL`)
# ---------------------------------------------------------------------------

#: Orange, so it never reads as a gizmo handle (red / green / blue / white); the placement preview is half as opaque.
COLOR_PIVOT = (1.0, 0.55, 0.1, 1.0)
PIVOT_PREVIEW_ALPHA = 0.5
#: Half-length of the cross arms and radius of the ring, as fractions of the gizmo size at the point.
PIVOT_CROSS_RATIO: float = 0.35
PIVOT_RING_RATIO: float = 0.2
PIVOT_LINE_WIDTH = 2.5


def pivot_marker_items(camera, point: Vec3, scale: float = GIZMO_SCALE, preview: bool = False) -> list[DrawItem]:
    """The Working Pivot: a world-axis cross through `point` (U-4: World axes) and a camera-facing ring, constant
    on screen like the gizmo. Drawn whenever the pivot is on - also while a W/E/R gesture runs - and dimmed as the
    preview of where a click would place it."""
    size = gizmo_size(camera, point, scale)
    arm = size * PIVOT_CROSS_RATIO
    color = COLOR_PIVOT if not preview else COLOR_PIVOT[:3] + (PIVOT_PREVIEW_ALPHA,)
    cross: list[float] = []
    for _, direction in WORLD_AXES:
        start = (point[0] - direction[0] * arm, point[1] - direction[1] * arm, point[2] - direction[2] * arm)
        cross.extend(axis_line_positions(start, direction, 2.0 * arm))
    _, right, up = camera.basis()
    ring = screen_ring_positions(point, right, up, size * PIVOT_RING_RATIO, segments=24)
    return [
        DrawItem(tuple(cross), color, "lines", PIVOT_LINE_WIDTH),
        DrawItem(tuple(ring), color, "loop", PIVOT_LINE_WIDTH),
    ]
