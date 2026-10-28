"""SubD preview in the Production app (2026-10-23, `mirai.subdivision`), headless (TraceStore).

The control mesh is changed only by the app's own tools; the replacement surface (AD-013 H7) must
always equal `apply_full` of the *current* control mesh at the shown level — after W/E/R, Tweak,
Soft, symmetry, Knife, Extrude, Connect, Delete / Dissolve and their Undo / Redo. Position-only
changes never rebuild topology; topology changes rebuild; an unsupported control mesh shows the
cage with a status, never a stale surface. The SubD keys live in the context "subd", change view
state only and never shadow an app key. Moved and extended from the SubD Lab's `test_app_lab.py`.
"""

from __future__ import annotations

import itertools

import pytest

import tests.subdivision_meshes  # noqa: F401  (examples/ on sys.path)
from core import SelectionMode
from loaders.assets import asset_path
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import KNIFE_CONTEXT, SUBD_CONTEXT, Input
from mirai.subdivision import (
    CYCLE_VIEW,
    DEFAULT_LEVEL,
    MAX_LEVEL,
    SUBD_COMMANDS,
    SUBD_KEYS,
    VIEW_CAGE,
    VIEW_ISO,
    VIEW_OFF,
    SubdBindingConflict,
    SubdSurface,
    SubdSurfaceProvider,
    install_subd_bindings,
)
from mirai.subdivision.preview import CAGE_LAYER, ISO_LAYER
from mirai.interaction.bindings import build_default_bindings
from mirai.scene_factory import mesh_from_positions_and_faces
from mirai.topology.knife_pick import knife_pick
from mirai.topology.knife_preview import target_position

WIDTH, HEIGHT = 800, 600


def _key(value: str, *mods: str) -> Input:
    return Input("key", value, frozenset(mods))


V, SHIFT_V = _key("v"), _key("v", "shift")
W, E, R, T, C, O = _key("w"), _key("e"), _key("r"), _key("t"), _key("c"), _key("o")
K1, K2, K3 = _key("1"), _key("2"), _key("3")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")
SHIFT_S = _key("s", "shift")
ENTER, DELETE, BACKSPACE = _key("enter"), _key("delete"), _key("backspace")
LMB = Input("mouse", "LEFT")


def ctrl(n: int) -> Input:
    return _key(str(n), "ctrl")


def _app(asset: str = "subd_cube") -> Application:
    app = Application()
    if asset == "cube":
        app.init_scene("cube")
    else:
        app.init_scene("obj", obj_path=asset_path(asset))
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.knife_clock = itertools.count(0.0, 10.0).__next__
    return app


@pytest.fixture
def app() -> Application:
    return _app()


def frame(app) -> None:
    app.viewport.sync()


def on(app, view: str = VIEW_CAGE) -> None:
    while app.subdivision.view != view:
        assert app.key_press(V)
    frame(app)


def expected_positions(mesh, level: int) -> list:
    surface = SubdSurface(mesh)
    positions = [tuple(mesh.vertex_position(v)) for v in surface.topology.vertex_ids]
    return surface.level(level).apply_full(positions)


def assert_surface_matches(app) -> None:
    provider = app.subdivision.provider
    surface = provider.surface_mesh
    assert surface is not None
    assert app.viewport.surface_render_mesh is not None
    assert app.viewport.surface_render_mesh.mesh is surface  # never a stale RenderMesh
    level, vertex_ids, face_ids = provider.derived_elements()
    reference = SubdSurface(app.viewport.mesh).level(app.subdivision.level)
    want = expected_positions(app.viewport.mesh, app.subdivision.level)
    assert len(vertex_ids) == len(want) == len(surface.all_vertex_ids())
    for vid, b in zip(vertex_ids, want):
        assert tuple(surface.vertex_position(vid)) == pytest.approx(b, abs=1e-9)
    # structure: every derived face of a fresh evaluation is exactly the shown face
    assert len(face_ids) == len(reference.faces) == len(surface.all_face_ids())
    assert level.faces == reference.faces
    for fid, face in zip(face_ids, reference.faces):
        assert surface.face_vertices(fid) == [vertex_ids[v] for v in face]


