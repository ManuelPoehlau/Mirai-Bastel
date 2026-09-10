"""Instrumentierung/Benchmark-Counter für den Viewport v0.2.

Portiert aus dem verifizierten Proof-of-Architecture-Experiment
(`experiments/mirai_bastel_viewport_V02/stats.py`).

Alle Messung läuft durch ein einziges `BenchmarkCounters`-Objekt, damit
sichtbar ist, was tatsächlich passiert: Zähler, Ressourcen-Snapshots,
Upload-Bytes und (diagnostisches) CPU-Timing.

Von VIEWPORT_V02_ARCHITECTURE.md §8 / Appendix A geforderte Zähler:
    camera_updates, selection_updates, material_updates, vertex_updates
    (aka position_updates), topology_updates, structural_rebuilds,
    mesh_rebuilds, geometry_uploads, partial_updates,
    bounds_recalculations, normal_recomputations,
    gpu_resource_creations, gpu_resource_destroys, bytes_uploaded

Diese Zähler beweisen NICHT automatisch "gut" — sie sind Rohmaterial für
Tests/Assertions (siehe VIEWPORT_V02_ARCHITECTURE.md §8, "Explicit
Non-Claims"). Timing ist rein diagnostisch, keine harte Performance-Aussage.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any


class BenchmarkCounters:
    """Zentrale Zähler-/Timing-/Ressourcen-Instrumentierung."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = defaultdict(int)
        self.timings_ms: dict[str, list[float]] = defaultdict(list)
        self.resource_snapshots: dict[str, dict[str, Any]] = {}
        self.uploaded_bytes: int = 0
        self._timer_stack: list[tuple[str, float]] = []

    # -- Zähler ----------------------------------------------------------
    def count(self, name: str, amount: int = 1) -> None:
        self.counters[name] += amount

    def get(self, name: str) -> int:
        return self.counters.get(name, 0)

    # -- Timing (diagnostisch, keine harte Zusicherung) -------------------
    def start(self, name: str) -> None:
        self._timer_stack.append((name, time.perf_counter()))

    def stop(self, name: str) -> None:
        for i in range(len(self._timer_stack) - 1, -1, -1):
            timer_name, t0 = self._timer_stack[i]
            if timer_name == name:
                self.timings_ms[name].append((time.perf_counter() - t0) * 1000.0)
                del self._timer_stack[i]
                return

    def average_ms(self, name: str) -> float:
        values = self.timings_ms.get(name)
        if not values:
            return 0.0
        return sum(values) / len(values)

    # -- Ressourcen-Uploads -------------------------------------------------
    def add_upload(self, nbytes: int) -> None:
        self.uploaded_bytes += nbytes

    def snapshot_resource(self, resource) -> None:
        """Registriert den aktuellen Zustand einer GPU-Ressource fürs Reporting."""
        self.resource_snapshots[resource.name] = {
            "resource_id": resource.resource_id,
            "name": resource.name,
            "created": resource.created,
            "updates": resource.updates,
            "bytes": resource.bytes_uploaded,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "uploaded_bytes": self.uploaded_bytes,
            "resources": dict(sorted(self.resource_snapshots.items())),
            "timings_ms": {
                name: round(self.average_ms(name), 4) for name in self.timings_ms
            },
        }

    def reset(self) -> None:
        """Setzt alle Zähler zurück (nur für Tests/Benchmark-Isolation gedacht)."""
        self.counters.clear()
        self.timings_ms.clear()
        self.resource_snapshots.clear()
        self.uploaded_bytes = 0
        self._timer_stack.clear()
