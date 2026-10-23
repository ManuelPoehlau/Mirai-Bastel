"""SubD line presentation (2026-10-23), headless: hierarchy, correspondence and depth policy.

- Exactly one line system is primary per view: cage view = the cage (no isolines except highlighted
  chains); iso view = the isolines, the cage secondary at `secondary_strength` (default 0.35, Alt+V
  steps, 0 = hidden).
- A hovered / selected control edge highlights its isoline chain — taken from the evaluator's
  provenance (`SubdLevel.iso_control_edge`), never from proximity — and stays correct after moves,
  topology edits, symmetry and Undo/Redo. Face mode: the chains of the face's boundary edges.
- The presentation draws under the app's highlights (`DRAW_UNDER_HIGHLIGHTS`), so the app's own
  hover/selected cage edge is drawn last; with the cage always visible (Shift+V) the hidden part of a
  highlighted cage edge gets its own layer (depth GREATER), so the highlight is never covered.
- The replacement surface is always polygon-offset; the viewport's wire overlay is not drawn on top of
  the preview's own cage lines (`replaces_wire`); in Wireframe the preview draws nothing.
- Hover changes rebuild no cage / isoline segments and touch no surface data.
"""

from __future__ import annotations

import itertools

import pytest

import tests.subdivision_meshes  # noqa: F401  (examples/ on sys.path)
from core import SelectionMode
from loaders.assets import asset_path
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.subdivision import KIND_EDGE, KIND_VERTEX, VIEW_CAGE, VIEW_ISO, SubdSurface
from mirai.subdivision.preview import (
    CAGE_HOVER_LAYER,
    CAGE_LAYER,
    CAGE_SELECTED_LAYER,
    DEFAULT_SECONDARY_STRENGTH,
    ISO_HOVER_LAYER,
    ISO_LAYER,
    ISO_SELECTED_LAYER,
    SECONDARY_STEPS,
)
from viewport.resource_store import TraceStore

WIDTH, HEIGHT = 800, 600


def _key(value: str, *mods: str) -> Input:
    return Input("key", value, frozenset(mods))


V, SHIFT_V, ALT_V, W = _key("v"), _key("v", "shift"), _key("v", "alt"), _key("w")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


class _StyleStore(TraceStore):
    """TraceStore that records the draw style the viewport hands to a GL store."""

    def set_draw_style(self, flat: bool, polygon_offset: bool, alpha: float = 1.0) -> None:
        self.flat, self.polygon_offset, self.alpha = flat, polygon_offset, alpha


class _Sink:
    """Headless stand-in for `GLSubdLineOverlay`: records data, styles, depth modes and draws."""

    def __init__(self) -> None:
        self.segments: dict = {}
        self.styles: dict = {}
        self.depth: dict = {}
        self.set_calls = 0
        self.drawn: list = []

    def set_segments(self, layer, segments) -> None:
        self.set_calls += 1
        self.segments[layer] = list(segments)

    def set_style(self, layer, rgba) -> None:
        self.styles[layer] = tuple(rgba)

    def set_depth(self, layer, mode) -> None:
        self.depth[layer] = mode

    def draw(self, camera_uniforms, layers) -> None:
        self.drawn.append(tuple(layers))


def _app(asset="subd_cube", sink=True) -> Application:
    app = Application()
    app.init_scene("obj", obj_path=asset_path(asset), store_type=_StyleStore,
                   subd_overlay_type=_Sink if sink else None)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.knife_clock = itertools.count(0.0, 10.0).__next__
    return app


def on(app, view=VIEW_CAGE) -> None:
    while app.subdivision.view != view:
        app.key_press(V)
    app.viewport.sync()


def lines(app):
    return app.subdivision.lines


def hover(app, element) -> None:
    app.selection.hovered = element
    app.viewport.on_selection_changed()
    app.viewport.sync()


def chain_is_the_control_edge(app, edge, segments) -> None:
    """`segments` is exactly the isoline chain of control `edge` by provenance: 2^level segments,
    every one along that control edge, joined into one path between the two endpoints' vertex points."""
    provider = app.subdivision.provider
    level, vertex_ids, _faces = provider.derived_elements()
    surface = SubdSurface(app.viewport.mesh)
    index = surface.topology.edge_ids.index(edge)
    chain = [level.iso_edges[i] for i, c in enumerate(level.iso_control_edge) if c == index]
    assert len(chain) == 2 ** level.level
    p = provider.derived_positions()
    assert sorted(segments) == sorted((p[a], p[b]) for a, b in chain)
    a, b = surface.topology.edges[index]
    ends = [d for seg in chain for d in seg]
    for d in ends:
        assert (level.vert_kind[d], level.vert_origin[d]) in ((KIND_EDGE, index), (KIND_VERTEX, a), (KIND_VERTEX, b))
    odd = [d for d in set(ends) if ends.count(d) == 1]
    assert sorted(level.vert_origin[d] for d in odd) == sorted((a, b))


