"""PresentationExperiment — Basisklasse für AP-02.5 Darstellungs-Varianten.

Jede Variante setzt im activate()-Hook den gewünschten DisplayState
und show_vertices-Flag auf der PlaygroundApp. Der Konstruktor nimmt
die App-Referenz entgegen, damit die Variante keinen globalen State braucht.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mirai.viewport.display import DisplayMode, DisplayState
from playground.experiment import Experiment

if TYPE_CHECKING:
    from playground.app import PlaygroundApp


class PresentationExperiment(Experiment):
    """Basis für alle Presentation-Varianten.

    Unterklassen setzen _mode, _wireframe_overlay und _show_vertices
    als Klassenattribute und rufen super().activate() auf.
    """

    _mode: DisplayMode = DisplayMode.SHADED
    _wireframe_overlay: bool = False
    _show_vertices: bool = False

    def __init__(self, app: PlaygroundApp) -> None:
        self._app = app

    def activate(self) -> None:
        self._app.display_state.set_mode(self._mode)
        self._app.display_state.set_wireframe_overlay(self._wireframe_overlay)
        self._app.show_vertices = self._show_vertices

    def deactivate(self) -> None:
        pass
