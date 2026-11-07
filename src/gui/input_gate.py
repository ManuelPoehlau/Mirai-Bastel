"""Eingabe-Hoheit (Brief Kriterium 1), reine Logik ohne pyglet/imgui.

Die Regel: ImGui bekommt Maus nur über dem Panel (oder wenn ein Drag dort begann) und Tasten nur bei aktivem Textfeld.
Alles andere geht unverändert an `Application` (BindingSet). Ein Drag, der im Viewport begann, bleibt beim Viewport,
auch wenn der Zeiger über das Panel wandert; ein Drag, der im Panel begann, kommt nie in `Application` an.
"""

from __future__ import annotations

Rect = tuple[float, float, float, float]  # x, y (oben links, imgui-Koordinaten), w, h


def rect_hit(rect: Rect | None, x: float, y: float) -> bool:
    if rect is None:
        return False
    rx, ry, rw, rh = rect
    return rx <= x < rx + rw and ry <= y < ry + rh


class InputGate:
    """Entscheidet pro Ereignis: `True` = ImGui behält es (nicht an `Application`), `False` = an `Application`.

    `over_panel(x, y)` und `keyboard_wanted()` liefert der Aufrufer (Rechteck des letzten Frames bzw. imgui's
    `want_capture_keyboard`)."""

    def __init__(self, over_panel, keyboard_wanted) -> None:
        self._over = over_panel
        self._kbd = keyboard_wanted
        self._owner: dict[int, str] = {}  # Maustaste -> "imgui" | "app", gesetzt beim Press
        self._keys_forwarded: set[int] = set()
        self.hovering_panel = False

    # -- Maus ------------------------------------------------------------------------------------------------
    def press(self, button: int, x: float, y: float) -> bool:
        owner = "imgui" if self._over(x, y) else "app"
        self._owner[button] = owner
        return owner == "imgui"

    def drag(self, buttons_down: tuple[int, ...]) -> bool:
        """Ein Drag gehört dem Besitzer des Press (bei mehreren Tasten: imgui, sobald eine dort begann)."""
        return any(self._owner.get(b) == "imgui" for b in buttons_down)

    def release(self, button: int) -> bool:
        return self._owner.pop(button, "app") == "imgui"

    def motion(self, x: float, y: float) -> bool:
        """Zeiger ohne Taste. Gibt True über dem Panel; `hovering_panel` speichert, ob er gerade dort war."""
        over = self._over(x, y)
        self.hovering_panel = over
        return over

    def scroll(self, x: float, y: float) -> bool:
        return self._over(x, y)

    # -- Tasten ----------------------------------------------------------------------------------------------
    def key_press(self, symbol: int) -> bool:
        if self._kbd():
            return True
        self._keys_forwarded.add(symbol)
        return False

    def key_release(self, symbol: int) -> bool:
        """Eine Taste, deren Press an `Application` ging, bekommt auch ihr Release dort (sonst bliebe z.B. W 'gehalten')."""
        if symbol in self._keys_forwarded:
            self._keys_forwarded.discard(symbol)
            return False
        return self._kbd()
