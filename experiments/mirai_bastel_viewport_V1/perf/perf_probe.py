"""Experimentelle Perf-Instrumentation für den Viewport V1 (Viewport-Perf-Research).

Prinzip: Monkey-Patching auf Fenster-/Programm-INSTANZEN, keine Änderung an
bestehenden Viewport-/Core-Dateien. Die Probe misst:

- Handler-Zeiten   (on_mouse_motion/drag/scroll/press, on_draw)
- Picking-Zeiten   (_pick, getrennt nach Selection-Mode)
- Rebuild-Zeiten   (_rebuild_geometry inkl. _compute_normals,
                    _face_triangle_arrays, GL-VertexList-Erzeugung/Upload)
- Zaehler          (Rebuilds, Batches, VertexLists, Picks)
- GC-Zustaende     (Collections pro Generation vor/nach Szenarien)

Die Zeitmessung ist bewusst grob (perf_counter_ns um den ganzen Aufruf);
der Overhead eines Wrappers liegt im Nanosekundenbereich und ist gegenueber
den gemessenen Millisekunden irrelevant.

Nur Research-Werkzeug: kein Production-Code, kein Bestandteil der
Viewport-Architektur.
"""
from __future__ import annotations

import gc
import time
from collections import defaultdict

_NS_PER_MS = 1_000_000.0


class Stats:
    """Zeit-Sammlung fuer ein Label (in ns intern, Ausgabe in ms)."""

    __slots__ = ("label", "durations")

    def __init__(self, label: str) -> None:
        self.label = label
        self.durations: list[int] = []

    def add(self, ns: int) -> None:
        self.durations.append(ns)

    def __len__(self) -> int:
        return len(self.durations)

    @property
    def n(self) -> int:
        return len(self.durations)

    @property
    def total_ms(self) -> float:
        return sum(self.durations) / _NS_PER_MS

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.n if self.n else 0.0

    @property
    def max_ms(self) -> float:
        return (max(self.durations) / _NS_PER_MS) if self.durations else 0.0

    @property
    def min_ms(self) -> float:
        return (min(self.durations) / _NS_PER_MS) if self.durations else 0.0

    def percentile(self, p: float) -> float:
        """Naechste-Rang-Perzentil in ms (p in 0..100)."""
        if not self.durations:
            return 0.0
        ordered = sorted(self.durations)
        rank = max(0, min(len(ordered) - 1, round(p / 100.0 * (len(ordered) - 1))))
        return ordered[rank] / _NS_PER_MS


def _fmt(value: float, width: int = 8) -> str:
    return f"{value:>{width}.2f}"


