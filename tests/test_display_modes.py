"""Display-Modi (WP-06 B5a): Dispatch, Viewport-Setter, Edge-Segmente.

Headless (TraceStore, kein GL-Kontext). Der echte GL-Zeichenpfad
(Flat Shading, Linien-Overlay) liegt in `tests/test_gl_line_overlay.py`.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import GLOBAL_CONTEXT, TOPOLOGY_CONTEXT, Input
from mirai.scene_factory import create_cube
from mirai.viewport.display import DisplayMode
from viewport import GLLineOverlay, Viewport, edge_segments
from viewport.gl_line_overlay import WIRE_LAYER

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


D = _key("d")
SHIFT_D = _key("d", "shift")
W = _key("w")
CTRL_Z = _key("z", "ctrl")
CTRL_Y = _key("y", "ctrl")


class RecordingLineOverlay:
    """Stellvertreter für `GLLineOverlay` (gleiche Schnittstelle, kein GL).
    `segments`/`draws` beziehen sich auf den Wire-Layer (B5a); die
    Highlight-Layer (B5b) landen in `layers`."""

    def __init__(self) -> None:
        self.segments: list = []
        self.layers: dict[str, list] = {}
        self.draws = 0

    def set_segments(self, segments, layer: str = WIRE_LAYER) -> None:
        if layer == WIRE_LAYER:
            self.segments = list(segments)
        else:
            self.layers[layer] = list(segments)

    def draw(self, camera_uniforms, layers=(WIRE_LAYER,)) -> None:
        if WIRE_LAYER in layers:
            self.draws += 1


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube", line_overlay_type=RecordingLineOverlay)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


@pytest.fixture
def set_display_calls(app, monkeypatch) -> list[tuple[bool, bool, bool]]:
    calls: list[tuple[bool, bool, bool]] = []
    original = app.viewport.set_display

    def spy(show_faces, show_edges, flat):
        calls.append((show_faces, show_edges, flat))
        original(show_faces=show_faces, show_edges=show_edges, flat=flat)

    monkeypatch.setattr(app.viewport, "set_display", spy)
    return calls


def _rebuilds(app) -> int:
    return app.viewport.benchmark_counters.get("line_overlay_rebuilds", 0)


def _expected_segments(app) -> list:
    return edge_segments(app.scene.mesh)


# -- Dispatch / Tasten -----------------------------------------------------------


def test_start_state_is_shaded_without_overlay(app):
    vp = app.viewport
    assert (vp.show_faces, vp.show_edges, vp.flat) == (True, False, False)
    assert app.display.label == "Shaded"


def test_d_cycles_shaded_flat_wireframe_shaded(app):
    seen = []
    for _ in range(4):
        assert app.key_press(D) is True
        seen.append((app.display.mode, app.status_message))
    assert seen == [
        (DisplayMode.FLAT_SHADED, "Display: Flat Shaded"),
        (DisplayMode.WIREFRAME, "Display: Wireframe"),
        (DisplayMode.SHADED, "Display: Shaded"),
        (DisplayMode.FLAT_SHADED, "Display: Flat Shaded"),
    ]


def test_shift_d_toggles_overlay(app):
    app.key_press(SHIFT_D)
    assert app.display.wireframe_overlay is True
    assert app.status_message == "Display: Shaded + Wire"
    app.key_press(SHIFT_D)
    assert app.display.wireframe_overlay is False
    assert app.status_message == "Display: Shaded"


def test_set_commands_set_mode_directly(app):
    for command, mode in (
        (cmd.SET_WIREFRAME, DisplayMode.WIREFRAME),
        (cmd.SET_FLAT_SHADED, DisplayMode.FLAT_SHADED),
        (cmd.SET_SHADED, DisplayMode.SHADED),
    ):
        assert app.dispatch_command(command) is True
        assert app.display.mode is mode
        assert app.status_message == "Display: " + app.display.label


def test_every_display_change_sets_a_status_line(app):
    serial = app.status_serial
    app.key_press(D)
    app.key_press(SHIFT_D)
    app.dispatch_command(cmd.SET_WIREFRAME)
    assert app.status_serial == serial + 3


def test_display_command_before_init_scene_is_applied_later():
    app = Application()
    app.dispatch_command(cmd.SET_WIREFRAME)
    app.init_scene("cube")
    vp = app.viewport
    assert (vp.show_faces, vp.show_edges, vp.flat) == (False, True, False)


# -- Viewport.set_display bekommt die richtigen Grundwerte (E36) -----------------


def test_set_display_values_per_mode(app, set_display_calls):
    app.key_press(D)          # Flat Shaded
    app.key_press(D)          # Wireframe
    app.key_press(SHIFT_D)    # Wireframe (+ Overlay-Flag, ohne sichtbare Wirkung)
    app.key_press(D)          # Shaded + Wire
    app.key_press(D)          # Flat Shaded + Wire
    assert set_display_calls == [
        (True, False, True),
        (False, True, False),
        (False, True, False),
        (True, True, False),
        (True, True, True),
    ]
    assert app.status_message == "Display: Flat Shaded + Wire"


def test_set_display_forwards_draw_style_to_a_drawable_store():
    vp = Viewport(create_cube())
    styles = []
    vp.render_mesh.store.set_draw_style = lambda flat, polygon_offset: styles.append(
        (flat, polygon_offset)
    )
    vp.set_display(show_faces=True, show_edges=True, flat=True)
    vp.set_display(show_faces=False, show_edges=True, flat=False)
    vp.set_display(show_faces=True, show_edges=False, flat=False)
    # Polygon-Offset nur, wenn Faces UND Edges gezeichnet werden (E40).
    assert styles == [(True, True), (False, False), (False, False)]


# -- Edge-Segmente (E38) ----------------------------------------------------------


def test_cube_gives_twelve_segments_with_edge_endpoints():
    mesh = create_cube()
    segments = edge_segments(mesh)
    assert len(segments) == 12
    expected = {
        frozenset((mesh.vertex_position(a), mesh.vertex_position(b)))
        for a, b in (mesh.edge_vertices(e) for e in mesh.all_edge_ids())
    }
    assert {frozenset(s) for s in segments} == expected
    # Würfelkanten sind achsparallel: genau eine Koordinate unterscheidet sich.
    for a, b in segments:
        assert sum(1 for i in range(3) if a[i] != b[i]) == 1


def test_no_segments_while_edges_hidden(app):
    app.viewport.sync()
    assert app.viewport.edge_segments == []
    assert _rebuilds(app) == 0


def test_segments_built_when_edges_become_visible(app):
    app.key_press(SHIFT_D)
    app.viewport.sync()
    assert app.viewport.edge_segments == _expected_segments(app)
    assert app.viewport.line_overlay.segments == app.viewport.edge_segments
    assert _rebuilds(app) == 1
    app.viewport.sync()
    assert _rebuilds(app) == 1  # nichts dirty → kein Rebuild


def _move_vertex(app, vid, delta=(0.25, 0.0, 0.0)):
    mesh = app.scene.mesh
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x + delta[0], y + delta[1], z + delta[2]))
    app.viewport.on_vertices_moved({vid})


def test_moved_vertex_updates_its_segments_and_counts_a_rebuild(app):
    app.key_press(SHIFT_D)
    app.viewport.sync()
    before = _rebuilds(app)
    vid = app.scene.mesh.all_vertex_ids()[0]
    _move_vertex(app, vid)
    app.viewport.sync()
    new_pos = app.scene.mesh.vertex_position(vid)
    touching = [s for s in app.viewport.edge_segments if new_pos in s]
    assert len(touching) == 3  # Würfel-Ecke: drei Edges
    assert app.viewport.edge_segments == _expected_segments(app)
    assert _rebuilds(app) == before + 1


def test_no_rebuild_on_move_while_edges_hidden_but_fresh_when_shown(app):
    app.viewport.sync()
    vid = app.scene.mesh.all_vertex_ids()[0]
    _move_vertex(app, vid)
    app.viewport.sync()
    assert _rebuilds(app) == 0
    app.key_press(D)
    app.key_press(D)  # Wireframe
    app.viewport.sync()
    assert _rebuilds(app) == 1
    assert app.viewport.edge_segments == _expected_segments(app)


def test_camera_or_selection_change_does_not_rebuild_segments(app):
    app.key_press(SHIFT_D)
    app.viewport.sync()
    before = _rebuilds(app)
    app.camera.orbit(0.3, 0.1)
    app.viewport.on_camera_changed(WIDTH / HEIGHT)
    app.selection.set({app.scene.mesh.all_vertex_ids()[0]})
    app.viewport.on_selection_changed()
    app.viewport.sync()
    assert _rebuilds(app) == before


def test_segments_follow_move_gesture_and_undo_redo(app):
    app.key_press(SHIFT_D)
    app.viewport.sync()
    original = list(app.viewport.edge_segments)

    app.selection.set({app.scene.mesh.all_vertex_ids()[0]})
    app.viewport.on_selection_changed()
    app.key_press(W)
    app.pointer_motion(400, 300, 30, 10)
    app.viewport.sync()
    moved = list(app.viewport.edge_segments)
    assert moved != original
    assert moved == _expected_segments(app)
    app.key_release(W)

    app.key_press(CTRL_Z)
    app.viewport.sync()
    assert app.viewport.edge_segments == original

    app.key_press(CTRL_Y)
    app.viewport.sync()
    assert app.viewport.edge_segments == moved


def test_topology_change_rebuilds_segments(app):
    app.key_press(SHIFT_D)
    app.viewport.sync()
    app.scene.mesh.split_edge(app.scene.mesh.all_edge_ids()[0])
    app.viewport.on_topology_changed()
    app.viewport.sync()
    assert len(app.viewport.edge_segments) == 13
    assert app.viewport.edge_segments == _expected_segments(app)


# -- Draw-Reihenfolge (headless beobachtbar) --------------------------------------


def test_line_overlay_drawn_only_while_edges_visible(app):
    overlay = app.viewport.line_overlay
    app.viewport.sync()
    app.viewport.render()
    assert overlay.draws == 0
    app.key_press(SHIFT_D)
    app.viewport.sync()
    app.viewport.render()
    assert overlay.draws == 1


def test_wireframe_skips_the_face_pass(app, monkeypatch):
    face_draws = []
    monkeypatch.setattr(
        app.viewport.render_mesh, "render", lambda camera: face_draws.append(camera)
    )
    app.viewport.render()
    assert len(face_draws) == 1
    app.dispatch_command(cmd.SET_WIREFRAME)
    app.viewport.render()
    assert len(face_draws) == 1


# -- GLLineOverlay ohne GL-Kontext --------------------------------------------------


def test_gl_line_overlay_constructs_without_gl_context():
    overlay = GLLineOverlay()
    overlay.set_segments(edge_segments(create_cube()))
    assert overlay.segment_count() == 12
    assert overlay.vertex_list() is None
    assert overlay.uploads == 0


# -- Bindings (E42) -----------------------------------------------------------------


def test_bare_d_cycles_and_o_is_unbound():
    bs = build_default_bindings()
    assert bs.command_for(D) == cmd.CYCLE_DISPLAY_MODE
    assert bs.command_for(SHIFT_D) == cmd.TOGGLE_WIREFRAME_OVERLAY
    assert bs.command_for(_key("o")) is None
    # Kein Topology-Binding auf D: auch dort greift der globale Fallback.
    assert bs.command_for(D, TOPOLOGY_CONTEXT) == cmd.CYCLE_DISPLAY_MODE


def test_d_does_not_collide_with_transform_or_constraint_keys():
    bs = build_default_bindings()
    expected = {
        _key("w"): cmd.MOVE,
        _key("e"): cmd.ROTATE,
        _key("r"): cmd.SCALE,
        _key("x"): cmd.CONSTRAIN_AXIS_X,
        _key("y"): cmd.CONSTRAIN_AXIS_Y,
        _key("z"): cmd.CONSTRAIN_AXIS_Z,
        _key("x", "shift"): cmd.CONSTRAIN_PLANE_YZ,
        _key("y", "shift"): cmd.CONSTRAIN_PLANE_XZ,
        _key("z", "shift"): cmd.CONSTRAIN_PLANE_XY,
    }
    for inp, command in expected.items():
        assert bs.command_for(inp, GLOBAL_CONTEXT) == command
    for command in (cmd.SET_SHADED, cmd.SET_FLAT_SHADED, cmd.SET_WIREFRAME):
        assert command not in {
            bs.command_for(_key(c, *m)) for c in "abcdefghijklmnopqrstuvwxyz"
            for m in ((), ("shift",), ("ctrl",), ("alt",))
        }


def test_display_key_during_armed_transform_keeps_transform(app):
    app.selection.set({app.scene.mesh.all_vertex_ids()[0]})
    app.key_press(W)
    assert app.key_press(D) is True
    assert app.transform_command == cmd.MOVE
    assert app.display.mode is DisplayMode.FLAT_SHADED
