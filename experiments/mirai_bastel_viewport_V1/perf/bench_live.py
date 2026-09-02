"""Live-Perf-Messung am echten Head-Viewport (manuelle Interaktion).

Startet exakt denselben Head-Viewport wie run_viewport.py des
Rigging-Experiments (LivingMeshResearchWindow = All-Tools-Playground mit
head_basemesh.obj) und legt die Perf-Instrumentation darueber. Waehrend der
Nutzer normal orbitet, pannst, zoomt, hovert und dragged, laufen alle Events
durch die Zeitmesser.

Ausgabe: alle 5 Sekunden ein Zwischenreport auf der Konsole; beim Schliessen
des Fensters ein Final-Report.

Start:  python -m perf.bench_live   (aus experiments/mirai_bastel_viewport_V1)
"""
from __future__ import annotations

import sys
from pathlib import Path

_THIS = Path(__file__).resolve().parent
_VIEWPORT_V1_DIR = _THIS.parent
_EXPERIMENTS_DIR = _VIEWPORT_V1_DIR.parent
for _path in (
    str(_VIEWPORT_V1_DIR),
    str(_EXPERIMENTS_DIR / "mirai_bastel_core_V1"),
    str(_EXPERIMENTS_DIR / "rigging-skinning-morphing"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import pyglet  # noqa: E402

from perf.perf_probe import PerfProbe, instrument_window  # noqa: E402
from run_viewport import LivingMeshResearchWindow  # noqa: E402  (main() ist __main__-geschuetzt)
from viewport_adapter import DEFAULT_HEAD_ASSET, build_scene_from_obj  # noqa: E402

_REPORT_EVERY_S = 5.0


def main() -> None:
    window = LivingMeshResearchWindow(build_scene_from_obj(DEFAULT_HEAD_ASSET))

    probe = PerfProbe()
    instrument_window(window, probe)

    print("\n[Perf] Live-Instrumentation aktiv. Normal arbeiten (Orbit/Pan/Zoom/")
    print("[Perf] Hover/Selection/Drag). Alle 5 s Zwischenreport; Final-Report beim Schliessen.\n")

    def periodic_report(_dt) -> None:
        header = f"[Perf] Zwischenreport ({probe.counters.get('rebuilds', 0)} Rebuilds bisher)"
        print(probe.render_report(header), flush=True)
        print(flush=True)

    pyglet.clock.schedule_interval(periodic_report, _REPORT_EVERY_S)

    original_on_close = window.on_close

    def on_close_with_report():
        periodic_report(0.0)
        print(probe.render_report("[Perf] FINAL-REPORT (gesamte Session)"), flush=True)
        original_on_close()

    window.on_close = on_close_with_report

    pyglet.app.run()


if __name__ == "__main__":
    main()
