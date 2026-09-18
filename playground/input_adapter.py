"""Playground Input Adapter — pyglet events to production Input/Command routing.

Converts pyglet key/mouse events to semantic Input objects, resolves them
through BindingSet (production infrastructure), and routes to commands.

Preserves Playground's variant-aware precedence: topology context is
dynamically determined by the active slot/experiment, not statically bound.

Design:
  pyglet event (on_key_press(symbol, modifiers), on_mouse_press(button, modifiers))
       ↓
  Playground input adapter (symbol → Input)
       ↓
  BindingSet.command_for(input, context)
       ↓
  Command string
       ↓
  Playground dispatcher (variant-aware routing)

BindingSet is context-aware: resolves specific context first, then falls back
to GLOBAL_CONTEXT. Playground determines which context to use dynamically
based on the active experiment slot.
"""

from __future__ import annotations

from pyglet.window import key as _key, mouse as _mouse

from mirai.interaction.input import BindingSet, Input, GLOBAL_CONTEXT, TOPOLOGY_CONTEXT
from mirai.interaction.bindings import build_default_bindings


def _key_from_pyglet(symbol: int, modifiers: int) -> Input:
    """Convert pyglet key symbol+modifiers to Input object.

    Maps pyglet._key constants to string names matching production Input format.
    Modifiers: pyglet.window.key.MOD_CTRL → "ctrl", etc.
    """
    # Map pyglet key symbols to string names.
    _PYGLET_KEY_MAP = {
        _key.A: "a", _key.B: "b", _key.C: "c", _key.D: "d", _key.E: "e",
        _key.F: "f", _key.G: "g", _key.H: "h", _key.I: "i", _key.J: "j",
        _key.K: "k", _key.L: "l", _key.M: "m", _key.N: "n", _key.O: "o",
        _key.P: "p", _key.Q: "q", _key.R: "r", _key.S: "s", _key.T: "t",
        _key.U: "u", _key.V: "v", _key.W: "w", _key.X: "x", _key.Y: "y",
        _key.Z: "z",
        _key._0: "0", _key._1: "1", _key._2: "2", _key._3: "3", _key._4: "4",
        _key._5: "5", _key._6: "6", _key._7: "7", _key._8: "8", _key._9: "9",
        _key.TAB: "tab", _key.ESCAPE: "ESCAPE", _key.SPACE: "space",
        _key.UP: "up", _key.DOWN: "down", _key.LEFT: "left", _key.RIGHT: "right",
    }

    key_name = _PYGLET_KEY_MAP.get(symbol)
    if key_name is None:
        return None

    mods = frozenset()
    if modifiers & _key.MOD_CTRL:
        mods = mods | {"ctrl"}
    if modifiers & _key.MOD_SHIFT:
        mods = mods | {"shift"}
    if modifiers & _key.MOD_ALT:
        mods = mods | {"alt"}

    return Input("key", key_name, mods)


def _mouse_from_pyglet(button: int, modifiers: int) -> Input:
    """Convert pyglet mouse button+modifiers to Input object."""
    _PYGLET_MOUSE_MAP = {
        _mouse.LEFT: "LEFT",
        _mouse.MIDDLE: "MIDDLE",
        _mouse.RIGHT: "RIGHT",
    }

    button_name = _PYGLET_MOUSE_MAP.get(button)
    if button_name is None:
        return None

    mods = frozenset()
    if modifiers & _key.MOD_CTRL:
        mods = mods | {"ctrl"}
    if modifiers & _key.MOD_SHIFT:
        mods = mods | {"shift"}
    if modifiers & _key.MOD_ALT:
        mods = mods | {"alt"}

    return Input("mouse", button_name, mods)


def _wheel_from_pyglet(scroll_y: int) -> Input:
    """Convert pyglet scroll direction to wheel Input."""
    direction = "UP" if scroll_y > 0 else "DOWN"
    return Input("wheel", direction, frozenset())


class PlaygroundInputBinding:
    """Manages BindingSet integration for Playground with variant-aware context.

    Wraps production BindingSet and provides context resolution based on
    active experiment variant. Playground determines whether to use
    TOPOLOGY_CONTEXT based on which experiment family is active and its
    configuration.
    """

    def __init__(self) -> None:
        self._binding_set = build_default_bindings()

    @property
    def binding_set(self) -> BindingSet:
        """Access underlying BindingSet for testing/inspection."""
        return self._binding_set

    def command_for(self, input_obj: Input, context: str = GLOBAL_CONTEXT) -> str | None:
        """Resolve input to command, respecting context.

        Args:
            input_obj: Input object (key/mouse/wheel)
            context: Context string (GLOBAL_CONTEXT or TOPOLOGY_CONTEXT)
                     Default: GLOBAL_CONTEXT

        Returns:
            Command string, or None if unbound
        """
        if input_obj is None:
            return None
        return self._binding_set.command_for(input_obj, context)

    def bind(self, input_obj: Input, command: str, context: str = GLOBAL_CONTEXT) -> None:
        """Override a binding (user preference)."""
        if input_obj is not None:
            self._binding_set.bind(input_obj, command, context=context)

    def unbind(self, input_obj: Input, context: str = GLOBAL_CONTEXT) -> bool:
        """Remove a binding override."""
        if input_obj is None:
            return False
        return self._binding_set.unbind(input_obj, context=context)


def determine_input_context(active_family: str | None) -> str:
    """Determine BindingSet context based on active experiment family.

    Playground variants can override input precedence via context.
    Currently, only "topology" family uses TOPOLOGY_CONTEXT to give
    topology-specific bindings precedence (S→SPLIT_EDGE instead of SCALE, etc.).

    Args:
        active_family: Currently focused experiment family (e.g., "topology", "selection")

    Returns:
        TOPOLOGY_CONTEXT if active_family == "topology", else GLOBAL_CONTEXT
    """
    if active_family == "topology":
        return TOPOLOGY_CONTEXT
    return GLOBAL_CONTEXT
