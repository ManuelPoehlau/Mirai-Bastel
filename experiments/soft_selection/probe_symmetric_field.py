"""Headless probe SS0 for symmetric Soft Selection (AD-SYM-04 §5.2, SS0). PROVISIONAL name.

Usage (from the repo root, Windows and Linux alike; no window, no GL, no pyglet):
    python experiments/soft_selection/probe_symmetric_field.py
    python experiments/soft_selection/probe_symmetric_field.py --assets subd_cube --radii 5 15 50
    python experiments/soft_selection/probe_symmetric_field.py --skip-cost
    python experiments/soft_selection/probe_symmetric_field.py --help

Pure measurement. Reads `src/` only (`mirai.soft_selection.influence`, `mirai.symmetry`,
`mirai.symmetry_axis`); nothing here is a candidate for `src/`, nothing is tuned to pass,
no tolerance is introduced. Every comparison is exact (`==`); where two values differ the
probe counts them and reports the size of the difference (absolute, and in ulp when both
are non-zero). Four questions (AD-SYM-04 §5.1 / §5.2):

1. D-1  The field over seeds + mirrored seeds (`compute_influence` on the union, weight from
        the nearest seed, no summing) against (a) its two members of a pair, (b) each side's
        own field (`compute_influence` on the seeds / on the mirrored seeds alone), (c) a seam
        vertex seen from both sides. Per asset, axis X/Y/Z, both metrics, over the radius
        steps of the app (`RADIUS_STEPS_PERCENT`), seeds off the plane (near / mid / far /
        ring). Meshes that are not `valid` (`partial`) are only counted, not judged (D-2).
2. R-6  Edges that cross the plane with neither end on it (the precondition of the geodesic
        half of D-1), per asset and axis, plus a hand-built exactly symmetric mesh that has
        such an edge.
3. D-3  How often the influence reaches a seam vertex, per radius step (basis of P-a in SS1).
4. Cost Correspondence + mirrored seeds + influence per gesture start, symmetric against
        today (container numbers must be labelled as such; the reference PC decides).

Exit code 1 and a `STOP` block (smallest counterexample) if D-1 fails on a `valid` mesh whose
precondition holds; exit code 0 otherwise. Output is plain ASCII.
"""

from __future__ import annotations

import argparse
import math
import statistics
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Stage 0 (script start): experiments/ on sys.path, as in probe_cost.py.
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from soft_selection._paths import ensure_paths  # noqa: E402

ensure_paths()

from core import Mesh, VertexId  # noqa: E402
from loaders.assets import asset_names, asset_path  # noqa: E402
from mirai.mesh_geometry import mesh_center_and_radius  # noqa: E402
from mirai.scene_factory import (  # noqa: E402
    build_core_scene_from_obj,
    mesh_from_positions_and_faces,
)
from mirai.soft_selection.influence import METRICS, compute_influence  # noqa: E402
from mirai.soft_selection.settings import (  # noqa: E402
    DEFAULT_CURVE,
    RADIUS_STEPS_PERCENT,
)
from mirai.symmetry import (  # noqa: E402
    CorrespondenceState,
    SymmetryState,
    mirrored_selection,
    symmetry_state,
    vertex_correspondence,
)
from mirai.symmetry_axis import AXIS_INDEX, set_symmetry_axis  # noqa: E402

from soft_selection.probe_cost import machine_info  # noqa: E402

DEFAULT_ASSETS = ("subd_cube", "head_basemesh", "man_with_shoes_basemesh")
AXES = ("X", "Y", "Z")
METRIC_NAMES = ("euclidean", "geodesic")
SEED_KINDS = ("near", "mid", "far", "ring")
COST_FRACTIONS = (0.05, 0.15, 0.30)  # same rows as probe_cost.py
DEFAULT_REPEAT = 5

_PAIRED = CorrespondenceState.PAIRED
_SEAM = CorrespondenceState.SEAM
_UNPAIRED = CorrespondenceState.UNPAIRED


# --- Exact comparison -------------------------------------------------------------

