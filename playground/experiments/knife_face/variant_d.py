"""Knife Face Lab — Variant D: Collected (Silo-like, applied at commit).

Every click (vertex, edge point, face-interior point) only extends a virtual
path; the mesh changes only on commit (Enter, click outside, or click on the
first point = close + commit). Interior start allowed. Covers FC1-FC4 plus
the closed-shape stand-in (discovery §2, §1 Silo evidence).
"""

from playground.experiment import Experiment
from playground.experiments.knife_face.engine import KnifeFaceCollected


class KnifeFaceVariantD(Experiment):
    id = "knife_face"
    name = "Knife Face"
    variant = "D — Collected (applied at commit)"
    activation = "collected"
    session_cls = KnifeFaceCollected

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
