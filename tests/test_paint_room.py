"""AD-037 §8 Phase 2: the Paint Room in the app (`Application.open_paint_room`, `controllers.paint_room`).

Pinned: entering and leaving is view state (display restored, no History step) and refused without UVs or on an eye; a
stroke is one Undo step that also makes the paint stack (Undo leaves the object unpainted, Redo brings the same pixels);
Esc restores exactly; the room's input (modelling keys refused, Undo refused mid-stroke, Shift+wheel radius, Alt+wheel
opacity, the plain wheel zooms); Pick; the mirrored dab; the live texture shows the composite and only changed tiles are
re-composited; SubD on paints on the SubD surface; saving in the room writes the paint and the pre-room view; a changed
edit object ends the room.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from core import SymmetryDefinition
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.paint.surface import PaintSurface
from mirai.viewport import DisplayMode
from viewport.live_texture import LiveTexture

LMB = Input("mouse", "LEFT", frozenset())
W = H = 800, 600


def _app(uvs: bool = True) -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    if uvs:
        mesh = app.scene.mesh
        for i, fid in enumerate(mesh.all_face_ids()):  # six faces side by side in UV
            mesh.set_face_uvs(fid, [(i / 6 + du / 6, dv) for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1))])
    app.frame_scene()
    return app


def _centre(app) -> tuple[float, float]:
    """The screen point of the middle of the face that faces the camera most."""
    mesh = app.scene.mesh
    camera = app._objects.edit_camera
    eye = np.asarray(camera.eye())
    best = None
    for fid in mesh.all_face_ids():
        pts = np.array([mesh.vertex_position(v) for v in mesh.face_vertices(fid)])
        centre = pts.mean(axis=0)
        normal = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        score = np.dot(normal / np.linalg.norm(normal), (eye - centre) / np.linalg.norm(eye - centre))
        if best is None or score > best[0]:
            best = (score, centre)
    return camera.project_to_screen(tuple(best[1]), 800, 600)


def _finish(app, frames: int = 200, display: bool = True) -> None:
    """Frames until a released stroke has finished (AD-037 §12: the release never evaluates in the event);
    `display` False: only the room's work, not the paint display's update."""
    for _ in range(frames):
        if not app.paint_stroking:
            return
        app.update_viewport(0.0) if display else app._paint_room.frame()
    raise AssertionError("the stroke did not finish")


def _stroke(app, steps: int = 12, dx: float = 4.0, release: bool = True, display: bool = True) -> tuple[float, float]:
    x, y = _centre(app)
    app.pointer_motion(x, y)
    app.pointer_press(LMB, x, y)
    for i in range(1, steps + 1):
        app.pointer_drag(dx, 0.0, x + dx * i, y)
        app.update_viewport(0.0) if display else app._paint_room.frame()  # the stroke's work runs in the frames
    if release:
        app.pointer_release("LEFT", x + dx * steps, y)
        _finish(app, display=display)
    return x, y


@pytest.fixture()
def app():
    app = _app()
    app.set_paint_resolution(1024)
    return app


def test_entering_and_leaving_is_view_state_and_restores_the_display(app):
    app.display.set_mode(DisplayMode.FLAT_SHADED)
    app.display.set_wireframe_overlay(True)
    app.display.region_tint = True
    history = len(app.history)
    assert app.open_paint_room() and app.paint_room_open
    assert app.display.mode is DisplayMode.SHADED and not app.display.wireframe_overlay
    assert app.display.show_texture and not app.display.region_tint
    assert "Paint Room" in app.status_message and "Käfig" in app.status_message
    assert app.interaction_owner == "paint" and len(app.history) == history
    assert app.close_paint_room() and not app.paint_room_open
    assert app.display.mode is DisplayMode.FLAT_SHADED and app.display.wireframe_overlay and app.display.region_tint
    assert app.interaction_owner is None and len(app.history) == history
    assert app.scene.edit_object.paint is None


def test_the_room_is_refused_without_uvs_and_on_an_eye():
    plain = _app(uvs=False)
    assert not plain.open_paint_room() and "no UVs" in plain.status_message
    app = _app()
    eye = app.add_eye()
    app._objects.set_edit_object(eye.id)
    app._follow_edit_object()
    assert not app.open_paint_room() and "eye" in app.status_message


def test_a_stroke_is_one_undo_step_that_makes_the_paint(app):
    obj = app.scene.edit_object
    app.open_paint_room()
    history = len(app.history)
    _stroke(app)
    assert len(app.history) == history + 1
    assert obj.paint is not None and obj.paint.width == 1024 and obj.paint.layers[0].name == "Ebene 1"
    pixels = app.paint.pixels(obj, "Ebene 1").copy()
    assert pixels[..., 3].any()
    assert app.paint_brush.colour == pytest.approx(
        tuple(c / 255 for c in pixels.reshape(-1, 4)[pixels.reshape(-1, 4)[:, 3] == 255][0, :3]), abs=1 / 255)
    app.dispatch_command(commands.UNDO)
    assert obj.paint is None and len(app.history) == history  # the first stroke made the paint: Undo removes it
    app.dispatch_command(commands.REDO)
    assert obj.paint is not None and np.array_equal(app.paint.pixels(obj, "Ebene 1"), pixels)
    _stroke(app)
    assert len(app.history) == history + 2
    app.dispatch_command(commands.UNDO)
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), pixels)  # the second stroke only


def test_escape_restores_the_stroke_exactly_and_makes_no_paint(app):
    obj = app.scene.edit_object
    app.open_paint_room()
    _stroke(app)
    before = app.paint.pixels(obj, "Ebene 1").copy()
    history = len(app.history)
    x, y = _stroke(app, release=False)
    assert not np.array_equal(app.paint.pixels(obj, "Ebene 1"), before)
    assert app.key_press(Input("key", "ESCAPE", frozenset())) is True
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), before) and len(app.history) == history
    app.pointer_drag(4.0, 0.0, x + 60, y)  # the rest of the press paints nothing
    app.pointer_release("LEFT", x + 60, y)
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), before) and len(app.history) == history
    fresh = _app()
    fresh.open_paint_room()
    _stroke(fresh, release=False)
    fresh.key_press(Input("key", "ESCAPE", frozenset()))
    fresh.pointer_release("LEFT", 0.0, 0.0)
    assert fresh.scene.edit_object.paint is None and len(fresh.history) == 0  # no stack without a stroke


def test_the_room_input(app):
    app.open_paint_room()
    mesh_before = app.scene.mesh.export_state()
    assert app.key_press(Input("key", "w", frozenset())) is False  # modelling keys: refused, silently
    assert app.key_press(Input("key", "2", frozenset())) is False
    step = app.paint_brush.radius_step
    assert app.pointer_scroll(Input("wheel", "UP", frozenset({"shift"}))) is True
    assert app.paint_brush.radius_step == step + 1
    assert app.pointer_scroll(Input("wheel", "DOWN", frozenset({"alt"}))) is True
    assert app.paint_brush.opacity == pytest.approx(0.9)
    distance = app.camera.distance
    assert app.pointer_scroll(Input("wheel", "UP", frozenset())) is True and app.camera.distance < distance
    _stroke(app, release=False)
    history = len(app.history)
    app.dispatch_command(commands.UNDO)
    assert len(app.history) == history  # not while a stroke runs
    app.pointer_release("LEFT", *_centre(app))
    _finish(app)
    assert len(app.history) == history + 1
    assert app.scene.mesh.export_state() == mesh_before  # painting never writes the mesh


def test_pick_takes_the_composite_colour_and_returns_to_the_tool(app):
    obj = app.scene.edit_object
    app.open_paint_room()
    app.set_paint_brush(colour=(0.2, 0.6, 1.0), hardness=1.0)
    _stroke(app, steps=2)
    app.set_paint_brush(colour=(1.0, 0.0, 0.0), tool="pick")
    x, y = _centre(app)
    app.pointer_press(LMB, x, y)
    app.pointer_release("LEFT", x, y)
    assert app.paint_brush.tool == "paint"
    assert app.paint_brush.colour == pytest.approx((0.2, 0.6, 1.0), abs=1 / 255)
    assert len(app.history) == 1 and obj.paint is not None


def test_the_mirrored_dab_paints_the_other_side(app):
    obj = app.scene.edit_object
    mesh = app.scene.mesh
    mesh.symmetry_definition = SymmetryDefinition((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    app.open_paint_room()
    app.set_paint_brush(radius_step=8)  # 5 %
    x, y = _centre(app)
    app.pointer_motion(x + 40, y)
    assert app.viewport.tool_line_layers["tool_mirror_dim"]  # the mirror's circle
    app.pointer_press(LMB, x + 40, y)
    app.pointer_release("LEFT", x + 40, y)
    _finish(app)
    surface = PaintSurface(mesh, 1024, 1024)
    painted = np.nonzero(app.paint.pixels(obj, "Ebene 1").reshape(-1, 4)[:, 3])[0]
    painted = painted[surface.map.slot[painted] >= 0]
    xs = surface.map.surface_points(painted)[:, 0]
    assert (xs > 0.05).any() and (xs < -0.05).any()
    app.set_paint_brush(mirror=False)
    app.pointer_motion(x + 41, y)
    assert app.viewport.tool_line_layers["tool_mirror_dim"] == [] and app.viewport.tool_line_layers["tool_preview"]


def test_the_live_texture_shows_the_composite_and_recomposites_only_changed_tiles(app):
    obj = app.scene.edit_object
    app.open_paint_room()
    _stroke(app)
    app.update_viewport(0.0)
    texture = app.viewport.render_mesh.material.texture
    assert isinstance(texture, LiveTexture) and texture is app.paint_display.texture(obj)
    full = app.paint_display.full_composites
    composite = texture.rgba.copy()
    _stroke(app, steps=3, display=False)
    tiles = app.paint_display.update()
    assert 0 < tiles < 16 and app.paint_display.full_composites == full
    assert not np.array_equal(texture.rgba, composite)
    expected = app.paint.composite(obj, app.paint_display._entries[id(obj)].base)
    assert np.array_equal(texture.rgba, expected)


def test_subd_on_paints_on_the_subd_surface(app):
    app.dispatch_command(commands.SUBD_CYCLE_VIEW)
    app.update_viewport(0.0)
    assert app.subdivision.active
    app.open_paint_room()
    assert "SubD-Fläche" in app.status_message
    surface = app._paint_room.surface()
    assert surface.mesh is app.subdivision.provider.surface_mesh and surface.kind.startswith("subd")
    _stroke(app)
    assert app.scene.edit_object.paint is not None
    app.dispatch_command(commands.SUBD_CYCLE_VIEW)  # SubD keys work in the room (P-10): off again
    app.dispatch_command(commands.SUBD_CYCLE_VIEW)
    app.update_viewport(0.0)
    assert app._paint_room.surface().kind in ("cage", f"subd{app.subdivision.level}")


def test_saving_in_the_room_writes_the_paint_and_the_view_before_the_room(app, tmp_path):
    app.display.set_mode(DisplayMode.FLAT_SHADED)
    app.open_paint_room()
    _stroke(app)
    path = tmp_path / "painted.mirai.json"
    assert app.save_scene_file(path), app.status_message
    data = json.loads(path.read_text())
    assert data["version"] == 14 and data["view"]["display"]["mode"] == "FLAT_SHADED"
    names = sorted(p.name for p in (tmp_path / "painted_textures").iterdir())
    assert len(names) == 2 and any("_paint_flat_" in name for name in names)  # the layer and the flattened image
    pixels = app.paint.pixels(app.scene.edit_object, "Ebene 1").copy()
    assert app.paint_room_open  # saving does not end the room
    loaded = Application()
    loaded.init_scene("file", scene_path=path)
    obj = loaded.scene.edit_object
    assert obj.paint is not None
    assert np.array_equal(loaded.paint.pixels(obj, "Ebene 1"), pixels)


def test_a_changed_edit_object_ends_the_room(app):
    first = app.scene.edit_object
    other = app.add_primitive("cube", name="zweiter")
    app._objects.set_edit_object(first.id)
    app._follow_edit_object()
    app.open_paint_room()
    assert app.add_primitive("cube", name="dritter") is None  # modelling is not the room's
    app._objects.set_edit_object(other.id)  # as an Undo that carries the edit object would
    app.update_viewport(0.0)
    assert not app.paint_room_open and "edit object changed" in app.status_message


def test_the_panel_model_and_the_space_row():
    from gui import paint_model as pm

    plain = _app(uvs=False)
    assert pm.menu_label(plain) is None  # no UVs: no row
    app = _app()
    assert pm.menu_label(app) == pm.MENU_OPEN
    assert pm.toggle(app) is True and app.paint_room_open and pm.menu_label(app) == pm.MENU_CLOSE
    st = pm.state(app)
    assert st.open and st.resolution == 2048 and not st.resolution_fixed and st.mirror_plane is None
    assert "Käfig" in st.surface and st.brush.tool == "paint"
    app.set_paint_resolution(1024)
    _stroke(app, steps=2)
    st = pm.state(app)
    assert st.resolution == 1024 and st.resolution_fixed
    assert app.set_paint_resolution(2048) is False and app.paint_resolution == 1024  # set by the first stroke
    assert pm.toggle(app) is True and not app.paint_room_open


# -- Manu's first observations (2026-11-18) ---------------------------------------------------------------------------


def test_the_composite_is_ready_when_the_room_opens_and_the_first_dab_only_adds_tiles(app):
    """„Erster Tupfer dauert ca 7 Sekunden“: the base is read when the room opens; the first stroke makes no whole-image
    composite, and the shown pixels equal the composite exactly."""
    obj = app.scene.edit_object
    app.open_paint_room()
    assert "Basisbild gelesen" in app.status_message
    app.update_viewport(0.0)
    texture = app.viewport.render_mesh.material.texture
    assert isinstance(texture, LiveTexture) and obj.paint is None  # shown through the composite before any paint
    full = app.paint_display.full_composites
    _stroke(app)
    app.update_viewport(0.0)
    assert app.paint_display.full_composites == full
    assert app.viewport.render_mesh.material.texture is texture
    expected = app.paint.composite(obj, app.paint_display._entries[id(obj)].base)
    assert np.array_equal(texture.rgba, expected)
    app.dispatch_command(commands.UNDO)  # the first stroke and the paint go: the base again
    app.update_viewport(0.0)
    from mirai.paint.display import base_composite

    base = app.paint_display._entries[id(obj)].base
    assert obj.paint is None and np.array_equal(texture.rgba, base_composite(base, 1024, 1024))
    app.dispatch_command(commands.REDO)
    app.update_viewport(0.0)
    assert np.array_equal(texture.rgba, app.paint.composite(obj, base))
    app.close_paint_room()
    app.dispatch_command(commands.UNDO)  # unpainted again, room closed: the texture path as before (P-E)
    app.update_viewport(0.0)
    assert not isinstance(app.viewport.render_mesh.material.texture if app.viewport.render_mesh.material else None,
                          LiveTexture)


def test_the_live_texture_regenerates_its_mipmaps_with_every_upload(app):
    """„je steiler der Winkel ist, weniger sichtbar“: the minified levels follow the stroke (policy "frame")."""
    app.open_paint_room()
    app.update_viewport(0.0)
    texture = app.viewport.render_mesh.material.texture
    assert texture.mipmaps == "frame"
    texture.take()
    _stroke(app, release=False)
    app.update_viewport(0.0)
    full, boxes, mips = texture.take()
    assert boxes and mips  # mid-stroke: the boxes and the mip chain


def test_alt_wheel_steps_the_opacity_in_the_room_and_zooms_outside():
    import main as main_module

    assert main_module.wheel_input(0, 1, False, False, True) == Input("wheel", "UP", frozenset({"alt"}))
    app = _app()
    distance = app.camera.distance
    assert app.pointer_scroll(Input("wheel", "UP", frozenset({"alt"}))) is True and app.camera.distance < distance
    app.open_paint_room()
    distance = app.camera.distance
    assert app.pointer_scroll(Input("wheel", "DOWN", frozenset({"alt"}))) is True
    assert app.paint_brush.opacity == pytest.approx(0.9) and app.camera.distance == distance


def test_the_panels_take_the_mouse_in_the_room_but_not_during_a_stroke(app):
    from gui.imgui_layer import ImguiLayer

    layer = ImguiLayer.__new__(ImguiLayer)
    layer.app = app
    app.open_paint_room()
    assert not layer._gesture_running()  # the panel and the SPACE menu work between strokes
    _stroke(app, release=False)
    assert layer._gesture_running()
    app.pointer_release("LEFT", *_centre(app))
    _finish(app)
    assert not layer._gesture_running()


# -- Phase 4a (AD-037 §12): the queue, the finishing stroke, the alpha tip --------------------------------------------

CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
ESC = Input("key", "ESCAPE", frozenset())


def _released(app, steps: int = 12) -> tuple[float, float]:
    """A stroke whose drags and release come without a frame between them: all its work waits for the frames."""
    x, y = _centre(app)
    app.pointer_motion(x, y)
    app.pointer_press(LMB, x, y)
    for i in range(1, steps + 1):
        app.pointer_drag(4.0, 0.0, x + 4.0 * i, y)
    app.pointer_release("LEFT", x + 4.0 * steps, y)
    return x, y


def test_the_release_never_evaluates_in_the_event_and_the_stroke_finishes_over_frames(app, monkeypatch):
    from mirai.controllers import paint_room

    obj = app.scene.edit_object
    app.open_paint_room()
    _stroke(app)
    before = app.paint.pixels(obj, "Ebene 1").copy()
    history = len(app.history)
    monkeypatch.setattr(paint_room.dynamics_api, "FINISH_BUDGET_S", 0.0)  # one step per frame
    _released(app)
    room = app._paint_room
    assert room.finishing and app.paint_stroking and room._queue.evaluated == 0  # nothing evaluated in the events
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), before) and len(app.history) == history
    frames = 0
    while app.paint_stroking:
        app.update_viewport(0.0)
        frames += 1
    assert frames > 3 and len(app.history) == history + 1 and room.last_dabs > 3
    assert not np.array_equal(app.paint.pixels(obj, "Ebene 1"), before)
    app.dispatch_command(commands.UNDO)  # one step per stroke
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), before)


def test_escape_while_finishing_restores_exactly(app, monkeypatch):
    from mirai.controllers import paint_room

    obj = app.scene.edit_object
    app.open_paint_room()
    _stroke(app)
    before = app.paint.pixels(obj, "Ebene 1").copy()
    history = len(app.history)
    monkeypatch.setattr(paint_room.dynamics_api, "FINISH_BUDGET_S", 0.0)
    _released(app)
    for _ in range(4):
        app.update_viewport(0.0)
    assert app._paint_room.finishing and not np.array_equal(app.paint.pixels(obj, "Ebene 1"), before)
    assert app.key_press(ESC) is True
    assert not app.paint_stroking and len(app.history) == history
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), before)
    fresh = _app()
    fresh.open_paint_room()
    _released(fresh)
    fresh.key_press(ESC)  # the first stroke, finishing: no paint stack either
    assert fresh.scene.edit_object.paint is None and len(fresh.history) == 0


def test_undo_and_a_new_press_while_finishing_wait_for_the_stroke(app):
    obj = app.scene.edit_object
    app.open_paint_room()
    _stroke(app)
    first = app.paint.pixels(obj, "Ebene 1").copy()
    history = len(app.history)
    _released(app)
    assert app._paint_room.finishing
    app.dispatch_command(commands.UNDO)  # the API path: refused while it finishes, as while stroking
    assert app._paint_room.finishing and len(app.history) == history
    app.key_press(CTRL_Z)  # the key: the stroke finishes first, then Undo takes it back
    assert not app.paint_stroking and len(app.history) == history
    assert np.array_equal(app.paint.pixels(obj, "Ebene 1"), first)
    app.dispatch_command(commands.REDO)
    second = app.paint.pixels(obj, "Ebene 1").copy()
    assert not np.array_equal(second, first)
    x, y = _released(app)
    assert app._paint_room.finishing
    app.pointer_press(LMB, x, y)  # a new press: the finishing stroke is committed first, the new one starts
    assert len(app.history) == history + 2 and app._paint_room.session.stroking
    app.pointer_release("LEFT", x, y)
    _finish(app)
    assert len(app.history) == history + 3


def test_an_alpha_tip_paints_its_spacing_and_draws_an_oriented_rectangle(app):
    from gui import paint_model as pm
    from mirai.paint import dynamics

    obj = app.scene.edit_object
    app.open_paint_room()
    assert app.paint_brush.dynamics.spacing == dynamics.ROUND_SPACING
    assert app.set_paint_tip("test/poren") and app.paint_brush.tip.alpha == "test/poren"
    assert app.paint_brush.dynamics.spacing == dynamics.ALPHA_SPACING  # the alpha kind's default
    assert "Spitze Poren" in app.status_message and "Abstand 100 %" in app.status_message
    x, y = _centre(app)
    app.pointer_motion(x, y)
    rectangle = app.viewport.tool_line_layers["tool_preview"]
    assert len(rectangle) == 4  # the rectangle; the circle dimmed
    assert len(app.viewport.tool_line_layers["tool_mirror_dim"]) == 48
    history = len(app.history)
    _stroke(app, steps=20, dx=6.0)
    assert len(app.history) == history + 1 and obj.paint is not None
    painted = app.paint.pixels(obj, "Ebene 1")[..., 3]
    assert len(np.unique(painted[painted > 0])) > 20  # the alpha's greys, not a round dab's plateau
    assert app.set_paint_tip(None) and app.paint_brush.dynamics.spacing == dynamics.ROUND_SPACING
    st = pm.state(app)
    assert [label for _, label in st.tips] == ["Rund", "Poren", "Ader", "Kratzer", "Fleck", "Punkte", "Quadrat"]
    with pytest.raises(ValueError):
        app.set_paint_tip("nope")