def builds(app) -> tuple[int, int]:
    p = app.subdivision.provider
    return p.topology_builds, p.level_builds


def screen(app, point):
    return app.camera.project_to_screen(point, WIDTH, HEIGHT)


def hover_some_vertex(app):
    mesh = app.viewport.mesh
    for vid in sorted(mesh.all_vertex_ids(), key=int):
        sx, sy = screen(app, mesh.vertex_position(vid))
        app.pointer_motion(sx, sy)
        if app.selection.hovered is not None:
            return vid, (sx, sy)
    raise AssertionError("no vertex hoverable")


def hold_move(app, key: Input = W, dx: float = 25.0, dy: float = 10.0, at=None) -> None:
    x, y = at or app._cursor or (WIDTH / 2, HEIGHT / 2)
    before = app.viewport.mesh.export_state()
    app.key_press(key)
    for _ in range(3):
        x, y = x + dx / 3, y + dy / 3
        app.pointer_motion(x, y, dx / 3, dy / 3)
    app.key_release(key)
    assert app.viewport.mesh.export_state() != before


def undo_redo_matches(app) -> None:
    app.key_press(CTRL_Z)
    frame(app)
    assert_surface_matches(app)
    app.key_press(CTRL_Y)
    frame(app)
    assert_surface_matches(app)


# -- keys ---------------------------------------------------------------------------------------


def test_subd_keys_are_installed_in_their_own_context_and_free_in_the_app():
    app = Application()
    for entry in SUBD_KEYS:
        assert app.bindings.command_for(entry.input) is None  # global: unbound
        assert app.bindings.command_for(entry.input, SUBD_CONTEXT) == entry.command
    assert {entry.command for entry in SUBD_KEYS} == SUBD_COMMANDS
    assert len({entry.input for entry in SUBD_KEYS}) == len(SUBD_KEYS)


def test_a_conflicting_default_aborts_the_install():
    bindings = build_default_bindings()
    bindings.set_default(V, "Something")
    with pytest.raises(SubdBindingConflict):
        install_subd_bindings(bindings)


def test_a_knife_only_binding_on_a_subd_key_does_not_abort_the_install():
    # K-1 (AD-013 addendum 2026-10-28): a Knife session never resolves SubD keys, so the check skips the
    # knife context - the default V = KnifeMirrorVariant lives there.
    bindings = build_default_bindings()
    assert bindings.command_for(V, KNIFE_CONTEXT) == cmd.KNIFE_MIRROR_VARIANT
    install_subd_bindings(bindings)
    assert bindings.command_for(V, SUBD_CONTEXT) == SUBD_KEYS[0].command


def test_a_user_binding_of_a_subd_key_wins_over_subd(app):
    app.bindings.bind(V, cmd.CYCLE_DISPLAY_MODE)  # e.g. keymap.json
    app.key_press(V)
    assert app.subdivision.view == VIEW_OFF
    assert app.display.mode.name == "FLAT_SHADED"


def test_start_is_off_and_the_viewport_untouched(app):
    frame(app)
    assert app.subdivision.view == VIEW_OFF
    assert app.viewport.surface_provider is None  # H7-R1: inert without SubD
    assert app.viewport.surface_render_mesh is None
    assert app.subdivision.level == DEFAULT_LEVEL


