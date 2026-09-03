"""cProfile-Hotspot-Analyse des Viewport-Hot-Paths (Head-Asset, echtes Fenster).

Fuehrt eine gemischte Interaktionslast aus (Orbit + Hover + Vertex-Drag) und
proifiliert sie mit cProfile. Ergebnis: Top-Funktionen nach tottime (eigene
Zeit) und cumtime (inklusive) — der Nachweis fuer die Hotspot-Tabelle im
Perf-Bericht.

Ausfuehrung:  python -m perf.profile_hotspots
"""
from __future__ import annotations

import cProfile
import io
import pstats
import sys
from pathlib import Path

_THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS))

from perf.perf_probe import PerfProbe, instrument_window  # noqa: E402
from perf.scenario_runner import (  # noqa: E402
    build_head_window,
    scenario_hover,
    scenario_orbit,
    scenario_vertex_drag,
)

_OUT_PATH = _THIS / "profile_results.txt"


def _stats_to_text(stats: pstats.Stats, sort_key: str, limit: int) -> str:
    buf = io.StringIO()
    stats.stream = buf
    stats.sort_stats(sort_key).print_stats(limit)
    return buf.getvalue().rstrip()


def main() -> None:
    events = 80
    window = build_head_window(vsync=False)
    probe = PerfProbe()
    instrument_window(window, probe)

    profiler = cProfile.Profile()
    try:
        window.on_draw()  # Initialisierung ausserhalb der Profilerstellung
        profiler.enable()
        scenario_orbit(window, probe, events)
        scenario_hover(window, probe, events)
        scenario_vertex_drag(window, probe, events // 2)
        profiler.disable()
    finally:
        window.close()

    stats = pstats.Stats(profiler)
    stats.strip_dirs()

    lines = [
        f"cProfile: orbit={events}, hover={events}, vertex-drag={events // 2} Events (Head-Asset)",
        "",
        "===== Top 30 nach eigener Zeit (tottime) =====",
        _stats_to_text(stats, "tottime", 30),
        "",
        "===== Top 30 nach inklusiver Zeit (cumtime) =====",
        _stats_to_text(stats, "cumtime", 30),
    ]

    report = "\n".join(lines)
    print(report)
    _OUT_PATH.write_text(report, encoding="utf-8")
    print(f"[written] {_OUT_PATH}")


if __name__ == "__main__":
    main()
