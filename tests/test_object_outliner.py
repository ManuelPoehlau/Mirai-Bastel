"""Objekt-Verwaltung ohne Panel (Outliner 2026-11-07): Ausblenden, Duplizieren, Gruppen, Datei-Roundtrip."""

from __future__ import annotations

import json

import tests._bootstrap  # noqa: F401

import pytest

from core import ObjectState
from mirai.application import Application
from mirai.interaction import commands


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _with_teeth(app: Application, count: int = 3):
    """The edit cube plus `count` extra cubes (the teeth), all Normal; returns their ids."""
    ids = []
    for _ in range(count):
        ids.append(app.add_primitive("cube").id)
    return ids


def _select(app: Application, *ids) -> None:
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = set(ids)


def _run(app: Application, command: str) -> bool:
    return app.dispatch_command(command)


def test_hide_removes_from_selection_draw_and_pick_and_undo_restores():
    app = _app()
    (tooth,) = _with_teeth(app, 1)
    _select(app, tooth)
    assert _run(app, commands.HIDE_OBJECTS)
    assert app.scene.objects[tooth].hidden is True
    assert tooth not in app.selection.objects
    assert tooth not in app.viewport.object_entries
    _run(app, commands.UNDO)
    assert app.scene.objects[tooth].hidden is False
    assert tooth in app.viewport.object_entries


def test_edit_object_cannot_be_hidden():
    app = _app()
    _with_teeth(app, 1)
    _select(app, app.scene.edit_object_id)
    assert _run(app, commands.HIDE_OBJECTS) is False
    assert app.scene.edit_object.hidden is False


def test_isolate_and_show_all():
    app = _app()
    a, b, c = _with_teeth(app, 3)
    _select(app, a)
    assert _run(app, commands.ISOLATE_OBJECTS)
    assert not app.scene.objects[a].hidden and app.scene.objects[b].hidden and app.scene.objects[c].hidden
    assert not app.scene.edit_object.hidden
    assert _run(app, commands.SHOW_ALL_OBJECTS)
    assert not any(obj.hidden for obj in app.scene.objects.values())


def test_group_moves_hides_and_undoes_as_a_unit():
    app = _app()
    a, b, c = _with_teeth(app, 3)
    _select(app, a, b)
    assert _run(app, commands.GROUP_OBJECTS)
    (group,) = [o for o in app.scene.objects.values() if o.state is ObjectState.GROUP]
    assert app.scene.objects[a].parent == group.id == app.scene.objects[b].parent
    assert app.scene.objects[c].parent is None
    assert app.selection.objects == {group.id}

    assert _run(app, commands.HIDE_OBJECTS)  # hiding the group hides both members
    assert app.scene.is_hidden(a) and app.scene.is_hidden(b) and not app.scene.is_hidden(c)
    assert a not in app.viewport.object_entries and group.id not in app.viewport.object_entries
    _run(app, commands.UNDO)
    assert not app.scene.is_hidden(a)

    _run(app, commands.UNDO)  # undo the grouping
    assert group.id not in app.scene.objects
    assert app.scene.objects[a].parent is None


def test_group_pick_never_returns_the_group():
    app = _app()
    a, b = _with_teeth(app, 2)
    _select(app, a, b)
    _run(app, commands.GROUP_OBJECTS)
    (group,) = [o for o in app.scene.objects.values() if o.state is ObjectState.GROUP]
    assert group.id not in app.viewport.object_entries
    assert app._objects.highlighted() == {a, b}


def test_ungroup_dissolves_and_a_member_can_leave():
    app = _app()
    a, b, c = _with_teeth(app, 3)
    _select(app, a, b, c)
    _run(app, commands.GROUP_OBJECTS)
    (group,) = [o for o in app.scene.objects.values() if o.state is ObjectState.GROUP]
    _select(app, a)
    assert _run(app, commands.UNGROUP_OBJECTS)  # a leaves
    assert app.scene.objects[a].parent is None and app.scene.objects[b].parent == group.id
    _select(app, group.id)
    assert _run(app, commands.UNGROUP_OBJECTS)  # dissolve
    assert group.id not in app.scene.objects
    assert app.scene.objects[b].parent is None
    _run(app, commands.UNDO)
    assert group.id in app.scene.objects and app.scene.objects[b].parent == group.id


def test_select_group_selects_the_group_of_a_member():
    app = _app()
    a, b = _with_teeth(app, 2)
    _select(app, a, b)
    _run(app, commands.GROUP_OBJECTS)
    (group,) = [o for o in app.scene.objects.values() if o.state is ObjectState.GROUP]
    _select(app, a)
    assert _run(app, commands.SELECT_OBJECT_GROUP)
    assert app.selection.objects == {group.id}


