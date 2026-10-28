"""Working Pivot (2026-10-28, Manu U-1..U-4; AD-012 addendum "Working Pivot").

A persistent point that W/E/R gestures rotate and scale around instead of the selection centre. It is
app state, not mesh data: a position in the edit object's space (so it follows the object's placement)
handed to the transform tools as `params["pivot"]`, which they and the Core ops already accept (Core
mirrors it for symmetry partners). Placing it is not an undo step (U-3); World axes only (U-4).

`place_pivot` turns a click into that point (U-2): on the mesh the middle between where the view ray
enters and leaves it ("inside": jaw hinge, elbow, knuckle in one click); with `snap` the vertex or edge
point under the cursor (the Knife's pick, Shift as in the Knife); off the mesh the plane facing the camera
through `anchor`, so a click after orbiting moves the pivot sideways without changing its depth.
Pure maths: `camera` is the edit object's camera (`ObjectSpaceCamera` or `OrbitCamera`).

Symmetry plane snap (V-3, Manu 2026-10-28; WP Ortho / Views): with symmetry on, a placed point within
`PIVOT_PLANE_SNAP_PX` (screen) of its projection onto the symmetry plane lands exactly on the plane -
in every view and after every placement mode (`snap_to_plane`; `Application._pivot_point_at` applies it).
In an orthographic Side view every view ray runs along the plane normal, so the "inside" point of a
mirror-symmetric mesh is on the plane already and the snap only removes float rounding.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from core import ObjectId

from .topology.knife_pick import knife_pick
from .viewport import vecmath as v
from .viewport.camera import ray_plane_point
from .viewport.picking import face_hits_t

Vec3 = tuple[float, float, float]

#: V-3 (`PROVISIONAL`): screen distance in pixels within which a placed pivot snaps onto the symmetry plane.
PIVOT_PLANE_SNAP_PX: float = 12.0

#: Two hits closer than this (relative to the entry `t`) are one surface: a ray through a shared edge or
#: a quad's diagonal hits both triangles at the same `t`.
SAME_HIT_RELATIVE = 1e-6


@dataclass(frozen=True)
class WorkingPivot:
    """The placed pivot of one object; `enabled` False = remembered but not used (a tap on the key)."""

    object_id: ObjectId
    position: Vec3
    enabled: bool = True

    def toggled(self) -> "WorkingPivot":
        return replace(self, enabled=not self.enabled)


def _ray_point(origin: Vec3, direction: Vec3, t: float) -> Vec3:
    return (origin[0] + t * direction[0], origin[1] + t * direction[1], origin[2] + t * direction[2])


def inside_point(camera, mesh, sx: float, sy: float, width: int, height: int, *, cache=None) -> Vec3 | None:
    """The middle between the first surface the ray meets and the next one behind it (where it leaves the
    volume); only the entry point when nothing lies behind it (an open sheet). None = the ray misses."""
    hits = face_hits_t(camera, mesh, sx, sy, width, height, cache=cache)
    if not hits:
        return None
    origin, direction = camera.screen_to_ray(sx, sy, width, height)
    entry = hits[0]
    tolerance = SAME_HIT_RELATIVE * max(1.0, abs(entry))
    exit_t = next((t for t in hits[1:] if t - entry > tolerance), None)
    t = entry if exit_t is None else (entry + exit_t) / 2.0
    return _ray_point(origin, direction, t)


def snap_point(
    camera, mesh, sx: float, sy: float, width: int, height: int, *, cache=None, occlusion: bool = False
) -> Vec3 | None:
    """The vertex or edge point under the cursor (the Knife's pick and tolerances); None on a face or off it."""
    target = knife_pick(camera, mesh, sx, sy, width, height, cache=cache, occlusion=occlusion)
    if target["kind"] == "vertex":
        return tuple(mesh.vertex_position(target["vertex_id"]))  # type: ignore[return-value]
    if target["kind"] == "edge":
        a, b = (mesh.vertex_position(vid) for vid in mesh.edge_vertices(target["edge_id"]))
        return v.add(a, v.scale(v.sub(b, a), target["t"]))
    return None


def view_plane_point(camera, sx: float, sy: float, width: int, height: int, anchor: Vec3) -> Vec3 | None:
    """The cursor ray met with the plane through `anchor` facing the camera."""
    origin, direction = camera.screen_to_ray(sx, sy, width, height)
    forward = camera.basis()[0]
    return ray_plane_point(origin, direction, anchor, forward)


def place_pivot(
    camera,
    mesh,
    sx: float,
    sy: float,
    width: int,
    height: int,
    *,
    snap: bool = False,
    anchor: Vec3 | None = None,
    cache=None,
    occlusion: bool = False,
) -> Vec3 | None:
    """Where a click at (sx, sy) puts the Working Pivot (module docstring). `anchor` = the depth for a click
    off the mesh (the current pivot, else the selection centre); without one the camera target."""
    if snap:
        point = snap_point(camera, mesh, sx, sy, width, height, cache=cache, occlusion=occlusion)
        if point is not None:
            return point
    point = inside_point(camera, mesh, sx, sy, width, height, cache=cache)
    if point is not None:
        return point
    return view_plane_point(camera, sx, sy, width, height, tuple(camera.target) if anchor is None else anchor)


def snap_to_plane(
    camera,
    point: Vec3,
    plane_point: Vec3,
    plane_normal: Vec3,
    width: int,
    height: int,
    threshold_px: float = PIVOT_PLANE_SNAP_PX,
) -> tuple[Vec3, bool]:
    """(point, on_plane) (V-3): `point` projected onto the plane (unit `plane_normal`) when the two are at
    most `threshold_px` apart on screen, else `point` unchanged. For an axis plane through the origin the
    projected coordinate is exactly 0 (x - 1·x)."""
    d = v.dot(v.sub(point, plane_point), plane_normal)
    if d == 0.0:
        return point, True
    projected = v.sub(point, v.scale(plane_normal, d))
    a = camera.project_to_screen(point, width, height)
    b = camera.project_to_screen(projected, width, height)
    if a is None or b is None:
        return point, False
    if (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 <= threshold_px * threshold_px:
        return projected, True
    return point, False
