"""The Morph Lab on the app path, headless (TraceStore, no window).

Built like `run.build_app_lab`, from a scene file in a temp folder. The target is sculpted with the
app's own tools and entry points; the replacement surface (AD-013 H7) must always equal
`morph.evaluate(base, target, weight)`, through switching the edit object, Undo/Redo (Q-8), Apply
transform on the target and save/reopen. The weight keys are view state only.
"""

from __future__ import annotations

import json

import pytest

from core.selection import SelectionMode
from mirai import object_space
from mirai.interaction.input import Input

from morph_lab.lab_app import (
    LAB_KEYS,
    LabBindingConflict,
    assert_lab_keys_free,
    hud_text,
    lab_key_press,
    object_line,
    role_name,
)
from morph_lab.lab_scene import LabSceneError, backup_path, scene_path, target_name
from morph_lab.morph import MESSAGE_OFFSET, MESSAGE_TOPOLOGY, evaluate
from morph_lab.run import build_app_lab

WIDTH, HEIGHT = 800, 600
ASSET = "head_basemesh"


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


UP, DOWN, SHIFT_UP, CTRL_UP, CTRL_DOWN, M = (
    _key("up", "alt"), _key("down", "alt"), _key("up", "alt", "shift"), _key("up", "ctrl"), _key("down", "ctrl"), _key("m"),
)
ONE, FOUR, W = _key("1"), _key("4"), _key("w")
CTRL_Z, CTRL_Y, CTRL_A, SHIFT_S = _key("z", "ctrl"), _key("y", "ctrl"), _key("a", "ctrl"), _key("s", "shift")
LMB = Input("mouse", "LEFT", frozenset())


@pytest.fixture
def lab_app(tmp_path):
    app, lab, files = build_app_lab(ASSET, WIDTH, HEIGHT, scene_dir=tmp_path)
    return app, lab, files


def frame(app) -> None:
    app.viewport.sync()


def objects(app, lab):
    return app.scene.objects[lab.provider.base_id], app.scene.objects[lab.provider.target_id]


def shown(lab) -> dict:
    surface = lab.provider.surface_mesh
    return {v: surface.vertex_position(v) for v in surface.all_vertex_ids()}


def assert_surface_is_the_morph(app, lab) -> None:
    base, target = objects(app, lab)
    assert app.viewport.surface_render_mesh.mesh is lab.provider.surface_mesh
    assert shown(lab) == evaluate(base.mesh, target.mesh, lab.weight)


def press(app, lab, *inputs) -> None:
    for inp in inputs:
        lab_key_press(app, lab, inp)


def click(app, x, y, button=LMB) -> None:
    app.pointer_press(button, x, y)
    app.pointer_release("LEFT", x, y)


def screen_of(app, obj) -> tuple[float, float]:
    mesh = obj.mesh
    points = [object_space.to_world(obj, mesh.vertex_position(v)) for v in mesh.all_vertex_ids()]
    centre = tuple(sum(p[i] for p in points) / len(points) for i in range(3))
    return app.camera.project_to_screen(centre, WIDTH, HEIGHT)


def switch_to(app, lab, obj) -> None:
    """The artist's gesture (README): 4 · click the object · 1 (a plain click selects only,
    Q-12 revised 2026-10-16)."""
    app.key_press(FOUR)
    for _ in range(12):  # zoom out until the object is on screen (it starts beside the frame)
        x, y = screen_of(app, obj)
        if 20 < x < WIDTH - 20 and 20 < y < HEIGHT - 20:
            break
        app.pointer_scroll(Input("wheel", "DOWN", frozenset()))
    click(app, x, y)
    assert app.selection.objects == {obj.id}
    assert obj.state.name == "NORMAL"  # selecting never switches it to Reference
    assert role_name(lab, obj.id) in object_line(lab)
    app.key_press(ONE)
    assert app.scene.edit_object_id == obj.id


def sculpt(app, lab, delta=(0.0, 0.4, 0.15)) -> None:
    """One undoable step on the edit object (the target), through the host entry H3."""
    mesh = app.scene.mesh
    vids = sorted(mesh.all_vertex_ids())[:40]

    def mutate():
        for vid in vids:
            x, y, z = mesh.vertex_position(vid)
            mesh.set_vertex_position(vid, (x + delta[0], y + delta[1], z + delta[2]))
        return set(vids)

    assert app.apply_mesh_change("sculpt target", mutate)


