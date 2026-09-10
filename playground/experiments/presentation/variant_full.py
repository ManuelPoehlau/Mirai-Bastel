from mirai.viewport.display import DisplayMode
from playground.experiments.presentation.base import PresentationExperiment


class FullVariant(PresentationExperiment):
    id = "presentation"
    name = "Presentation"
    variant = "Shaded + Wire + V"
    _mode = DisplayMode.SHADED
    _wireframe_overlay = True
    _show_vertices = True
