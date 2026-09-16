"""EX-A — Articulation Slot: single variant (H02).

One variant only — a second variant (e.g. estimated vs. set pivot) would
introduce a second research variable, which is explicitly out of scope per
the EX-A Experiment Brief.
"""

from playground.experiment import Experiment


class ArticulationVariant(Experiment):
    id = "articulation"
    name = "Articulation"
    variant = "LMB drag (F = restore)"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
