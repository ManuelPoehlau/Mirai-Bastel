"""AP-03 Phase 1 / Phase 2 Baseline — Face Select (Replace, explizit)."""

from playground.experiment import Experiment
from playground.selector import SelectMode


class FaceSelectReplaceExperiment(Experiment):
    id = "selection"
    name = "Selection"
    variant = "Replace"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        self._app.select_mode = SelectMode.REPLACE

    def deactivate(self) -> None:
        pass
