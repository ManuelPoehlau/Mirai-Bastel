"""Minimales Tool-Framework für die Produktions-Application.

Vertrag: INPUT_COMMAND_TOOL_CONTRACT.md — ein Tool besitzt temporären
Interaktions-/Editorzustand, keine persistente Modell-Mutation. Die
eigentliche Domain-Mutation bleibt in der Core-Operation
(Operation / MoveOperation / RotateOperation / ScaleOperation).

Bewusst klein und pyglet-frei:

- kein Plugin-/Tool-Registry-Framework;
- keine Dependency Injection;
- keine Command Palette;
- keine Multi-Window-Orchestrierung.

Lebenszyklus:

    IDLE --activate--> ACTIVE --begin--> INTERACTING
                                         ├── update*
                                         ├── commit --> ACTIVE
                                         └── cancel --> ACTIVE
    ACTIVE --deactivate--> IDLE

Regeln:

- update() ist nur im Zustand INTERACTING erlaubt.
- commit() beendet die Interaktion; die History-Grenze entsteht exakt in
  der Core-Operation (genau ein Eintrag pro Interaktion).
- cancel() stellt den Vorzustand wieder her und erzeugt keine History.
- deactivate() während INTERACTING ist verboten (muss erst durch
  commit()/cancel() beendet werden) — der ToolManager errzwingt das
  automatisch, damit kein stale Drag-/Tool-State hängen bleibt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any


class ToolState(Enum):
    """Externe Tool-Zustände (WP-02 §8)."""

    IDLE = auto()
    ACTIVE = auto()
    INTERACTING = auto()


class ToolStateError(RuntimeError):
    """Lifecycle-Methode eines Tools wurde im falschen Zustand aufgerufen."""


class Tool(ABC):
    """Basisklasse für interaktive Tools (temporärer Editor-Zustand).

    Konkrete Tools implementieren die `_on_*`-Hooks, nicht die öffentlichen
    Lifecycle-Methoden — so bleibt der Vertrag (kein stale State, exakte
    History-Grenze in commit) an einer einzelnen Stelle erzwungen.
    """

    def __init__(self) -> None:
        self._state = ToolState.IDLE

    # ------------------------------------------------------------------
    # Zustand (öffentlich, lesend)
    # ------------------------------------------------------------------

    @property
    def state(self) -> ToolState:
        return self._state

    @property
    def is_active(self) -> bool:
        return self._state is not ToolState.IDLE

    @property
    def is_interacting(self) -> bool:
        return self._state is ToolState.INTERACTING

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def activate(self) -> None:
        """IDLE → ACTIVE: Tool wird aktiviert (noch keine Interaktion)."""
        if self._state is not ToolState.IDLE:
            raise ToolStateError(
                f"activate() nur aus IDLE (state={self._state.name})."
            )
        self._on_activate()
        self._state = ToolState.ACTIVE

    def begin(self, **params: Any) -> None:
        """ACTIVE → INTERACTING: Interaktion starten (Operation begin)."""
        if self._state is not ToolState.ACTIVE:
            raise ToolStateError(
                f"begin() nur aus ACTIVE (state={self._state.name})."
            )
        self._on_begin(**params)
        self._state = ToolState.INTERACTING

    def update(self, **kwargs: Any) -> None:
        """Pointer-/Modifier-Update verarbeiten (nur während INTERACTING)."""
        if self._state is not ToolState.INTERACTING:
            raise ToolStateError(
                f"update() nur während INTERACTING (state={self._state.name})."
            )
        self._on_update(**kwargs)

    def commit(self) -> Any:
        """INTERACTING → ACTIVE: Interaktion bestätigen (Operation commit).

        Liefert das von der Operation erzeugte History-Command (oder None,
        wenn sich nichts geändert hat). Ein neuer History-Eintrag entsteht
        ausschließlich hier über die Core-Operation — nie in update().
        """
        if self._state is not ToolState.INTERACTING:
            raise ToolStateError(
                f"commit() nur während INTERACTING (state={self._state.name})."
            )
        result = self._on_commit()
        self._state = ToolState.ACTIVE
        return result

    def cancel(self) -> None:
        """INTERACTING → ACTIVE: Interaktion abbrechen (Operation cancel).

        Stellt den Vorzustand wieder her und erzeugt keinen History-Eintrag.
        """
        if self._state is not ToolState.INTERACTING:
            raise ToolStateError(
                f"cancel() nur während INTERACTING (state={self._state.name})."
            )
        self._on_cancel()
        self._state = ToolState.ACTIVE

    def deactivate(self) -> None:
        """ACTIVE/IDLE → IDLE: Tool deaktivieren.

        Während einer laufenden Interaktion verboten — commit()/cancel()
        müssen zuerst beendet haben. verhindert stale interaktiven State.
        """
        if self._state is ToolState.INTERACTING:
            raise ToolStateError(
                "deactivate() während einer laufenden Interaktion nicht "
                "erlaubt — erst commit()/cancel() ausführen (kein stale State)."
            )
        self._on_deactivate()
        self._state = ToolState.IDLE

    # ------------------------------------------------------------------
    # Hooks für konkrete Tools
    # ------------------------------------------------------------------

    def _on_activate(self) -> None:
        """Tool wird aktiv. Standard: nichts."""

    @abstractmethod
    def _on_begin(self, **params: Any) -> None:
        """Interaktion starten (z. B. Operation.begin())."""

    @abstractmethod
    def _on_update(self, **kwargs: Any) -> None:
        """Pointer-/Modifier-Update verarbeiten (z. B. Operation.update())."""

    @abstractmethod
    def _on_commit(self) -> Any:
        """Interaktion bestätigen (z. B. Operation.commit()) → Command/None."""

    @abstractmethod
    def _on_cancel(self) -> None:
        """Interaktion abbrechen (z. B. Operation.cancel()) — Vorzustand exakt."""

    def _on_deactivate(self) -> None:
        """Tool-Zustand aufräumen. Darf die Model-History nicht berühren."""


