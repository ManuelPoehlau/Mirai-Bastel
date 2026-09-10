from mirai.viewport.display import DisplayMode
from playground.experiments.presentation.base import PresentationExperiment


class ShadedWireVariant(PresentationExperiment):
    id = "presentation"
    name = "Presentation"
    variant = "Shaded + Wire"
    _mode = DisplayMode.SHADED
    _wireframe_overlay = True
    _show_vertices = False