def test_duplicate_copies_mesh_independently_and_selects_the_copy():
    app = _app()
    (tooth,) = _with_teeth(app, 1)
    app.scene.objects[tooth].name = "Tooth"
    _select(app, tooth)
    before = len(app.scene.objects)
    assert _run(app, commands.DUPLICATE_OBJECTS)
    assert len(app.scene.objects) == before + 1
    (copy_id,) = app.selection.objects
    copy = app.scene.objects[copy_id]
    assert copy_id != tooth and copy.name == "Tooth.001"
    assert copy.mesh is not app.scene.objects[tooth].mesh
    assert copy.mesh.all_vertex_ids() == app.scene.objects[tooth].mesh.all_vertex_ids()
    _run(app, commands.UNDO)
    assert copy_id not in app.scene.objects


def test_duplicate_group_copies_members_into_the_copy():
    app = _app()
    a, b = _with_teeth(app, 2)
    _select(app, a, b)
    _run(app, commands.GROUP_OBJECTS)
    (group,) = [o for o in app.scene.objects.values() if o.state is ObjectState.GROUP]
    before = len(app.scene.objects)
    assert _run(app, commands.DUPLICATE_OBJECTS)
    assert len(app.scene.objects) == before + 3
    (new_group_id,) = app.selection.objects
    new_group = app.scene.objects[new_group_id]
    assert new_group.state is ObjectState.GROUP and new_group.id != group.id
    assert len(app.scene.children_of(new_group_id)) == 2
    assert {o.id for o in app.scene.children_of(group.id)} == {a, b}
    _run(app, commands.UNDO)  # one step removes the whole copy
    assert len(app.scene.objects) == before


def test_delete_group_deletes_members_and_undo_restores_them():
    app = _app()
    a, b = _with_teeth(app, 2)
    _select(app, a, b)
    _run(app, commands.GROUP_OBJECTS)
    (group,) = [o for o in app.scene.objects.values() if o.state is ObjectState.GROUP]
    assert _run(app, commands.DELETE)
    for oid in (a, b, group.id):
        assert oid not in app.scene.objects
    _run(app, commands.UNDO)
    assert {a, b, group.id} <= set(app.scene.objects)
    assert app.scene.objects[a].parent == group.id


def test_file_roundtrip_keeps_groups_hidden_and_parents(tmp_path):
    app = _app()
    a, b, c = _with_teeth(app, 3)
    _select(app, a, b)
    _run(app, commands.GROUP_OBJECTS)
    _select(app, c)
    _run(app, commands.HIDE_OBJECTS)
    path = tmp_path / "s.mirai.json"
    assert app.save_scene_file(path)
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 8

    fresh = _app()
    fresh.load_scene("file", scene_path=path)
    groups = [o for o in fresh.scene.objects.values() if o.state is ObjectState.GROUP]
    assert len(groups) == 1
    members = fresh.scene.children_of(groups[0].id)
    assert len(members) == 2
    assert sum(1 for o in fresh.scene.objects.values() if o.hidden) == 1
    hidden = next(o for o in fresh.scene.objects.values() if o.hidden)
    assert hidden.id not in fresh.viewport.object_entries


def test_bad_hierarchy_in_a_file_is_rejected():
    from core.serialization import scene_from_dict, scene_to_dict

    app = _app()
    (a,) = _with_teeth(app, 1)
    data = scene_to_dict(app.scene)
    data["version"] = 8
    for raw in data["objects"]:
        if raw["id"] == a:
            raw["parent"] = raw["id"]  # parent is itself / not a group
    with pytest.raises(ValueError):
        scene_from_dict(data)


def test_a_selected_group_is_what_the_object_gesture_moves():
    app = _app()
    a, b, c = _with_teeth(app, 3)
    _select(app, a, b)
    _run(app, commands.GROUP_OBJECTS)
    targets, references = app._objects.targets("Object Move", "")
    assert [o.id for o in targets] == [a, b] and references == ()


def test_hidden_objects_are_not_pickable_and_groups_never_are():
    app = _app()
    a, b = _with_teeth(app, 2)
    scene = app.scene
    pickable = lambda: {  # noqa: E731 - the objects the picker would consider
        oid for oid, obj in scene.objects.items() if obj.state is not ObjectState.GROUP and not scene.is_hidden(oid)
    }
    assert {a, b} <= pickable()
    _select(app, a)
    _run(app, commands.HIDE_OBJECTS)
    assert a not in pickable()


def test_duplicate_is_refused_for_a_mesh_with_point_layers():
    from core.mesh import LayerKind, PointLayerInfo

    app = _app()
    (tooth,) = _with_teeth(app, 1)
    app.scene.objects[tooth].mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    _select(app, tooth)
    before = len(app.scene.objects)
    assert _run(app, commands.DUPLICATE_OBJECTS) is False
    assert len(app.scene.objects) == before


