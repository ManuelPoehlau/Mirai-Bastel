"""AD-037 Phase 3: several paint layers and the Multiply blend (P-12, Manu 2026-11-19: "Normal + Multiply").

Pinned: the composite's Multiply arithmetic; every layer change (add, delete, rename, move, opacity / visibility / blend,
merge down, clear) is one Undo step and Undo / Redo restore stack and pixels exactly; merge down keeps the composite (both
blends, opacities baked in) and refuses what one layer cannot hold; a name used again never finds another layer's
pixels; strokes paint on the active layer, not on a hidden one; the held opacity slider previews without a step; the
display re-composites only painted tiles on a layer change and equals a whole composite; save / load keeps every layer
and its blend; the panel model.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import PaintLayer, PaintStack
from mirai.application import Application
from mirai.interaction import commands
from mirai.paint import layers as layers_api
from mirai.paint.store import PaintStore, merge_pixels

from tests.test_paint_room import _app, _stroke


@pytest.fixture()
def app():
    app = _app()
    app.set_paint_resolution(1024)
    app.open_paint_room()
    _stroke(app)
    return app


def _undo(app):
    app.dispatch_command(commands.UNDO)


def _redo(app):
    app.dispatch_command(commands.REDO)


def _names(obj):
    return [layer.name for layer in obj.paint.layers]


def _shown(app, obj):
    """What the viewport shows for `obj` after this frame's updates."""
    display = app.paint_display
    display.texture(obj)
    display.update()
    return display._entries[id(obj)].composite.copy()


def _whole(app, obj):
    return app.paint.composite(obj, app.paint_display._entries[id(obj)].base)


# -- the composite ------------------------------------------------------------------------------------------------------


def test_multiply_darkens_by_the_layer_colour_and_normal_covers():
    store = PaintStore()  # the store reads only `paint` and `name` of an object
    rng = np.random.default_rng(3)
    base = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)
    pixels = rng.integers(0, 256, (8, 8, 4), dtype=np.uint8)

    class Obj:
        name = "o"
        paint = PaintStack(8, 8, (PaintLayer("m", None, opacity=0.6, blend="multiply"),))

    o = Obj()
    store.set_pixels(o, "m", pixels)
    got = store.composite(o, base)[..., :3].astype(np.float64)
    t, c, a = base[..., :3].astype(np.float64), pixels[..., :3].astype(np.float64), pixels[..., 3:4] / 255.0 * 0.6
    assert np.abs(got - (t + (t * c / 255.0 - t) * a)).max() <= 0.5 + 1e-6
    white = pixels.copy()
    white[..., :3] = 255
    store.set_pixels(o, "m", white)
    assert np.array_equal(store.composite(o, base)[..., :3], base[..., :3])  # white multiplies to no change


@pytest.mark.parametrize("blend", ["normal", "multiply"])
def test_merge_pixels_composites_like_the_two_layers(blend):
    rng = np.random.default_rng(7)
    base = rng.integers(0, 256, (32, 32, 4), dtype=np.uint8)
    upper = rng.integers(0, 256, (32, 32, 4), dtype=np.uint8)
    lower = rng.integers(0, 256, (32, 32, 4), dtype=np.uint8)
    upper[:4, :, 3] = 0
    lower[:, :4, 3] = 0
    store = PaintStore()

    class Two:
        name = "o"
        paint = PaintStack(32, 32, (PaintLayer("l", None, opacity=0.7, blend=blend),
                                    PaintLayer("u", None, opacity=0.4, blend=blend)))

    class One:
        name = "o"
        paint = PaintStack(32, 32, (PaintLayer("l", None, blend=blend),))

    two, one = Two(), One()
    store.set_pixels(two, "l", lower)
    store.set_pixels(two, "u", upper)
    store.set_pixels(one, "l", merge_pixels(upper, 0.4, lower, 0.7, blend))
    diff = np.abs(store.composite(two, base).astype(int) - store.composite(one, base))
    assert diff.max() <= 2 and diff.mean() < 0.5


# -- layer steps --------------------------------------------------------------------------------------------------------