def _ordered_bits(x: float) -> int:
    i = struct.unpack("<q", struct.pack("<d", x))[0]
    return i if i >= 0 else -(2**63) - i


def ulp_distance(a: float, b: float) -> int:
    """Number of representable doubles between `a` and `b` (both finite)."""
    return abs(_ordered_bits(a) - _ordered_bits(b))


@dataclass
class Diff:
    """Exact comparison of pairs of values: how many were checked, how many differ, by how much."""

    checked: int = 0
    bad: int = 0
    max_abs: float = 0.0
    max_ulp: int = 0
    first: str = ""  # first (lowest key) mismatch, for the counterexample

    def add(self, key: str, x: float, y: float) -> None:
        self.checked += 1
        if x == y:
            return
        self.bad += 1
        if math.isfinite(x) and math.isfinite(y):
            self.max_abs = max(self.max_abs, abs(x - y))
            if x != 0.0 and y != 0.0:
                self.max_ulp = max(self.max_ulp, ulp_distance(x, y))
        else:
            self.max_abs = math.inf
        if not self.first:
            self.first = f"{key}: {x!r} vs {y!r}"

    def merge(self, other: "Diff") -> None:
        self.checked += other.checked
        self.bad += other.bad
        self.max_abs = max(self.max_abs, other.max_abs)
        self.max_ulp = max(self.max_ulp, other.max_ulp)
        if not self.first:
            self.first = other.first

    def cell(self) -> str:
        if self.checked == 0:
            return "-"
        if self.bad == 0:
            return f"0/{self.checked}"
        ulp = f" {self.max_ulp}ulp" if self.max_ulp else ""
        return f"{self.bad}/{self.checked} max|d|={self.max_abs:.3g}{ulp}"


# --- Geometry of one (mesh, axis) -------------------------------------------------

@dataclass
class Geometry:
    asset: str
    axis: str
    state: SymmetryState
    counts: dict[str, int]
    seam_edges: int
    straddling: int          # edges with the end points strictly on opposite sides
    onplane_not_seam: int    # vertices with position == 0 on the axis that are no seam end point
    edge_asymmetric: int     # edges whose mirror image is not an edge (testable edges only)
    edge_untestable: int     # edges with an unpaired / ambiguous end point
    pairs: int

    @property
    def precondition(self) -> bool:
        """What the geodesic half of D-1 needs on a valid mesh (review R-6, plus edge symmetry)."""
        return self.straddling == 0 and self.edge_asymmetric == 0


def analyse_geometry(asset: str, mesh: Mesh, axis: str, corr) -> Geometry:
    i = AXIS_INDEX[axis]
    counts = {s.value: 0 for s in CorrespondenceState}
    for c in corr.values():
        counts[c.state.value] += 1
    seam_vertices = {v for v, c in corr.items() if c.state is _SEAM}
    image = {v: (v if c.state is _SEAM else c.partner)
             for v, c in corr.items() if c.state in (_SEAM, _PAIRED)}
    edges = {frozenset(mesh.edge_vertices(e)) for e in mesh.all_edge_ids()}
    straddling = asymmetric = untestable = 0
    for edge in edges:
        a, b = tuple(edge)
        if mesh.vertex_position(a)[i] * mesh.vertex_position(b)[i] < 0.0:
            straddling += 1
        if a not in image or b not in image:
            untestable += 1
        elif frozenset((image[a], image[b])) not in edges:
            asymmetric += 1
    onplane = sum(
        1 for v in mesh.all_vertex_ids()
        if mesh.vertex_position(v)[i] == 0.0 and v not in seam_vertices
    )
    return Geometry(
        asset, axis, symmetry_state(mesh), counts,
        len(mesh.symmetry_definition.seam_edges), straddling, onplane, asymmetric, untestable,
        counts[_PAIRED.value] // 2,
    )


# --- Seeds off the plane ----------------------------------------------------------

