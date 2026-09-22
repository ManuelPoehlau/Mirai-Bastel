"""Connect Lab — Discovery-Variante: pro Face (Wings-artig), Face-Größe egal."""

from playground.experiment import Experiment
from playground.topology_tools.connect_per_face import connect_selected_edges_per_face


class ConnectPerFaceVariant(Experiment):
    id = "connect"
    name = "Connect"
    variant = "Pro Face (Wings-artig)"
    connect_fn = staticmethod(connect_selected_edges_per_face)

    def __init__(self, app) -> None:
        self._app = app
