"""The UV check (AD-037 §5, audit 2026-11-18 §5.3 step 1, Phase 1a): read-only, names the faces that cannot be painted
correctly. Nothing here writes the mesh.

- **unmapped**: the mesh has UVs, this face has none (Bridge faces, AD-026 §3) - it draws the base colour;
- **zero area**: the face's UV polygon has no area (Extrude / Inset walls: a line in UV) - it holds no texel;
- **overlapping**: some texel centre of the face lies strictly inside another face's UV area too - one stroke would paint
  both places; counted on a raster at `resolution` (strict interior, so faces that only share a UV edge do not count;
  the coverage counts edges);
- **outside**: a corner lies outside [0, 1] - those parts hold no texel of the paint image (it does not wrap);
- **density**: texels per scene unit at `resolution` (sqrt(UV area x resolution² / surface area)) per face with both
  areas, as p5 / p50 / p95 and their spread p95 / p5;
- **islands** (faces joined across edges whose two corners carry the same UVs on both sides) and **seams** (shared edges
  where they differ).

`check(mesh)` returns a `UVHealth`; `problem_faces()` and `status_line()` are what the app shows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from core import FaceId, Mesh
from viewport.derived import triangulate_mesh_face

from .texel_map import raster_triangle

#: The check's raster side (`PROVISIONAL`): 1024² finds overlaps down to about a texel at 2048² paint (audit §2.2 used
#: 512²) in ~0.3 s on the Gollum head (container).
DEFAULT_RESOLUTION = 1024
#: UV polygon area below which a face counts as zero area (UV units; 1e-9 is 0.004 texel² at 2048²).
ZERO_AREA = 1e-9
_OUTSIDE_EPS = 1e-6
#: Barycentric margin of the overlap count: a centre this close to a triangle edge is not inside it.
_STRICT_EPS = 1e-6


@dataclass(frozen=True)
class UVHealth:
    faces: int
    mapped: int
    unmapped: tuple[FaceId, ...]
    zero_area: tuple[FaceId, ...]
    overlapping: tuple[FaceId, ...]
    outside: tuple[FaceId, ...]
    #: share of covered texels (at `resolution`) covered by more than one face
    overlap_share: float
    #: share of the unit square covered by at least one face
    coverage: float
    islands: int
    seams: int
    #: texels per scene unit at `resolution`: (p5, p50, p95), None without any measurable face
    density: tuple[float, float, float] | None
    resolution: int

    @property
    def has_uvs(self) -> bool:
        return self.mapped > 0

    @property
    def clean(self) -> bool:
        return self.has_uvs and not (self.unmapped or self.zero_area or self.overlapping or self.outside)

    def density_at(self, size: int) -> tuple[float, float, float] | None:
        """The density percentiles for a paint image of side `size` (they scale linearly)."""
        if self.density is None:
            return None
        k = size / self.resolution
        return (self.density[0] * k, self.density[1] * k, self.density[2] * k)

    def problem_faces(self) -> dict[FaceId, str]:
        """{face: kind} with one kind per face, in the order unmapped, zero area, outside, overlapping."""
        out: dict[FaceId, str] = {}
        for kind, faces in (("unmapped", self.unmapped), ("zero_area", self.zero_area), ("outside", self.outside),
                            ("overlapping", self.overlapping)):
            for f in faces:
                out.setdefault(f, kind)
        return out

    def status_line(self) -> str:
        if not self.has_uvs:
            return "UV check: the mesh has no UVs - nothing can be painted"
        parts = [f"{self.faces:,} faces", f"{self.islands} island{'s' if self.islands != 1 else ''}",
                 f"{self.coverage * 100:.1f} % of the square used"]
        if self.unmapped:
            parts.append(f"{len(self.unmapped)} without UVs")
        if self.zero_area:
            parts.append(f"{len(self.zero_area)} without UV area")
        if self.overlapping:
            parts.append(f"{len(self.overlapping)} overlapping ({self.overlap_share * 100:.1f} % of used texels)")
        if self.outside:
            parts.append(f"{len(self.outside)} outside 0-1")
        if self.density is not None and self.density[0] > 0.0:
            parts.append(f"density spread x{self.density[2] / self.density[0]:.1f}")
        if self.clean:
            parts.append("clean")
        return "UV check: " + " · ".join(parts)


def _polygon_area(uvs) -> float:
    total = 0.0
    n = len(uvs)
    for i in range(n):
        (u0, v0), (u1, v1) = uvs[i], uvs[(i + 1) % n]
        total += u0 * v1 - u1 * v0
    return abs(total) * 0.5


def _surface_area(mesh: Mesh, fid: FaceId) -> float:
    total = 0.0
    for a, b, c in triangulate_mesh_face(mesh, fid):
        pa, pb, pc = (mesh.vertex_position(v) for v in (a, b, c))
        e1 = (pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2])
        e2 = (pc[0] - pa[0], pc[1] - pa[1], pc[2] - pa[2])
        cx = e1[1] * e2[2] - e1[2] * e2[1]
        cy = e1[2] * e2[0] - e1[0] * e2[2]
        cz = e1[0] * e2[1] - e1[1] * e2[0]
        total += 0.5 * math.sqrt(cx * cx + cy * cy + cz * cz)
    return total


def _islands_and_seams(mesh: Mesh, mapped: list[FaceId]) -> tuple[int, int]:
    parent = {f: f for f in mapped}

    def find(f):
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    seams = 0
    seen = set()
    for fid in mapped:
        for eid in mesh.face_edges(fid):
            if eid in seen:
                continue
            seen.add(eid)
            faces = [f for f in mesh.edge_faces(eid) if f in parent]
            if len(faces) != 2:
                continue
            v0, v1 = mesh.edge_vertices(eid)
            f0, f1 = faces
            if mesh.corner_uv(f0, v0) == mesh.corner_uv(f1, v0) and mesh.corner_uv(f0, v1) == mesh.corner_uv(f1, v1):
                r0, r1 = find(f0), find(f1)
                if r0 != r1:
                    parent[r0] = r1
            else:
                seams += 1
    return len({find(f) for f in mapped}), seams


def check(mesh: Mesh, resolution: int = DEFAULT_RESOLUTION) -> UVHealth:
    """The UV check of `mesh` (module docstring). Read-only."""
    faces = mesh.all_face_ids()
    if not mesh.has_face_uvs():
        return UVHealth(len(faces), 0, (), (), (), (), 0.0, 0.0, 0, 0, None, resolution)
    unmapped, zero, outside, mapped = [], [], [], []
    densities = []
    count = np.zeros(resolution * resolution, dtype=np.uint16)
    used_mask = np.zeros(resolution * resolution, dtype=bool)
    texels: dict[FaceId, np.ndarray] = {}
    for fid in faces:
        uvs = mesh.face_uvs(fid)
        if uvs is None:
            unmapped.append(fid)
            continue
        mapped.append(fid)
        if any(not (-_OUTSIDE_EPS <= c <= 1.0 + _OUTSIDE_EPS) for uv in uvs for c in uv):
            outside.append(fid)
        area = _polygon_area(uvs)
        if area < ZERO_AREA:
            zero.append(fid)
            continue
        surface = _surface_area(mesh, fid)
        if surface > 0.0:
            densities.append(math.sqrt(area / surface) * resolution)
        corner = dict(zip(mesh.face_vertices(fid), uvs))
        parts, inner = [], []
        for a, b, c in triangulate_mesh_face(mesh, fid):
            raster = raster_triangle(corner[a], corner[b], corner[c], resolution, resolution)
            if raster is not None:
                flat, w1, w2 = raster
                parts.append(flat)
                inner.append(flat[np.minimum(np.minimum(w1, w2), 1.0 - w1 - w2) > _STRICT_EPS])
        if parts:
            used_mask[np.concatenate(parts)] = True  # with edges: the coverage
            own = np.unique(np.concatenate(inner))  # strict: a UV edge shared with a neighbour is no overlap
            texels[fid] = own
            count[own] += 1
    shared = count > 1
    overlapping = tuple(f for f, own in texels.items() if shared[own].any())
    used = int(np.count_nonzero(used_mask))
    islands, seams = _islands_and_seams(mesh, mapped)
    density = None
    if densities:
        p5, p50, p95 = np.percentile(np.asarray(densities), (5, 50, 95))
        density = (float(p5), float(p50), float(p95))
    return UVHealth(
        faces=len(faces), mapped=len(mapped), unmapped=tuple(unmapped), zero_area=tuple(zero),
        overlapping=overlapping, outside=tuple(outside),
        overlap_share=(int(np.count_nonzero(shared)) / used) if used else 0.0,
        coverage=used / (resolution * resolution), islands=islands, seams=seams, density=density,
        resolution=resolution,
    )
