"""Soft Selection input (WP-SOFT-01 S2a/S2d, AD-020; Manu 2026-10-10 / 2026-10-11): bindings and the
window's wheel.

- O = on/off, Shift+wheel up/down = radius step, Shift+O = curve, Ctrl+O = metric, Ctrl+wheel up/down =
  rounder/sharper custom curve, Alt+O = bands on/off, as defaults of `build_default_bindings()`
  (re-bindable through keymap.json; the binding carries the direction);
- the plain wheel stays Zoom; Shift+wheel and Ctrl+wheel never zoom; Ctrl+Shift+wheel is unbound;
- `src/main.py`: the window reports "Shift/Ctrl held" with the wheel event (`wheel_input`), a driver
  that maps the modified wheel to a horizontal scroll is read from `scroll_x`, and the handlers wire
  it through.
"""

from __future__ import annotations

import importlib.util

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _SRC

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import BindingSet, Input, KNIFE_CONTEXT, TOPOLOGY_CONTEXT
from mirai.soft_selection import DEFAULT_RADIUS_STEP, RADIUS_STEPS_PERCENT

pyglet = pytest.importorskip("pyglet")
pyglet.options["headless"] = True
try:
    from pyglet.window import key  # noqa: E402
except Exception as exc:  # pragma: no cover - environment-dependent (no EGL)
    pytest.skip(f"pyglet.window unavailable: {exc}", allow_module_level=True)


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _wheel(direction: str, *modifiers: str) -> Input:
    return Input("wheel", direction, frozenset(modifiers))


