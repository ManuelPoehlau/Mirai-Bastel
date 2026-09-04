"""Material-Zustand für das V0.2 Experiment.

Material ist eine eigene Update-Kategorie. Eine Material-Änderung darf ihre
eigenen Ressourcen/Parameter aktualisieren (Uniform-Paket), darf aber NICHT
automatisch Geometry invalidieren. Der Beweis: Der Geometry-Rebuild-Zähler
bleibt bei einer reinen Material-Änderung bei 0.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MaterialState:
    # Minimales Uniform-Paket (RGBA-Farbe der Base-Geometrie)
    base_color: tuple[float, float, float, float] = (0.6, 0.7, 0.9, 1.0)
    # eigener Uniform-Wert fürs Highlight-Overlay (Getrenntheit sichtbar)
    highlight_color: tuple[float, float, float, float] = (1.0, 0.4, 0.2, 1.0)

    def set_base_color(self, rgba: tuple[float, float, float, float]) -> None:
        self.base_color = tuple(float(c) for c in rgba)

    def set_highlight_color(self, rgba: tuple[float, float, float, float]) -> None:
        self.highlight_color = tuple(float(c) for c in rgba)

    def uniform_packet(self) -> list[float]:
        """Flaches 8-float-Paket (base_rgba + highlight_rgba)."""
        return list(self.base_color) + list(self.highlight_color)
