"""AP-03 Phase 1 Baseline — Face Select Replace."""

from playground.experiment import Experiment
from playground.selector import SelectMode, SelectMethod


class FaceSelectReplaceExperiment(Experiment):
    id = "selection"
    name = "Selection"
    variant = "Replace"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        self._app.select_mode   = SelectMode.REPLACE
        self._app.select_method = SelectMethod.PICK

    def deactivate(self) -> None:
        pass
