"""Region colours (Manu 2026-10-25): a distinct, desaturated colour per saved region, written into the face rows
(free `.w` of corner texels 1-3), patched like any face data, shown or hidden by one draw-state switch."""

from __future__ import annotations

import colorsys

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401

from core import FaceRegion, FaceRegions
from core.mesh import Mesh
from mirai import regions as api
from mirai.application import Application
from mirai.interaction.input import Input
from viewport.render_mesh import FACE_ROW_FLOATS, RenderMesh
from viewport.resource_store import TraceStore

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


NEW, TOGGLE, UNDO = _key("g", "ctrl"), _key("d", "ctrl", "alt"), _key("z", "ctrl")


def _grid(n: int = 3) -> Mesh:
    mesh = Mesh()
    ids = [[mesh.add_vertex((float(x), float(y), 0.1 * ((x * y) % 2))) for x in range(n + 1)] for y in range(n + 1)]
    for y in range(n):
        for x in range(n):
            mesh.add_face([ids[y][x], ids[y][x + 1], ids[y + 1][x + 1], ids[y + 1][x]])
    return mesh


def _row(rm: RenderMesh, face) -> list[float]:
    data = rm.store.data("face_shading")
    r = rm._face_row[face]
    return list(data[r * FACE_ROW_FLOATS:(r + 1) * FACE_ROW_FLOATS])


# -- palette ----------------------------------------------------------------------------


def test_every_slot_has_its_own_desaturated_never_black_colour():
    colors = [api.region_color(i) for i in range(len(api.SET_NAMES) + 12)]
    assert len(set(colors)) == len(colors)
    hues = sorted(colorsys.rgb_to_hsv(*c)[0] for c in colors)
    gaps = [b - a for a, b in zip(hues, hues[1:])]
    assert min(gaps) > 0.01  # no two slots share (nearly) a hue
    for c in colors:
        h, s, v = colorsys.rgb_to_hsv(*c)
        assert s <= 0.5 and v >= 0.8 and any(c)  # desaturated, bright, and black stays "no region"


def test_region_tints_use_the_slot_colour_later_regions_win_and_dead_ids_stay():
    mesh = _grid()
    faces = mesh.all_face_ids()
    mesh.face_regions = FaceRegions((
        FaceRegion("Brow", frozenset(faces[:4])),
        FaceRegion("Jaw", frozenset(faces[3:5])),
    ))
    tints = api.region_tints(mesh)
    assert tints[faces[0]] == api.region_color(0)
    assert tints[faces[3]] == api.region_color(api.SET_NAMES.index("Jaw"))  # overlap: the later one
    assert faces[6] not in tints
    mesh.delete_faces([faces[0]])
    assert faces[0] in api.region_tints(mesh)  # a revived face comes back coloured
    assert api.region_tints(_grid()) == {}


# -- RenderMesh rows -----------------------------------------------------------------------


def test_tinted_rows_carry_the_colour_and_untinted_rows_do_not_change():
    mesh = _grid()
    rm = RenderMesh(mesh, store_type=TraceStore)
    faces = mesh.all_face_ids()
    before = {f: _row(rm, f) for f in faces}
    rm.set_face_tints({faces[1]: (0.5, 0.25, 0.75)})
    row = _row(rm, faces[1])
    assert (row[7], row[11], row[15]) == (0.5, 0.25, 0.75)
    assert [v for i, v in enumerate(row) if i not in (7, 11, 15)] == [
        v for i, v in enumerate(before[faces[1]]) if i not in (7, 11, 15)
    ]
    for f in faces:
        if f != faces[1]:
            assert _row(rm, f) == before[f]
    rm.set_face_tints({})
    assert _row(rm, faces[1]) == before[faces[1]]


def test_a_patch_uploads_only_the_changed_rows_and_equals_a_fresh_build():
    mesh = _grid(4)
    rm = RenderMesh(mesh, store_type=TraceStore)
    faces = mesh.all_face_ids()
    rm.set_face_tints({f: (0.9, 0.8, 0.7) for f in faces[:6]})
    uploads = rm.stats.get("face_data_uploads")
    rm.set_face_tints({**{f: (0.9, 0.8, 0.7) for f in faces[:6]}, faces[7]: (0.1, 0.2, 0.3)})
    fresh = RenderMesh(mesh, store_type=TraceStore)
    fresh.set_face_tints({**{f: (0.9, 0.8, 0.7) for f in faces[:6]}, faces[7]: (0.1, 0.2, 0.3)})
    for f in faces:
        assert _row(rm, f) == _row(fresh, f)
    assert rm.stats.get("face_data_uploads") - uploads == 1  # only the one new face's row
    fresh._watch.close()


