"""WP-KNIFE-01 UX2 — the pen lift in the Production `KnifeTool` (headless, tool level).

Artist decisions (Manu, 2026-10-02): one session holds several chains; `E` (and an `RMB` click) ends the
current chain without committing anything, the next click starts a new chain; a double-click closes the chain
and lifts the pen. Defaults D2–D5 (decision.md "WP-KNIFE-01 UX2"): `finish_chain()` closes when it can and
always lifts; the first click after a lift is a fresh start, an earlier own boundary point as the start
branches off it; the lift is one in-session step; nothing to lift is refused. The Application side (keys,
`RMB`, double-click timing, `Shift` midpoint snap) is `tests/test_application_knife_pen_lift.py`.

Grid fixture (4 x 4 unit quads in z = 0, `knife_parity_driver.build_grid`).
"""

from __future__ import annotations

import math

import tests._bootstrap  # noqa: F401

from mirai.topology.face_geometry import FaceFrame, segment_in_face
from mirai.topology.knife import CLOSE_NEEDS, EARLIER_INTERIOR, NOTHING_TO_LIFT
from tests.knife_parity_driver import begin, broken, build_grid, canon_faces, content, quiet, target, vef

LIFT = {"kind": "break", "reason": "lift"}

# quad (1, 1) of the grid and its sides; quad (2, 2) far from it
LEFT, RIGHT = ((1, 1, 0), (1, 2, 0)), ((2, 1, 0), (2, 2, 0))
BOTTOM, TOP = ((1, 1, 0), (2, 1, 0)), ((1, 2, 0), (2, 2, 0))
FAR_LEFT, FAR_RIGHT = ((2, 2, 0), (2, 3, 0)), ((3, 2, 0), (3, 3, 0))


def face(mesh, pos, dist_px=20.0) -> dict:
    for fid in mesh.all_face_ids():
        if FaceFrame(mesh, fid).height(pos) <= 1e-9 and segment_in_face(mesh, fid, pos, pos) == "inside":
            return {"kind": "face", "face_id": fid, "position": tuple(float(c) for c in pos), "distance_px": dist_px}
    raise LookupError(pos)


def edge(mesh, a, b, t):
    return target(None, mesh, ("e", tuple(map(float, a)), tuple(map(float, b)), t))


def own(tool, i):
    return {"kind": "point", "pid": tool.points[i]["pid"]}


def click(tool, t) -> bool:
    with quiet():
        acc = tool.accepts(t)
        ok = tool.click(t)
    assert acc == ok
    return ok


def lift(tool) -> bool:
    with quiet():
        return tool.lift()


def finish(tool) -> bool:
    with quiet():
        return tool.finish_chain()


def undo(tool) -> bool:
    with quiet():
        return tool.undo_step()


def redo(tool) -> bool:
    with quiet():
        return tool.redo_step()


def commit(tool):
    with quiet():
        cmd = tool.commit()
        tool.deactivate()
    return cmd


def session(chains, *, between=lift):
    """Play `chains` (each a list of `mesh -> target` callables) in one session on a fresh grid, `between`
    the chains; commit. Returns (mesh, scene, tool, before-state)."""
    mesh = build_grid()
    before = mesh.export_state()
    tool, scene = begin(mesh)
    for i, chain in enumerate(chains):
        if i:
            assert between(tool)
        for make in chain:
            assert click(tool, make(mesh)), tool.last_plan
    commit(tool)
    return mesh, scene, tool, before


def changed_faces(before_state, mesh) -> tuple[set, set]:
    """(faces gone, faces new) against `before_state`, position-based (id-free)."""
    ref = build_grid()
    ref.load_state(before_state)
    old, new = set(map(repr, canon_faces(ref))), set(map(repr, canon_faces(mesh)))
    return old - new, new - old


def vertices_at(mesh, pos) -> int:
    return sum(1 for v in mesh.all_vertex_ids() if math.dist(mesh.vertex_position(v), pos) < 1e-9)


A_CHAIN = [lambda m: edge(m, *LEFT, .5), lambda m: edge(m, *RIGHT, .5)]
B_CHAIN = [lambda m: edge(m, *FAR_LEFT, .5), lambda m: edge(m, *FAR_RIGHT, .5)]


# -- 1. the lift itself ---------------------------------------------------------------------------


def test_lift_ends_the_chain_without_touching_mesh_or_history():
    mesh = build_grid()
    before = content(mesh.export_state())
    tool, scene = begin(mesh)
    assert click(tool, edge(mesh, *LEFT, .5)) and click(tool, edge(mesh, *RIGHT, .5))

    assert lift(tool)

    assert tool.path[-1] == LIFT
    assert tool.last_plan.ok and tool.last_plan.lift
    assert tool.last_point is None and tool.chain_points == []
    assert len(tool.cut_segments) == 1
    assert tool.is_active
    assert len(scene.history) == 0 and content(mesh.export_state()) == before
    data = tool.hover(edge(mesh, *BOTTOM, .5))
    assert data["start"] is None


