"""The coordinated tools under symmetry, end to end through `Application` (AD-SYM-03, AD-SYM-04).

Ported 2026-10-24 from the Symmetry Lab's app-path tests (`experiments/symmetry_lab/tests/test_app_lab_*`,
removed with the Lab; last state in commit `61ebe77`). The Lab ran these cases through its own key path and
MARK/BLOCK gate; since AD-SYM-04 A1-A3 the same behaviour is the Production app's, so they run here on a plain
`Application()` with its default bindings and no `command_gate` - what `src/main.py` builds. Gate-, HUD- and
Lab-key-only cases were not ported. The coordinators themselves are tested in `test_symmetric_*.py`; the
smoke per tool and the Shift+S cycle are `test_application_symmetry_cycle.py`.

- hover target (A4/E7/E8/E9): W on a hovered paired vertex moves it and its partner, target fixed at the press;
- W/E/R: one Undo step each, exact Esc, constraints keep the pair mirrored, seam rules (rotate only about the
  plane normal, seam vertices stay on the plane), symmetry off moves only the selection;
- `C`: Split / Edge Connect / Vertex Connect coordinated as one Undo step, residue on the side worked on,
  refusals visible and side-effect free; the Knife session coordinated, its mirror-variant key, a pending
  session keeps the definition it started with;
- `T`: coordinated Extrude, caps on the working side, seam caps extrude again, exact Esc, visible refusals;
- Delete / Dissolve / Dissolve (no cleanup): coordinated as one Undo step on head and cube, seam rules
  (seam face pair, seam edge refused, crossing edge merges two seam edges), symmetry off is one-sided.
"""

from __future__ import annotations

import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import SelectionMode  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.application import KNIFE_MIRROR_VARIANT_KEY, Application  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.interaction.tools.move import MoveTool  # noqa: E402
from mirai.symmetric_extrude import TEXT_EXTRUDE_SPANNING  # noqa: E402
from mirai.symmetric_ops import TEXT_SEAM_DISSOLVE, TEXT_UNPAIRED  # noqa: E402
from mirai.symmetry import (  # noqa: E402
    CorrespondenceState,
    SymmetryState,
    mirror_position,
    symmetry_state,
    vertex_correspondence,
)
from mirai.symmetry_axis import AXIS_NORMALS, ORIGIN, current_axis  # noqa: E402
from mirai.symmetry_coordination import SymmetryIndex, completeness_report  # noqa: E402
from mirai.topology.knife_pick import knife_pick  # noqa: E402
from mirai.viewport.picking import pick_nearest_vertex  # noqa: E402

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)

SHIFT_S = Input("key", "s", frozenset({"shift"}))
W, E, R, T = Input("key", "w"), Input("key", "e"), Input("key", "r"), Input("key", "t")
X, Y, Z = Input("key", "x"), Input("key", "y"), Input("key", "z")
C = Input("key", "c")
ENTER = Input("key", "enter")
ESC = Input("key", "ESCAPE")
DELETE = Input("key", "delete")
DISSOLVE = Input("key", "backspace")
DISSOLVE_NO_CLEANUP = Input("key", "backspace", frozenset({"ctrl"}))
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
VARIANT = Input("key", KNIFE_MIRROR_VARIANT_KEY)
LMB = Input("mouse", "LEFT")

V_MODE, E_MODE, F_MODE = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE
DRAGS = [(40, 2), (30, -3), (20, 7)]
MOVE_DRAGS = [(6, 2), (5, -3), (4, 7)]


# -- set-up and helpers -----------------------------------------------------------------------


def make_app(asset: str = "subd_cube") -> Application:
    app = Application()
    app.init_scene("obj", obj_path=asset_path(asset))
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.pointer_motion(*MISS)
    return app


def symmetric_app(asset: str = "subd_cube") -> Application:
    """`asset` with symmetry X set by Shift+S (its own history entry)."""
    app = make_app(asset)
    assert app.key_press(SHIFT_S) is True
    assert current_axis(app.scene.mesh) == "X"
    app.pointer_motion(*MISS)
    return app


def topology_state(app) -> dict:
    return {k: v for k, v in app.scene.mesh.export_state().items() if not k.endswith("_id_counter")}


def selection_state(app) -> tuple:
    s = app.selection
    return (s.mode, frozenset(s.vertices), frozenset(s.edges), frozenset(s.faces))


def select(app, mode, ids) -> None:
    app.selection.clear()
    app.selection.mode = mode
    setattr(app.selection, {V_MODE: "vertices", E_MODE: "edges", F_MODE: "faces"}[mode], set(ids))


def select_vertices(app, *vids) -> None:
    app.selection.set(set(vids))
    app.viewport.on_selection_changed()


def screen(app, vid):
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


def move_mouse(app, drags=DRAGS, start=(400.0, 300.0)) -> None:
    """Pointer motion without a button while a transform key is held."""
    x, y = start
    for dx, dy in drags:
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, float(dx), float(dy))


def hold(app, key, drags=DRAGS) -> None:
    assert app.key_press(key)
    move_mouse(app, drags)
    app.key_release(key)


