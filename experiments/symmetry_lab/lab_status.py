"""Statuszeile des Labs — reiner Text, GL-frei (Handoff Slice 3 §4.6).

Slice 4: zeigt zusätzlich, was ein scharfer/ziehender Move bewegen wird
("Auswahl" / "Hover v<id>", `dispatcher.move_target_label`, A4/E7).

Slice 5: Während der Re-Symmetrize-Vorschau steht Richtung, Anzahlen und
„M = ausführen, ESC = abbrechen" (`lab_resymmetrize.plan_summary`, E15) in
einer eigenen Zeile über der Statuszeile (`preview_text`) — in der Statuszeile
selbst würde sie bei langen Asset-Namen am Fensterrand abgeschnitten.

Slice 7 (E30): Während einer Knife-Session steht „Knife: aktiv (Start v<id> /
kein Start)" in der Statuszeile; ist das Ziel unter dem Cursor nicht klickbar,
zusätzlich der Grund aus dem Dry-Run (`knife_hover.reason`). Die Meldung eines
abgelehnten Klicks (`knife.last_message`, ggf. mit der Validierung) kommt wie
jede andere Meldung über `dispatcher.message`.
"""

from __future__ import annotations

from mirai.application import Application

from .lab_dispatch import LabDispatcher
from .lab_resymmetrize import plan_summary
from .lab_symmetry import SymmetryReport


def status_text(
    app: Application, asset_name: str, dispatcher: LabDispatcher, report: SymmetryReport
) -> str:
    selected = sorted(app.scene.selection.vertices, key=int)
    picked = ", ".join(f"v{int(v)}" for v in selected) or "—"
    vertex_count = len(app.scene.mesh.all_vertex_ids())
    parts = [
        f"{asset_name} | {vertex_count} V",
        f"Symmetrie: {report.axis or 'aus'} ({report.state.value})",
    ]
    if report.axis is not None:
        unpaired = f"ohne Partner: {len(report.unpaired)}"
        if report.ambiguous:
            unpaired += f", mehrdeutig: {len(report.ambiguous)}"
        parts.append(unpaired)
    move_part = f"Move: {dispatcher.move_state.value}"
    if dispatcher.move_target_label:
        move_part += f" ({dispatcher.move_target_label})"
    parts.append(move_part)
    knife_part = knife_text(dispatcher)
    if knife_part:
        parts.append(knife_part)
    parts.append(f"Auswahl: {picked}")
    if dispatcher.message:
        parts.append(dispatcher.message)
    return " | ".join(parts)


def knife_text(dispatcher: LabDispatcher) -> str:
    """„Knife: aktiv (…)"; leer ohne Session (E30)."""
    knife = dispatcher.knife
    if knife is None:
        return ""
    start = f"Start v{int(knife.start)}" if knife.start is not None else "kein Start"
    text = f"Knife: aktiv ({start}{'' if knife.mirrored else ', ungespiegelt'})"
    hover = dispatcher.knife_hover
    if hover is not None and not hover.clickable:
        text += f" — Ziel: {hover.reason}"
    return text


def preview_text(dispatcher: LabDispatcher) -> str:
    """Zeile der Re-Symmetrize-Vorschau (E15); leer, wenn keine Vorschau aktiv ist."""
    plan = dispatcher.resym_plan
    return plan_summary(plan) if plan is not None else ""
