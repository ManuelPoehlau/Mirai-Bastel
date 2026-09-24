"""Lab-Dispatcher: aufgelöstes Command → Lab-Aktion (GL- und pyglet-frei).

Pfad: pyglet-Event → `mirai.pyglet_input` → `app.bindings.command_for(input,
SYMMETRY_LAB_CONTEXT)` → dieser Dispatcher. Das Fenster übersetzt nur Events
und reicht `Input` + Pixelkoordinaten durch; alles Weitere passiert hier,
damit es ohne GL-Kontext testbar ist.

Drag-/Klick-Semantik ist bewusst Lab-lokal (AD-013 A3 bleibt offen):

- Press löst das Command auf. `Orbit`/`Pan` halten diesen Zustand bis zum
  Release derselben Maustaste; Drag-Deltas gehen an die Kamera. Modifier, die
  während des Drags wechseln, ändern die Geste nicht.
- `Select` merkt sich den Press und wird bei Release ausgeführt, wenn die
  Bewegung unter `CLICK_THRESHOLD_PX` blieb (sonst verworfen — kein Box-Select
  in diesem Slice).
- Jedes andere Command (z. B. globale Defaults auf Tasten) ist ein No-op.
- Während eine Geste läuft, werden weitere Maus-Presses ignoriert.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_vertex

from .lab_bindings import SYMMETRY_LAB_CONTEXT

#: Wert und Messart (Manhattan-Summe der Drag-Deltas) wie
#: `playground/selector.py::CLICK_THRESHOLD` (Stand `47f821b`).
CLICK_THRESHOLD_PX = 5.0
#: Wie `playground/window.py::_camera_navigate` / `on_mouse_scroll`.
ORBIT_RAD_PER_PX = 0.005
ZOOM_IN_FACTOR = 0.9
ZOOM_OUT_FACTOR = 1.1


@dataclass
class _Gesture:
    command: str
    button: str
    moved: float = 0.0


class LabDispatcher:
    def __init__(self, app: Application, width: int = 1, height: int = 1) -> None:
        self.app = app
        self.width = width
        self.height = height
        self._gesture: Optional[_Gesture] = None

    @property
    def active_command(self) -> Optional[str]:
        """Command der laufenden Maus-Geste (`Orbit`/`Pan`/`Select`) oder None."""
        return self._gesture.command if self._gesture is not None else None

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def resolve(self, inp: Input) -> Optional[str]:
        return self.app.bindings.command_for(inp, SYMMETRY_LAB_CONTEXT)

    # -- Maus -------------------------------------------------------------

    def press(self, inp: Input) -> None:
        if inp.kind != "mouse" or self._gesture is not None:
            return
        command = self.resolve(inp)
        if command in (cmd.ORBIT, cmd.PAN, cmd.SELECT):
            self._gesture = _Gesture(command, inp.value)

    def drag(self, dx: float, dy: float) -> None:
        gesture = self._gesture
        if gesture is None:
            return
        gesture.moved += abs(dx) + abs(dy)
        if gesture.command == cmd.ORBIT:
            self.app.camera.orbit(-dx * ORBIT_RAD_PER_PX, -dy * ORBIT_RAD_PER_PX)
        elif gesture.command == cmd.PAN:
            self.app.camera.pan(dx, dy, self.width, self.height)

    def release(self, button: str, x: float, y: float) -> bool:
        """Beendet die Geste von `button`. True, wenn sich die Auswahl geändert hat."""
        gesture = self._gesture
        if gesture is None or gesture.button != button:
            return False
        self._gesture = None
        if gesture.command == cmd.SELECT and gesture.moved < CLICK_THRESHOLD_PX:
            return self.select_at(x, y)
        return False

    def scroll(self, inp: Optional[Input]) -> None:
        if inp is None or inp.kind != "wheel":
            return
        if self.resolve(inp) == cmd.ZOOM:
            self.app.camera.dolly(ZOOM_IN_FACTOR if inp.value == "UP" else ZOOM_OUT_FACTOR)

    # -- Auswahl ----------------------------------------------------------

    def select_at(self, x: float, y: float) -> bool:
        """Ersetzt die Vertex-Auswahl durch den nächsten Vertex, oder leert sie."""
        selection = self.app.scene.selection
        before = set(selection.vertices)
        vid = pick_nearest_vertex(
            self.app.camera, self.app.scene.mesh, x, y, self.width, self.height
        )
        if vid is None:
            selection.clear()
        else:
            selection.set({vid})
        return set(selection.vertices) != before
