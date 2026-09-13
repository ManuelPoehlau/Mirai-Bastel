"""Tweak Lab — Variant 2: Silo-style (Ctrl+LMB, early-releasable Ctrl).

Ctrl+LMB press → Ctrl may be released immediately → LMB held through drag
→ Tweak using currently selected persistent mode. LMB-release = commit.
ESC → cancel.
"""

from playground.experiment import Experiment


class TweakV2Silo(Experiment):
    id = "tweak"
    name = "Tweak"
    variant = "V2-Silo (Ctrl+LMB)"
    tweak_variant = "v2"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
