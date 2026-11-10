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


# -- Mesh > Detach, SPACE > Select Linked (AD-031 P3) -------------------------------------------------------------


def test_menu_detach_and_select_linked_call_the_application():
    """Ohne Fenster: Mesh > Detach ruft `detach_faces` (die Ablehnung steht in der Statuszeile); SPACE merkt sich beim
    Öffnen das Element unter dem Cursor, und Select Linked nutzt es, auch wenn der Hover danach weg ist."""
    from gui.menus import DETACH_LABEL, LINKED_HINT, LINKED_LABEL, Menus
    from mirai.interaction import commands

    assert (DETACH_LABEL, LINKED_LABEL) == ("Detach", "Select Linked") and LINKED_HINT
    app = _app()
    menus = Menus(None, app, None)
    assert menus.detach() is False and "press 3" in app.status_message  # Modus 1: abgelehnt, nichts geändert
    app.dispatch_command(commands.SET_FACE_MODE)
    face = sorted(app.scene.mesh.all_face_ids())[0]
    app.selection.hovered = face
    menus.open_space(10.0, 10.0)
    assert menus.linked_seed is not None and menus.linked_seed.element == face
    app.pointer_leave()  # der Zeiger erreicht das Menü: kein Hover mehr
    assert menus.select_linked(), app.status_message
    assert app.selection.faces == set(app.scene.mesh.all_face_ids()) and menus.linked_seed is None
    objects = set(app.scene.objects)
    app.selection.faces = {face}
    assert menus.detach(), app.status_message
    assert len(app.scene.objects) == len(objects) + 1
    menus.open_space(10.0, 10.0)  # nichts unter dem Cursor
    assert menus.linked_seed is None
    assert menus.select_linked() is False and "nothing under the cursor" in app.status_message


# -- Mesh > Weld… (AD-031 P4) ---------------------------------------------------------------------------------------


def _weld_app():
    """Zwei Quads nebeneinander, die Naht-Punkte doppelt (0,0003 auseinander), Modus 1, alles ausgewählt."""
    from core import Mesh
    from mirai.interaction import commands

    mesh = Mesh()
    for x0 in (0.0, 1.0003):
        ids = [mesh.add_vertex((x0 + dx, y, 0.0)) for dx, y in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))]
        mesh.add_face(ids)
    app = _app()
    app.scene.mesh.load_state(mesh.export_state())
    app.viewport.on_topology_changed()
    app.dispatch_command(commands.SET_VERTEX_MODE)
    app.selection.vertices = set(app.scene.mesh.all_vertex_ids())
    return app


def test_the_weld_window_shows_the_default_and_its_preview_and_welds_with_the_field():
    """Ohne Fenster: Öffnen setzt den vorläufigen Startwert (0,001 × Diagonale, D10) ins Feld und rechnet die Vorschau
    („n Gruppen, m Punkte“ oder der Grund); eine Änderung des Felds rechnet sie neu; „Weld“ nutzt den Wert im Feld."""
    from gui.menus import WELD_ENTRY, WELD_LABEL, Menus, weld_preview
    from mirai.interaction.input import Input

    assert (WELD_ENTRY, WELD_LABEL) == ("Weld…", "Weld")
    app = _weld_app()
    menus = Menus(None, app, None)
    history = len(app.history)
    menus.open_weld()
    assert menus.weld_threshold == app.weld_default_threshold() > 0.0
    assert weld_preview(menus.weld_plan) == "2 Gruppen, 4 Punkte"
    menus.set_weld_threshold(0.0001)  # kleiner als die Naht: nichts zu verschweißen
    assert "nothing to weld" in weld_preview(menus.weld_plan) and len(app.history) == history
    menus.set_weld_threshold(0.0)
    assert "above 0" in weld_preview(menus.weld_plan)
    menus.set_weld_threshold(0.0005)
    assert weld_preview(menus.weld_plan) == "2 Gruppen, 4 Punkte"
    assert menus.weld(), app.status_message
    assert "(distance 0.0005)" in app.status_message and len(app.history) == history + 1
    assert len(app.scene.mesh.all_vertex_ids()) == 6
    # W5 (Manu 2026-11-10, „Change W5“): ein einzelnes Paar wird verschweißt, die Vorschau sagt es vorher
    app.key_press(Input("key", "z", frozenset({"ctrl"})))
    mesh = app.scene.mesh
    app.selection.vertices = {v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[1] == 0.0
                              and 0.9 < mesh.vertex_position(v)[0] < 1.1}
    menus.set_weld_threshold(0.0005)
    assert weld_preview(menus.weld_plan) == "1 Gruppen, 2 Punkte, 1 nur an einem Punkt verbunden"


