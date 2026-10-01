"""WP-KNIFE-01 S3 — face points in the Production `KnifeTool` (headless, Production only).

The full comparison with the Lab's Q5 is `playground/tests/test_knife_q5_differential.py`; this module pins the
Production rules on their own: face records, the 9 px margin, close ≠ commit and the seed, earlier points,
refusals with their reasons, one History entry, the mesh untouched during the session, and seeded random
sessions with interior points that stay clean (grid / cube / head).
"""

from __future__ import annotations

import random

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh
from mirai.topology.face_geometry import FaceFrame, segment_in_face
from mirai.topology.knife import (
    CLOSE_NEEDS,
    CROSS_FACE,
    EARLIER_INTERIOR,
    SAME_POINT,
    TOO_CLOSE,
    KnifeTool,
)
from tests.knife_parity_driver import (
    HEAD_ASSET,
    SCENES,
    begin,
    broken,
    build_grid,
    canon_faces,
    content,
    quiet,
    target,
    vef,
)
from viewport.derived import triangulate_face


def face(mesh, pos, dist_px=20.0) -> dict:
    """The face-interior target at `pos` (a planar scene), as `knife_pick` returns it."""
    for fid in mesh.all_face_ids():
        if FaceFrame(mesh, fid).height(pos) <= 1e-9 and segment_in_face(mesh, fid, pos, pos) == "inside":
            return {"kind": "face", "face_id": fid, "position": tuple(float(c) for c in pos), "distance_px": dist_px}
    raise LookupError(pos)


def edge(mesh, a, b, t):
    return target(None, mesh, ("e", tuple(map(float, a)), tuple(map(float, b)), t))


def vertex(mesh, p):
    return target(None, mesh, ("v", tuple(map(float, p))))


def own(tool, i):
    return {"kind": "point", "pid": tool.points[i]["pid"]}


def click(tool, t) -> bool:
    with quiet():
        acc = tool.accepts(t)
        ok = tool.click(t)
    assert acc == ok
    return ok


def commit(tool):
    with quiet():
        cmd = tool.commit()
        tool.deactivate()
    return cmd


# quad (1, 1) of the 4 x 4 grid
LEFT, RIGHT = ((1, 1, 0), (1, 2, 0)), ((2, 1, 0), (2, 2, 0))


def test_a_bent_cut_through_two_interior_points_is_one_history_entry():
    mesh = build_grid()
    before = mesh.export_state()
    tool, scene = begin(mesh)
    for t in (edge(mesh, *LEFT, .5), face(mesh, (1.3, 1.3, 0)), face(mesh, (1.7, 1.7, 0)), edge(mesh, *RIGHT, .5)):
        assert click(tool, t)
        assert content(mesh.export_state()) == content(before)        # nothing cut while clicking
    assert [p["kind"] for p in tool.path] == ["edge", "face", "face", "edge"]
    assert len({p["pid"] for p in tool.path}) == 4
    assert tool.path[1]["position"] == (1.3, 1.3, 0.0) and "distance_px" not in tool.path[1]
    assert commit(tool) is not None
    assert vef(mesh) == "29/45/17" and len(scene.history) == 1        # 2 edge points + 2 interior points
    assert len(scene.selection.edges) == 3 and broken(mesh, "grid") == []
    scene.history.undo()
    assert content(mesh.export_state()) == content(before)


def test_an_interior_click_inside_the_edge_margin_is_refused():
    mesh = build_grid()
    tool, _scene = begin(mesh)
    assert click(tool, edge(mesh, *LEFT, .5))
    near = face(mesh, (1.5, 1.05, 0), dist_px=5.0)
    assert not click(tool, near) and tool.last_plan.reason == TOO_CLOSE
    assert not click(tool, dict(near, distance_px=None))                 # no clearance known: refused too
    assert click(tool, dict(near, distance_px=9.0))                       # exactly the margin: accepted