def test_add_paints_on_the_new_layer_and_undo_redo_restore_exactly(app):
    obj = app.scene.edit_object
    first = app.paint.pixels(obj, "Ebene 1").copy()
    history = len(app.history)
    assert app.add_paint_layer() and _names(obj) == ["Ebene 1", "Ebene 2"]
    assert app.paint_active_layer == "Ebene 2" and len(app.history) == history + 1
    app.set_paint_brush(colour=(0.0, 0.0, 1.0))
    _stroke(app, dx=-3.0)
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), first)  # the stroke went to the active layer
    second = app.paint.pixels(obj, "Ebene 2").copy()
    assert second[..., 3].any()
    _undo(app)
    _undo(app)
    assert _names(obj) == ["Ebene 1"] and app.paint_active_layer == "Ebene 1"
    _redo(app)
    _redo(app)
    assert _names(obj) == ["Ebene 1", "Ebene 2"] and np.array_equal(app.paint.pixels(obj, "Ebene 2"), second)


def test_delete_rename_move_and_values_are_one_step_each(app):
    obj = app.scene.edit_object
    app.add_paint_layer()
    _stroke(app, dx=-3.0)
    pixels = app.paint.pixels(obj, "Ebene 2").copy()
    steps = [
        (lambda: app.set_paint_layer("Ebene 2", opacity=0.25), lambda: obj.paint.layers[1].opacity == 0.25),
        (lambda: app.set_paint_layer("Ebene 2", visible=False), lambda: not obj.paint.layers[1].visible),
        (lambda: app.set_paint_layer("Ebene 2", blend="multiply"), lambda: obj.paint.layers[1].blend == "multiply"),
        (lambda: app.rename_paint_layer("Ebene 2", " Adern "), lambda: _names(obj) == ["Ebene 1", "Adern"]),
        (lambda: app.move_paint_layer("Adern", -1), lambda: _names(obj) == ["Adern", "Ebene 1"]),
        (lambda: app.delete_paint_layer("Adern"), lambda: _names(obj) == ["Ebene 1"]),
    ]
    stacks = [obj.paint]
    for run, check in steps:
        history = len(app.history)
        assert run(), app.status_message
        assert check() and len(app.history) == history + 1
        stacks.append(obj.paint)
    for stack in reversed(stacks[:-1]):
        _undo(app)
        assert obj.paint == stack
    assert np.array_equal(app.paint.pixels(obj, "Ebene 2"), pixels)  # back under its own name
    for stack in stacks[1:]:
        _redo(app)
        assert obj.paint == stack


def test_refusals_change_nothing(app):
    obj = app.scene.edit_object
    history, stack = len(app.history), obj.paint
    assert not app.delete_paint_layer("Ebene 1") and "only paint layer" in app.status_message
    assert not app.merge_paint_layer_down("Ebene 1") and "bottom layer" in app.status_message
    assert not app.move_paint_layer("Ebene 1", 1) and "top" in app.status_message
    assert not app.rename_paint_layer("Ebene 1", "") and "name" in app.status_message
    app.add_paint_layer()
    history, stack = len(app.history), obj.paint
    assert not app.rename_paint_layer("Ebene 2", "Ebene 1") and "exists" in app.status_message
    assert not app.clear_paint_layer("Ebene 2") and "already empty" in app.status_message
    assert not app.set_paint_layer("Ebene 2", opacity=1.0)  # nothing changes: no step
    assert not app.set_paint_layer("Ebene 2", blend="screen") and "blend" in app.status_message
    assert len(app.history) == history and obj.paint == stack
    for _ in range(layers_api.MAX_LAYERS - 2):
        assert app.add_paint_layer()
    assert not app.add_paint_layer() and f"at most {layers_api.MAX_LAYERS}" in app.status_message


