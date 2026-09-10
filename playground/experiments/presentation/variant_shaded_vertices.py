from mirai.viewport.display import DisplayMode
from playground.experiments.presentation.base import PresentationExperiment


class ShadedVerticesVariant(PresentationExperiment):
    id = "presentation"
    name = "Presentation"
    variant = "Shaded + V"
    _mode = DisplayMode.SHADED
    _wireframe_overlay = False
    _show_vertices = True
