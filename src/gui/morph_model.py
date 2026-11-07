"""Morph-Panel, reine Logik (AD-030 §13, Manu 2026-11-07, `PROVISIONAL`).

Kein pyglet, kein imgui: nur Lesen über die öffentlichen `Application.morph_*`-Zugriffe. Das Panel zeichnet `state(app)`
und ruft bei einem Klick dieselben Wege wie die Tasten (`select_morph_target`, `set_morph_weight`, `edit_morph_target`,
...); es hält keinen Dokumentzustand. Gewichte und Solo sind Ansicht (kein Undo, nicht gespeichert), Neu / Umbenennen /
Löschen je ein Undo-Schritt.
"""

from __future__ import annotations

from dataclasses import dataclass

from mirai.morph_targets import MAX_TARGETS


@dataclass(frozen=True)
class MorphRow:
    lid: object
    name: str
    weight: int
    current: bool
    editing: bool  # die Bearbeitungsansicht (Tab) zeigt dieses Ziel
    solo: bool


@dataclass(frozen=True)
class MorphPanelState:
    object_name: str
    rows: tuple[MorphRow, ...]
    view_open: bool  # die Bearbeitungsansicht eines Ziels ist das Edit-Objekt
    object_mode: bool  # Modus 4: "Bearbeiten" geht nur aus 1/2/3

    @property
    def has_targets(self) -> bool:
        return bool(self.rows)

    @property
    def can_lifecycle(self) -> bool:
        """Neu / Umbenennen / Löschen laufen nur an der Basis (die Controller lehnen sie in der Ansicht ab)."""
        return not self.view_open

    @property
    def can_create(self) -> bool:
        return self.can_lifecycle and len(self.rows) < MAX_TARGETS

    @property
    def can_edit(self) -> bool:
        """Der Knopf "Bearbeiten" (Tab): aus 1/2/3; "Zurück" in der Ansicht immer."""
        return self.view_open or not self.object_mode

    @property
    def count_text(self) -> str:
        return f"{len(self.rows)} / {MAX_TARGETS} Ziele"

    @property
    def header(self) -> str:
        editing = next((r for r in self.rows if r.editing), None)
        where = f"Ziel {editing.name!r} daneben" if editing is not None else "Basis"
        return f"{self.object_name} · {where}"

    @property
    def current(self) -> MorphRow | None:
        return next((r for r in self.rows if r.current), None)


def state(app) -> MorphPanelState:
    view_open = app.morph_view_open
    editing = app.morph_editing_target_name
    solo = app.morph_solo_target
    rows = tuple(
        MorphRow(
            lid=lid,
            name=name,
            weight=weight,
            current=current,
            editing=view_open and current and name == editing,
            solo=lid == solo,
        )
        for lid, name, weight, current in app.morph_target_rows()
    )
    return MorphPanelState(
        object_name=app.morph_document_object.name,
        rows=rows,
        view_open=view_open,
        object_mode=app.selection.mode.name == "OBJECT",
    )
