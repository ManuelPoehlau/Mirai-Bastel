"""Bone- und Skin-Panel, reine Logik (Bone tool 01, 2026-11-17, AD-028 Nachtrag; Layout und Texte `PROVISIONAL`).

Kein pyglet, kein imgui: nur Lesen über die öffentlichen `Application`-Zugriffe. Das Panel zeichnet `state(app)` und ruft bei
einer Eingabe dieselben Wege wie die Tasten bzw. das Werkzeug (`start_bone_chain`, `edit_bone`, `rename_bone`,
`select_bone`, `set_bones_hidden`, `delete_bone`, `weights_from_group_value`, `set_weight_value`); es hält keinen
Dokumentzustand (AD-030). Jede Änderung ist ein Undo-Schritt, jede Ablehnung steht in der Statuszeile; `*_blocker` sagt
vorab, warum etwas gerade nicht geht (das Panel graut den Knopf aus).

Knochen stehen weiter im Outliner; das Panel zeigt den aktuellen Knochen (Name, Parent, Kopf, Spitze, Roll, Ausblenden,
Löschen) und die Skinning-Aktionen (Gewichte aus Gruppe mit Breite, Gewicht setzen mit Wert, Gewichtsansicht).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core import SelectionMode
from mirai.interaction import commands
from mirai.interaction.tools import resolve_selection_vertices
from mirai.soft_selection import RADIUS_STEPS_PERCENT


@dataclass(frozen=True)
class BoneDetail:
    id: object
    name: str
    parent: object  # BoneId | None
    parent_name: str | None
    head: tuple
    tail: tuple
    length: float
    roll_degrees: float
    hidden: bool


@dataclass(frozen=True)
class BoneRow:
    id: object
    name: str
    depth: int
    current: bool
    hidden: bool


@dataclass(frozen=True)
class BonePanelState:
    rows: tuple[BoneRow, ...]
    current: BoneDetail | None
    parent_choices: tuple[tuple[object, str], ...]  # (BoneId | None, Name): ohne den Knochen selbst und seine Kinder
    posed: bool
    edit_blocker: str | None
    chain_active: bool
    chain_blocker: str | None
    chain_snap: bool
    chain_parent_name: str | None  # Parent, den „Kette starten“ vergäbe (der aktuelle Knochen)
    group: str | None
    selected_points: int
    soft_on: bool
    weight_view: bool
    falloff_percent: float  # Startbreite: die Soft-Radius-Stufe (wie die Taste)

    @property
    def has_bones(self) -> bool:
        return bool(self.rows)

    @property
    def count_text(self) -> str:
        n = len(self.rows)
        return f"{n} Knochen" if n != 1 else "1 Knochen"

    @property
    def can_edit(self) -> bool:
        return self.current is not None and self.edit_blocker is None

    @property
    def can_weights(self) -> bool:
        """Grob: es gibt einen Knochen und keine Interaktion läuft. Die feinen Ablehnungen (Objektebene, Symmetrie,
        keine Gruppe, keine Auswahl) kommen aus `Application` in die Statuszeile, wie bei den Tasten."""
        return self.current is not None and not self.chain_active  # (Gewichte gehen auch in der Pose, AD-028 §7.1)


def _tree_rows(rig, current, hidden) -> tuple[BoneRow, ...]:
    """Die Knochen als Baum (Wurzeln und Geschwister nach Id), mit Einrückungstiefe."""
    rows: list[BoneRow] = []

    def walk(bone_id, depth: int) -> None:
        bone = rig.bone(bone_id)
        rows.append(BoneRow(bone_id, bone.name, depth, bone_id == current, bone_id in hidden))
        for child in rig.children(bone_id):
            walk(child, depth + 1)

    for bone in rig.bones:
        if bone.parent is None:
            walk(bone.id, 0)
    return tuple(rows)


def state(app) -> BonePanelState:
    rig = app.scene.rig
    current_id = app.current_bone
    rows: tuple[BoneRow, ...] = ()
    detail = None
    choices: tuple = ()
    if rig is not None and rig.bones:
        hidden = rig.hidden_ids()
        rows = _tree_rows(rig, current_id, hidden)
        if current_id is not None:
            b = rig.bone(current_id)
            detail = BoneDetail(
                id=b.id,
                name=b.name,
                parent=b.parent,
                parent_name=None if b.parent is None else rig.bone(b.parent).name,
                head=b.head,
                tail=b.tail,
                length=b.length,
                roll_degrees=math.degrees(b.roll),
                hidden=b.hidden,
            )
            choices = ((None, "(keiner, Wurzel)"),) + tuple(
                (o.id, o.name) for o in rig.bones if o.id != b.id and b.id not in rig.ancestors(o.id)
            )
    mesh = app.scene.mesh
    selection = app.selection
    selected = 0 if selection.mode is SelectionMode.OBJECT else len(resolve_selection_vertices(mesh, selection, selection.mode))
    soft = app.soft_settings
    return BonePanelState(
        rows=rows,
        current=detail,
        parent_choices=choices,
        posed=app.posed,
        edit_blocker=app.bone_edit_blocker,
        chain_active=app.bone_chain_active,
        chain_blocker=app.bone_chain_blocker,
        chain_snap=app.bone_chain_snap,
        chain_parent_name=None if current_id is None else app.current_bone_name,
        group=app.active_region,
        selected_points=selected,
        soft_on=soft.enabled,
        weight_view=app.weight_view,
        falloff_percent=float(RADIUS_STEPS_PERCENT[soft.radius_step]),
    )


# -- Aktionen: ein Aufruf an Application, mit denselben Ablehnungen wie die Tasten -------------------------------------


#: Nachkommastellen der Zahlenfelder. ImGui liest beim Verlassen eines bearbeiteten Felds den angezeigten Text zurück:
#: was weniger als eine halbe Stelle abweicht, ist Rundung der Anzeige, keine Eingabe (sonst schriebe schon ein
#: Hineinklicken eine gerundete Kopie in den Knochen und einen Undo-Schritt).
POSITION_DECIMALS = 4
ROLL_DECIMALS = 2


def differs(old: float, new: float, decimals: int) -> bool:
    return abs(float(new) - float(old)) > 0.6 * 10.0 ** -decimals


def merge_vec(current: tuple, edits: dict) -> tuple:
    """`current` mit den bearbeiteten Komponenten `{0|1|2: Wert}`; die anderen bleiben, wie sie sind (kein Rundungsfehler
    des Zahlenfelds in einer Komponente, die niemand angefasst hat). Eine „Eingabe“, die nur das Anzeigebild des alten Werts
    ist, bleibt der alte Wert."""
    return tuple(
        float(edits[i]) if i in edits and differs(current[i], edits[i], POSITION_DECIMALS) else float(current[i])
        for i in range(3)
    )


def set_head(app, bone, current: tuple, edits: dict) -> bool:
    return app.edit_bone(bone, head=merge_vec(current, edits))


def set_tail(app, bone, current: tuple, edits: dict) -> bool:
    return app.edit_bone(bone, tail=merge_vec(current, edits))


def set_roll_degrees(app, bone, current_degrees: float, degrees: float) -> bool:
    if not differs(current_degrees, degrees, ROLL_DECIMALS):
        return False
    return app.edit_bone(bone, roll=math.radians(degrees))


def set_parent(app, bone, parent) -> bool:
    return app.edit_bone(bone, parent=parent)


def toggle_weight_view(app) -> bool:
    return app.dispatch_command(commands.WEIGHT_VIEW_TOGGLE)


def step_bone(app, step: int) -> bool:
    """Der vorige / nächste Knochen (wie `Alt+J` / `Ctrl+Alt+J`: überspringt ausgeblendete)."""
    return app.dispatch_command(commands.BONE_NEXT if step > 0 else commands.BONE_PREVIOUS)
