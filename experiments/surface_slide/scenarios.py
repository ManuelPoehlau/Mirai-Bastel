"""The test scenarios: required geometries x drags, each a `harness.Scenario`. Builders are deterministic (fixed
vertex choices, fixed paths), so a scenario name reproduces its numbers."""

from __future__ import annotations

import math

import numpy as np

from . import geometries as G
from . import mirai_io
from .algorithms import SlideSetup
from .fields import EdgeGraph, mirror_partners, soft_weights, transport_frames
from .harness import Scenario, build_ref, circle_path, line_path, polyline_path
from .refsurf import RefSurface

_I = np.intp
_CACHE: dict = {}


def cached(key, make):
    if key not in _CACHE:
        _CACHE[key] = make()
    return _CACHE[key]


def ref_of(geo: G.Geometry) -> RefSurface:
    return cached(("ref", geo.name), lambda: build_ref(geo.V, geo.faces))


def graph_of(ref: RefSurface) -> EdgeGraph:
    return cached(("graph", id(ref)), lambda: EdgeGraph(ref.nv, ref.edges, ref.V))


def soft_setup(ref: RefSurface, seeds, radius: float, pivot_vertex: int | None = None, nbr=None) -> SlideSetup:
    """Seeds plus their geodesic `smooth` falloff, with the tangent transport from the pivot (default: first seed)."""
    graph = graph_of(ref)
    verts, w = soft_weights(graph, seeds, radius)
    pivot_vertex = int(seeds[0]) if pivot_vertex is None else int(pivot_vertex)
    pivot = int(np.flatnonzero(verts == pivot_vertex)[0])
    transport = transport_frames(ref, graph, pivot_vertex, verts)
    return SlideSetup.from_vertices(ref, verts, w, pivot, transport, nbr)


def rigid_setup(ref: RefSurface, centre: int, depth: int = 3) -> SlideSetup:
    """A patch of `depth` rings, every vertex with weight 1 (no falloff): what a plain multi-vertex selection is."""
    graph = graph_of(ref)
    verts = ring(ref, centre, depth)
    pivot = int(np.flatnonzero(verts == centre)[0])
    return SlideSetup.from_vertices(ref, verts, np.ones(len(verts)), pivot, transport_frames(ref, graph, centre, verts))


def nearest_vertex(ref: RefSurface, point) -> int:
    return int(np.argmin(np.linalg.norm(ref.V - np.asarray(point, dtype=np.float64), axis=1)))


def ring(ref: RefSurface, v: int, depth: int = 1) -> np.ndarray:
    """`v` and its neighbours over visible edges up to `depth` rings."""
    graph = graph_of(ref)
    seen = {int(v)}
    front = [int(v)]
    for _ in range(depth):
        nxt = []
        for a in front:
            for i in range(graph.ptr[a], graph.ptr[a + 1]):
                b = graph.nbr[i]
                if b not in seen:
                    seen.add(b)
                    nxt.append(b)
        front = nxt
    return np.array(sorted(seen), dtype=_I)


# --- A. sphere ----------------------------------------------------------------------------------------------------------

def sphere_geo(n: int = 16) -> G.Geometry:
    return cached(("cube_sphere", n), lambda: G.cube_sphere(n))


def sphere_truth(geo: G.Geometry):
    an = geo.analytic

    def truth(setup: SlideSetup, delta: np.ndarray) -> np.ndarray:
        t = an.tangent(setup.p0, np.broadcast_to(delta, setup.p0.shape)) * setup.weights[:, None]
        return an.exp(setup.p0, t)

    return truth


def sphere_probes(ref: RefSurface, count: int = 48) -> np.ndarray:
    """Independent probe vertices spread over the sphere, including the eight valence-3 cube corners."""
    corners = np.flatnonzero(ref.valence == np.min(ref.valence))
    rng = np.random.default_rng(7)
    rest = rng.choice(ref.nv, size=count, replace=False)
    return np.unique(np.r_[corners, rest]).astype(_I)


