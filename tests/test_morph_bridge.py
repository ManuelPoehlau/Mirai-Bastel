"""Brücke main.py -> Morph Lab (`src/morph_bridge.py`): welches Objekt gesendet wird, was
geschrieben wird, wann abgelehnt wird. Der Prozessstart ist ein Stand-in (`launcher`)."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from core.scene import ObjectState
from core.selection import SelectionMode
from core.serialization import scene_from_json
from mirai.application import Application
from mirai.interaction.input import Input
from morph_bridge import pick_object, send_to_morph_lab, write_object_scene


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    return app


def _launcher(calls):
    return lambda path: calls.append(path)


def test_sends_the_edit_object_outside_object_mode(tmp_path):
    app, calls = _app(), []

    path = send_to_morph_lab(app, tmp_path, _launcher(calls))

    assert calls == [path] and path.parent == tmp_path
    sent = scene_from_json(path.read_text(encoding="utf-8")).edit_object
    edit = app.scene.edit_object
    assert sent.name == edit.name
    assert sent.mesh.export_state() == edit.mesh.export_state()
    assert sent.mesh is not edit.mesh  # a copy: the lab never touches the production mesh


def test_object_mode_sends_the_one_selected_object(tmp_path):
    app, calls = _app(), []
    other = app.add_reference("cube")
    app.selection.mode = SelectionMode.OBJECT
    app.selection.objects.clear()
    app.selection.objects.add(other.id)

    path = send_to_morph_lab(app, tmp_path, _launcher(calls))

    assert path is not None
    assert scene_from_json(path.read_text(encoding="utf-8")).edit_object.name == other.name


def test_object_mode_needs_exactly_one_selected_object(tmp_path):
    app, calls = _app(), []
    app.selection.mode = SelectionMode.OBJECT
    app.selection.objects.clear()

    assert send_to_morph_lab(app, tmp_path, _launcher(calls)) is None
    assert calls == [] and "exactly one" in app.status_message

    app.selection.objects.update(app.scene.objects)
    if len(app.scene.objects) > 1:
        assert pick_object(app) is None


def test_refused_while_an_interaction_owns_the_keys(tmp_path):
    app, calls = _app(), []
    app.selection.vertices.add(next(iter(app.scene.mesh.all_vertex_ids())))
    app.key_press(Input("key", "w", frozenset()))
    assert app.interaction_owner is not None

    assert send_to_morph_lab(app, tmp_path, _launcher(calls)) is None
    assert calls == [] and "not while" in app.status_message
    assert list(tmp_path.iterdir()) == []


def test_a_failing_launch_is_one_status_line(tmp_path):
    app = _app()

    def boom(_path):
        raise OSError("no python")

    assert send_to_morph_lab(app, tmp_path, boom) is None
    assert "Morph Lab failed" in app.status_message


def test_resend_overwrites_and_leaves_no_tmp(tmp_path):
    app = _app()
    first = write_object_scene(app.scene.edit_object, tmp_path)
    second = write_object_scene(app.scene.edit_object, tmp_path)

    assert first == second
    assert [p.name for p in tmp_path.iterdir()] == [first.name]


def test_state_of_the_object_does_not_leak(tmp_path):
    app = _app()
    path = write_object_scene(app.scene.edit_object, tmp_path)
    assert scene_from_json(path.read_text(encoding="utf-8")).edit_object.state is ObjectState.NORMAL