def test_merge_down_keeps_what_is_shown_and_refuses_what_one_layer_cannot_hold(app):
    obj = app.scene.edit_object
    app.add_paint_layer()
    app.set_paint_brush(colour=(0.1, 0.8, 0.2))
    _stroke(app, dx=-3.0)
    app.set_paint_layer("Ebene 2", opacity=0.5)
    app.set_paint_layer("Ebene 1", opacity=0.8)
    before = _shown(app, obj)
    lower = app.paint.pixels(obj, "Ebene 1").copy()
    app.set_paint_layer("Ebene 2", blend="multiply")
    assert not app.merge_paint_layer_down("Ebene 2") and "same blend" in app.status_message
    _undo(app)
    app.set_paint_layer("Ebene 2", visible=False)
    assert not app.merge_paint_layer_down("Ebene 2") and "show both" in app.status_message
    _undo(app)
    history = len(app.history)
    assert app.merge_paint_layer_down("Ebene 2") and len(app.history) == history + 1
    assert _names(obj) == ["Ebene 1"] and obj.paint.layers[0].opacity == 1.0 and app.paint_active_layer == "Ebene 1"
    assert np.abs(_shown(app, obj).astype(int) - before).max() <= 1
    _undo(app)
    assert _names(obj) == ["Ebene 1", "Ebene 2"] and np.array_equal(app.paint.pixels(obj, "Ebene 1"), lower)
    assert np.array_equal(_shown(app, obj), before)


def test_multiply_layers_merge_and_clear(app):
    obj = app.scene.edit_object
    app.set_paint_layer("Ebene 1", blend="multiply")
    app.add_paint_layer()
    app.set_paint_layer("Ebene 2", blend="multiply")
    app.set_paint_brush(colour=(0.5, 0.2, 0.9))
    _stroke(app, dx=-3.0)
    before = _shown(app, obj)
    assert app.merge_paint_layer_down("Ebene 2"), app.status_message
    assert obj.paint.layers[0].blend == "multiply"
    assert np.abs(_shown(app, obj).astype(int) - before).max() <= 2
    painted = app.paint.pixels(obj, "Ebene 1").copy()
    assert app.clear_paint_layer("Ebene 1") and not app.paint.pixels(obj, "Ebene 1")[..., 3].any()
    _undo(app)
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), painted)


def test_a_name_used_again_starts_transparent(app):
    obj = app.scene.edit_object
    app.add_paint_layer()
    _stroke(app, dx=-3.0)
    app.delete_paint_layer("Ebene 2")
    app.add_paint_layer()  # "Ebene 2" again; the deleted layer's step is dropped from Redo
    assert _names(obj) == ["Ebene 1", "Ebene 2"]
    assert not app.paint.pixels(obj, "Ebene 2")[..., 3].any()


def test_a_hidden_active_layer_is_not_painted_and_steps_wait_for_the_stroke(app):
    obj = app.scene.edit_object
    app.set_paint_layer("Ebene 1", visible=False)
    history = len(app.history)
    pixels = app.paint.pixels(obj, "Ebene 1").copy()
    _stroke(app)
    assert len(app.history) == history and "hidden" in app.status_message
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), pixels)
    app.set_paint_layer("Ebene 1", visible=True)
    _stroke(app, release=False)
    assert not app.add_paint_layer() and "stroke" in app.status_message
    assert not app.set_paint_active_layer("Ebene 1")


def test_the_held_opacity_slider_previews_without_a_step(app):
    obj = app.scene.edit_object
    history, stack = len(app.history), obj.paint
    assert app.preview_paint_layer("Ebene 1", opacity=0.3)
    assert obj.paint.layers[0].opacity == pytest.approx(0.3) and len(app.history) == history
    assert app.preview_paint_layer("Ebene 1", opacity=0.6)
    assert app.end_paint_layer_preview() and obj.paint == stack  # Esc / dropped: as before
    app.preview_paint_layer("Ebene 1", opacity=0.4)
    assert app.set_paint_layer("Ebene 1", opacity=0.4) and len(app.history) == history + 1
    _undo(app)
    assert obj.paint == stack  # the step starts at the value before the preview
    app.preview_paint_layer("Ebene 1", opacity=0.2)
    app.close_paint_room()
    assert obj.paint == stack  # closing the room ends a preview


