"""GUI Phase A3 (W1a, Manu 2026-11-03): the weight view - the current bone's share on the edit mesh at rest, shown in
the Soft face-shading sink through the one routing point (`Application._soft_show`), with the Soft preview off while
it is on; a running Soft or weight gesture owns the display for its lifetime, then the share returns.

Headless, in the AD-027 scenario driver on the head (`tests/rig_support.py`; the window's sink types hold their data
without a GL context). The expected share is read independently from the weights layer.
"""

from __future__ import annotations

import json

import tests._bootstrap  # noqa: F401
from hud import hud_rows, hud_state, key_hints, strip_rows
from mirai import layer_declarations as gate
from mirai.controllers.skeleton import POSE_MODE_ALLOWS
from mirai.interaction import commands
from mirai.interaction.bindings import KEYMAP_PATH
from mirai.interaction.input import GLOBAL_CONTEXT, KNIFE_CONTEXT, MORPH_CONTEXT, SUBD_CONTEXT, WINDOW_CONTEXT
from mirai.soft_selection.bands import EMPTY_BANDS
from tests.interaction_trace import CTRL_Y, CTRL_Z, ESC, HEIGHT, OVERLAYS, WIDTH, key
from tests.rig_support import (
    BONE_ADD, BONE_DELETE, BONE_NEXT, E, FALLOFF, O, POSE_MODE, POSE_TOGGLE, WEIGHT, head_driver, hold, place_pivot,
    rig_head, weights,
)
from tests.test_application_rig import MORPH_LAB_KEYS

from loaders.assets import asset_path  # (on the path through `tests.interaction_trace`)

VIEW = key("9")


def share(app, bone=None) -> dict:
    """The bone's share on the edit mesh, from the layer (independent of the app's computation)."""
    bone = app.current_bone if bone is None else bone
    out = {}
    for v, value in weights(app.scene.mesh).items():
        for k, w in value:
            if k == bone and w > 0.0:
                out[v] = w
    return out


def rows(app) -> dict:
    return {r.label: r for r in hud_rows(hud_state(app), key_hints(app.bindings))}


def weighted_head(**kw):
    d = head_driver(**kw)
    rig_head(d)
    hold(d, FALLOFF, ((40, 0),))
    assert weights(d.app.scene.mesh)
    return d


def test_the_toggle_shows_the_share_and_is_session_view_state() -> None:
    d = weighted_head()
    app = d.app
    history = len(app.history)
    assert not app.weight_view and app.soft_shading == {}
    d.tap(VIEW)
    assert app.weight_view and app.soft_shading == share(app) and app.soft_bands == EMPTY_BANDS
    assert len(app.history) == history  # no Undo step
    assert app.status_message.startswith("Weights view: Bone 1")
    row = rows(app)["Weights"]
    assert row.value == "Bone 1" and row.on and not row.quiet and row.keys == "9"
    d.tap(VIEW)
    assert not app.weight_view and app.soft_shading == {} and len(app.history) == history
    assert rows(app)["Weights"].quiet and rows(app)["Weights"].value == "off"
    assert "Weights" not in [r.label for r in strip_rows(hud_rows(hud_state(app), {}), "compact")]


def test_the_soft_preview_is_suppressed_while_on_and_returns_when_off() -> None:
    d = weighted_head()
    app = d.app
    d.tap(key("1"))
    mesh = app.scene.mesh
    app.selection.vertices = {sorted(share(app))[0]}
    app.viewport.on_selection_changed()
    d.tap(O)  # Soft on: the bands preview of the selection
    preview = app.soft_bands
    assert preview != EMPTY_BANDS
    d.tap(VIEW)
    assert app.soft_bands == EMPTY_BANDS and app.soft_shading == share(app)
    soft_row = rows(app)["Soft"]
    assert soft_row.value.endswith("preview hidden (weights view)") and soft_row.on
    # a selection change and a Soft setting step recompute nothing and keep the share
    computes = app.weight_share_computes
    app.selection.vertices = {sorted(share(app))[1]}
    app.viewport.on_selection_changed()
    app._soft_preview_refresh()
    d.tap(key("o", "shift"))  # the curve
    assert app.soft_bands == EMPTY_BANDS and app.soft_shading == share(app)
    assert app.weight_share_computes == computes
    d.tap(VIEW)  # off: the Soft preview comes back through its normal refresh
    assert app.soft_bands != EMPTY_BANDS and app.soft_shading == {}
    assert not rows(app)["Soft"].value.endswith("(weights view)")
    assert mesh is app.scene.mesh


