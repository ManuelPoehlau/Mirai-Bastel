"""Per-object material on the app path (AD-024 §4–§7): setters on the targets of the mode, the render
path as a uniform update only, the selection tint on a custom colour, Undo/Redo, delete/undo, save/load
(v4 and an old v3 file), the mirror copy, References and the material Look rows; plus the light drag
on a held `L` (Q-L2) and the light staying out of the Undo history (Q-L1).

Headless (`Application` with the trace viewport of `init_scene`).
"""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401

from core import ObjectMaterial, ObjectState
from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.scene_objects import REFERENCE_BASE_COLOR, SELECTED_TINT, SELECTED_TINT_SHARE, selected_color
from mirai.viewport.look_controls import MATERIAL_ROW_IDS, hsv, material_row
from viewport.gl_render_store import DEFAULT_BASE_COLOR
from viewport.material import DEFAULT_FINISH

RED = (0.8, 0.1, 0.1)
GEOMETRY = ("structural_rebuilds", "topology_updates", "vertex_updates", "geometry_uploads", "mesh_rebuilds")


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")
UP, DOWN, LEFT, RIGHT = _key("up"), _key("down"), _key("left"), _key("right")
L = _key("l")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _two_objects(app: Application):
    """The edit cube plus a second cube; both selected in mode `4`."""
    edit = app.scene.edit_object
    other = app.add_primitive("cube")
    app.selection.objects = {edit.id, other.id}
    return edit, other


def _packet(render_mesh) -> list[float]:
    return list(render_mesh.material.uniform_packet())


# -- targets and the render path ------------------------------------------------------------------


def test_component_mode_edits_the_edit_object_as_a_uniform_update_only(app):
    vp = app.viewport
    vp.sync()
    rm = vp.render_mesh
    before = dict(rm.benchmark_counters)
    assert app.set_object_material(base_color=RED, specular=0.7, glossiness=0.9) is True
    vp.sync()
    assert app.scene.edit_object.material == ObjectMaterial(RED, 0.7, 0.9)
    assert _packet(rm)[:5] == pytest.approx([*RED, 0.7, 0.9])
    after = rm.benchmark_counters
    assert after.get("material_updates", 0) == before.get("material_updates", 0) + 1
    for name in GEOMETRY:
        assert after.get(name, 0) == before.get(name, 0), name


def test_object_mode_edits_the_selected_objects_and_keeps_them_apart(app):
    edit, other = _two_objects(app)
    app.selection.objects = {other.id}
    assert app.set_object_material(base_color=RED, specular=0.9) is True
    app.selection.objects = {edit.id}
    assert app.set_object_material(base_color=(0.1, 0.2, 0.9), glossiness=0.1) is True
    assert other.material == ObjectMaterial(RED, 0.9, DEFAULT_FINISH.glossiness)
    assert edit.material == ObjectMaterial((0.1, 0.2, 0.9), DEFAULT_FINISH.specular, 0.1)
    app.selection.objects = set()
    app._objects.sync_views()
    entry = app.viewport.object_entries[other.id]
    assert _packet(entry)[:5] == pytest.approx([*RED, 0.9, DEFAULT_FINISH.glossiness])
    assert _packet(app.viewport.render_mesh)[:5] == pytest.approx([0.1, 0.2, 0.9, DEFAULT_FINISH.specular, 0.1])


def test_untouched_objects_keep_the_default_look(app):
    _, other = _two_objects(app)
    app.selection.objects = set()
    app._objects.sync_views()
    assert other.material is None
    assert _packet(app.viewport.object_entries[other.id])[:5] == pytest.approx(
        [*DEFAULT_BASE_COLOR, DEFAULT_FINISH.specular, DEFAULT_FINISH.glossiness]
    )


def test_fill_specular_stays_the_worklight_value(app):
    app.display.set_surface_finish(fill_specular=0.4)
    app._apply_display()
    app.set_object_material(specular=0.8)
    assert _packet(app.viewport.render_mesh)[3:] == pytest.approx([0.8, DEFAULT_FINISH.glossiness, 0.4])


def test_references_are_skipped_and_stay_blue(app):
    ref = app.add_reference("cube")
    ref.material = ObjectMaterial(RED, 0.9, 0.9)  # e.g. from a file: kept, not shown (Q-M3)
    app.selection.mode = app.selection.mode.OBJECT
    app.selection.objects = {ref.id}
    assert app.set_object_material(specular=0.1) is False
    assert "Reference" in app.status_message
    app.selection.objects = set()
    app._objects.sync_views()
    packet = _packet(app.viewport.object_entries[ref.id])
    assert packet[:3] == pytest.approx(list(REFERENCE_BASE_COLOR))
    assert packet[3:5] == pytest.approx([DEFAULT_FINISH.specular, DEFAULT_FINISH.glossiness])
    # mixed selection: the Normal object changes, the Reference is named as locked
    edit = app.scene.edit_object
    app.selection.objects = {ref.id, edit.id}
    assert app.set_object_material(specular=0.2) is True
    assert edit.material.specular == 0.2 and ref.material.specular == 0.9
    assert "stays (locked)" in app.status_message


