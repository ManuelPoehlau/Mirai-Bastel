"""Statuszeile des Labs — reiner Text, GL-frei (Handoff Slice 3 §4.6)."""

from __future__ import annotations

from mirai.application import Application

from .lab_dispatch import LabDispatcher
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
    parts.append(f"Move: {dispatcher.move_state.value}")
    parts.append(f"Auswahl: {picked}")
    if dispatcher.message:
        parts.append(dispatcher.message)
    return " | ".join(parts)
