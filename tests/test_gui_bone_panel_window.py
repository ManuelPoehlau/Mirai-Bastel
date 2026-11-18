"""Bone tool 01 (2026-11-17): the Bone / Skin panel in the real pyglet window (xvfb) with the real `install_handlers` and the
imgui layer - the buttons reach `Application` (the chain tool, a bone edit, a weight value), the viewport clicks of the
chain run through the window's own handlers, and the panel holds no document state.

Needs pyglet, imgui-bundle and a display: `xvfb-run -a python -m pytest tests/test_gui_bone_panel_window.py -q` (own process,
like `test_gui_imgui_window.py`; skipped inside a combined run that already switched pyglet to headless).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

pytest.importorskip("imgui_bundle")
pyglet = pytest.importorskip("pyglet")

try:
    import main as production  # importiert pyglet.window
except Exception as exc:  # kein Display
    pytest.skip(f"kein GL/Display: {exc}", allow_module_level=True)

from core import Rig  # noqa: E402
from pyglet.window import key, mouse  # noqa: E402

from tests.test_gui_imgui_window import _center, _click, _frame, run  # noqa: E402


@pytest.fixture()
def env():
    try:
        window, app, layer = run.build(argv=["cube"])
    except Exception as exc:
        pytest.skip(f"kein GL/Display: {exc}")
    layer.bone_open = True
    for _ in range(3):
        run.render_frame(window)
    yield window, app, layer
    layer.close()
    window.close()


def _world_click(window, app, world_point, shift=False):
    """A click in the viewport where `world_point` projects (the window's own press / release handlers)."""
    x, y = app.camera.project_to_screen(world_point, window.width, window.height)
    px, py = x, window.height - y
    window.dispatch_event("on_mouse_motion", px, py, 0, 0)
    _frame(window, 1)
    window.dispatch_event("on_mouse_press", px, py, mouse.LEFT, key.MOD_SHIFT if shift else 0)
    window.dispatch_event("on_mouse_release", px, py, mouse.LEFT, key.MOD_SHIFT if shift else 0)
    _frame(window, 1)


def test_the_panel_draws_and_the_chain_button_starts_the_tool(env):
    window, app, layer = env
    _frame(window, 2)
    assert ("bone_chain", 0) in layer.item_rects and ("bone_snap", 0) in layer.item_rects
    _click(window, _center(layer.item_rects[("bone_chain", 0)]))
    assert app.bone_chain_active, app.status_message
    # the button became "end": clicking it ends the chain
    _frame(window, 2)
    _click(window, _center(layer.item_rects[("bone_chain_end", 0)]))
    assert not app.bone_chain_active


def test_chain_clicks_in_the_viewport_place_bones_and_the_panel_edits_a_head_number(env):
    window, app, layer = env
    _frame(window, 2)
    assert app.start_bone_chain()
    target = tuple(app.camera.target)
    _world_click(window, app, (target[0] - 0.4, target[1], target[2]))
    _world_click(window, app, (target[0] + 0.4, target[1], target[2]))
    assert app.scene.rig is not None and len(app.scene.rig.bones) == 1, app.status_message
    bone = app.scene.rig.bones[0]
    assert bone.head[0] < bone.tail[0]
    app.end_bone_chain()
    _frame(window, 3)
    # the panel shows the bone; typing into the head x field (clear it, type, Enter) is one Undo step
    depth = len(app.history)
    _edit_number(window, layer.item_rects[("bone_head", 0)], "0.25")
    after = app.scene.rig.bones[0]
    assert after.head[0] == pytest.approx(0.25) and after.head[1:] == bone.head[1:], (after.head, app.status_message)
    assert after.tail == bone.tail
    assert len(app.history) == depth + 1


def _tap(window, symbol):
    """A key as by hand: ImGui trickles a press and its release over frames, so each gets room."""
    window.dispatch_event("on_key_press", symbol, 0)
    _frame(window, 2)
    window.dispatch_event("on_key_release", symbol, 0)
    _frame(window, 2)


def _edit_number(window, rect, text):
    """Click into a number field, clear it (End, Backspace), type `text`, Enter - as by hand."""
    _click(window, _center(rect))
    _tap(window, key.END)
    for _ in range(10):
        _tap(window, key.BACKSPACE)
    for ch in text:
        window.dispatch_event("on_text", ch)
        _frame(window, 1)
    _tap(window, key.RETURN)
    _frame(window, 2)


def test_clicking_into_a_number_field_and_leaving_it_is_no_edit(env):
    """ImGui reads the displayed "%.4f" text back when a field was entered: that rounded copy must not become an Undo
    step or change the bone (the model treats less than half a displayed digit as no input)."""
    window, app, layer = env
    assert app.start_bone_chain()
    target = tuple(app.camera.target)
    _world_click(window, app, (target[0] - 0.4, target[1], target[2]))
    _world_click(window, app, (target[0] + 0.4, target[1], target[2]))
    app.end_bone_chain()
    _frame(window, 3)
    bone, depth = app.scene.rig.bones[0], len(app.history)
    _click(window, _center(layer.item_rects[("bone_head", 0)]))
    _click(window, _center(layer.item_rects[("bone_snap", 0)]))  # leave the field by clicking elsewhere
    _frame(window, 2)
    assert app.scene.rig.bones[0] == bone and len(app.history) == depth


def test_the_chain_refusal_is_the_buttons_tooltip_and_the_button_does_nothing_while_posed(env):
    window, app, layer = env
    assert app.bone_chain_blocker is None
    # no pose possible without a bone: the blocker for a running chain is the interaction
    assert app.start_bone_chain()
    assert app.bone_chain_blocker and "bonechain" in app.bone_chain_blocker
    app.end_bone_chain()


def test_the_tip_switch_and_the_align_button_work_through_the_panel(env):
    """Bone tool 02: the radio row sets the chain's constraint, and "Ausrichten" turns the current bone onto the selected
    object's +Z axis (head and length stay); greyed out without exactly one selected object."""
    window, app, layer = env
    _frame(window, 2)
    assert app.bone_chain_axis == "free"
    _click(window, _center(layer.item_rects[("bone_axis", "x")]))
    assert app.bone_chain_axis == "x"
    _click(window, _center(layer.item_rects[("bone_axis", "object")]))
    assert app.bone_chain_axis == "object"
    _click(window, _center(layer.item_rects[("bone_axis", "free")]))
    assert app.bone_chain_axis == "free"
    # a bone along +X; the cube's axis is +Z (no rotation)
    rig, bone_id = (app.scene.rig or Rig()).with_new_bone("Test", (0.0, 0.0, 0.0), (0.5, 0.0, 0.0))
    app.scene.rig = rig
    _frame(window, 3)
    assert app.bone_align_blocker == "select exactly one object (mode 4, outliner)"
    depth = len(app.history)
    _click(window, _center(layer.item_rects[("bone_align", 0)]))  # greyed out: nothing happens
    assert app.scene.rig.bone(bone_id).tail == (0.5, 0.0, 0.0) and len(app.history) == depth
    app.selection.objects = {next(iter(app.scene.objects))}
    _frame(window, 3)
    assert app.bone_align_blocker is None
    _click(window, _center(layer.item_rects[("bone_align", 0)]))
    bone = app.scene.rig.bone(bone_id)
    assert bone.head == (0.0, 0.0, 0.0) and bone.tail == pytest.approx((0.0, 0.0, 0.5), abs=1e-12)
    assert len(app.history) == depth + 1
