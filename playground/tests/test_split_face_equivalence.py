"""WP-KNIFE-00 — `Mesh.split_face` against the Knife Face Lab stand-ins (equivalence oracle).

The Core contract tests live in `tests/test_core.py` (`test_split_face_*`) and do not import
`playground`; this file only checks that the new primitive builds the **same faces** as the Lab
functions it is meant to replace (`playground/experiments/knife_face/engine.py`):

- FC1–FC4 (`docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md` §2): one `split_face` call vs one
  `split_face_path` call;
- FC6 / closed shape with 2 bridges: two `split_face` calls (bv1 → arc → bv2, then loop[i2] → other
  arc → loop[i1]) vs `close_loop_with_bridges`;
- loop at a point, 1 bridge: two calls (x → c1..cj → bridge end, then cj → c(j+1).. → x) vs
  `close_loop_at_vertex`;

on the grid, the cube (its folds: neighbouring faces at 90°) and the head (non-planar quads) — the
gap the discovery named (the `--b2c` probe ran on the grid only).

Faces are compared position-canonically (rotation-normalised cycles, winding kept, ids ignored).
ID shape (asserted below, not "fixed"): one call allocates exactly the Lab's ids (same sets of new
vertex, edge and face ids); the two-call constructions allocate the same vertices and edges but one
FaceId more than the Lab's 3-way split — the intermediate face of call 1 is burned (AD-001: no reuse).

Which piece hosts call 2 is decided by winding, not by trying both: the inner face must run like the
parent (the Lab's own `loop_matches_winding` rule), so call 2 goes into the piece that walks the
call-1 path in the inner face's direction. That choice is the resolver's (S1) policy, not Core's.

Result 2026-10-01: every case on every scene gives the same faces (grid 2, cube 6, head 15 quads —
the 6 least planar plus every 40th; 5 single-call cases, 5 closed shapes, 8 loops at a point per
quad); no case needs more than the calls above, and the Lab refused none of them. Timing on head
(this machine, median): two `split_face` calls 0.08 ms vs the Lab's 3-way split 0.28 ms; one call
0.03 ms vs `split_face_path` 0.12 ms (the Lab's `_find_edge` scans every edge) — negligible.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT), str(_REPO_ROOT / "tests"), str(_REPO_ROOT / "examples"),
           str(_REPO_ROOT / "experiments" / "rigging-skinning-morphing")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from core import Mesh  # noqa: E402
from core.mesh import MeshError  # noqa: E402
from mesh_invariants import assert_mesh_invariants  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj, create_cube  # noqa: E402
from playground._paths import DEFAULT_HEAD_ASSET  # noqa: E402
from playground.experiments.knife_face.engine import (  # noqa: E402
    close_loop_at_vertex,
    close_loop_with_bridges,
    loop_matches_winding,
    select_bridge,
    split_face_path,
)


# -- scenes ------------------------------------------------------------------------------

def _grid(n: int = 4) -> Mesh:
    mesh, p = Mesh(), {}
    for r in range(n + 1):
        for c in range(n + 1):
            p[(r, c)] = mesh.add_vertex((float(c), float(r), 0.0))
    for r in range(n):
        for c in range(n):
            mesh.add_face([p[(r, c)], p[(r, c + 1)], p[(r + 1, c + 1)], p[(r + 1, c)]])
    return mesh


def _nonplanarity(mesh: Mesh, face) -> float:
    a, b, c, d = (mesh.vertex_position(v) for v in mesh.face_vertices(face))
    diag = [(c[k] - a[k]) for k in range(3)], [(d[k] - b[k]) for k in range(3)]
    n = (diag[0][1] * diag[1][2] - diag[0][2] * diag[1][1],
         diag[0][2] * diag[1][0] - diag[0][0] * diag[1][2],
         diag[0][0] * diag[1][1] - diag[0][1] * diag[1][0])
    length = sum(x * x for x in n) ** 0.5 or 1.0
    # Distance between the two diagonals along their common normal: 0 for a planar quad.
    return abs(sum(n[k] * (b[k] - a[k]) for k in range(3))) / length


_HEAD_STATE: dict | None = None


def _scene(name: str) -> tuple[Mesh, list]:
    """The mesh and the quad faces to cut in it (deterministic)."""
    global _HEAD_STATE
    if name == "grid":
        mesh = _grid()
        return mesh, sorted(mesh.all_face_ids(), key=int)[5:7]
    if name == "cube":
        mesh = create_cube()
        return mesh, sorted(mesh.all_face_ids(), key=int)
    if _HEAD_STATE is None:
        _HEAD_STATE = build_core_scene_from_obj(DEFAULT_HEAD_ASSET).mesh.export_state()
    mesh = Mesh.from_state(_HEAD_STATE)
    faces = sorted(mesh.all_face_ids(), key=int)
    bent = sorted(faces, key=lambda f: -_nonplanarity(mesh, f))[:6]
    spread = faces[::40]
    return mesh, list(dict.fromkeys(bent + spread))


SCENES = ("grid", "cube", "head")


# -- comparison ----------------------------------------------------------------------------

def _r(p):
    return tuple(round(c, 9) + 0.0 for c in p)


def canon_faces(mesh: Mesh) -> frozenset:
    """Faces as position cycles, rotation-normalised, winding kept — independent of ids."""
    out = []
    for f in mesh.all_face_ids():
        cyc = [_r(mesh.vertex_position(v)) for v in mesh.face_vertices(f)]
        k = cyc.index(min(cyc))
        out.append(tuple(cyc[k:] + cyc[:k]))
    return frozenset(out)


def _new_ids(before: dict, mesh: Mesh) -> tuple[set, set, set]:
    return (
        {int(v) for v in mesh.all_vertex_ids()} - {int(k) for k in before["vertices"]},
        {int(e) for e in mesh.all_edge_ids()} - {int(k) for k in before["edges"]},
        {int(f) for f in mesh.all_face_ids()} - {int(k) for k in before["faces"]},
    )


def _assert_same(ref: Mesh, alt: Mesh, label: str) -> None:
    assert_mesh_invariants(ref, context=f"{label} (Lab)")
    assert_mesh_invariants(alt, context=f"{label} (split_face)")
    assert canon_faces(alt) == canon_faces(ref), f"{label}: different faces"


# -- geometry helpers ------------------------------------------------------------------------

def _bilinear(mesh: Mesh, face, u: float, v: float):
    return _bilinear_from(mesh, mesh.face_vertices(face), u, v)


def _bilinear_from(mesh: Mesh, corners, u: float, v: float):
    """Point (u, v) of the quad with these corners, u along corners[0] -> corners[1]."""
    c0, c1, c2, c3 = (mesh.vertex_position(x) for x in corners)
    return tuple((1 - u) * (1 - v) * c0[k] + u * (1 - v) * c1[k] + u * v * c2[k] + (1 - u) * v * c3[k]
                 for k in range(3))


def _edge(mesh: Mesh, a, b):
    return next(e for e in mesh.vertex_edges(a) if set(mesh.edge_vertices(e)) == {a, b})


def _split_at(mesh: Mesh, a, b, t: float):
    """Split edge a-b at t measured from a; returns the new vertex."""
    e = _edge(mesh, a, b)
    return mesh.split_edge(e, t if mesh.edge_vertices(e)[0] == a else 1.0 - t)[0]


def _parent_positions(mesh: Mesh, face) -> list:
    return [mesh.vertex_position(v) for v in mesh.face_vertices(face)]


def _walks(mesh: Mesh, face, u, w) -> bool:
    """True if `face`'s boundary steps directly from u to w."""
    b = mesh.face_vertices(face)
    return b[(b.index(u) + 1) % len(b)] == w