def test_refused_while_a_transform_is_armed(app):
    app.selection.vertices = {next(iter(app.scene.mesh.all_vertex_ids()))}
    assert app.key_press(_key("w")) is True and app.interaction_owner == "transform"
    assert app.set_object_material(specular=0.1) is False
    assert app.scene.edit_object.material is None
    assert "not while" in app.status_message


def test_values_are_clamped_and_unknown_parameters_refused(app):
    app.set_object_material(base_color=(2.0, -1.0, 0.5), specular=3.0)
    assert app.scene.edit_object.material == ObjectMaterial((1.0, 0.0, 0.5), 1.0, DEFAULT_FINISH.glossiness)
    with pytest.raises(KeyError):
        app.set_object_material(roughness=0.5)


# -- selection highlight -------------------------------------------------------------------------------


def test_selected_tint_works_on_a_custom_colour(app):
    edit, other = _two_objects(app)
    app.selection.objects = {other.id}
    app.set_object_material(base_color=RED)
    app._objects.sync_views()
    expected = tuple(b + SELECTED_TINT_SHARE * (t - b) for b, t in zip(RED, SELECTED_TINT))
    assert selected_color(other, DEFAULT_BASE_COLOR) == pytest.approx(expected)
    assert _packet(app.viewport.object_entries[other.id])[:3] == pytest.approx(list(expected))
    app.selection.objects = set()
    app._objects.sync_highlight()
    assert _packet(app.viewport.object_entries[other.id])[:3] == pytest.approx(list(RED))


# -- Undo / Redo ------------------------------------------------------------------------------------


def test_one_undo_step_per_change_and_redo(app):
    history = len(app.history)
    app.set_object_material(base_color=RED)
    app.set_object_material(specular=0.9)
    assert len(app.history) == history + 2
    assert app.key_press(CTRL_Z) is True
    assert app.scene.edit_object.material == ObjectMaterial(RED, DEFAULT_FINISH.specular, DEFAULT_FINISH.glossiness)
    assert app.key_press(CTRL_Z) is True
    assert app.scene.edit_object.material is None
    assert _packet(app.viewport.render_mesh)[:3] == pytest.approx(list(DEFAULT_BASE_COLOR))
    assert app.key_press(CTRL_Y) is True and app.key_press(CTRL_Y) is True
    assert app.scene.edit_object.material == ObjectMaterial(RED, 0.9, DEFAULT_FINISH.glossiness)
    assert _packet(app.viewport.render_mesh)[:4] == pytest.approx([*RED, 0.9])


def test_undo_of_a_material_after_a_light_change_keeps_the_light(app):
    app.set_object_material(base_color=RED)
    app.set_light(key_azimuth=60.0)
    app.key_press(CTRL_Z)
    assert app.scene.edit_object.material is None
    assert app.display.light_rig.key_azimuth == 60.0


def test_a_deleted_object_comes_back_with_its_material(app):
    edit, other = _two_objects(app)
    app.selection.objects = {other.id}
    app.set_object_material(base_color=RED)
    assert app.key_press(_key("delete")) is True
    assert other.id not in app.scene.objects
    app.key_press(CTRL_Z)
    assert app.scene.objects[other.id].material.base_color == RED


def test_mirror_copy_takes_the_material(app):
    edit = app.scene.edit_object
    app.selection.mode = app.selection.mode.OBJECT
    app.selection.objects = {edit.id}
    app.set_object_material(base_color=RED, glossiness=0.2)
    copy = app.mirror_copy("X")
    assert copy is not None and copy.material == edit.material


# -- save / load -------------------------------------------------------------------------------------


def test_materials_survive_save_and_load(app, tmp_path):
    edit, other = _two_objects(app)
    app.selection.objects = {other.id}
    app.set_object_material(base_color=RED, specular=0.9, glossiness=0.3)
    path = tmp_path / "m.mirai.json"
    assert app.save_scene_file(path) is True
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 4
    fresh = Application()
    fresh.init_scene("cube")
    fresh.load_scene("file", scene_path=path)
    materials = sorted((obj.name, obj.material) for obj in fresh.scene.objects.values())
    assert materials == sorted([(edit.name, None), (other.name, ObjectMaterial(RED, 0.9, 0.3))])
    loaded = next(obj for obj in fresh.scene.objects.values() if obj.material is not None)
    if loaded.id != fresh.scene.edit_object_id:
        assert _packet(fresh.viewport.object_entries[loaded.id])[:5] == pytest.approx([*RED, 0.9, 0.3])