# -- 2. several chains, one commit ------------------------------------------------------------------


def test_after_a_lift_the_next_click_is_a_start_and_commit_cuts_both_chains_as_one_entry():
    mesh = build_grid()
    before = mesh.export_state()
    tool, scene = begin(mesh)
    for make in A_CHAIN:
        assert click(tool, make(mesh))
    b0 = edge(mesh, *FAR_LEFT, .5)
    assert not tool.accepts(b0)                    # without the lift: no shared face with the last point

    assert lift(tool)
    assert click(tool, b0) and tool.last_plan.start
    assert len(tool.cut_segments) == 1             # no segment from the first chain to the new start
    assert click(tool, edge(mesh, *FAR_RIGHT, .5))
    assert len(tool.cut_segments) == 2

    assert commit(tool) is not None
    assert len(scene.history) == 1
    assert broken(mesh, "grid") == []
    gone_ab, new_ab = changed_faces(before, mesh)
    mesh_a, _sa, _ta, before_a = session([A_CHAIN])
    mesh_b, _sb, _tb, before_b = session([B_CHAIN])
    gone_a, new_a = changed_faces(before_a, mesh_a)
    gone_b, new_b = changed_faces(before_b, mesh_b)
    assert new_ab == new_a | new_b and gone_ab == gone_a | gone_b
    assert vef(mesh) == "29/46/18"
    scene.history.undo()
    assert content(mesh.export_state()) == content(before)


def test_two_lifted_chains_crossing_in_one_face_share_one_intersection_vertex():
    mesh, scene, tool, before = session([A_CHAIN, [lambda m: edge(m, *BOTTOM, .5), lambda m: edge(m, *TOP, .5)]])
    assert len(scene.history) == 1
    res = tool.last_resolution
    assert res.applied == res.runs == 2
    assert vertices_at(mesh, (1.5, 1.5, 0.0)) == 1
    assert vef(mesh) == "30/48/19" and broken(mesh, "grid") == []
    scene.history.undo()
    assert content(mesh.export_state()) == content(before)


# -- 3. a start on an earlier own point -------------------------------------------------------------


def test_a_start_on_an_earlier_own_boundary_point_branches_off_it():
    mesh = build_grid()
    tool, scene = begin(mesh)
    assert click(tool, edge(mesh, *LEFT, .5)) and click(tool, edge(mesh, *RIGHT, .5))
    branch = tool.points[1]
    assert lift(tool)

    assert click(tool, own(tool, 1))
    assert tool.last_plan.start and tool.path[-1] is branch and tool.last_point is branch
    assert click(tool, edge(mesh, (3, 1, 0), (3, 2, 0), .5))

    assert commit(tool) is not None
    assert vertices_at(mesh, (2.0, 1.5, 0.0)) == 1     # one vertex for the shared point
    assert vef(mesh) == "28/45/18" and broken(mesh, "grid") == [] and len(scene.history) == 1


def test_a_start_on_an_earlier_interior_point_is_refused_as_today():
    """Current rule, unchanged by UX2: an earlier interior point cannot be clicked again (EARLIER_INTERIOR)."""
    mesh = build_grid()
    tool, _scene = begin(mesh)
    assert click(tool, edge(mesh, *LEFT, .5)) and click(tool, face(mesh, (1.5, 1.5, 0)))
    assert lift(tool)
    path = tool.path
    assert not click(tool, own(tool, 1))
    assert tool.last_plan.reason == EARLIER_INTERIOR and tool.path == path


# -- 4. the tail join per chain ----------------------------------------------------------------------


def test_a_lifted_chain_ending_inside_a_face_is_still_joined_to_the_nearest_corner():
    tail_chain = [lambda m: edge(m, *LEFT, .5), lambda m: face(m, (1.6, 1.7, 0))]
    mesh, scene, tool, before = session([tail_chain, B_CHAIN])
    assert tool.last_resolution.joined == 1 and not tool.last_resolution.dropped_tail
    mesh_t, _st, tool_t, before_t = session([tail_chain])
    mesh_b, _sb, _tb, before_b = session([B_CHAIN])
    assert tool_t.last_resolution.joined == 1
    gone, new = changed_faces(before, mesh)
    gone_t, new_t = changed_faces(before_t, mesh_t)
    gone_b, new_b = changed_faces(before_b, mesh_b)
    assert new == new_t | new_b and gone == gone_t | gone_b
    assert broken(mesh, "grid") == [] and len(scene.history) == 1


# -- 5. nothing to lift ---------------------------------------------------------------------------


def test_lift_with_nothing_to_lift_is_refused_and_changes_nothing():
    mesh = build_grid()
    tool, _scene = begin(mesh)
    assert not lift(tool)
    assert tool.last_plan.reason == NOTHING_TO_LIFT and tool.path == []
    assert click(tool, edge(mesh, *LEFT, .5)) and lift(tool)
    path = tool.path
    assert not lift(tool)
    assert tool.last_plan.reason == NOTHING_TO_LIFT and tool.path == path
    assert undo(tool) and tool.path == path[:-1]          # the refused lift added no step


