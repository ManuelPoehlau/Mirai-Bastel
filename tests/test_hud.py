"""GUI Stage 1: the read-only HUD (`src/hud.py`), headless.

Snapshot, rows, key hints (binding layer), the H cycle, change detection and both layouts run
without GL: the layouts get a stand-in builder whose labels measure ~7 px per character. The
window wiring (H, on_draw) is in `tests/test_main_wiring.py`.
"""

from __future__ import annotations

import dataclasses

import pytest

import tests._bootstrap  # noqa: F401

from hud import FIXED_ROW, VARIANTS, Hud, HudState, hud_rows, hud_state, key_hint, key_hints
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import WINDOW_CONTEXT, BindingSet, Input


def _key(value: str, *mods: str) -> Input:
    return Input("key", value, frozenset(mods))


@pytest.fixture
def app():
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(800, 600)
    return app


# -- snapshot ---------------------------------------------------------------------------------


def test_default_state(app):
    state = hud_state(app)
    assert state.mode == "Vertex"
    assert state.tool == "Move" and state.active is None
    assert state.constraint is None and state.symmetry is None
    assert state.display == "Shaded"
    assert state.soft_on is False and state.subd_view == "off"


def test_state_follows_the_keys(app):
    app.key_press(_key("3"))
    app.key_press(_key("e"))
    app.key_release(_key("e"))
    app.key_press(_key("y", "shift"))
    app.key_press(_key("s", "shift"))
    app.key_press(_key("d"))
    app.key_press(_key("d", "shift"))
    app.key_press(_key("o"))
    app.key_press(_key("v"))
    app.key_press(_key("d", "shift"))  # in a SubD view: hides the preview's lines, not the wire
    state = hud_state(app)
    assert state.mode == "Face"
    assert state.tool == "Rotate"
    assert state.constraint == "xz"
    assert state.symmetry == "X"
    assert state.display == "Flat Shaded + Wire"
    assert state.subd_view == "cage" and state.subd_lines is False
    assert state.soft_on is True and state.soft_radius_percent == 15
    assert state.status == app.status_message and state.status_serial == app.status_serial


def test_running_interaction_is_shown(app):
    app.selection.vertices = {next(iter(app.scene.mesh.all_vertex_ids()))}
    app.key_press(_key("w"))  # armed (held): the hold-key gesture is "Tweak" (Manu A2, 2026-10-28)
    assert hud_state(app).active == "Tweak · Move"
    app.key_release(_key("w"))
    assert hud_state(app).active is None


def test_snapshot_is_read_only(app):
    """Reading the HUD state writes nothing: same status, history, selection and settings."""

    def observable(a):
        return (
            a.status_serial, a.status_message, len(a.history.undo_stack) if hasattr(a.history, "undo_stack") else None,
            a.selection.mode, frozenset(a.selection.vertices), a.selection.hovered, a.soft_settings,
            a.display.label, a.axis_constraint, a.tweak_command, a.subdivision.view, a.scene.mesh.symmetry_definition,
        )

    app.key_press(_key("s", "shift"))
    app.key_press(_key("o"))
    before = observable(app)
    hud = Hud(app.bindings)
    for _ in range(3):
        hud_state(app)
        hud.update(app, 800, 600)
    assert observable(app) == before


def test_hud_never_assigns_to_the_app(app):
    class Guard:
        def __init__(self, target):
            object.__setattr__(self, "_t", target)

        def __getattr__(self, name):
            return getattr(self._t, name)

        def __setattr__(self, name, value):
            raise AssertionError(f"HUD wrote app.{name}")

    Hud(app.bindings).update(Guard(app), 800, 600)


# -- rows and key hints -------------------------------------------------------------------------


def test_key_hints_come_from_the_bindings(app):
    hints = key_hints(app.bindings)
    assert hints["Mode"] == "1/2/3/4"
    assert hints["Tool"] == "W/E/R"
    assert hints["Axis"] == "X/Y/Z/F7"  # F7: one-shot <-> sticky (session switch, 2026-10-28)
    assert hints["Sym"] == "Shift+S/Alt+M"
    assert hints["Display"] == "D/Shift+D"
    assert hints["Soft"] == "O"
    assert hints["SubD"] == "V"
    assert hints["HUD"] == "H"


def test_a_rebinding_changes_the_hint():
    bindings = BindingSet()
    bindings.set_default(_key("w"), commands.MOVE)
    bindings.bind(_key("m"), commands.MOVE)
    bindings.bind(_key("w"), None)  # explicit unbind of the default
    assert key_hint(bindings, (commands.MOVE,)) == "M"
    bindings.bind(_key("m"), None)
    assert key_hint(bindings, (commands.MOVE,)) == ""


def test_hud_key_lives_in_the_window_context(app):
    """`Application` never resolves `window`: H is no app command (no host gate sees it)."""
    assert app.bindings.command_for(_key("h")) is None
    assert app.bindings.command_for(_key("h"), WINDOW_CONTEXT) == commands.TOGGLE_HUD
    serial = app.status_serial
    assert app.key_press(_key("h")) is False
    assert app.status_serial == serial