def test_hover_changes_compute_nothing_while_on() -> None:
    d = weighted_head()
    app = d.app
    d.tap(key("1"))
    app.selection.clear()
    app.viewport.on_selection_changed()
    d.tap(O)
    d.tap(VIEW)
    shown = app.soft_shading
    computes = app.weight_share_computes
    for x, y in d.targets("vertex", visible=True, limit=6):
        d.motion(x, y)
    assert app.selection.hovered is not None
    assert app.soft_shading == shown and app.soft_bands == EMPTY_BANDS
    assert app.weight_share_computes == computes


def test_a_soft_transform_owns_the_display_and_hands_back_to_the_share() -> None:
    d = weighted_head()
    app = d.app
    d.tap(key("1"))
    app.selection.vertices = {sorted(share(app))[0]}
    app.viewport.on_selection_changed()
    d.tap(O)
    d.tap(VIEW)
    d.key_down(key("w"))
    d.nudge(12, 0)
    assert app.soft_bands != EMPTY_BANDS and app.soft_shading == {}  # the gesture's own weights, bands mode
    d.key_up("w")
    assert app.soft_bands == EMPTY_BANDS and app.soft_shading == share(app)  # the share again, not the preview
    # Esc hands back the same way
    d.key_down(key("w"))
    d.nudge(12, 0)
    d.key_down(ESC)
    d.key_up("ESCAPE")
    d.key_up("w")
    assert app.soft_bands == EMPTY_BANDS and app.soft_shading == share(app)


def test_a_weight_gesture_owns_the_display_its_commit_and_undo_redo_update_the_share() -> None:
    d = weighted_head()
    app = d.app
    d.tap(key("1"))
    seed = next(v for v, w in sorted(share(app).items()) if 0.3 < w < 1.0)
    app.selection.vertices = {seed}
    app.viewport.on_selection_changed()
    d.tap(VIEW)
    before = share(app)
    d.key_down(WEIGHT)
    d.nudge(-60, 0)
    # the gesture owns the display (its stroke: every point that had the bone at the press and its targets)
    assert app._gesture.soft_op_running and app.soft_shading == share(app) != before
    d.key_up("8")
    after = share(app)
    assert after != before and app.soft_shading == after
    d.tap(CTRL_Z)
    assert share(app) == before and app.soft_shading == before
    d.tap(CTRL_Y)
    assert app.soft_shading == after
    # Esc of a weight gesture: rolled back, the share again
    d.key_down(WEIGHT)
    d.nudge(-60, 0)
    d.key_down(ESC)
    d.key_up("ESCAPE")
    d.key_up("8")
    assert app.soft_shading == after


def test_a_current_bone_change_updates_the_share() -> None:
    d = weighted_head()
    app = d.app
    d.tap(VIEW)
    jaw = app.current_bone
    jaw_share = share(app)
    place_pivot(d, (0.0, 1.0, 0.3))
    d.tap(BONE_ADD)  # a new bone: current, no weights yet
    child = app.current_bone
    assert child != jaw and app.soft_shading == {} and rows(app)["Weights"].value == "Bone 2"
    d.tap(BONE_NEXT)  # Alt+J
    assert app.current_bone == jaw and app.soft_shading == jaw_share
    # a pick in pose mode
    d.tap(POSE_MODE)
    app.gizmo_enabled = False
    app.camera.set_view(0.9, 0.2)
    app.set_viewport_size(WIDTH, HEIGHT)
    x, y = app.camera.project_to_screen(app.scene.rig.bone(child).head, WIDTH, HEIGHT)
    d.click(x + 3, y)
    assert app.current_bone == child and app.soft_shading == {}
    tail = app.scene.rig.bone(jaw)
    near = tuple(p + 0.1 * (q - p) for p, q in zip(tail.head, tail.tail))
    x, y = app.camera.project_to_screen(near, WIDTH, HEIGHT)
    d.click(x, y)
    assert app.current_bone == jaw and app.soft_shading == jaw_share
    # Delete the jaw: its weights go to the object (no parent), the child becomes... the parent (none): last bone
    d.tap(BONE_DELETE)
    assert app.current_bone == child and app.soft_shading == share(app)
    d.tap(CTRL_Z)  # the jaw is back with its weights
    assert app.soft_shading == share(app)


