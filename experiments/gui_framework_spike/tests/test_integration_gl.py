"""Echtes pyglet-Fenster (xvfb) mit den echten `install_handlers` und dem imgui-Layer: Eingabe-Hoheit und GL-Zustand.

Läuft nur mit pyglet, imgui-bundle und Display: `xvfb-run -a python -m pytest experiments/gui_framework_spike/tests -q`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_HERE))

pytest.importorskip("imgui_bundle")
pyglet = pytest.importorskip("pyglet")

try:
    import run  # noqa: E402  (legt src/ auf den Pfad, importiert main -> pyglet.window)
except Exception as exc:  # kein Display
    pytest.skip(f"kein GL/Display: {exc}", allow_module_level=True)

from mirai.interaction import commands  # noqa: E402
from pyglet.window import key, mouse  # noqa: E402


@pytest.fixture()
def env():
    try:
        window, app, layer = run.build(argv=["cube"])
    except Exception as exc:
        pytest.skip(f"kein GL/Display: {exc}")
    run.add_demo_objects(app)
    app.dispatch_command(commands.SET_OBJECT_MODE)
    calls = {"press": 0, "release": 0, "motion": 0, "drag": 0, "key": 0, "key_release": 0}
    for name, label in (("pointer_press", "press"), ("pointer_release", "release"), ("pointer_motion", "motion"),
                        ("pointer_drag", "drag"), ("key_press", "key"), ("key_release", "key_release")):
        original = getattr(app, name)

        def spy(*a, _o=original, _l=label, **k):
            calls[_l] += 1
            return _o(*a, **k)

        setattr(app, name, spy)
    for _ in range(3):
        run.render_frame(window)
    yield window, app, layer, calls
    layer.close()
    window.close()


def _frame(window, n=2):
    for _ in range(n):
        run.render_frame(window)


def _center(rect):
    x, y, w, h = rect
    return x + w / 2, y + h / 2


def _to_pyglet(window, pos):
    return pos[0], window.height - pos[1]


def _click(window, pos, button=mouse.LEFT, modifiers=0):
    x, y = _to_pyglet(window, pos)
    window.dispatch_event("on_mouse_motion", x, y, 0, 0)
    _frame(window, 1)
    window.dispatch_event("on_mouse_press", x, y, button, modifiers)
    _frame(window, 1)
    window.dispatch_event("on_mouse_release", x, y, button, modifiers)
    _frame(window, 1)
    window.dispatch_pending_events()


def _id_of(app, name):
    return next(o.id for o in app.scene.objects.values() if o.name == name)


def test_click_on_row_selects_without_viewport_pick(env):
    window, app, layer, calls = env
    tooth = _id_of(app, "Zahn 3")
    _click(window, _center(layer.item_rects[("row", tooth)]))
    assert app.selection.objects == {tooth}
    assert calls["press"] == 0 and calls["release"] == 0  # Klick im Panel erreicht Application nie


def test_shift_click_adds_like_the_viewport(env):
    window, app, layer, calls = env
    a, b = _id_of(app, "Zahn 3"), _id_of(app, "Zahn 4")
    _click(window, _center(layer.item_rects[("row", a)]))
    _click(window, _center(layer.item_rects[("row", b)]), modifiers=key.MOD_SHIFT)
    assert app.selection.objects == {a, b}


def test_click_outside_panel_goes_to_application(env):
    window, app, layer, calls = env
    _click(window, (700.0, 300.0))
    assert calls["press"] == 1 and calls["release"] == 1


def test_drag_from_viewport_over_panel_stays_with_application(env):
    window, app, layer, calls = env
    x0, y0 = 700, window.height - 300
    window.dispatch_event("on_mouse_press", x0, y0, mouse.LEFT, key.MOD_ALT)
    px, py = _to_pyglet(window, _center(layer.item_rects[("row", _id_of(app, "Zahn 3"))]))
    window.dispatch_event("on_mouse_drag", px, py, -300, 0, mouse.LEFT, key.MOD_ALT)
    window.dispatch_event("on_mouse_release", px, py, mouse.LEFT, key.MOD_ALT)
    _frame(window)
    assert calls["press"] == 1 and calls["drag"] >= 1 and calls["release"] == 1


def test_eye_hides_through_the_command_and_undo_restores(env):
    window, app, layer, calls = env
    tooth = _id_of(app, "Zahn 3")
    _click(window, _center(layer.item_rects[("eye", tooth)]))
    assert app.scene.objects[tooth].hidden is True
    assert calls["press"] == 0
    app.dispatch_command(commands.UNDO)
    assert app.scene.objects[tooth].hidden is False


def test_keys_in_text_field_trigger_no_command_and_w_release_is_not_lost(env):
    window, app, layer, calls = env
    window.dispatch_event("on_key_press", key.W, 0)  # W gehalten (Move)
    _frame(window)
    assert calls["key"] == 1
    _click(window, _center(layer.item_rects[("filter", 0)]))
    _frame(window)
    assert layer._keyboard_wanted()
    window.dispatch_event("on_key_press", key.H, 0)  # H: HUD an/aus
    window.dispatch_event("on_text", "h")
    window.dispatch_event("on_key_release", key.H, 0)
    _frame(window, 1)
    app.selection.objects = {_id_of(app, "Zahn 3")}
    window.dispatch_event("on_key_press", key.H, key.MOD_CTRL)  # Ctrl+H: HideObjects in Modus 4
    window.dispatch_event("on_key_release", key.H, key.MOD_CTRL)
    _frame(window, 1)
    assert calls["key"] == 1  # weder H noch Ctrl+H kamen bei Application an
    assert not app.scene.objects[_id_of(app, "Zahn 3")].hidden
    assert layer.filter_text == "h"
    window.dispatch_event("on_key_release", key.W, 0)
    _frame(window, 1)
    assert calls["key_release"] >= 1  # das Release der vor dem Textfeld gedrückten Taste geht durch


def test_motion_over_panel_does_not_reach_application_hover(env):
    window, app, layer, calls = env
    x, y = _to_pyglet(window, _center(layer.item_rects[("row", _id_of(app, "Zahn 3"))]))
    window.dispatch_event("on_mouse_motion", x, y, 1, 1)
    _frame(window, 1)
    assert calls["motion"] == 0


def test_layer_leaves_gl_state_as_found():
    from imgui_layer import restore_gl_state, snapshot_gl_state  # noqa: F401

    try:
        window, app, layer = run.build(argv=["cube"])
    except Exception as exc:
        pytest.skip(f"kein GL/Display: {exc}")
    try:
        window.switch_to()
        run.render_frame(window)
        before = snapshot_gl_state()
        layer.draw()
        assert snapshot_gl_state() == before
    finally:
        layer.close()
        window.close()


def test_move_gesture_follows_the_mouse_over_the_panel(env):
    """W gehalten (Move): Zeigerbewegung über dem Panel erreicht Application weiter (sonst stockt die Geste)."""
    window, app, layer, calls = env
    app.selection.objects = {_id_of(app, "Zahn 3")}
    window.dispatch_event("on_key_press", key.W, 0)
    _frame(window, 1)
    assert app.interaction_owner == "transform"
    x, y = _to_pyglet(window, _center(layer.item_rects[("row", _id_of(app, "Zahn 3"))]))
    window.dispatch_event("on_mouse_motion", x, y, 5, 5)
    _frame(window, 1)
    assert calls["motion"] == 1
    window.dispatch_event("on_key_release", key.W, 0)
    _frame(window, 1)