# -- 6. undo / redo ----------------------------------------------------------------------------------


def test_undo_after_a_lift_removes_the_lift_only_and_redo_restores_it():
    mesh = build_grid()
    tool, _scene = begin(mesh)
    assert click(tool, edge(mesh, *LEFT, .5)) and click(tool, edge(mesh, *RIGHT, .5))
    last = tool.last_point
    before_lift = tool.path
    assert lift(tool)
    lifted = tool.path

    assert undo(tool)
    assert tool.path == before_lift and tool.last_point is last
    assert click(tool, edge(mesh, *TOP, .5))              # the chain continues from its last point
    assert undo(tool)
    assert redo(tool) and tool.last_point["kind"] == "edge"
    assert undo(tool) and tool.path == before_lift

    assert lift(tool) and undo(tool) and redo(tool)
    assert tool.path == lifted and tool.last_point is None
    assert undo(tool)
    assert click(tool, edge(mesh, *TOP, .5))
    assert not redo(tool)                                 # a new click clears the redo branch (the lift)


# -- 7. finish_chain (the double-click's second click) -------------------------------------------------


def test_finish_chain_closes_a_chain_of_three_and_lifts_in_one_step():
    mesh = build_grid()
    tool, scene = begin(mesh)
    for p in ((1.3, 1.3, 0), (1.7, 1.3, 0), (1.5, 1.7, 0)):
        assert click(tool, face(mesh, p))
    three = tool.path

    assert finish(tool)

    assert tool.last_plan.closing and tool.last_plan.cyclic and tool.last_plan.lift
    assert tool.path == three + [{"kind": "break", "reason": "closed", "cyclic": True}, LIFT]   # no seed
    assert tool.last_point is None and tool.chain_points == []
    assert len(tool.cut_segments) == 3
    assert undo(tool) and tool.path == three                # close + lift = one step
    assert undo(tool) and tool.path == three[:2]            # then the third point
    assert redo(tool) and redo(tool)
    assert commit(tool) is not None
    res = tool.last_resolution
    assert len(res.closed_shapes) == 1 and res.closed_shapes[0].built
    assert not res.short_shapes and not res.lost_continuation
    assert broken(mesh, "grid") == [] and len(scene.history) == 1


def test_finish_chain_with_fewer_than_three_points_only_lifts_and_says_why():
    mesh = build_grid()
    tool, _scene = begin(mesh)
    assert click(tool, edge(mesh, *LEFT, .5)) and click(tool, edge(mesh, *RIGHT, .5))
    two = tool.path
    assert finish(tool)
    assert tool.path == two + [LIFT]
    assert not tool.last_plan.closing and CLOSE_NEEDS in tool.last_plan.reason
    assert "not closed" in tool.last_plan.reason


def test_finish_chain_right_after_a_close_lifts_instead_of_the_seed():
    """A double-click on the chain's start: the first click closes (seed appended, as today), the second
    lifts — the seed is replaced, so the closed chain is not continued and leaves no trace at commit."""
    mesh = build_grid()
    tool, scene = begin(mesh)
    for p in ((1.3, 1.3, 0), (1.7, 1.3, 0), (1.5, 1.7, 0)):
        assert click(tool, face(mesh, p))
    assert click(tool, own(tool, 0)) and tool.last_plan.closing
    closed = tool.path
    assert tool.last_point is not None                      # the seed

    assert finish(tool)
    assert tool.path == closed[:-1] + [LIFT] and tool.last_point is None
    assert undo(tool) and tool.path == closed                # the seed is back
    assert redo(tool)
    commit(tool)
    res = tool.last_resolution
    assert len(res.closed_shapes) == 1 and res.closed_shapes[0].built
    assert not res.short_shapes and not res.lost_continuation and len(scene.history) == 1


def test_a_lift_right_after_a_close_replaces_the_seed_like_finish_chain():
    mesh = build_grid()
    tool, _scene = begin(mesh)
    for p in ((1.3, 1.3, 0), (1.7, 1.3, 0), (1.5, 1.7, 0)):
        assert click(tool, face(mesh, p))
    assert click(tool, own(tool, 0))
    closed = tool.path
    assert lift(tool)
    assert tool.path == closed[:-1] + [LIFT]
    commit(tool)
    assert not tool.last_resolution.short_shapes and not tool.last_resolution.lost_continuation


def test_regression_a_close_still_continues_from_its_start_without_a_lift():
    """Not changed by UX2: a click on the chain's start closes it and the next click continues from it."""
    mesh = build_grid()
    tool, _scene = begin(mesh)
    for p in ((1.3, 1.3, 0), (1.7, 1.3, 0), (1.5, 1.7, 0)):
        assert click(tool, face(mesh, p))
    start = tool.points[0]
    assert click(tool, own(tool, 0))
    assert tool.last_point is start and tool.chain_points == [start]
