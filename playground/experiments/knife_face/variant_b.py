"""Knife Face Lab — Variant B: Immediate (control).

Interior clicks inside the *current* face are pending (non-mutating) steps;
the path applies in one mutation as soon as it reaches a vertex/edge of that
face. No interior start. Covers FC1-FC4 (discovery §2).
"""

from playground.experiment import Experiment
from playground.experiments.knife_face.engine import KnifeFaceImmediate


class KnifeFaceVariantB(Experiment):
    id = "knife_face"
    name = "Knife Face"
    variant = "B — Immediate (control)"
    activation = "immediate"
    session_cls = KnifeFaceImmediate

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