def test_menu_bridge_calls_the_application():
    """Mesh > Bridge (AD-031 P5): ohne Auswahl abgelehnt (Statuszeile), mit je einem Punkt zweier Ränder gebaut."""
    from gui.menus import BRIDGE_LABEL, Menus
    from mirai.interaction import commands
    from tests.test_bridge import _rings

    assert BRIDGE_LABEL == "Bridge"
    app = _app()
    menus = Menus(None, app, None)
    mesh, bottom, top = _rings()
    app.scene.mesh.load_state(mesh.export_state())
    app.viewport.on_topology_changed()
    app.dispatch_command(commands.SET_VERTEX_MODE)
    app.selection.clear()
    assert menus.bridge() is False and "none selected" in app.status_message
    app.selection.vertices = {bottom[0], top[0]}
    assert menus.bridge(), app.status_message
    assert len(app.scene.mesh.all_face_ids()) == 24


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


def test_space_over_a_face_remembers_it_for_select_linked(env):
    """AD-031 P3: SPACE über einer Fläche öffnet das Menü am Cursor; der Zeiger über dem Menü löscht den Hover
    (`pointer_leave`), Select Linked wählt trotzdem den Teil unter der Stelle, an der SPACE gedrückt wurde."""
    from core import FaceId
    from mirai.interaction import commands

    window, app, layer, files, calls = env
    app.dispatch_command(commands.SET_FACE_MODE)
    x, y = window.width // 2, window.height // 2
    window.dispatch_event("on_mouse_motion", x, y, 0, 0)
    _frame(window, 2)
    app.flush_hover()
    face = app.selection.hovered
    assert isinstance(face, FaceId)
    window.dispatch_event("on_key_press", key.SPACE, 0)
    window.dispatch_event("on_key_release", key.SPACE, 0)
    _frame(window, 3)
    assert layer.popup_open and layer.menus.linked_seed.element == face
    bx, by, bw, bh = layer.panel_rects[0]
    window.dispatch_event("on_mouse_motion", 20, window.height - bh / 2, 0, 0)  # über ein Panel: der Hover geht
    window.dispatch_pending_events()
    assert app.selection.hovered is None
    assert layer.menus.select_linked(), app.status_message
    assert app.selection.faces == set(app.scene.mesh.all_face_ids())  # der Würfel ist ein Teil
    layer.popup_key()
    _frame(window, 3)
    assert not layer.popup_open


def test_the_mesh_menu_draws_detach_and_the_select_linked_hint(env):
    """AD-031 P3: die Menüleiste öffnet „Mesh“; darin stehen Attach, Detach (aktiv) und Select Linked (inaktiv, mit dem
    Hinweis aufs SPACE-Menü - über der Leiste gibt es keinen Hover)."""
    from gui.menus import DETACH_LABEL, LINKED_HINT, LINKED_LABEL

    window, app, layer, files, calls = env
    menus = layer.menus
    real = menus.imgui
    drawn: list = []

    class Recorder:
        def __getattr__(self, name):
            return getattr(real, name)

        def menu_item(self, label, shortcut="", selected=False, enabled=True):
            drawn.append((label, shortcut, enabled))
            return real.menu_item(label, shortcut, selected, enabled)

    menus.imgui = Recorder()
    bx, by, bw, bh = layer.panel_rects[0]
    y = window.height - bh / 2
    for x in range(30, 160, 6):  # „Mesh“ steht rechts neben „Datei“
        window.dispatch_event("on_mouse_motion", x, y, 0, 0)
        window.dispatch_event("on_mouse_press", x, y, mouse.LEFT, 0)
        _frame(window, 1)
        window.dispatch_event("on_mouse_release", x, y, mouse.LEFT, 0)
        _frame(window, 2)
        if any(label == DETACH_LABEL for label, _, _ in drawn):
            break
        layer.popup_key()
        _frame(window, 2)
    menus.imgui = real
    assert (DETACH_LABEL, "", True) in drawn and (LINKED_LABEL, LINKED_HINT, False) in drawn
    assert calls["press"] == 0  # die Klicks in die Leiste erreichen den Viewport nicht
    layer.popup_key()
    _frame(window, 3)
    assert not layer.popup_open