def test_an_edit_object_change_updates_the_share_and_says_when_there_is_none() -> None:
    d = weighted_head(symmetric=False)
    app = d.app
    head = app.scene.edit_object
    d.tap(VIEW)
    shown = app.soft_shading
    assert shown == share(app)
    cube = app.add_primitive("cube")  # selected at object level
    d.tap(key("1"))  # Q-5: the cube becomes the edit object
    assert app.scene.edit_object is cube
    assert app.weight_view and app.soft_shading == {}
    assert rows(app)["Weights"].value == f"— (no weights on {cube.name!r})" and not rows(app)["Weights"].on
    d.tap(key("4"))
    assert rows(app)["Weights"].value == "— (object level)" and app.soft_shading == {}
    app.selection.objects = {head.id}
    d.tap(key("1"))
    assert app.scene.edit_object is head and app.soft_shading == shown


def test_nothing_to_show_without_a_rig_and_the_toggle_is_refused_at_object_level() -> None:
    d = head_driver()
    app = d.app
    d.tap(key("4"))
    d.tap(VIEW)
    assert not app.weight_view and app.status_message.startswith("Weights view: in 1/2/3")
    d.tap(key("1"))
    d.tap(VIEW)
    assert app.weight_view and app.soft_shading == {} and rows(app)["Weights"].value == "— (no rig)"
    rig_head(d)  # a bone, not bound yet
    assert rows(app)["Weights"].value.startswith("— (no weights on")
    hold(d, FALLOFF, ((40, 0),))  # bind: the first weights
    assert rows(app)["Weights"].value == "Bone 1" and app.soft_shading == share(app) != {}
    d.tap(CTRL_Z)  # unbind
    assert app.soft_shading == {} and rows(app)["Weights"].value.startswith("— (no weights on")
    d.tap(CTRL_Y)
    assert app.soft_shading == share(app) != {}


def test_a_topology_change_updates_the_share() -> None:
    d = weighted_head(symmetric=False)
    app = d.app
    d.tap(VIEW)
    mesh = app.scene.mesh
    computes = app.weight_share_computes
    d.tap(key("3"))
    face = next(f for f in sorted(mesh.all_face_ids()) if any(v in share(app) for v in mesh.face_vertices(f)))
    app.selection.faces = {face}
    app.viewport.on_selection_changed()
    d.tap(key("delete"))
    assert not mesh.is_valid_face(face), app.status_message
    assert app.weight_share_computes > computes
    assert app.soft_shading == share(app)
    assert all(mesh.is_valid_vertex(v) for v in app.soft_shading)
    d.tap(CTRL_Z)
    assert mesh.is_valid_face(face) and app.soft_shading == share(app)


def test_the_target_editing_view_shows_no_share() -> None:
    d = weighted_head()
    app = d.app
    d.tap(VIEW)
    shown = app.soft_shading
    d.tap(key("n", "ctrl"))
    d.tap(key("tab"))
    assert app.morph_editing_target_name is not None, app.status_message
    assert app.soft_shading == {} and rows(app)["Weights"].value == "— (target view)"
    d.tap(key("tab"))
    assert app.morph_editing_target_name is None and app.soft_shading == shown