def sphere_scenarios() -> list[Scenario]:
    out = []
    geo = sphere_geo(16)
    ref = ref_of(geo)
    probes = sphere_probes(ref)
    setup = SlideSetup.from_vertices(ref, probes)
    truth = sphere_truth(geo)
    h = ref.mean_edge
    for name, delta in (("x", (1.0, 0.0, 0.0)), ("diag", (0.6, 0.5, 0.62)), ("y", (0.0, 1.0, 0.0))):
        d = np.array(delta) / np.linalg.norm(delta)
        out.append(Scenario(f"A1_sphere_probes_{name}_3edges", ref, setup, line_path(3.0 * h * d, 12), geo.analytic,
                            truth, notes="48 independent vertices (cube corners included), w = 1, drag 3 edge lengths"))
        out.append(Scenario(f"A2_sphere_probes_{name}_large", ref, setup, line_path(1.2 * d, 40), geo.analytic, truth,
                            notes="same probes, drag 1.2 R (about 13 edge lengths)"))
    # a soft patch on a face centre and on a cube corner, tangential drag in two directions
    for where, point in (("face", (0.0, 0.0, 1.0)), ("corner", (1.0, 1.0, 1.0))):
        v = nearest_vertex(ref, np.array(point) / np.linalg.norm(point))
        seeds = ring(ref, v, 1)
        s = soft_setup(ref, [v] + [int(x) for x in seeds if x != v], 0.6, v)
        n0 = s.n0[s.pivot]
        e1 = np.cross(n0, [0.0, 1.0, 0.3])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(n0, e1)
        for dname, d in (("u", e1), ("v", e2)):
            out.append(Scenario(f"A3_sphere_patch_{where}_{dname}", ref, s, line_path(0.35 * d, 20), geo.analytic,
                                notes=f"soft patch at a {where} (seeds = vertex + 1 ring, radius 0.6, {s.n} vertices),"
                                      " tangential drag 0.35 R"))
        out.append(Scenario(f"A4_sphere_patch_{where}_oblique", ref, s,
                            line_path(0.35 * (0.6 * e1 + 0.8 * n0), 20), geo.analytic,
                            notes="the same patch, drag with a large normal component (53 degrees off the tangent plane)"))
        r = rigid_setup(ref, v, 3)
        for dist in (3, 8):
            out.append(Scenario(f"A5_sphere_rigid_{where}_{dist}edges", ref, r, line_path(dist * h * e1, 4 * dist),
                                geo.analytic,
                                notes=f"3-ring patch, all weights 1 ({r.n} vertices, diameter about 6 edges), drag "
                                      f"{dist} edge lengths tangent at the pivot"))
    return out


# --- B. cylinder / capsule ------------------------------------------------------------------------------------------------

def cylinder_scenarios() -> list[Scenario]:
    out = []
    geo = cached("cyl", lambda: G.cylinder(32, 20, 1.0, 4.0))
    ref = ref_of(geo)
    an = geo.analytic

    def truth(setup: SlideSetup, delta: np.ndarray) -> np.ndarray:
        t = an.tangent(setup.p0, np.broadcast_to(delta, setup.p0.shape)) * setup.weights[:, None]
        return an.exp(setup.p0, t)

    mid = [r * 32 + s for r in (8, 10, 12) for s in range(0, 32, 2)]
    setup = SlideSetup.from_vertices(ref, mid)
    for name, delta in (("axial", (0.0, 0.8, 0.0)), ("circ", (0.0, 0.0, 0.8)), ("helix", (0.0, 0.6, 0.6))):
        out.append(Scenario(f"B1_cylinder_probes_{name}", ref, setup, line_path(delta, 24), an, truth,
                            notes="48 independent barrel vertices all round the tube, w = 1, world-space drag 0.8 R"))
    v = 10 * 32
    s = soft_setup(ref, [v] + [int(x) for x in ring(ref, v, 1) if x != v], 0.9, v)
    for name, delta in (("axial", (0.0, 0.6, 0.0)), ("circ", (0.0, 0.0, 0.6)), ("helix", (0.0, 0.45, 0.45))):
        out.append(Scenario(f"B2_cylinder_patch_{name}", ref, s, line_path(delta, 20), an,
                            notes=f"soft patch on the barrel (radius 0.9 R, {s.n} vertices), drag tangent at the pivot"))

    r = rigid_setup(ref, v, 3)
    for name, delta in (("axial", (0.0, 0.6, 0.0)), ("circ", (0.0, 0.0, 0.6)), ("helix", (0.0, 0.45, 0.45))):
        out.append(Scenario(f"B5_cylinder_rigid_{name}", ref, r, line_path(delta, 20), an,
                            notes=f"3-ring patch, all weights 1 ({r.n} vertices), drag 0.6 R tangent at the pivot"))

    cap = cached("capsule", lambda: G.capsule(32, 12, 8, 1.0, 1.5))
    cref = ref_of(cap)
    can = cap.analytic
    seg = 32
    barrel_top = 1 + 8 * seg          # first barrel ring below the upper cap seam (ring index 8)
    probes = [1 + r * seg + s for r in (7, 8, 9) for s in range(0, seg, 4)]
    cs = SlideSetup.from_vertices(cref, probes)
    out.append(Scenario("B3_capsule_probes_barrel_to_cap", cref, cs, line_path((0.0, 1.2, 0.0), 30), can,
                        notes="vertices around the barrel / cap transition dragged along the axis onto the cap"))
    out.append(Scenario("B3_capsule_probes_circ_at_transition", cref, cs, line_path((0.0, 0.0, 0.9), 30), can,
                        notes="the same vertices dragged sideways along the transition"))
    v = barrel_top
    ps = soft_setup(cref, [v] + [int(x) for x in ring(cref, v, 1) if x != v], 0.9, v)
    for name, delta in (("up", (0.0, 0.7, 0.0)), ("down", (0.0, -0.7, 0.0)), ("diag", (0.0, 0.5, 0.5))):
        out.append(Scenario(f"B4_capsule_patch_{name}", cref, ps, line_path(delta, 20), can,
                            notes=f"soft patch astride the transition (radius 0.9 R, {ps.n} vertices)"))
    return out