def test_closing_a_shape_does_not_commit_and_the_next_cut_continues_from_its_start():
    mesh = build_grid()
    tool, scene = begin(mesh)
    for p in ((1.3, 1.3, 0), (1.7, 1.3, 0), (1.5, 1.7, 0)):
        assert click(tool, face(mesh, p))
    start = tool.points[0]
    assert click(tool, own(tool, 0))
    assert tool.last_plan.closing and tool.last_plan.cyclic
    assert tool.path[-2] == {"kind": "break", "reason": "closed", "cyclic": True}
    assert tool.path[-1] is start and tool.last_point is start and tool.chain_points == [start]
    assert len(scene.history) == 0
    assert len(tool.cut_segments) == 3                                    # the closing segment included
    assert click(tool, edge(mesh, (1, 1, 0), (2, 1, 0), .5))              # from the closing point
    assert tool.cut_segments[-1] == (start, tool.points[-1])
    assert commit(tool) is not None and len(scene.history) == 1
    assert tool.last_resolution.closed_shapes and tool.last_resolution.closed_shapes[0].built
    assert broken(mesh, "grid") == []


def test_closing_needs_three_points_and_an_earlier_interior_point_is_no_target():
    mesh = build_grid()
    tool, _scene = begin(mesh)
    assert click(tool, face(mesh, (1.3, 1.3, 0)))
    assert click(tool, face(mesh, (1.7, 1.3, 0)))
    assert not click(tool, own(tool, 0)) and tool.last_plan.reason == CLOSE_NEEDS
    assert not click(tool, own(tool, 1)) and tool.last_plan.reason == SAME_POINT
    assert click(tool, face(mesh, (1.5, 1.7, 0)))
    assert not click(tool, own(tool, 1)) and tool.last_plan.reason == EARLIER_INTERIOR


def test_an_earlier_boundary_point_is_connected_and_the_chain_continues_from_it():
    mesh = build_grid()
    tool, _scene = begin(mesh)
    for t in (edge(mesh, *LEFT, .5), edge(mesh, (1, 1, 0), (2, 1, 0), .5), edge(mesh, *RIGHT, .5),
              face(mesh, (1.6, 1.6, 0))):
        assert click(tool, t)
    bottom = tool.points[1]
    assert click(tool, own(tool, 1)) and tool.last_plan.earlier and tool.last_point is bottom
    assert click(tool, edge(mesh, (1, 0, 0), (2, 0, 0), .5))             # on from the bottom point
    assert commit(tool) is not None
    assert tool.last_resolution.applied == tool.last_resolution.runs
    assert broken(mesh, "grid") == []


def test_an_interior_point_in_another_face_is_cross_face_and_refused():
    mesh = build_grid()
    tool, _scene = begin(mesh)
    assert click(tool, face(mesh, (1.5, 1.5, 0)))
    assert not click(tool, face(mesh, (2.5, 1.5, 0))) and tool.last_plan.reason == CROSS_FACE
    assert not click(tool, edge(mesh, (3, 1, 0), (3, 2, 0), .5)) and tool.last_plan.reason == CROSS_FACE


def test_the_last_click_inside_a_face_is_joined_to_the_nearest_corner_at_commit():
    mesh = build_grid()
    tool, scene = begin(mesh)
    assert click(tool, edge(mesh, (0, 0, 0), (0, 1, 0), .5))
    assert click(tool, face(mesh, (0.6, 0.7, 0)))
    assert commit(tool) is not None
    assert tool.last_resolution.joined == 1 and vef(mesh) == "27/43/17"
    corner = (1.0, 1.0, 0.0)                                              # nearest to (0.6, 0.7)
    assert any(corner in [mesh.vertex_position(x) for x in mesh.edge_vertices(e)] for e in scene.selection.edges)


def test_undo_and_redo_take_one_click_each_the_close_included():
    mesh = build_grid()
    tool, _scene = begin(mesh)
    for p in ((1.3, 1.3, 0), (1.7, 1.3, 0), (1.5, 1.7, 0)):
        click(tool, face(mesh, p))
    click(tool, own(tool, 0))
    closed = tool.path
    with quiet():
        assert tool.undo_step()
        assert len(tool.path) == 3 and tool.chain_points == tool.points
        assert tool.redo_step()
    assert tool.path == closed