def test_an_old_v3_file_still_loads(app, tmp_path):
    path = tmp_path / "old.mirai.json"
    app.save_scene_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = 3
    for raw in data["objects"]:
        del raw["material"]
    path.write_text(json.dumps(data), encoding="utf-8")
    fresh = Application()
    fresh.init_scene("cube")
    fresh.load_scene("file", scene_path=path)
    assert all(obj.material is None for obj in fresh.scene.objects.values())


# -- material Look rows -----------------------------------------------------------------------------


def _select_row(app: Application, row_id: str) -> None:
    for _ in range(40):
        if app.look_row.id == row_id:
            return
        app.key_press(DOWN)
    raise AssertionError(row_id)


def test_material_rows_follow_the_light_rows_and_step_by_keys(app):
    app.key_press(UP)
    assert app.look_row.id == MATERIAL_ROW_IDS[-1]
    _select_row(app, "specular")
    assert app.look_text == f"Material Specular {DEFAULT_FINISH.specular:.2f} (cube)"
    assert app.key_press(RIGHT) is True
    assert app.scene.edit_object.material.specular == pytest.approx(DEFAULT_FINISH.specular + 0.05)
    assert app.key_press(_key("left", "ctrl")) is True
    assert app.scene.edit_object.material.specular == pytest.approx(DEFAULT_FINISH.specular + 0.04)
    app.key_press(CTRL_Z)
    assert app.scene.edit_object.material.specular == pytest.approx(DEFAULT_FINISH.specular + 0.05)


def test_hsv_rows_change_the_colour_each_object_from_its_own():
    red = ObjectMaterial(RED, 0.5, 0.5)
    hue = material_row("hue").step(red, 1, False)
    assert hsv(hue)[0] * 360 == pytest.approx(hsv(red)[0] * 360 + 10.0, abs=1e-3)
    assert hsv(hue)[1:] == pytest.approx(hsv(red)[1:], abs=1e-5)
    darker = material_row("value").step(red, -1, True)
    assert hsv(darker)[2] == pytest.approx(hsv(red)[2] - 0.01, abs=1e-5)
    grey = ObjectMaterial((0.5, 0.5, 0.5), 0.5, 0.5)
    assert not material_row("hue").applies(grey)
    assert material_row("saturation").step(grey, 1, False).base_color != grey.base_color


def test_hue_on_a_grey_object_is_refused_with_a_hint(app):
    app.set_object_material(base_color=(0.5, 0.5, 0.5))
    assert app.step_object_material("hue", 1) is False
    assert "Sättigung" in app.status_message


def test_relative_steps_on_two_objects_keep_their_own_values(app):
    edit, other = _two_objects(app)
    app.selection.objects = {edit.id}
    app.set_object_material(specular=0.2)
    app.selection.objects = {edit.id, other.id}
    assert app.step_object_material("specular", 1) is True
    assert edit.material.specular == pytest.approx(0.25)
    assert other.material.specular == pytest.approx(DEFAULT_FINISH.specular + 0.05)


# -- light drag (hold L, Q-L2) ----------------------------------------------------------------------


def test_l_is_the_light_drag_key():
    bs = build_default_bindings()
    assert bs.command_for(L) == cmd.LIGHT_DRAG
    assert bs.command_for(_key("l", "shift")) == cmd.EDGE_LOOP


def test_holding_l_and_moving_turns_the_key_light(app):
    rig = app.display.light_rig
    history = len(app.history)
    assert app.key_press(L) is True
    assert app.pointer_motion(400, 300, 20.0, -10.0) is True
    after = app.display.light_rig
    assert after.key_azimuth == pytest.approx(rig.key_azimuth + 10.0)
    assert after.key_elevation == pytest.approx(rig.key_elevation - 5.0)
    assert app.viewport.light_rig == after
    assert app.key_release(L) is True
    app.pointer_motion(410, 300, 20.0, 0.0)
    assert app.display.light_rig == after
    assert len(app.history) == history


def test_light_drag_waits_for_a_held_transform(app):
    app.selection.vertices = {next(iter(app.scene.mesh.all_vertex_ids()))}
    assert app.key_press(_key("w")) is True and app.interaction_owner == "transform"
    assert app.key_press(L) is False
