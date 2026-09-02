"""Skalierungsmessung: Wie verhaelt sich die Viewport-Pipeline mit der Mesh-Groesse?

Echtes Fenster, echte GL-VertexLists/Upload; Szene wird pro Groesse ausgetauscht
(dasselbe Fenster-Objekt, wie es auch der Head-Playground nutzt). Gemessen wird
pro Groesse:

- erster voller Rebuild nach Szenenwechsel (Initialisierung)
- ORBIT-Drag-Event + Draw (Hover-Refresh inklusive — realer Orbit-Pfad)
- HOVER-Move-Event uebers Mesh + Draw (Hover-Wechsel -> Pick + Rebuild)

Mit Zeitbudget pro Szenario, damit 20k Quads (vermutlich sekundenlange
Rebuilds) nicht ausufern.

Ausfuehrung:  python -m perf.bench_scaling --events 50 --budget 20
"""
from __future__ import annotations

import argparse
import sys
import time
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

from mirai_bastel_core import SelectionMode  # noqa: E402
from viewport.topology_app import TopologyWindow  # noqa: E402

from perf.perf_probe import PerfProbe, instrument_window, render_scenario_block  # noqa: E402
from perf.scenario_runner import sweep_points  # noqa: E402
from perf.synthetic_meshes import build_scaling_scenes  # noqa: E402
from viewport_adapter import DEFAULT_HEAD_ASSET, build_scene_from_obj, frame_camera_on_bounds  # noqa: E402


def swap_scene(window, scene) -> float:
    """Szene austauschen + vollen Rebuild ausfuehren; gibt die Rebuild-Zeit (ms) zurueck."""
    window.scene = scene
    window._hovered_id = None
    window.scene.selection.clear()
    window.scene.selection.hovered = None
    start = time.perf_counter_ns()
    window._rebuild_geometry()
    return (time.perf_counter_ns() - start) / 1e6


def run_sized_scenario(window, probe: PerfProbe, label: str, events: int, budget_s: float):
    """Szenario mit Zeitbudget: bricht ab, wenn budget_s realisiert ist."""
    from pyglet.window import mouse

    probe.reset()
    stats = probe.stat(f"frame:{label}")
    started = time.perf_counter()

    if label == "orbit":
        window.on_mouse_press(window.width // 2, window.height // 2, mouse.RIGHT, 0)
        points = sweep_points(window, events, inside=False)
        for i, (x, y) in enumerate(points):
            frame_start = time.perf_counter_ns()
            dx = 3.0 if i % 2 == 0 else -3.0
            dy = 2.0 if i % 3 == 0 else -1.0
            window.on_mouse_drag(x, y, dx, dy, mouse.RIGHT, 0)
            window.on_draw()
            stats.add(time.perf_counter_ns() - frame_start)
            if time.perf_counter() - started > budget_s:
                print(f"    [budget] {label} abgebrochen nach {i + 1}/{events} Events")
                break
        window.on_mouse_release(points[-1][0], points[-1][1], mouse.RIGHT, 0)
    elif label == "hover":
        points = sweep_points(window, events, inside=True)
        for i, (x, y) in enumerate(points):
            frame_start = time.perf_counter_ns()
            window.on_mouse_motion(x, y, 2, 1)
            window.on_draw()
            stats.add(time.perf_counter_ns() - frame_start)
            if time.perf_counter() - started > budget_s:
                print(f"    [budget] {label} abgebrochen nach {i + 1}/{events} Events")
                break
    else:
        raise ValueError(label)


def main() -> None:
    parser = argparse.ArgumentParser(description="Viewport V1 Skalierungs-Benchmark")
    parser.add_argument("--events", type=int, default=50)
    parser.add_argument("--budget", type=float, default=20.0, help="Sekunden Budget pro Szenario")
    parser.add_argument(
        "--labels", type=str, default="324,1.3k,5k,20k",
        help="Komma-separierte Torus-Groessen; HEAD wird immer mit gemessen",
    )
    args = parser.parse_args()
    labels = [l.strip() for l in args.labels.split(",") if l.strip()]

    scenes = build_scaling_scenes()
    head_scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)

    window = TopologyWindow(scene=head_scene)
    window._set_selection_mode(SelectionMode.VERTEX)
    window.set_vsync(False)
    probe = PerfProbe()
    instrument_window(window, probe)

    blocks = []
    try:
        cases = [("HEAD (324 Quads)", head_scene)] + [
            (f"TORUS ~{label} ({len(scene.mesh.all_face_ids())} Quads)", scene)
            for label, scene in scenes.items()
            if label in labels
        ]

        for title, scene in cases:
            full_rebuild_ms = swap_scene(window, scene)
            frame_camera_on_bounds(window.camera, window.scene.mesh)
            print(f"\n### {title}")
            print(f"full rebuild (einmalig): {full_rebuild_ms:.2f} ms")
            for label in ("orbit", "hover"):
                run_sized_scenario(window, probe, label, args.events, args.budget)
                block = render_scenario_block(probe, f"frame:{label}", f"{title} — {label}")
                blocks.append(block)
                print(block, flush=True)
    finally:
        window.close()

    out_path = _THIS / "scaling_results.txt"
    out_path.write_text("\n\n".join(blocks), encoding="utf-8")
    print(f"\n[written] {out_path}")


if __name__ == "__main__":
    main()
