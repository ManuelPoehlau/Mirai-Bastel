"""Weight Room panel, pure logic (AD-041 §7, slice 2, `gui/weight_model.py`): headless, no pyglet, no imgui.

The panel reads `state(app)` and calls `Application`: the bone rows with the current one, the brush values, the reason
painting is refused, the symmetry text; the SPACE row (open / close, none for an eye); the actions (operation, bone,
"Aufräumen", rest / pose, symmetry) go the app's ways. The Bone panel offers "Gewichte malen …".
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401
from gui import bone_model as bm
from gui import weight_model as wm
from tests.interaction_trace import key
from tests.test_weight_room import room, screen_point, share, stroke


def test_the_state_reads_the_room_and_its_brush() -> None:
    d = room(operation="replace", value=0.4)
    app = d.app
    st = wm.state(app)
    assert st.open and not st.stroking and st.can_paint
    assert st.operation == "replace" and st.value == 0.4 and st.connected and not st.front_only
    assert [r.current for r in st.rows] == [True] and st.current_name == app.current_bone_name
    assert st.symmetry == "X" and st.symmetry_text == "Symmetrie X"
    assert st.radius_label.endswith("%")


def test_the_menu_row_and_the_bone_panel_button() -> None:
    d = room()
    app = d.app
    assert wm.menu_label(app) == wm.MENU_CLOSE
    assert wm.toggle(app) and not app.weight_room_open
    assert wm.menu_label(app) == wm.MENU_OPEN
    st = bm.state(app)
    assert not st.weight_room_open and st.weight_room_blocker is None
    assert bm.open_weight_room(app) and app.weight_room_open and bm.state(app).weight_room_open
    app.close_weight_room()
    d.tap(key("4"))
    assert "1/2/3" in bm.state(app).weight_room_blocker
    eye = app.add_eye()
    app._objects.set_edit_object(eye.id)
    app._follow_edit_object()
    assert wm.menu_label(app) is None


def test_the_actions_go_the_apps_ways() -> None:
    d = room(flow=0.15)
    app = d.app
    assert wm.set_operation(app, "smooth") and app.weight_brush.operation == "smooth"
    wm.set_operation(app, "add")
    stroke(d, *screen_point(app))
    history = len(app.history)
    assert wm.clean(app, 0.2) and len(app.history) == history + 1
    assert wm.cycle_symmetry(app) and wm.state(app).symmetry == "Y"
    after, other = app.scene.rig.with_new_bone("Kopf", (0.0, 1.0, 0.0), (0.0, 2.0, 0.0))
    app.scene.rig = after
    assert wm.choose_bone(app, other) and wm.state(app).current_name == "Kopf"
    assert not share(app)


def test_a_refused_bone_shows_its_reason() -> None:
    d = room()
    app = d.app
    after, other = app.scene.rig.with_new_bone("Wange_Links", (1.0, 0.5, 1.0), (1.5, 0.0, 1.2))
    app.scene.rig = after
    wm.choose_bone(app, other)
    st = wm.state(app)
    assert not st.can_paint and "Symmetrie" in st.blocker