# -- hierarchy ---------------------------------------------------------------------------------


def test_cage_view_draws_the_cage_primary_and_no_isolines():
    app = _app()
    on(app, VIEW_CAGE)
    seg = lines(app).segments
    assert seg[CAGE_LAYER] and not seg[ISO_LAYER]
    sink = lines(app).sink
    assert sink.styles[CAGE_LAYER][3] == 1.0
    lines(app).draw([0.0] * 32)
    assert CAGE_LAYER in sink.drawn[-1] and ISO_LAYER not in sink.drawn[-1]


def test_iso_view_draws_isolines_primary_and_the_cage_secondary():
    app = _app()
    on(app, VIEW_ISO)
    seg = lines(app).segments
    assert seg[ISO_LAYER] and seg[CAGE_LAYER]
    sink = lines(app).sink
    assert sink.styles[ISO_LAYER][3] == 1.0
    assert sink.styles[CAGE_LAYER][3] == pytest.approx(DEFAULT_SECONDARY_STRENGTH)
    lines(app).draw([0.0] * 32)
    order = sink.drawn[-1]
    assert order.index(ISO_LAYER) < order.index(CAGE_LAYER)  # primary first, the faint cage over it


def test_secondary_strength_is_one_parameter_with_a_documented_default_and_steps():
    app = _app()
    on(app, VIEW_ISO)
    assert DEFAULT_SECONDARY_STRENGTH == 0.35
    assert 0.0 in SECONDARY_STEPS and all(0.0 <= s < 1.0 for s in SECONDARY_STEPS)
    seen = []
    for _ in SECONDARY_STEPS:
        assert app.key_press(ALT_V)
        app.viewport.sync()
        seen.append(app.subdivision.secondary_strength)
        assert lines(app).sink.styles[CAGE_LAYER][3] == pytest.approx(seen[-1])
    assert sorted(seen) == sorted(SECONDARY_STEPS)
    assert seen[-1] == DEFAULT_SECONDARY_STRENGTH
    # 0 = hidden: no cage drawn in the iso view, but the option is one key away
    app.subdivision.set_secondary_strength(0.0)
    app.viewport.sync()
    lines(app).draw([0.0] * 32)
    assert CAGE_LAYER not in lines(app).sink.drawn[-1]


def test_the_secondary_strength_does_not_weaken_the_cage_view():
    app = _app()
    on(app, VIEW_CAGE)
    app.subdivision.set_secondary_strength(0.15)
    app.viewport.sync()
    assert lines(app).sink.styles[CAGE_LAYER][3] == 1.0


# -- correspondence ------------------------------------------------------------------------------


@pytest.mark.parametrize("view", [VIEW_CAGE, VIEW_ISO])
def test_a_hovered_edge_highlights_its_isoline_chain_by_provenance(view):
    app = _app()
    on(app, view)
    app.key_press(_key("2"))
    edge = sorted(app.viewport.mesh.all_edge_ids(), key=int)[5]
    hover(app, edge)
    chain_is_the_control_edge(app, edge, lines(app).segments[ISO_HOVER_LAYER])
    assert lines(app).segments[ISO_SELECTED_LAYER] == []


def test_selected_edges_highlight_their_chains_and_survive_moves_topology_and_undo():
    app = _app()
    on(app, VIEW_CAGE)
    mesh = app.viewport.mesh
    app.key_press(_key("2"))
    edge = sorted(mesh.all_edge_ids(), key=int)[3]
    app.selection.set({edge})
    app.viewport.on_selection_changed()
    app.viewport.sync()

    def check():
        chain_is_the_control_edge(app, edge, lines(app).segments[ISO_SELECTED_LAYER])

    check()
    # move the edge (W on the selection): positions only
    x, y = WIDTH / 2, HEIGHT / 2
    app.key_press(W)
    for _ in range(3):
        x += 8
        app.pointer_motion(x, y, 8, 0)
    app.key_release(W)
    app.viewport.sync()
    check()
    # a topology edit elsewhere (split another edge), then Undo / Redo
    other = sorted(mesh.all_edge_ids(), key=int)[20]
    assert app.apply_mesh_change("Split (Test)", lambda: (mesh.split_edge(other), None)[1])
    app.selection.set({edge})
    app.viewport.on_selection_changed()
    app.viewport.sync()
    check()
    for key in (CTRL_Z, CTRL_Z, CTRL_Y):
        app.key_press(key)
        app.selection.mode = SelectionMode.EDGE
        app.selection.set({edge})
        app.viewport.on_selection_changed()
        app.viewport.sync()
        check()


