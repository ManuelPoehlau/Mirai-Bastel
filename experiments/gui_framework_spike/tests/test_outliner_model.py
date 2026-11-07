"""Panel-Logik ohne pyglet und imgui (Brief Punkt 7)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
for _p in (_ROOT / "src", _ROOT):
    sys.path.insert(0, str(_p))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mirai.application import Application  # noqa: E402
from mirai.interaction import commands  # noqa: E402

import outliner_model as om  # noqa: E402


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


def test_eye_on_visible_selects_then_hides_and_edit_object_refuses():
    app = _app()
    (tooth,) = _teeth(app, 1)
    listed = {r.object_id: r for r in om.rows(app.scene, app.selection.objects)}
    plan = om.eye_plan(listed[tooth])
    assert plan.command == commands.HIDE_OBJECTS and plan.select == frozenset({tooth})
    app.selection.objects = set(plan.select)
    assert app.dispatch_command(plan.command)
    assert app.scene.objects[tooth].hidden
    again = {r.object_id: r for r in om.rows(app.scene, app.selection.objects)}
    assert again[tooth].hidden and again[tooth].effectively_hidden
    edit = again[app.scene.edit_object_id]
    assert not edit.can_hide and om.eye_plan(edit).command is None


def test_eye_on_hidden_can_only_show_all():
    app = _app()
    a, b = _teeth(app, 2)
    app.selection.objects = {a}
    app.dispatch_command(commands.HIDE_OBJECTS)
    row = {r.object_id: r for r in om.rows(app.scene, ())}[a]
    plan = om.eye_plan(row)
    assert plan.command == commands.SHOW_ALL_OBJECTS
    assert app.dispatch_command(plan.command)
    assert not app.scene.objects[a].hidden
