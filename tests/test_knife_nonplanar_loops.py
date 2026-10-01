"""WP-KNIFE-01 S3b — loops at a single point (the bow-tie) on non-planar faces (Production only, headless).

Open point S3-j (`playground/experiments/knife_face/decision.md`, "One Knife S3" / "One Knife S3b"): the
bow-tie committed on flat faces (grid, cube) but on none of the 324 `head` quads. Q5 imports the same
resolver (`mirai.topology.knife_resolve`), so the Q5-vs-Production differential tests cannot see this —
the spec here is absolute: counts, invariants, History, undo / redo.

The recipe (S3b handoff §3), per quad with Newell frame `fr` and corners p0..p3: an edge point on p1-p2
at t = 0.6 (from p1), three interior points at bilinear (u, v) = (0.2, 0.5), (0.55, 0.1), (0.4, 0.9) of
the corners' 2D frame coordinates, lifted back into `fr`'s plane; the last click is the edge point again
(the own-point snap); commit. The third segment crosses the first: two loops at a point — loop A at the
crossing X, loop B at the edge point. On a flat quad: V+5 E+9 F+4, `loops_built == 2`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import tests._bootstrap  # noqa: F401

from core import FaceId, Mesh, Scene
from mirai.topology import knife_resolve
from mirai.topology.face_geometry import FaceFrame
from mirai.topology.knife import KnifeTool
from tests.knife_parity_driver import broken, build_grid, canon_faces, content, head_mesh, quiet

RECIPE_T = 0.6
RECIPE_UV = ((0.2, 0.5), (0.55, 0.1), (0.4, 0.9))
FLAT_DELTA = (5, 9, 4)


def _lift(fr: FaceFrame, xy) -> tuple:
    return tuple(fr.origin[k] + xy[0] * fr.u[k] + xy[1] * fr.v[k] for k in range(3))


@dataclass
class Bowtie:
    mesh: Mesh
    scene: Scene
    before: dict
    accepted: list
    delta: tuple
    resolution: object
    committed: bool


def play_bowtie(mesh: Mesh, fid: FaceId) -> Bowtie:
    """The recipe on quad `fid`, through the Production `KnifeTool`'s public session interface."""
    fr = FaceFrame(mesh, fid)
    vs = mesh.face_vertices(fid)
    p = fr.pts2

    def bilinear(u, v):
        return tuple((1 - u) * (1 - v) * p[0][k] + u * (1 - v) * p[1][k] + u * v * p[2][k] + (1 - u) * v * p[3][k]
                     for k in range(2))

    eid = next(x for x in mesh.all_edge_ids() if set(mesh.edge_vertices(x)) == {vs[1], vs[2]})
    t = RECIPE_T if mesh.edge_vertices(eid)[0] == vs[1] else 1.0 - RECIPE_T
    scene = Scene()
    scene.mesh = mesh
    tool = KnifeTool()
    before = mesh.export_state()
    targets = [{"kind": "edge", "edge_id": eid, "t": t}]
    targets += [{"kind": "face", "face_id": fid, "position": _lift(fr, bilinear(u, v)), "distance_px": 20.0}
                for u, v in RECIPE_UV]
    accepted = []
    with quiet():
        tool.activate()
        tool.begin(mesh=mesh, scene=scene, selection=scene.selection)
        for tgt in targets:
            accepted.append(tool.click(tgt))
        accepted.append(tool.click({"kind": "point", "pid": tool.path[0]["pid"]}))
        cmd = tool.commit()
        tool.deactivate()
    delta = (len(mesh.all_vertex_ids()) - len(before["vertices"]),
             len(mesh.all_edge_ids()) - len(before["edges"]),
             len(mesh.all_face_ids()) - len(before["faces"]))
    return Bowtie(mesh, scene, before, accepted, delta, tool.last_resolution, cmd is not None)


def assert_bowtie_built(run: Bowtie, scene_name: str) -> None:
    assert all(run.accepted)
    assert run.committed
    assert run.delta == FLAT_DELTA
    assert run.resolution.loops_built == 2
    assert not run.resolution.loops_dropped
    assert broken(run.mesh, scene_name) == []
    assert len(run.scene.history) == 1
    after = canon_faces(run.mesh)
    run.scene.history.undo()
    assert content(run.mesh.export_state()) == content(run.before)
    run.scene.history.redo()
    assert canon_faces(run.mesh) == after


def grid_quad(mesh: Mesh) -> FaceId:
    """The grid's quad (1, 1)-(2, 2)."""
    return next(fid for fid in mesh.all_face_ids()
                if min(mesh.vertex_position(x)[:2] for x in mesh.face_vertices(fid)) == (1.0, 1.0))