def test_face_mode_highlights_the_chains_of_the_face_boundary():
    app = _app()
    on(app, VIEW_ISO)
    mesh = app.viewport.mesh
    app.key_press(_key("3"))
    face = sorted(mesh.all_face_ids(), key=int)[0]
    hover(app, face)
    segs = lines(app).segments[ISO_HOVER_LAYER]
    boundary = mesh.face_edges(face)
    assert len(segs) == len(boundary) * 2 ** app.subdivision.level
    expected = []
    for e in boundary:
        p = app.subdivision.provider.derived_positions()
        level = app.subdivision.provider.derived_elements()[0]
        expected += [(p[a], p[b]) for a, b in (level.iso_edges[i] for i in app.subdivision.provider.iso_indices_of(e))]
    assert sorted(segs) == sorted(expected)


def test_symmetric_move_keeps_the_chain_on_the_control_edge():
    app = Application()
    app.init_scene("cube", store_type=_StyleStore, subd_overlay_type=_Sink)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    on(app, VIEW_CAGE)
    app.key_press(_key("s", "shift"))
    mesh = app.viewport.mesh
    app.key_press(_key("2"))
    edge = sorted(mesh.all_edge_ids(), key=int)[0]
    app.selection.set({edge})
    app.viewport.on_selection_changed()
    app.key_press(W)
    app.pointer_motion(WIDTH / 2 + 10, HEIGHT / 2, 10, 0)
    app.pointer_motion(WIDTH / 2 + 20, HEIGHT / 2, 10, 0)
    app.key_release(W)
    app.viewport.sync()
    chain_is_the_control_edge(app, edge, lines(app).segments[ISO_SELECTED_LAYER])


# -- depth policy --------------------------------------------------------------------------------


def test_depth_policy_of_every_layer():
    app = _app()
    on(app, VIEW_CAGE)
    sink = lines(app).sink
    assert type(lines(app)).DRAW_UNDER_HIGHLIGHTS is True
    assert sink.depth[CAGE_LAYER] == "lequal"
    assert sink.depth[ISO_LAYER] == "lequal"
    assert sink.depth[ISO_HOVER_LAYER] == sink.depth[ISO_SELECTED_LAYER] == "lequal"
    lines(app).draw([0.0] * 32)
    assert CAGE_HOVER_LAYER not in sink.drawn[-1]  # the app's own highlight covers the visible cage
    app.key_press(SHIFT_V)  # cage always visible
    app.viewport.sync()
    assert sink.depth[CAGE_LAYER] == "always"
    assert sink.depth[CAGE_HOVER_LAYER] == sink.depth[CAGE_SELECTED_LAYER] == "greater"
    lines(app).draw([0.0] * 32)
    assert CAGE_HOVER_LAYER in sink.drawn[-1] and CAGE_SELECTED_LAYER in sink.drawn[-1]


def test_the_hidden_part_of_a_highlighted_cage_edge_is_drawn_when_the_cage_is_always_visible():
    app = _app()
    on(app, VIEW_CAGE)
    app.key_press(SHIFT_V)
    app.key_press(_key("2"))
    mesh = app.viewport.mesh
    edge = sorted(mesh.all_edge_ids(), key=int)[1]
    app.selection.set({edge})
    app.viewport.on_selection_changed()
    app.viewport.sync()
    a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(edge))
    assert lines(app).segments[CAGE_SELECTED_LAYER] == [(a, b)]


def test_the_replacement_surface_is_always_polygon_offset():
    app = _app()
    on(app, VIEW_ISO)
    store = app.viewport.surface_render_mesh.store
    assert store.polygon_offset is True  # no wire, no highlight
    app.key_press(_key("d"))  # Flat
    app.viewport.sync()
    assert store.polygon_offset is True and store.flat is True


def test_the_wire_overlay_does_not_double_the_preview_cage():
    app = _app()
    app.key_press(_key("d", "shift"))  # wire overlay on
    assert app.viewport.wire_drawn()
    on(app, VIEW_ISO)
    assert not app.viewport.wire_drawn()  # the preview draws the cage (secondary) itself
    app.key_press(V)  # off
    app.viewport.sync()
    assert app.viewport.wire_drawn()


def test_wireframe_display_shows_the_plain_wire_and_no_preview_lines():
    app = _app()
    on(app, VIEW_CAGE)
    app.key_press(_key("d"))
    app.key_press(_key("d"))  # Shaded -> Flat -> Wireframe
    app.viewport.sync()
    assert app.display.mode.name == "WIREFRAME"
    assert app.viewport.wire_drawn()
    sink = lines(app).sink
    n = len(sink.drawn)
    lines(app).draw([0.0] * 32)
    assert len(sink.drawn) == n  # nothing drawn without faces


def test_hover_changes_rebuild_no_cage_or_isoline_segments():
    app = _app()
    on(app, VIEW_ISO)
    cage, iso = lines(app).segments[CAGE_LAYER], lines(app).segments[ISO_LAYER]
    revision = app.subdivision.provider.revision
    app.key_press(_key("2"))
    for e in sorted(app.viewport.mesh.all_edge_ids(), key=int)[:5]:
        hover(app, e)
        assert lines(app).segments[CAGE_LAYER] is cage
        assert lines(app).segments[ISO_LAYER] is iso
    assert app.subdivision.provider.revision == revision