# --- C. concave U ----------------------------------------------------------------------------------------------------------

def u_geo(gap: float, bend: int, cell: float = 0.1) -> G.Geometry:
    return cached(("u", gap, bend, cell), lambda: G.u_shape(gap, 2.0, 2.0, cell, bend))


def u_region(geo: G.Geometry, ref: RefSurface):
    an = geo.analytic

    def region(tri, bary, pos):
        return an.wall(an.anchor_sy(ref.V, ref.T, tri, bary)[:, 0])

    return region


def u_truth_project(geo: G.Geometry, ref: RefSurface):
    """Exact end points of the per-point projected drag on the polyhedral U: a straight line in the unrolled chart."""
    an = geo.analytic

    def truth(setup: SlideSetup, delta: np.ndarray) -> np.ndarray:
        sy0 = an.anchor_sy(ref.V, ref.T, setup.tri0, setup.bary0)
        t = (delta[None, :] - (setup.n0 @ delta)[:, None] * setup.n0) * setup.weights[:, None]
        e_s, e_y = an.frame(sy0[:, 0])
        # a vertex on a profile node has two adjacent segments; its tangent plane (vertex normal) splits them
        e_s2, _ = an.frame(np.maximum(sy0[:, 0] - 1e-9, 0.0))
        e_mid = e_s + e_s2
        e_mid /= np.linalg.norm(e_mid, axis=1, keepdims=True)
        ds = np.einsum("ij,ij->i", t, e_mid) / np.einsum("ij,ij->i", e_mid, e_s)
        sy = sy0 + np.stack([ds, t[:, 1]], axis=1)
        return an.point(sy)

    return truth


