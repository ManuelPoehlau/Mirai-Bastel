"""Bone / Skin panel, pure logic (Bone tool 01, 2026-11-17, `gui/bone_model.py`): headless, no pyglet, no imgui.

The panel reads `state(app)` and calls `Application`: the tree rows, the current bone's numbers (roll in degrees), the parent
choices without the bone and its descendants (the cycle refusal made visible), the blockers that grey the buttons, the weight
defaults - and the actions with the display-precision rule (a field read back from its "%.4f" text is no edit).
"""

from __future__ import annotations

import math

import pytest

import tests._bootstrap  # noqa: F401
from core import Bone, BoneId, Rig
from gui import bone_model as bm
from mirai.application import Application
from mirai.interaction import commands
from mirai.soft_selection import RADIUS_STEPS_PERCENT
from tests.interaction_trace import key
from tests.rig_support import E, POSE_MODE, head_driver, hold, rig_head


def _app():
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    bones = (
        Bone(BoneId(0), "Root", None, (0, 0, 0), (0, 1, 0)),
        Bone(BoneId(1), "Spine", BoneId(0), (0, 1, 0), (0, 2, 0), roll=math.radians(90.0)),
        Bone(BoneId(2), "Head", BoneId(1), (0, 2, 0), (0, 3, 0)),
        Bone(BoneId(3), "Eye L", BoneId(2), (-0.2, 2.8, 0.2), (-0.2, 2.8, 0.5)),
        Bone(BoneId(4), "Tail", BoneId(0), (0, 0, 0), (0, 0, -1)),
    )
    app.scene.rig = Rig(bones=bones, bone_id_counter=5)
    return app


def test_without_a_rig_the_panel_state_is_empty_but_the_chain_can_start() -> None:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    st = bm.state(app)
    assert not st.has_bones and st.rows == () and st.current is None and st.parent_choices == ()
    assert not st.can_edit and not st.can_weights
    assert st.chain_blocker is None and st.chain_parent_name is None and not st.chain_active and st.chain_snap


def test_the_rows_are_the_tree_with_depth_and_the_current_bone() -> None:
    app = _app()
    app.select_bone(BoneId(3))
    st = bm.state(app)
    assert [(r.name, r.depth) for r in st.rows] == [("Root", 0), ("Spine", 1), ("Head", 2), ("Eye L", 3), ("Tail", 1)]
    assert [r.name for r in st.rows if r.current] == ["Eye L"]
    assert st.count_text == "5 Knochen" and st.chain_parent_name == "Eye L"


def test_the_current_bones_numbers_and_roll_in_degrees() -> None:
    app = _app()
    app.select_bone(BoneId(1))
    cur = bm.state(app).current
    assert (cur.name, cur.parent_name, cur.head, cur.tail, cur.length) == ("Spine", "Root", (0.0, 1.0, 0.0), (0.0, 2.0, 0.0), 1.0)
    assert cur.roll_degrees == pytest.approx(90.0) and not cur.hidden
    app.set_bones_hidden([BoneId(1)], True)
    assert bm.state(app).current.hidden


def test_the_parent_choices_leave_out_the_bone_and_its_descendants() -> None:
    app = _app()
    app.select_bone(BoneId(1))  # Spine: Head and Eye L hang below it
    names = [n for _, n in bm.state(app).parent_choices]
    assert names == ["(keiner, Wurzel)", "Root", "Tail"]
    # every offered parent is accepted by the application, every other one is refused (the same rule, shown and enforced)
    for pid, _ in bm.state(app).parent_choices:
        assert bm.set_parent(app, BoneId(1), pid) or app.scene.rig.bone(BoneId(1)).parent == pid
    assert not bm.set_parent(app, BoneId(1), BoneId(3))
    assert "cycle" in app.status_message


