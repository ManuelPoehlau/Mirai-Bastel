"""AP-05 — Extrude Variante 2: E + Drag + LMB.

E drücken → begin, LMB-Drag → live update, LMB release → commit, ESC → cancel.
"""

from playground.experiment import Experiment


class ExtrudeLmbVariant(Experiment):
    id = "topology"
    name = "Extrude"
    variant = "LMB (E + drag + click)"
    activation = "lmb"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
