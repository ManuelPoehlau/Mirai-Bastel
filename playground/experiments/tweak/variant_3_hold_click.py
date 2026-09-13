"""Tweak Lab — Variant 3: Hold X/R/S + LMB click, early-releasable key.

X/R/S held AND LMB pressed → drag starts Tweak with the corresponding transform.
X/R/S may be released mid-drag without cancelling — LMB alone governs.
LMB-release = commit. ESC → cancel.
"""

from playground.experiment import Experiment


class TweakV3HoldClick(Experiment):
    id = "tweak"
    name = "Tweak"
    variant = "V3-HoldClick (X/R/S + LMB)"
    tweak_variant = "v3"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
