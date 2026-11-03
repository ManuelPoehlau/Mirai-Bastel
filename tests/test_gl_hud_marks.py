"""GUI Phase A1 in the real pyglet / GL path: the status strip, the orientation triad and the bone tag draw without
a GL error, the triad's axes show in the gizmo's colours where the geometry says they are, it keeps clear of the
strip in both corners, and moving it never builds new objects.

Needs a real GL context (Xvfb or a real display); run it in its own process:
`xvfb-run -a python -m pytest tests/test_gl_hud_marks.py` (CLAUDE.md, Testing). Skips cleanly without a context.
The headless logic is in `tests/test_hud_strip.py`.
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from hud import BoneTag, Hud, OrientationTriad, triad_center  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.viewport import gizmo  # noqa: E402
from mirai.viewport.camera import OrbitCamera  # noqa: E402

WIDTH, HEIGHT = 640, 480
BACKGROUND = (0.7, 0.7, 0.7)  # the window's clear colour (src/main.py)


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=WIDTH, height=HEIGHT, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


@pytest.fixture
def app():
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _frame(win, draw):
    """Clears, runs `draw()`, returns the RGB bytes (bottom row first)."""
    from pyglet import gl

    win.switch_to()
    gl.glClearColor(*BACKGROUND, 1.0)
    win.clear()
    draw()
    gl.glFinish()
    buf = (gl.GLubyte * (win.width * win.height * 3))()
    gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
    gl.glReadPixels(0, 0, win.width, win.height, gl.GL_RGB, gl.GL_UNSIGNED_BYTE, buf)
    assert gl.glGetError() == gl.GL_NO_ERROR
    return bytes(buf)


def _pixel(buf, x, y):
    i = (int(y) * WIDTH + int(x)) * 3
    return buf[i], buf[i + 1], buf[i + 2]


def _differs(pixel):
    return any(abs(c - round(b * 255)) > 12 for c, b in zip(pixel, BACKGROUND))


def _is_colour(pixel, colour, tol=70):
    return all(abs(c - round(k * 255)) <= tol for c, k in zip(pixel, colour[:3]))


def _front_ortho():
    camera = OrbitCamera()
    camera.set_view(0.0, 0.0, ortho=True)
    return camera


def _find(buf, box, test):
    x0, y0, x1, y1 = (int(v) for v in box)
    return [(x, y) for y in range(max(y0, 0), min(y1, HEIGHT)) for x in range(max(x0, 0), min(x1, WIDTH))
            if test(_pixel(buf, x, y))]


def test_the_strip_draws_at_the_bottom_and_at_the_top(gl_window, app):
    hud = Hud(app.bindings)
    for position in ("bottom", "top"):
        if hud.position != position:
            hud.toggle_position()

        def draw():
            hud.update(app, WIDTH, HEIGHT)
            hud.draw()

        buf = _frame(gl_window, draw)
        assert hud._batch is not None and hud.inset_bottom + hud.inset_top > 0
        inset = hud.inset_bottom or hud.inset_top
        strip_y = 2 if position == "bottom" else HEIGHT - 3
        other_y = HEIGHT - 3 if position == "bottom" else 2
        assert _differs(_pixel(buf, 3, strip_y)), position  # the dark strip background
        assert not _differs(_pixel(buf, 3, other_y)), position  # the other end of the window is untouched
        # the strip ends where the reported inset says (one pixel of slack)
        edge = inset - 2 if position == "bottom" else HEIGHT - inset + 1
        beyond = inset + 2 if position == "bottom" else HEIGHT - inset - 3
        assert _differs(_pixel(buf, 3, edge)) and not _differs(_pixel(buf, 3, beyond))


def test_the_triad_shows_the_axes_in_the_gizmo_colours_where_the_geometry_says(gl_window):
    triad = OrientationTriad(corner="bottom-left", size="M")
    camera = _front_ortho()
    buf = _frame(gl_window, lambda: triad.draw(camera, WIDTH, HEIGHT))
    assert triad._parts is not None
    cx, cy = triad_center("bottom-left", triad.length, WIDTH, HEIGHT)
    reach = triad.length
    # Front ortho: X to the right, Y up. A pixel half way along each axis carries the axis colour.
    assert _is_colour(_pixel(buf, cx + reach / 2, cy), gizmo.COLOR_X)
    assert _is_colour(_pixel(buf, cx, cy + reach / 2), gizmo.COLOR_Y)
    # No blue (Z) line runs along the X axis in this view: Z points at the viewer (its letter sits beside the centre).
    assert not _find(buf, (cx + 2, cy - 1, cx + reach, cy + 2), lambda p: _is_colour(p, gizmo.COLOR_Z, 40))
    assert _find(buf, (cx + 2, cy + 2, cx + 30, cy + 30), lambda p: _is_colour(p, gizmo.COLOR_Z, 40)), "the Z letter"
    # Seen from the right (yaw 90 deg) Z runs to the left of the centre.
    camera.set_view(1.5707963267948966, 0.0, ortho=True)
    buf = _frame(gl_window, lambda: triad.draw(camera, WIDTH, HEIGHT))
    assert _is_colour(_pixel(buf, cx - reach / 2, cy), gizmo.COLOR_Z)
    assert not _differs(_pixel(buf, cx + reach / 2, cy))
    assert triad.moves == 2


@pytest.mark.parametrize("position", ("bottom", "top"))
@pytest.mark.parametrize("corner", ("bottom-left", "top-right"))
def test_the_triad_keeps_clear_of_the_strip_on_screen(gl_window, app, position, corner):
    hud = Hud(app.bindings, position=position, detail="full")
    triad = OrientationTriad(corner=corner, size="M")
    camera = _front_ortho()

    def draw():
        hud.update(app, WIDTH, HEIGHT)
        hud.draw()
        triad.draw(camera, WIDTH, HEIGHT, hud.inset_top, hud.inset_bottom)

    buf = _frame(gl_window, draw)
    strip = (0, 0, WIDTH, hud.inset_bottom) if position == "bottom" else (0, HEIGHT - hud.inset_top, WIDTH, HEIGHT)
    red = lambda p: _is_colour(p, gizmo.COLOR_X, 40)  # noqa: E731
    assert _find(buf, (0, 0, WIDTH, HEIGHT), red), "the X axis is drawn"
    assert not _find(buf, strip, red), "no triad pixel lands on the strip"
    cx, cy = triad_center(corner, triad.length, WIDTH, HEIGHT, hud.inset_top, hud.inset_bottom)
    assert _find(buf, (cx, cy - 3, cx + triad.length, cy + 3), red)


def test_the_bone_tag_draws_with_the_real_label(gl_window, app):
    tag = BoneTag()
    camera = app.camera
    info = ("Jaw", (0.0, 0.0, 0.0))
    _frame(gl_window, lambda: tag.draw(info, camera, WIDTH, HEIGHT))
    assert tag.shown and tag.name == "Jaw" and tag._parts is not None and tag.position is not None
    x, y = tag.position
    buf = _frame(gl_window, lambda: tag.draw(info, camera, WIDTH, HEIGHT))
    assert _differs(_pixel(buf, x + 1, y)), "the dark plate behind the name"
    buf = _frame(gl_window, lambda: tag.draw(None, camera, WIDTH, HEIGHT))
    assert not _differs(_pixel(buf, x + 1, y)) and not tag.shown


def test_orbiting_moves_the_real_triad_without_building_objects(gl_window):
    triad = OrientationTriad()
    camera = OrbitCamera()
    _frame(gl_window, lambda: triad.draw(camera, WIDTH, HEIGHT))
    parts, lines, labels = triad._parts, list(triad._parts.lines), list(triad._parts.labels)
    for _ in range(60):
        camera.orbit(0.02, 0.003)
        _frame(gl_window, lambda: triad.draw(camera, WIDTH, HEIGHT))
    assert triad._parts is parts and triad._parts.lines == lines and triad._parts.labels == labels
    assert triad.moves == 61
