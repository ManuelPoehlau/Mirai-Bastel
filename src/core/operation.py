"""Operation: generischer Interactive-Lifecycle.

Bezug: V1_SPEC.md §4 (Transform), Architecture Decision AD-003.

Architekturvertrag:

- Der Lifecycle begin() -> update()* -> commit()|cancel() ist bewusst
  NICHT mesh-spezifisch typisiert (§15 Punkt 4). OperationContext trägt
  ein generisches `target`-Feld statt eines hart codierten `mesh`-Feldes,
  damit ein späteres Rig-/Pose-/Animation-System denselben Vertrag nutzen
  kann.
- update() arbeitet für V1 bewusst direkt am Live-Zustand (siehe
  Diskussion AD-003) - keine separate Preview-Kopie. Das ist eine
  bewusste V1-Vereinfachung, keine Dauerentscheidung.
- update()-Semantik ist festgeschrieben als INKREMENTELL: jeder
  update(**kwargs)-Aufruf wendet sein Argument relativ zum aktuellen
  Live-Zustand an (Zustand nach dem letzten update()), NICHT relativ zum
  begin()-Snapshot. Fünf aufeinanderfolgende update(delta=(0.1,0,0))-
  Aufrufe verschieben also insgesamt um (0.5,0,0), nicht um (0.1,0,0).
  Dieser Vertrag gilt für die Basisklasse und muss von jeder konkreten
  Operation eingehalten werden (siehe MoveOperation._on_update sowie
  test_ad003_update_is_incremental in tests/test_core.py). Eine künftige
  Operation, die stattdessen eine absolute, gegen den begin()-Snapshot
  gemessene Semantik braucht, muss das explizit und sichtbar abweichend
  dokumentieren - sonst gilt implizit inkrementell.
- Ein History-Eintrag entsteht ausschließlich in commit(), nie in
  update(). Das verhindert strukturell, dass ein Drag mit vielen
  update()-Aufrufen viele History-Einträge erzeugt.
- Event-/Redraw-Benachrichtigung wird hier bewusst nicht implementiert
  (V1 hat noch keinen Viewport) - der Haken (`_on_update`) ist aber genau
  die Stelle, an der ein späteres System ein "dirty"-Flag statt eines
  Events pro Aufruf setzen würde.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .history import HistoryStack, Command
from .selection import Selection


@dataclass
class OperationContext:
    """Generischer Kontext für eine Operation.

    `target` ist bewusst generisch (nicht `mesh: Mesh`) - siehe §15
    Punkt 4. V1 übergibt hier praktisch immer ein Mesh, aber die
    Operation-Basisklasse selbst erzwingt das nicht.
    """

    target: Any
    selection: Selection
    history: HistoryStack
    params: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.params is None:
            self.params = {}


class OperationStateError(RuntimeError):
    """Lifecycle-Methode wurde im falschen Zustand aufgerufen."""


class Operation(ABC):
    """Basisklasse für interaktive Operationen.

    Konkrete Operationen implementieren die vier `_on_*`-Haken, nicht die
    öffentlichen Lifecycle-Methoden direkt - so bleibt der Vertrag
    (genau ein History-Eintrag in commit(), kein History-Eintrag in
    update()/cancel()) an einer einzigen Stelle erzwungen.
    """

    def __init__(self, context: OperationContext) -> None:
        self.context = context
        self._active = False

    def begin(self) -> None:
        if self._active:
            raise OperationStateError("Operation ist bereits aktiv.")
        self._on_begin(self.context)
        self._active = True

    def update(self, **kwargs) -> None:
        if not self._active:
            raise OperationStateError("update() ohne vorheriges begin().")
        self._on_update(**kwargs)

    def commit(self) -> Command | None:
        if not self._active:
            raise OperationStateError("commit() ohne vorheriges begin().")
        command = self._on_commit()
        self._active = False
        if command is not None:
            self.context.history.push(command)
        return command

    def cancel(self) -> None:
        if not self._active:
            raise OperationStateError("cancel() ohne vorheriges begin().")
        self._on_cancel()
        self._active = False

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Von konkreten Operationen zu implementieren
    # ------------------------------------------------------------------

    @abstractmethod
    def _on_begin(self, context: OperationContext) -> None:
        """Ausgangszustand erfassen (Snapshot)."""

    @abstractmethod
    def _on_update(self, **kwargs) -> None:
        """Live-Zustand verändern. Darf NICHT die History berühren."""

    @abstractmethod
    def _on_commit(self) -> Command | None:
        """Diff aus Snapshot vs. aktuellem Zustand bilden und als Command
        zurückgeben (oder None, falls es nichts zu committen gibt, z. B.
        wenn sich während update() nichts geändert hat)."""

    @abstractmethod
    def _on_cancel(self) -> None:
        """Live-Zustand auf den begin()-Snapshot zurücksetzen."""