def sculpted_lab(app, lab):
    base, target = objects(app, lab)
    switch_to(app, lab, target)
    sculpt(app, lab)
    switch_to(app, lab, base)
    frame(app)
    return base, target


# -- start scene ------------------------------------------------------------------------------


def test_start_scene_is_base_plus_id_identical_target(lab_app, tmp_path):
    app, lab, files = lab_app
    base, target = objects(app, lab)
    assert base.name == ASSET and target.name == target_name(ASSET)
    assert app.scene.edit_object_id == base.id
    assert target.mesh.export_state() == base.mesh.export_state()
    assert target.transform.translation[0] > 0.0 and base.transform.translation == (0.0, 0.0, 0.0)
    assert len(app.history) == 0
    assert files.current == scene_path(ASSET, tmp_path)
    assert app.viewport.surface_provider is lab.provider  # attached after the load (F-5)


def test_zero_weight_draws_the_base_itself(lab_app):
    app, lab, _ = lab_app
    frame(app)
    assert lab.weight == 0
    assert app.viewport.surface_render_mesh is None


# -- weight -----------------------------------------------------------------------------------


def test_weight_keys_show_the_morph_and_are_view_state_only(lab_app):
    app, lab, _ = lab_app
    base, target = sculpted_lab(app, lab)
    states = (base.mesh.export_state(), target.mesh.export_state())
    undo_steps = len(app.history)
    for inp, weight in ((UP, 10), (UP, 20), (SHIFT_UP, 21), (DOWN, 11), (CTRL_UP, 100), (M, 0), (M, 100),
                        (CTRL_DOWN, 0), (M, 100)):
        press(app, lab, inp)
        frame(app)
        assert lab.weight == weight
        if weight == 0:
            assert app.viewport.surface_render_mesh is None
        else:
            assert_surface_is_the_morph(app, lab)
    assert shown(lab) == {v: target.mesh.vertex_position(v) for v in target.mesh.all_vertex_ids()}
    assert (base.mesh.export_state(), target.mesh.export_state()) == states
    assert len(app.history) == undo_steps
    assert app.status_message == "Morph: Gewicht 100 %"


def test_any_path_of_weights_gives_the_same_surface(lab_app):
    import random

    app, lab, _ = lab_app
    sculpted_lab(app, lab)
    rng = random.Random(3)
    for _ in range(200):
        lab.set_weight(rng.randint(0, 100))
        frame(app)
        if lab.weight:
            assert_surface_is_the_morph(app, lab)


def test_weight_is_clamped(lab_app):
    app, lab, _ = lab_app
    press(app, lab, DOWN)
    assert lab.weight == 0
    press(app, lab, CTRL_UP, UP)
    assert lab.weight == 100


# -- sculpting the target with the app --------------------------------------------------------


def test_w_move_with_symmetry_on_the_target_reaches_the_surface(lab_app):
    app, lab, _ = lab_app
    base, target = objects(app, lab)
    switch_to(app, lab, target)
    app.key_press(SHIFT_S)  # symmetry X on the target's own mesh (object space)
    mesh, cam = app.scene.mesh, app._edit_camera
    before = mesh.export_state()
    for vid in sorted(mesh.all_vertex_ids()):
        if abs(mesh.vertex_position(vid)[0]) < 1e-3:
            continue
        sx, sy = cam.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
        app.pointer_motion(sx, sy)
        if app.selection.hovered == vid:
            break
    assert app.selection.hovered is not None
    app.key_press(W)
    app.pointer_motion(sx + 30, sy - 20, 30, -20)
    app.key_release(W)
    assert mesh.export_state() != before
    switch_to(app, lab, base)
    press(app, lab, CTRL_UP)
    frame(app)
    assert_surface_is_the_morph(app, lab)
    moved = [v for v in base.mesh.all_vertex_ids()
             if base.mesh.vertex_position(v) != target.mesh.vertex_position(v)]
    assert len(moved) >= 2  # the vertex and its mirror partner


def test_undo_of_a_target_step_jumps_to_the_target_and_the_surface_follows(lab_app):
    app, lab, _ = lab_app
    base, target = sculpted_lab(app, lab)
    press(app, lab, CTRL_UP)
    frame(app)
    sculpted = shown(lab)
    app.key_press(CTRL_Z)  # Q-8: back to the target, the sculpt step undone
    frame(app)
    assert app.scene.edit_object_id == target.id
    assert app.viewport.surface_render_mesh is None
    switch_to(app, lab, base)
    frame(app)
    assert shown(lab) == {v: base.mesh.vertex_position(v) for v in base.mesh.all_vertex_ids()}
    app.key_press(CTRL_Y)
    switch_to(app, lab, base)
    frame(app)
    assert shown(lab) == sculpted