# -- 1. grid quad warped by one corner -----------------------------------------------------------

WARPS = (0.0, 1e-9, 1e-6, 1e-4, 1e-2, 1e-1)
WARPS_FAILING = {1e-4, 1e-2, 1e-1}       # S3b: refused before the fix (handoff §3)


@pytest.mark.parametrize("w", [pytest.param(w, marks=pytest.mark.xfail(strict=True, reason="S3-j"))
                               if w in WARPS_FAILING else w for w in WARPS])
def test_bowtie_on_a_grid_quad_warped_by_one_corner(w):
    mesh = build_grid()
    corner = next(x for x in mesh.all_vertex_ids() if mesh.vertex_position(x) == (1.0, 2.0, 0.0))
    mesh.set_vertex_position(corner, (1.0, 2.0, w))
    assert_bowtie_built(play_bowtie(mesh, grid_quad(mesh)), "grid-warped")


# -- 2. every head quad ---------------------------------------------------------------------------

HEAD_QUADS = 324


def test_head_has_the_quads_the_replay_walks():
    mesh = head_mesh()
    assert sorted(int(f) for f in mesh.all_face_ids()) == list(range(HEAD_QUADS))
    assert all(len(mesh.face_vertices(f)) == 4 for f in mesh.all_face_ids())


@pytest.mark.parametrize("fid", [pytest.param(i, marks=pytest.mark.xfail(strict=True, reason="S3-j"))
                                 for i in range(HEAD_QUADS)])
def test_bowtie_on_every_head_quad(fid):
    assert_bowtie_built(play_bowtie(head_mesh(), FaceId(fid)), "head")


# -- 3. the reason text says what happened -------------------------------------------------------

# A flat quad (head quad 62 laid flat in its Newell plane, scaled to size 1, rounded): loop B (at the edge
# point) gets its bridge first, and that bridge runs through loop A — loop A no longer lies inside one face.
# Nothing on this quad is non-planar, and the run does not cut through its own loop.
BRIDGE_THROUGH_LOOP_QUAD = ((0.0, 0.0, 0.0), (0.52, 0.03, 0.0), (0.7, 0.71, 0.0), (-0.3, 0.57, 0.0))


def _single_quad(corners) -> tuple[Mesh, FaceId]:
    mesh = Mesh()
    fid = mesh.add_face([mesh.add_vertex(c) for c in corners])
    return mesh, fid


@pytest.mark.xfail(strict=True, reason="S3-j: the reason text says 'the run cuts through its own loop again'")
def test_a_loop_split_by_another_loops_bridge_does_not_claim_the_run_crossed_it():
    mesh, fid = _single_quad(BRIDGE_THROUGH_LOOP_QUAD)
    run = play_bowtie(mesh, fid)
    assert all(run.accepted)
    assert not run.committed and run.delta == (0, 0, 0)
    assert content(mesh.export_state()) == content(run.before)
    assert sum(run.resolution.loops_dropped.values()) == 1
    assert knife_resolve.LOOP_CROSSED not in run.resolution.loops_dropped


def test_a_run_that_cuts_through_its_own_loop_keeps_its_reason():
    """P5 (the Lab's recorded case, grid quad (0, 0)): after the loop closes the run cuts back through
    it — that one *is* "the run cuts through its own loop again"."""
    mesh = build_grid()
    scene = Scene()
    scene.mesh = mesh
    tool = KnifeTool()
    before = mesh.export_state()
    fid = next(f for f in mesh.all_face_ids() if min(mesh.vertex_position(x)[:2] for x in mesh.face_vertices(f)) == (0.0, 0.0))

    def edge(a, b, t):
        eid = next(x for x in mesh.all_edge_ids()
                   if {mesh.vertex_position(v) for v in mesh.edge_vertices(x)} == {a, b})
        return {"kind": "edge", "edge_id": eid, "t": t if mesh.vertex_position(mesh.edge_vertices(eid)[0]) == a else 1 - t}

    clicks = [edge((1.0, 0.0, 0.0), (1.0, 1.0, 0.0), 0.3)]
    clicks += [{"kind": "face", "face_id": fid, "position": pos, "distance_px": 20.0}
               for pos in ((0.2, 0.6, 0.0), (0.8, 0.8, 0.0), (0.55, 0.15, 0.0), (0.3, 0.75, 0.0))]
    clicks.append(edge((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 0.9))
    with quiet():
        tool.activate()
        tool.begin(mesh=mesh, scene=scene, selection=scene.selection)
        assert all(tool.click(c) for c in clicks)
        assert tool.commit() is None
    assert dict(tool.last_resolution.loops_dropped) == {knife_resolve.LOOP_CROSSED: 1}
    assert content(mesh.export_state()) == content(before)
