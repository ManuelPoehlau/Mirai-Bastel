"""Geteilte pyglet → Input-Übersetzung (WP-SYM-LAB-01 Slice 1).

Übersetzt pyglet-Tastatur-, Maus- und Wheel-Events in Produktions-
`Input`-Objekte (`mirai.interaction.input.Input`). Nutzbar von jedem
Fenster/Lab, das eine Input-Übersetzung braucht — ohne Abhängigkeit von
`playground/`.

Herkunft: Kopie von `playground/input_adapter.py`
(`_key_from_pyglet`/`_mouse_from_pyglet`/`_wheel_from_pyglet`, eingeführt in
`54e9840`), Stand HEAD zum Zeitpunkt dieses Slices. Grund: Die
Binding-Architecture-Checkpoint-Entscheidung vom 2026-09-24 (siehe Handoff
WP-SYM-LAB-01 Slice 1) verlangt eine geteilte, playground-freie
Adapter-Schicht — `mirai.interaction` bleibt bewusst pyglet-frei (siehe
Docstring `mirai.interaction.input`), das Symmetry Lab darf nicht aus
`playground/` importieren.

Abweichungen vom Original:
  - Rückgabetyp korrekt als `Input | None` annotiert (Original behauptet
    `-> Input`, gibt aber `None` zurück, wenn Symbol/Button unbekannt ist).
  - `wheel_from_pyglet(0)` gibt `None` zurück (Original liefert bei `0`
    fälschlich `"DOWN"`, weil `scroll_y > 0` False ist). `> 0` → `"UP"`,
    `< 0` → `"DOWN"` wie bisher.
  - Öffentliche Namen ohne führenden Unterstrich.
  - Die Lookup-Tabellen (Key-/Maus-Map) werden lazy, aber nur beim ersten
    Aufruf gebaut und danach auf Modulebene gecacht (Original baut das
    Dict bei jedem Aufruf neu).

Dieses Modul vergibt **keine Bedeutung**: keine Commands, keine Kontexte,
kein Wissen über `BindingSet`. Es übersetzt ausschließlich physische
pyglet-Events in physische `Input`-Objekte (siehe
INPUT_COMMAND_TOOL_CONTRACT.md: Input beschreibt, WAS physisch passiert
ist, nicht was es bedeutet).

pyglet wird lazy importiert (Präzedenz: `src/viewport/resource_store.py`,
`PygletStore.allocate`), damit `import mirai.pyglet_input` selbst ohne
pyglet/Display funktioniert und `mirai.interaction` weiterhin pyglet-frei
bleibt.
"""

from __future__ import annotations

from mirai.interaction.input import Input

_KEY_MAP: dict[int, str] | None = None
_MOUSE_MAP: dict[int, str] | None = None


def _key_map() -> dict[int, str]:
    """Baut die pyglet-Symbol → Key-Value-Lookup-Tabelle einmalig (gecacht)."""
    global _KEY_MAP
    if _KEY_MAP is None:
        from pyglet.window import key as _key

        _KEY_MAP = {
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
    return _KEY_MAP


def _mouse_map() -> dict[int, str]:
    """Baut die pyglet-Button → Mouse-Value-Lookup-Tabelle einmalig (gecacht)."""
    global _MOUSE_MAP
    if _MOUSE_MAP is None:
        from pyglet.window import mouse as _mouse

        _MOUSE_MAP = {
            _mouse.LEFT: "LEFT",
            _mouse.MIDDLE: "MIDDLE",
            _mouse.RIGHT: "RIGHT",
        }
    return _MOUSE_MAP


def _modifiers_from_pyglet(modifiers: int) -> frozenset[str]:
    """Übersetzt pyglet-Modifier-Bitmask nach `ctrl`/`shift`/`alt` (andere ignoriert)."""
    from pyglet.window import key as _key

    mods: set[str] = set()
    if modifiers & _key.MOD_CTRL:
        mods.add("ctrl")
    if modifiers & _key.MOD_SHIFT:
        mods.add("shift")
    if modifiers & _key.MOD_ALT:
        mods.add("alt")
    return frozenset(mods)


def key_from_pyglet(symbol: int, modifiers: int) -> Input | None:
    """Übersetzt pyglet `on_key_press(symbol, modifiers)` in ein `Input` (kind="key").

    Gibt `None` zurück, wenn `symbol` nicht im übernommenen Key-Set liegt
    (A–Z, 0–9, TAB, ESCAPE, SPACE, Pfeile).
    """
    key_name = _key_map().get(symbol)
    if key_name is None:
        return None
    return Input("key", key_name, _modifiers_from_pyglet(modifiers))


def mouse_from_pyglet(button: int, modifiers: int) -> Input | None:
    """Übersetzt pyglet `on_mouse_press(button, modifiers)` in ein `Input` (kind="mouse").

    Gibt `None` zurück, wenn `button` nicht LEFT/MIDDLE/RIGHT ist.
    """
    button_name = _mouse_map().get(button)
    if button_name is None:
        return None
    return Input("mouse", button_name, _modifiers_from_pyglet(modifiers))


def wheel_from_pyglet(scroll_y: float) -> Input | None:
    """Übersetzt pyglet `on_mouse_scroll(..., scroll_y)` in ein `Input` (kind="wheel").

    `scroll_y > 0` → `"UP"`, `scroll_y < 0` → `"DOWN"`, `scroll_y == 0` →
    `None` (kein Wheel-Event; Original-Verhalten lieferte hier fälschlich
    `"DOWN"`, siehe Modul-Docstring).
    """
    if scroll_y > 0:
        return Input("wheel", "UP", frozenset())
    if scroll_y < 0:
        return Input("wheel", "DOWN", frozenset())
    return None