def test_v_cycles_off_cage_iso_off_and_the_surface_matches(app):
    assert app.key_press(V)
    frame(app)
    assert app.subdivision.view == VIEW_CAGE
    assert app.viewport.surface_provider is app.subdivision.provider
    assert_surface_matches(app)
    assert app.subdivision.lines.segments[CAGE_LAYER] and not app.subdivision.lines.segments[ISO_LAYER]

    app.key_press(V)
    frame(app)
    assert app.subdivision.view == VIEW_ISO
    assert app.subdivision.lines.segments[ISO_LAYER]

    app.key_press(V)
    frame(app)
    assert app.subdivision.view == VIEW_OFF
    assert app.viewport.surface_provider is None
    assert app.viewport.surface_render_mesh is None
    assert app.subdivision.provider._watch is None  # no journal kept while off


def test_subd_keys_are_view_state_only(app):
    state = app.viewport.mesh.export_state()
    on(app)
    app.key_press(ctrl(3))
    app.key_press(SHIFT_V)
    frame(app)
    assert app.viewport.mesh.export_state() == state
    assert not app.history.can_undo()


def test_levels_up_to_the_maximum_and_the_documented_face_counts(app):
    on(app)
    counts = {}
    for n in (1, 2, 3):
        assert app.key_press(ctrl(n))
        frame(app)
        assert app.subdivision.level == n
        counts[n] = app.subdivision.provider.derived_counts[1]
        assert_surface_matches(app)
    assert counts == {1: 96, 2: 384, 3: 1536}  # subd_cube: 24 quads
    assert MAX_LEVEL == 3


def test_head_face_counts_per_level():
    app = _app("head_basemesh")
    on(app)
    seen = {}
    for n in (1, 2, 3):
        app.key_press(ctrl(n))
        frame(app)
        seen[n] = app.subdivision.provider.derived_counts[1]
    assert seen == {1: 1296, 2: 5184, 3: 20736}


def test_level_above_the_face_limit_is_refused(app):
    on(app)
    app.key_press(ctrl(2))
    frame(app)
    app.subdivision.provider.max_faces = 400
    assert not app.key_press(ctrl(3))
    assert "abgelehnt" in app.status_message
    assert app.subdivision.level == 2


def test_subd_keys_refused_while_a_transform_is_armed(app):
    vid = sorted(app.viewport.mesh.all_vertex_ids(), key=int)[0]
    app.selection.set({vid})
    app.key_press(W)
    assert app.interaction_owner == "transform"
    assert not app.key_press(V)
    assert app.subdivision.view == VIEW_OFF
    assert "ignoriert" in app.status_message
    app.key_release(W)


def test_other_keys_still_reach_the_app(app):
    on(app)
    assert app.key_press(K2)
    assert app.selection.mode is SelectionMode.EDGE


def test_preview_survives_a_scene_load_and_reattaches(app):
    on(app)
    app.load_scene("cube")
    frame(app)
    assert app.subdivision.view == VIEW_CAGE
    assert app.viewport.surface_provider is app.subdivision.provider
    assert_surface_matches(app)


def test_another_hosts_provider_keeps_the_slot(app):
    class Other:
        surface_mesh = None
        dirty = False

        def sync(self, mesh, selection):
            return set()

    other = Other()
    app.viewport.set_surface_provider(other)
    assert not app.key_press(V)
    assert app.subdivision.view == VIEW_OFF
    assert app.viewport.surface_provider is other
    assert "nicht verfügbar" in app.status_message


# -- position-only updates -------------------------------------------------------------------


def test_w_move_updates_without_rebuild_and_undo_redo(app):
    on(app)
    rm = app.viewport.surface_render_mesh
    before = builds(app)
    structural = rm.benchmark_counters.get("structural_rebuilds", 0)
    hover_some_vertex(app)
    hold_move(app)
    frame(app)
    assert app.viewport.surface_render_mesh is rm  # positions only: same RenderMesh
    assert builds(app) == before  # no topology / stencil / level rebuild
    assert rm.benchmark_counters.get("structural_rebuilds", 0) == structural
    assert app.subdivision.provider.last_update_ms is not None
    assert_surface_matches(app)
    undo_redo_matches(app)
    assert builds(app) == before