def assert_clean(app) -> None:
    mesh = app.scene.mesh
    report = completeness_report(mesh)
    assert not (report.unpaired_vertices | report.faces_without_partner | report.edges_without_partner)
    assert not (report.self_mirrored_faces | report.dead_seam_ids)
    assert symmetry_state(mesh) is SymmetryState.VALID


def mirrored_ok(app, vid, partner) -> bool:
    mesh = app.scene.mesh
    return mesh.vertex_position(partner) == mirror_position(mesh.vertex_position(vid), ORIGIN, AXIS_NORMALS["X"])


def vertex_in_state(app, state):
    corr = vertex_correspondence(app.scene.mesh)
    return min(v for v, c in corr.items() if c.state is state)


def paired(app):
    vid = vertex_in_state(app, CorrespondenceState.PAIRED)
    return vid, vertex_correspondence(app.scene.mesh)[vid].partner


def same_side_pair(app, vid):
    """A second paired vertex on `vid`'s side and its partner: Rotate/Scale pivot per side (2026-10-03), so a
    single vertex would rotate/scale about itself."""
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    side = mesh.vertex_position(vid)[0] > 0
    for w in sorted(mesh.all_vertex_ids(), key=int):
        c = corr[w]
        if w != vid and c.state is CorrespondenceState.PAIRED and (mesh.vertex_position(w)[0] > 0) == side:
            return w, c.partner
    raise AssertionError("no second paired vertex on the same side")


def plus_x_quad(app):
    """A quad entirely on the +X side (no vertex on x = 0)."""
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) == 4 and all(mesh.vertex_position(v)[0] > 1e-9 for v in vids):
            return fid
    raise AssertionError("no quad entirely on the +X side")


def plus_x_edge(app):
    mesh = app.scene.mesh
    for eid in sorted(mesh.all_edge_ids(), key=int):
        if all(mesh.vertex_position(v)[0] > 0.0 for v in mesh.edge_vertices(eid)):
            return eid
    raise AssertionError("no edge on the +X side")


def displace(app, vertex) -> None:
    """Move a +X vertex off its mirror position: it and its edges/faces lose their partner."""
    mesh = app.scene.mesh
    x, y, z = mesh.vertex_position(vertex)
    mesh.set_vertex_position(vertex, (x + 0.01, y, z))


def assert_refused_twice(app, key, text) -> None:
    before = (topology_state(app), selection_state(app), len(app.history))
    serial = app.status_serial
    for n in (1, 2):
        assert app.key_press(key) is False
        assert app.status_serial == serial + n
        assert app.status_message == text
    assert (topology_state(app), selection_state(app), len(app.history)) == before


# -- the Move target from the hover (A4 / E7 / E8 / E9) ----------------------------------------


@pytest.fixture
def hover_app():
    app = symmetric_app()
    assert app.selection.is_empty()
    return app


def visible_pairs(app) -> list[tuple]:
    mesh = app.scene.mesh
    corr = vertex_correspondence(mesh)
    out = []
    for vid in sorted(mesh.all_vertex_ids()):
        sx, sy = screen(app, vid)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) != vid:
            continue
        if corr[vid].state is CorrespondenceState.PAIRED:
            out.append((vid, corr[vid].partner))
    assert len(out) >= 2
    return out


def hover_on(app, vid) -> None:
    app.pointer_motion(*screen(app, vid))
    assert app.selection.hovered == vid


def test_hover_target_moves_mirrored_and_leaves_the_selection_empty(hover_app):
    app = hover_app
    mesh = app.scene.mesh
    vid, partner = visible_pairs(app)[0]
    hover_on(app, vid)
    history_before = len(app.history)
    p0, q0 = mesh.vertex_position(vid), mesh.vertex_position(partner)

    assert app.key_press(W)
    assert app.transform_target == {vid}
    move_mouse(app, MOVE_DRAGS)
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool) and tool.moves == {vid, partner}
    assert app.key_release(W)

    p1, q1 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert p1 != p0 and q1 != q0
    assert mirror_position(p1, ORIGIN, AXIS_NORMALS["X"]) == q1
    assert len(app.history) == history_before + 1
    assert app.selection.is_empty()
    assert app.transform_command is None


def test_target_fixed_at_w_press_cursor_over_other_vertex_does_not_retarget(hover_app):
    app = hover_app
    mesh = app.scene.mesh
    pairs = visible_pairs(app)
    vid, partner = pairs[0]
    other = next(v for v, _p in pairs if v not in (vid, partner))
    hover_on(app, vid)

    assert app.key_press(W)
    assert app.transform_target == {vid}
    assert app.selection.hovered is None
    app.pointer_motion(*screen(app, other))      # no delta: no move step, no hover
    assert app.selection.hovered is None
    assert app.transform_target == {vid}

    other_before = mesh.vertex_position(other)
    move_mouse(app, MOVE_DRAGS)
    assert app.tool_manager.active_tool.moves == {vid, partner}
    assert app.key_release(W)
    assert mesh.vertex_position(other) == other_before


def test_esc_during_drag_with_hover_target_restores_exactly(hover_app):
    app = hover_app
    mesh = app.scene.mesh
    vid, _partner = visible_pairs(app)[0]
    hover_on(app, vid)
    state_before = mesh.export_state()
    history_before = len(app.history)

    assert app.key_press(W)
    move_mouse(app, MOVE_DRAGS)
    assert mesh.export_state() != state_before
    assert app.key_press(ESC) is True

    assert mesh.export_state() == state_before
    assert len(app.history) == history_before
    assert app.selection.is_empty()
    assert app.transform_command is None
    assert app.tool_manager.active_tool is None


