"""Connect Lab — Baseline: Streifen-Semantik (heutiges Verhalten, unverändert)."""

from playground.experiment import Experiment
from playground.topology_tools.connect_edges import connect_selected_edges


class ConnectStripVariant(Experiment):
    id = "connect"
    name = "Connect"
    variant = "Streifen (nur Quads)"
    connect_fn = staticmethod(connect_selected_edges)

    def __init__(self, app) -> None:
        self._app = app