def test_an_undo_under_a_held_slider_is_not_undone_by_its_release(app):
    obj = app.scene.edit_object
    app.add_paint_layer()
    with_two = obj.paint
    app.preview_paint_layer("Ebene 2", opacity=0.3)
    _undo(app)  # Ctrl+Z while the slider is held: the layer goes
    assert _names(obj) == ["Ebene 1"]
    assert not app.end_paint_layer_preview() and _names(obj) == ["Ebene 1"]  # the release keeps the Undo's stack
    _redo(app)
    app.preview_paint_layer("Ebene 2", opacity=0.3)
    _undo(app)
    _redo(app)
    assert app.set_paint_layer("Ebene 2", opacity=0.3)
    _undo(app)
    assert obj.paint == with_two  # the step starts from the stack that was there, not the stale preview start


def test_a_layer_change_recomposites_only_painted_tiles_and_equals_a_whole_composite(app):
    obj = app.scene.edit_object
    _shown(app, obj)
    whole = app.paint_display.full_composites
    app.add_paint_layer()
    app.set_paint_brush(colour=(0.9, 0.1, 0.1))
    _stroke(app, dx=-3.0)
    for run in (lambda: app.set_paint_layer("Ebene 2", opacity=0.5),
                lambda: app.set_paint_layer("Ebene 2", blend="multiply"),
                lambda: app.move_paint_layer("Ebene 2", -1),
                lambda: app.set_paint_layer("Ebene 1", visible=False),
                lambda: app.delete_paint_layer("Ebene 2"),
                lambda: _undo(app), lambda: _undo(app), lambda: _redo(app)):
        run()
        assert np.array_equal(_shown(app, obj), _whole(app, obj))
    assert app.paint_display.full_composites == whole


def test_save_and_load_keep_every_layer_and_its_blend(app, tmp_path):
    obj = app.scene.edit_object
    app.add_paint_layer()
    _stroke(app, dx=-3.0)
    app.set_paint_layer("Ebene 2", blend="multiply")
    app.set_paint_layer("Ebene 2", opacity=0.5)
    app.add_paint_layer()  # an empty top layer: no file
    path = tmp_path / "layers.mirai.json"
    assert app.save_scene_file(path), app.status_message
    data = json.loads(path.read_text())
    raw = next(o for o in data["objects"] if o.get("paint"))["paint"]
    assert [(layer["name"], layer["blend"], layer["image"] is None) for layer in raw["layers"]] == [
        ("Ebene 1", "normal", False), ("Ebene 2", "multiply", False), ("Ebene 3", "normal", True)]
    loaded = Application()
    loaded.init_scene("file", scene_path=path)
    other = loaded.scene.edit_object
    assert other.paint.layers[1].opacity == 0.5
    for name in ("Ebene 1", "Ebene 2", "Ebene 3"):
        assert np.array_equal(loaded.paint.pixels(other, name), app.paint.pixels(obj, name))


def test_layer_steps_need_the_room_and_paint():
    app = _app()
    assert not app.add_paint_layer() and "Paint Room" in app.status_message
    app.open_paint_room()
    assert not app.add_paint_layer() and "first stroke" in app.status_message


def test_the_panel_model_lists_the_layers_top_first():
    from gui import paint_model as pm

    app = _app()
    app.open_paint_room()
    st = pm.state(app)
    assert st.layers == () and not st.can_add
    _stroke(app)
    app.add_paint_layer()
    app.set_paint_layer("Ebene 2", opacity=0.5)
    app.set_paint_layer("Ebene 2", blend="multiply")
    st = pm.state(app)
    assert [(row.name, row.active) for row in st.layers] == [("Ebene 2", True), ("Ebene 1", False)]
    assert st.layers[0].label == "Ebene 2  (50 %, Multiplizieren)" and st.layers[1].label == "Ebene 1"
    assert st.can_add and st.can_delete and st.can_down and not st.can_up and not st.can_merge
    app.set_paint_active_layer("Ebene 1")
    st = pm.state(app)
    assert st.can_up and not st.can_down and not st.can_merge
