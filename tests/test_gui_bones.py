"""Outliner und Knochen (AD-030): Auswahl, Umbenennen, Ein-/Ausblenden (gespeichert, mit Undo)."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from core import Bone, BoneId, Rig
from mirai.application import Application
from mirai.interaction import commands


def _app_with_bones():
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    bones = (
        Bone(BoneId(0), "Root", None, (0, 0, 0), (0, 1, 0)),
        Bone(BoneId(1), "Spine", BoneId(0), (0, 1, 0), (0, 2, 0)),
        Bone(BoneId(2), "Head", BoneId(1), (0, 2, 0), (0, 3, 0)),
    )
    app.scene.rig = Rig(bones=bones, bone_id_counter=3)
    return app, [b.id for b in bones]


def test_select_bone_sets_current_and_ignores_unknown():
    app, (root, spine, head) = _app_with_bones()
    assert app.select_bone(spine) is True
    assert app._skeleton.current_bone == spine
    assert app.select_bone(spine) is False
    assert app.select_bone(BoneId(99)) is False


def test_rename_bone_by_id_is_undoable_and_names_stay_unique():
    app, (root, spine, head) = _app_with_bones()
    assert app.rename_bone(spine, " Wirbel ") is True
    assert app.scene.rig.bone(spine).name == "Wirbel"
    assert app.rename_bone(head, "Root") is False  # taken
    assert app.rename_bone(head, "") is False
    assert app.rename_bone(BoneId(99), "X") is False
    app.dispatch_command(commands.UNDO)
    assert app.scene.rig.bone(spine).name == "Spine"


def test_hidden_bones_are_not_drawn_picked_or_stepped_to():
    app, (root, spine, head) = _app_with_bones()
    sk = app._skeleton
    full = len(sk.bone_items(app.camera, 1.0))
    assert app.set_bones_hidden([spine], True) is True
    assert app.set_bones_hidden([spine], True) is False  # no change
    assert sk.hidden == {spine}
    assert len(sk.bone_items(app.camera, 1.0)) == full - 2  # a line and a cross per bone
    app.select_bone(root)
    sk.step_bone(1)
    assert sk.current_bone == head  # Spine skipped
    assert app.set_bones_hidden([spine], False) is True
    assert len(sk.bone_items(app.camera, 1.0)) == full
    app.set_bones_hidden([root, spine, head], True)
    before = sk.current_bone
    assert sk.step_bone(1) is False and sk.current_bone == before


def test_hiding_a_bone_is_one_undo_step_and_survives_a_rename_and_a_delete():
    app, (root, spine, head) = _app_with_bones()
    depth = len(app.history)
    app.set_bones_hidden([spine], True)
    assert len(app.history) == depth + 1
    app.rename_bone(spine, "Wirbel")
    assert app.scene.rig.bone(spine).hidden and app.scene.rig.bone(spine).name == "Wirbel"
    app.dispatch_command(commands.UNDO)
    app.dispatch_command(commands.UNDO)
    assert app._skeleton.hidden == frozenset()
    app.dispatch_command(commands.REDO)
    assert app._skeleton.hidden == {spine}
    app.select_bone(root)
    app.dispatch_command(commands.BONE_DELETE)  # the root goes: its child Spine keeps its hidden flag
    assert app.scene.rig.bone(spine).hidden


def test_bone_visibility_is_saved_with_the_scene_and_old_files_still_load(tmp_path):
    from core.serialization import scene_from_dict, scene_to_dict

    app, (root, spine, head) = _app_with_bones()
    plain = scene_to_dict(app.scene)
    assert plain["version"] == 7 and all("hidden" not in b for b in plain["rig"]["bones"])  # unchanged file
    app.set_bones_hidden([spine], True)
    raw = scene_to_dict(app.scene)
    assert raw["version"] == 8
    assert [b.get("hidden") for b in raw["rig"]["bones"]] == [None, True, None]
    again = scene_from_dict(raw)
    assert again.rig.hidden_ids() == {spine}
    assert scene_from_dict(plain).rig.hidden_ids() == frozenset()