def test_posed_the_shading_sits_on_the_posed_surface() -> None:
    d = weighted_head()
    app = d.app
    d.tap(VIEW)
    d.tap(POSE_MODE)
    app.camera.set_view(0.6, 0.15)
    app.update_viewport(0)
    hold(d, E, ((0, 60), (0, 40)))
    assert app.posed
    assert rows(app)["Weights"].value == "Bone 1" and app.soft_shading == share(app)  # pose mode shows it too
    surface = app.skin.provider.surface_mesh
    overlay = app._soft_shading_overlay
    posed = {tuple(surface.vertex_position(v)) for v in surface.all_vertex_ids()}
    flat = overlay.triangles()
    points = {tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)}
    moved = {tuple(surface.vertex_position(v)) for v in app.soft_shading} - {
        tuple(app.scene.mesh.vertex_position(v)) for v in app.soft_shading
    }
    assert points and points <= posed and points & moved
    # a further pose step moves the shading with it (the cage watch), without a recompute of the share
    computes = app.weight_share_computes
    hold(d, E, ((0, 30),))
    flat2 = overlay.triangles()
    assert flat2 != flat and {tuple(flat2[i:i + 3]) for i in range(0, len(flat2), 3)} <= {
        tuple(surface.vertex_position(v)) for v in surface.all_vertex_ids()
    }
    assert app.weight_share_computes == computes
    d.tap(POSE_TOGGLE)  # rest: back on the rest cage
    app.update_viewport(0)
    mesh = app.scene.mesh
    rest = {tuple(mesh.vertex_position(v)) for v in mesh.all_vertex_ids()}
    flat3 = overlay.triangles()
    assert {tuple(flat3[i:i + 3]) for i in range(0, len(flat3), 3)} <= rest


def test_a_scene_load_keeps_the_view_on_and_shows_the_loaded_share(tmp_path) -> None:
    d = weighted_head()
    app = d.app
    place_pivot(d, (0.0, 1.0, 0.3))
    d.tap(BONE_ADD)  # current: the second bone (no weights)
    path = tmp_path / "rigged.json"
    assert app.save_scene_file(path)
    d.tap(VIEW)
    assert app.soft_shading == {}
    app.init_scene("obj", obj_path=asset_path("head_basemesh"), **OVERLAYS)
    assert app.weight_view and app.soft_shading == {} and rows(app)["Weights"].value == "— (no rig)"
    app.load_scene("file", scene_path=path, **OVERLAYS)
    # a load starts with no chosen bone: the rig's last one - the one the HUD names is the one shown
    assert app.weight_view and rows(app)["Weights"].value == app.current_bone_name
    assert app.soft_shading == share(app)
    d.tap(BONE_NEXT)
    assert app.soft_shading == share(app) != {}
    # loaded again while the first bone is the chosen one: the load chooses none, so the last bone shows
    assert app.current_bone_name == "Bone 1"
    app.init_scene("file", scene_path=path, **OVERLAYS)
    assert app.current_bone_name == "Bone 2" and app.soft_shading == share(app) == {}


def test_set_edit_object_alone_updates_the_view() -> None:
    """The one place that changes the edit object (`ObjectController.set_edit_object`) updates the view itself, also
    for a caller that leaves the Soft preview refresh out."""
    d = weighted_head(symmetric=False)
    app = d.app
    head = app.scene.edit_object
    d.tap(VIEW)
    shown = app.soft_shading
    cube = app.add_primitive("cube")
    d.tap(key("1"))
    app._objects.set_edit_object(head.id)
    assert app.soft_shading == shown
    app._objects.set_edit_object(cube.id)
    assert app.soft_shading == {}


def test_the_key_is_free_and_the_command_only_shows() -> None:
    d = head_driver()
    bindings = d.app.bindings
    (inp,) = [i for i in bindings.inputs_for(commands.WEIGHT_VIEW_TOGGLE) if i.kind == "key"]
    assert (inp.value, inp.modifiers) == ("9", frozenset())
    keymap = json.loads(KEYMAP_PATH.read_text(encoding="utf-8"))
    taken = {(e["input"]["value"], tuple(sorted(e["input"]["modifiers"]))) for e in keymap["bindings"]}
    assert ("9", ()) not in taken and ("9", ()) not in MORPH_LAB_KEYS
    assert bindings.command_for(inp, GLOBAL_CONTEXT) == commands.WEIGHT_VIEW_TOGGLE
    for context in (KNIFE_CONTEXT, SUBD_CONTEXT, MORPH_CONTEXT, WINDOW_CONTEXT):
        assert bindings.command_for(inp, context) in (None, commands.WEIGHT_VIEW_TOGGLE), context
    assert gate.COMMAND_CLASSES[commands.WEIGHT_VIEW_TOGGLE] == gate.NON_MESH
    assert commands.WEIGHT_VIEW_TOGGLE in POSE_MODE_ALLOWS
    assert commands.WEIGHT_VIEW_TOGGLE not in commands.RIG_COMMANDS
