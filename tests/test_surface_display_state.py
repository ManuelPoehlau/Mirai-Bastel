"""Display state on the viewport's replacement surface (audit 2026-11-04, Hide/Show + Region Colours + Morph; Manu I4).

Every surface drawn for the edit mesh shows the edit mesh's Hide / Isolate and region colours, whichever provider
supplies it: the morph mix and the posed surface (ID-identical, `wire_follows_surface`) take the edit mesh's own sets, the
SubD surface maps them through provenance. A provider installed after a Hide learns the current set, and a new surface
RenderMesh for the same surface mesh (the mix kept at 0 %) gets both again. Picking agrees with what is drawn.

Through the whole path: `Application` -> `SurfaceChain` -> `Viewport` -> `RenderMesh` (headless `TraceStore`); the GL
draw and ID pass on the mix are `tests/test_gl_region_tint.py` and `tests/test_gl_morph_picking.py`.
"""

from __future__ import annotations

import random

import tests._bootstrap  # noqa: F401

from core import BoneId, PointLayerInfo, SelectionMode
from mirai import regions as api
from mirai.interaction.input import Input
from mirai.scene_factory import mesh_from_positions_and_faces
from mirai.subdivision import VIEW_CAGE, VIEW_OFF
from mirai.surface_chain import ChainedSurface
from tests.test_application_delete_dissolve import _app
from tests.test_skin_stage import _bind, _bone_pose, _rig


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_H, ALT_H = _key("h", "ctrl"), _key("h", "alt")
NEW_GROUP, TINT_TOGGLE = _key("g", "ctrl"), _key("d", "ctrl", "alt")
UNDO, REDO = _key("z", "ctrl"), _key("y", "ctrl")
SUBD_VIEW = _key("v")


# -- helpers --------------------------------------------------------------------------------------------


def _dead_faces(rm) -> set:
    """The faces whose every triangle is uploaded dead (hidden: not drawn, not in the ID pass)."""
    return {
        f for f, slots in rm._face_triangles.items()
        if slots and all(rm._triangle_hidden(t, rm._triangle_indices[t]) for t in slots)
    }


def _sync(app) -> None:
    app.update_viewport(0.0)


def _faces(app, *indices):
    faces = app.scene.mesh.all_face_ids()
    return {faces[i] for i in indices}


def _group(app, faces) -> None:
    app.selection.mode = SelectionMode.FACE
    app.selection.set(set(faces))
    app.viewport.on_selection_changed()
    assert app.key_press(NEW_GROUP), app.status_message
    _sync(app)


def _hide(app, faces) -> None:
    app.selection.mode = SelectionMode.FACE
    app.selection.set(set(faces))
    app.viewport.on_selection_changed()
    assert app.key_press(CTRL_H), app.status_message
    _sync(app)


def _target(app, weight: int = 50):
    """A target that moves every point (so the mix differs from the rest shape), dialled to `weight`."""
    mesh = app.scene.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Jaw open"))
    for v in mesh.all_vertex_ids():
        x, y, _ = mesh.vertex_position(v)
        mesh.set_layer_value(lid, v, (0.2, 0.1 * y, 0.3 + 0.05 * x))
    app.set_morph_weight(weight, lid)
    _sync(app)
    return lid


def _subd(app, on: bool) -> None:
    want = VIEW_CAGE if on else VIEW_OFF
    for _ in range(4):
        if app.subdivision.view == want:
            break
        assert app.key_press(SUBD_VIEW)
    assert app.subdivision.view == want
    _sync(app)


def _hidden_edit_faces(app) -> set:
    mesh, hidden = app.scene.mesh, app._hidden
    return {f for f in mesh.all_face_ids() if hidden.is_hidden_face(mesh, f)}


def _assert_mix_shows_state(app, tints: dict) -> None:
    """The drawn surface is the morph mix (ID-identical) and carries the edit mesh's hidden faces and colours; the ID
    pass (the mix is the cage) and the CPU pick cache hide the same."""
    vp = app.viewport
    rm = vp.surface_render_mesh
    assert rm is not None and rm.mesh is app.morph.provider.surface_mesh
    hidden = _hidden_edit_faces(app)
    assert _dead_faces(rm) == hidden
    assert rm._tints == tints
    cage = vp.cage_mesh  # headless: no ID pass; the RenderMesh it draws from is checked directly
    assert cage is rm.mesh and _dead_faces(vp._cage_pick_render_mesh(cage)) == hidden
    assert app._pick_cache.hidden == app._hidden.vertices()