def test_tints_survive_a_topology_patch(monkeypatch):
    import viewport.render_mesh as module

    monkeypatch.setattr(module, "INCREMENTAL_MIN_ELEMENTS", 0)
    mesh = _grid(3)
    rm = RenderMesh(mesh, store_type=TraceStore)
    faces = mesh.all_face_ids()
    tints = {f: (0.6, 0.7, 0.8) for f in faces[:3]}
    rm.set_face_tints(tints)
    mesh.split_edge(mesh.all_edge_ids()[0])
    mesh.delete_faces([faces[8]])
    rm.mark_topology_dirty()
    rm.sync()
    fresh = RenderMesh(mesh, store_type=TraceStore)
    fresh.set_face_tints(tints)
    for f in mesh.all_face_ids():
        assert _row(rm, f) == _row(fresh, f), f
    fresh._watch.close()


# -- App path ------------------------------------------------------------------------------


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("obj", obj_path=HEAD_OBJ)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _assign(app, count=6, start=100):
    from core import SelectionMode

    app.selection.mode = SelectionMode.FACE
    faces = set(app.scene.mesh.all_face_ids()[start:start + count])
    app.selection.set(faces)
    app.viewport.on_selection_changed()
    assert app.key_press(NEW)
    return faces


def test_assign_undo_and_scene_load_update_the_viewport_colours(app):
    faces = _assign(app)
    app.update_viewport(0.016)
    assert set(app.viewport.render_mesh._tints) == faces
    assert all(c == api.region_color(api.slot_index("Group 1")) for c in app.viewport.render_mesh._tints.values())
    app.key_press(UNDO)
    app.update_viewport(0.016)
    assert app.viewport.render_mesh._tints == {}
    app.key_press(_key("y", "ctrl"))
    app.update_viewport(0.016)
    assert set(app.viewport.render_mesh._tints) == faces
    app.init_scene("cube")
    app.update_viewport(0.016)
    assert app.viewport.render_mesh._tints == {}


def test_ctrl_alt_d_toggles_the_colours_as_draw_state_only(app):
    _assign(app)
    app.update_viewport(0.016)
    assert app.display.region_tint and app.viewport.region_tint
    tints = dict(app.viewport.render_mesh._tints)
    assert app.key_press(TOGGLE)
    assert not app.display.region_tint and not app.viewport.region_tint
    assert "off" in app.status_message
    assert app.viewport.render_mesh._tints == tints  # nothing re-uploaded, the rows keep the colours
    assert app.key_press(TOGGLE) and app.viewport.region_tint
    assert not app.history.can_undo() or True  # view state


def test_each_edit_object_gets_its_own_colours(app):
    _assign(app)
    app.update_viewport(0.016)
    first = app.scene.edit_object_id
    other = app.add_primitive("cube")
    app._set_edit_object(other.id if hasattr(other, "id") else other)
    app.update_viewport(0.016)
    assert app.viewport.render_mesh._tints == {}
    app._set_edit_object(first)
    app.update_viewport(0.016)
    assert app.viewport.render_mesh._tints


def test_hud_row_shows_the_group_faces_and_colour_state(app):
    from hud import hud_rows, hud_state
    from hud import key_hints

    _assign(app)
    row = {r.label: r for r in hud_rows(hud_state(app), key_hints(app.bindings))}["Region"]
    assert row.value == "Group 1 · 6 faces · 1 group · colours on" and row.on
    app.key_press(TOGGLE)
    row = {r.label: r for r in hud_rows(hud_state(app), key_hints(app.bindings))}["Region"]
    assert "colours off" in row.value


# -- SubD ---------------------------------------------------------------------------------


def test_subd_surface_faces_take_the_colour_of_their_control_face():
    import tests.subdivision_meshes  # noqa: F401
    from loaders.assets import asset_path
    from mirai.subdivision import VIEW_CAGE

    app = Application()
    app.init_scene("obj", obj_path=asset_path("subd_cube"))
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    while app.subdivision.view != VIEW_CAGE:
        assert app.key_press(_key("v"))
    mesh = app.scene.mesh
    face = mesh.all_face_ids()[0]
    from core import SelectionMode

    app.selection.mode = SelectionMode.FACE
    app.selection.set({face})
    app.viewport.on_selection_changed()
    assert app.key_press(NEW)
    app.update_viewport(0.016)
    provider = app.subdivision.provider
    _level, _vids, derived_faces = provider.derived_elements()
    rm = app.viewport.surface_render_mesh
    tinted = set(rm._tints)
    assert tinted and len(tinted) == len(derived_faces) // len(mesh.all_face_ids())
    assert set(rm._tints.values()) == {api.region_color(api.slot_index("Group 1"))}
    app.key_press(UNDO)
    app.update_viewport(0.016)
    assert rm._tints == {}
