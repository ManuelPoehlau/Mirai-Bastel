"""Ansichts-Zustand reist mit der Szenendatei (`mirai.view_state`, Manu 2026-11-07)."""

from __future__ import annotations

import json

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.interaction import commands
from mirai.viewport.display import DisplayMode


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _roundtrip(app: Application, tmp_path) -> Application:
    path = tmp_path / "a.mirai.json"
    assert app.save_scene_file(path)
    fresh = _app()
    fresh.load_scene("file", scene_path=path)
    return fresh


def test_view_state_survives_save_and_load(tmp_path):
    app = _app()
    app.dispatch_command(commands.CYCLE_DISPLAY_MODE)
    app.dispatch_command(commands.TOGGLE_WIREFRAME_OVERLAY)
    app.dispatch_command(commands.TOGGLE_REGION_TINT)
    app.dispatch_command(commands.CYCLE_LIGHT_PRESET)
    app.dispatch_command(commands.TOGGLE_LIGHT_SPACE)
    app.set_light(key_intensity=0.4)
    app.display.set_surface_finish(specular=0.1, glossiness=0.9)
    app.camera.target = (1.0, 2.0, 3.0)
    app.camera.distance = 9.0
    app.camera.yaw, app.camera.pitch = 0.3, -0.2
    app.camera.ortho = True

    fresh = _roundtrip(app, tmp_path)

    assert fresh.display.mode is DisplayMode.FLAT_SHADED
    assert fresh.display.wireframe_overlay is True
    assert fresh.display.region_tint is False
    assert fresh.display.light_rig == app.display.light_rig
    assert fresh.display.light_label == app.display.light_label
    assert fresh.display.surface_finish == app.display.surface_finish
    assert (fresh.camera.target, fresh.camera.distance) == ((1.0, 2.0, 3.0), 9.0)
    assert (fresh.camera.yaw, fresh.camera.pitch, fresh.camera.ortho) == (0.3, -0.2, True)


def test_file_without_view_keeps_current_view(tmp_path):
    app = _app()
    path = tmp_path / "old.mirai.json"
    app.save_scene_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["view"]
    path.write_text(json.dumps(data), encoding="utf-8")

    other = _app()
    other.dispatch_command(commands.CYCLE_DISPLAY_MODE)
    other.load_scene("file", scene_path=path)
    assert other.display.mode is DisplayMode.FLAT_SHADED


def test_broken_section_is_skipped_not_fatal(tmp_path):
    app = _app()
    path = tmp_path / "bad.mirai.json"
    app.save_scene_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["view"]["light"] = {"preset": "nope", "space": None, "edit": None}
    data["view"]["camera"]["distance"] = "far"
    data["view"]["display"]["mode"] = "WIREFRAME"
    path.write_text(json.dumps(data), encoding="utf-8")

    fresh = _app()
    fresh.load_scene("file", scene_path=path)
    assert fresh.display.mode is DisplayMode.WIREFRAME
    assert fresh.display.light_preset == app.display.light_preset


def test_core_ignores_the_view_key(tmp_path):
    from core.serialization import scene_from_json

    app = _app()
    path = tmp_path / "c.mirai.json"
    app.save_scene_file(path)
    assert "view" in json.loads(path.read_text(encoding="utf-8"))
    assert scene_from_json(path.read_text(encoding="utf-8")).edit_object is not None