def _subd_surface_state(app):
    """(hidden derived faces, tinted derived faces, derived faces per control face) of the drawn SubD surface."""
    rm = app.viewport.surface_render_mesh
    provider = app.subdivision.provider
    assert rm is not None and rm.mesh is provider.surface_mesh
    _level, _vids, derived = provider.derived_elements()
    per_face = len(derived) // len(app.scene.mesh.all_face_ids())
    return _dead_faces(rm), set(rm._tints), per_face


# -- region colours on the morph mix (F1, F2) --------------------------------------------------------------


def test_region_colours_stay_on_the_mix_at_every_weight():
    app = _app(4)
    _group(app, _faces(app, 0, 1, 5))
    tints = dict(app.viewport.render_mesh._tints)
    assert len(tints) == 3
    lid = _target(app, 50)
    _assert_mix_shows_state(app, tints)
    app.set_morph_weight(100, lid)
    _sync(app)
    _assert_mix_shows_state(app, tints)


def test_region_colours_come_back_on_the_mix_after_zero_percent():
    """The mix mesh is kept at 0 % (a patch, not a rebuild), but its RenderMesh is released: the new one gets the
    colours again (the cache is keyed by the RenderMesh, not the surface mesh)."""
    app = _app(4)
    _group(app, _faces(app, 2, 3))
    tints = dict(app.viewport.render_mesh._tints)
    lid = _target(app, 50)
    mix = app.morph.provider.surface_mesh
    app.set_morph_weight(0, lid)
    _sync(app)
    assert app.viewport.surface_render_mesh is None and app.viewport.render_mesh._tints == tints
    app.set_morph_weight(50, lid)
    _sync(app)
    assert app.morph.provider.surface_mesh is mix  # the same surface mesh, a new RenderMesh
    _assert_mix_shows_state(app, tints)


def test_group_assign_undo_and_redo_update_the_colours_on_the_mix():
    app = _app(4)
    _target(app, 50)
    _group(app, _faces(app, 4, 5, 6))
    tints = dict(app.viewport.render_mesh._tints)
    assert len(tints) == 3
    _assert_mix_shows_state(app, tints)
    assert app.key_press(UNDO)
    _sync(app)
    _assert_mix_shows_state(app, {})
    assert app.key_press(REDO)
    _sync(app)
    _assert_mix_shows_state(app, tints)


def test_the_colour_switch_reaches_the_mix_as_draw_state_only():
    app = _app(4)
    _group(app, _faces(app, 0))
    _target(app, 50)
    rm = app.viewport.surface_render_mesh
    rows = list(rm.store.data("face_corners"))
    assert app.key_press(TINT_TOGGLE)
    _sync(app)
    assert not app.viewport.region_tint
    assert getattr(rm.store, "region_tint", False) is False
    assert list(rm.store.data("face_corners")) == rows  # nothing re-uploaded
    assert app.key_press(TINT_TOGGLE)
    _sync(app)
    assert app.viewport.region_tint


# -- hide on the morph mix --------------------------------------------------------------------------------


def test_hidden_faces_stay_hidden_across_the_weight():
    app = _app(4)
    _hide(app, _faces(app, 5))
    hidden = _hidden_edit_faces(app)
    assert hidden and _dead_faces(app.viewport.render_mesh) == hidden
    lid = _target(app, 50)
    _assert_mix_shows_state(app, {})
    for weight in (100, 0, 50):
        app.set_morph_weight(weight, lid)
        _sync(app)
        drawn = app.viewport.surface_render_mesh or app.viewport.render_mesh
        assert _dead_faces(drawn) == hidden, weight
    _assert_mix_shows_state(app, {})


def test_hide_and_show_all_on_the_mix_reach_drawing_and_picking():
    app = _app(4)
    lid = _target(app, 50)
    _hide(app, _faces(app, 10))
    _assert_mix_shows_state(app, {})
    app.set_morph_weight(0, lid)
    _sync(app)
    assert _dead_faces(app.viewport.render_mesh) == _hidden_edit_faces(app)
    app.set_morph_weight(50, lid)
    _sync(app)
    assert app.key_press(ALT_H)
    _sync(app)
    assert not app._hidden
    _assert_mix_shows_state(app, {})


# -- SubD after a Hide / Show All (F3) --------------------------------------------------------------------


def test_subd_switched_on_after_hide_hides_the_derived_faces():
    app = _app(4)
    _group(app, _faces(app, 0))
    _hide(app, _faces(app, 5))
    hidden = _hidden_edit_faces(app)
    _subd(app, True)
    dead, tinted, per_face = _subd_surface_state(app)
    assert len(dead) == len(hidden) * per_face
    assert len(tinted) == per_face


