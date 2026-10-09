"""AD-SYM-03 slice 6b: the symmetric Knife's commit coordinator (`mirai.symmetric_knife.coordinate_knife`),
headless (slice 6c wired it: `CContext.KNIFE` is declared and `Application` passes it, see
`tests/test_symmetric_knife_preview.py`).

What is pinned (the handoff's §5 table):

- equivariance E-a…E-d over a seeded camera-free fuzz, a seam-biased fuzz and a both-sides fuzz on `subd_cube`,
  `head_basemesh` and a tie grid (≥ 300 valid paths each), and on other exact planes (Y, Z, negative normals);
- the regression rows from the Discovery probe as **frozen path data** (`tests/fixtures/symmetric_knife_sessions.json`):
  R1 (two chains, both orders), R8 (crossings through seam vertices), R10 (the K5 side-camera union session),
  R9-type sessions (the ones the plain K-C refused), K7 a–h and the plane-spanning rows, the closed loops, N5;
- the clip's edge cases, each refusal path (the nets are driven with a forged resolver report), the residue
  F4 = A, no duplicate vertices, the cost, the module boundaries, and that the Knife without a coordinator is
  unchanged.

The tests do not import the probe. The golden net (`playground/tests/test_knife_kept_calls_golden.py`),
`tests/test_knife_parity.py` and the 6a tests are separate files and unchanged.
"""

from __future__ import annotations

import ast
import collections
import dataclasses
import random
import statistics
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh
from mirai import symmetric_knife as sk
from mirai import symmetry_declarations
from mirai.symmetric_knife import (
    TEXT_KNIFE_COLLISION,
    TEXT_KNIFE_MIRROR_FAILED,
    TEXT_KNIFE_ON_PLANE,
    TEXT_KNIFE_OTHER_SIDE,
    TEXT_KNIFE_PLANE_IN_FACE,
    TEXT_KNIFE_SEED_LOST,
    TEXT_KNIFE_SELF_PARTNER_EDGE,
    TEXT_KNIFE_UNKNOWN_CALL,
    KnifeRefusal,
    clip_path,
    coordinate_knife,
)
from mirai.symmetric_ops import TEXT_DELTA, TEXT_NON_EXACT_PLANE, TEXT_UNPAIRED, SymmetryRefusal
from mirai.symmetry import symmetry_state
from mirai.symmetry_coordination import SymmetryIndex, completeness_report
from mirai.topology import knife_resolve as kr
from mirai.topology.contextual_c import CContext
from mirai.topology.knife_resolve import KeptSplitEdge, KeptSplitFace, KnifeResolution, RecordedMesh
from tests.symmetric_knife_support import (
    FIXTURE,
    Outcome,
    T_e,
    T_f,
    T_p,
    T_v,
    canon_faces,
    commit_session,
    content,
    evaluate,
    fresh,
    frozen_sessions,
    fuzz_paths,
    make_tool,
    permute_path,
    quiet,
    run_and_evaluate,
    set_plane,
    source_commits,
    start_state,
    to_axis,
)

_SRC = Path(__file__).resolve().parent.parent / "src" / "mirai"
SEED = 20261008


def assert_restored(out: Outcome) -> None:
    assert out.restored, f"{out.status}: the mesh is not the session start ({out.text})"
    assert len(out.scene.history) == 0, "a refused / empty commit pushed history"


def assert_equivariant(out: Outcome, what: str) -> None:
    assert out.status == "committed", f"{what}: {out.status} ({out.text})"
    assert (out.ea, out.eb, out.ec, out.ed) == (True, True, True, True), (
        f"{what}: E-a..E-d = {out.ea, out.eb, out.ec, out.ed} {out.info.get('delta')}")
    assert out.dup == (0, 0), f"{what}: duplicate vertices {out.dup}"
    assert out.selected_ok, f"{what}: residue selects the mirror side or nothing"


# ---------------------------------------------------------------------------------------------
# 1. Equivariance over fuzz (camera-free, seam-biased, both sides) — every exact plane
# ---------------------------------------------------------------------------------------------

#: kind -> (fuzz options, what it stands for)
FUZZ_KINDS = {
    "camera-free": dict(region="normal side"),                    # the probe's K10: the working side's faces only
    "seam-biased": dict(region="normal side", seam_bias=True),    # the review's R7: seam vertices / edges / near-seam
    "both-sides": dict(region="both sides", seam_bias=True),      # paths that walk over the seam and start anywhere
}
REFUSALS_ALLOWED = {TEXT_KNIFE_SEED_LOST}   # a clipped closed loop whose interior seed is lost: refused with a text