# -- FC1–FC4: one call ------------------------------------------------------------------------

def _single_cases(mesh: Mesh, face):
    """(name, prepare(mesh) -> (a, b), positions) for FC1–FC4 in quad `face`."""
    c = mesh.face_vertices(face)

    def fc1(m):
        return _split_at(m, c[0], c[1], 0.3), _split_at(m, c[2], c[3], 0.4)

    def fc3(m):
        a = _split_at(m, c[0], c[1], 0.3)
        return a, _split_at(m, a, c[1], 0.5)

    def corners(m):
        return c[0], c[1]

    return [
        ("FC1 edge -> 1 point -> edge", fc1, [_bilinear(mesh, face, 0.45, 0.5)]),
        ("FC2 edge -> 2 points -> edge", fc1, [_bilinear(mesh, face, 0.35, 0.35), _bilinear(mesh, face, 0.6, 0.65)]),
        ("FC3 notch through one edge", fc3, [_bilinear(mesh, face, 0.5, 0.3)]),
        ("FC4 vertex -> point -> adjacent vertex", corners, [_bilinear(mesh, face, 0.5, 0.35)]),
        ("FC1 reversed arguments", lambda m: fc1(m)[::-1], [_bilinear(mesh, face, 0.45, 0.5)]),
    ]


