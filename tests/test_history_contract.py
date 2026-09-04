"""HistoryStack: Vertragstests des generischen Command-Stacks (WP-04-Verification).

Bezug: src/core/history.py — Architekturvertrag gemäß V1_SPEC.md §10 und AD-003.

Geprüft wird der dokumentierte Stack-Vertrag unabhängig von einer konkreten
Operation bzw. Mesh-Mutation:

- push() macht can_undo() wahr, can_redo() bleibt falsch.
- undo()/redo() bewegen Einträge LIFO zwischen Undo- und Redo-Stack.
- Ein neuer push() verwirft den Redo-Zweig (kein History-Baum).
- undo()/redo() auf leeren Stacks sind No-ops ohne Fehler.
- Das Command-Protocol ist das einzige, was die History über die Einträge
  wissen muss (description/undo/redo) — kein Mesh-Bezug im Vertrag.

Ausführen: python -m unittest tests.test_history_contract -v
"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401 — Produktionspfad src/core/

from core.history import Command, HistoryStack


class _RecordingCommand:
    """Minimales Command mit aufrufbarer description — erfüllt das Protocol strukturell."""

    def __init__(self, name: str = "Test Command") -> None:
        self.description = name
        self.undo_calls: list[str] = []
        self.redo_calls: list[str] = []

    def undo(self) -> None:
        self.undo_calls.append(self.description)

    def redo(self) -> None:
        self.redo_calls.append(self.description)


class HistoryStackContractTests(unittest.TestCase):
    def test_empty_stack_has_no_undo_no_redo(self) -> None:
        history = HistoryStack()
        self.assertFalse(history.can_undo())
        self.assertFalse(history.can_redo())
        self.assertEqual(len(history), 0)

    def test_undo_on_empty_stack_is_noop(self) -> None:
        # Dokumentierter No-op: kein Fehler, nichts passiert.
        history = HistoryStack()
        history.undo()
        history.undo()
        self.assertFalse(history.can_undo())
        self.assertFalse(history.can_redo())

    def test_redo_on_empty_stack_is_noop(self) -> None:
        history = HistoryStack()
        history.redo()
        history.redo()
        self.assertFalse(history.can_undo())
        self.assertFalse(history.can_redo())

    def test_push_enables_undo_and_clears_redo(self) -> None:
        history = HistoryStack()
        a, b = _RecordingCommand("A"), _RecordingCommand("B")
        history.push(a)
        history.undo()  # A → Redo
        self.assertTrue(history.can_redo())
        history.push(b)  # Neuer Eintrag verwirft den Redo-Zweig
        self.assertTrue(history.can_undo())
        self.assertFalse(history.can_redo())

    def test_undo_redo_roundtrip_calls_command(self) -> None:
        history = HistoryStack()
        command = _RecordingCommand("Move Vertices")
        history.push(command)  # type: ignore[arg-type]  # strukturelles Command-Protocol
        history.undo()
        self.assertEqual(command.undo_calls, ["Move Vertices"])
        self.assertTrue(history.can_redo())
        history.redo()
        self.assertEqual(command.redo_calls, ["Move Vertices"])
        self.assertTrue(history.can_undo())

    def test_lifo_ordering_after_undo_and_redo(self) -> None:
        history = HistoryStack()
        a, b, c = _RecordingCommand("A"), _RecordingCommand("B"), _RecordingCommand("C")
        history.push(a)
        history.push(b)
        history.push(c)

        history.undo()
        self.assertEqual(c.undo_calls, ["C"])
        history.undo()
        self.assertEqual(b.undo_calls, ["B"])
        self.assertFalse(a.undo_calls)
        self.assertTrue(history.can_undo())

        # Redo stellt in umgekehrter Reihenfolge wieder her.
        history.redo()
        self.assertEqual(b.redo_calls, ["B"])
        history.redo()
        self.assertEqual(c.redo_calls, ["C"])

    def test_undo_after_push_discards_redo_branch(self) -> None:
        # Kern-Vertrag (history.py): „Ein neuer Eintrag verwirft den Redo-Zweig."
        history = HistoryStack()
        a, b = _RecordingCommand("A"), _RecordingCommand("B")
        history.push(a)
        history.push(b)
        history.undo()  # B → Redo
        self.assertTrue(history.can_redo())

        # Neue Aktion: den Redo-Zweig sofort leeren.
        history.push(a)
        self.assertFalse(history.can_redo())

        # Selbst über vollständiges Undo/Redo hinweg wird B nie wieder
        # redo()-ed — der Redo-Zweig bestand nach dem Push nur noch aus a'/a.
        history.undo()  # a' → Redo
        history.undo()  # a  → Redo
        self.assertTrue(history.can_redo())
        history.redo()
        history.redo()
        self.assertFalse(history.can_redo())
        self.assertEqual(b.redo_calls, [], "B wurde mit dem Redo-Zweig verworfen")

    def test_len_counts_only_undo_entries(self) -> None:
        history = HistoryStack()
        a, b = _RecordingCommand("A"), _RecordingCommand("B")
        history.push(a)
        history.push(b)
        self.assertEqual(len(history), 2)
        history.undo()
        self.assertEqual(len(history), 1)

    def test_command_description_is_preserved(self) -> None:
        history = HistoryStack()
        command = _RecordingCommand("Scale Vertices")
        history.push(command)  # type: ignore[arg-type]  # strukturelles Command-Protocol
        history.undo()
        history.redo()
        self.assertEqual(command.description, "Scale Vertices")

    def test_protocol_compliance_via_runtime_checkable(self) -> None:
        # Das Command-Protocol (runtime_checkable) ist der einzige Vertrag,
        # den history.py über Einträge kennt.
        self.assertTrue(isinstance(_RecordingCommand("X"), Command))


if __name__ == "__main__":
    unittest.main()