def test_hover_is_repicked_after_a_tap(hover_app):
    app = hover_app
    vid, _partner = visible_pairs(app)[0]
    hover_on(app, vid)
    state_before = app.scene.mesh.export_state()

    assert app.key_press(W)
    assert app.selection.hovered is None
    assert app.key_release(W)                    # a tap disarms
    assert app.transform_command is None
    assert app.selection.hovered == vid
    assert app.scene.mesh.export_state() == state_before
    assert len(app.history) == 1                 # only the Shift+S step


# -- W / E / R ---------------------------------------------------------------------------------


@pytest.mark.parametrize("key,label", [(E, "Rotate"), (R, "Scale")])
def test_rotate_and_scale_run_symmetric_as_one_undo_step(key, label):
    app = symmetric_app()
    mesh = app.scene.mesh
    vid, partner = paired(app)
    other, other_partner = same_side_pair(app, vid)
    select_vertices(app, vid, other)
    state0, before = mesh.export_state(), len(app.history)
    p0 = mesh.vertex_position(vid)
    assert app.key_press(key) is True
    assert app.status_message.startswith(f"{label}: 2 vertices")
    move_mouse(app)
    assert app.transform_interacting
    assert app.key_release(key) is True
    assert mesh.vertex_position(vid) != p0
    assert mirrored_ok(app, vid, partner) and mirrored_ok(app, other, other_partner)
    assert vertex_correspondence(mesh)[vid].partner == partner
    assert app.status_message == f"{label} committed"
    assert len(app.history) == before + 1
    assert app.key_press(CTRL_Z)
    assert mesh.export_state() == state0
    assert len(app.history) == before


@pytest.mark.parametrize("key", [E, R])
def test_cancel_leaves_no_history(key):
    app = symmetric_app()
    mesh = app.scene.mesh
    vid, _ = paired(app)
    select_vertices(app, vid)
    state0, before = mesh.export_state(), len(app.history)
    assert app.key_press(key)
    move_mouse(app)
    assert app.key_press(ESC)
    assert mesh.export_state() == state0
    assert len(app.history) == before
    assert app.transform_command is None


def test_constraints_x_y_z_all_keep_the_pair_mirrored():
    app = symmetric_app()
    vid, partner = paired(app)
    for key in (X, Y, Z):
        assert app.key_press(key)
        select_vertices(app, vid)
        hold(app, E)
        assert mirrored_ok(app, vid, partner)
        assert app.key_press(key)                # constraint free again


def test_seam_vertex_rotate_about_x_is_allowed_and_stays_on_the_plane():
    app = symmetric_app()
    seam = vertex_in_state(app, CorrespondenceState.SEAM)
    select_vertices(app, seam)
    assert app.key_press(X)
    hold(app, E)
    assert "refused" not in app.status_message
    assert app.scene.mesh.vertex_position(seam)[0] == 0.0


@pytest.mark.parametrize("constraint_key", [Y, Z, None])
def test_seam_vertex_rotate_other_axes_refused_with_message(constraint_key):
    app = symmetric_app()
    mesh = app.scene.mesh
    seam = vertex_in_state(app, CorrespondenceState.SEAM)
    select_vertices(app, seam)
    if constraint_key is not None:               # None: free = view axis (not parallel to the normal)
        assert app.key_press(constraint_key)
    state, before = mesh.export_state(), len(app.history)
    assert app.key_press(E)
    move_mouse(app)
    assert app.transform_command is None         # H5: never ran, ended visibly
    assert app.status_message.startswith("Rotate: refused — ")
    assert "Seam" in app.status_message
    assert mesh.export_state() == state and len(app.history) == before
    assert app.key_release(E) is False
    assert mesh.export_state() == state


def test_seam_vertex_scale_allowed_and_on_plane():
    app = symmetric_app()
    seam = vertex_in_state(app, CorrespondenceState.SEAM)
    select_vertices(app, seam)
    hold(app, R)
    assert "refused" not in app.status_message
    assert app.scene.mesh.vertex_position(seam)[0] == 0.0


def test_move_honours_the_constraint_and_stays_mirrored():
    app = symmetric_app()
    mesh = app.scene.mesh
    vid, partner = paired(app)
    select_vertices(app, vid)
    p0, q0 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert app.key_press(X)
    assert app.key_press(W)
    move_mouse(app)
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool) and tool.moves == {vid, partner}
    assert app.transform_space == "x"
    assert app.key_release(W)
    assert mirrored_ok(app, vid, partner)
    p1, q1 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert p1 != p0 and p1[1:] == p0[1:] and q1[1:] == q0[1:]


