from mirai.viewport.display import DisplayMode
from playground.experiments.presentation.base import PresentationExperiment


class WireframeVariant(PresentationExperiment):
    id = "presentation"
    name = "Presentation"
    variant = "Wireframe"
    _mode = DisplayMode.WIREFRAME
    _wireframe_overlay = False
    _show_vertices = False
