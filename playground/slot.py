"""Experiment-Slot-System — WP-AP-02.

Minimale Infrastruktur zum Verwalten von Experiment-Varianten, Aktivieren
einzelner Varianten und Festhalten einer Artist-Entscheidung (KEEP / ITERATE /
REJECT) pro Variante.

Aufbau:
    Decision       — Enum der möglichen Entscheidungen
    VariantEntry   — Experiment + Decision + optionale Notizen
    ExperimentSlot — Container für eine Variantengruppe

Dateistruktur (Konvention):
    playground/experiments/<experiment_id>/variant_a.py
    playground/experiments/<experiment_id>/variant_b.py
    playground/experiments/<experiment_id>/decision.md   ← generate_decision_md()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Sequence

from playground.experiment import Experiment


class Decision(Enum):
    UNDECIDED = "UNDECIDED"
    KEEP = "KEEP"
    ITERATE = "ITERATE"
    REJECT = "REJECT"


@dataclass
class VariantEntry:
    """Variante innerhalb eines Experiment-Slots."""

    experiment: Experiment
    decision: Decision = Decision.UNDECIDED
    notes: str = ""


class ExperimentSlot:
    """Container für eine Gruppe von Experiment-Varianten.

    Verwaltet:
    - Liste von VariantEntry (jede Variante ist ein Experiment-Objekt)
    - Aktivierung einer Variante (deactivate old, activate new)
    - Decision (KEEP / ITERATE / REJECT) pro Variante
    - decision.md-Template-Generierung

    Die bestehende Experiment-Basisklasse (experiment.py) bleibt unverändert.
    ExperimentSlot ist ein reiner Container — kein eigenes Tool-, Input- oder
    History-System.
    """

    def __init__(self, *variants: VariantEntry) -> None:
        if not variants:
            raise ValueError("ExperimentSlot benötigt mindestens eine Variante.")
        self._variants: list[VariantEntry] = list(variants)
        self._active_index: int = 0

    # -- Aktive Variante --------------------------------------------------

    @property
    def active(self) -> VariantEntry:
        """Aktiver VariantEntry (Experiment + Decision)."""
        return self._variants[self._active_index]

    @property
    def active_experiment(self) -> Experiment:
        """Das Experiment-Objekt der aktiven Variante."""
        return self.active.experiment

    @property
    def active_index(self) -> int:
        return self._active_index

    # -- Variantenliste ---------------------------------------------------

    @property
    def variants(self) -> list[VariantEntry]:
        return list(self._variants)

    @property
    def variant_count(self) -> int:
        return len(self._variants)

    # -- Aktivierung ------------------------------------------------------

    def activate(self, index: int) -> None:
        """Variante per Index aktivieren.

        Ruft deactivate() auf dem alten Experiment und activate() auf dem
        neuen auf — analog PlaygroundApp.set_experiment().
        """
        if not 0 <= index < len(self._variants):
            raise IndexError(
                f"Variant-Index {index} außerhalb [0, {len(self._variants) - 1}]"
            )
        if index == self._active_index:
            return
        self.active.experiment.deactivate()
        self._active_index = index
        self.active.experiment.activate()

    # -- Decision ---------------------------------------------------------

    def set_decision(self, decision: Decision, notes: str = "") -> None:
        """Decision für die aktive Variante setzen."""
        self.active.decision = decision
        if notes:
            self.active.notes = notes

    # -- decision.md-Template ---------------------------------------------

    def generate_decision_md(self) -> str:
        """Git-freundliches decision.md-Template für alle Varianten.

        Format (per Roadmap WP-AP-02):
            # <Name>
            ## <Variant>
            Decision: KEEP / ITERATE / REJECT
            What felt better: ...
            What felt worse: ...
            Artist verdict: ...
        """
        exp_name = self.active_experiment.name
        sections: list[str] = [f"# {exp_name}", ""]

        for entry in self._variants:
            e = entry.experiment
            label = e.variant or e.id
            sections += [
                f"## {label}",
                "",
                f"Decision: {entry.decision.value}",
                "",
                f"Notes: {entry.notes or '—'}",
                "",
                "What felt better:",
                "- ",
                "",
                "What felt worse:",
                "- ",
                "",
                "Artist verdict:",
                "- ",
                "",
            ]

        return "\n".join(sections)

    def write_decision_md(self, directory: Path) -> Path:
        """decision.md in `directory` schreiben und Pfad zurückgeben.

        `directory` ist üblicherweise:
            playground/experiments/<experiment_id>/
        """
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "decision.md"
        path.write_text(self.generate_decision_md(), encoding="utf-8")
        return path
