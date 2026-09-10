"""AP-04 Phase 1 — Move Tool Variant.

Hotkey: X gedrückt halten + Drag = Move-Transform
Losgelassen → Commit
ESC während Drag → Cancel
"""

from playground.experiment import Experiment


class MoveVariant(Experiment):
    id = "transform"
    name = "Transform"
    variant = "Move (X + Drag)"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        # Die Move-Tool wird beim X-Press erstellt (window.py:on_key_press).
        # Hier nur als Marker für den aktiven Experiment.
        pass

    def deactivate(self) -> None:
        pass