@pytest.mark.parametrize("key", [E, R])
def test_rotate_and_scale_of_a_selection(app, key):
    on(app)
    mesh = app.viewport.mesh
    app.selection.set(set(sorted(mesh.all_vertex_ids(), key=int)[:5]))
    before = builds(app)
    hold_move(app, key, dx=40.0, dy=15.0)
    frame(app)
    assert builds(app) == before
    assert_surface_matches(app)
    undo_redo_matches(app)


def test_hover_and_selection_changes_do_no_surface_work(app):
    on(app)
    rm = app.viewport.surface_render_mesh
    revision = app.subdivision.provider.revision
    uploads = rm.stats.uploaded_bytes
    hover_some_vertex(app)
    frame(app)
    app.selection.set({sorted(app.viewport.mesh.all_vertex_ids(), key=int)[3]})
    app.viewport.on_selection_changed()
    frame(app)
    assert app.subdivision.provider.revision == revision
    assert rm.stats.uploaded_bytes == uploads


def test_tweak_moves_through_the_preview(app):
    on(app)
    vid, pos = hover_some_vertex(app)
    before = builds(app)
    # The `Tweak` drag lost its Ctrl+LMB default 2026-10-28 (Manu A3); bound here, the mechanism stays (E4).
    app.bindings.set_default(Input("drag", "LEFT", frozenset({"ctrl"})), cmd.TWEAK)
    app.pointer_press(Input("mouse", "LEFT", frozenset({"ctrl"})), *pos)
    x, y = pos
    for _ in range(6):
        x += 5
        app.pointer_drag(5, 0, x, y)
    app.pointer_release("LEFT", x, y)
    assert app.history.can_undo()
    frame(app)
    assert builds(app) == before
    assert_surface_matches(app)
    undo_redo_matches(app)


def test_soft_selection_move(app):
    on(app)
    app.key_press(O)  # Soft on
    mesh = app.viewport.mesh
    app.selection.set({sorted(mesh.all_vertex_ids(), key=int)[0]})
    before = builds(app)
    hold_move(app, W, dx=30.0, dy=0.0)
    frame(app)
    assert builds(app) == before
    assert_surface_matches(app)
    undo_redo_matches(app)


def test_symmetry_definition_alone_rebuilds_nothing_and_symmetric_move_matches():
    app = _app("cube")
    on(app)
    before = builds(app)
    rm = app.viewport.surface_render_mesh
    app.key_press(SHIFT_S)  # symmetry X; reported as a topology change (K-3), no geometry changed
    frame(app)
    assert "Symmetrie X" in app.status_message
    assert builds(app) == before
    assert app.viewport.surface_render_mesh is rm
    mesh = app.viewport.mesh
    right = [v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] > 0.5]
    app.selection.set({right[0]})
    hold_move(app, W, dx=0.0, dy=-30.0)
    frame(app)
    assert_surface_matches(app)
    undo_redo_matches(app)


# -- topology tools -------------------------------------------------------------------------


def test_extrude_rebuilds_and_undo_restores(app):
    on(app)
    app.key_press(K3)
    faces_before = app.subdivision.provider.derived_counts[1]
    topo_before = app.subdivision.provider.topology_builds
    face = sorted(app.viewport.mesh.all_face_ids(), key=int)[0]
    app.selection.set({face})
    hold_move(app, T, dx=40.0, dy=0.0, at=(WIDTH / 2, HEIGHT / 2))
    frame(app)
    assert app.subdivision.provider.topology_builds > topo_before
    assert app.subdivision.provider.derived_counts[1] > faces_before
    assert_surface_matches(app)
    app.key_press(CTRL_Z)
    frame(app)
    assert app.subdivision.provider.derived_counts[1] == faces_before
    assert_surface_matches(app)
    app.key_press(CTRL_Y)
    frame(app)
    assert_surface_matches(app)


