"""Drag-Kosten-Probe des Labs auf dem App-Pfad (WP-SYM-LAB-03 Slice 2, Plan A3).

Verwendung (vom Repo-Root, Windows und Linux gleich; kein Fenster, kein GL):
    python experiments/symmetry_lab/probe_drag_cost.py
    python experiments/symmetry_lab/probe_drag_cost.py --moves 400
    python experiments/symmetry_lab/probe_drag_cost.py --assets subd_cube

Misst, was ein symmetrischer W-Drag pro Mausbewegung auf der CPU kostet: den
Transform-Schritt (`app.pointer_motion` → `MoveTool`) plus die Neuberechnung der
Lab-Overlays (`sync` von Ebene und Markern). Aufbau wie im Fenster
(`run_app.build_app_lab`: `Application` + Lab + Szene + Overlays, nur ohne Fenster
und mit `TraceStore` statt GL — gemessen wird die CPU-Seite der Overlays, nicht
das Zeichnen). Ablauf je Asset: Symmetrie X über die Lab-Taste Shift+S, eine
Auswahl per Klick und Shift+Klick (gepaarte, sichtbare Vertices auf einer Seite
nahe der Bildmitte), dann W drücken, `--moves` Mausbewegungen, W loslassen — alles
über die öffentlichen Eingänge `key_press`/`pointer_*`/`key_release`, wie der
Fenster-Adapter. Nach jeder Bewegung läuft `viewport.sync()` wie im nächsten Frame.

Ausgabe: Klartext zum Einfügen in den Chat — Maschine, je Asset p50/p95/max in ms
für Bewegung gesamt (die Schwelle aus Plan A3: p95 ≤ 8 ms), Transform-Schritt,
Lab-Overlays und den übrigen `viewport.sync()` (App-eigene Puffer, zur Einordnung),
dazu einmal den ersten `sync()` nach dem Commit (dort rechnen die Overlays den
während des Drags aufgeschobenen Befund nach, `lab_overlays`).
Zahlen aus einem Container sind als solche zu kennzeichnen
(`docs/architecture/REFERENCE_HARDWARE.md` §4); maßgeblich ist der Referenz-PC.
"""

from __future__ import annotations

import argparse
import math
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Stufe 0 (Skriptstart), wie run_app.py: experiments/ auf sys.path.
_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from symmetry_lab._paths import ensure_paths  # noqa: E402

ensure_paths()

from mirai.interaction.input import Input  # noqa: E402
from mirai.symmetry import (  # noqa: E402
    CorrespondenceState,
    mirrored_selection,
    vertex_correspondence,
)
from mirai.viewport.picking import pick_nearest_vertex  # noqa: E402

from symmetry_lab.lab_app import lab_key_press  # noqa: E402
from symmetry_lab.run_app import build_app_lab  # noqa: E402

THRESHOLD_P95_MS = 8.0
DEFAULT_ASSETS = ("head_basemesh", "man_with_shoes_basemesh")
DEFAULT_MOVES = 200
DEFAULT_SELECTION = 6
WIDTH, HEIGHT = 1280, 800
#: Schrittweite je Bewegung (Pixel); die Richtung kehrt nach der Hälfte um, damit
#: die Auswahl nicht aus dem Bild wandert.
STEP = (3.0, 1.0)
#: Anzahl gemessener Commit-Frames (der lange Drag + kurze Drags).
COMMIT_SAMPLES = 10

SHIFT_S = Input("key", "s", frozenset({"shift"}))
W = Input("key", "w")
LMB = Input("mouse", "LEFT")
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))


@dataclass(frozen=True)
class Stats:
    p50: float
    p95: float
    max: float

    @classmethod
    def of(cls, samples_ms: list[float]) -> "Stats":
        ordered = sorted(samples_ms)
        p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)  # nearest rank
        return cls(statistics.median(ordered), ordered[p95_index], ordered[-1])

    def text(self) -> str:
        return f"p50 {self.p50:6.2f}  p95 {self.p95:6.2f}  max {self.max:6.2f}"


@dataclass(frozen=True)
class ProbeResult:
    asset: str
    vertex_count: int
    selected: int
    moved: int
    moves: int
    total: Stats
    transform: Stats
    lab_overlays: Stats
    viewport_rest: Stats
    #: Der erste `viewport.sync()` nach dem Loslassen von W: hier holen die
    #: Overlays den aufgeschobenen Befund nach (einmal je Drag, nicht je Bewegung).
    #: Der lange Drag plus `COMMIT_SAMPLES - 1` kurze Drags.
    commit_sync: Stats
    #: Hover-Wechsel ohne Transform (Cursor über wechselnde Vertices): Pick +
    #: Lab-Overlays, zur Einordnung (Slice 1b maß hier 5,1 ms Median, Container).
    hover: Stats

    @property
    def within_threshold(self) -> bool:
        return self.total.p95 <= THRESHOLD_P95_MS