def u_scenarios() -> list[Scenario]:
    out = []
    for gap, bend, tag in ((0.3, 8, "gap3cells"), (0.1, 4, "gap1cell")):
        geo = u_geo(gap, bend)
        ref = ref_of(geo)
        region = u_region(geo, ref)
        truth = u_truth_project(geo, ref)
        # wall A, mid height: profile nodes 8..12 (z = 1.2 .. 0.8), rows 6..14
        verts = np.array([G.u_vertex(geo, i, r) for i in range(8, 13) for r in range(6, 15, 2)], dtype=_I)
        setup = SlideSetup.from_vertices(ref, verts)
        expect = np.zeros(setup.n, dtype=_I)
        for psi in (30, 60, 80):
            a = math.radians(psi)
            d = np.array([math.sin(a), 0.0, math.cos(a)])      # up the wall and into the gap
            out.append(Scenario(f"C1_u_{tag}_into_gap_{psi}deg", ref, setup, line_path(0.6 * d, 30), geo.analytic,
                                truth, region, expect,
                                notes=f"wall A vertices, drag 0.6 at {psi} deg off the wall towards the opposite wall "
                                      f"(gap {gap}); they must stay on wall A"))
        d = np.array([0.5, 0.8, 0.0])
        out.append(Scenario(f"C2_u_{tag}_along_y_into_gap", ref, setup, line_path(0.7 * d / np.linalg.norm(d), 30),
                            geo.analytic, truth, region, expect,
                            notes="drag along the extrusion with a component into the gap"))
        # around the bend: legitimately changes wall, along the surface
        low = np.array([G.u_vertex(geo, 17, r) for r in range(6, 15, 2)], dtype=_I)     # 3 cells above the bend
        ls = SlideSetup.from_vertices(ref, low)
        out.append(Scenario(f"C3_u_{tag}_around_bend", ref, ls, line_path((0.0, 0.0, -1.0), 40), geo.analytic, truth,
                            notes="wall A vertices 3 cells above the bend dragged 1.0 straight down: the surface path "
                                  "runs through the bend and up wall B"))
        # soft patch astride the bend
        v = G.u_vertex(geo, 19, 10)
        s = soft_setup(ref, [v], 0.6, v)
        out.append(Scenario(f"C4_u_{tag}_soft_patch_down", ref, s, line_path((0.0, 0.0, -0.4), 20), geo.analytic,
                            notes=f"one seed near the bend, geodesic radius 0.6 reaching round the bend ({s.n} "
                                  "vertices), dragged down"))
        out.append(Scenario(f"C4_u_{tag}_soft_patch_into_gap", ref, s, line_path((0.35, 0.2, -0.1), 20), geo.analytic,
                            notes="the same patch, dragged mostly into the gap"))
    # sharp creases: one or two bend segments
    for bend in (1, 2):
        geo = u_geo(0.3, bend)
        ref = ref_of(geo)
        truth = u_truth_project(geo, ref)
        low = np.array([G.u_vertex(geo, 19, r) for r in range(6, 15, 2)], dtype=_I)     # 1 cell above the crease
        ls = SlideSetup.from_vertices(ref, low)
        out.append(Scenario(f"C5_u_sharp{bend}_across_crease", ref, ls, line_path((0.0, 0.0, -0.5), 30), geo.analytic,
                            truth, notes=f"bend made of {bend} segment(s) (sharp creases); vertices 1 cell above "
                                         "the crease dragged 0.5 down across it"))
    return out


# --- D. Gollum -------------------------------------------------------------------------------------------------------------

def gollum_cage_ref(symmetric: bool = True):
    """The cage with its declared symmetry. `symmetric` (default): the triangulation is mirrored across the plane,
    as the report recommends for Production; False keeps the per-face rules (to measure what that costs)."""
    def make():
        m = mirai_io.gollum_cage()
        partner = mirror_partners(m.V, *m.plane) if symmetric else None
        return m, build_ref(m.V, m.faces, partner)

    return cached(("gollum_cage", symmetric), make)


def gollum_hires_ref():
    def make():
        m = mirai_io.gollum_hires()
        return m, build_ref(m.V, m.faces)

    return cached("gollum_hires", make)


def front_vertex(ref: RefSurface, x: float, y: float, radius: float | None = None) -> int:
    """The front-most (+z) vertex near (x, y) seen from the front."""
    radius = 1.5 * ref.mean_edge if radius is None else radius
    d = np.hypot(ref.V[:, 0] - x, ref.V[:, 1] - y)
    near = np.flatnonzero((d < radius) & (ref.VN[:, 2] > 0.0))
    if not len(near):
        near = np.flatnonzero(d < 3.0 * radius)
    best = near[np.argmax(ref.V[near, 2] - 2.0 * d[near])]
    return int(best)


