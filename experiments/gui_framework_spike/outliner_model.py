"""Outliner-Panel, reine Logik (GUI-Framework-Spike, 2026-11-07, `PROVISIONAL`).

Kein pyglet, kein imgui: nur Funktionen über Scene und Selection. Das Panel zeichnet `rows(...)` und fragt bei einem
Klick `click_selection` / `eye_plan`; es hält keinen Dokumentzustand (Brief: Core -> Viewport, nie zurück).
Alle Änderungen laufen über die vorhandenen Object-Commands (`commands.HIDE_OBJECTS`, `SHOW_ALL_OBJECTS`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from core import ObjectState
from mirai.interaction import commands

# Modifier wie im Viewport (`ObjectController.select_at`): plain = ersetzen, Shift = hinzufügen, Ctrl = entfernen,
# Alt = umschalten.
MODIFIER_COMMANDS = {
    frozenset(): commands.SELECT,
    frozenset({"shift"}): commands.SELECT_ADD,
    frozenset({"ctrl"}): commands.SELECT_REMOVE,
    frozenset({"alt"}): commands.SELECT_TOGGLE,
}


@dataclass(frozen=True)
class Row:
    object_id: object
    name: str
    depth: int
    is_group: bool
    is_reference: bool
    is_edit: bool
    selected: bool
    hidden: bool  # das Objekt selbst
    effectively_hidden: bool  # oder eine seiner Gruppen
    can_hide: bool  # False: Edit-Objekt oder Gruppe, die es hält (`ObjectController._kept_visible`)


def rows(scene, selected: Iterable, collapsed: frozenset = frozenset()) -> list[Row]:
    """Die Zeilen in Anzeigereihenfolge: oberste Ebene nach ID, Mitglieder eingerückt unter ihrer Gruppe (Tiefensuche).
    Mitglieder einer eingeklappten Gruppe fehlen."""
    chosen = set(selected)
    objects = scene.objects
    edit = scene.edit_object_id
    keep = {edit, *(group.id for group in scene.ancestors_of(edit))}
    out: list[Row] = []

    def emit(obj, depth: int) -> None:
        out.append(
            Row(
                object_id=obj.id,
                name=obj.name,
                depth=depth,
                is_group=obj.state is ObjectState.GROUP,
                is_reference=obj.state is ObjectState.REFERENCE,
                is_edit=obj.id == edit,
                selected=obj.id in chosen,
                hidden=obj.hidden,
                effectively_hidden=scene.is_hidden(obj.id),
                can_hide=obj.id not in keep,
            )
        )
        if obj.state is ObjectState.GROUP and obj.id not in collapsed:
            for child in sorted(scene.children_of(obj.id), key=lambda o: int(o.id)):
                emit(child, depth + 1)

    for obj in sorted(objects.values(), key=lambda o: int(o.id)):
        if obj.parent is None or obj.parent not in objects:
            emit(obj, 0)
    return out


def click_selection(current: Iterable, clicked, modifiers: Iterable[str]) -> tuple[str, set]:
    """Klick auf eine Zeile -> (Select-Command des Viewports, neue Auswahl). Dieselbe Tabelle wie ein Viewport-Klick."""
    mods = frozenset(m for m in modifiers if m in ("shift", "ctrl", "alt"))
    command = MODIFIER_COMMANDS.get(mods, commands.SELECT)  # unbekannte Kombination = plain, wie der Viewport
    selection = set(current)
    if command == commands.SELECT:
        selection = {clicked}
    elif command == commands.SELECT_ADD:
        selection.add(clicked)
    elif command == commands.SELECT_REMOVE:
        selection.discard(clicked)
    else:
        selection.symmetric_difference_update({clicked})
    return command, selection


@dataclass(frozen=True)
class EyePlan:
    """Was ein Klick auf das Auge tut: erst die Auswahl auf `select` setzen (None = unverändert), dann `command`."""

    select: frozenset | None
    command: str | None
    note: str = ""


def eye_plan(row: Row) -> EyePlan:
    """Auge-Klick -> Plan. Ausblenden: `HideObjects` wirkt auf die Auswahl, also zuerst genau dieses Objekt wählen.
    Einblenden: es gibt keinen Command für ein einzelnes Objekt (nur `ShowAllObjects`) - Befund im AD."""
    if not row.hidden:
        if not row.can_hide:
            return EyePlan(None, None, "hält das Edit-Objekt, bleibt sichtbar")
        return EyePlan(frozenset({row.object_id}), commands.HIDE_OBJECTS)
    return EyePlan(None, commands.SHOW_ALL_OBJECTS, "Einzel-Einblenden fehlt: zeigt alle")


def group_of(row: Row) -> str:
    return "Gruppe" if row.is_group else ("Reference" if row.is_reference else "Objekt")
