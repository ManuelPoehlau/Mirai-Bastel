"""Knife Lab — Variant A: Live Preview.

Hover over an edge → split-point preview follows the cursor continuously.
Click commits the cut at the current cursor position.
"""

from playground.experiment import Experiment


class KnifeVariantA(Experiment):
    id = "knife"
    name = "Knife"
    variant = "A — Live Preview"
    activation = "live_preview"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