def test_symmetric_move_one_history_entry_and_exact_undo():
    app = symmetric_app()
    mesh = app.scene.mesh
    vid, partner = paired(app)
    select_vertices(app, vid)
    history_before = len(app.history)
    state_before = mesh.export_state()
    p0, q0 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert app.key_press(W) is True
    assert app.transform_command == "Move" and not app.transform_interacting
    move_mouse(app, MOVE_DRAGS)
    assert app.transform_interacting
    tool = app.tool_manager.active_tool
    assert isinstance(tool, MoveTool) and tool.moves == {vid, partner}
    assert app.key_release(W) is True
    p1, q1 = mesh.vertex_position(vid), mesh.vertex_position(partner)
    assert p1 != p0 and q1 != q0
    assert mirror_position(p1, ORIGIN, AXIS_NORMALS["X"]) == q1
    assert vertex_correspondence(mesh)[vid].partner == partner
    assert len(app.history) == history_before + 1
    assert app.key_press(CTRL_Z)
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before


def test_move_without_symmetry_moves_only_the_selection():
    app = symmetric_app()
    for _ in range(3):                           # X -> Y -> Z -> off
        assert app.key_press(SHIFT_S)
    assert app.scene.mesh.symmetry_definition is None
    vid = min(app.scene.mesh.all_vertex_ids())
    select_vertices(app, vid)
    assert app.key_press(W)
    move_mouse(app, MOVE_DRAGS)
    assert app.tool_manager.active_tool.moves == {vid}
    assert app.key_release(W)


def test_seam_vertex_stays_exactly_on_plane():
    app = symmetric_app()
    mesh = app.scene.mesh
    vid = vertex_in_state(app, CorrespondenceState.SEAM)
    select_vertices(app, vid)
    p0 = mesh.vertex_position(vid)
    hold(app, W, MOVE_DRAGS * 3)
    p1 = mesh.vertex_position(vid)
    assert p1 != p0                              # it did move, inside the plane
    assert p1[0] == 0.0
    assert symmetry_state(mesh) is SymmetryState.VALID


def test_undo_takes_back_exactly_one_action_each():
    app = symmetric_app()
    mesh = app.scene.mesh
    vid, _partner = paired(app)
    select_vertices(app, vid)
    after_symmetry = mesh.export_state()
    hold(app, W, MOVE_DRAGS)
    assert len(app.history) == 2
    assert app.key_press(CTRL_Z)
    assert mesh.export_state() == after_symmetry
    assert app.selection.vertices == {vid}
    assert app.key_press(CTRL_Z)
    assert mesh.symmetry_definition is None
    assert len(app.history) == 0
    assert app.key_press(CTRL_Y)
    assert mesh.export_state() == after_symmetry


def test_esc_during_drag_restores_exactly_without_history():
    app = symmetric_app()
    mesh = app.scene.mesh
    vid, _ = paired(app)
    select_vertices(app, vid)
    state_before = mesh.export_state()
    history_before = len(app.history)
    assert app.key_press(W)
    move_mouse(app, MOVE_DRAGS)
    assert mesh.export_state() != state_before
    assert app.key_press(ESC) is True
    assert mesh.export_state() == state_before
    assert len(app.history) == history_before
    assert app.transform_command is None
    assert app.tool_manager.active_tool is None
    assert app.key_release(W) is False
    assert mesh.export_state() == state_before


# -- C: Split, Edge Connect, Vertex Connect -----------------------------------------------------


def select_opposite_edges(app) -> None:
    edges = app.scene.mesh.face_edges(plus_x_quad(app))
    select(app, E_MODE, {edges[0], edges[2]})


def select_diagonal(app) -> None:
    vids = app.scene.mesh.face_vertices(plus_x_quad(app))
    select(app, V_MODE, {vids[0], vids[2]})


@pytest.mark.parametrize("kind", ["edge", "vertex"])
def test_connect_runs_symmetric_as_one_undo_step(kind):
    app = symmetric_app()
    (select_opposite_edges if kind == "edge" else select_diagonal)(app)
    before = topology_state(app)
    selection_before = selection_state(app)
    history = len(app.history)
    assert app.key_press(C) is True
    assert app.status_message == ("Connect Edges" if kind == "edge" else "Vertex Connect")
    assert len(app.history) == history + 1
    assert_clean(app)
    after = topology_state(app)
    assert after != before
    assert app.key_press(CTRL_Z) is True
    assert len(app.history) == history
    assert topology_state(app) == before
    assert selection_state(app) == selection_before
    assert app.key_press(CTRL_Y) is True
    assert topology_state(app) == after


def edge_sides(app, edges) -> set:
    mesh = app.scene.mesh
    out = set()
    for e in edges:
        total = sum(mesh.vertex_position(v)[0] for v in mesh.edge_vertices(e))
        out.add((total > 0) - (total < 0))
    return out


def test_connect_residue_is_the_created_edges_on_the_side_worked_on_or_on_both_sides():
    """Artist ITERATE 2026-10-08: one side selected -> that side's created edges; both sides selected on
    purpose -> the created edges of both; Undo restores the selection."""
    app = symmetric_app()
    select_opposite_edges(app)
    one_sided = set(app.selection.edges)
    selection_before = selection_state(app)
    assert app.key_press(C) is True
    assert edge_sides(app, app.selection.edges) == {1}
    assert app.key_press(CTRL_Z) is True
    assert selection_state(app) == selection_before
    index = SymmetryIndex(app.scene.mesh)
    app.selection.edges = one_sided | {index.edge_partner(e) for e in one_sided}
    assert app.key_press(C) is True
    assert edge_sides(app, app.selection.edges) == {1, -1}


