from mirai.viewport.display import DisplayMode
from playground.experiments.presentation.base import PresentationExperiment


class FlatVariant(PresentationExperiment):
    id = "presentation"
    name = "Presentation"
    variant = "Flat Shaded"
    _mode = DisplayMode.FLAT_SHADED
    _wireframe_overlay = False
    _show_vertices = False