class _TimedOverlay:
    """Misst die Zeit eines Overlay-`sync` (Wrapper um die Instanz-Methode)."""

    def __init__(self, overlay) -> None:
        self.elapsed = 0.0
        original = overlay.sync

        def timed(mesh, selection):
            start = time.perf_counter()
            try:
                return original(mesh, selection)
            finally:
                self.elapsed += time.perf_counter() - start

        overlay.sync = timed


def cpu_name() -> str:
    """Modellname der CPU: Windows aus der Registry, Linux aus /proc/cpuinfo,
    sonst `platform.processor()` (liefert auf Windows nur „Intel64 Family …",
    auf Linux oft nur die Architektur)."""
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            ) as key:
                return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.is_file():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unbekannt"


def machine_info() -> list[str]:
    return [
        f"Plattform: {platform.platform()}",
        f"CPU: {cpu_name()} ({os.cpu_count()} logische Kerne)",
        f"Python: {platform.python_version()} ({platform.python_implementation()})",
    ]


def _screen(app, vid) -> tuple[float, float]:
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


def _by_distance_to_center(app, ids) -> list:
    """`ids` nach Bildschirm-Abstand zur Bildmitte (Projektion ist billig, der
    Sichtbarkeits-Pick nicht — er läuft danach nur bis genug gefunden sind)."""
    def key(vid):
        sx, sy = _screen(app, vid)
        return ((sx - WIDTH / 2) ** 2 + (sy - HEIGHT / 2) ** 2, int(vid))

    return sorted(ids, key=key)


def _clickable(app, vid) -> bool:
    sx, sy = _screen(app, vid)
    return pick_nearest_vertex(
        app.camera, app.scene.mesh, sx, sy, WIDTH, HEIGHT, occlusion=True
    ) == vid


def _pick_selection(app, count: int) -> list:
    """Gepaarte Vertices auf der +X-Seite, sichtbar und eindeutig anklickbar,
    nächst der Bildmitte — eine typische kleine Artist-Auswahl."""
    mesh = app.scene.mesh
    paired = [
        vid
        for vid, corr in vertex_correspondence(mesh).items()
        if corr.state is CorrespondenceState.PAIRED and mesh.vertex_position(vid)[0] > 0.0
    ]
    chosen = []
    for vid in _by_distance_to_center(app, paired):
        if len(chosen) == count:
            break
        if _clickable(app, vid):
            chosen.append(vid)
    return chosen


def _click(app, vid, inp: Input) -> None:
    x, y = _screen(app, vid)
    app.pointer_motion(x, y)
    app.pointer_press(inp, x, y)
    app.pointer_release(inp.value, x, y)


def run_probe(
    asset: str, moves: int = DEFAULT_MOVES, selection_size: int = DEFAULT_SELECTION
) -> ProbeResult:
    """Ein symmetrischer W-Drag über `moves` Mausbewegungen auf `asset`."""
    if moves < 1:
        raise ValueError("moves >= 1")
    app, lab = build_app_lab(asset, WIDTH, HEIGHT)
    viewport = app.viewport
    timers = [_TimedOverlay(overlay) for overlay in lab.overlays]

    if not lab_key_press(app, lab, SHIFT_S) or lab.axis != "X":
        raise RuntimeError(f"{asset}: Symmetrie X ließ sich nicht setzen")
    targets = _pick_selection(app, selection_size)
    if not targets:
        raise RuntimeError(f"{asset}: kein gepaarter, sichtbarer Vertex auf der +X-Seite")
    for i, vid in enumerate(targets):
        _click(app, vid, LMB if i == 0 else SHIFT_LMB)
    selected = len(app.selection.vertices)
    if selected == 0:
        raise RuntimeError(f"{asset}: Auswahl per Klick fehlgeschlagen")
    viewport.sync()

    if not lab_key_press(app, lab, W) or app.transform_command is None:
        raise RuntimeError(f"{asset}: W ließ sich nicht scharf schalten ({app.status_message})")
    x, y = _screen(app, targets[0])
    totals, transforms, overlays, rests = [], [], [], []
    for i in range(moves):
        dx, dy = STEP if i < (moves + 1) // 2 else (-STEP[0], -STEP[1])
        x, y = x + dx, y + dy
        for timer in timers:
            timer.elapsed = 0.0
        start = time.perf_counter()
        app.pointer_motion(x, y, dx, dy)
        after_step = time.perf_counter()
        viewport.sync()
        end = time.perf_counter()
        overlay_s = sum(timer.elapsed for timer in timers)
        transforms.append((after_step - start) * 1000.0)
        overlays.append(overlay_s * 1000.0)
        rests.append((end - after_step - overlay_s) * 1000.0)
        totals.append(transforms[-1] + overlays[-1])
    chosen = set(app.selection.vertices)
    moved = len(chosen | mirrored_selection(app.scene.mesh, chosen))
    app.key_release(W)
    commits = [_timed_sync(viewport)]
    for i in range(COMMIT_SAMPLES - 1):
        commits.append(_short_drag(app, lab, x, y, -1.0 if i % 2 else 1.0))
    hover = _hover_samples(app, timers)
    return ProbeResult(
        asset=asset,
        vertex_count=len(app.scene.mesh.all_vertex_ids()),
        selected=selected,
        moved=moved,
        moves=moves,
        total=Stats.of(totals),
        transform=Stats.of(transforms),
        lab_overlays=Stats.of(overlays),
        viewport_rest=Stats.of(rests),
        commit_sync=Stats.of(commits),
        hover=Stats.of(hover),
    )


