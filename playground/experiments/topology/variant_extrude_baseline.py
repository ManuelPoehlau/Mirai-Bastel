"""AP-05 — Topology Slot: Baseline Extrude (einzige Variante).

Dünner Experiment-Wrapper für den 'topology'-Slot in window.py.
Die eigentliche Tool-Logik liegt in playground/topology_tools/extrude.py.
"""

from playground.experiment import Experiment


class ExtrudeBaselineVariant(Experiment):
    id = "topology"
    name = "Extrude"
    variant = "Baseline (E + drag + LMB)"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