@pytest.mark.parametrize("kind", ["edge", "vertex"])
def test_connect_with_an_unpaired_selection_is_refused_visibly(kind):
    app = symmetric_app()
    displace(app, app.scene.mesh.face_vertices(plus_x_quad(app))[0])
    (select_opposite_edges if kind == "edge" else select_diagonal)(app)
    assert_refused_twice(app, C, TEXT_UNPAIRED)


def test_split_with_one_edge_splits_both_sides_as_one_undo_step():
    app = symmetric_app()
    mesh = app.scene.mesh
    select(app, E_MODE, {plus_x_edge(app)})
    before = topology_state(app)
    selection_before = selection_state(app)
    vertices = set(mesh.all_vertex_ids())
    history = len(app.history)
    assert app.key_press(C) is True
    assert app.status_message == "Split"
    assert len(app.history) == history + 1
    created = set(mesh.all_vertex_ids()) - vertices
    assert len(created) == 2
    assert_clean(app)
    (selected,) = app.selection.vertices         # only the new vertex of the selected (+X) side
    assert selected in created and mesh.vertex_position(selected)[0] > 0.0
    after, after_selection = topology_state(app), selection_state(app)
    assert app.key_press(CTRL_Z) is True
    assert len(app.history) == history
    assert topology_state(app) == before
    assert selection_state(app) == selection_before
    assert app.key_press(CTRL_Y) is True
    assert topology_state(app) == after
    assert selection_state(app) == after_selection


def test_split_of_a_mirror_pair_splits_exactly_twice():
    """A2 = A: the edge and its mirror are one intent, no double split, both new vertices selected."""
    app = symmetric_app()
    mesh = app.scene.mesh
    edge = plus_x_edge(app)
    partner = SymmetryIndex(mesh).edge_partner(edge)
    assert partner is not None and partner != edge
    select(app, E_MODE, {edge, partner})
    vertices = set(mesh.all_vertex_ids())
    edges = len(mesh.all_edge_ids())
    assert app.key_press(C) is True
    created = set(mesh.all_vertex_ids()) - vertices
    assert len(created) == 2
    assert len(mesh.all_edge_ids()) == edges + 2
    assert set(app.selection.vertices) == created
    assert_clean(app)


def test_split_of_a_seam_edge_splits_once_and_the_new_vertex_is_a_seam_vertex():
    app = symmetric_app()
    mesh = app.scene.mesh
    seam = mesh.symmetry_definition.seam_edges
    old = next(e for e in sorted(seam, key=int) if len(mesh.edge_faces(e)) == 2)
    select(app, E_MODE, {old})
    vertices = set(mesh.all_vertex_ids())
    before = topology_state(app)
    assert app.key_press(C) is True
    (new_vertex,) = set(mesh.all_vertex_ids()) - vertices
    assert mesh.vertex_position(new_vertex)[0] == 0.0
    assert old not in mesh.symmetry_definition.seam_edges
    assert len(mesh.symmetry_definition.seam_edges) == len(seam) + 1
    assert set(app.selection.vertices) == {new_vertex}
    assert_clean(app)
    assert app.key_press(CTRL_Z) is True
    assert topology_state(app) == before
    assert mesh.symmetry_definition.seam_edges == seam


def test_split_refused_press_leaves_the_selection_untouched():
    app = symmetric_app()
    edge = plus_x_edge(app)
    displace(app, app.scene.mesh.edge_vertices(edge)[0])
    select(app, E_MODE, {edge})
    assert_refused_twice(app, C, TEXT_UNPAIRED)
    assert app.selection.mode is E_MODE


# -- C: the Knife --------------------------------------------------------------------------------


def one_side_diagonal(app):
    """Two diagonal vertices of a quad entirely on the +X side that the Knife hits as vertices."""
    mesh = app.scene.mesh

    def hits(vid) -> bool:
        target = knife_pick(app.camera, mesh, *screen(app, vid), WIDTH, HEIGHT)
        return target.get("kind") == "vertex" and target.get("vertex_id") == vid

    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) != 4 or any(mesh.vertex_position(v)[0] <= 1e-9 for v in vids):
            continue
        if hits(vids[0]) and hits(vids[2]):
            return vids[0], vids[2]
    raise AssertionError("no one-sided quad with a visible diagonal")


def knife_click(app, vid) -> None:
    pos = screen(app, vid)
    app.pointer_motion(*pos)
    app.pointer_press(LMB, *pos)
    assert app.pointer_release("LEFT", *pos)


def begin_knife(app) -> None:
    app.pointer_motion(*MISS)
    app.selection.clear()
    assert app.key_press(C) is True
    assert app.knife_active


