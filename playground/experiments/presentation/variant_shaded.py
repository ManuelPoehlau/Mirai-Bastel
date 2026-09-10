from mirai.viewport.display import DisplayMode
from playground.experiments.presentation.base import PresentationExperiment


class ShadedVariant(PresentationExperiment):
    id = "presentation"
    name = "Presentation"
    variant = "Shaded"
    _mode = DisplayMode.SHADED
    _wireframe_overlay = False
    _show_vertices = False