def run_fuzz(name: str, axis: int, sign: int, kind: str, n_valid: int) -> collections.Counter:
    """Commit `n_valid` random paths (whose unclipped source alone commits, as in the probe) plus every other
    path generated on the way (those may only be refused, empty or rolled back — and committed ones are checked
    all the same)."""
    state = start_state(name, axis, sign)
    rnd = random.Random(SEED + 31 * axis + (sign < 0) + len(kind))
    base = Mesh.from_state(state)
    base_report, base_state = completeness_report(base), symmetry_state(base)
    tally = collections.Counter()
    while tally["valid"] < n_valid:
        assert tally["paths"] < 6 * n_valid, f"too few valid fuzz paths: {dict(tally)}"
        for path in fuzz_paths(state, rnd, max(50, n_valid // 2), **FUZZ_KINDS[kind]):
            tally["paths"] += 1
            valid = source_commits(state, path)
            tally["valid"] += valid
            out = commit_session(state, path)
            tally[out.status] += 1
            if out.status == "committed":
                evaluate(out, path, base_report, base_state)
                assert_equivariant(out, f"{name} axis {axis} sign {sign} {kind}")
                tally["E++++"] += 1
                tally["clipped"] += clip_path(base, base.symmetry_definition, path).clipped
            else:
                assert_restored(out)
                if valid:
                    # The population of the probe: nothing but the lost-seed loop is refused, nothing is rolled back.
                    assert out.status != "rolled back", f"integrity net fired: {out.text}"
                    if out.status == "refused":
                        assert out.text in REFUSALS_ALLOWED, out.text
                elif out.status == "refused":
                    # A source that is broken on its own (the same face point twice cuts two coincident vertices):
                    # the one-sided Knife rolls it back, the symmetric commit refuses it by the delta (ambiguous partners).
                    assert out.text in REFUSALS_ALLOWED | {TEXT_DELTA}, out.text
                    tally["refused, source invalid"] += 1
    return tally


@pytest.mark.parametrize("kind", list(FUZZ_KINDS))
@pytest.mark.parametrize("name", ["subd_cube", "head_basemesh", "tie_grid"])
def test_fuzz_x_plane(name, kind):
    n = 150 if (name == "head_basemesh" and kind == "both-sides") else 300
    tally = run_fuzz(name, 0, 1, kind, n)
    assert tally["valid"] >= n
    assert tally["E++++"] + tally["nothing"] + tally["refused"] + tally["rolled back"] == tally["paths"]
    assert tally["E++++"] >= n // 2


@pytest.mark.parametrize("kind", list(FUZZ_KINDS))
@pytest.mark.parametrize("name,axis,sign", [
    ("head_basemesh", 1, 1),     # plane y = 0, the normal's side up
    ("subd_cube", 2, -1),        # plane z = 0, negative normal
    ("tie_grid", 1, -1),         # plane y = 0, negative normal
    ("head_basemesh", 0, -1),    # the head's own plane, negative normal (the working side flips its sign)
])
def test_fuzz_other_exact_planes(name, axis, sign, kind):
    """The same pass rate as the X plane: every valid path commits E ++++ or cuts nothing, none is refused but
    the lost-seed loop, no union, no duplicate vertex (the assertions of `run_fuzz`)."""
    n = 60
    tally = run_fuzz(name, axis, sign, kind, n)
    assert tally["valid"] >= n
    assert tally["E++++"] + tally["nothing"] + tally["refused"] + tally["rolled back"] == tally["paths"]
    assert tally["E++++"] >= n // 2


def test_both_sides_fuzz_really_clips():
    """The both-sides fuzz is a test of the clip only if it produces clipped paths on both working sides."""
    state = start_state("tie_grid")
    base = Mesh.from_state(state)
    rnd = random.Random(SEED)
    sides, clipped = collections.Counter(), 0
    for path in fuzz_paths(state, rnd, 200, region="both sides", seam_bias=True):
        try:
            c = clip_path(base, base.symmetry_definition, path)
        except KnifeRefusal:
            continue
        sides[c.side] += 1
        clipped += c.clipped
    assert sides[1] > 20 and sides[-1] > 20
    assert clipped > 10


# ---------------------------------------------------------------------------------------------
# 2. The regression rows (frozen path data)
# ---------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sessions() -> list:
    return frozen_sessions()


def by_group(sessions, group):
    return [s for s in sessions if s.group == group]


def test_fixture_is_present_and_complete(sessions):
    groups = collections.Counter(s.group for s in sessions)
    assert FIXTURE.is_file()
    assert groups["R1"] == 4 and groups["loop"] == 2 and groups["R8"] == 60 and groups["K7"] == 35
    assert groups["N5"] == 2 and groups["K4"] >= 150 and groups["K5"] >= 150
    assert sum(1 for s in sessions if s.r10) == 1


def test_r1_two_chains_both_orders(sessions):
    """R1 / 'Fall 3': the side where the cut starts is cut and mirrored, the chain on the other side falls away.
    One chain entirely on the other side is simply the working side."""
    expected_side = {
        "R1 +X chain, lift, -X chain (non-partner face)": 1,
        "R1 one chain entirely on -X": -1,
        "R1' -X chain, lift, +X chain (started on -X)": -1,
    }
    rows = by_group(sessions, "R1")
    assert len(rows) == 4
    for s in rows:
        out = run_and_evaluate(s.mesh, s.path)
        assert_equivariant(out, s.label)
        want = expected_side.get(s.label, 1 if s.label.startswith("R1 head") else None)
        assert out.side == want, (s.label, out.side)
        # The other chain is gone: the result is the working chain alone plus its mirror, not the union of both.
        if "lift" in s.label:
            lift = next(i for i, p in enumerate(s.path) if p["kind"] == "break")
            alone = run_and_evaluate(s.mesh, s.path[:lift])
            assert_equivariant(alone, s.label + " (first chain alone)")
            assert sorted(canon_faces(alone.mesh)) == sorted(canon_faces(out.mesh)), s.label


def test_r8_crossings_through_seam_vertices(sessions):
    """R8: an edge point on one side, a seam vertex, an edge point in a non-partner face on the other side —
    a union under the plain K-C. Now: the clipped cut plus its exact mirror, 60 / 60, no union."""
    rows = by_group(sessions, "R8")
    assert len(rows) == 60
    for s in rows:
        out = run_and_evaluate(s.mesh, s.path)
        assert_equivariant(out, f"{s.mesh} {s.label}")
        base = fresh(s.mesh)
        assert clip_path(base, base.symmetry_definition, s.path).clipped, s.label   # the far side was really cut away
        assert not out.union


def test_r10_the_k5_side_camera_union_session(sessions):
    (s,) = [x for x in sessions if x.r10]
    assert (s.mesh, s.camera) == ("head_basemesh", "side (+X)")
    out = run_and_evaluate(s.mesh, s.path)
    assert_equivariant(out, s.label)
    base = fresh(s.mesh)
    c = clip_path(base, base.symmetry_definition, s.path)
    assert c.clipped and not out.union


def test_camera_sessions_k4_k5(sessions):
    """All 371 + camera sessions of the Discovery (K4, K5, incl. the R9-type ones the plain K-C refused): the
    result is what the probe pinned — E ++++ with the same element counts, or nothing cut — never a union,
    never a refusal, never a duplicate."""
    rows = by_group(sessions, "K4") + by_group(sessions, "K5")
    committed = nothing = r9 = 0
    for s in rows:
        out = run_and_evaluate(s.mesh, s.path)
        assert out.status == s.expect["status"], (s.label, out.status, out.text)
        if out.status == "committed":
            assert_equivariant(out, s.label)
            m = out.mesh
            assert [len(m.all_vertex_ids()), len(m.all_edge_ids()), len(m.all_face_ids())] == s.expect["counts"], s.label
            committed += 1
            r9 += s.k_c_refused
        else:
            assert_restored(out)
            nothing += 1
    assert committed >= 360 and r9 >= 80 and nothing <= 15, (committed, r9, nothing)


K7_REFUSED = {  # (label prefix) -> (reason of the coordinator, text)
    "e. ": ("kept cut inside a face on or spanning the plane (item 9)", TEXT_KNIFE_ON_PLANE),
    "e'.": ("kept cut inside a face on or spanning the plane (item 9)", TEXT_KNIFE_ON_PLANE),
    "f. ": ("plane crossed inside a face", TEXT_KNIFE_PLANE_IN_FACE),
    "f'.": ("plane crossed inside a face", TEXT_KNIFE_PLANE_IN_FACE),
    "f''": ("plane crossed inside a face", TEXT_KNIFE_PLANE_IN_FACE),
}


def test_k7_seam_rows(sessions):
    """K7 a–h on the three assets as in KD §1.4 (c and d / d' / d'' are clipped at the seam now); the plane-spanning
    rows e, e', f, f', f'' are refused with the mesh at the session start."""
    rows = by_group(sessions, "K7")
    assert len(rows) == 35
    refused = 0
    for s in rows:
        head = next((k for k in K7_REFUSED if s.label.startswith(k)), None)
        state = start_state(s.mesh)
        if head is None:
            out = run_and_evaluate(s.mesh, s.path)
            assert_equivariant(out, f"{s.mesh} {s.label}")
            continue
        refused += 1
        mesh = Mesh.from_state(state)
        with pytest.raises(KnifeRefusal) as exc:
            coordinate_knife(mesh, s.path, state)
        reason, text = K7_REFUSED[head]
        assert exc.value.reason == reason and str(exc.value) == text, (s.label, exc.value.reason)
        assert content(mesh) == content(state)
        out = commit_session(state, s.path)
        assert out.status == "refused" and out.text == text
        assert_restored(out)
    assert refused == 5


def test_k7_c_and_d_rows_are_clipped_at_the_seam(sessions):
    """c (a path over the seam into the other side) and d / d' / d'' (the Artist drew the mirror by hand, exact or
    off by 1e-12 / 1e-6): the part beyond the seam is replaced by the exact mirror — the result is the same
    whatever the hand-drawn half was."""
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        rows = {s.label[:3]: s for s in by_group(sessions, "K7") if s.mesh == asset}
        counts = set()
        for key in ("c. ", "d. ", "d'.", "d''"):
            out = run_and_evaluate(asset, rows[key].path)
            assert_equivariant(out, f"{asset} {key}")
            base = fresh(asset)
            assert clip_path(base, base.symmetry_definition, rows[key].path).clipped
            m = out.mesh
            counts.add((len(m.all_vertex_ids()), len(m.all_edge_ids()), len(m.all_face_ids())))
        assert len(counts) == 1, (asset, counts)    # c is an arbitrary hand path, d* are the same: all give one cut + mirror


def test_k7_seam_maintenance_s1(sessions):
    """b: a seam edge point is split — the seam edge is replaced by its two halves in the same mutation (S1) and
    Undo restores the old seam with the mesh; b2: two points on one seam edge, the second splits a half."""
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        rows = {s.label[:3]: s for s in by_group(sessions, "K7") if s.mesh == asset}
        for key, splits in (("b. ", 1), ("b2.", 2)):
            state = start_state(asset)
            before = Mesh.from_state(state).symmetry_definition
            out = run_and_evaluate(asset, rows[key].path)
            assert_equivariant(out, f"{asset} {key}")
            after = out.mesh.symmetry_definition
            assert len(after.seam_edges) == len(before.seam_edges) + splits
            assert all(out.mesh.is_valid_edge(e) for e in after.seam_edges)
            assert completeness_report(out.mesh).dead_seam_ids == frozenset()


def test_loops_across_the_seam(sessions):
    """A closed chain across the seam is rotated so its closing segment stays a cut; a clipped closed chain whose
    interior start the next chain continues is refused with a text."""
    loop, seeded = by_group(sessions, "loop")
    out = run_and_evaluate(loop.mesh, loop.path)
    assert_equivariant(out, loop.label)
    base = fresh(loop.mesh)
    assert clip_path(base, base.symmetry_definition, loop.path).rotated == 1

    state = start_state(seeded.mesh)
    with pytest.raises(KnifeRefusal) as exc:
        coordinate_knife(Mesh.from_state(state), seeded.path, state)
    assert str(exc.value) == TEXT_KNIFE_SEED_LOST
    out = commit_session(state, seeded.path)
    assert out.status == "refused" and out.text == TEXT_KNIFE_SEED_LOST
    assert_restored(out)


def test_n5_self_partner_edge_across_the_plane(sessions):
    """The span grid's edges across the plane are their own partners (N5); a cut through them lies in
    self-mirrored faces and is refused (item 9)."""
    rows = by_group(sessions, "N5")
    assert len(rows) == 2
    for s in rows:
        state = start_state(s.mesh)
        out = commit_session(state, s.path)
        assert out.status == "refused" and out.text == TEXT_KNIFE_ON_PLANE, s.label
        assert_restored(out)


# ---------------------------------------------------------------------------------------------
# 3. Other planes: the frozen rows give the same results (axis-permuted and negative-normal copies)
# ---------------------------------------------------------------------------------------------

PLANES = [(1, 1), (2, -1), (0, -1), (1, -1)]


@pytest.mark.parametrize("axis,sign", PLANES)
def test_frozen_rows_on_other_planes_equal_the_x_plane(sessions, axis, sign):
    """R1, R8, K7, the loops and N5 on a Y / Z / negative-normal copy of the same meshes (ids kept, positions
    permuted): the same status, the same element counts, E ++++ — a non-X plane behaves like X."""
    rows = [s for s in sessions if s.group in ("R1", "R8", "K7", "loop", "N5")]
    seen = collections.Counter()
    for s in rows:
        path = permute_path(s.path, axis)
        out = run_and_evaluate(s.mesh, path, axis, sign)
        ref = run_and_evaluate(s.mesh, s.path)
        assert out.status == ref.status, (s.label, axis, sign, out.status, ref.status, out.text)
        if out.status == "committed":
            assert_equivariant(out, f"{s.label} axis {axis} sign {sign}")
            sizes = lambda o: (len(o.mesh.all_vertex_ids()), len(o.mesh.all_edge_ids()), len(o.mesh.all_face_ids()))  # noqa: E731
            assert sizes(out) == sizes(ref), (s.label, axis, sign)
            assert out.side == ref.side * sign, (s.label, axis, sign)   # the working side follows the normal's sign
        else:
            assert out.text == ref.text
            assert_restored(out)
        seen[out.status] += 1
    assert seen["committed"] == 95 and seen["refused"] == 8


# ---------------------------------------------------------------------------------------------
# 4. The clip (unit level): side rule, runs, rotation, refusals
# ---------------------------------------------------------------------------------------------

def grid():
    """tie_grid: squares x in [-3, 3], y in [0, 3]; the seam is x = 0."""
    mesh = fresh("tie_grid")
    pos = {tuple(mesh.vertex_position(v)[:2]): v for v in mesh.all_vertex_ids()}

    def edge(p, q):
        return kr.find_edge(mesh, pos[p], pos[q])

    return mesh, pos, edge


def rec(pid, target, **extra):
    return dict(target, pid=pid, **extra)


def sides_of(mesh, path):
    d = mesh.symmetry_definition
    return "".join("|" if p["kind"] == "break" else
                   {1: "+", -1: "-", 0: "0"}[(sk._sign(sk._signed_distance(d, sk._record_position(mesh, p))))]
                   if p["kind"] != "space" else "s" for p in path)


def test_clip_is_the_identity_on_a_working_side_path():
    mesh, pos, edge = grid()
    path = [rec(0, T_e(edge((1.0, 0.0), (1.0, 1.0)), 0.3)), rec(1, T_e(edge((2.0, 0.0), (2.0, 1.0)), 0.6)),
            {"kind": "break", "reason": "lift"}, rec(2, T_v(pos[(1.0, 2.0)])), rec(3, T_v(pos[(2.0, 3.0)]))]
    clip = clip_path(mesh, mesh.symmetry_definition, path)
    assert clip.side == 1 and clip.path == path and not clip.clipped and clip.stretches == 0


def test_a_seam_record_ends_and_starts_a_run():
    """+, 0, -, -, 0, +: the other-side stretch becomes one pen lift; the two seam records end / start the runs
    next to it. Walking along the seam (all records on the plane) is not clipped."""
    mesh, pos, edge = grid()
    path = [rec(0, T_v(pos[(1.0, 1.0)])), rec(1, T_v(pos[(0.0, 1.0)])), rec(2, T_v(pos[(-1.0, 1.0)])),
            rec(3, T_v(pos[(-1.0, 2.0)])), rec(4, T_v(pos[(0.0, 2.0)])), rec(5, T_v(pos[(1.0, 2.0)]))]
    assert sides_of(mesh, path) == "+0--0+"
    clip = clip_path(mesh, mesh.symmetry_definition, path)
    assert sides_of(mesh, clip.path) == "+0|0+" and clip.path[2]["reason"] == "lift"
    assert (clip.stretches, clip.dropped) == (1, 2) and clip.clipped

    along = [rec(0, T_v(pos[(0.0, 0.0)])), rec(1, T_v(pos[(0.0, 1.0)])), rec(2, T_v(pos[(0.0, 2.0)]))]
    clip = clip_path(mesh, mesh.symmetry_definition, along)
    assert clip.side == 0 and clip.path == along


def test_working_side_is_the_first_mesh_record_off_the_plane_not_a_point_in_space():
    mesh, pos, edge = grid()
    space_minus = {"kind": "space", "position": (-2.0, 1.0, 5.0), "pid": 0}
    path = [space_minus, {"kind": "break", "reason": "space"}, rec(1, T_v(pos[(1.0, 1.0)])), rec(2, T_v(pos[(2.0, 1.0)]))]
    clip = clip_path(mesh, mesh.symmetry_definition, path)
    assert clip.side == 1                                         # not -1, where the point in space lies
    assert clip.dropped_space == 1 and not clip.clipped          # a dropped point in space alone changes nothing
    assert [p["kind"] for p in clip.path if p["kind"] != "break"] == ["vertex", "vertex"]
    # a point in space on the working side stays in the clipped path (the coordinator strips it)
    space_plus = dict(space_minus, position=(2.0, 1.0, 5.0))
    clip = clip_path(mesh, mesh.symmetry_definition, [rec(1, T_v(pos[(1.0, 1.0)])), space_plus])
    assert any(p["kind"] == "space" for p in clip.path)


def test_the_second_chain_on_the_other_side_is_dropped():
    mesh, pos, edge = grid()
    path = [rec(0, T_v(pos[(1.0, 1.0)])), rec(1, T_v(pos[(2.0, 1.0)])), {"kind": "break", "reason": "lift"},
            rec(2, T_v(pos[(-1.0, 2.0)])), rec(3, T_v(pos[(-2.0, 2.0)]))]
    clip = clip_path(mesh, mesh.symmetry_definition, path)
    assert sides_of(mesh, clip.path) == "++|"
    path = path[3:] + [{"kind": "break", "reason": "lift"}] + path[:2]
    clip = clip_path(mesh, mesh.symmetry_definition, path)
    assert clip.side == -1 and sides_of(mesh, clip.path) == "--|"


def test_a_straight_segment_across_the_plane_is_refused():
    """A cut from a working-side record straight to an other-side record (no break, no seam record between) crosses
    the plane inside a face: there is no seam record to clip at (item 9)."""
    mesh = fresh("hexagon_grid")
    pos = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
    right = kr.find_edge(mesh, pos[(1.0, 1.0, 0.0)], pos[(1.0, 2.0, 0.0)])
    left = kr.find_edge(mesh, pos[(-1.0, 1.0, 0.0)], pos[(-1.0, 2.0, 0.0)])
    path = [rec(0, T_e(right, 0.3)), rec(1, T_e(left, 0.6))]
    with pytest.raises(KnifeRefusal) as exc:
        clip_path(mesh, mesh.symmetry_definition, path)
    assert str(exc.value) == TEXT_KNIFE_PLANE_IN_FACE and exc.value.reason == "plane crossed inside a face"
    # ... the other way round, and as the closing segment of a loop
    with pytest.raises(KnifeRefusal):
        clip_path(mesh, mesh.symmetry_definition, path[::-1])
    third = rec(2, T_e(kr.find_edge(mesh, pos[(2.0, 1.0, 0.0)], pos[(2.0, 2.0, 0.0)]), 0.5))
    loop = [path[0], third, path[1], {"kind": "break", "reason": "closed", "cyclic": True}, path[0]]
    with pytest.raises(KnifeRefusal):
        clip_path(mesh, mesh.symmetry_definition, loop)


def test_every_refusal_is_a_symmetry_refusal_with_a_reason():
    with pytest.raises(SymmetryRefusal) as exc:
        mesh = fresh("hexagon_grid")
        pos = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
        a = kr.find_edge(mesh, pos[(1.0, 1.0, 0.0)], pos[(1.0, 2.0, 0.0)])
        b = kr.find_edge(mesh, pos[(-1.0, 1.0, 0.0)], pos[(-1.0, 2.0, 0.0)])
        clip_path(mesh, mesh.symmetry_definition, [rec(0, T_e(a, 0.5)), rec(1, T_e(b, 0.5))])
    assert isinstance(exc.value, KnifeRefusal) and exc.value.commit_refusal is True
    assert exc.value.violations[0] == exc.value.reason


# ---------------------------------------------------------------------------------------------
# 5. Refusals: every path restores the session start, pushes no history and sets the text
# ---------------------------------------------------------------------------------------------

def a_cut_path(name="tie_grid", side=1):
    """A valid one-sided path: two edge points in squares on `side`."""
    mesh = fresh(name)
    pos = {tuple(mesh.vertex_position(v)[:2]): v for v in mesh.all_vertex_ids()}
    s = side
    e1 = kr.find_edge(mesh, pos[(1.0 * s, 0.0)], pos[(1.0 * s, 1.0)])
    e2 = kr.find_edge(mesh, pos[(2.0 * s, 0.0)], pos[(2.0 * s, 1.0)])
    return [rec(0, T_e(e1, 0.3)), rec(1, T_e(e2, 0.6))]


def assert_refused(state, path, text, reason=None, *, coordinator=coordinate_knife, restores=True):
    """The coordinator raises the refusal with the mesh at the session start; through the tool: no history, no
    selection, `last_problem` is the text, the mesh is the session start. `restores=False`: a callable that does not
    restore by itself (only the tool's own restore is then checked)."""
    mesh = Mesh.from_state(state)
    with pytest.raises(SymmetryRefusal) as exc:
        coordinator(mesh, path, state)
    assert str(exc.value) == text
    if reason is not None:
        assert exc.value.reason == reason
    if restores:
        assert content(mesh) == content(state), "the coordinator did not restore the session start"
        assert mesh.symmetry_definition == Mesh.from_state(state).symmetry_definition
    out = commit_session(state, path, coordinator=coordinator)
    assert out.status == "refused" and out.text == text
    assert_restored(out)
    assert out.knife.last_resolution is None and out.knife.path_edges == []
    assert not out.scene.selection.edges
    return exc.value


def test_the_coordinator_restores_by_itself_and_the_tool_does_not_rely_on_it():
    """A refusal is raised after the coordinator has taken its mutations back (so the mesh is the session start whatever
    the caller does); the tool restores once more for a callable it did not write."""
    state = start_state("tie_grid")

    def forgetful(mesh, path, before):        # mutates, then refuses without restoring
        mesh.split_edge(next(iter(mesh.all_edge_ids())), 0.5)
        raise KnifeRefusal("Symmetrie: test", "forged")

    assert_refused(state, a_cut_path(), "Symmetrie: test", "forged", coordinator=forgetful, restores=False)


def forge(monkeypatch, mutate):
    """Replace the resolver inside the coordinator: `mutate(recorded_mesh)` makes real, recorded mutations and may
    make unrecorded ones; its kept calls are the report. (The nets never fire after the clip on real paths — this is how
    they are driven.)"""
    def fake(mesh, path, before):
        rm = RecordedMesh(mesh)
        extra = mutate(rm)
        return KnifeResolution(kept_calls=tuple(rm.kept), path_edges=list(extra or []))

    monkeypatch.setattr(sk, "resolve_cross_face", fake)


def grid_ids():
    mesh, pos, edge = grid()
    return mesh, pos, edge


def test_refusal_non_exact_plane_and_missing_definition():
    state = start_state("tie_grid")
    for normal, point in (((0.6, 0.8, 0.0), (0.0, 0.0, 0.0)), ((1.0, 0.0, 0.0), (0.5, 0.0, 0.0))):
        mesh = Mesh.from_state(state)
        d = mesh.symmetry_definition
        mesh.symmetry_definition = type(d)(point, normal, d.seam_edges)
        bad = mesh.export_state()
        assert_refused(bad, a_cut_path(), TEXT_NON_EXACT_PLANE, "non-exact plane")
    plain = Mesh.from_state(state)
    plain.symmetry_definition = None
    with pytest.raises(ValueError):
        coordinate_knife(plain, a_cut_path(), plain.export_state())


def test_refusal_unpaired_target():
    """F3 = A at the commit: a vertex / edge / face record without a mirror partner (man_with_shoes is partial)."""
    state = start_state("man_with_shoes_basemesh")
    mesh = Mesh.from_state(state)
    index = SymmetryIndex(mesh)
    bad_v = next(v for v in sorted(mesh.all_vertex_ids()) if index.vertex_partner(v) is None
                 and mesh.vertex_position(v)[0] > 0.0)
    bad_e = next(e for e in sorted(mesh.all_edge_ids()) if index.edge_partner(e) is None)
    bad_f = next(f for f in sorted(mesh.all_face_ids()) if index.face_partner(f) is None)
    for target, reason in ((T_v(bad_v), "vertex target without partner"), (T_e(bad_e, 0.5), "edge target without partner"),
                           (T_f(bad_f, tuple(sum(c) / 3 for c in zip(*[mesh.vertex_position(v) for v in mesh.face_vertices(bad_f)][:3]))),
                            "face target without partner")):
        if target["kind"] == "edge" and sk._sign(sk._signed_distance(mesh.symmetry_definition, sk._record_position(mesh, rec(0, target)))) < 0:
            pass   # either side: the working side is derived from the first mesh record off the plane
        path = [rec(0, target)]
        assert_refused(state, path, TEXT_UNPAIRED, reason)


def test_unpaired_geometry_next_to_a_valid_cut_still_commits():
    """The same asset, a cut on paired geometry: commits (D-strict only refuses what has no partner)."""
    state = start_state("man_with_shoes_basemesh")
    base = Mesh.from_state(state)
    rnd = random.Random(SEED)
    n = 0
    for path in fuzz_paths(state, rnd, 60, region="normal side"):
        out = commit_session(state, path)
        if out.status == "committed":
            n += 1
            assert out.mesh.symmetry_definition is not None
        else:
            assert_restored(out)
            assert out.status in ("refused", "nothing")
            if out.status == "refused":
                assert out.text == TEXT_UNPAIRED
    assert n > 0 and base is not None


def test_net_kept_mutation_on_the_other_side(monkeypatch):
    mesh, pos, edge = grid_ids()
    state = start_state("tie_grid")
    plus, minus = edge((1.0, 0.0), (1.0, 1.0)), edge((-2.0, 0.0), (-2.0, 1.0))

    def mutate(rm):
        kr.kept_split_edge(rm, plus, 0.3)
        kr.kept_split_edge(rm, minus, 0.4)          # not the mirror of the first: the other side of the working side

    forge(monkeypatch, mutate)
    assert_refused(state, [], TEXT_KNIFE_OTHER_SIDE, "kept mutation on the other side (side rule)")


def test_net_no_kept_call_off_the_plane(monkeypatch):
    mesh, pos, edge = grid_ids()
    state = start_state("tie_grid")
    seam_edge = edge((0.0, 0.0), (0.0, 1.0))
    forge(monkeypatch, lambda rm: kr.kept_split_edge(rm, seam_edge, 0.5))
    assert_refused(state, [], TEXT_KNIFE_ON_PLANE, "no kept call off the plane (item 9)")


def test_net_kept_cut_in_a_face_on_or_spanning_the_plane(monkeypatch):
    state = start_state("hexagon_grid")
    mesh = Mesh.from_state(state)
    hexf = next(f for f in mesh.all_face_ids() if len(mesh.face_vertices(f)) == 6)
    a, b = mesh.face_vertices(hexf)[0], mesh.face_vertices(hexf)[3]
    forge(monkeypatch, lambda rm: kr.kept_split_face(rm, hexf, a, b))
    assert_refused(state, [], TEXT_KNIFE_ON_PLANE, "kept cut inside a face on or spanning the plane (item 9)")


def test_net_unknown_kept_call_kind(monkeypatch):
    """Fail-closed (AD-017 §13 item 6): a kind this reader does not know is refused — by the guard, and by the replay
    itself should the guard ever be passed."""
    state = start_state("tie_grid")
    monkeypatch.setattr(sk, "resolve_cross_face", lambda mesh, path, before: KnifeResolution(kept_calls=(object(),)))
    assert_refused(state, [], TEXT_KNIFE_UNKNOWN_CALL)
    monkeypatch.undo()
    mesh = Mesh.from_state(state)
    replay = sk._Replay(mesh, mesh.symmetry_definition, SymmetryIndex(mesh))
    with pytest.raises(KnifeRefusal) as exc:
        replay.run((object(),))
    assert str(exc.value) == TEXT_KNIFE_UNKNOWN_CALL


def test_net_self_partner_edge_across_the_plane_n5(monkeypatch):
    """The span grid's bottom edge runs from (-0.5, 0) to (0.5, 0): its own partner, ends swapped, not on the plane. A
    kept split of it (off the plane, so the guard passes) would map its halves onto themselves instead of crossed."""
    state = start_state("span_grid")
    mesh = Mesh.from_state(state)
    pos = {tuple(mesh.vertex_position(v)): v for v in mesh.all_vertex_ids()}
    bottom = kr.find_edge(mesh, pos[(-0.5, 0.0, 0.0)], pos[(0.5, 0.0, 0.0)])
    assert SymmetryIndex(mesh).edge_partner(bottom) == bottom
    forge(monkeypatch, lambda rm: kr.kept_split_edge(rm, bottom, 0.25))
    assert_refused(state, [], TEXT_KNIFE_SELF_PARTNER_EDGE, "self-partner edge crossing the plane (N5)")


def test_net_mirror_element_already_cut_by_the_source(monkeypatch):
    """The mirror edge / face was already cut by something the report does not know (here an unrecorded mutation):
    the replay finds it gone and refuses."""
    mesh, pos, edge = grid_ids()
    state = start_state("tie_grid")
    e, e_mirror = edge((1.0, 0.0), (1.0, 1.0)), edge((-1.0, 0.0), (-1.0, 1.0))

    def cut_edge(rm):
        kr.kept_split_edge(rm, e, 0.3)
        rm.raw.split_edge(e_mirror, 0.5)             # unrecorded

    forge(monkeypatch, cut_edge)
    assert_refused(state, [], TEXT_KNIFE_COLLISION, "mirror edge already cut by the source")
    monkeypatch.undo()

    f = next(x for x in mesh.all_face_ids() if mesh.face_vertices(x) == [pos[(1.0, 0.0)], pos[(2.0, 0.0)], pos[(2.0, 1.0)], pos[(1.0, 1.0)]]
             or set(mesh.face_vertices(x)) == {pos[(1.0, 0.0)], pos[(2.0, 0.0)], pos[(2.0, 1.0)], pos[(1.0, 1.0)]})
    g = SymmetryIndex(mesh).face_partner(f)
    vs, ws = mesh.face_vertices(f), mesh.face_vertices(g)

    def cut_face(rm):
        kr.kept_split_face(rm, f, vs[0], vs[2])
        rm.raw.split_face(g, ws[0], ws[2])           # unrecorded

    forge(monkeypatch, cut_face)
    assert_refused(state, [], TEXT_KNIFE_COLLISION, "mirror face already cut by the source")


def test_net_mirror_cut_cannot_be_repeated(monkeypatch):
    """A forged report whose mirror cut Core refuses (adjacent ends, no interior point), one whose halves cannot be
    told apart and one without halves at all (malformed): refused with the mesh restored."""
    mesh, pos, edge = grid_ids()
    state = start_state("tie_grid")
    f = next(x for x in mesh.all_face_ids() if set(mesh.face_vertices(x)) == {pos[(1.0, 0.0)], pos[(2.0, 0.0)], pos[(2.0, 1.0)], pos[(1.0, 1.0)]})
    vs = mesh.face_vertices(f)
    holder = {}

    def real_cut(rm):
        kr.kept_split_face(rm, f, vs[0], vs[2])
        holder["call"] = rm.kept[-1]

    for forged, reason in (
        (lambda c: dataclasses.replace(c, b=vs[1]), "mirror face cut refused"),            # adjacent, no interior point
        (lambda c: dataclasses.replace(c, face_1_vertices=(c.a, c.b), face_2_vertices=(c.a, c.b)),
         "mirror halves not distinguishable"),                                              # both halves fit both
        (lambda c: dataclasses.replace(c, face_1_vertices=(), face_2_vertices=()), "kept split_face without halves"),
    ):
        def fake(m, path, before, forged=forged):
            rm = RecordedMesh(m)
            real_cut(rm)
            return KnifeResolution(kept_calls=(forged(holder["call"]),))

        monkeypatch.setattr(sk, "resolve_cross_face", fake)
        text = TEXT_KNIFE_UNKNOWN_CALL if reason.startswith("kept split_face") else TEXT_KNIFE_MIRROR_FAILED
        err = assert_refused(state, [], text)
        assert err.reason.startswith(reason), err.reason
        monkeypatch.undo()


def test_net_completeness_delta(monkeypatch):
    """The completeness delta (D-strict) is the last net: a surviving vertex that lost its partner (an unrecorded
    move) is refused with TEXT_DELTA and the detail in `violations`."""
    mesh, pos, edge = grid_ids()
    state = start_state("tie_grid")
    e = edge((1.0, 0.0), (1.0, 1.0))
    far = pos[(3.0, 3.0)]

    def mutate(rm):
        kr.kept_split_edge(rm, e, 0.3)
        rm.raw.set_vertex_position(far, (3.0, 3.5, 0.0))      # unrecorded: (3, 3) no longer mirrors (-3, 3)

    forge(monkeypatch, mutate)
    err = assert_refused(state, [], TEXT_DELTA, "completeness delta (D-strict)")
    assert any("lost their partner" in v for v in err.violations[1:])


def test_other_exceptions_propagate_and_the_mesh_is_restored(monkeypatch):
    """A bug is not a refusal: it propagates (the tool does not swallow it), after the mesh was taken back."""
    state = start_state("tie_grid")
    path = a_cut_path()
    mesh = Mesh.from_state(state)

    def boom(self, kept):
        raise RuntimeError("boom")

    monkeypatch.setattr(sk._Replay, "run", boom)
    with pytest.raises(RuntimeError):
        coordinate_knife(mesh, path, state)
    assert content(mesh) == content(state)

    knife, scene = make_tool(Mesh.from_state(state))
    knife._path = list(path)
    with pytest.raises(RuntimeError), quiet():
        knife.commit()
    assert len(scene.history) == 0


# ---------------------------------------------------------------------------------------------
# 6. Residue F4 = A, the one history entry, nothing cut
# ---------------------------------------------------------------------------------------------

def test_residue_selects_the_working_sides_cut_edges_only(sessions):
    """After a cut with a seam split: the working side's cut edges are selected (Edge mode), the mirror side's are
    not, the halves of the split seam edge are not (they are split remnants, as in the AD-017 residue)."""
    for asset in ("subd_cube", "head_basemesh", "tie_grid"):
        s = next(x for x in by_group(sessions, "K7") if x.mesh == asset and x.label.startswith("b. "))
        state = start_state(asset)
        base = Mesh.from_state(state)
        out = run_and_evaluate(asset, s.path)
        assert_equivariant(out, s.label)
        res = out.knife.last_resolution
        mesh = out.mesh
        selected = set(out.scene.selection.edges)
        assert out.scene.selection.mode.name == "EDGE"
        assert selected == {e for e in res.path_edges if mesh.is_valid_edge(e)} and selected

        seam_split = [c for c in res.kept_calls if isinstance(c, KeptSplitEdge) and c.edge_id in base.symmetry_definition.seam_edges]
        assert len(seam_split) == 1
        assert not ({seam_split[0].half_1, seam_split[0].half_2} & selected)           # seam halves: not selected
        assert {seam_split[0].half_1, seam_split[0].half_2} <= mesh.symmetry_definition.seam_edges

        d = mesh.symmetry_definition
        w = out.side
        for e in selected:
            ds = [sk._signed_distance(d, mesh.vertex_position(v)) * w for v in mesh.edge_vertices(e)]
            assert min(ds) >= 0.0 and max(ds) > 0.0       # the working side, not the plane
        # the mirror side has the mirrored cut edges, and none of them is selected
        mirrored = {tuple(sorted(tuple(sk.mirror_position(tuple(mesh.vertex_position(v)), d.plane_point, d.plane_normal))
                                 for v in mesh.edge_vertices(e))) for e in selected}
        present = {tuple(sorted(tuple(mesh.vertex_position(v)) for v in mesh.edge_vertices(e))): e for e in mesh.all_edge_ids()}
        assert mirrored <= set(present)
        assert not ({present[m] for m in mirrored} & selected)


def test_one_history_entry_and_the_commit_is_one_step(sessions):
    s = next(x for x in by_group(sessions, "R8") if x.mesh == "head_basemesh")
    out = run_and_evaluate(s.mesh, s.path)
    assert len(out.scene.history) == 1 and out.ed


def test_a_path_that_cuts_nothing_commits_nothing():
    mesh, pos, edge = grid()
    state = start_state("tie_grid")
    for path in ([], [rec(0, T_v(pos[(1.0, 1.0)]))],
                 [rec(0, T_v(pos[(1.0, 1.0)])), {"kind": "break", "reason": "edge"}, rec(1, T_v(pos[(2.0, 1.0)]))]):
        out = commit_session(state, path)
        assert out.status == "nothing", out.status
        assert_restored(out)


# ---------------------------------------------------------------------------------------------
# 7. Unchanged without symmetry
# ---------------------------------------------------------------------------------------------

def test_without_a_coordinator_the_commit_is_what_it_always_was():
    """No coordinator -> `_on_commit` resolves and checks exactly as before, with or without a definition: the committed
    state equals a plain `resolve_cross_face` + `check_commit` on a copy."""
    rnd = random.Random(SEED)
    for name in ("subd_cube", "head_basemesh"):
        with_definition = start_state(name)
        plain = Mesh.from_state(with_definition)
        plain.symmetry_definition = None
        for st in (with_definition, plain.export_state()):
            for path in fuzz_paths(with_definition, rnd, 25, region="both sides"):
                out = commit_session(st, path, coordinator=None)
                ref = Mesh.from_state(st)
                with quiet():
                    kr.resolve_cross_face(ref, [p for p in path if p["kind"] != "space"], st)
                check = kr.check_commit(ref, st)
                if check.after_state is None:
                    assert out.status in ("nothing", "rolled back")
                    assert content(out.mesh) == content(st)
                else:
                    assert out.status == "committed"
                    assert out.mesh.export_state() == check.after_state
                    assert len(out.scene.history) == 1


def test_begin_without_the_keyword_has_no_coordinator():
    knife, _scene = make_tool(fresh("tie_grid"), coordinator=None)
    assert knife._symmetric_commit is None
    knife, _scene = make_tool(fresh("tie_grid"))
    assert knife._symmetric_commit is coordinate_knife
    knife.cancel()
    knife.deactivate()


def test_a_refusal_needs_the_marker_the_tool_recognises():
    """The tool takes back only an exception that says it is a commit refusal; a plain `SymmetryRefusal` or anything else
    is a bug and propagates (the mesh is then whatever the callable left — the coordinator restores for every exception)."""
    state = start_state("tie_grid")

    def plain(mesh, path, before):
        raise SymmetryRefusal("Symmetrie: plain")

    knife, scene = make_tool(Mesh.from_state(state), coordinator=plain)
    knife._path = a_cut_path()
    with pytest.raises(SymmetryRefusal), quiet():
        knife.commit()
    assert len(scene.history) == 0


# ---------------------------------------------------------------------------------------------
# 8. Boundaries
# ---------------------------------------------------------------------------------------------

def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = ("." * node.level) + (node.module or "")
            names.add(base)
            names |= {f"{base}.{a.name}" for a in node.names}
    return names


def test_knife_tool_imports_nothing_from_symmetry():
    for name in _imports(_SRC / "topology" / "knife.py"):
        assert "symmetr" not in name, name


def test_the_coordinator_imports_neither_application_nor_the_tool():
    names = _imports(_SRC / "symmetric_knife.py")
    for name in names:
        assert "application" not in name, name
        assert not name.rstrip(".").endswith("topology.knife") and not name.endswith(".knife"), name
    assert ".topology.knife_resolve" in names and ".symmetric_ops" in names and ".symmetry_coordination" in names


def test_the_knife_is_declared_with_this_coordinator_since_slice_6c():
    """6b left the Knife undeclared and unwired; 6c declares it (the entry is the switch, D-b)."""
    assert CContext.KNIFE in symmetry_declarations.declared_c_contexts()
    assert symmetry_declarations.C_CONTEXT_COORDINATORS[CContext.KNIFE] is coordinate_knife


def test_a_live_application_knife_session_runs_the_coordinator_only_with_a_definition():
    from mirai.application import Application
    from mirai.interaction.input import Input

    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(800, 600)
    set_plane(app.scene.mesh)
    assert app.key_press(Input("key", "c", frozenset()))
    assert app.knife_active and app._knife._symmetric_commit is coordinate_knife
    assert app._knife._symmetric_view is not None
    assert app.key_press(Input("key", "ESCAPE", frozenset()))

    app.scene.mesh.symmetry_definition = None
    assert app.key_press(Input("key", "c", frozenset()))
    assert app.knife_active and app._knife._symmetric_commit is None and app._knife._symmetric_view is None


def test_the_probe_is_not_imported_by_src_or_by_these_tests():
    """The Discovery probe stays evidence. (The 6a test `tests/test_knife_kept_calls.py` still imports its generator for
    its fuzz; it is unchanged by this slice.)"""
    here = Path(__file__).resolve().parent
    mine = [here / "test_symmetric_knife.py", here / "symmetric_knife_support.py"]
    for path in list(_SRC.parent.rglob("*.py")) + mine:
        assert "symmetry_knife_probe" not in " ".join(_imports(path)), path


# ---------------------------------------------------------------------------------------------
# 9. Cost (numbers only, no threshold)
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["subd_cube", "head_basemesh", "tie_grid"])
def test_cost_symmetric_vs_one_sided_commit(name, capsys):
    """Median commit time of the symmetric commit and of the one-sided Knife on the same camera-free paths (the
    mesh carries the definition in both runs). Printed, not asserted against a threshold."""
    state = start_state(name)
    rnd = random.Random(SEED)
    sym, one = [], []
    for path in fuzz_paths(state, rnd, 120, region="normal side"):
        if not source_commits(state, path):
            continue
        for _ in range(2):    # the second run is the warm one
            a = commit_session(state, path)
            b = commit_session(state, path, coordinator=None)
        if a.status == b.status == "committed":
            sym.append(a.ms)
            one.append(b.ms)
    assert len(sym) >= 50
    m_s, m_o = statistics.median(sym), statistics.median(one)
    with capsys.disabled():
        print(f"\n[cost] {name}: n={len(sym)} median commit symmetric {m_s:.2f} ms, one-sided {m_o:.2f} ms "
              f"(x{m_s / m_o:.2f}); p95 {sorted(sym)[int(0.95 * (len(sym) - 1))]:.2f} / {sorted(one)[int(0.95 * (len(one) - 1))]:.2f} ms")
    assert m_s > 0 and m_o > 0
