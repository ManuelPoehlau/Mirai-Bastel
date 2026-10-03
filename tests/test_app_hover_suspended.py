"""`Application.hover_suspended` (WP-SYM-LAB-03 H2, AD-013 H2 addendum, Slice 3).

Headless, fixture as `tests/test_application_pointer.py`. The addendum's T-H at
`Application` level (review CLAUDE-001 F3, probe P2; CLAUDE-002 N5: Face mode set
before the flag), plus T-R5a extended to the flag. The Lab-level T-H (through the
Re-Symmetrize preview) is in `experiments/symmetry_lab/tests/test_app_lab_preview.py`.

Deliberately not named `test_application_*` (that set is what T-R5c re-runs).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import FaceId, SelectionMode
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_face, pick_nearest_vertex

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)

THREE = Input("key", "3")
W = Input("key", "w")
ESC = Input("key", "ESCAPE")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
WHEEL_UP = Input("wheel", "UP")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


class _Notifications:
    """Counts the viewport's selection/hover notifications."""

    def __init__(self, app: Application, monkeypatch) -> None:
        self.count = 0
        original = app.viewport.on_selection_changed

        def counted():
            self.count += 1
            original()

        monkeypatch.setattr(app.viewport, "on_selection_changed", counted)


def _face_screen(app, fid) -> tuple[float, float]:
    mesh = app.scene.mesh
    points = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
    centroid = tuple(sum(p[i] for p in points) / len(points) for i in range(3))
    return app.camera.project_to_screen(centroid, WIDTH, HEIGHT)


def _visible_face(app) -> tuple[FaceId, tuple[float, float]]:
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids()):
        x, y = _face_screen(app, fid)
        if pick_face(app.camera, mesh, x, y, WIDTH, HEIGHT) == fid:
            return fid, (x, y)
    raise AssertionError("no visible face")


def _face_at(app, x, y):
    return pick_face(app.camera, app.scene.mesh, x, y, WIDTH, HEIGHT)


@pytest.fixture
def face_hovered(app):
    """Face mode (set before the flag, N5), the cursor resting on a face."""
    assert app.key_press(THREE)
    assert app.selection.mode is SelectionMode.FACE
    fid, (x, y) = _visible_face(app)
    assert app.pointer_motion(x, y)
    assert app.selection.hovered == fid and isinstance(app.selection.hovered, FaceId)
    return app, fid, (x, y)


# -- T-R5a (extended) ---------------------------------------------------------------


def test_default_is_false_before_and_after_init_scene():
    """T-R5a: `Application()` has `hover_suspended is False` (backing field; no
    viewport yet), and setting it before `init_scene` needs no viewport."""
    app = Application()
    assert app.hover_suspended is False
    assert app.viewport is None
    app.hover_suspended = True
    assert app.hover_suspended is True and app.selection.hovered is None
    app.hover_suspended = False
    app.init_scene("cube")
    assert app.hover_suspended is False


# -- T-H ------------------------------------------------------------------------------


def test_t_h_hover_stays_cleared_on_every_path_and_comes_back(face_hovered, monkeypatch):
    """T-H (F3, probe P2): Face mode, hover over a face → flag True → hover None
    (viewport notified); motion over the face → None; one wheel step → None;
    flag False → re-picked at the cursor."""
    app, fid, (x, y) = face_hovered
    notes = _Notifications(app, monkeypatch)

    app.hover_suspended = True
    assert app.hover_suspended is True
    assert app.selection.hovered is None
    assert notes.count == 1

    assert app.pointer_motion(x, y) is False
    assert app.selection.hovered is None
    assert app.pointer_motion(x + 1, y + 1) is False
    assert app.selection.hovered is None

    assert app.pointer_scroll(WHEEL_UP) is True  # the camera zooms ...
    assert app.selection.hovered is None  # ... the hover stays cleared (P2)
    assert notes.count == 1

    app.hover_suspended = False
    expected = _face_at(app, x + 1, y + 1)
    assert expected is not None
    assert app.selection.hovered == expected and isinstance(app.selection.hovered, FaceId)
    assert notes.count == 2


def test_t_h_negative_control_wheel_brings_the_hover_back_without_the_flag(face_hovered):
    """T-H negative control: without the flag the same wheel step re-picks the
    hover at the resting cursor, so the `None` above is the flag's doing."""
    app, _fid, (x, y) = face_hovered
    app.selection.hovered = None  # cleared some other way, cursor still known
    assert app.pointer_scroll(WHEEL_UP) is True
    assert app.selection.hovered is not None
    assert app.selection.hovered == _face_at(app, x, y)


def test_t_h_refreshes_after_undo_and_commit_keep_it_cleared(app):
    """The refresh paths (Undo, transform commit) go through `_update_hover` too."""
    mesh = app.scene.mesh
    x, y = next(
        (sx, sy)
        for vid in sorted(mesh.all_vertex_ids())
        for sx, sy in [app.camera.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)]
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == vid
    )
    app.pointer_motion(x, y)
    assert app.selection.hovered is not None
    # Move the hovered vertex (hover target), commit: one history entry.
    assert app.key_press(W)
    app.pointer_motion(x + 10, y, 10.0, 0.0)
    assert app.key_release(W)
    assert app.history.can_undo()

    app.pointer_motion(x, y)
    app.hover_suspended = True
    assert app.key_press(CTRL_Z) is True
    assert app.selection.hovered is None
    app.hover_suspended = False
    assert app.selection.hovered is not None


def test_setting_the_same_value_again_is_a_no_op(face_hovered, monkeypatch):
    app, _fid, _pos = face_hovered
    notes = _Notifications(app, monkeypatch)
    app.hover_suspended = False
    assert notes.count == 0
    app.hover_suspended = True
    app.hover_suspended = True
    assert notes.count == 1


def test_false_without_a_known_cursor_leaves_the_hover_empty(face_hovered):
    app, _fid, _pos = face_hovered
    app.hover_suspended = True
    app.pointer_leave()
    app.hover_suspended = False
    assert app.selection.hovered is None


def test_knife_hover_is_not_affected(app):
    """The flag pauses the selection hover only; the Knife's own hover preview is
    a separate path (`_knife_hover`) and keeps working."""
    app.hover_suspended = True
    app.pointer_motion(*MISS)
    app.selection.clear()
    assert app.key_press(Input("key", "c"))
    assert app.knife_active
    _fid, (x, y) = _visible_face(app)
    app.pointer_motion(x, y)
    assert app.knife_render_data.prospective_point is not None
    assert app.selection.hovered is None
    assert app.key_press(ESC)
    assert not app.knife_active
