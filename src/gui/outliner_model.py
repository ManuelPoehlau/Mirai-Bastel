"""Outliner-Panel, reine Logik (AD-030, 2026-11-07, `PROVISIONAL`).

Kein pyglet, kein imgui: nur Funktionen über Scene und Selection. Das Panel zeichnet `rows(...)` und fragt bei einem
Klick `click_selection` / `eye_plan`; es hält keinen Dokumentzustand (Core -> Viewport, nie zurück). Änderungen laufen
über `Application.select_objects` und `Application.set_objects_hidden` (beide ein Aufruf des ObjectController, Undo wie
die Tasten Ctrl+H / Alt+H).
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


@dataclass(frozen=True)
class BoneRow:
    bone_id: object
    name: str
    depth: int
    has_children: bool
    current: bool  # die Zeile des aktuellen Knochens (hervorgehoben)
    hidden: bool


def bone_rows(rig, current, hidden: Iterable = (), collapsed: frozenset = frozenset()) -> list[BoneRow]:
    """Die Knochen als Baum nach Elternknochen (Wurzeln und Geschwister nach ID, Tiefensuche); Kinder eingeklappter
    Knochen fehlen. Ohne Rig leer."""
    if rig is None:
        return []
    off = set(hidden)
    out: list[BoneRow] = []

    def emit(bone, depth: int) -> None:
        kids = rig.children(bone.id)
        out.append(BoneRow(bone.id, bone.name, depth, bool(kids), bone.id == current, bone.id in off))
        if bone.id not in collapsed:
            for kid in kids:
                emit(rig.bone(kid), depth + 1)

    for bone in rig.bones:
        if bone.parent is None:
            emit(bone, 0)
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
    """Was ein Klick auf das Auge tut: `hide` True/False auf `ids`, oder (`ids` leer) nichts, nur der Hinweis."""

    ids: tuple = ()
    hide: bool = True
    note: str = ""


def eye_plan(row: Row) -> EyePlan:
    """Auge-Klick -> Plan: ein sichtbares Objekt wird ausgeblendet (außer das Edit-Objekt und seine Gruppen), ein
    ausgeblendetes wieder eingeblendet."""
    if row.hidden:
        return EyePlan((row.object_id,), False)
    if not row.can_hide:
        return EyePlan((), True, "hält das Edit-Objekt, bleibt sichtbar")
    return EyePlan((row.object_id,), True)


def group_of(row: Row) -> str:
    return "Gruppe" if row.is_group else ("Reference" if row.is_reference else "Objekt")