def test_hide_and_group_keys_act_on_objects_in_mode_4_and_on_components_otherwise():
    app = _app()
    a, b = _with_teeth(app, 2)
    _select(app, a, b)
    assert app.dispatch_command(commands.REGION_NEW)  # Ctrl+G in mode 4 = group the objects
    (group,) = [o for o in app.scene.objects.values() if o.state is ObjectState.GROUP]
    assert app.scene.objects[a].parent == group.id
    assert app.dispatch_command(commands.HIDE_SELECTION)  # Ctrl+H in mode 4 = hide the object selection
    assert app.scene.is_hidden(a)
    assert app.dispatch_command(commands.SHOW_ALL)
    assert not app.scene.is_hidden(a)
    app.dispatch_command(commands.SET_VERTEX_MODE)
    app.dispatch_command(commands.HIDE_SELECTION)  # component hide: the objects stay as they are
    assert not any(o.hidden for o in app.scene.objects.values())


# -- Panel entries (AD-030): by id, not by the object selection -------------------------------------------------


def test_set_objects_hidden_by_id_hides_shows_and_undoes_without_touching_other_selection():
    app = _app()
    a, b = _with_teeth(app, 2)
    _select(app, a)
    assert app.set_objects_hidden([b], True)
    assert app.scene.objects[b].hidden and not app.scene.objects[a].hidden
    assert app.selection.objects == {a}
    assert app.set_objects_hidden([b], True) is False  # already hidden
    assert app.set_objects_hidden([b], False)
    assert not app.scene.objects[b].hidden
    app.dispatch_command(commands.UNDO)
    assert app.scene.objects[b].hidden
    app.dispatch_command(commands.UNDO)
    assert not app.scene.objects[b].hidden


def test_set_objects_hidden_refuses_edit_object_and_hiding_drops_selection():
    app = _app()
    (tooth,) = _with_teeth(app, 1)
    assert app.set_objects_hidden([app.scene.edit_object_id], True) is False
    _select(app, tooth)
    assert app.set_objects_hidden([tooth], True)
    assert tooth not in app.selection.objects


def test_set_objects_hidden_group_follows_members_and_show_restores():
    app = _app()
    a, b, c = _with_teeth(app, 3)
    _select(app, a, b)
    _run(app, commands.GROUP_OBJECTS)
    (group,) = [o for o in app.scene.objects.values() if o.state is ObjectState.GROUP]
    assert app.set_objects_hidden([group.id, a], True)  # a rides along with its group
    assert app.scene.is_hidden(a) and app.scene.is_hidden(b) and not app.scene.is_hidden(c)
    assert app.set_objects_hidden([group.id], False)
    assert not app.scene.is_hidden(a)


def test_select_objects_only_in_object_mode_and_skips_hidden():
    app = _app()
    a, b = _with_teeth(app, 2)
    app.selection.objects = set()
    app.dispatch_command(commands.SET_VERTEX_MODE)  # nothing selected: the edit object stays the cube
    assert app.select_objects([a]) is False
    _select(app, b)
    assert app.set_objects_hidden([b], True)
    assert app.select_objects([a, b]) is True
    assert app.selection.objects == {a}
    assert app.select_objects([a]) is False  # no change
    assert app.select_objects([]) is True and app.selection.objects == set()


def test_ctrl_c_ctrl_v_pastes_independent_copies_and_each_paste_is_one_undo_step():
    from mirai.interaction.input import Input
    from mirai.interaction.bindings import build_default_bindings

    bindings = build_default_bindings()
    assert bindings.command_for(Input("key", "c", frozenset({"ctrl"}))) == commands.COPY_OBJECTS
    assert bindings.command_for(Input("key", "v", frozenset({"ctrl"}))) == commands.PASTE_OBJECTS

    app = _app()
    (tooth,) = _with_teeth(app, 1)
    _select(app, tooth)
    before = len(app.scene.objects)
    assert _run(app, commands.COPY_OBJECTS)
    assert len(app.scene.objects) == before  # copying changes nothing
    assert _run(app, commands.PASTE_OBJECTS) and _run(app, commands.PASTE_OBJECTS)
    assert len(app.scene.objects) == before + 2
    _run(app, commands.UNDO)
    assert len(app.scene.objects) == before + 1


def test_paste_without_copy_or_outside_mode_4_is_refused_and_a_deleted_source_is_skipped():
    app = _app()
    (tooth,) = _with_teeth(app, 1)
    assert _run(app, commands.PASTE_OBJECTS) is False  # nothing copied
    _select(app, tooth)
    _run(app, commands.COPY_OBJECTS)
    _run(app, commands.DELETE)  # the source is gone
    assert _run(app, commands.PASTE_OBJECTS) is False
    app.dispatch_command(commands.SET_VERTEX_MODE)
    assert _run(app, commands.PASTE_OBJECTS) is False