def test_the_knife_runs_coordinated_with_one_history_entry():
    app = symmetric_app()
    mesh = app.scene.mesh
    a, b = one_side_diagonal(app)
    before = topology_state(app)
    definition = mesh.symmetry_definition
    history = len(app.history)
    edges = len(mesh.all_edge_ids())
    begin_knife(app)
    knife_click(app, a)
    knife_click(app, b)
    assert app.key_press(ENTER) is True
    assert not app.knife_active
    assert len(app.history) == history + 1       # both sides in one step
    assert len(mesh.all_edge_ids()) == edges + 2  # the cut and its mirror
    assert_clean(app)
    assert len(app.selection.edges) == 1         # residue F4 = A: the working side's cut edge
    assert all(mesh.vertex_position(v)[0] >= 0.0 for e in app.selection.edges for v in mesh.edge_vertices(e))
    after = topology_state(app)
    assert app.key_press(CTRL_Z) is True
    assert len(app.history) == history
    assert topology_state(app) == before and mesh.symmetry_definition == definition
    assert app.key_press(CTRL_Y) is True
    assert topology_state(app) == after
    assert_clean(app)


def test_the_mirror_variant_key_switches_inside_the_knife_session_only():
    app = symmetric_app()
    history = len(app.history)
    # Outside the session the key is the app's SubD key (view state only, no history step).
    assert app.key_press(VARIANT) is True
    assert app.subdivision.view == "cage" and len(app.history) == history
    app.key_press(VARIANT)
    app.key_press(VARIANT)
    assert app.subdivision.view == "off"
    begin_knife(app)
    assert app.knife_mirror_variant == "V-b"
    assert app.key_press(VARIANT) is True
    assert app.knife_mirror_variant == "V-c" and "V-c" in app.status_message
    assert app.key_press(ESC) is True
    assert not app.knife_active
    assert len(app.history) == history


def test_a_pending_knife_session_follows_the_definition_it_started_with():
    """The session view is built at begin; the session gate ignores Shift+S while the Knife runs."""
    app = symmetric_app()
    begin_knife(app)
    assert app._knife._symmetric_view is not None and app._knife._symmetric_commit is not None
    definition = app.scene.mesh.symmetry_definition
    assert app.key_press(SHIFT_S) is False
    assert app.scene.mesh.symmetry_definition is definition
    assert app.key_press(ESC) is True


def test_without_a_definition_the_knife_is_the_plain_knife():
    app = make_app()
    begin_knife(app)
    assert app._knife._symmetric_commit is None and app._knife._symmetric_view is None
    assert app.key_press(ESC) is True


# -- T: Extrude ----------------------------------------------------------------------------------


def extrude_state(app) -> tuple:
    return (topology_state(app), len(app.history), app.selection.mode, frozenset(app.selection.faces))


def plus_x_face(app, *, seam: bool = False):
    """A +X quad away from the seam (`seam=False`) or with an edge on it."""
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        xs = [mesh.vertex_position(v)[0] for v in mesh.face_vertices(fid)]
        on = sum(1 for x in xs if x == 0.0)
        if len(xs) == 4 and min(xs) >= 0.0 and max(xs) > 0.0 and on == (2 if seam else 0):
            return fid
    raise AssertionError("no matching +X quad")


def drag_t(app, steps: int = 4, dx: float = 30.0, dy: float = 20.0) -> bool:
    assert app.key_press(T)
    x, y = 400.0, 300.0
    for _ in range(steps):
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)
    return app.key_release(T)


@pytest.mark.parametrize("seam", [False, True], ids=["interior_face", "seam_face"])
def test_extrude_is_coordinated_in_one_undo_step_and_selects_the_caps_on_the_working_side(seam):
    app = symmetric_app("head_basemesh")
    mesh = app.scene.mesh
    select(app, F_MODE, {plus_x_face(app, seam=seam)})
    before = extrude_state(app)
    seam_before = mesh.symmetry_definition.seam_edges
    steps = len(app.history)

    assert drag_t(app)
    assert app.status_message == "Extrude committed"
    assert len(app.history) == steps + 1
    assert_clean(app)
    assert (mesh.symmetry_definition.seam_edges != seam_before) is seam   # S3 moves the seam with the mesh
    caps = set(app.selection.faces)
    assert caps and all(mesh.is_valid_face(f) for f in caps)
    assert all(sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0 for f in caps)

    assert app.key_press(CTRL_Z) is True
    assert extrude_state(app) == before
    assert mesh.symmetry_definition.seam_edges == seam_before
    assert app.key_press(CTRL_Y) is True
    assert len(app.history) == steps + 1
    assert_clean(app)


def test_the_caps_of_a_seam_extrude_extrude_again():
    """Manu's report: the newly selected cap of a seam extrude was refused as unpaired. Three extrudes and three
    Undos, one step each, symmetry valid throughout."""
    app = symmetric_app("head_basemesh")
    mesh = app.scene.mesh
    select(app, F_MODE, {plus_x_face(app, seam=True)})
    steps = len(app.history)
    for n in (1, 2, 3):
        assert drag_t(app)
        assert app.status_message == "Extrude committed", f"extrude #{n}: {app.status_message}"
        assert len(app.history) == steps + n
        assert_clean(app)
        assert app.selection.faces
    for n in (2, 1, 0):
        assert app.key_press(CTRL_Z) is True
        assert len(app.history) == steps + n
        assert_clean(app)
    assert all(mesh.is_valid_edge(e) for e in mesh.symmetry_definition.seam_edges)