# -- refusals and warnings --------------------------------------------------------------------


def test_topology_change_switches_off_with_one_status_and_undo_restores(lab_app):
    app, lab, _ = lab_app
    base, _target = sculpted_lab(app, lab)
    press(app, lab, UP)
    frame(app)

    def split():
        base.mesh.split_edge(sorted(base.mesh.all_edge_ids())[0])
        return None

    assert app.apply_mesh_change("split", split)
    serial = app.status_serial
    for _ in range(30):
        app.update_viewport(1 / 60)
    assert app.viewport.surface_render_mesh is None
    assert app.status_message == MESSAGE_TOPOLOGY
    assert app.status_serial == serial + 1  # once, not every frame (review F-1)
    app.key_press(CTRL_Z)
    for _ in range(3):
        app.update_viewport(1 / 60)
    assert_surface_is_the_morph(app, lab)


def test_apply_transform_on_the_target_warns_and_undo_restores(lab_app):
    app, lab, _ = lab_app
    base, target = sculpted_lab(app, lab)
    press(app, lab, CTRL_UP)
    frame(app)
    app.key_press(FOUR)
    x, y = screen_of(app, target)
    click(app, x, y)
    app.key_press(CTRL_A)  # bakes the placement into the target's positions (review F-2)
    assert target.transform.translation == (0.0, 0.0, 0.0)
    for _ in range(2):
        app.update_viewport(1 / 60)
    assert lab.provider.message == MESSAGE_OFFSET
    assert_surface_is_the_morph(app, lab)  # shows what is there - display only, no correction
    app.key_press(CTRL_Z)
    for _ in range(2):
        app.update_viewport(1 / 60)
    assert target.transform.translation[0] > 0.0
    assert lab.provider.message is None
    assert_surface_is_the_morph(app, lab)


def test_lab_keys_are_refused_while_an_interaction_owns_the_keys(lab_app):
    app, lab, _ = lab_app
    mesh = app.scene.mesh
    vid = sorted(mesh.all_vertex_ids())[0]
    app.key_press(ONE)
    app.selection.vertices = {vid}
    app.key_press(W)
    assert app.interaction_owner is not None
    assert lab_key_press(app, lab, UP) is False
    assert lab.weight == 0
    assert "ignoriert" in app.status_message
    app.key_release(W)


def test_other_keys_go_to_the_app(lab_app):
    app, lab, _ = lab_app
    lab_key_press(app, lab, FOUR)
    assert app.selection.mode is SelectionMode.OBJECT


def test_lab_keys_are_free_in_the_app_and_conflicts_abort(lab_app):
    app, _lab, _ = lab_app
    assert_lab_keys_free(app.bindings)
    app.bindings.set_default(LAB_KEYS[0].input, "Something")
    with pytest.raises(LabBindingConflict):
        assert_lab_keys_free(app.bindings)


def test_hud_names_the_edited_and_selected_object_and_the_app_status(lab_app):
    app, lab, _ = lab_app
    base, target = objects(app, lab)
    assert "Bearbeitet: Basis" in object_line(lab)
    switch_to(app, lab, target)
    assert "Bearbeitet: Ziel 1" in object_line(lab)
    app.key_press(FOUR)
    x, y = screen_of(app, base)
    click(app, x, y)
    text = hud_text(lab, ASSET)
    assert "Ausgewählt: Basis" in text and "Modus: Objekte (4)" in text
    assert "App: Object 'head_basemesh' selected - 1/2/3 edits it" in text


def test_hud_names_weight_and_the_rest_shape_hint(lab_app):
    app, lab, _ = lab_app
    sculpted_lab(app, lab)
    assert "Gewicht 0 %" in hud_text(lab, ASSET)
    press(app, lab, UP)
    frame(app)
    text = hud_text(lab, ASSET)
    assert "Gewicht 10 %" in text and "Basis-Ruhelage" in text
    app.key_press(FOUR)
    frame(app)
    assert "Basis-Ruhelage" not in hud_text(lab, ASSET)


# -- save and reopen --------------------------------------------------------------------------


