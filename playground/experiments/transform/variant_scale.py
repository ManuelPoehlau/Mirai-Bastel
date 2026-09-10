"""AP-04 Phase 1 — Scale Tool Variant.

Hotkey: S gedrückt halten + Drag = Scale-Transform (Z-Achse)
Losgelassen → Commit
ESC während Drag → Cancel
"""

from playground.experiment import Experiment


class ScaleVariant(Experiment):
    id = "transform"
    name = "Transform"
    variant = "Scale (S + Drag)"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        # Die Scale-Tool wird beim S-Press erstellt (window.py:on_key_press).
        # Hier nur als Marker für den aktiven Experiment.
        pass

    def deactivate(self) -> None:
        pass
