"""Knife Lab — Variant B: Press-Slide-Release.

Mouse-down on a valid edge arms a slide: the preview point follows the cursor
along the edge while LMB is held.  Release on a valid edge target commits the
cut at the release position; release off a valid target cancels.
"""

from playground.experiment import Experiment


class KnifeVariantB(Experiment):
    id = "knife"
    name = "Knife"
    variant = "B — Press-Slide-Release"
    activation = "press_slide_release"

    def __init__(self, app) -> None:
        self._app = app

    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass
