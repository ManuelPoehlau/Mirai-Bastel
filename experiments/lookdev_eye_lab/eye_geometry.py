"""The synthetic eye of the Eye Proof (D-L2, Manu 2026-11-13: "kontrollierte Geometrie") and its reference spheres,
as `core.Mesh` objects, plus the iris image (GL-free).

Units: 1 = the sclera radius (12 mm). The eye looks down +Z, centred at the origin.

| Part | Shape | Real eye |
|---|---|---|
| sclera | sphere of radius 1, **open at the limbus**: polar axis = +Z, the front cap (polar angle < `limbus` angle) removed, so the ring of the opening is the limbus circle and the front pole fan does not exist (audit §5.2 wanted no pole fan in the iris area; removing the cap achieves that and leaves the iris visible). The back pole is out of view. | 24 mm |
| cornea | spherical cap, radius `CORNEA_RADIUS`, centre on +Z, its rim = the sclera's limbus ring (same positions) | radius of curvature 7.8 mm, limbus diameter 11.8 mm |
| iris | a slightly concave annulus (the pupil edge sits `IRIS_CONCAVITY` behind the root) from the pupil to just inside the sclera wall (the root ring stays inside the sphere), plus a short pupil tube and a black pupil floor, so the pupil has depth and never shows the background | pupil 3.8 mm |
| chrome / grey | spheres of radius 0.6 beside the eye (research §10 reference spheres) | - |

Planar UVs on the iris (`u = 0.5 + x / (2 R)`, `v = 0.5 + y / (2 R)`, R = the iris root radius): the iris image is shown
through the production face-corner UV path (`Mesh.set_face_uvs` -> `RenderMesh` triangle UVs -> the store's texture),
audit Q4. The tube and the floor map to the image centre (black).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from core import Mesh

from lookdev_gpu_probe import cube_math as cm

SCLERA_RADIUS = 1.0
LIMBUS_RADIUS = 0.49
CORNEA_RADIUS = 0.65
LIMBUS_Z = math.sqrt(SCLERA_RADIUS ** 2 - LIMBUS_RADIUS ** 2)
CORNEA_CENTRE_Z = LIMBUS_Z - math.sqrt(CORNEA_RADIUS ** 2 - LIMBUS_RADIUS ** 2)
CORNEA_APEX_Z = CORNEA_CENTRE_Z + CORNEA_RADIUS
IRIS_ROOT_Z = 0.80
# Just inside the sclera wall at the root's depth: a root outside the sphere pokes through the sclera as a dark ring
# (seen 2026-11-14 with + 0.01); the 0.002 gap is hidden behind the limbus rim.
IRIS_RADIUS = math.sqrt(SCLERA_RADIUS ** 2 - IRIS_ROOT_Z ** 2) - 0.002
PUPIL_RADIUS = 0.16
IRIS_CONCAVITY = 0.03
PUPIL_DEPTH = 0.06
SEGMENTS = 64
REFERENCE_RADIUS = 0.6
CHROME_CENTRE = (-2.3, 0.0, 0.0)
GREY_CENTRE = (2.3, 0.0, 0.0)
IRIS_IMAGE_SIZE = 512

PARTS = ("sclera", "iris", "cornea", "chrome", "grey")


def _ring(radius: float, z: float, segments: int, phase: float = 0.0) -> list[tuple[float, float, float]]:
    return [(radius * math.cos(2.0 * math.pi * k / segments + phase), radius * math.sin(2.0 * math.pi * k / segments
             + phase), z) for k in range(segments)]


def _strip(mesh: Mesh, inner: list, outer: list, uv_inner=None, uv_outer=None) -> None:
    """Quads between two rings of equal length; `outer` is the next ring away from the front. Faces wind
    counter-clockwise seen from the side the normal points to (Newell -> outward for the sphere parts)."""
    n = len(inner)
    for k in range(n):
        k2 = (k + 1) % n
        ids = [inner[k], outer[k], outer[k2], inner[k2]]
        uvs = None
        if uv_inner is not None:
            uvs = [uv_inner[k], uv_outer[k], uv_outer[k2], uv_inner[k2]]
        mesh.add_face(ids, uvs=uvs, infer_uvs=False)


def _sphere_band(mesh: Mesh, centre, radius: float, theta0: float, theta1: float, rings: int, segments: int,
                 close_back: bool) -> list:
    """Rings of a +Z-polar sphere from polar angle `theta0` to `theta1` (theta 0 = +Z). Returns the vertex ids of the
    first ring. With `close_back` the last ring is closed by a triangle fan to the -Z pole."""
    cx, cy, cz = centre
    ring_ids = []
    for r in range(rings + 1):
        theta = theta0 + (theta1 - theta0) * r / rings
        s, c = math.sin(theta), math.cos(theta)
        ring_ids.append([mesh.add_vertex((cx + x * s * radius, cy + y * s * radius, cz + c * radius))
                         for x, y in ((math.cos(2 * math.pi * k / segments), math.sin(2 * math.pi * k / segments))
                                      for k in range(segments))])
    for r in range(rings):
        _strip(mesh, ring_ids[r], ring_ids[r + 1])
    if close_back:
        pole = mesh.add_vertex((cx, cy, cz - radius))
        last = ring_ids[-1]
        for k in range(segments):
            mesh.add_face([last[k], pole, last[(k + 1) % segments]])
    return ring_ids[0]


def sclera_mesh(segments: int = SEGMENTS, rings: int = 36) -> Mesh:
    mesh = Mesh()
    theta_l = math.acos(LIMBUS_Z / SCLERA_RADIUS)
    _sphere_band(mesh, (0.0, 0.0, 0.0), SCLERA_RADIUS, theta_l, math.pi * (1.0 - 1.0 / (rings + 1)), rings,
                 segments, close_back=True)
    return mesh


def cornea_mesh(segments: int = SEGMENTS, rings: int = 16) -> Mesh:
    """The cap from the apex to the limbus ring; the apex is one vertex with a fan (tiny triangles at 64 segments)."""
    mesh = Mesh()
    theta_c = math.acos((LIMBUS_Z - CORNEA_CENTRE_Z) / CORNEA_RADIUS)
    apex = mesh.add_vertex((0.0, 0.0, CORNEA_APEX_Z))
    first = _sphere_band(mesh, (0.0, 0.0, CORNEA_CENTRE_Z), CORNEA_RADIUS, theta_c / rings, theta_c, rings - 1,
                         segments, close_back=False)
    for k in range(segments):
        mesh.add_face([apex, first[k], first[(k + 1) % segments]])
    return mesh


def iris_z(radius: float) -> float:
    """The iris surface depth at `radius`: the root at `IRIS_ROOT_Z`, the pupil edge `IRIS_CONCAVITY` further back."""
    t = (IRIS_RADIUS - radius) / (IRIS_RADIUS - PUPIL_RADIUS)
    return IRIS_ROOT_Z - IRIS_CONCAVITY * t


def iris_uv(x: float, y: float) -> tuple[float, float]:
    return 0.5 + x / (2.0 * IRIS_RADIUS), 0.5 + y / (2.0 * IRIS_RADIUS)


def iris_mesh(segments: int = SEGMENTS, rings: int = 12) -> Mesh:
    mesh = Mesh()
    radii = [PUPIL_RADIUS + (IRIS_RADIUS - PUPIL_RADIUS) * r / rings for r in range(rings + 1)]
    rings_xyz = [_ring(radius, iris_z(radius), segments) for radius in radii]
    ids = [[mesh.add_vertex(p) for p in ring] for ring in rings_xyz]
    uvs = [[iris_uv(p[0], p[1]) for p in ring] for ring in rings_xyz]
    # Seen from +Z the annulus winds counter-clockwise like the sphere strips (smaller ring first): normal +Z.
    for r in range(rings):
        _strip(mesh, ids[r], ids[r + 1], uvs[r], uvs[r + 1])
    centre_uv = (0.5, 0.5)
    floor_z = iris_z(PUPIL_RADIUS) - PUPIL_DEPTH
    tube = [mesh.add_vertex(p) for p in _ring(PUPIL_RADIUS, floor_z, segments)]
    black = [centre_uv] * segments
    _strip(mesh, tube, ids[0], black, black)  # floor ring first: the pupil wall faces the axis
    floor_centre = mesh.add_vertex((0.0, 0.0, floor_z))
    for k in range(segments):
        mesh.add_face([tube[k], tube[(k + 1) % segments], floor_centre], uvs=[centre_uv] * 3, infer_uvs=False)
    return mesh


def sphere_mesh(centre, radius: float = REFERENCE_RADIUS, segments: int = 48, rings: int = 32) -> Mesh:
    mesh = Mesh()
    cx, cy, cz = centre
    top = mesh.add_vertex((cx, cy, cz + radius))
    first = _sphere_band(mesh, centre, radius, math.pi / (rings + 1), math.pi * rings / (rings + 1), rings - 1,
                         segments, close_back=True)
    for k in range(segments):
        mesh.add_face([top, first[k], first[(k + 1) % segments]])
    return mesh


def build_parts() -> dict[str, Mesh]:
    return {
        "sclera": sclera_mesh(),
        "iris": iris_mesh(),
        "cornea": cornea_mesh(),
        "chrome": sphere_mesh(CHROME_CENTRE),
        "grey": sphere_mesh(GREY_CENTRE),
    }


# -- the iris image --------------------------------------------------------------------------------------------------


def iris_image(size: int = IRIS_IMAGE_SIZE, seed: int = 7) -> np.ndarray:
    """(size, size, 3) sRGB values in [0, 1]: a procedural iris (radial fibres, a collarette, crypts, a dark limbal
    ring) in planar UV space, black inside the pupil. Row 0 is the image's top row, v = 1 (a PNG is stored top
    down; pyglet's texture has v = 0 at the bottom row)."""
    rng = np.random.default_rng(seed)
    c = (np.arange(size) + 0.5) / size * 2.0 - 1.0
    y, x = np.meshgrid(-c, c, indexing="ij")
    rho = np.sqrt(x * x + y * y)  # 1 = the iris root
    ang = np.arctan2(y, x)
    pupil = PUPIL_RADIUS / IRIS_RADIUS
    limbus = LIMBUS_RADIUS / IRIS_RADIUS
    t = np.clip((rho - pupil) / (limbus - pupil), 0.0, 1.0)
    inner = np.array([0.55, 0.42, 0.22])  # amber collarette
    outer = np.array([0.36, 0.48, 0.55])  # blue-grey stroma
    collarette = 1.0 / (1.0 + np.exp(-(t - 0.35) * 18.0))
    base = inner + (outer - inner) * collarette[..., None]
    fibres = np.zeros_like(rho)
    for k, (freq, amp) in enumerate(((37, 0.10), (71, 0.07), (113, 0.05), (173, 0.035))):
        phase = rng.uniform(0, 2 * math.pi)
        fibres += amp * np.sin(freq * ang + phase + 3.0 * np.sin(2.0 * ang + k) * t)
    crypts = np.zeros_like(rho)
    for _ in range(26):
        ca, ct = rng.uniform(-math.pi, math.pi), rng.uniform(0.2, 0.8)
        da = np.angle(np.exp(1j * (ang - ca)))
        crypts += np.exp(-((da * (pupil + t * (limbus - pupil)) / 0.03) ** 2 + ((t - ct) / 0.06) ** 2))
    shade = 1.0 + fibres - 0.35 * np.clip(crypts, 0.0, 1.0)
    shade *= 1.0 - 0.55 * np.exp(-((t - 1.0) / 0.10) ** 2)  # limbal ring
    shade *= 1.0 - 0.45 * np.exp(-(t / 0.06) ** 2)  # pupillary ruff
    rgb = np.clip(base * shade[..., None], 0.0, 1.0)
    rgb = np.where((rho > limbus * 1.04)[..., None], np.array([0.10, 0.11, 0.13]), rgb)  # hidden behind the sclera
    return np.where((rho < pupil * 1.02)[..., None], np.array([0.012, 0.012, 0.012]), rgb)


def write_iris_png(path: Path) -> Path:
    """The iris image as an 8-bit PNG (written only when missing or different, so the texture cache keeps its key).
    Never the user's own image (`iris_source.CUSTOM_NAME`): that file is only read."""
    path = Path(path)
    if path.name == "iris_custom.png":
        raise ValueError("write_iris_png never writes the custom iris image (iris_source.CUSTOM_NAME)")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.png")
    cm.write_png(tmp, iris_image())
    if path.exists() and path.read_bytes() == tmp.read_bytes():
        tmp.unlink()
    else:
        tmp.replace(path)
    return path
