"""AP-03 Phase 3 / Variante C — Box-Select (LMB-Drag = Rechteck)."""

from playground.experiment import Experiment
from playground.selector import SelectMode, SelectMethod


class BoxSelectExperiment(Experiment):
    id = "selection"
    name = "Selection"
    variant = "Box"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        self._app.select_method = SelectMethod.BOX

    def deactivate(self) -> None:
        pass