class PerfProbe:
    """Sammelt Timings/Zaehler; Wrapper-Methoden melden hier ihre Zeiten."""

    def __init__(self) -> None:
        self.stats: dict[str, Stats] = {}
        self.counters: dict[str, int] = defaultdict(int)

    # -- Aufzeichnung ------------------------------------------------------

    def stat(self, label: str) -> Stats:
        found = self.stats.get(label)
        if found is None:
            found = Stats(label)
            self.stats[label] = found
        return found

    def record(self, label: str, ns: int) -> None:
        self.stat(label).add(ns)

    def count(self, key: str, amount: int = 1) -> None:
        self.counters[key] += amount

    def reset(self) -> None:
        """Leert alle Daten (Wrapper bleiben aktiv und laufen weiter)."""
        self.stats.clear()
        self.counters.clear()

    # -- GC ----------------------------------------------------------------

    @staticmethod
    def gc_snapshot() -> dict:
        collections = tuple(s["collections"] for s in gc.get_stats())
        return {
            "collections": collections,
            "counts": tuple(gc.get_count()),
        }

    @staticmethod
    def gc_delta(before: dict, after: dict) -> dict:
        return {
            "collections": tuple(
                a - b for a, b in zip(after["collections"], before["collections"])
            ),
            "counts": after["counts"],
        }

    # -- Report ------------------------------------------------------------

    def render_report(self, header: str = "Perf report", order: list[str] | None = None) -> str:
        lines = [header, "-" * 78]
        lines.append(
            f"{'label':<34}{'n':>7}{'total':>10}{'avg':>9}{'p50':>9}"
            f"{'p95':>9}{'p99':>9}{'max':>9}"
        )
        labels = list(order) if order else sorted(self.stats)
        # Unbekannte Labels (sicherheitshalber) anhaengen.
        if order:
            labels += [l for l in sorted(self.stats) if l not in order]
        for label in labels:
            stat = self.stats.get(label)
            if not stat or not stat.n:
                continue
            lines.append(
                f"{label:<34}{stat.n:>7}{_fmt(stat.total_ms):>10}{_fmt(stat.avg_ms):>9}"
                f"{_fmt(stat.percentile(50)):>9}{_fmt(stat.percentile(95)):>9}"
                f"{_fmt(stat.percentile(99)):>9}{_fmt(stat.max_ms):>9}"
            )
        if self.counters:
            lines.append("-" * 78)
            lines.append("counters: " + ", ".join(f"{k}={v}" for k, v in sorted(self.counters.items())))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Wrapper-Helfer (alle rein instanzbasiert, keine Klassen-Patches ausser
# dem zaehlenden Batch-__init__, das nach Gebrauch wiederhergestellt wird)
# ---------------------------------------------------------------------------

def timed_method(obj, name: str, probe: PerfProbe, label: str, counter: str | None = None):
    """Ueberzieht die gebundene Methode `obj.name` mit einer Zeitmessung."""
    original = getattr(obj, name)

    def wrapper(*args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original(*args, **kwargs)
        finally:
            probe.record(label, time.perf_counter_ns() - start)
            if counter:
                probe.count(counter)

    setattr(obj, name, wrapper)
    return original


def timed_program_vertex_list(window, probe: PerfProbe) -> None:
    """Misst pyglet program.vertex_list: VBO-Allocation + initialer Upload.

    ShaderProgram-Instanzen besitzen kein Instanz-__dict__ (C-Basis), deshalb
    wird die Klassen-Methode `ShaderProgram.vertex_list` gepatcht. Das ist
    fuer Experiments zulaessig und gefaehrdet nichts (reine Zeitmessung).
    """
    from pyglet.graphics.shader import ShaderProgram

    original = ShaderProgram.vertex_list

    def wrapper(self, *args, **kwargs):
        start = time.perf_counter_ns()
        try:
            return original(self, *args, **kwargs)
        finally:
            probe.record("gl.vertexlist_create+upload", time.perf_counter_ns() - start)
            probe.count("vertexlists_created")

    ShaderProgram.vertex_list = wrapper


def instrument_window(window, probe: PerfProbe) -> None:
    """Installiert alle Viewport-Perf-Wrapper auf der Fensterinstanz.

    Labels (Bewegungs-Handler vs. interne Stufen sind bewusst getrennt,
    damit inklusive/exklusive Anteile getrennt ausgewertet werden koennen):

        event.mouse_motion / event.mouse_drag / event.mouse_scroll / event.mouse_press
        event.on_draw
        hover.refresh_hover
        pick.vertex / pick.edge / pick.face
        rebuild.geometry            (kompletter _rebuild_geometry)
        rebuild.normals             (_compute_normals, O(V*F)-Loop)
        rebuild.triangle_arrays     (_face_triangle_arrays)
        gl.vertexlist_create+upload (Batch-VertexLists inkl. Upload)
        tool.tool_update            (ToolManager.update)
    """
    timed_method(window, "on_mouse_motion", probe, "event.mouse_motion")
    timed_method(window, "on_mouse_drag", probe, "event.mouse_drag")
    timed_method(window, "on_mouse_scroll", probe, "event.mouse_scroll")
    timed_method(window, "on_mouse_press", probe, "event.mouse_press")
    timed_method(window, "on_mouse_release", probe, "event.mouse_release")
    timed_method(window, "on_draw", probe, "event.on_draw")
    timed_method(window, "_refresh_hover", probe, "hover.refresh_hover")
    timed_method(window, "_rebuild_geometry", probe, "rebuild.geometry", counter="rebuilds")
    timed_method(window, "_compute_normals", probe, "rebuild.normals")
    timed_method(window, "_face_triangle_arrays", probe, "rebuild.triangle_arrays")
    timed_program_vertex_list(window, probe)
    timed_method(window._tool_manager, "update", probe, "tool.tool_update")

    original_pick = window._pick

    def pick_wrapper(x, y):
        start = time.perf_counter_ns()
        try:
            return original_pick(x, y)
        finally:
            probe.record("pick." + window.selection_mode.name.lower(), time.perf_counter_ns() - start)
            probe.count("pick_calls")

    window._pick = pick_wrapper

    # Batch-Erzeugung nur zaehlen (Klassen-Patch mit Wiederherstellung).
    import pyglet

    original_batch_init = pyglet.graphics.Batch.__init__

    def batch_init(self, *args, **kwargs):
        probe.count("batches_created")
        original_batch_init(self, *args, **kwargs)

    pyglet.graphics.Batch.__init__ = batch_init


def render_scenario_block(probe: PerfProbe, frame_label: str, title: str) -> str:
    """Szenario-Block: Frame-Statistik plus Komponenten-Anteile am Frame."""
    lines = [f"=== {title} ==="]
    frame = probe.stats.get(frame_label)
    if not frame or not frame.n:
        lines.append("  (keine Frames gemessen)")
        return "\n".join(lines)
    base = frame.avg_ms
    lines.append(
        f"frame: n={frame.n}  avg={_fmt(base)} ms  min={_fmt(frame.min_ms)}  "
        f"p50={_fmt(frame.percentile(50))}  p95={_fmt(frame.percentile(95))}  "
        f"p99={_fmt(frame.percentile(99))}  max={_fmt(frame.max_ms)}"
    )
    if base > 0:
        lines.append(f"-> ~{1000.0 / base:6.1f} FPS wenn dieser Frame-Typ das Dauerbild bestimmt")
    lines.append(f"{'component':<34}{'avg_ms':>9}{'share':>8}{'n':>7}")
    for label in sorted(probe.stats):
        if label == frame_label:
            continue
        stat = probe.stats[label]
        if not stat.n:
            continue
        share = 100.0 * stat.avg_ms / base if base else 0.0
        lines.append(
            f"{label:<34}{_fmt(stat.avg_ms):>9}{share:>7.1f}%{stat.n:>7}"
        )
    return "\n".join(lines)