def test_split_and_edge_connect(app):
    on(app)
    mesh = app.viewport.mesh
    app.key_press(K2)
    face = sorted(mesh.all_face_ids(), key=int)[0]
    boundary = mesh.face_vertices(face)
    edges = [next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {boundary[k], boundary[(k + 1) % 4]})
             for k in range(4)]
    app.selection.set({edges[0], edges[2]})  # two opposite edges of one quad: Edge Connect
    assert app.key_press(C)
    frame(app)
    assert_surface_matches(app)
    undo_redo_matches(app)
    app.selection.set({edges[1]})  # one edge: Split
    assert app.key_press(C)
    frame(app)
    assert_surface_matches(app)
    undo_redo_matches(app)


def test_knife_cut_commit_and_undo():
    app = _app("cube")
    on(app)
    mesh = app.viewport.mesh
    faces_before = app.subdivision.provider.derived_counts[1]
    vids = sorted(mesh.all_vertex_ids(), key=int)

    def edge(a, b):
        return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {vids[a], vids[b]})

    def edge_screen(eid, t):
        pos = screen(app, target_position(mesh, {"kind": "edge", "edge_id": eid, "t": t}))
        assert knife_pick(app.camera, mesh, *pos, WIDTH, HEIGHT)["edge_id"] == eid
        return pos

    app.selection.clear()
    assert app.key_press(C) and app.knife_active
    for pos in (screen(app, mesh.vertex_position(vids[7])), edge_screen(edge(5, 6), 0.3),
                edge_screen(edge(2, 6), 0.5), edge_screen(edge(7, 3), 0.5)):
        app.pointer_motion(*pos)
        app.pointer_press(LMB, *pos)
        app.pointer_release("LEFT", *pos)
    assert app.key_press(ENTER)
    assert not app.knife_active
    frame(app)
    assert app.subdivision.provider.derived_counts[1] != faces_before
    assert_surface_matches(app)
    undo_redo_matches(app)


def test_dissolve_makes_an_ngon_the_evaluator_supports(app):
    on(app)
    mesh = app.viewport.mesh
    app.key_press(K2)
    app.selection.set({sorted(mesh.all_edge_ids(), key=int)[0]})
    assert app.key_press(BACKSPACE)
    frame(app)
    assert app.subdivision.provider.message is None
    assert_surface_matches(app)
    undo_redo_matches(app)


def test_delete_with_a_hole_keeps_a_boundary_surface(app):
    on(app)
    mesh = app.viewport.mesh
    app.key_press(K3)
    app.selection.set({sorted(mesh.all_face_ids(), key=int)[0]})
    assert app.key_press(DELETE)
    frame(app)
    assert app.subdivision.provider.message is None
    assert_surface_matches(app)
    undo_redo_matches(app)


# -- unsupported topology -------------------------------------------------------------------


def _bowtie_faces(mesh):
    """Two opposite faces around an interior valence-4 vertex: deleting both leaves that vertex
    with four boundary edges (outside the Catmull-Clark boundary rule)."""
    for v in sorted(mesh.all_vertex_ids(), key=int):
        faces = [f for f in mesh.all_face_ids() if v in mesh.face_vertices(f)]
        if len(faces) != 4:
            continue
        f0 = faces[0]
        opposite = [f for f in faces[1:] if not (set(mesh.face_vertices(f)) & set(mesh.face_vertices(f0))) - {v}]
        if opposite:
            return {f0, opposite[0]}
    raise AssertionError("no valence-4 vertex")


