"""Application: the Knife stays active after a commit (WP-KNIFE-01 UX1, PROVISIONAL).

Artist decisions (Manu, 2026-10-01): after a commit the Knife begins a fresh, empty session at once; `Ctrl+Z`
right after a commit, while that re-armed session is untouched, undoes the last commit and the Knife stays
active. Defaults of the handoff (not Artist-decided, `playground/experiments/knife_face/decision.md`, "WP-KNIFE-01
UX1"): Enter and a click outside both re-arm (A1); `Esc` leaves (A2); an empty commit keeps the tool (A3);
`Ctrl+Y` mirrors `Ctrl+Z` (A4); once a click was made the in-session rule of AD-017 holds unchanged (A5).

Headless, same fixture as `test_application_knife.py` (the framed default cube). `Application` has no grid
scene; the curved case runs on the head OBJ.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

# The head OBJ needs `examples/` on the path (same local setup as `test_application_obj_scene.py`).
_EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

from core import SelectionMode
from mirai.application import Application
from mirai.topology.knife_pick import knife_pick
from mirai.topology.knife_preview import target_position
from tests.mesh_invariants import assert_mesh_invariants
from tests.test_application_knife import (  # noqa: F401  (the `app` fixture)
    CTRL_Y,
    CTRL_Z,
    ENTER,
    ESC,
    HEIGHT,
    OUTSIDE,
    WIDTH,
    _begin,
    _click,
    _edge,
    _edge_screen,
    _history_depths,
    _key,
    _topology,
    _v,
    app,
)
from viewport.overlay import TOOL_ACTIVE_LAYER

HEAD_OBJ = _EXAMPLES_DIR / "meshes" / "head_basemesh.obj"
COMMITTED_TAIL = "next cut ready - Esc leaves the Knife"
EMPTY_TAIL = "Knife still active, Esc leaves"


def _front_cut(app) -> None:
    """Front face (z = +1): edge 5-6 at 0.5 -> edge 4-7 at 0.5 (two clicks, one cut)."""
    e56, e47 = _edge(app, _v(app, 5), _v(app, 6)), _edge(app, _v(app, 4), _v(app, 7))
    assert _click(app, _edge_screen(app, e56, 0.5)) is True
    assert _click(app, _edge_screen(app, e47, 0.5)) is True


def _top_cut(app) -> None:
    """Top face (y = +1): edge 2-6 at 0.5 -> edge 7-3 at 0.5."""
    e26, e73 = _edge(app, _v(app, 2), _v(app, 6)), _edge(app, _v(app, 7), _v(app, 3))
    assert _click(app, _edge_screen(app, e26, 0.5)) is True
    assert _click(app, _edge_screen(app, e73, 0.5)) is True


def _selection(app) -> tuple:
    s = app.selection
    return (s.mode, frozenset(s.vertices), frozenset(s.edges), frozenset(s.faces))


def _assert_fresh_session(app) -> None:
    """A re-armed session: active, no path, render data, the session engine on the current mesh, and the
    preview / pick cache consistent with the mesh as it is now."""
    assert app.knife_active
    knife = app._knife
    assert knife.path == []
    assert knife._mesh is app.scene.mesh
    assert _topology_of_state(knife._session_before) == _topology(app.scene.mesh)
    assert app.knife_render_data is not None
    assert app.viewport.tool_line_layers[TOOL_ACTIVE_LAYER] == []
    _assert_preview_current(app)
    _assert_pick_cache_current(app)


def _topology_of_state(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.endswith("_id_counter")}


def _assert_preview_current(app) -> None:
    """No stale target: the previewed element exists in the mesh, and it is what a fresh pick at the cursor
    gives (or nothing when there is no cursor)."""
    mesh = app.scene.mesh
    target = app._knife_target
    if target is not None:
        kind = target["kind"]
        assert {"vertex": mesh.is_valid_vertex, "edge": mesh.is_valid_edge,
                "face": mesh.is_valid_face}[kind](target[f"{kind}_id"]), target
    if app._cursor is None:
        assert target is None
    else:
        fresh = app._knife_pick(*app._cursor)
        assert target == (fresh if app._knife.accepts(fresh) else None)


def _assert_pick_cache_current(app) -> None:
    """The cached pick equals an uncached pick on the current mesh (cache invalidated on topology change)."""
    mesh = app.scene.mesh
    for x in range(40, WIDTH, 90):
        for y in range(40, HEIGHT, 90):
            cached = knife_pick(app.camera, mesh, x, y, WIDTH, HEIGHT, cache=app._pick_cache,
                                occlusion=app.display.show_faces)
            fresh = knife_pick(app.camera, mesh, x, y, WIDTH, HEIGHT, occlusion=app.display.show_faces)
            assert cached == fresh, (x, y)


# -- 1-3. a commit re-arms ----------------------------------------------------------------------


@pytest.mark.parametrize("finish", ["enter", "click_outside"])
def test_commit_keeps_the_knife_active_with_a_fresh_session(app, finish):
    app.key_press(_key("1"))  # Vertex mode before the session
    _begin(app)
    _front_cut(app)

    if finish == "enter":
        assert app.key_press(ENTER) is True
    else:
        assert _click(app, OUTSIDE) is True

    assert _history_depths(app) == (1, 0)
    assert app.selection.mode is SelectionMode.EDGE           # residue as before UX1
    assert len(app.selection.edges) == 1
    assert app.status_message == f"Knife committed (1 path edge selected); {COMMITTED_TAIL}"
    assert_mesh_invariants(app.scene.mesh, context="after a re-arming commit")
    _assert_fresh_session(app)


def test_the_re_armed_session_cuts_again_and_records_its_own_selection_history(app):
    _begin(app)
    _front_cut(app)
    app.key_press(ENTER)
    residue = _selection(app)

    _top_cut(app)
    assert app.key_press(ENTER) is True

    assert _history_depths(app) == (2, 0)
    assert len(app.selection.edges) == 1 and _selection(app) != residue
    assert app._selection_undo_stack[-1][0] == residue      # "before" of the second commit = the first's residue
    _assert_fresh_session(app)


def test_an_empty_commit_changes_nothing_and_keeps_the_knife(app):
    _begin(app)
    before = _topology(app.scene.mesh)
    selection = _selection(app)

    assert app.key_press(ENTER) is True

    assert _topology(app.scene.mesh) == before
    assert _selection(app) == selection
    assert _history_depths(app) == (0, 0)
    assert app.status_message == f"Knife: no cuts made, nothing committed - {EMPTY_TAIL}"
    _assert_fresh_session(app)


def test_a_start_point_only_commit_changes_nothing_and_keeps_the_knife(app):
    _begin(app)
    before = _topology(app.scene.mesh)
    _click(app, _edge_screen(app, _edge(app, _v(app, 5), _v(app, 6)), 0.5))

    assert app.key_press(ENTER) is True

    assert _topology(app.scene.mesh) == before
    assert _history_depths(app) == (0, 0)
    assert app.status_message.startswith("Knife: no cuts made, nothing committed")
    assert app.status_message.endswith(EMPTY_TAIL)
    _assert_fresh_session(app)


# -- 4. Esc leaves ------------------------------------------------------------------------------


def test_esc_in_a_re_armed_session_with_points_cancels_it_and_leaves(app):
    _begin(app)
    _front_cut(app)
    app.key_press(ENTER)
    mesh_after_commit, residue = _topology(app.scene.mesh), _selection(app)
    _top_cut(app)

    assert app.key_press(ESC) is True

    assert not app.knife_active
    assert _topology(app.scene.mesh) == mesh_after_commit
    assert _selection(app) == residue
    assert _history_depths(app) == (1, 0)
    assert app.status_message == "Knife cancelled"


def test_esc_in_a_fresh_re_armed_session_just_leaves(app):
    _begin(app)
    _front_cut(app)
    app.key_press(ENTER)
    mesh_after_commit, residue = _topology(app.scene.mesh), _selection(app)

    assert app.key_press(ESC) is True

    assert not app.knife_active
    assert _topology(app.scene.mesh) == mesh_after_commit
    assert _selection(app) == residue
    assert _history_depths(app) == (1, 0)
    assert all(not v for v in app.viewport.tool_line_layers.values())
    assert all(not v for v in app.viewport.tool_point_layers.values())


# -- 5-7. Ctrl+Z / Ctrl+Y right after a commit ---------------------------------------------------


def test_ctrl_z_right_after_a_commit_undoes_it_and_ctrl_y_redoes_it_knife_stays(app):
    app.key_press(_key("3"))  # Face mode, empty selection
    mesh = app.scene.mesh
    before_mesh, before_selection = _topology(mesh), _selection(app)
    _begin(app)
    _front_cut(app)
    app.key_press(ENTER)
    after_mesh, residue = _topology(mesh), _selection(app)

    assert app.key_press(CTRL_Z) is True
    assert _topology(mesh) == before_mesh
    assert _selection(app) == before_selection
    assert _history_depths(app) == (0, 1)
    assert_mesh_invariants(mesh, context="global undo from the Knife")
    _assert_fresh_session(app)

    assert app.key_press(CTRL_Y) is True
    assert _topology(mesh) == after_mesh
    assert _selection(app) == residue
    assert _history_depths(app) == (1, 0)
    _assert_fresh_session(app)

    # The session on the restored mesh cuts like any other.
    _top_cut(app)
    assert app.key_press(ENTER) is True
    assert _history_depths(app) == (2, 0)


def test_after_a_click_ctrl_z_is_in_session_only_and_never_falls_through(app):
    _begin(app)
    _front_cut(app)
    app.key_press(ENTER)
    mesh_after_commit = _topology(app.scene.mesh)
    _click(app, _edge_screen(app, _edge(app, _v(app, 2), _v(app, 6)), 0.5))

    assert app.key_press(CTRL_Z) is True                     # the click
    assert app._knife.path == []
    assert _history_depths(app) == (1, 0)

    assert app.key_press(CTRL_Z) is False                    # empty but touched: no fall-through (A5)
    assert app.status_message == "Knife: nothing to undo"
    assert _history_depths(app) == (1, 0)
    assert _topology(app.scene.mesh) == mesh_after_commit
    assert app.knife_active


def test_ctrl_y_after_an_in_session_redo_stays_in_session(app):
    _begin(app)
    _front_cut(app)
    app.key_press(ENTER)
    _click(app, _edge_screen(app, _edge(app, _v(app, 2), _v(app, 6)), 0.5))
    app.key_press(CTRL_Z)
    assert app.key_press(CTRL_Y) is True                     # the click is back
    assert len(app._knife.points) == 1
    assert app.key_press(CTRL_Y) is False                    # nothing more to redo in-session
    assert _history_depths(app) == (1, 0)


def test_two_commits_then_two_ctrl_z_undo_them_one_by_one(app):
    mesh = app.scene.mesh
    states = [(_topology(mesh), _selection(app))]
    _begin(app)
    _front_cut(app)
    app.key_press(ENTER)
    states.append((_topology(mesh), _selection(app)))
    _top_cut(app)
    app.key_press(ENTER)
    states.append((_topology(mesh), _selection(app)))

    assert app.key_press(CTRL_Z) is True
    assert (_topology(mesh), _selection(app)) == states[1]
    assert _history_depths(app) == (1, 1)
    _assert_fresh_session(app)

    assert app.key_press(CTRL_Z) is True
    assert (_topology(mesh), _selection(app)) == states[0]
    assert _history_depths(app) == (0, 2)
    _assert_fresh_session(app)

    assert app.key_press(CTRL_Y) is True
    assert app.key_press(CTRL_Y) is True
    assert (_topology(mesh), _selection(app)) == states[2]
    _assert_fresh_session(app)


def test_ctrl_z_with_nothing_to_undo_keeps_the_re_armed_session(app):
    _begin(app)
    _front_cut(app)
    app.key_press(ENTER)
    app.key_press(CTRL_Z)
    assert _history_depths(app) == (0, 1)

    assert app.key_press(CTRL_Z) is False
    assert app.status_message == "Knife: nothing to undo"
    assert _history_depths(app) == (0, 1)
    _assert_fresh_session(app)


def test_a_session_begun_with_c_keeps_the_in_session_rule(app):
    """The narrow rule is for the session re-armed by a commit (decision 2); a session begun with `C` is
    untouched too, but `Ctrl+Z` there stays in-session (AD-017) — an earlier History entry is not undone."""
    app.selection.mode = SelectionMode.EDGE
    app.selection.set({_edge(app, _v(app, 5), _v(app, 6))})
    app.key_press(_key("c"))                                 # Split: one History entry
    assert _history_depths(app) == (1, 0)
    mesh_after_split = _topology(app.scene.mesh)
    _begin(app)

    assert app.key_press(CTRL_Z) is False
    assert app.status_message == "Knife: nothing to undo"
    assert _history_depths(app) == (1, 0)
    assert _topology(app.scene.mesh) == mesh_after_split


# -- 8. session gate ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    [_key("w"), _key("e"), _key("r"), _key("1"), _key("2"), _key("3"),
     _key("d"), _key("d", "shift"), _key("c"), _key("x"), _key("z", "shift")],
    ids=lambda k: "+".join(sorted(k.modifiers) + [k.value]),
)
def test_session_gate_holds_in_a_re_armed_session(app, key):
    _begin(app)
    _front_cut(app)
    app.key_press(ENTER)
    mesh_state, selection = _topology(app.scene.mesh), _selection(app)
    display = (app.display.mode, app.display.show_edges)

    assert app.key_press(key) is False
    app.key_release(key)

    assert app.knife_active and app._knife.path == []
    assert _topology(app.scene.mesh) == mesh_state
    assert _selection(app) == selection
    assert (app.display.mode, app.display.show_edges) == display
    assert app.transform_command is None


# -- 9-10. preview and pick cache ---------------------------------------------------------------


def test_preview_is_current_after_re_arm_and_global_undo_redo(app):
    _begin(app)
    e56 = _edge(app, _v(app, 5), _v(app, 6))
    _front_cut(app)
    hover = _edge_screen(app, e56, 0.25)
    app.pointer_motion(*hover)                               # the cursor rests on an edge that the cut splits
    app.key_press(ENTER)
    assert app._knife_target is not None
    _assert_fresh_session(app)

    app.key_press(CTRL_Z)
    assert app._knife_target is not None
    _assert_fresh_session(app)
    app.key_press(CTRL_Y)
    _assert_fresh_session(app)


def test_re_arm_and_global_undo_without_a_cursor_do_not_crash(app):
    _begin(app)
    _front_cut(app)
    app.pointer_leave()
    assert app._cursor is None

    assert app.key_press(ENTER) is True
    _assert_fresh_session(app)
    assert app.key_press(CTRL_Z) is True
    _assert_fresh_session(app)
    assert app.key_press(CTRL_Y) is True
    _assert_fresh_session(app)


# -- curved mesh --------------------------------------------------------------------------------


def _head_app() -> Application:
    app = Application()
    app.init_scene("obj", obj_path=HEAD_OBJ)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _visible_quad_cut(app):
    """Two opposite edge midpoints of the first head quad whose midpoints the Knife picks as those edges."""
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        vs = mesh.face_vertices(fid)
        if len(vs) != 4:
            continue
        picks = []
        for a, b in ((vs[0], vs[1]), (vs[2], vs[3])):
            eid = _edge(app, a, b)
            pos = app.camera.project_to_screen(target_position(mesh, {"kind": "edge", "edge_id": eid, "t": 0.5}),
                                               WIDTH, HEIGHT)
            hit = knife_pick(app.camera, mesh, *pos, WIDTH, HEIGHT, occlusion=True)
            if hit.get("kind") != "edge" or hit["edge_id"] != eid:
                break
            picks.append(pos)
        if len(picks) == 2:
            return picks
    raise LookupError("no visible head quad")


def test_head_commit_re_arms_and_ctrl_z_ctrl_y_round_trip():
    app = _head_app()
    mesh = app.scene.mesh
    before = _topology(mesh)
    _begin(app)
    for pos in _visible_quad_cut(app):
        assert _click(app, pos) is True
    assert app.key_press(ENTER) is True
    after = _topology(mesh)
    assert after != before and _history_depths(app) == (1, 0)
    _assert_fresh_session(app)

    assert app.key_press(CTRL_Z) is True
    assert _topology(mesh) == before
    _assert_fresh_session(app)
    assert app.key_press(CTRL_Y) is True
    assert _topology(mesh) == after
    _assert_fresh_session(app)