def test_the_weld_window_opens_from_the_mesh_menu_and_escape_changes_nothing(env):
    """AD-031 P4 („Weld-Fenster passt so“): „Mesh“ zeigt „Weld…“; das Fenster ist modal (die Maus gehört dem Layer),
    zeigt Feld und Vorschau; Esc schließt ohne Änderung, „Weld“ verschweißt mit dem Wert im Feld."""
    from gui.menus import WELD_ENTRY, WELD_LABEL, WELD_TITLE
    from mirai.interaction import commands

    window, app, layer, files, calls = env
    menus = layer.menus
    mesh = app.scene.mesh
    for x0 in (2.0, 3.0003):  # zwei unverbundene Quads neben dem Würfel
        ids = [mesh.add_vertex((x0 + dx, y, 0.0)) for dx, y in ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))]
        mesh.add_face(ids)
    app.viewport.on_topology_changed()
    app.dispatch_command(commands.SET_VERTEX_MODE)
    app.selection.vertices = {v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] > 1.5}
    real = menus.imgui
    drawn: list = []
    press: set = set()

    class Recorder:
        def __getattr__(self, name):
            return getattr(real, name)

        def menu_item(self, label, shortcut="", selected=False, enabled=True):
            drawn.append(label)
            return real.menu_item(label, shortcut, selected, enabled)

        def button(self, label, *args):
            return real.button(label, *args) or label in press

        def begin_popup_modal(self, name, *args):
            opened = real.begin_popup_modal(name, *args)
            if (opened[0] if isinstance(opened, tuple) else opened) and name == WELD_TITLE:
                drawn.append(name)
            return opened

    menus.imgui = Recorder()
    bx, by, bw, bh = layer.panel_rects[0]
    y = window.height - bh / 2
    for x in range(30, 160, 6):  # „Mesh“ öffnen
        window.dispatch_event("on_mouse_motion", x, y, 0, 0)
        window.dispatch_event("on_mouse_press", x, y, mouse.LEFT, 0)
        _frame(window, 1)
        window.dispatch_event("on_mouse_release", x, y, mouse.LEFT, 0)
        _frame(window, 2)
        if WELD_ENTRY in drawn:
            break
        layer.popup_key()
        _frame(window, 2)
    assert WELD_ENTRY in drawn and "Bridge" in drawn
    layer.popup_key()
    _frame(window, 2)
    history, state = len(app.history), mesh.export_state()
    menus.open_weld()
    _frame(window, 3)
    assert layer.popup_open and WELD_TITLE in drawn
    assert menus.weld_plan is not None and menus.weld_plan.refusal is None and menus.weld_plan.points == 4
    layer.popup_key()  # Esc
    _frame(window, 3)
    assert not layer.popup_open and len(app.history) == history and mesh.export_state() == state
    menus.open_weld()
    _frame(window, 2)
    press.add(WELD_LABEL)
    _frame(window, 1)
    press.clear()
    _frame(window, 2)
    menus.imgui = real
    assert not layer.popup_open, app.status_message
    assert len(app.history) == history + 1 and app.status_message.startswith("Weld: 4 points into 2")
    assert calls["press"] == 0
