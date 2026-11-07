"""Panel-Logik ohne pyglet und imgui (Brief Punkt 7)."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from gui import outliner_model as om
from mirai.application import Application
from mirai.interaction import commands


def _app():
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    app.dispatch_command(commands.SET_OBJECT_MODE)
    return app


def _teeth(app, n):
    return [app.add_primitive("cube").id for _ in range(n)]


def test_rows_indent_members_under_group_and_collapse():
    app = _app()
    a, b, c = _teeth(app, 3)
    app.selection.objects = {a, b}
    assert app.dispatch_command(commands.GROUP_OBJECTS)
    scene = app.scene
    listed = om.rows(scene, app.selection.objects)
    depths = {r.object_id: r.depth for r in listed}
    (group,) = [r for r in listed if r.is_group]
    assert depths[a] == depths[b] == 1 and depths[c] == 0 and depths[group.object_id] == 0
    idx = [r.object_id for r in listed]
    assert idx.index(a) > idx.index(group.object_id) and idx.index(b) > idx.index(group.object_id)
    assert group.selected
    folded = om.rows(scene, (), frozenset({group.object_id}))
    assert a not in [r.object_id for r in folded]


def test_click_modifiers_match_the_viewport_table():
    assert om.click_selection({1, 2}, 3, ()) == (commands.SELECT, {3})
    assert om.click_selection({1}, 3, ("shift",)) == (commands.SELECT_ADD, {1, 3})
    assert om.click_selection({1, 3}, 3, ("ctrl",)) == (commands.SELECT_REMOVE, {1})
    assert om.click_selection({1, 3}, 3, ("alt",)) == (commands.SELECT_TOGGLE, {1})
    assert om.click_selection({1}, 3, ("alt",))[1] == {1, 3}


def test_eye_hides_a_visible_object_and_refuses_the_edit_object():
    app = _app()
    (tooth,) = _teeth(app, 1)
    listed = {r.object_id: r for r in om.rows(app.scene, app.selection.objects)}
    plan = om.eye_plan(listed[tooth])
    assert plan.ids == (tooth,) and plan.hide is True
    assert app.set_objects_hidden(plan.ids, plan.hide)
    again = {r.object_id: r for r in om.rows(app.scene, app.selection.objects)}
    assert again[tooth].hidden and again[tooth].effectively_hidden
    edit = again[app.scene.edit_object_id]
    assert not edit.can_hide and om.eye_plan(edit).ids == ()


def test_eye_on_hidden_shows_just_that_object():
    app = _app()
    a, b = _teeth(app, 2)
    app.set_objects_hidden([a, b], True)
    row = {r.object_id: r for r in om.rows(app.scene, ())}[a]
    plan = om.eye_plan(row)
    assert plan.ids == (a,) and plan.hide is False
    assert app.set_objects_hidden(plan.ids, plan.hide)
    assert not app.scene.objects[a].hidden and app.scene.objects[b].hidden
