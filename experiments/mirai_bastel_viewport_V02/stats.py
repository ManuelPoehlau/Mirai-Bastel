"""Instrumentierung für das Viewport V0.2 Experiment.

Alle Messung läuft durch ein einziges ``Stats``-Objekt. Damit zeigt das
Experiment sichtbar, was tatsächlich passiert: Zähler, Ressourcen-IDs,
Upload-Bytes und CPU-Timing. Timing ist rein diagnostisch.

Vom Spec geforderte Zähler:
    camera_updates, selection_updates, material_updates, vertex_updates,
    topology_updates, structural_rebuilds, mesh_rebuilds, geometry_uploads,
    partial_updates, bounds_recalculations, gpu_resource_creations,
    gpu_resource_destroys
Zusätzlich: Ressourcen-IDs, Upload-Bytes/Update-Größe, CPU-Timing.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional


class Stats:
    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.timings_ms: dict[str, list[float]] = defaultdict(list)
        # name -> ResourceSnapshot (unterstützend fürs Reporting)
        self.resource_snapshots: dict[str, object] = {}
        self.uploaded_bytes: int = 0
        self._timer_stack: list[tuple[str, float]] = []

    # -- Zähler ------------------------------------------------------------
    def count(self, name: str, amount: int = 1) -> None:
        self.counters[name] += amount

    # -- Timing (diagnostisch) ---------------------------------------------
    def start(self, name: str) -> None:
        self._timer_stack.append((name, time.perf_counter()))

    def stop(self, name: str) -> None:
        # Holt den zuletzt gestarteten Timer mit diesem Namen
        for i in range(len(self._timer_stack) - 1, -1, -1):
            timer_name, t0 = self._timer_stack[i]
            if timer_name == name:
                self.timings_ms[name].append((time.perf_counter() - t0) * 1000.0)
                del self._timer_stack[i]
                return

    def add_upload(self, nbytes: int) -> None:
        self.uploaded_bytes += nbytes

    # -- Ressourcen ---------------------------------------------------------
    def snapshot(self, resource) -> None:
        """Registriert den aktuellen Zustand einer Ressource fürs Reporting."""
        data = getattr(resource, "data", None)
        self.resource_snapshots[resource.name] = {
            "resource_id": resource.resource_id,
            "name": resource.name,
            "items": len(data) if hasattr(data, "__len__") else None,
            "created": resource.created,
            "updates": resource.updates,
            "bytes": resource.bytes_uploaded,
        }

    def summary(self) -> dict[str, object]:
        return {
            "counters": dict(self.counters),
            "uploaded_bytes": self.uploaded_bytes,
            "resources": {
                name: snap
                for name, snap in sorted(self.resource_snapshots.items())
            },
            "timings_ms": {
                name: round(sum(v) / len(v), 4) if v else 0.0
                for name, v in self.timings_ms.items()
            },
        }