def test_save_and_reopen_keeps_the_sculpted_target(lab_app, tmp_path):
    app, lab, files = lab_app
    base, target = sculpted_lab(app, lab)
    want = {v: target.mesh.vertex_position(v) for v in target.mesh.all_vertex_ids()}
    assert files.save() == scene_path(ASSET, tmp_path)

    app2, lab2, _ = build_app_lab(ASSET, WIDTH, HEIGHT, scene_dir=tmp_path)
    assert lab2.weight == 0
    lab2.set_weight(100)
    frame(app2)
    assert shown(lab2) == want
    assert_surface_is_the_morph(app2, lab2)


def test_neu_keeps_one_backup(lab_app, tmp_path):
    app, lab, files = lab_app
    sculpted_lab(app, lab)
    files.save()
    saved = scene_path(ASSET, tmp_path).read_text(encoding="utf-8")
    app2, lab2, _ = build_app_lab(ASSET, WIDTH, HEIGHT, scene_dir=tmp_path, new=True)
    assert backup_path(scene_path(ASSET, tmp_path)).read_text(encoding="utf-8") == saved
    base, target = objects(app2, lab2)
    assert target.mesh.export_state() == base.mesh.export_state()


def test_ambiguous_names_refuse_the_start(lab_app, tmp_path):
    path = scene_path(ASSET, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    extra = json.loads(json.dumps(data["objects"][0]))
    extra["id"] = data["object_id_counter"]
    data["objects"].append(extra)
    data["object_id_counter"] += 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(LabSceneError, match="--neu"):
        build_app_lab(ASSET, WIDTH, HEIGHT, scene_dir=tmp_path)


def test_broken_file_refuses_the_start(tmp_path):
    path = scene_path(ASSET, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ kein json", encoding="utf-8")
    with pytest.raises(LabSceneError, match="--neu"):
        build_app_lab(ASSET, WIDTH, HEIGHT, scene_dir=tmp_path)


# -- Left/Right switch, relative target -----------------------------------------------------------

LEFT, RIGHT = _key("comma"), _key("period")


def test_left_right_switch_the_edit_object_through_the_apps_own_gesture(lab_app):
    app, lab, _files = lab_app
    base, target = objects(app, lab)
    history = len(app.history)
    press(app, lab, RIGHT)
    assert app.scene.edit_object_id == target.id and app.selection.mode is SelectionMode.VERTEX
    assert "Ziel 1" in object_line(lab)
    press(app, lab, LEFT)
    assert app.scene.edit_object_id == base.id
    app.key_press(_key("2"))
    press(app, lab, RIGHT)
    assert app.scene.edit_object_id == target.id and app.selection.mode is SelectionMode.EDGE
    press(app, lab, RIGHT)  # already there: refused visibly, nothing changes
    assert app.scene.edit_object_id == target.id and "schon" in app.status_message
    assert len(app.history) == history  # no Undo step (Q-5)


def test_left_right_are_refused_while_an_interaction_runs(lab_app):
    app, lab, _files = lab_app
    vid = sorted(app.scene.mesh.all_vertex_ids())[0]
    app.key_press(ONE)
    app.selection.vertices = {vid}
    app.key_press(W)
    assert app.interaction_owner is not None
    assert lab_key_press(app, lab, RIGHT) is False
    assert app.scene.edit_object_id == lab.provider.base_id
    app.key_release(W)


def test_editing_the_base_after_the_target_moves_the_target_along(lab_app):
    app, lab, _files = lab_app
    base, target = sculpted_lab(app, lab)
    original = {v: base.mesh.vertex_position(v) for v in base.mesh.all_vertex_ids()}
    sculpt(app, lab, delta=(0.3, 0.0, 0.0))  # the edit object is the base again
    assert app.scene.edit_object_id == base.id
    press(app, lab, CTRL_UP)
    frame(app)
    sculpted = sorted(base.mesh.all_vertex_ids())[:40]
    for vid in sculpted:
        b, t, o = base.mesh.vertex_position(vid), target.mesh.vertex_position(vid), original[vid]
        want = tuple(bi + (ti - oi) for bi, ti, oi in zip(b, t, o))
        got = lab.provider.surface_mesh.vertex_position(vid)
        assert got == pytest.approx(want, abs=1e-9)
    assert got != pytest.approx(target.mesh.vertex_position(vid), abs=1e-6)  # not the old absolute shape


# -- Absolute/relative, base preview while the target is edited -----------------------------------

B_KEY = _key("b")


def entry_surface(app, lab):
    rm = app.viewport.entry_surface_render_meshes.get(lab.provider.base_id)
    return None if rm is None else {v: rm.mesh.vertex_position(v) for v in rm.mesh.all_vertex_ids()}


def test_base_shows_the_mixture_while_the_target_is_edited_and_up_down_morph_there(lab_app):
    app, lab, _files = lab_app
    base, target = objects(app, lab)
    press(app, lab, RIGHT)
    sculpt(app, lab)
    frame(app)
    assert entry_surface(app, lab) is None  # 0 %: the base is drawn as itself
    press(app, lab, UP, UP, UP, UP, UP)  # 50 % while sculpting the target
    frame(app)
    assert lab.weight == 50 and app.scene.edit_object_id == target.id
    assert entry_surface(app, lab) == evaluate(base.mesh, target.mesh, 50)
    sculpt(app, lab, delta=(0.0, 0.2, 0.0))  # the mixture follows each target step
    frame(app)
    assert entry_surface(app, lab) == evaluate(base.mesh, target.mesh, 50)
    assert app.viewport.surface_render_mesh is None  # the target itself is drawn as itself
    press(app, lab, LEFT)
    frame(app)
    assert entry_surface(app, lab) is None and lab.provider.surface_mesh is not None
    assert_surface_is_the_morph(app, lab)


def test_b_switches_relative_and_absolute(lab_app):
    app, lab, _files = lab_app
    base, target = sculpted_lab(app, lab)
    sculpt(app, lab, delta=(0.3, 0.0, 0.0))  # base edited after the target
    press(app, lab, CTRL_UP)
    frame(app)
    vid = sorted(base.mesh.all_vertex_ids())[0]
    relative_shape = shown(lab)[vid]
    press(app, lab, B_KEY)
    frame(app)
    assert lab.provider.relative is False and "absolut" in hud_text(lab, ASSET)
    assert shown(lab) == evaluate(base.mesh, target.mesh, 100)  # absolute: exactly the target
    assert shown(lab)[vid] == target.mesh.vertex_position(vid) != relative_shape
    press(app, lab, B_KEY)
    frame(app)
    assert lab.provider.relative is True and shown(lab)[vid] == pytest.approx(relative_shape, abs=1e-12)


def test_sent_object_becomes_base_with_an_id_identical_target(tmp_path):
    # Bridge from src/main.py (run.py --von): the sent object, not an asset, is the base.
    from core.mesh import Mesh
    from core.scene import ObjectTransform, Scene, SceneObject
    from core.ids import ObjectId
    from core.serialization import scene_to_json
    from morph_lab.lab_scene import read_sent_object, safe_file_stem

    asset = build_app_lab(ASSET, WIDTH, HEIGHT, scene_dir=tmp_path / "a")[0].scene.edit_object
    sent_obj = SceneObject(ObjectId(0), Mesh.from_state(asset.mesh.export_state()), name="Mein Kopf!",
                           transform=ObjectTransform(translation=(5.0, 0.0, 0.0)))
    sent_file = tmp_path / "sent.mirai.json"
    sent_file.write_text(scene_to_json(Scene.from_objects([sent_obj], edit_object_id=sent_obj.id,
                                                          object_id_counter=1)), encoding="utf-8")
    sent = read_sent_object(sent_file)

    app, lab, files = build_app_lab(sent[0], WIDTH, HEIGHT, scene_dir=tmp_path / "lab", sent=sent)

    base, target = objects(app, lab)
    assert base.name == "Mein Kopf!" and target.name == target_name("Mein Kopf!")
    assert base.transform.translation == (0.0, 0.0, 0.0)  # placement dropped
    assert target.mesh.export_state() == base.mesh.export_state() == asset.mesh.export_state()
    assert files.current == scene_path(safe_file_stem("Mein Kopf!"), tmp_path / "lab")

    # sending again starts over, the old file is kept once as .bak
    build_app_lab(sent[0], WIDTH, HEIGHT, scene_dir=tmp_path / "lab", sent=sent)
    assert backup_path(files.current).exists()


def test_unreadable_sent_file_is_a_lab_scene_error(tmp_path):
    from morph_lab.lab_scene import read_sent_object

    bad = tmp_path / "bad.mirai.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(LabSceneError):
        read_sent_object(bad)