@pytest.mark.parametrize("scene", SCENES)
def test_single_call_cases_give_the_lab_faces_and_ids(scene):
    base, faces = _scene(scene)
    state = base.export_state()
    compared = 0
    for face in faces:
        for name, prepare, positions in _single_cases(base, face):
            label = f"{scene} face {int(face)} {name}"
            ref, alt = Mesh.from_state(state), Mesh.from_state(state)
            a, b = prepare(ref)
            assert prepare(alt) == (a, b)
            before = ref.export_state()
            split_face_path(ref, face, a, b, positions)
            new_vs, new_es, f1, f2 = alt.split_face(face, a, b, positions)
            _assert_same(ref, alt, label)
            assert _new_ids(before, alt) == _new_ids(before, ref), f"{label}: different new ids"
            assert (len(new_vs), len(new_es)) == (len(positions), len(positions) + 1)
            compared += 1
    assert compared == 5 * len(faces)


# -- FC6 closed shape: two calls -------------------------------------------------------------

def _closed_shape_two_calls(mesh: Mesh, face, loop, i1, bv1, i2, bv2) -> None:
    """bv1 -> loop[i1] .. loop[i2] -> bv2, then loop[i2] -> (other arc) -> loop[i1] in the piece
    that walks the first arc in the inner face's (= parent's) direction."""
    k = len(loop)
    fwd = [(i1 + j) % k for j in range((i2 - i1) % k + 1)]               # i1 .. i2, loop order
    back = [(i2 + j) % k for j in range((i1 - i2) % k + 1)]              # i2 .. i1, loop order
    # Call 1 takes the longer arc so call 2 never joins two loop points that call 1 made adjacent.
    first, second = (fwd, back) if len(fwd) >= len(back) else (back[::-1], fwd[::-1])
    wound_as_clicked = loop_matches_winding(loop, _parent_positions(mesh, face))
    vs, _es, f1, f2 = mesh.split_face(face, bv1, bv2, [loop[i] for i in first])
    # The inner face runs first arc, then second arc; it must run like the parent.
    along = (first == fwd) == wound_as_clicked
    host = next(f for f in (f1, f2) if _walks(mesh, f, vs[0], vs[1]) == along)
    mesh.split_face(host, vs[-1], vs[0], [loop[i] for i in second[1:-1]])



def _loops(mesh: Mesh, face):
    ccw = [_bilinear(mesh, face, u, v) for u, v in ((0.3, 0.3), (0.7, 0.3), (0.7, 0.7), (0.3, 0.7))]
    tri = [_bilinear(mesh, face, u, v) for u, v in ((0.3, 0.25), (0.75, 0.4), (0.4, 0.7))]
    five = [_bilinear(mesh, face, u, v) for u, v in ((0.5, 0.2), (0.8, 0.45), (0.65, 0.8), (0.3, 0.75), (0.2, 0.4))]
    return [("square, parent winding", ccw), ("square, clicked backwards", ccw[::-1]),
            ("triangle", tri), ("triangle backwards", tri[::-1]), ("pentagon", five)]


