"""Experiment-Basisklasse — minimales Interface für WP-AP-02.

Jedes Playground-Experiment implementiert (oder überschreibt) dieses
Interface. Der Default-Zustand ist "none" — kein aktives Experiment.
"""

from __future__ import annotations


class Experiment:
    """Minimales Interface für ein Playground-Experiment.

    WP-AP-01: Nur Interface, keine Logik. Konkrete Experimente
    (WP-AP-02+) erben von dieser Klasse und überschreiben die Hooks.
    """

    id: str = "none"
    name: str = "No Experiment"
    variant: str = ""

    def activate(self) -> None:
        """Wird aufgerufen, wenn dieses Experiment aktiv gesetzt wird."""

    def deactivate(self) -> None:
        """Wird aufgerufen, wenn ein anderes Experiment übernimmt."""

    def update(self, dt: float) -> None:
        """Optionaler per-Frame-Tick (dt in Sekunden)."""

    def draw(self) -> None:
        """Optionaler Zeichen-Hook (nach dem Hauptrender, vor HUD)."""
