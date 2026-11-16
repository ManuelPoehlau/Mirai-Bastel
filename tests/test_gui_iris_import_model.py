"""Eye LookDev phase 5: the Eye Lab's import dialog, pure logic (`gui.iris_import_model`) - opening a draft with the
suggested circles, moving and resizing them by handle or by value, the options and the symmetry hint. Headless."""

from __future__ import annotations

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

from gui import iris_import_model as im
from mirai import iris_import as ii


def _image(tmp_path, alpha: int = 255):
    yy, xx = np.mgrid[0:200, 0:200]
    rr = np.hypot(xx - 99.5, yy - 99.5)
    rgba = np.full((200, 200, 4), 255, np.uint8)
    rgba[rr < 80, :3] = (90, 120, 160)
    rgba[rr < 25, :3] = 5
    rgba[..., 3] = alpha
    path = tmp_path / "iris.png"
    path.write_bytes(ii.encode_png(rgba))
    return path


def test_a_draft_opens_with_the_suggested_circles(tmp_path):
    draft, message = im.open_draft(f'"{_image(tmp_path)}"')  # quotes as pasted from Explorer
    assert message == "" and draft.estimated == "" and draft.kind == "photo" and draft.correct
    assert abs(draft.marks.pupil.r - 25) < 2 and abs(draft.marks.iris.r - 80) < 2 and draft.hint == ""
    assert not draft.has_alpha and "200 x 200" in draft.summary
    missing, why = im.open_draft(tmp_path / "nope.png")
    assert missing is None and "nicht gefunden" in why
    (tmp_path / "bad.png").write_bytes(b"not an image")
    assert im.open_draft(tmp_path / "bad.png")[0] is None


def test_handles_move_and_resize_the_circles(tmp_path):
    draft, _ = im.open_draft(_image(tmp_path))
    p = draft.marks.pupil
    assert im.pick_handle(draft.marks, p.x + 1, p.y, 4.0) == ("both", "centre")  # coinciding centres
    whole = im.drag_handle(draft, ("both", "centre"), p.x + 5, p.y)
    assert whole.marks.pupil.x == whole.marks.iris.x == p.x + 5
    draft = im.set_circle(draft, "pupil", x=p.x + 10)
    p = draft.marks.pupil
    assert im.pick_handle(draft.marks, p.x + 1, p.y, 4.0) == ("pupil", "centre")
    assert im.pick_handle(draft.marks, p.x + p.r, p.y + 1, 4.0) == ("pupil", "edge")
    iris = draft.marks.iris
    assert im.pick_handle(draft.marks, iris.x, iris.y - iris.r, 4.0) == ("iris", "edge")  # anywhere on the line
    assert im.pick_handle(draft.marks, iris.x + 50, iris.y + 10, 4.0) is None
    moved = im.drag_handle(draft, ("pupil", "centre"), p.x + 6, p.y - 3)
    assert (moved.marks.pupil.x, moved.marks.pupil.y, moved.marks.pupil.r) == (p.x + 6, p.y - 3, p.r)
    bigger = im.drag_handle(moved, ("iris", "edge"), iris.x, iris.y + 90, check=True)
    assert bigger.marks.iris.r == pytest.approx(90) and bigger.marks.iris.x == iris.x
    typed = im.set_circle(bigger, "pupil", r=200)
    assert typed.problem  # larger than the iris: the dialog shows why and offers no import


def test_options_and_the_symmetry_hint(tmp_path):
    draft, _ = im.open_draft(_image(tmp_path, alpha=120))
    assert draft.has_alpha
    off = im.set_circle(draft, "pupil", x=draft.marks.iris.x + 20)
    assert "neben der Irismitte" in off.hint
    flat = im.with_options(off, kind="flat")
    assert flat.hint == ""  # only a frontal photo is checked for symmetry
    with pytest.raises(ValueError):
        im.with_options(draft, kind="scan")
    again = im.reestimate(off)
    assert abs(again.marks.pupil.x - draft.marks.pupil.x) < 1.0


def test_import_goes_through_the_application(tmp_path):
    calls = []

    class App:
        def import_eye_iris(self, *args, **kwargs):
            calls.append((args, kwargs))
            return True

    draft, _ = im.open_draft(_image(tmp_path))
    draft = im.with_options(draft, kind="flat", keep_alpha=True, hold_outer_color=False)
    assert im.run_import(App(), draft) is True
    (path, marks, kind), options = calls[0]
    assert path == draft.path and marks == draft.marks and kind == "flat"
    assert options == dict(correct=True, keep_alpha=False, hold_outer_color=False)  # no alpha in the image: derived
