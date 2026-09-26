"""Window-freier Pointer-Gesten-Resolver: Klick vs. Drag (AD-019).

Eine physische Maustaste kann zwei Bindungen tragen: `mouse` (Klick) und
`drag` (Press + Bewegung ≥ Schwelle), z. B. Alt+LMB-Klick = SelectToggle und
Alt+LMB-Drag = Orbit. `PointerGestures` schlägt beim Press beide Bindungen für
genau (Taste, Modifier) nach und entscheidet anhand der Bewegung:

- nur `drag` gebunden  → Drag startet sofort (keine Totzone),
- nur `mouse` gebunden → Klick beim Release unter der Schwelle, sonst verworfen,
- beide gebunden       → offen, bis die Schwelle erreicht ist (→ Drag, das
                         aufgelaufene Delta wird nachgereicht) oder die Taste
                         vorher losgelassen wird (→ Klick),
- nichts gebunden      → Geste wird geschluckt.

Die Geste ist beim Press fixiert: Modifier-Wechsel während der Geste zählen
nicht, Presses anderer Tasten werden ignoriert, nur das Release der eigenen
Taste beendet sie.

Der Resolver führt nichts aus — er liefert `DragStep`/`Click` an den Aufrufer
(`Application`). Kein pyglet, kein Fenster (Vorbild: Playground
`selector.CLICK_THRESHOLD` / `window.on_mouse_release`, Symmetry Lab
`lab_dispatch.py` — nur Technik-Referenz, kein Import).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .input import BindingSet, Input

#: Pixel, Manhattan-Summe über alle Drag-Deltas (gleiches Maß wie Playground).
CLICK_THRESHOLD_PX = 5.0


@dataclass(frozen=True)
class DragStep:
    """Ein auszuführender Drag-Schritt (`dx`/`dy` in Pixeln)."""

    command: str
    dx: float
    dy: float


@dataclass(frozen=True)
class Click:
    """Ein auszuführender Klick an der Release-Position."""

    command: str
    x: float
    y: float


@dataclass
class _Gesture:
    button: str
    click_command: Optional[str]
    drag_command: Optional[str]
    moved: float = 0.0
    dragging: bool = False
    pending_dx: float = 0.0
    pending_dy: float = 0.0


class PointerGestures:
    """Löst Press/Drag/Release einer Maustaste gegen ein `BindingSet` auf."""

    def __init__(
        self,
        bindings: BindingSet,
        threshold: float = CLICK_THRESHOLD_PX,
        context: str | None = None,
    ) -> None:
        self._bindings = bindings
        self._threshold = threshold
        self._context = context
        self._gesture: Optional[_Gesture] = None

    @property
    def active(self) -> bool:
        return self._gesture is not None

    @property
    def active_button(self) -> Optional[str]:
        return self._gesture.button if self._gesture is not None else None

    def press(self, input: Input) -> None:
        """Beginnt eine Geste für `input` (kind `"mouse"`: Taste + Modifier).

        Ein Press während einer laufenden Geste wird ignoriert."""
        if self._gesture is not None or input.kind != "mouse":
            return
        drag_input = Input("drag", input.value, input.modifiers)
        click_command = self._bindings.command_for(input, self._context)
        drag_command = self._bindings.command_for(drag_input, self._context)
        self._gesture = _Gesture(
            button=input.value,
            click_command=click_command,
            drag_command=drag_command,
            dragging=drag_command is not None and click_command is None,
        )

    def drag(self, dx: float, dy: float) -> Optional[DragStep]:
        """Bewegung der laufenden Geste; liefert den auszuführenden Drag-Schritt."""
        gesture = self._gesture
        if gesture is None:
            return None
        gesture.moved += abs(dx) + abs(dy)
        if gesture.dragging:
            return DragStep(gesture.drag_command, dx, dy)
        if gesture.drag_command is None:
            # Nur Klick gebunden (oder nichts): Bewegung zählt nur für die Schwelle.
            return None
        gesture.pending_dx += dx
        gesture.pending_dy += dy
        if gesture.moved < self._threshold:
            return None
        gesture.dragging = True
        step = DragStep(gesture.drag_command, gesture.pending_dx, gesture.pending_dy)
        gesture.pending_dx = gesture.pending_dy = 0.0
        return step

    def release(self, button: str, x: float, y: float) -> Optional[Click]:
        """Beendet die Geste von `button`; liefert einen Klick, falls einer fällt.

        Das Release einer fremden Taste wird ignoriert."""
        gesture = self._gesture
        if gesture is None or gesture.button != button:
            return None
        self._gesture = None
        if gesture.dragging or gesture.click_command is None:
            return None
        if gesture.moved >= self._threshold:
            return None
        return Click(gesture.click_command, x, y)
