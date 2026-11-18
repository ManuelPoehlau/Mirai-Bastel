"""AD-037 Phase 1a: the UV check in the app (`Application.toggle_uv_check`) - status line, the face colours in place of
the region colours while it shows, recomputed after a UV edit, view state only (no History, mesh unchanged)."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.paint.uv_check_display import UV_CHECK_COLOURS


class Viewport:
    """The two viewport calls the check uses, recorded."""

    def __init__(self, real) -> None:
        self.real, self.tints, self.tint_on = real, None, None

    def __getattr__(self, name):
        return getattr(self.real, name)

    def set_face_tints(self, tints) -> None:
        self.tints = dict(tints)
        self.real.set_face_tints(tints)

    def set_region_tint(self, on) -> None:
        self.tint_on = on
        self.real.set_region_tint(on)


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    mesh = app.scene.mesh
    faces = mesh.all_face_ids()
    for i, fid in enumerate(faces):  # six faces side by side in UV
        mesh.set_face_uvs(fid, [(i / 6 + du / 6, dv) for du, dv in ((0, 0), (1, 0), (1, 1), (0, 1))])
    app.viewport = Viewport(app.viewport)
    return app


def test_the_check_reports_colours_and_switches_off_again():
    app = _app()
    mesh = app.scene.mesh
    faces = mesh.all_face_ids()
    mesh.set_face_uvs(faces[0], [(0.0, 0.0), (0.1, 0.0), (0.1, 0.0), (0.0, 0.0)])  # no UV area
    mesh.set_face_uvs(faces[1], mesh.face_uvs(faces[2]))  # on face 2
    history = len(app.history)
    app.display.region_tint = False
    assert app.toggle_uv_check() and app.uv_check_on
    assert "1 without UV area" in app.status_message and "2 overlapping" in app.status_message
    assert app.viewport.tint_on is True  # shown even with the region colours off
    app.update_viewport(0.0)
    assert app.viewport.tints == {faces[0]: UV_CHECK_COLOURS["zero_area"], faces[1]: UV_CHECK_COLOURS["overlapping"],
                                  faces[2]: UV_CHECK_COLOURS["overlapping"]}
    mesh.set_face_uvs(faces[1], [(1 / 6, 0.0), (2 / 6, 0.0), (2 / 6, 1.0), (1 / 6, 1.0)])  # back: an edit while it shows
    app.update_viewport(0.0)
    assert app.viewport.tints == {faces[0]: UV_CHECK_COLOURS["zero_area"]}
    assert not app.toggle_uv_check() and app.status_message == "UV check: off"
    app.update_viewport(0.0)
    assert app.viewport.tints == {} and app.viewport.tint_on is False
    mesh.set_face_uvs(faces[1], mesh.face_uvs(faces[2]))
    mesh.set_face_uvs(faces[1], None)
    assert len(app.history) == history
    assert app.uv_health().unmapped == (faces[1],)
