"""AP-04 Phase 1 — Rotate Tool Variant.

Hotkey: R gedrückt halten + Drag = Rotate-Transform (Z-Achse)
Losgelassen → Commit
ESC während Drag → Cancel
"""

from playground.experiment import Experiment


class RotateVariant(Experiment):
    id = "transform"
    name = "Transform"
    variant = "Rotate (R + Drag)"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        # Die Rotate-Tool wird beim R-Press erstellt (window.py:on_key_press).
        # Hier nur als Marker für den aktiven Experiment.
        pass

    def deactivate(self) -> None:
        pass