def test_both_sides_selected_extrude_as_one_intent_and_select_both_caps():
    app = symmetric_app("head_basemesh")
    mesh = app.scene.mesh
    face = plus_x_face(app)
    select(app, F_MODE, {face, SymmetryIndex(mesh).face_partner(face)})
    steps = len(app.history)
    assert drag_t(app)
    assert app.status_message == "Extrude committed" and len(app.history) == steps + 1
    assert_clean(app)
    sides = {sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) > 0 for f in app.selection.faces}
    assert sides == {True, False}


def test_esc_during_the_extrude_gesture_restores_mesh_seam_and_selection():
    app = symmetric_app("head_basemesh")
    select(app, F_MODE, {plus_x_face(app, seam=True)})
    before = extrude_state(app)
    seam_before = app.scene.mesh.symmetry_definition.seam_edges
    assert app.key_press(T)
    x, y = 400.0, 300.0
    for _ in range(4):
        x, y = x + 30, y + 20
        app.pointer_motion(x, y, 30.0, 20.0)
    assert app.transform_interacting
    assert app.key_press(ESC)
    assert extrude_state(app) == before
    assert app.scene.mesh.symmetry_definition.seam_edges == seam_before


def test_extrude_of_a_face_without_a_partner_is_refused_visibly():
    app = symmetric_app("head_basemesh")
    face = plus_x_face(app)
    displace(app, app.scene.mesh.face_vertices(face)[0])
    select(app, F_MODE, {face})
    before = extrude_state(app)
    drag_t(app)
    assert app.status_message == TEXT_UNPAIRED
    assert extrude_state(app) == before
    assert app.transform_command is None and app.interaction_owner is None


def test_extrude_of_a_face_spanning_the_plane_is_refused_visibly():
    """Artist statement 2026-10-09 (case 4): refuse visibly, for now. A +X quad is rebuilt over two of its
    partner's vertices so the face spans the plane and is its own mirror."""
    app = symmetric_app("head_basemesh")
    mesh = app.scene.mesh
    index = SymmetryIndex(mesh)
    face = plus_x_face(app)
    partner = index.face_partner(face)
    vs = mesh.face_vertices(face)
    pvs = [index.vertex_partner(v) for v in vs]
    mesh.remove_face(face)
    mesh.remove_face(partner)
    spanning = mesh.add_face([vs[0], vs[1], pvs[1], pvs[0]])
    assert SymmetryIndex(mesh).face_partner(spanning) == spanning
    select(app, F_MODE, {spanning})
    before = extrude_state(app)
    drag_t(app)
    assert app.status_message == TEXT_EXTRUDE_SPANNING
    assert extrude_state(app) == before
    assert app.transform_command is None


# -- Delete / Dissolve / Dissolve (no cleanup) ---------------------------------------------------

REMOVAL_KEYS = [DELETE, DISSOLVE, DISSOLVE_NO_CLEANUP]
REMOVAL_IDS = ["delete", "dissolve", "dissolve_no_cleanup"]


def far_selection(app, mode, dissolve: bool):
    mesh = app.scene.mesh
    quad = plus_x_quad(app)
    if mode is V_MODE:
        return {mesh.face_vertices(quad)[0]}
    if mode is E_MODE:
        return {mesh.face_edges(quad)[0]}
    if not dissolve:
        return {quad}
    for e in mesh.face_edges(quad):              # a neighbouring +X face to merge with
        for g in mesh.edge_faces(e):
            if g != quad and all(mesh.vertex_position(v)[0] > 1e-9 for v in mesh.face_vertices(g)):
                return {quad, g}
    raise AssertionError("no neighbouring face on the +X side")


def seam_pair(app):
    mesh = app.scene.mesh
    edge = next(e for e in sorted(mesh.symmetry_definition.seam_edges) if len(mesh.edge_faces(e)) == 2)
    return edge, set(mesh.edge_faces(edge))


def crossing_edge(app):
    """An edge with exactly one end on the plane (it crosses the seam)."""
    mesh = app.scene.mesh
    for e in sorted(mesh.all_edge_ids()):
        if sum(mesh.vertex_position(v)[0] == 0.0 for v in mesh.edge_vertices(e)) == 1:
            return e
    raise AssertionError("no edge crossing the seam")


@pytest.mark.parametrize("key", REMOVAL_KEYS, ids=REMOVAL_IDS)
@pytest.mark.parametrize("component", [V_MODE, E_MODE, F_MODE], ids=["vertex", "edge", "face"])
@pytest.mark.parametrize("asset", ["subd_cube", "head_basemesh"])
def test_removal_runs_symmetric_as_one_undo_step(asset, component, key):
    if key is DISSOLVE_NO_CLEANUP and component is V_MODE:
        pytest.skip("vertex Dissolve has no no-cleanup variant")
    app = symmetric_app(asset)
    select(app, component, far_selection(app, component, key is not DELETE))
    before = topology_state(app)
    selection_before = selection_state(app)
    definition = app.scene.mesh.symmetry_definition
    history = len(app.history)
    assert app.key_press(key) is True
    assert len(app.history) == history + 1
    assert_clean(app)
    after = topology_state(app)
    assert after != before
    assert app.key_press(CTRL_Z) is True
    assert len(app.history) == history
    assert topology_state(app) == before
    assert selection_state(app) == selection_before
    assert app.scene.mesh.symmetry_definition == definition
    assert app.key_press(CTRL_Y) is True
    assert topology_state(app) == after


