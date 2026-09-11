"""AP-03 Phase 2 Variante A — Modifier-basiert (Shift=Add, Ctrl=Remove, Alt=Toggle)."""

from playground.experiment import Experiment
from playground.selector import SelectMode, SelectMethod


class FaceSelectModifierExperiment(Experiment):
    id = "selection"
    name = "Selection"
    variant = "Modifier (Shift/Ctrl/Alt)"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        self._app.select_mode   = SelectMode.MODIFIER
        self._app.select_method = SelectMethod.PICK

    def deactivate(self) -> None:
        pass