def _load_main():
    spec = importlib.util.spec_from_file_location("mirai_src_main_soft", _SRC / "main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


main_module = _load_main()

#: One wheel notch up / down from the default 15 %.
ONE_UP = RADIUS_STEPS_PERCENT[DEFAULT_RADIUS_STEP + 1]
ONE_DOWN = RADIUS_STEPS_PERCENT[DEFAULT_RADIUS_STEP - 1]

SOFT_BINDINGS = [
    (_key("o"), cmd.SOFT_TOGGLE),
    (_wheel("UP", "shift"), cmd.SOFT_RADIUS_UP),
    (_wheel("DOWN", "shift"), cmd.SOFT_RADIUS_DOWN),
    (_key("o", "shift"), cmd.SOFT_CURVE_CYCLE),
    (_key("o", "ctrl"), cmd.SOFT_METRIC_CYCLE),
    (_wheel("UP", "ctrl"), cmd.SOFT_CURVE_SHAPE_ROUNDER),
    (_wheel("DOWN", "ctrl"), cmd.SOFT_CURVE_SHAPE_SHARPER),
    (_key("o", "alt"), cmd.SOFT_BANDS_TOGGLE),
    (_key("o", "alt", "shift"), cmd.SOFT_VIEW_MODE_CYCLE),  # 2026-10-22, PROVISIONAL
    (_key("o", "ctrl", "shift"), cmd.SOFT_LOOK_CYCLE),  # 2026-10-22, PROVISIONAL
]


# -- bindings -------------------------------------------------------------------------------


@pytest.mark.parametrize("inp,command", SOFT_BINDINGS)
@pytest.mark.parametrize("context", [None, KNIFE_CONTEXT, TOPOLOGY_CONTEXT])
def test_default_soft_bindings_resolve_in_every_context(inp, command, context):
    assert build_default_bindings().command_for(inp, context) == command


def test_each_soft_command_has_its_own_input():
    bs = build_default_bindings()
    assert {bs.command_for(inp) for inp, _ in SOFT_BINDINGS} == {c for _, c in SOFT_BINDINGS}
    assert len(SOFT_BINDINGS) == len({c for _, c in SOFT_BINDINGS}) == 10


def test_plain_wheel_stays_zoom_and_other_modifiers_are_unbound():
    bs = build_default_bindings()
    assert bs.command_for(_wheel("UP")) == cmd.ZOOM
    assert bs.command_for(_wheel("DOWN")) == cmd.ZOOM
    assert bs.command_for(_wheel("UP", "alt")) is None
    assert bs.command_for(_wheel("UP", "shift", "ctrl")) is None  # Ctrl+Shift+wheel: unbound
    assert bs.command_for(_wheel("DOWN", "shift", "ctrl")) is None
    assert bs.command_for(_key("o", "alt", "ctrl")) is None


def test_o_is_not_a_display_key():
    """O was the display key until WP-06 B5a (Artist Input Truth: D). It now carries Soft; the
    display keys are D and Shift+D, and nothing display-related answers to O in any form."""
    bs = build_default_bindings()
    display = {cmd.CYCLE_DISPLAY_MODE, cmd.TOGGLE_WIREFRAME_OVERLAY, cmd.SET_SHADED,
               cmd.SET_FLAT_SHADED, cmd.SET_WIREFRAME}
    for mods in ((), ("shift",), ("ctrl",), ("alt",)):
        assert bs.command_for(_key("o", *mods)) not in display
    assert bs.command_for(_key("d")) == cmd.CYCLE_DISPLAY_MODE
    assert bs.command_for(_key("d", "shift")) == cmd.TOGGLE_WIREFRAME_OVERLAY


def test_keymap_json_can_rebind_the_soft_inputs():
    bs = build_default_bindings()
    overlay = BindingSet.from_dict({
        "schemaVersion": 1,
        "bindings": [
            {"context": "global", "input": {"kind": "wheel", "value": "UP", "modifiers": ["ctrl"]},
             "command": cmd.SOFT_RADIUS_UP},
            {"context": "global", "input": {"kind": "key", "value": "o", "modifiers": []}, "command": None},
        ],
    })
    bs.add_overrides(overlay)
    assert bs.command_for(_wheel("UP", "ctrl")) == cmd.SOFT_RADIUS_UP
    assert bs.command_for(_key("o")) is None
    assert bs.command_for(_wheel("UP", "shift")) == cmd.SOFT_RADIUS_UP  # the default is still there


# -- wheel_input (the window's translation) ----------------------------------------------------


def test_wheel_input_without_shift_is_the_plain_wheel():
    assert main_module.wheel_input(0, 1, False) == _wheel("UP")
    assert main_module.wheel_input(0, -2.5, False) == _wheel("DOWN")
    assert main_module.wheel_input(0, 0, False) is None
    # A horizontal scroll without Shift is no wheel event, as before.
    assert main_module.wheel_input(3, 0, False) is None


def test_wheel_input_with_shift_carries_the_modifier():
    assert main_module.wheel_input(0, 1, True) == _wheel("UP", "shift")
    assert main_module.wheel_input(0, -1, True) == _wheel("DOWN", "shift")
    assert main_module.wheel_input(0, 0, True) is None


def test_wheel_input_with_shift_reads_scroll_x_when_scroll_y_is_zero():
    """Drivers that report Shift+wheel as a horizontal scroll (E5). The sign is not confirmed;
    this pins the current reading (positive = up) so the Artist test result can change it."""
    assert main_module.wheel_input(2, 0, True) == _wheel("UP", "shift")
    assert main_module.wheel_input(-2, 0, True) == _wheel("DOWN", "shift")
    # scroll_y wins when both are present.
    assert main_module.wheel_input(5, -1, True) == _wheel("DOWN", "shift")


def test_wheel_input_with_ctrl_carries_the_modifier():
    assert main_module.wheel_input(0, 1, False, True) == _wheel("UP", "ctrl")
    assert main_module.wheel_input(0, -1, False, True) == _wheel("DOWN", "ctrl")
    assert main_module.wheel_input(0, 0, False, True) is None
    assert main_module.wheel_input(0, 1, True, True) == _wheel("UP", "shift", "ctrl")


def test_wheel_input_with_ctrl_reads_scroll_x_when_scroll_y_is_zero():
    """Same horizontal-scroll fallback as Shift (E6); the sign is not confirmed either."""
    assert main_module.wheel_input(2, 0, False, True) == _wheel("UP", "ctrl")
    assert main_module.wheel_input(-2, 0, False, True) == _wheel("DOWN", "ctrl")
    assert main_module.wheel_input(5, -1, False, True) == _wheel("DOWN", "ctrl")


def test_ctrl_keys_after_tracks_left_and_right_separately():
    after = main_module.ctrl_keys_after
    held = after(frozenset(), key.LCTRL, True)
    assert held == {key.LCTRL}
    assert after(held, key.LCTRL, True) == held  # key repeat changes nothing
    both = after(held, key.RCTRL, True)
    assert both == {key.LCTRL, key.RCTRL}
    assert after(both, key.LCTRL, False) == {key.RCTRL}  # the other one is still held
    assert after(frozenset(), key.RCTRL, False) == frozenset()  # release without press
    assert after(held, key.LSHIFT, True) is None and after(held, key.O, True) is None


# -- the window wiring -------------------------------------------------------------------------


class FakeWindow:
    def __init__(self, width: int = 800, height: int = 600) -> None:
        self.width = width
        self.height = height
        self.handlers: dict = {}

    def event(self, func):
        self.handlers[func.__name__] = func
        return func

    def clear(self) -> None:
        pass


@pytest.fixture
def wired():
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(800, 600)
    window = FakeWindow()
    main_module.install_handlers(window, app)
    return window, app


def test_plain_scroll_zooms_and_leaves_soft_alone(wired):
    window, app = wired
    before, settings = app.camera.distance, app.soft_settings
    window.handlers["on_mouse_scroll"](10, 10, 0, 1)
    assert app.camera.distance < before
    assert app.soft_settings == settings


@pytest.mark.parametrize("shift_symbol", [key.LSHIFT, key.RSHIFT])
def test_shift_scroll_steps_the_radius_and_does_not_zoom(wired, shift_symbol):
    window, app = wired
    h = window.handlers
    distance = app.camera.distance
    assert app.soft_settings.radius_percent == 15
    h["on_key_press"](shift_symbol, key.MOD_SHIFT)
    h["on_mouse_scroll"](10, 10, 0, 1)
    assert app.soft_settings.radius_percent == ONE_UP
    h["on_mouse_scroll"](10, 10, 0, -1)
    h["on_mouse_scroll"](10, 10, 0, -1)
    assert app.soft_settings.radius_percent == ONE_DOWN
    assert app.camera.distance == distance  # never zoomed
    h["on_key_release"](shift_symbol, 0)
    h["on_mouse_scroll"](10, 10, 0, 1)  # Shift released: the wheel zooms again
    assert app.soft_settings.radius_percent == ONE_DOWN
    assert app.camera.distance < distance


def test_shift_scroll_with_horizontal_driver_steps_the_radius(wired):
    window, app = wired
    h = window.handlers
    distance = app.camera.distance
    h["on_key_press"](key.LSHIFT, key.MOD_SHIFT)
    h["on_mouse_scroll"](10, 10, 3, 0)
    assert app.soft_settings.radius_percent == ONE_UP
    assert app.camera.distance == distance


@pytest.mark.parametrize("ctrl_symbol", [key.LCTRL, key.RCTRL])
def test_ctrl_scroll_shapes_the_curve_and_does_not_zoom(wired, ctrl_symbol):
    window, app = wired
    h = window.handlers
    distance = app.camera.distance
    assert app.soft_settings.curve == "smooth"
    h["on_key_press"](ctrl_symbol, key.MOD_CTRL)
    h["on_mouse_scroll"](10, 10, 0, 1)  # up = rounder
    assert app.soft_settings.curve == "custom"
    assert app.soft_settings.curve_power == 0.67
    h["on_mouse_scroll"](10, 10, 0, -1)
    h["on_mouse_scroll"](10, 10, 0, -1)
    assert app.soft_settings.curve_power == 1.5  # down = sharper
    assert app.camera.distance == distance  # never zoomed
    assert app.soft_settings.radius_percent == 15  # and no radius step
    h["on_key_release"](ctrl_symbol, 0)
    h["on_mouse_scroll"](10, 10, 0, 1)  # Ctrl released: the wheel zooms again
    assert app.soft_settings.curve_power == 1.5
    assert app.camera.distance < distance


def test_ctrl_scroll_with_horizontal_driver_shapes_the_curve(wired):
    window, app = wired
    h = window.handlers
    distance = app.camera.distance
    h["on_key_press"](key.LCTRL, key.MOD_CTRL)
    h["on_mouse_scroll"](10, 10, 3, 0)
    assert app.soft_settings.curve == "custom" and app.soft_settings.curve_power == 0.67
    assert app.camera.distance == distance


def test_ctrl_shift_scroll_does_nothing(wired):
    window, app = wired
    h = window.handlers
    distance, settings = app.camera.distance, app.soft_settings
    h["on_key_press"](key.LCTRL, key.MOD_CTRL)
    h["on_key_press"](key.LSHIFT, key.MOD_CTRL | key.MOD_SHIFT)
    h["on_mouse_scroll"](10, 10, 0, 1)
    h["on_mouse_scroll"](10, 10, 0, -1)
    assert app.camera.distance == distance  # no zoom ...
    assert app.soft_settings == settings  # ... and no soft change


def test_losing_focus_releases_ctrl_for_the_wheel(wired):
    window, app = wired
    h = window.handlers
    h["on_key_press"](key.LCTRL, key.MOD_CTRL)
    h["on_deactivate"]()
    distance = app.camera.distance
    h["on_mouse_scroll"](10, 10, 0, 1)
    assert app.camera.distance < distance  # plain wheel: Zoom
    assert app.soft_settings.curve == "smooth"


def test_alt_o_through_the_window_toggles_the_bands(wired):
    window, app = wired
    assert app.soft_settings.bands_visible
    assert window.handlers["on_key_press"](key.O, key.MOD_ALT)
    assert not app.soft_settings.bands_visible and app.status_message.endswith("bands off · mono")
    window.handlers["on_key_press"](key.O, key.MOD_ALT)
    assert app.soft_settings.bands_visible


def test_losing_focus_releases_shift_for_the_wheel(wired):
    window, app = wired
    h = window.handlers
    h["on_key_press"](key.LSHIFT, key.MOD_SHIFT)
    h["on_deactivate"]()
    distance = app.camera.distance
    h["on_mouse_scroll"](10, 10, 0, 1)
    assert app.camera.distance < distance  # plain wheel: Zoom
    assert app.soft_settings.radius_percent == 15


def test_o_through_the_window_toggles_soft(wired):
    window, app = wired
    assert window.handlers["on_key_press"](key.O, 0)
    assert app.soft_settings.enabled
    window.handlers["on_key_press"](key.O, key.MOD_SHIFT)
    assert app.soft_settings.curve == "sphere"
    window.handlers["on_key_press"](key.O, key.MOD_CTRL)
    assert app.soft_settings.metric == "euclidean"
    window.handlers["on_key_press"](key.O, 0)
    assert not app.soft_settings.enabled