def test_a_field_read_back_from_its_text_is_no_edit_but_a_typed_value_is() -> None:
    app = _app()
    app.select_bone(BoneId(3))
    cur = bm.state(app).current
    depth = len(app.history)
    # ImGui reads "%.4f" back: -0.2 shown as "-0.2000" comes back as -0.2 (float32: -0.20000000298...)
    assert not bm.set_head(app, cur.id, cur.head, {0: -0.20000000298023224, 1: 2.8000001907348633})
    assert len(app.history) == depth
    assert bm.set_head(app, cur.id, cur.head, {0: -0.25})
    b = app.scene.rig.bone(cur.id)
    assert b.head == (-0.25, 2.8, 0.2)  # only x changed - y and z stay exactly as stored, not the float32 copy
    assert len(app.history) == depth + 1
    assert bm.set_tail(app, cur.id, b.tail, {2: 0.9}) and app.scene.rig.bone(cur.id).tail == (-0.2, 2.8, 0.9)
    assert not bm.set_roll_degrees(app, cur.id, 0.0, 0.003)  # below half a displayed digit
    assert bm.set_roll_degrees(app, cur.id, 0.0, 45.0)
    assert app.scene.rig.bone(cur.id).roll == pytest.approx(math.radians(45.0))
    for _ in range(3):
        app.dispatch_command(commands.UNDO)
    assert app.scene.rig.bone(cur.id).head == (-0.2, 2.8, 0.2) and len(app.history) == depth


def test_merge_vec_keeps_untouched_components_bit_exact() -> None:
    cur = (0.1 + 0.2, 1.0 / 3.0, -2.5)
    assert bm.merge_vec(cur, {}) == cur
    assert bm.merge_vec(cur, {1: 7.0}) == (cur[0], 7.0, cur[2])
    assert bm.merge_vec(cur, {0: cur[0] + 4e-5}) == cur  # less than half a digit of "%.4f"
    assert bm.merge_vec(cur, {0: cur[0] + 8e-5})[0] == cur[0] + 8e-5


def test_the_blockers_that_grey_the_panel() -> None:
    d = head_driver()
    rig_head(d)
    app = d.app
    st = bm.state(app)
    assert st.chain_blocker is None and st.edit_blocker is None and st.can_edit
    d.tap(POSE_MODE)
    hold(d, E, ((30, 5), (10, 0)))
    st = bm.state(app)
    assert st.posed and not st.can_edit and st.edit_blocker.startswith("the rig is posed") and st.chain_blocker.startswith("the rig is posed")
    assert st.can_weights  # weights go in the pose too (AD-028 §7.1)
    d.tap(key("6"))
    assert app.start_bone_chain()
    st = bm.state(app)
    assert st.chain_active and st.chain_blocker == "not while the bonechain interaction runs" and not st.can_edit
    assert not st.can_weights  # nothing to weight while the chain runs


def test_the_skinning_defaults_the_selection_and_the_start_width() -> None:
    d = head_driver()
    rig_head(d)
    app = d.app
    st = bm.state(app)
    assert st.selected_points >= 1
    assert st.falloff_percent == float(RADIUS_STEPS_PERCENT[app.soft_settings.radius_step]) and not st.soft_on
    assert not st.weight_view
    assert bm.toggle_weight_view(app) and bm.state(app).weight_view
    assert bm.toggle_weight_view(app) and not bm.state(app).weight_view
    app.selection.clear()
    assert bm.state(app).selected_points == 0
    d.tap(key("4"))  # object level: no component selection
    assert bm.state(app).selected_points == 0


def test_step_bone_walks_the_bones_like_the_keys_and_skips_hidden_ones() -> None:
    app = _app()
    app.select_bone(BoneId(0))
    app.set_bones_hidden([BoneId(1)], True)
    assert bm.step_bone(app, 1) and app.current_bone == BoneId(2)  # Spine is hidden
    assert bm.step_bone(app, -1) and app.current_bone == BoneId(0)


def test_the_panel_holds_no_document_state_a_rig_edit_is_all_in_the_scene() -> None:
    """Undo through the application takes a panel edit back with nothing left over in the model: the next `state` reads it
    from the scene (the model is a pure function of `app`)."""
    app = _app()
    app.select_bone(BoneId(2))
    before = bm.state(app)
    bm.set_roll_degrees(app, BoneId(2), 0.0, 33.0)
    assert bm.state(app) != before
    app.dispatch_command(commands.UNDO)
    assert bm.state(app) == before
