"""Tweak Lab — Variant 4: Hold Ctrl + drag (no LMB needed).

Ctrl held + mouse motion → Tweak using the currently selected persistent mode.
Ctrl-release = commit. ESC → cancel.
"""

from playground.experiment import Experiment


class TweakV4HoldCtrl(Experiment):
    id = "tweak"
    name = "Tweak"
    variant = "V4-HoldCtrl (Ctrl + move)"
    tweak_variant = "v4"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