def test_rows_text(app):
    app.key_press(_key("x"))
    app.key_press(_key("o"))
    rows = {row.label: row for row in hud_rows(hud_state(app), key_hints(app.bindings))}
    assert list(rows) == [
        "Mode", "Tool", "Axis", "Space", "Pivot", "Sym", "Display", "View", "Soft", "SubD", "Region", "Look", "Fixed"
    ]
    # WP Ortho / Views: the view row with the toggle key; on once it is not the plain perspective.
    assert rows["View"].value == "Persp" and rows["View"].keys == "U" and not rows["View"].on
    app.key_press(_key("u"))
    view = {row.label: row for row in hud_rows(hud_state(app), {})}["View"]
    assert view.value == "Ortho" and view.on
    # AD-013 addendum 2026-10-28: the fixed modifier grammar is listed read-only, without keys.
    assert rows["Fixed"].value == FIXED_ROW and rows["Fixed"].keys == ""
    assert rows["Region"].value == "no groups · colours on" and not rows["Region"].on
    assert rows["Look"].value == "Raitt 2:1 · Kamera · Licht Bezugsraum Kamera"
    assert rows["Look"].keys == "↑/↓/←/→"
    assert rows["Axis"].value == "X · one-shot" and rows["Axis"].on
    assert rows["Sym"].value == "off" and not rows["Sym"].on
    assert rows["Soft"].value == "on · 15 % · smooth" and rows["Soft"].on
    assert rows["Mode"].keys == "1/2/3/4"
    state = dataclasses.replace(hud_state(app), constraint="yz", subd_view="iso", subd_lines=False, active="Knife")
    rows = {row.label: row for row in hud_rows(state, {})}
    assert rows["Axis"].value == "YZ plane · one-shot"
    sticky = dataclasses.replace(state, constraint=None, constraint_mode="sticky")
    assert {row.label: row for row in hud_rows(sticky, {})}["Axis"].value == "free · sticky"
    assert rows["SubD"].value == "isolines · L2 · lines hidden"
    assert rows["Tool"].value == "Knife (running)" and rows["Tool"].on


# -- the HUD: H cycle, change detection, layouts ------------------------------------------------


def test_h_cycles_bar_corner_hidden(app):
    hud = Hud(app.bindings)
    assert (hud.visible, hud.variant) == (True, "bar")
    assert hud.toggle() == "corner"
    assert hud.toggle() is None and not hud.visible
    assert hud.toggle() == "bar" and hud.visible
    with pytest.raises(ValueError):
        Hud(app.bindings, variant="side")


class FakeLabel:
    def __init__(self, text, x, y):
        self.text, self.x, self.y = text, x, y
        self.content_width = 7 * len(text)

    def delete(self):
        pass


class FakeBuilder:
    def __init__(self, sink):
        self.batch = None  # nothing to draw headless
        self.sink = sink
        self.rects = []

    def label(self, text, x, y, color):
        label = FakeLabel(text, x, y)
        self.sink.append(label)
        return label

    def rect(self, x, y, width, height):
        self.rects.append((x, y, width, height))


def _hud(app, **kwargs) -> Hud:
    hud = Hud(app.bindings, **kwargs)
    hud.make_builder = FakeBuilder
    return hud


def test_rebuild_only_on_change(app):
    hud = _hud(app)
    assert hud.update(app, 800, 600) is True
    hud.draw()
    assert hud.rebuilds == 1
    for _ in range(5):  # camera moves are no HUD state
        app.camera.distance *= 1.1 if hasattr(app.camera, "distance") else 1
        assert hud.update(app, 800, 600) is False
        hud.draw()
    assert hud.rebuilds == 1
    app.key_press(_key("2"))
    assert hud.update(app, 800, 600) is True
    hud.draw()
    app.set_status("Undo")
    app.set_status("Undo")  # a repeated text is a new message (status_serial)
    assert hud.update(app, 800, 600) is True
    hud.draw()
    assert hud.update(app, 1024, 768) is True  # resize
    hud.draw()
    hud.toggle()  # layout switch
    assert hud.update(app, 1024, 768) is True
    hud.draw()
    assert hud.rebuilds == 5
    hud.toggle()  # hidden: no snapshot, no rebuild
    app.key_press(_key("3"))
    assert hud.update(app, 1024, 768) is False
    hud.draw()
    assert hud.rebuilds == 5


@pytest.mark.parametrize("variant", VARIANTS)
def test_layouts_place_every_row(app, variant):
    hud = _hud(app, variant=variant)
    app.set_status("Mode: Edge")
    hud.update(app, 1024, 768)
    hud.draw()
    texts = [item.text for item in hud._drawables]
    for row in hud_rows(hud.state, hud.hints):
        assert row.label in texts and row.value in texts
    assert "Mode: Edge" in texts and "H: HUD" in texts
    for item in hud._drawables:
        assert 0 <= item.x and item.x + item.content_width <= 1024, (item.text, item.x)
        assert 0 <= item.y <= 768


def test_bar_wraps_when_narrow(app):
    hud = _hud(app, variant="bar")
    hud.update(app, 1600, 768)
    hud.draw()
    wide = {item.y for item in hud._drawables}
    hud.update(app, 500, 768)
    hud.draw()
    narrow = {item.y for item in hud._drawables}
    assert len(narrow) > len(wide)
    assert all(item.x + item.content_width <= 500 for item in hud._drawables if item.text != hud.state.status)


def test_state_is_hashable_signature(app):
    assert isinstance(hash(hud_state(app)), int)
    assert hud_state(app) == hud_state(app)
    assert isinstance(hud_state(app), HudState)