def test_unsupported_topology_falls_back_to_the_cage_visibly_and_recovers_on_undo(app):
    on(app)
    mesh = app.viewport.mesh
    app.key_press(K3)
    app.selection.set(_bowtie_faces(mesh))
    assert app.key_press(DELETE)
    frame(app)
    provider = app.subdivision.provider
    assert provider.surface_mesh is None
    assert app.viewport.surface_render_mesh is None  # the viewport draws the cage's own faces
    assert provider.message.startswith("SubD aus:")
    assert app.status_message.startswith("SubD aus:")
    assert "Randvertex" in provider.message
    assert app.subdivision.view == VIEW_CAGE  # the user's choice stays; only the surface is off
    # edits keep working on the control mesh and the History stays intact
    hover_some_vertex(app)
    hold_move(app)
    frame(app)
    assert provider.surface_mesh is None
    app.key_press(CTRL_Z)  # the move
    app.key_press(CTRL_Z)  # the delete
    frame(app)
    assert provider.message is None
    assert_surface_matches(app)


def test_unsupported_mesh_provider_alone():
    positions = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (-1, 0, 0), (-1, -1, 0), (0, -1, 0)]
    mesh = mesh_from_positions_and_faces(positions, [(0, 1, 2, 3), (0, 4, 5, 6)])
    provider = SubdSurfaceProvider()
    messages = []
    provider.on_message = messages.append
    provider.set_enabled(True)
    assert provider.sync(mesh, None) == set()
    assert provider.surface_mesh is None
    assert messages and messages[0].startswith("SubD aus:")
    provider.set_enabled(False)
    provider.sync(mesh, None)
    provider.set_enabled(True)
    provider.sync(mesh, None)
    assert provider.surface_mesh is None and provider.message.startswith("SubD aus:")


def test_switching_off_and_on_follows_moves_made_while_off(app):
    on(app)
    app.key_press(V)
    app.key_press(V)  # off
    frame(app)
    hover_some_vertex(app)
    hold_move(app)
    frame(app)
    on(app)
    assert_surface_matches(app)


def test_edit_object_switch_rebuilds_for_the_new_mesh(app):
    on(app)
    old = app.subdivision.provider.surface_mesh
    app.viewport.set_edit_mesh(mesh_from_positions_and_faces(
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)], [[0, 1, 2, 3]]))
    frame(app)
    assert app.subdivision.provider.surface_mesh is not old
    assert_surface_matches(app)


def test_a_topology_edit_patches_the_derived_mesh_and_its_gpu_buffers_in_place():
    """Head, level 2 (5 184 faces, above `RenderMesh`'s incremental threshold): splitting one control
    edge rebuilds stencils, but the derived mesh is the same object, patched; the surface's
    RenderMesh patches its topology instead of a structural rebuild. Undo / Redo the same."""
    app = _app("head_basemesh")
    on(app)
    provider = app.subdivision.provider
    surface, rm = provider.surface_mesh, app.viewport.surface_render_mesh
    faces = len(surface.all_face_ids())
    stats = lambda name: rm.benchmark_counters.get(name, 0)  # noqa: E731
    structural, patches = stats("structural_rebuilds"), stats("topology_patches")
    mesh = app.viewport.mesh
    edge = sorted(mesh.all_edge_ids(), key=int)[40]
    assert app.apply_mesh_change("Split (Test)", lambda: (mesh.split_edge(edge), None)[1])
    frame(app)
    assert provider.surface_mesh is surface and app.viewport.surface_render_mesh is rm
    assert provider.surface_patches == 1
    assert stats("structural_rebuilds") == structural
    assert stats("topology_patches") == patches + 1
    assert len(surface.all_face_ids()) > faces
    assert_surface_matches(app)
    for key in (CTRL_Z, CTRL_Y):
        app.key_press(key)
        frame(app)
        assert provider.surface_mesh is surface
        assert stats("structural_rebuilds") == structural
        assert_surface_matches(app)
    assert provider.surface_patches == 3


def test_a_level_switch_builds_a_fresh_surface(app):
    on(app)
    surface = app.subdivision.provider.surface_mesh
    app.key_press(ctrl(3))
    frame(app)
    assert app.subdivision.provider.surface_mesh is not surface
    assert_surface_matches(app)
