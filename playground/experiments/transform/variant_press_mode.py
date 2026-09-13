"""AP-04 — Move Activation Variant B: Press-Mode.

X/R/S einmal drücken → Move/Rotate/Scale Mode wird aktiv (persistent)
Drag → Transform ausführen
Zweites Drücken derselben Taste → Commit
ESC → Cancel
"""

from playground.experiment import Experiment


class PressModeVariant(Experiment):
    id = "transform"
    name = "Move Activation"
    variant = "Press-Mode (key → drag → key again)"
    activation = "press_mode"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