@pytest.mark.parametrize("scene", SCENES)
def test_closed_shape_is_two_split_face_calls(scene):
    base, faces = _scene(scene)
    state = base.export_state()
    compared = 0
    for face in faces:
        for name, loop in _loops(base, face):
            label = f"{scene} face {int(face)} closed shape, {name}"
            ref, alt = Mesh.from_state(state), Mesh.from_state(state)
            i1, bv1, i2, bv2 = select_bridge(ref, ref.face_vertices(face), loop)
            close_loop_with_bridges(ref, face, loop, i1, bv1, i2, bv2)
            _closed_shape_two_calls(alt, face, loop, i1, bv1, i2, bv2)
            _assert_same(ref, alt, label)
            ref_state, alt_state = ref.export_state(), alt.export_state()
            assert alt_state["vertex_id_counter"] == ref_state["vertex_id_counter"]
            assert alt_state["edge_id_counter"] == ref_state["edge_id_counter"]
            assert alt_state["face_id_counter"] == ref_state["face_id_counter"] + 1, f"{label}: burned FaceId"
            compared += 1
    assert compared == 5 * len(faces)


# -- loop at a point: two calls --------------------------------------------------------------

def _loop_at_point_two_calls(mesh: Mesh, face, x, pts, j, w) -> None:
    """x -> c1..cj -> w (the Lab's bridge end), then cj -> c(j+1).. -> x in the piece that walks
    x -> c1 in the loop face's (= parent's) direction."""
    along = loop_matches_winding([mesh.vertex_position(x)] + list(pts), _parent_positions(mesh, face))
    vs, _es, f1, f2 = mesh.split_face(face, x, w, pts[:j + 1])
    host = next(f for f in (f1, f2) if _walks(mesh, f, x, vs[0]) == along)
    mesh.split_face(host, vs[-1], x, pts[j + 1:])


@pytest.mark.parametrize("scene", SCENES)
def test_loop_at_a_point_is_two_split_face_calls(scene):
    base, faces = _scene(scene)
    state = base.export_state()
    compared = refused = 0
    for face in faces:
        corners = base.face_vertices(face)
        for x_index in range(4):
            rot = corners[x_index:] + corners[:x_index]
            # (u, v) measured from corner x: a small loop leaving x and coming back to it.
            pts0 = [(0.4, 0.2), (0.6, 0.5), (0.2, 0.4)]
            for name, uv in (("clicked one way", pts0), ("clicked the other way", pts0[::-1])):
                label = f"{scene} face {int(face)} loop at corner {x_index}, {name}"
                ref, alt = Mesh.from_state(state), Mesh.from_state(state)
                pts = [_bilinear_from(ref, rot, u, v) for u, v in uv]
                x = rot[0]
                try:
                    loop_vs, _f_loop, ring, _edges = close_loop_at_vertex(ref, face, x, pts)
                except MeshError:
                    refused += 1          # the Lab's own geometry checks refuse it: nothing to compare
                    continue
                loop_set = set(loop_vs)
                c, w = next((u, v) for f in ring
                            for u, v in zip(ref.face_vertices(f), ref.face_vertices(f)[1:] + ref.face_vertices(f)[:1])
                            if u in loop_set and v not in loop_set and v != x)
                _loop_at_point_two_calls(alt, face, x, pts, loop_vs.index(c), w)
                _assert_same(ref, alt, label)
                ref_state, alt_state = ref.export_state(), alt.export_state()
                assert alt_state["vertex_id_counter"] == ref_state["vertex_id_counter"]
                assert alt_state["edge_id_counter"] == ref_state["edge_id_counter"]
                # The Lab's first bridge candidate fits in every case here (no retry, which would burn
                # FaceIds on the Lab side too), so the difference is exactly the intermediate face.
                assert alt_state["face_id_counter"] == ref_state["face_id_counter"] + 1, f"{label}: burned FaceId"
                compared += 1
    assert compared >= len(faces) * 4, f"{scene}: only {compared} compared, {refused} refused by the Lab"
    assert refused == 0, f"{scene}: the Lab refused {refused} case(s) - no longer all compared"

