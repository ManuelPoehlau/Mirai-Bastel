"""Szenen speichern und laden (`src/scene_files.py`, `Application.save_scene_file`,
`Application.load_scene("file", ...)`), headless mit TraceStore.

Entscheidung Manu 2026-10-15: SPACE-Menü + `scenes/`-Ordner, Strg+S. Die Tests schreiben in
`tmp_path`, nie in den echten `scenes/`-Ordner.
"""

from __future__ import annotations

import json
import os
import time

import tests._bootstrap  # noqa: F401

from core import ObjectState, ObjectTransform
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.scene_objects import replace_scene
from mirai.symmetry_axis import current_axis, set_symmetry_axis
from core.serialization import scene_from_json, scene_to_json
from scene_files import (
    FILE_LABEL_PREFIX,
    MAX_LISTED_FILES,
    SAVE_LABEL,
    SAVE_NEW_LABEL,
    SCENE_SUFFIX,
    SceneFiles,
)

_FIXED_TIME = time.struct_time((2026, 10, 15, 14, 30, 0, 3, 288, 0))


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _files(app: Application, tmp_path) -> SceneFiles:
    return SceneFiles(app, tmp_path / "scenes", clock=lambda: _FIXED_TIME)


def _two_object_scene() -> Application:
    """Edit-Objekt mit Symmetrie und Verschiebung + eine platzierte Referenz."""
    app = _app()
    mesh = app.scene.mesh
    set_symmetry_axis(mesh, "X")
    vid = sorted(mesh.all_vertex_ids())[0]
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x, y + 0.25, z))
    ref = app.add_reference("cube", name="ref")
    ref.transform = ObjectTransform(translation=(3.0, 0.0, -1.0), scale=2.0)
    ref.pivot = (0.5, 0.0, 0.0)
    return app


def _summary(app: Application) -> list:
    scene = app.scene
    return [
        (
            obj.name,
            obj.state,
            obj.transform,
            obj.pivot,
            obj.id == scene.edit_object_id,
            obj.mesh.export_state(),
        )
        for obj in scene.objects.values()
    ]


# -- replace_scene / Application ------------------------------------------------


def test_replace_scene_keeps_the_scene_instance_and_every_object_field():
    app = _two_object_scene()
    loaded = scene_from_json(scene_to_json(app.scene))
    target = _app()
    scene, selection = target.scene, target.scene.selection

    edit = replace_scene(target.scene, loaded)

    assert target.scene is scene and target.scene.selection is selection
    assert edit is target.scene.edit_object
    assert _summary(target) == _summary(app)


def test_save_then_load_round_trips_objects_edit_object_and_symmetry(tmp_path):
    app = _two_object_scene()
    path = tmp_path / f"x{SCENE_SUFFIX}"
    expected = _summary(app)

    assert app.save_scene_file(path) is True
    assert app.status_message == f"Saved scene: {path}"
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 4  # v4 since the object material (AD-024)

    other = _app()
    other.load_scene("file", scene_path=path)

    assert _summary(other) == expected
    assert current_axis(other.scene.mesh) == "X"
    assert other.scene.objects[next(
        oid for oid in other.scene.objects if oid != other.scene.edit_object_id
    )].state is ObjectState.REFERENCE
    assert set(other.viewport.object_entries) == {
        oid for oid in other.scene.objects if oid != other.scene.edit_object_id
    }


def test_loading_a_file_resets_selection_and_history(tmp_path):
    app = _app()
    path = tmp_path / f"x{SCENE_SUFFIX}"
    app.save_scene_file(path)
    vid = sorted(app.scene.mesh.all_vertex_ids())[0]
    app.selection.set({vid})
    app.add_reference("cube")
    assert len(app.history) == 1

    app.load_scene("file", scene_path=path)

    assert len(app.history) == 0 and app.history is app.scene.history
    assert not app.selection.vertices
    assert len(app.scene.objects) == 1


def test_save_is_refused_while_a_transform_gesture_holds_the_keys(tmp_path):
    app = _app()
    app.selection.set({sorted(app.scene.mesh.all_vertex_ids())[0]})
    app.key_press(Input("key", "w", frozenset()))
    assert app.interaction_owner == "transform"
    path = tmp_path / f"x{SCENE_SUFFIX}"

    assert app.save_scene_file(path) is False

    assert not path.exists()
    assert "not while the transform interaction runs" in app.status_message