def pick_seed_sets(mesh: Mesh, axis: str, corr) -> dict[str, set[VertexId]]:
    """Seeds on the positive side, each with a partner (D-2 would refuse a seed without one).

    near = smallest distance to the plane (so the falloff reaches the middle early), mid =
    median, far = largest, ring = mid plus its paired same-side one-ring. Empty dict if the
    asset has no pair at all (then symmetric Soft is refused anyway)."""
    i = AXIS_INDEX[axis]
    side = sorted(
        (mesh.vertex_position(v)[i], int(v), v)
        for v, c in corr.items()
        if c.state is _PAIRED and mesh.vertex_position(v)[i] > 0.0
    )
    if not side:
        return {}
    mid = side[len(side) // 2][2]
    ring = {mid}
    for eid in mesh.vertex_edges(mid):
        for w in mesh.edge_vertices(eid):
            c = corr[w]
            if c.state is _PAIRED and mesh.vertex_position(w)[i] > 0.0:
                ring.add(w)
    return {"near": {side[0][2]}, "mid": {mid}, "far": {side[-1][2]}, "ring": ring}


# --- One case: seeds x radius x metric --------------------------------------------

@dataclass
class CaseResult:
    pair_w: Diff = field(default_factory=Diff)     # D-1: both members of a pair
    pair_d: Diff = field(default_factory=Diff)     #      same on the raw distances
    own_w: Diff = field(default_factory=Diff)      # D-1: field == own side's field
    own_d: Diff = field(default_factory=Diff)
    mirror_w: Diff = field(default_factory=Diff)   # own field of side A == mirrored own field of B
    seam_w: Diff = field(default_factory=Diff)     # seam vertex: union vs A vs B
    cross_wins: int = 0                            # union distance strictly shorter than own side's
    cross_first: str = ""
    seam_reached: int = 0                          # D-3: seam vertices with w > 0
    unpaired_reached: int = 0                      # D-2: unpaired vertices inside the falloff
    influenced: int = 0


def _fields(mesh: Mesh, seeds, radius: float, metric: str, curve: str):
    valid = {s for s in seeds if mesh.is_valid_vertex(s)}
    return (
        compute_influence(mesh, valid, radius, metric=metric, curve=curve),
        METRICS[metric](mesh, valid, radius),
    )


def evaluate_case(
    mesh: Mesh, axis: str, corr, seeds: set[VertexId], radius: float, metric: str,
    curve: str = DEFAULT_CURVE,
) -> CaseResult:
    i = AXIS_INDEX[axis]
    mirrors = mirrored_selection(mesh, seeds, corr)
    w_sym, d_sym = _fields(mesh, seeds | mirrors, radius, metric, curve)
    w_a, d_a = _fields(mesh, seeds, radius, metric, curve)
    w_b, d_b = _fields(mesh, mirrors, radius, metric, curve)
    inf = math.inf
    out = CaseResult(influenced=len(w_sym))

    for v, c in corr.items():
        key = f"vertex {int(v)}"
        pos = mesh.vertex_position(v)[i]
        if c.state is _UNPAIRED:
            out.unpaired_reached += v in w_sym
            continue
        if c.state is _PAIRED:
            p = c.partner
            if int(v) < int(p):
                out.pair_w.add(f"pair {int(v)},{int(p)}", w_sym.get(v, 0.0), w_sym.get(p, 0.0))
                out.pair_d.add(f"pair {int(v)},{int(p)}", d_sym.get(v, inf), d_sym.get(p, inf))
            if pos > 0.0:  # v on the seeds' side, p on the mirrored side
                out.mirror_w.add(f"pair {int(v)},{int(p)}", w_a.get(v, 0.0), w_b.get(p, 0.0))
        if c.state is _SEAM:
            out.seam_reached += v in w_sym
            out.seam_w.add(key + " union/A", w_sym.get(v, 0.0), w_a.get(v, 0.0))
            out.seam_w.add(key + " union/B", w_sym.get(v, 0.0), w_b.get(v, 0.0))
            own = [(w_a, d_a), (w_b, d_b)]
        else:
            own = [(w_a, d_a)] if pos > 0.0 else [(w_b, d_b)]
        for w_own, d_own in own:
            out.own_w.add(key, w_sym.get(v, 0.0), w_own.get(v, 0.0))
            out.own_d.add(key, d_sym.get(v, inf), d_own.get(v, inf))
            if d_sym.get(v, inf) < d_own.get(v, inf):
                out.cross_wins += 1
                if not out.cross_first:
                    out.cross_first = (f"{key}: union {d_sym[v]!r} < own side "
                                       f"{d_own.get(v, inf)!r}")
    return out


# --- Aggregation over seeds x radius steps ----------------------------------------

@dataclass
class Aggregate:
    cases: int = 0
    pair_w: Diff = field(default_factory=Diff)
    pair_d: Diff = field(default_factory=Diff)
    own_w: Diff = field(default_factory=Diff)
    own_d: Diff = field(default_factory=Diff)
    mirror_w: Diff = field(default_factory=Diff)
    seam_w: Diff = field(default_factory=Diff)
    cross_wins: int = 0
    unpaired_reached: int = 0
    counter: str = ""  # first failing case, smallest radius first

    def add(self, label: str, r: CaseResult) -> None:
        self.cases += 1
        for name in ("pair_w", "pair_d", "own_w", "own_d", "mirror_w", "seam_w"):
            getattr(self, name).merge(getattr(r, name))
        self.cross_wins += r.cross_wins
        self.unpaired_reached += r.unpaired_reached
        failed = r.pair_w.bad or r.pair_d.bad or r.own_w.bad or r.own_d.bad or r.seam_w.bad
        if failed and not self.counter:
            detail = r.pair_w.first or r.pair_d.first or r.own_w.first or r.own_d.first \
                or r.seam_w.first
            self.counter = f"{label}: {detail}"

    def claim_holds(self, with_own_side: bool) -> bool:
        bad = self.pair_w.bad + self.pair_d.bad + self.seam_w.bad + self.mirror_w.bad
        if with_own_side:
            bad += self.own_w.bad + self.own_d.bad + self.cross_wins
        return bad == 0


@dataclass
class AssetAxisResult:
    geometry: Geometry
    seed_sets: dict[str, set[VertexId]]
    aggregates: dict[str, Aggregate]                        # per metric
    seam_reach: dict[tuple[str, str], list[int]]            # (metric, seed kind) -> per radius


def load_mesh(asset: str) -> Mesh:
    return build_core_scene_from_obj(asset_path(asset)).mesh


def probe_asset_axis(
    asset: str, mesh: Mesh, axis: str, bounding_radius: float, percents: tuple[int, ...]
) -> AssetAxisResult:
    set_symmetry_axis(mesh, axis)
    corr = vertex_correspondence(mesh)
    geometry = analyse_geometry(asset, mesh, axis, corr)
    seed_sets = pick_seed_sets(mesh, axis, corr)
    aggregates = {m: Aggregate() for m in METRIC_NAMES}
    reach: dict[tuple[str, str], list[int]] = {}
    for metric in METRIC_NAMES:
        for kind, seeds in seed_sets.items():
            reach[(metric, kind)] = []
            for percent in percents:
                radius = bounding_radius * percent / 100.0
                result = evaluate_case(mesh, axis, corr, seeds, radius, metric)
                aggregates[metric].add(f"{kind} seeds, {percent}%", result)
                reach[(metric, kind)].append(result.seam_reached)
    set_symmetry_axis(mesh, None)
    return AssetAxisResult(geometry, seed_sets, aggregates, reach)


# --- R-6: a hand-built exactly symmetric mesh with a straddling edge --------------

def straddling_quad() -> Mesh:
    """One quad s -> v' -> v -> a, X axis. Every vertex has its partner (s<->a, v<->v'),
    nothing lies on the plane, so the state is `valid` and the seam is empty; all four edges
    cross the plane. Edge set is mirror-symmetric (s-v' <-> a-v, v'-v <-> v-v', a-s <-> s-a)."""
    positions = [
        (0.5, 0.0, 0.0),   # s
        (-0.1, 1.0, 0.0),  # v'
        (0.1, 1.0, 0.0),   # v
        (-0.5, 0.0, 0.0),  # a
    ]
    return mesh_from_positions_and_faces(positions, [(0, 1, 2, 3)])


def probe_straddling_quad() -> list[str]:
    mesh = straddling_quad()
    set_symmetry_axis(mesh, "X")
    corr = vertex_correspondence(mesh)
    geometry = analyse_geometry("straddling_quad", mesh, "X", corr)
    ids = mesh.all_vertex_ids()
    seeds = {ids[0]}  # s
    lines = [
        f"  synthetic straddling_quad (4 V, X): state {geometry.state.value}, "
        f"seam edges {geometry.seam_edges}, straddling edges {geometry.straddling}, "
        f"edge-asymmetric {geometry.edge_asymmetric}",
        "  radius 2.0, seed s = vertex 0 at x=+0.5 (partner a = vertex 3):",
    ]
    for metric in METRIC_NAMES:
        r = evaluate_case(mesh, "X", corr, seeds, 2.0, metric)
        lines.append(
            f"    {metric:<9} pair {r.pair_w.cell()} (dist {r.pair_d.cell()})   "
            f"own side {r.own_w.cell()} (dist {r.own_d.cell()}, union nearer than own side "
            f"at {r.cross_wins} vertices)"
        )
        if r.own_d.first:
            lines.append(f"              first: {r.own_d.first}")
    return lines


# --- Cost -------------------------------------------------------------------------

@dataclass(frozen=True)
class CostRow:
    fraction: float
    radius: float
    metric: str
    corr_ms: float
    mirror_ms: float
    today_ms: float
    sym_ms: float
    influenced_today: int
    influenced_sym: int


def _median_ms(fn, repeat: int):
    samples, value = [], None
    for _ in range(repeat):
        t0 = time.perf_counter()
        value = fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(samples), value


def probe_cost(asset: str, axis: str, repeat: int) -> tuple[Mesh, int, int, list[CostRow]]:
    mesh = load_mesh(asset)
    _, bounding_radius = mesh_center_and_radius(mesh)
    set_symmetry_axis(mesh, axis)
    corr = vertex_correspondence(mesh)
    seeds = pick_seed_sets(mesh, axis, corr)["ring"]
    rows: list[CostRow] = []
    corr_ms, corr = _median_ms(lambda: vertex_correspondence(mesh), repeat)
    mirror_ms, mirrors = _median_ms(lambda: mirrored_selection(mesh, seeds, corr), repeat)
    union = seeds | mirrors
    for fraction in COST_FRACTIONS:
        radius = fraction * bounding_radius
        for metric in METRIC_NAMES:
            today_ms, today = _median_ms(
                lambda: compute_influence(mesh, seeds, radius, metric=metric), repeat)
            sym_ms, sym = _median_ms(
                lambda: compute_influence(mesh, union, radius, metric=metric), repeat)
            rows.append(CostRow(fraction, radius, metric, corr_ms, mirror_ms, today_ms, sym_ms,
                                len(today), len(sym)))
    return mesh, len(seeds), len(mesh.all_vertex_ids()), rows


def format_cost(asset: str, axis: str, seeds: int, vertices: int, rows: list[CostRow]) -> list[str]:
    lines = [
        f"Asset {asset}, axis {axis}: {vertices} vertices, seeds {seeds} (ring) + {seeds} mirrored",
        "  radius          metric     corr_ms  mirror_ms  today_ms  sym_ms  start_today  start_sym"
        "  ratio  infl_today  infl_sym",
    ]
    for r in rows:
        start_today = r.today_ms
        start_sym = r.corr_ms + r.mirror_ms + r.sym_ms
        lines.append(
            f"  {r.fraction * 100:3.0f}% {r.radius:8.4f}  {r.metric:<9}  {r.corr_ms:7.3f}"
            f"  {r.mirror_ms:9.3f}  {r.today_ms:8.3f}  {r.sym_ms:6.3f}  {start_today:11.3f}"
            f"  {start_sym:9.3f}  {start_sym / start_today:5.2f}  {r.influenced_today:10d}"
            f"  {r.influenced_sym:8d}"
        )
    return lines


# --- Report -----------------------------------------------------------------------

def verdict(geometry: Geometry, agg: Aggregate, metric: str) -> str:
    if not agg.cases:
        return "n.a. (no seed with a partner: symmetric Soft would refuse, D-2)"
    if geometry.state is not SymmetryState.VALID:
        # D-1 is a claim about exact meshes; here: only the pair question of D-2 is counted.
        return "partial: pairs " + ("equal" if agg.pair_w.bad == 0 else "DIFFER")
    # Euclidean needs no precondition; geodesic needs R-6 (no straddling) and edge symmetry.
    own_applies = metric == "euclidean" or geometry.precondition
    holds = agg.claim_holds(with_own_side=own_applies)
    if holds:
        return "HOLDS" + ("" if own_applies else " (pair level; own-side not asserted, precondition false)")
    return "FAILS" if own_applies else "FAILS at pair level"


def format_geometry(results: list[AssetAxisResult]) -> list[str]:
    lines = [
        "asset                    axis  state     paired  seam  unpaired  ambig  seam_edges"
        "  straddling  onplane_noseam  edge_asym  edge_untestable"
    ]
    for r in results:
        g = r.geometry
        lines.append(
            f"{g.asset:<24} {g.axis:<4}  {g.state.value:<8}  {g.counts['paired']:6d}"
            f"  {g.counts['seam']:4d}  {g.counts['unpaired']:8d}  {g.counts['ambiguous']:5d}"
            f"  {g.seam_edges:10d}  {g.straddling:10d}  {g.onplane_not_seam:14d}"
            f"  {g.edge_asymmetric:9d}  {g.edge_untestable:15d}"
        )
    return lines


def format_field(results: list[AssetAxisResult], n_radii: int) -> list[str]:
    lines = [
        "Every cell is bad/checked (exact ==), then the largest |difference| and, if both values "
        "are non-zero, the largest ulp distance.",
        "pair = both members of a pair; own = union field vs the side's own field (cross = vertices "
        "where the union is strictly nearer); seam = a seam vertex, union vs A and vs B;",
        "mirror = own field A vs own field B at the partner. 'w' = weight (curve smooth), "
        "'d' = raw distance. cases = seed sets x radius steps.",
        "",
    ]
    for r in results:
        g = r.geometry
        for metric in METRIC_NAMES:
            agg = r.aggregates[metric]
            lines.append(f"{g.asset} axis {g.axis} ({g.state.value}, pairs {g.pairs}) {metric}: "
                         f"{agg.cases} cases ({len(r.seed_sets)} seed sets x {n_radii} radii)")
            if not agg.cases:
                lines.append(f"    {verdict(g, agg, metric)}")
                continue
            lines.append(f"    pair  w {agg.pair_w.cell()}   d {agg.pair_d.cell()}")
            lines.append(f"    own   w {agg.own_w.cell()}   d {agg.own_d.cell()}   "
                         f"cross {agg.cross_wins}")
            lines.append(f"    seam  w {agg.seam_w.cell()}   mirror w {agg.mirror_w.cell()}   "
                         f"unpaired vertices inside the falloff (summed over cases) "
                         f"{agg.unpaired_reached}")
            lines.append(f"    D-1: {verdict(g, agg, metric)}")
            if agg.counter:
                lines.append(f"    first failing case: {agg.counter}")
    return lines


def format_reach(results: list[AssetAxisResult], percents: tuple[int, ...]) -> list[str]:
    lines = [
        "Seam vertices with w > 0 in the union field, per radius step (percent of the bounding "
        "radius). A seed is never a seam vertex.",
        "asset                    axis metric    seed  seam_total  " + " ".join(f"{p:>4}%" for p in percents),
    ]
    for r in results:
        g = r.geometry
        for (metric, kind), counts in r.seam_reach.items():
            lines.append(
                f"{g.asset:<24} {g.axis:<4} {metric:<9}  {kind:<4}  {g.counts['seam']:10d}  "
                + " ".join(f"{c:5d}" for c in counts)
            )
    cases = [(r, k, c) for r in results for k, c in r.seam_reach.items()]
    reached = sum(1 for _, _, c in cases for x in c if x)
    total = sum(len(c) for _, _, c in cases)
    lines.append(f"cases where the influence reaches the seam: {reached} of {total}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help=f"asset names (registry: {', '.join(asset_names())})")
    parser.add_argument("--axes", nargs="+", default=list(AXES), choices=AXES)
    parser.add_argument("--radii", nargs="+", type=int, default=list(RADIUS_STEPS_PERCENT),
                        help="radius steps in percent of the bounding radius "
                             f"(default: the app's {list(RADIUS_STEPS_PERCENT)})")
    parser.add_argument("--repeat", type=int, default=DEFAULT_REPEAT,
                        help=f"timing runs per cost cell, median reported (default {DEFAULT_REPEAT})")
    parser.add_argument("--skip-cost", action="store_true", help="only the field/seam questions")
    args = parser.parse_args(argv)
    unknown = [a for a in args.assets if a not in asset_names()]
    if unknown:
        parser.error(f"unknown asset(s) {unknown}; valid: {', '.join(asset_names())}")
    if args.repeat < 1 or any(p <= 0 for p in args.radii):
        parser.error("--repeat must be >= 1 and radii > 0")
    percents = tuple(args.radii)

    print("Symmetric Soft Selection field probe SS0 (AD-SYM-04 5.2), CPU only, exact comparisons")
    for line in machine_info():
        print(line)
    print(f"Radius steps (% of bounding radius): {list(percents)}; curve {DEFAULT_CURVE}")

    results: list[AssetAxisResult] = []
    for asset in args.assets:
        mesh = load_mesh(asset)
        _, bounding_radius = mesh_center_and_radius(mesh)
        for axis in args.axes:
            results.append(probe_asset_axis(asset, mesh, axis, bounding_radius, percents))

    print("\n== Geometry per asset and axis (R-6, D-2) ==")
    print("\n".join(format_geometry(results)))
    print("\n== D-1: the field over seeds + mirrored seeds ==")
    print("\n".join(format_field(results, len(percents))))
    print("\n== R-6: a valid mesh with an edge across the plane and no end point on it ==")
    print("\n".join(probe_straddling_quad()))
    print("\n== D-3: how often the influence reaches a seam vertex ==")
    print("\n".join(format_reach(results, percents)))

    if not args.skip_cost:
        print("\n== Cost per gesture start (container, not the reference PC) ==")
        print("corr_ms = vertex_correspondence, mirror_ms = mirrored_selection, today_ms = "
              "compute_influence(seeds), sym_ms = compute_influence(seeds + mirrored seeds);")
        print("start_today = today_ms; start_sym = corr_ms + mirror_ms + sym_ms.")
        for asset in args.assets:
            _, seeds, vertices, rows = probe_cost(asset, "X", args.repeat)
            print()
            print("\n".join(format_cost(asset, "X", seeds, vertices, rows)))

    stops = []
    for r in results:
        g = r.geometry
        if g.state is not SymmetryState.VALID:
            continue
        for metric in METRIC_NAMES:
            agg = r.aggregates[metric]
            own_applies = metric == "euclidean" or g.precondition
            if agg.cases and not agg.claim_holds(with_own_side=own_applies):
                stops.append((g, metric, agg))
    print()
    if stops:
        print("STOP: D-1 does not hold on an exactly symmetric (valid) mesh. Nothing further "
              "is built (AD-SYM-04 5.2, SS0).")
        for g, metric, agg in stops:
            print(f"  {g.asset} axis {g.axis} {metric}: {agg.counter or 'see counts above'}")
        return 1
    print("D-1 holds on every valid case whose precondition holds (see the counts above); "
          "no stop.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
