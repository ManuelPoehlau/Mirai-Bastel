"""Automatisierte Szenarien A-H am echten Viewport-V1-Fenster (Head-Asset).

Reproduzierbarer Benchmark: echtes pyglet-Fenster (echter GL-Kontext), echte
Head-Szene (326 V / 648 E / 324 Quads), Events werden direkt an die
Event-Handler des Fensters geliefert (gleiches Muster wie _smoke_all_tools.py
und tests/test_tool_integration.py) — kein Maus-Automations-Framework.

Szenarien (pro Event folgt ein on_draw — das ist ein "Frame"):

    A  idle          on_draw ohne Interaktion
    B  orbit         Rechts-Ziehen (ORBIT-Drag) — Hover-Refresh inklusive
    C  pan           Mitte-Ziehen (PAN-Drag) — Hover-Refresh inklusive
    D  zoom          Mausrad — Hover-Refresh inklusive
    E  hover         Maus-Move ueber das Mesh (Hover-Wechsel -> Rebuild)
    E2 hover-still   Maus-Move an fester Position (kein Hover-Wechsel)
    F  vertex drag   Vertex selektieren (Klick) und ziehen (MoveTool)
    G  edge drag     Edge selektieren und ziehen
    H  face drag     Face selektieren und ziehen

Ausfuehrung:   python -m perf.scenario_runner  --events 200   (aus
experiments/mirai_bastel_viewport_V1)  bzw. direkt per Pfad.

Hinweis: Oeffnet fuer die Laufzeit ein sichtbares Fenster; VSync ist fuer
die CPU-Kostenmessung bewusst AUS.
"""
from __future__ import annotations

import argparse
import math
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

from pyglet.window import key, mouse  # noqa: E402

from mirai_bastel_core import SelectionMode  # noqa: E402
from viewport.topology_app import TopologyWindow  # noqa: E402

from perf.perf_probe import PerfProbe, instrument_window, render_scenario_block  # noqa: E402
from viewport_adapter import DEFAULT_HEAD_ASSET, build_scene_from_obj, frame_camera_on_bounds  # noqa: E402


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def build_head_window(vsync: bool = False) -> TopologyWindow:
    """Echtes Fenster mit der echten Head-Szene (gleicher Pfad wie run_viewport)."""
    scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
    window = TopologyWindow(scene=scene)
    window._set_selection_mode(SelectionMode.VERTEX)
    window.set_vsync(vsync)
    frame_camera_on_bounds(window.camera, window.scene.mesh)
    return window


def project_bounds(window):
    mesh = window.scene.mesh
    points = []
    for vid in mesh.all_vertex_ids():
        projected = window.camera.project_to_screen(
            mesh.vertex_position(vid), window.width, window.height
        )
        if projected is not None:
            points.append(projected)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def sweep_points(window, count: int, inside: bool = True):
    """Schlangenlinien-Pfad ueber (bzw. neben) dem projizierten Mesh."""
    if inside:
        x0, y0, x1, y1 = project_bounds(window)
    else:
        x1, y1 = window.width - 30.0, window.height - 30.0
        x0, y0 = x1 - 60.0, y1 - 60.0
    width = max(1.0, x1 - x0)
    height = max(1.0, y1 - y0)
    cx, cy = x0 + width / 2.0, y0 + height / 2.0
    points = []
    for i in range(count):
        t = i / max(1, count)
        x = cx + (width / 2.0) * (1.0 - math.cos(2.0 * math.pi * t))
        y = cy + (height / 4.0) * math.sin(4.0 * math.pi * t)
        points.append((x, y))
    return points


def nearest_vertex_to_center(window):
    mesh = window.scene.mesh
    cx, cy = window.width / 2.0, window.height / 2.0
    best_vid, best_dist = None, float("inf")
    for vid in mesh.all_vertex_ids():
        projected = window.camera.project_to_screen(
            mesh.vertex_position(vid), window.width, window.height
        )
        if projected is None:
            continue
        dist = math.hypot(projected[0] - cx, projected[1] - cy)
        if dist < best_dist:
            best_vid, best_dist = vid, dist
    return window.camera.project_to_screen(
        mesh.vertex_position(best_vid), window.width, window.height
    )


