"""AP-04 — Move Activation Variant A: Hold.

X/R/S gehalten + Drag = Transform
Lostassen → Commit
ESC während Drag → Cancel
"""

from playground.experiment import Experiment


class HoldActivationVariant(Experiment):
    id = "transform"
    name = "Move Activation"
    variant = "Hold (key + drag + release)"
    activation = "hold"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