def test_a_session_that_cuts_nothing_leaves_mesh_and_history_untouched():
    mesh = build_grid()
    before = mesh.export_state()
    tool, scene = begin(mesh)
    click(tool, face(mesh, (1.5, 1.5, 0)))                                # a lone interior click
    assert commit(tool) is None
    assert len(scene.history) == 0 and content(mesh.export_state()) == content(before)
    assert tool.last_resolution.short_shapes == [1]


# -- seeded random sessions with interior points (Production only) ------------------------------------

def _interior(rnd, mesh, fid):
    cyc = mesh.face_vertices(fid)
    pos = {x: mesh.vertex_position(x) for x in cyc}
    tri = rnd.choice(triangulate_face(cyc, pos))
    u, w = rnd.random(), rnd.random()
    if u + w > 1:
        u, w = 1 - u, 1 - w
    a, b, c = (pos[x] for x in tri)
    p = tuple(a[k] + u * (b[k] - a[k]) + w * (c[k] - a[k]) for k in range(3))
    centre = tuple((a[k] + b[k] + c[k]) / 3 for k in range(3))
    return tuple(centre[k] + 0.8 * (p[k] - centre[k]) for k in range(3))


def _random_target(rnd, tool, mesh):
    last = tool.last_point
    chain = tool.chain_points
    if len(chain) >= 3 and rnd.random() < 0.12:
        return {"kind": "point", "pid": chain[0]["pid"]}
    if tool.points and rnd.random() < 0.1:
        return {"kind": "point", "pid": rnd.choice(tool.points)["pid"]}
    if last is not None and rnd.random() < 0.9:
        faces = sorted({last["face_id"]} if last["kind"] == "face" else
                       (mesh.edge_faces(last["edge_id"]) if last["kind"] == "edge" else
                        {f for e in mesh.vertex_edges(last["vertex_id"]) for f in mesh.edge_faces(e)}), key=int)
    else:
        faces = sorted(mesh.all_face_ids(), key=int)
    fid = rnd.choice(faces)
    roll = rnd.random()
    if roll < 0.2:
        return {"kind": "vertex", "vertex_id": rnd.choice(mesh.face_vertices(fid))}
    if roll < 0.5:
        return {"kind": "edge", "edge_id": rnd.choice(mesh.face_edges(fid)), "t": rnd.uniform(0.1, 0.9)}
    return {"kind": "face", "face_id": fid, "position": _interior(rnd, mesh, fid), "distance_px": 20.0}


@pytest.mark.parametrize("scene_name,runs", [("grid", 80), ("cube", 80), ("head", 20)])
def test_seeded_random_sessions_with_interior_points_stay_clean(scene_name, runs):
    """Per session: accepts() == click(); the mesh untouched before commit; at most one History entry,
    undone / redone exactly; no rollback; the geometry check is clean."""
    if scene_name == "head" and not HEAD_ASSET.is_file():
        pytest.skip("head asset not found (examples/meshes/)")
    rnd = random.Random(20261001 + 3)
    committed = interior = 0
    for run_index in range(runs):
        mesh: Mesh = SCENES[scene_name]()
        for _session in range(rnd.randint(1, 2)):
            before = mesh.export_state()
            tool, scene = begin(mesh)
            for _ in range(rnd.randint(2, 8)):
                op = rnd.random()
                with quiet():
                    if op < 0.07:
                        tool.undo_step()
                    elif op < 0.1:
                        tool.redo_step()
                    else:
                        t = _random_target(rnd, tool, mesh)
                        assert tool.accepts(t) is tool.click(t), (scene_name, run_index, t)
                assert content(mesh.export_state()) == content(before)
            interior += sum(1 for p in tool.points if p["kind"] == "face")
            cmd = commit(tool)
            context = f"{scene_name} run {run_index}"
            assert tool.last_problem is None, context
            assert len(scene.history) == (0 if cmd is None else 1), context
            if cmd is None:
                assert content(mesh.export_state()) == content(before), context
                continue
            committed += 1
            assert broken(mesh, scene_name) == [], context
            after = canon_faces(mesh)
            scene.history.undo()
            assert content(mesh.export_state()) == content(before), context
            scene.history.redo()
            assert canon_faces(mesh) == after, context
    assert committed > runs // 3 and interior > runs