def _timed_sync(viewport) -> float:
    start = time.perf_counter()
    viewport.sync()
    return (time.perf_counter() - start) * 1000.0


def _short_drag(app, lab, x: float, y: float, sign: float) -> float:
    """W, zwei Bewegungen in Richtung `sign`, Loslassen; Dauer des ersten `sync()`
    danach. Die Richtung wechselt von Drag zu Drag, damit die Auswahl im Bild bleibt."""
    if not lab_key_press(app, lab, W):
        raise RuntimeError(f"W ließ sich nicht scharf schalten ({app.status_message})")
    dx, dy = sign * STEP[0], sign * STEP[1]
    for _ in range(2):
        app.pointer_motion(x, y, dx, dy)
        app.viewport.sync()
    app.key_release(W)
    return _timed_sync(app.viewport)


def _hover_samples(app, timers: list, count: int = 40) -> list[float]:
    """Cursor springt über sichtbare Vertices (beide Seiten, nächst der Bildmitte);
    je Sprung, der den Hover ändert: `pointer_motion` (Pick) + Lab-Overlay-Syncs in ms."""
    viewport = app.viewport
    samples = []
    for vid in _by_distance_to_center(app, app.scene.mesh.all_vertex_ids()):
        if len(samples) >= count:
            break
        if not _clickable(app, vid):
            continue
        x, y = _screen(app, vid)
        for timer in timers:
            timer.elapsed = 0.0
        start = time.perf_counter()
        changed = app.pointer_motion(x, y)
        picked = time.perf_counter()
        viewport.sync()
        if changed:
            overlay_s = sum(timer.elapsed for timer in timers)
            samples.append((picked - start + overlay_s) * 1000.0)
    return samples or [0.0]


def report_lines(results: list[ProbeResult], moves: int) -> list[str]:
    lines = ["Symmetry Lab — Drag-Kosten (WP-SYM-LAB-03 Slice 2, Plan A3)"]
    lines.extend(machine_info())
    lines.append(
        f"Ablauf: Symmetrie X, Auswahl per Klick, W + {moves} Mausbewegungen; "
        f"Schwelle p95 <= {THRESHOLD_P95_MS:.0f} ms je Bewegung (Transform + Lab-Overlays)"
    )
    for r in results:
        verdict = "OK" if r.within_threshold else "UEBERSCHRITTEN"
        lines.append("")
        lines.append(
            f"{r.asset}: {r.vertex_count} V, Auswahl {r.selected} V, bewegt {r.moved} V "
            f"(mit Partnern) — {verdict}"
        )
        lines.append(f"  Bewegung gesamt  {r.total.text()}  ms")
        lines.append(f"  Transform-Schritt {r.transform.text()}  ms")
        lines.append(f"  Lab-Overlays     {r.lab_overlays.text()}  ms")
        lines.append(f"  (übriger sync    {r.viewport_rest.text()}  ms, App-Puffer, nicht in der Schwelle)")
        lines.append(f"  (Commit-Frame    {r.commit_sync.text()}  ms, erster sync danach, einmal je Drag)")
        lines.append(f"  (Hover-Wechsel   {r.hover.text()}  ms, Pick + Lab-Overlays, ohne Transform)")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Drag-Kosten des Symmetry Lab auf dem App-Pfad (WP-SYM-LAB-03 A3)"
    )
    parser.add_argument("--assets", nargs="+", default=list(DEFAULT_ASSETS),
                        help="Registry-Namen (Default: head_basemesh man_with_shoes_basemesh)")
    parser.add_argument("--moves", type=int, default=DEFAULT_MOVES,
                        help=f"Mausbewegungen je Asset (Default: {DEFAULT_MOVES})")
    args = parser.parse_args(argv)
    results = [run_probe(asset, args.moves) for asset in args.assets]
    for line in report_lines(results, args.moves):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
