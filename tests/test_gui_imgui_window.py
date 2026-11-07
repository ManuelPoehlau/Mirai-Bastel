"""Echtes pyglet-Fenster (xvfb) mit den echten `install_handlers` und dem imgui-Layer: Eingabe-Hoheit und GL-Zustand.

Läuft nur mit pyglet, imgui-bundle und Display: `xvfb-run -a python -m pytest tests/test_gui_imgui_window.py -q` (eigener Prozess, siehe CLAUDE.md zu GL-Tests).
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

from gui.imgui_layer import ImguiLayer, snapshot_gl_state  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from pyglet.window import key, mouse  # noqa: E402


class run:  # kleine Helfer, wie sie auch das Messskript (`experiments/gui_framework_spike/bench.py`) braucht
    @staticmethod
    def build(argv=("cube",), **layer_kwargs):
        window = production.create_window("gui test")
        app = production.Application(keymap_path=production.KEYMAP_PATH)
        app.gizmo_enabled = True
        app.init_scene("cube", **production.GL_TYPES)
        app.frame_scene()
        app.set_viewport_size(window.width, window.height)
        layer = ImguiLayer(window, app, **layer_kwargs)
        production.install_handlers(
            window, app, hud=production.Hud(app.bindings), triad=production.OrientationTriad(),
            gui=layer,
        )
        return window, app, layer

    @staticmethod
    def render_frame(window):
        """Ein Frame ohne Event-Loop: pyglet reiht Ereignisse außerhalb von `app.run()` in eine Queue, ohne
        `dispatch_pending_events` läuft `on_draw` nie."""
        window.switch_to()
        window.dispatch_event("on_draw")
        window.dispatch_pending_events()
        window.flip()

    @staticmethod
    def add_demo_objects(app):
        teeth = [app.add_primitive("cube", name=f"Zahn {i + 1}").id for i in range(4)]
        app.dispatch_command(commands.SET_OBJECT_MODE)
        app.selection.objects = set(teeth[:2])
        app.dispatch_command(commands.GROUP_OBJECTS)
        app.selection.objects = set()


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


def test_eye_hides_and_shows_one_object_and_undo_follows(env):
    window, app, layer, calls = env
    tooth = _id_of(app, "Zahn 3")
    _click(window, _center(layer.item_rects[("eye", tooth)]))
    assert app.scene.objects[tooth].hidden is True
    assert calls["press"] == 0
    _click(window, _center(layer.item_rects[("eye", tooth)]))  # zweiter Klick blendet nur dieses Objekt wieder ein
    assert app.scene.objects[tooth].hidden is False
    app.dispatch_command(commands.UNDO)
    assert app.scene.objects[tooth].hidden is True


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


def _type(window, text):
    for ch in text:
        window.dispatch_event("on_text", ch)
        _frame(window, 1)


def _enter(window):
    window.dispatch_event("on_key_press", key.RETURN, 0)
    window.dispatch_event("on_key_release", key.RETURN, 0)
    _frame(window, 2)


def _double_click(window, pos):
    _click(window, pos)
    _click(window, pos)
    _frame(window, 2)


def test_double_click_renames_object_enter_commits_and_keys_stay_in_the_field(env):
    window, app, layer, calls = env
    tooth = _id_of(app, "Zahn 3")
    _double_click(window, _center(layer.item_rects[("row", tooth)]))
    assert layer.editing == ("o", tooth) and layer._keyboard_wanted()
    _type(window, "Eck")  # der Text ist beim Start markiert: er ersetzt den Namen
    _enter(window)
    assert app.scene.objects[tooth].name == "Eck"
    assert layer.editing is None
    assert calls["key"] == 0  # Enter und die Buchstaben kamen nie bei Application an
    app.dispatch_command(commands.UNDO)
    assert app.scene.objects[tooth].name == "Zahn 3"


def test_escape_cancels_the_rename_and_is_not_a_cancel_command(env):
    window, app, layer, calls = env
    tooth = _id_of(app, "Zahn 3")
    _double_click(window, _center(layer.item_rects[("row", tooth)]))
    _type(window, "X")
    window.dispatch_event("on_key_press", key.ESCAPE, 0)
    window.dispatch_event("on_key_release", key.ESCAPE, 0)
    _frame(window, 2)
    assert layer.editing is None and app.scene.objects[tooth].name == "Zahn 3"
    assert calls["key"] == 0


def _with_rig(app):
    from core import Bone, BoneId, Rig

    bones = (
        Bone(BoneId(0), "Root", None, (0, 0, 0), (0, 1, 0)),
        Bone(BoneId(1), "Spine", BoneId(0), (0, 1, 0), (0, 2, 0)),
    )
    app.scene.rig = Rig(bones=bones, bone_id_counter=2)
    return BoneId(0), BoneId(1)


def test_bones_listed_under_skeleton_click_selects_eye_hides_double_click_renames(env):
    window, app, layer, calls = env
    root, spine = _with_rig(app)
    _frame(window, 3)
    _click(window, _center(layer.item_rects[("bone", spine)]))
    assert app._skeleton.current_bone == spine and calls["press"] == 0
    _click(window, _center(layer.item_rects[("bone_eye", root)]))
    assert root in app._skeleton.hidden and spine not in app._skeleton.hidden
    _click(window, _center(layer.item_rects[("bone_eye", root)]))
    assert app._skeleton.hidden == set()
    _click(window, _center(layer.item_rects[("eye", "skeleton")]))
    assert app._skeleton.hidden == {root, spine}
    _double_click(window, _center(layer.item_rects[("bone", spine)]))
    assert layer.editing == ("b", spine)
    _type(window, "Wirbel")
    _enter(window)
    assert app.scene.rig.bone(spine).name == "Wirbel"


# -- AD-030 §13: das Morph-Panel ------------------------------------------------------------------------------------


def _morph_weights(app) -> dict:
    return {lid: w for lid, _, w, _ in app.morph_target_rows()}


def test_morph_panel_new_target_click_name_and_solo(env):
    window, app, layer, calls = env
    _frame(window, 2)
    assert ("morph_new", 0) in layer.item_rects and ("morph_zero", 0) not in layer.item_rects  # ohne Ziele nur „Neu“
    _click(window, _center(layer.item_rects[("morph_new", 0)]))
    _frame(window, 2)
    _click(window, _center(layer.item_rects[("morph_new", 0)]))
    _frame(window, 2)
    lids = [r[0] for r in app.morph_target_rows()]
    assert len(lids) == 2 and app.morph_current_target == lids[1]
    assert calls["press"] == 0 and calls["key"] == 0  # alles im Panel, nichts an Application
    _click(window, _center(layer.item_rects[("morph_name", lids[0])]))
    assert app.morph_current_target == lids[0]
    _click(window, _center(layer.item_rects[("morph_solo", lids[1])]))
    assert _morph_weights(app) == {lids[0]: 0, lids[1]: 100} and app.morph_solo_target == lids[1]
    _click(window, _center(layer.item_rects[("morph_solo", lids[1])]))
    assert _morph_weights(app) == {lids[0]: 0, lids[1]: 0}
    app.dispatch_command(commands.UNDO)  # das zweite „Neu“: Gewichte und Wahl waren kein Undo-Schritt
    assert len(app.morph_target_rows()) == 1


def test_morph_panel_slider_drag_sets_the_weight_without_history(env):
    window, app, layer, calls = env
    app.create_morph_target()
    lid = app.morph_current_target
    _frame(window, 3)
    depth = len(app.history._undo_stack)
    x, y, w, h = layer.item_rects[("morph_weight", lid)]
    start, end = _to_pyglet(window, (x + 2, y + h / 2)), _to_pyglet(window, (x + w * 0.6, y + h / 2))
    window.dispatch_event("on_mouse_motion", *start, 0, 0)
    _frame(window, 1)
    window.dispatch_event("on_mouse_press", *start, mouse.LEFT, 0)
    _frame(window, 1)
    steps = 6
    for i in range(1, steps + 1):
        px = start[0] + (end[0] - start[0]) * i / steps
        window.dispatch_event("on_mouse_drag", px, start[1], (end[0] - start[0]) / steps, 0, mouse.LEFT, 0)
        _frame(window, 1)
    window.dispatch_event("on_mouse_release", *end, mouse.LEFT, 0)
    _frame(window, 2)
    weight = app.morph_weight
    assert 40 <= weight <= 75, weight
    assert len(app.history._undo_stack) == depth
    assert calls["press"] == 0 and calls["drag"] == 0
    assert f"{weight} %" in app.status_message  # eine Meldung beim Loslassen


def test_morph_panel_double_click_renames_and_view_greys_out_the_lifecycle(env):
    window, app, layer, calls = env
    app.create_morph_target()
    lid = app.morph_current_target
    _frame(window, 3)
    _double_click(window, _center(layer.item_rects[("morph_name", lid)]))
    assert layer.editing == ("m", lid)
    _type(window, "Smile")
    _enter(window)
    assert app.scene.mesh.point_layer_info(lid).name == "Smile"
    assert calls["key"] == 0
    app.dispatch_command(commands.SET_VERTEX_MODE)  # die Fixture steht in Modus 4; Tab geht aus 1/2/3
    _frame(window, 2)
    _click(window, _center(layer.item_rects[("morph_edit", lid)]))
    assert app.morph_view_open, app.status_message
    _click(window, _center(layer.item_rects[("morph_delete", 0)]))  # ausgegraut: nichts passiert
    assert app.morph_view_open and len(app.morph_target_rows()) == 1
    _click(window, _center(layer.item_rects[("morph_edit", lid)]))  # jetzt „Zurück“
    assert not app.morph_view_open


def _enter_slow(window):
    """Enter wie von Hand: zwischen Drücken und Loslassen liegen Frames (das Feld schließt schon beim Drücken)."""
    window.dispatch_event("on_key_press", key.RETURN, 0)
    _frame(window, 2)
    window.dispatch_event("on_key_release", key.RETURN, 0)
    _frame(window, 2)


def test_second_rename_after_enter_works_without_touching_the_viewport(env):
    window, app, layer, calls = env
    first, second = _id_of(app, "Zahn 3"), _id_of(app, "Zahn 4")
    _double_click(window, _center(layer.item_rects[("row", first)]))
    _type(window, "Eck")
    _enter_slow(window)
    assert app.scene.objects[first].name == "Eck"
    _double_click(window, _center(layer.item_rects[("row", second)]))
    _frame(window, 40)  # länger als die Wiederholverzögerung einer „hängenden“ Enter-Taste
    assert layer.editing == ("o", second), "das zweite Feld schloss sich sofort wieder"
    _type(window, "Molar")
    _enter_slow(window)
    assert app.scene.objects[second].name == "Molar"
    assert calls["key"] == 0 and calls["key_release"] == 0  # das Enter-Release ging an ImGui, nicht an Application
