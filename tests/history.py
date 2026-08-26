"""History: generischer Command-/Reversible-Action-Stack.

Bezug: V1_SPEC.md §10, Architecture Decision AD-003.

Architekturvertrag:

- History kennt nur ein minimales Command-Protocol (undo/redo), KEINE
  harte Abhängigkeit auf MeshOperation oder Mesh (§15 Punkt 5). Damit
  kann später z. B. eine Rig-Pose-Änderung dieselbe HistoryStack-Klasse
  verwenden, ohne dass diese Klasse geändert werden muss.
- Ein History-Eintrag entsteht ausschließlich über push(). Für
  interaktive Operationen (z. B. MoveOperation) ruft ausschließlich
  Operation.commit() push() auf - nie aus update() (siehe operation.py).
  Für atomare, nicht-interaktive Mutationen ohne Operation-Lebenszyklus
  (split_edge/collapse_edge/connect_vertices, siehe
  operations/topology.py MeshStateCommand) bauen Aufrufer das Command
  selbst und rufen push() direkt auf - Mesh selbst bleibt dabei bewusst
  ohne jede History-Abhängigkeit (§15 Punkt 5).
- Kein Undo-Baum, kein Merge, keine Cross-Subsystem-Transaktionen (§10) -
  ein einfacher linearer Stack genügt für V1.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Command(Protocol):
    """Minimales Interface für einen reversiblen History-Eintrag.

    Absichtlich nicht mesh-spezifisch: jede reversible Aktion aus einem
    beliebigen zukünftigen Subsystem kann dieses Protocol implementieren.
    """

    description: str

    def undo(self) -> None: ...

    def redo(self) -> None: ...


class HistoryStack:
    def __init__(self) -> None:
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []

    def push(self, command: Command) -> None:
        """Wird ausschließlich in Operation.commit() aufgerufen."""
        self._undo_stack.append(command)
        # Ein neuer Eintrag verwirft den Redo-Zweig (kein History-Baum, §10).
        self._redo_stack.clear()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def undo(self) -> None:
        if not self._undo_stack:
            return
        command = self._undo_stack.pop()
        command.undo()
        self._redo_stack.append(command)

    def redo(self) -> None:
        if not self._redo_stack:
            return
        command = self._redo_stack.pop()
        command.redo()
        self._undo_stack.append(command)

    def __len__(self) -> int:
        return len(self._undo_stack)
