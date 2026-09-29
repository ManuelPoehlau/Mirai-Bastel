"""Knife Face Lab — Variant Q5: Cross-Face (Variant D + segment planner).

D's collected session (mesh changes only at commit) plus cross-face segments:
a click outside the last point's faces cuts every visible face in between,
gaps (holes, borders, hidden stretches) are skipped like Blender does, and a
click on the snapped start point closes the chain without committing. See
`engine_q5.py` and this package's decision.md ("Q5 — Artist answers").
"""

from playground.experiment import Experiment
from playground.experiments.knife_face.engine_q5 import KnifeFaceCrossFace


class KnifeFaceVariantQ5(Experiment):
    id = "knife_face"
    name = "Knife Face"
    variant = "Q5 — Cross-Face (D + planner)"
    activation = "cross_face"
    session_cls = KnifeFaceCrossFace

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