#: Feature points picked on the front renders (debug pictures `gollum_*_regions.png`): (x, y) seen from the front,
#: on the +x half (the side the symmetry normal points to).
CAGE_FEATURES = {
    "cheek": (0.20, 0.29),
    "forehead": (0.10, 0.68),
    "brow": (0.16, 0.56),
    "eye_rim_low": (0.16, 0.43),
    "nose_side": (0.07, 0.36),
    "upper_lip": (0.06, 0.20),
    "temple": (0.27, 0.52),
}
HIRES_FEATURES = {
    "cheek": (0.21, 0.02),
    "forehead": (0.10, 0.33),
    "brow": (0.14, 0.20),
    "eye_rim_low": (0.15, 0.10),
    "nose_side": (0.06, 0.03),
    "upper_lip": (0.04, -0.125),
    "temple": (0.27, 0.17),
}

#: Front view: the eye looks along -z; a screen drag is a vector in the x / y plane.
VIEW_FRONT = np.array([0.0, 0.0, -1.0])


def gollum_scenarios(which: str = "cage") -> list[Scenario]:
    mesh, ref = gollum_cage_ref() if which == "cage" else gollum_hires_ref()
    feats = CAGE_FEATURES if which == "cage" else HIRES_FEATURES
    h = ref.mean_edge
    size = 1.0
    out = []
    drags = {
        # (feature, screen drag in head units, description)
        "cheek_to_eye": ("cheek", (-0.02, 0.16), "cheek patch dragged up towards the eye socket"),
        "cheek_to_ear": ("cheek", (0.18, 0.04), "cheek patch dragged sideways round the head"),
        "forehead_down": ("forehead", (0.03, -0.16), "forehead patch dragged down over the brow"),
        "forehead_side": ("forehead", (0.18, 0.0), "forehead patch dragged sideways"),
        "brow_into_socket": ("brow", (0.0, -0.10), "brow patch dragged down into the eye socket"),
        "eye_rim_up": ("eye_rim_low", (0.0, 0.10), "lower eye rim dragged up across the eye opening"),
        "nose_to_cheek": ("nose_side", (0.14, 0.0), "side of the nose dragged out over the nose / cheek crease"),
        "lip_down": ("upper_lip", (0.0, -0.09), "upper lip dragged down across the mouth line"),
        "temple_to_eye": ("temple", (-0.12, -0.04), "temple dragged towards the eye"),
    }
    radius = 0.09 * size
    for name, (feat, drag, text) in drags.items():
        v = front_vertex(ref, *feats[feat])
        s = soft_setup(ref, [v], radius, v)
        delta = np.array([drag[0], drag[1], 0.0]) * size
        out.append(Scenario(f"D_{which}_{name}", ref, s, line_path(delta, 30),
                            notes=f"{text}; one seed, geodesic radius {radius:.3f} ({s.n} vertices), screen-plane drag "
                                  f"{np.linalg.norm(delta) / h:.1f} mean edges, front view",
                            tags={"feature": feat, "seed": v, "view": "front"}))
    for feat, drag in (("cheek", (0.0, 0.08)), ("forehead", (0.08, 0.0)), ("brow", (0.0, -0.06))):
        v = front_vertex(ref, *feats[feat])
        r = rigid_setup(ref, v, 2 if which == "cage" else 5)
        delta = np.array([drag[0], drag[1], 0.0])
        out.append(Scenario(f"D_{which}_{feat}_rigid", ref, r, line_path(delta, 20),
                            notes=f"patch around the {feat}, all weights 1 ({r.n} vertices), screen drag "
                                  f"{np.linalg.norm(delta) / h:.1f} mean edges",
                            tags={"feature": feat, "seed": v, "view": "front"}))
    # one closed loop per region: stability / closure
    for feat in ("cheek", "brow", "nose_side"):
        v = front_vertex(ref, *feats[feat])
        s = soft_setup(ref, [v], radius, v)
        out.append(Scenario(f"D_{which}_{feat}_loop", ref, s,
                            circle_path((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 0.05 * size, 48),
                            notes=f"closed circular screen drag (diameter {0.1 * size / h:.1f} mean edges) at the "
                                  f"{feat}, {s.n} vertices",
                            tags={"feature": feat, "seed": v, "view": "front"}))
    return out


def all_scenarios(include_hires: bool = True) -> list[Scenario]:
    out = sphere_scenarios() + cylinder_scenarios() + u_scenarios() + gollum_scenarios("cage")
    if include_hires:
        out += gollum_scenarios("hires")
    return out