def nearest_edge_to_center(window):
    mesh = window.scene.mesh
    cx, cy = window.width / 2.0, window.height / 2.0
    best = None
    best_dist = float("inf")
    for eid in mesh.all_edge_ids():
        va, vb = mesh.edge_vertices(eid)
        pa = window.camera.project_to_screen(mesh.vertex_position(va), window.width, window.height)
        pb = window.camera.project_to_screen(mesh.vertex_position(vb), window.width, window.height)
        if pa is None or pb is None:
            continue
        mx, my = (pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0
        dist = math.hypot(mx - cx, my - cy)
        if dist < best_dist:
            best, best_dist = (mx, my), dist
    return best


def nearest_face_to_center(window):
    mesh = window.scene.mesh
    cx, cy = window.width / 2.0, window.height / 2.0
    best = None
    best_dist = float("inf")
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        projected = [
            window.camera.project_to_screen(mesh.vertex_position(vid), window.width, window.height)
            for vid in boundary
        ]
        if any(p is None for p in projected):
            continue
        mx = sum(p[0] for p in projected) / len(projected)
        my = sum(p[1] for p in projected) / len(projected)
        dist = math.hypot(mx - cx, my - cy)
        if dist < best_dist:
            best, best_dist = (mx, my), dist
    return best


# ---------------------------------------------------------------------------
# Szenario-Rahmen
# ---------------------------------------------------------------------------

def run_frames(window, probe: PerfProbe, frame_label: str, events, draw: bool = True):
    """Fuehrt (Event + optional Draw) pro Frame aus und misst die Framezeit.

    `events` ist eine Liste von Callables (oder None fuer reine Draw-Frames).
    """
    stats = probe.stat(frame_label)
    for event in events:
        start = time.perf_counter_ns()
        if event is not None:
            event()
        if draw:
            window.on_draw()
        stats.add(time.perf_counter_ns() - start)


def scenario_idle(window, probe, n):
    run_frames(window, probe, "frame:idle", [None] * n)


def scenario_orbit(window, probe, n):
    window.on_mouse_press(window.width // 2, window.height // 2, mouse.RIGHT, 0)
    points = sweep_points(window, n, inside=False)
    events = []
    for i, (x, y) in enumerate(points):
        dx = 3.0 if i % 2 == 0 else -3.0
        dy = 2.0 if i % 3 == 0 else -1.0
        events.append(lambda x=x, y=y, dx=dx, dy=dy: window.on_mouse_drag(x, y, dx, dy, mouse.RIGHT, 0))
    run_frames(window, probe, "frame:orbit", events)
    window.on_mouse_release(points[-1][0], points[-1][1], mouse.RIGHT, 0)


def scenario_pan(window, probe, n):
    window.on_mouse_press(window.width // 2, window.height // 2, mouse.MIDDLE, 0)
    points = sweep_points(window, n, inside=False)
    events = []
    for i, (x, y) in enumerate(points):
        dx = 2.0 if i % 2 == 0 else -2.0
        dy = 1.0 if i % 2 == 0 else -1.0
        events.append(lambda x=x, y=y, dx=dx, dy=dy: window.on_mouse_drag(x, y, dx, dy, mouse.MIDDLE, 0))
    run_frames(window, probe, "frame:pan", events)
    window.on_mouse_release(points[-1][0], points[-1][1], mouse.MIDDLE, 0)


def scenario_zoom(window, probe, n):
    x, y = window.width // 2, window.height // 2
    events = [
        (lambda x=x, y=y, s=1.0 if i % 2 == 0 else -1.0: window.on_mouse_scroll(x, y, 0, s))
        for i in range(n)
    ]
    run_frames(window, probe, "frame:zoom", events)


def scenario_hover(window, probe, n):
    points = sweep_points(window, n, inside=True)
    events = [(lambda x=x, y=y: window.on_mouse_motion(x, y, 2, 1)) for x, y in points]
    run_frames(window, probe, "frame:hover", events)


def scenario_hover_still(window, probe, n):
    x, y = window.width // 2, window.height // 2
    events = [lambda: window.on_mouse_motion(x, y, 0, 0) for _ in range(n)]
    run_frames(window, probe, "frame:hover-still", events)


def _drag_scenario(window, probe, frame_label, screen_pos, n):
    window.on_mouse_press(int(screen_pos[0]), int(screen_pos[1]), mouse.LEFT, 0)
    if not window._tool_manager.is_interacting:
        # Klick hat nichts bewegt (Deselektion/Verfehlen): Trotzdem derselbe
        # Drag-Pfad — der Handler tut dann nichts ausser der _drag_mode-Pruefung.
        print(f"    [warn] {frame_label}: press hat keine Tool-Interaktion gestartet")
    events = []
    for i in range(n):
        dx = 2.0 if i % 2 == 0 else -2.0
        dy = 1.5 if i % 2 == 0 else -1.5
        events.append(
            lambda dx=dx, dy=dy: window.on_mouse_drag(screen_pos[0], screen_pos[1], dx, dy, mouse.LEFT, 0)
        )
    run_frames(window, probe, frame_label, events)
    window.on_mouse_release(int(screen_pos[0]), int(screen_pos[1]), mouse.LEFT, 0)


def scenario_vertex_drag(window, probe, n):
    pos = nearest_vertex_to_center(window)
    if pos is not None:
        _drag_scenario(window, probe, "frame:vertex-drag", pos, n)


def scenario_edge_drag(window, probe, n):
    window.on_key_press(key.E, 0)  # Edge-Mode
    pos = nearest_edge_to_center(window)
    if pos is not None:
        _drag_scenario(window, probe, "frame:edge-drag", pos, n)
    window.on_key_press(key.V, 0)  # zurueck in Vertex-Mode


def scenario_face_drag(window, probe, n):
    window.on_key_press(key.F, 0)  # Face-Mode
    pos = nearest_face_to_center(window)
    if pos is not None:
        _drag_scenario(window, probe, "frame:face-drag", pos, n)
    window.on_key_press(key.V, 0)


SCENARIOS = {
    "idle": scenario_idle,
    "orbit": scenario_orbit,
    "pan": scenario_pan,
    "zoom": scenario_zoom,
    "hover": scenario_hover,
    "hover-still": scenario_hover_still,
    "vertex-drag": scenario_vertex_drag,
    "edge-drag": scenario_edge_drag,
    "face-drag": scenario_face_drag,
}

COMPONENT_ORDER = [
    "event.mouse_motion", "event.mouse_drag", "event.mouse_scroll", "event.mouse_press",
    "event.mouse_release", "event.on_draw", "hover.refresh_hover",
    "pick.vertex", "pick.edge", "pick.face",
    "rebuild.geometry", "rebuild.normals", "rebuild.triangle_arrays",
    "gl.vertexlist_create+upload", "tool.tool_update",
]


def run_all(event_count: int, vsync: bool = False, scenarios=None) -> str:
    scenarios = scenarios or list(SCENARIOS)
    window = build_head_window(vsync=vsync)
    probe = PerfProbe()
    instrument_window(window, probe)
    report_lines = []
    try:
        # Erstes Rebuild nach Fenster-Setup gehoert zur Initialisierung,
        # nicht zu den Szenarien: einmal zeichnen, danach Reset.
        window.on_draw()
        probe.reset()

        for name in scenarios:
            scenario_fn = SCENARIOS[name]
            probe.reset()
            gc_before = PerfProbe.gc_snapshot()
            started = time.perf_counter()
            scenario_fn(window, probe, event_count)
            elapsed = time.perf_counter() - started
            gc_after = PerfProbe.gc_snapshot()
            frame_label = f"frame:{name}"
            block = render_scenario_block(probe, frame_label, f"{name.upper()}  (n={event_count}, {elapsed:.2f} s real)")
            gc_delta = PerfProbe.gc_delta(gc_before, gc_after)
            block += "\n  gc collections (gen0,gen1,gen2): " + str(gc_delta["collections"])
            report_lines.append(block)
            print(block, flush=True)

        window.on_draw()
    finally:
        window.close()
    return "\n\n".join(report_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Viewport V1 Szenario-Benchmark (Head-Asset)")
    parser.add_argument("--events", type=int, default=200, help="Events pro Szenario")
    parser.add_argument("--vsync", action="store_true", help="VSync aktivieren (Default: aus)")
    parser.add_argument(
        "--only", type=str, default="",
        help="Komma-separierte Szenario-Liste (idle,orbit,pan,zoom,hover,hover-still,vertex-drag,edge-drag,face-drag)",
    )
    args = parser.parse_args()
    scenarios = [s.strip() for s in args.only.split(",") if s.strip()] or None
    report = run_all(args.events, vsync=args.vsync, scenarios=scenarios)
    out_path = Path(__file__).resolve().parent / "scenario_results.txt"
    out_path.write_text(report, encoding="utf-8")
    print(f"\n[written] {out_path}")


if __name__ == "__main__":
    main()
