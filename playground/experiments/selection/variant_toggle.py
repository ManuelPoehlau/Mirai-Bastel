"""AP-03 Phase 2 Variante B — Toggle (jeder Klick togglet, kein Modifier nötig)."""

from playground.experiment import Experiment
from playground.selector import SelectMode


class FaceSelectToggleExperiment(Experiment):
    id = "selection"
    name = "Selection"
    variant = "Toggle"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        self._app.select_mode = SelectMode.TOGGLE

    def deactivate(self) -> None:
        pass