def test_delete_removes_the_element_on_both_sides():
    app = symmetric_app()
    mesh = app.scene.mesh
    quad = plus_x_quad(app)
    partner = SymmetryIndex(mesh).face_partner(quad)
    assert partner is not None and partner != quad
    select(app, F_MODE, {quad})
    assert app.key_press(DELETE) is True
    assert not mesh.is_valid_face(quad) and not mesh.is_valid_face(partner)
    assert app.status_message == "Delete Faces"


def test_delete_of_a_face_pair_at_the_seam_stays_valid_and_undo_restores_the_seam():
    """A1 case 1 (Manu: M): the seam disappears only where the adjacent faces are gone."""
    app = symmetric_app("head_basemesh")
    seam_before = app.scene.mesh.symmetry_definition.seam_edges
    seam_edge, pair = seam_pair(app)
    select(app, F_MODE, pair)
    before = topology_state(app)
    assert app.key_press(DELETE) is True
    mesh = app.scene.mesh
    assert not mesh.is_valid_edge(seam_edge) and seam_edge not in mesh.symmetry_definition.seam_edges
    assert mesh.symmetry_definition.seam_edges < seam_before
    assert_clean(app)
    assert app.key_press(CTRL_Z) is True
    assert topology_state(app) == before
    assert mesh.symmetry_definition.seam_edges == seam_before


@pytest.mark.parametrize("key", [DISSOLVE, DISSOLVE_NO_CLEANUP], ids=["dissolve", "dissolve_no_cleanup"])
def test_dissolve_of_a_seam_edge_is_refused_with_its_text(key):
    """A1 case 2 (Artist 2026-10-08): an edge lying on the seam stays refused, nothing changes."""
    app = symmetric_app("head_basemesh")
    seam_edge, _pair = seam_pair(app)
    select(app, E_MODE, {seam_edge})
    definition = app.scene.mesh.symmetry_definition
    serial = app.status_serial
    before = (topology_state(app), selection_state(app), len(app.history))
    assert app.key_press(key) is False
    assert app.status_message == TEXT_SEAM_DISSOLVE
    assert app.status_serial == serial + 1
    assert (topology_state(app), selection_state(app), len(app.history)) == before
    assert app.scene.mesh.symmetry_definition == definition


@pytest.mark.parametrize("key", [DISSOLVE, DISSOLVE_NO_CLEANUP], ids=["dissolve", "dissolve_no_cleanup"])
def test_dissolve_of_an_edge_crossing_the_seam_runs(key):
    """A1 case 2 refined (seam rule S2): two seam edges become one, one Undo step; Ctrl+Backspace (no cleanup)
    leaves the seam unchanged."""
    app = symmetric_app("head_basemesh")
    mesh = app.scene.mesh
    edge = crossing_edge(app)
    seam_before = mesh.symmetry_definition.seam_edges
    select(app, E_MODE, {edge})
    selection_before = selection_state(app)
    state_before = topology_state(app)
    history = len(app.history)
    assert app.key_press(key) is True
    assert len(app.history) == history + 1
    assert_clean(app)
    seam_after = mesh.symmetry_definition.seam_edges
    if key == DISSOLVE:
        assert len(seam_after) == len(seam_before) - 1
        assert all(mesh.is_valid_edge(e) for e in seam_after)
    else:
        assert seam_after == seam_before
    assert app.key_press(CTRL_Z) is True
    assert len(app.history) == history
    assert topology_state(app) == state_before
    assert mesh.symmetry_definition.seam_edges == seam_before
    assert selection_state(app) == selection_before
    assert app.key_press(CTRL_Y) is True
    assert mesh.symmetry_definition.seam_edges == seam_after
    assert len(app.history) == history + 1


@pytest.mark.parametrize("key", REMOVAL_KEYS, ids=REMOVAL_IDS)
def test_removal_of_an_unpaired_selection_is_refused_visibly(key):
    app = symmetric_app()
    mesh = app.scene.mesh
    quad = plus_x_quad(app)
    vertex = mesh.face_vertices(quad)[0]
    displace(app, vertex)
    select(app, E_MODE, {e for e in mesh.face_edges(quad) if vertex in mesh.edge_vertices(e)})
    assert_refused_twice(app, key, TEXT_UNPAIRED)


@pytest.mark.parametrize("key", REMOVAL_KEYS, ids=REMOVAL_IDS)
def test_with_symmetry_off_removal_runs_one_sided(key):
    app = make_app()
    assert app.scene.mesh.symmetry_definition is None
    mesh = app.scene.mesh
    edge = mesh.face_edges(plus_x_quad(app))[0]
    select(app, E_MODE, {edge})
    mirrored = {tuple(sorted((-x, y, z) for x, y, z in map(mesh.vertex_position, mesh.edge_vertices(edge))))}
    mirror = next(
        e for e in mesh.all_edge_ids()
        if tuple(sorted(map(mesh.vertex_position, mesh.edge_vertices(e)))) in mirrored
    )
    assert app.key_press(key) is True
    assert not mesh.is_valid_edge(edge) and mesh.is_valid_edge(mirror)   # one-sided: the mirror edge stays
    assert len(app.history) == 1
    assert app.scene.mesh.symmetry_definition is None
