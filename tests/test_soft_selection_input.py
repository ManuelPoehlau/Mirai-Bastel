"""Soft Selection input (WP-SOFT-01 S2a, AD-020; Manu 2026-10-10): bindings and the window's wheel.

- O = on/off, Shift+wheel up/down = radius step, Shift+O = curve, Ctrl+O = metric, as defaults
  of `build_default_bindings()` (re-bindable through keymap.json; the binding carries the direction);
- the plain wheel stays Zoom; Shift+wheel never zooms;
- `src/main.py`: the window reports "Shift held" with the wheel event (`wheel_input`), a driver that
  maps Shift+wheel to a horizontal scroll is read from `scroll_x`, and the handlers wire it through.
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

SOFT_BINDINGS = [
    (_key("o"), cmd.SOFT_TOGGLE),
    (_wheel("UP", "shift"), cmd.SOFT_RADIUS_UP),
    (_wheel("DOWN", "shift"), cmd.SOFT_RADIUS_DOWN),
    (_key("o", "shift"), cmd.SOFT_CURVE_CYCLE),
    (_key("o", "ctrl"), cmd.SOFT_METRIC_CYCLE),
]


# -- bindings -------------------------------------------------------------------------------


@pytest.mark.parametrize("inp,command", SOFT_BINDINGS)
@pytest.mark.parametrize("context", [None, KNIFE_CONTEXT, TOPOLOGY_CONTEXT])
def test_default_soft_bindings_resolve_in_every_context(inp, command, context):
    assert build_default_bindings().command_for(inp, context) == command


def test_five_commands_five_distinct_inputs():
    bs = build_default_bindings()
    assert {bs.command_for(inp) for inp, _ in SOFT_BINDINGS} == {c for _, c in SOFT_BINDINGS}
    assert len(SOFT_BINDINGS) == 5


def test_plain_wheel_stays_zoom_and_other_modifiers_are_unbound():
    bs = build_default_bindings()
    assert bs.command_for(_wheel("UP")) == cmd.ZOOM
    assert bs.command_for(_wheel("DOWN")) == cmd.ZOOM
    assert bs.command_for(_wheel("UP", "ctrl")) is None
    assert bs.command_for(_wheel("UP", "shift", "ctrl")) is None
    assert bs.command_for(_key("o", "alt")) is None
    assert bs.command_for(_key("o", "shift", "ctrl")) is None


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
    assert app.soft_settings.radius_percent == 20
    h["on_mouse_scroll"](10, 10, 0, -1)
    h["on_mouse_scroll"](10, 10, 0, -1)
    assert app.soft_settings.radius_percent == 10
    assert app.camera.distance == distance  # never zoomed
    h["on_key_release"](shift_symbol, 0)
    h["on_mouse_scroll"](10, 10, 0, 1)  # Shift released: the wheel zooms again
    assert app.soft_settings.radius_percent == 10
    assert app.camera.distance < distance


def test_shift_scroll_with_horizontal_driver_steps_the_radius(wired):
    window, app = wired
    h = window.handlers
    distance = app.camera.distance
    h["on_key_press"](key.LSHIFT, key.MOD_SHIFT)
    h["on_mouse_scroll"](10, 10, 3, 0)
    assert app.soft_settings.radius_percent == 20
    assert app.camera.distance == distance


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
    assert app.soft_settings.curve == "linear"
    window.handlers["on_key_press"](key.O, key.MOD_CTRL)
    assert app.soft_settings.metric == "geodesic"
    window.handlers["on_key_press"](key.O, 0)
    assert not app.soft_settings.enabled