def test_subd_switched_on_after_show_all_shows_everything():
    app = _app(4)
    _subd(app, True)
    _hide(app, _faces(app, 5))
    assert _subd_surface_state(app)[0]
    _subd(app, False)
    assert app.key_press(ALT_H)
    _sync(app)
    _subd(app, True)
    assert _subd_surface_state(app)[0] == set()


def test_morph_and_subd_follow_a_hide_made_before_subd():
    app = _app(4)
    _group(app, _faces(app, 0, 1))
    lid = _target(app, 50)
    _hide(app, _faces(app, 10))
    hidden = _hidden_edit_faces(app)
    _subd(app, True)
    assert isinstance(app.viewport.surface_provider, ChainedSurface)
    dead, tinted, per_face = _subd_surface_state(app)
    assert len(dead) == len(hidden) * per_face and len(tinted) == 2 * per_face
    # picking reads the mixed cage with the same hidden set
    cage = app.viewport.cage_mesh
    assert cage is not None and _dead_faces(app.viewport._cage_pick_render_mesh(cage)) == hidden
    for weight in (100, 0, 50):  # a weight step changes no display state
        app.set_morph_weight(weight, lid)
        _sync(app)
        dead, tinted, _ = _subd_surface_state(app)
        assert len(dead) == len(hidden) * per_face and len(tinted) == 2 * per_face
    _subd(app, False)
    _assert_mix_shows_state(app, dict(app.viewport.render_mesh._tints))


def test_mix_kept_at_zero_percent_under_a_refusing_subd_shows_the_state():
    """SubD wanted but refusing the topology: the chain draws the morph stage's surface kept at 0 % - it carries the
    hidden set and the colours too (F6)."""
    app = _app()
    positions = [(float(c), float(r), 0.0) for r in range(4) for c in range(4)] + [(1.5, 1.0, 1.0)]
    quads = [[r * 4 + c, r * 4 + c + 1, (r + 1) * 4 + c + 1, (r + 1) * 4 + c] for r in range(3) for c in range(3)]
    bad = mesh_from_positions_and_faces(positions, quads + [[5, 6, 16]])  # a fin: edge 5-6 has three faces
    app.scene.mesh.load_state(bad.export_state())
    app.viewport.on_topology_changed()
    _group(app, _faces(app, 0))
    _hide(app, _faces(app, 8))
    hidden = _hidden_edit_faces(app)
    assert hidden and len(hidden) < 10
    lid = _target(app, 50)
    app.set_morph_weight(0, lid)
    _subd(app, True)
    assert app.subdivision.provider.surface_mesh is None  # refused
    rm = app.viewport.surface_render_mesh
    assert rm is not None and rm.mesh is app.morph.provider.surface_mesh
    assert _dead_faces(rm) == hidden
    assert rm._tints == app.viewport.render_mesh._tints and rm._tints


# -- the posed surface (Manu I4) ------------------------------------------------------------------------------


def test_the_posed_surface_shows_hide_and_colours_and_picking_stays_at_rest():
    app = _app(3)
    rng = random.Random(4)
    mesh = app.scene.mesh
    _bind(mesh, rng)
    app.scene.rig = _rig(mesh)
    _group(app, _faces(app, 0, 1))
    _hide(app, _faces(app, 4))
    hidden = _hidden_edit_faces(app)
    tints = dict(app.viewport.render_mesh._tints)
    app.skin.provider.set_pose({BoneId(1): _bone_pose(rng)})
    _sync(app)
    rm = app.viewport.surface_render_mesh
    assert rm is not None and rm.mesh is app.skin.provider.surface_mesh
    assert _dead_faces(rm) == hidden and rm._tints == tints
    assert app.viewport.cage_mesh is None  # picks read the rest cage (AD-028 S5), with the same hidden set
    assert _dead_faces(app.viewport.render_mesh) == hidden


# -- unchanged without a replacement surface ------------------------------------------------------------------


def test_without_a_surface_the_edit_render_mesh_is_as_before():
    app = _app(4)
    _group(app, _faces(app, 0))
    _hide(app, _faces(app, 5))
    vp = app.viewport
    assert vp.surface_provider is None and vp.surface_render_mesh is None
    assert _dead_faces(vp.render_mesh) == _hidden_edit_faces(app)
    assert vp.render_mesh._tints == dict(api.region_tints(app.scene.mesh))
