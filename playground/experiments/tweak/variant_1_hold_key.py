"""Tweak Lab — Variant 1: Hold Key, self-deciding gesture.

X/R/S key-down + mouse motion >= CLICK_THRESHOLD → Tweak (key-up = commit).
X/R/S key-down + key-up without motion → persistent mode toggle.
ESC during Tweak → cancel.
"""

from playground.experiment import Experiment


class TweakV1HoldKey(Experiment):
    id = "tweak"
    name = "Tweak"
    variant = "V1-HoldKey (X/R/S, self-deciding)"
    tweak_variant = "v1"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