# -- SceneFiles ------------------------------------------------------------------


def test_ctrl_s_writes_a_new_file_then_overwrites_it(tmp_path):
    app = _app()
    files = _files(app, tmp_path)

    first = files.save()

    assert first == tmp_path / "scenes" / f"cube_20261015-143000{SCENE_SUFFIX}"
    assert first.is_file() and files.current == first
    app.add_reference("cube", name="ref")
    assert files.save() == first  # überschreibt die aktuelle Datei
    assert len(json.loads(first.read_text(encoding="utf-8"))["objects"]) == 2
    assert sorted(p.name for p in (tmp_path / "scenes").iterdir()) == [first.name]


def test_save_new_never_overwrites_and_avoids_name_collisions(tmp_path):
    app = _app()
    files = _files(app, tmp_path)
    first = files.save()

    second = files.save(new=True)

    assert second != first and second.name == f"cube_20261015-143000_2{SCENE_SUFFIX}"
    assert files.current == second


def test_load_sets_the_current_file_and_forget_clears_it(tmp_path):
    app = _app()
    files = _files(app, tmp_path)
    path = files.save()
    files.forget()
    assert files.current is None

    assert files.load(path) is True

    assert files.current == path
    assert app.status_message == f"Scene: {path.name}"


def test_a_broken_file_is_reported_and_leaves_the_scene_unchanged(tmp_path):
    app = _two_object_scene()
    files = _files(app, tmp_path)
    before = _summary(app)
    broken = tmp_path / f"broken{SCENE_SUFFIX}"
    broken.write_text("{not json", encoding="utf-8")

    assert files.load(broken) is False

    assert _summary(app) == before
    assert files.current is None
    assert app.status_message.startswith("Scene file 'broken.mirai.json' failed:")


def test_a_failed_save_is_reported(tmp_path, monkeypatch):
    app = _app()
    files = _files(app, tmp_path)

    def fail(path):
        raise OSError("disk full")

    monkeypatch.setattr(app, "save_scene_file", fail)

    assert files.save() is None
    assert files.current is None
    assert app.status_message == "Save scene failed: disk full"


def test_entries_list_the_actions_then_the_newest_files(tmp_path):
    app = _app()
    files = _files(app, tmp_path)
    assert files.entries() == (SAVE_LABEL, SAVE_NEW_LABEL)  # Ordner fehlt noch

    directory = tmp_path / "scenes"
    directory.mkdir()
    (directory / "notes.txt").write_text("x", encoding="utf-8")
    for index in range(MAX_LISTED_FILES + 2):
        path = directory / f"s{index:02d}{SCENE_SUFFIX}"
        path.write_text("{}", encoding="utf-8")
        os.utime(path, (1_000_000 + index, 1_000_000 + index))

    entries = files.entries()

    assert entries[:2] == (SAVE_LABEL, SAVE_NEW_LABEL)
    assert entries[2:] == tuple(
        f"{FILE_LABEL_PREFIX}s{index:02d}" for index in range(MAX_LISTED_FILES + 1, 1, -1)
    )
    assert all(files.handles(label) for label in entries)
    assert not files.handles("cube")


def test_activate_dispatches_save_save_new_and_load(tmp_path):
    app = _app()
    files = _files(app, tmp_path)
    files.entries()

    assert files.activate(SAVE_LABEL) is True
    first = files.current
    assert files.activate(SAVE_NEW_LABEL) is True
    assert files.current != first

    label = FILE_LABEL_PREFIX + first.name[: -len(SCENE_SUFFIX)]
    assert label in files.entries()
    assert files.activate(label) is True
    assert files.current == first
    assert files.activate("cube") is False


def test_shift_click_on_a_file_row_is_refused_with_a_status(tmp_path):
    app = _app()
    files = _files(app, tmp_path)

    assert files.refuse_add(SAVE_LABEL) is False

    assert len(app.scene.objects) == 1
    assert "only cube and the assets can be added as a Reference" in app.status_message
