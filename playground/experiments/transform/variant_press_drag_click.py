"""AP-04 — Move Activation Variant C: Press-Drag-Click.

X/R/S einmal drücken → Mode wird aktiv
Erster Drag → Transform startet
Maustaste loslassen → Commit
ESC → Cancel
"""

from playground.experiment import Experiment


class PressDragClickVariant(Experiment):
    id = "transform"
    name = "Move Activation"
    variant = "Press-Drag-Click (key → drag → release)"
    activation = "press_drag_click"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
