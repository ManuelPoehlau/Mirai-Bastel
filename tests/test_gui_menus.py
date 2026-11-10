"""Menüleiste, SPACE-Menü und Namensdialoge (AD-030 §12): Dateilogik headless, Eingabe im echten Fenster (xvfb).

Fensterteil: `xvfb-run -a python -m pytest tests/test_gui_menus.py -q` (eigener Prozess, CLAUDE.md zu GL-Tests).
Alle Dateien liegen in `tmp_path`.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from obj_files import ObjFiles
from scene_files import SCENE_SUFFIX, SceneFiles, clean_file_name


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


# -- Dateilogik ---------------------------------------------------------------------------------------------------


def test_clean_file_name_drops_suffix_and_odd_characters():
    assert clean_file_name("  Mein Kopf v2.mirai.json ") == "Mein_Kopf_v2"
    assert clean_file_name("a/b\\c") == "a_b_c"
    assert clean_file_name("zahn.obj", ".obj") == "zahn"
    assert clean_file_name("  ...  ") is None
    assert clean_file_name("") is None


def test_save_as_writes_the_named_file_and_makes_it_current(tmp_path):
    app = _app()
    files = SceneFiles(app, directory=tmp_path)
    assert files.suggested_name() == "cube"
    path = files.save_as("Kopf eins")
    assert path == tmp_path / f"Kopf_eins{SCENE_SUFFIX}" and path.is_file()
    assert files.current == path and files.suggested_name() == "Kopf_eins"
    path.write_text("alt")
    assert files.save_as("Kopf eins") == path and path.read_text() != "alt"  # gleichnamig: überschrieben


def test_save_as_refuses_a_name_without_usable_characters(tmp_path):
    app = _app()
    files = SceneFiles(app, directory=tmp_path)
    assert files.save_as("???") is None and files.current is None
    assert list(tmp_path.iterdir()) == []


def test_new_is_an_empty_scene_without_a_current_file(tmp_path):
    app = _app()
    files = SceneFiles(app, directory=tmp_path)
    files.save_as("x")
    assert files.new()
    assert files.current is None
    assert len(app.scene.objects) == 1
    assert app.scene.edit_object.mesh.export_state() == type(app.scene.edit_object.mesh)().export_state()
    path = files.save_as("leer")
    assert path is not None and files.load(path)  # eine leere Szene lässt sich speichern und laden


def test_export_with_a_name_writes_that_file(tmp_path):
    app = _app()
    obj = ObjFiles(app, directory=tmp_path)
    assert obj.suggested_name() == "cube"
    assert obj.export("Mein Würfel")
    assert (tmp_path / "Mein_W_rfel.obj").is_file()
    assert not obj.export("   ") and len(list(tmp_path.iterdir())) == 1


def test_add_asset_object_adds_an_editable_object():
    from scene_menu import add_asset_object

    app = _app()
    before = len(app.scene.objects)
    assert add_asset_object(app, "head_basemesh")
    assert len(app.scene.objects) == before + 1
    added = [o for o in app.scene.objects.values() if o.name.startswith("head_basemesh")]
    assert len(added) == 1 and added[0].state.name == "NORMAL"
    assert not add_asset_object(app, "gibt_es_nicht")


# -- Mesh > Attach (AD-031 P2, O-13) -----------------------------------------------------------------------------


def _bound_with_part(app):
    """Das Edit-Objekt an ein Rig gebunden (AD-028 §7.1), daneben ein ungewichteter Würfel, in Modus 4 ausgewählt."""
    from core import LayerKind, ObjectTransform, PointLayerInfo
    from mirai.interaction import commands
    from mirai.scene_factory import create_cube
    from tests.test_skinning import _rig

    app.scene.rig = _rig()
    bone = app.scene.rig.bone_ids()[0]
    mesh = app.scene.mesh
    skin = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(skin, v, ((int(bone), 1.0),))
    part = app.scene.add_object(create_cube(0.5), name="Part")
    part.transform = ObjectTransform(translation=(3.0, 0.0, 0.0))
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = {part.id}
    return part


def test_attach_request_runs_at_once_or_returns_the_unweighted_count():
    from gui.menus import attach_request

    app = _app()
    part = _bound_with_part(app)
    history = len(app.history)
    assert attach_request(app, False) == len(part.mesh.all_vertex_ids())  # O-5: nothing changed, the count
    assert len(app.history) == history and part.id in app.scene.objects
    app.scene.rig = None  # not bound any more: Attach runs at once
    assert attach_request(app, False) is None
    assert part.id not in app.scene.objects and len(app.history) == history + 1


# -- Fenster ------------------------------------------------------------------------------------------------------

pytest.importorskip("imgui_bundle")
pyglet = pytest.importorskip("pyglet")

try:
    import main as production
except Exception as exc:  # kein Display
    pytest.skip(f"kein GL/Display: {exc}", allow_module_level=True)

from gui.imgui_layer import ImguiLayer  # noqa: E402
from gui.menus import Services  # noqa: E402
from pyglet.window import key, mouse  # noqa: E402
from scene_menu import (  # noqa: E402
    add_asset_object, add_mesh_entries, add_named_reference, add_primitive_named, load_named_scene, scene_entries,
)


def _frame(window, n=2):
    for _ in range(n):
        window.switch_to()
        window.dispatch_event("on_draw")
        window.dispatch_pending_events()
        window.flip()


@pytest.fixture()
def env(tmp_path):
    try:
        window = production.create_window("menus test")
        app = production.Application(keymap_path=production.KEYMAP_PATH)
        app.gizmo_enabled = True
        app.init_scene("cube", **production.GL_TYPES)
        app.frame_scene()
        app.set_viewport_size(window.width, window.height)
    except Exception as exc:
        pytest.skip(f"kein GL/Display: {exc}")
    files = SceneFiles(app, directory=tmp_path / "scenes", gl_types=production.GL_TYPES)
    objs = ObjFiles(app, directory=tmp_path / "obj")
    services = Services(
        files=files, obj_files=objs, primitives=add_mesh_entries,
        add_primitive=lambda n: add_primitive_named(app, n), add_base=lambda n: add_asset_object(app, n),
        scenes=scene_entries, load_scene=lambda n: load_named_scene(app, n, production.GL_TYPES),
        add_reference=lambda n: add_named_reference(app, n),
    )
    layer = ImguiLayer(window, app, services=services)
    production.install_handlers(
        window, app, hud=production.Hud(app.bindings), triad=production.OrientationTriad(), gui=layer,
        save=layer.save,
    )
    calls = {"press": 0, "key": 0}
    for name, label in (("pointer_press", "press"), ("key_press", "key")):
        original = getattr(app, name)

        def spy(*a, _o=original, _l=label, **k):
            calls[_l] += 1
            return _o(*a, **k)

        setattr(app, name, spy)
    _frame(window, 3)
    yield window, app, layer, files, calls
    layer.close()
    window.close()


def test_layer_without_services_has_no_menus_and_no_popup():
    # ohne `services` bleibt der Layer der Outliner allein (kein Menü, SPACE bleibt beim alten Menü)
    assert ImguiLayer(None, None).has_menus is False


def test_menu_bar_is_part_of_the_panel_rects(env):
    window, app, layer, files, calls = env
    x, y, w, h = layer.panel_rects[0]
    assert (x, y) == (0.0, 0.0) and w == window.width and h > 10


def test_space_opens_the_panel_menu_and_swallows_clicks_and_keys_until_closed(env):
    window, app, layer, files, calls = env
    window.dispatch_event("on_mouse_motion", 400, 300, 0, 0)
    window.dispatch_event("on_key_press", key.SPACE, 0)
    _frame(window, 3)
    assert layer.popup_open
    window.dispatch_event("on_key_press", key.W, 0)  # modal: keine Taste erreicht Application
    assert calls["key"] == 0
    window.dispatch_event("on_mouse_press", 700, 600, mouse.LEFT, 0)  # Klick daneben schließt, erreicht den Viewport nie
    _frame(window, 1)
    window.dispatch_event("on_mouse_release", 700, 600, mouse.LEFT, 0)
    _frame(window, 3)
    assert calls["press"] == 0
    assert not layer.popup_open
    window.dispatch_event("on_mouse_press", 700, 400, mouse.LEFT, 0)  # danach läuft der Viewport wieder
    window.dispatch_pending_events()
    assert calls["press"] == 1


def test_space_again_and_escape_close_the_menu(env):
    window, app, layer, files, calls = env
    for closer in (key.SPACE, key.ESCAPE):
        window.dispatch_event("on_key_press", key.SPACE, 0)
        _frame(window, 3)
        assert layer.popup_open
        window.dispatch_event("on_key_release", key.SPACE, 0)
        window.dispatch_event("on_key_press", closer, 0)
        _frame(window, 3)
        assert not layer.popup_open
        window.dispatch_event("on_key_release", closer, 0)


def test_ctrl_s_on_a_new_scene_asks_for_a_name_then_saves_and_ctrl_s_again_overwrites(env):
    window, app, layer, files, calls = env
    window.dispatch_event("on_key_press", key.S, key.MOD_CTRL)
    window.dispatch_event("on_key_release", key.S, key.MOD_CTRL)
    _frame(window, 3)
    assert layer.popup_open and files.current is None and not files.directory.exists()
    layer.menus.name_buf = "Kopf zwei"
    files.save_as(layer.menus.name_buf)
    layer.popup_key()
    _frame(window, 3)
    assert not layer.popup_open
    saved = files.current
    assert saved is not None and saved.name == f"Kopf_zwei{SCENE_SUFFIX}"
    window.dispatch_event("on_key_press", key.S, key.MOD_CTRL)  # jetzt gibt es eine Datei: kein Dialog
    window.dispatch_event("on_key_release", key.S, key.MOD_CTRL)
    _frame(window, 3)
    assert not layer.popup_open and files.current == saved


def test_menu_bar_click_opens_the_file_menu_and_the_empty_scene_renders(env):
    window, app, layer, files, calls = env
    bx, by, bw, bh = layer.panel_rects[0]
    x, y = 20, window.height - bh / 2  # „Datei“ links in der Leiste
    window.dispatch_event("on_mouse_motion", x, y, 0, 0)
    _frame(window, 1)
    window.dispatch_event("on_mouse_press", x, y, mouse.LEFT, 0)
    _frame(window, 1)
    window.dispatch_event("on_mouse_release", x, y, mouse.LEFT, 0)
    _frame(window, 3)
    assert layer.popup_open and calls["press"] == 0
    layer.popup_key()
    _frame(window, 3)
    assert not layer.popup_open
    assert files.new()
    _frame(window, 3)  # leeres Objekt: der echte Draw-Pfad (GL) kommt damit klar
    assert len(app.scene.objects) == 1


def test_goz_panel_lists_send_and_survives_frames(env):
    window, app, layer, files, calls = env
    assert layer.goz is None  # ohne Brücke in den Services kein GoZ-Knopf


def test_mesh_attach_with_unweighted_points_opens_the_prompt_and_escape_changes_nothing(env):
    window, app, layer, files, calls = env
    part = _bound_with_part(app)
    history = len(app.history)
    layer.menus.attach(False)
    _frame(window, 3)
    assert layer.popup_open and layer.menus.attach_pending == (False, len(part.mesh.all_vertex_ids()))
    layer.popup_key()  # Esc
    _frame(window, 3)
    assert not layer.popup_open and len(app.history) == history and part.id in app.scene.objects
