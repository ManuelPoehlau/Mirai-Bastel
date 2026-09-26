"""Headless evidence for Slice 1 (handoff E17; Xvfb or EGL, no visible window).

Usage (from the repo root):
    xvfb-run -a python experiments/viewport_shading_lab/evidence.py
    xvfb-run -a python experiments/viewport_shading_lab/evidence.py --bench 300

Prints the T1 baseline difference and the T2 zero-upload invariants, writes
one PNG per preset (plus the production reference) to `evidence/`, and with
`--bench N` compares the frame time of "Heute" against each preset.

The bench runs on whatever GL the machine offers — here software GL
(llvmpipe). Its numbers are a relative indication only, never a hardware
claim for Manu's PC.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

_EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent
if str(_EXPERIMENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_EXPERIMENTS_DIR))

from viewport_shading_lab._paths import EVIDENCE_DIR, ensure_paths  # noqa: E402

ensure_paths()

from viewport_shading_lab.lab_controls import ROW_IDS  # noqa: E402
from viewport_shading_lab.lab_rig import PRESET_HEUTE, PRESET_ORDER  # noqa: E402
from viewport_shading_lab.lab_scene import DEFAULT_ASSET  # noqa: E402

EVIDENCE_WIDTH, EVIDENCE_HEIGHT = 480, 360


def open_hidden_window(asset_name: str = DEFAULT_ASSET, captures_dir=None):
    """Hidden `ShadingLabWindow` at the fixed evidence size (headless-safe)."""
    import os

    import pyglet

    if sys.platform.startswith("linux") and not (
        os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    ):
        pyglet.options["headless"] = True
    from viewport_shading_lab.lab_window import ShadingLabWindow

    window = ShadingLabWindow(asset_name, EVIDENCE_WIDTH, EVIDENCE_HEIGHT,
                              visible=False, captures_dir=captures_dir)
    window.switch_to()
    # Hidden windows get no on_resize before the first event loop tick; set
    # the viewport explicitly so every draw covers the fixed evidence size.
    from pyglet import gl

    fb_width, fb_height = window.get_framebuffer_size()
    gl.glViewport(0, 0, fb_width, fb_height)
    return window


def upload_snapshot(window) -> dict:
    """Everything that would move if a rig change touched a buffer."""
    rm = window.scene.render_mesh
    stats = rm.stats
    return {
        "resource_ids": rm.resource_ids(),
        "vertex_list_id": id(rm.store.vertex_list()),
        "counters": dict(stats.counters),
        "uploaded_bytes": stats.uploaded_bytes,
        "resources": {k: dict(v) for k, v in stats.resource_snapshots.items()},
    }


def exercise_all_controls(window, draw=True) -> tuple[int, int]:
    """T2 workload through the real window handlers: every preset, every row
    stepped in both directions (fine and coarse, with the fill on), A/B
    toggles and LMB light drags — drawing a frame after each action.
    Handlers are called directly: pyglet queues `dispatch_event()` outside
    the event loop, which would make this workload silently do nothing.
    Returns (actions performed, distinct rigs actually displayed) so the
    caller can prove the workload changed what was drawn."""
    from pyglet.window import key, mouse

    actions = 0
    displayed = set()

    def frame():
        nonlocal actions
        actions += 1
        displayed.add(window.state.displayed_rig())
        if draw:
            window.on_draw()

    for fkey in (key.F1, key.F2, key.F3, key.F4):
        window.on_key_press(fkey, 0)
        frame()
        window.on_key_press(key.B, 0)
        frame()
        window.on_key_press(key.B, 0)
        frame()

    window.on_key_press(key.F2, 0)
    for start_preset in (key.F2, key.F1):
        window.on_key_press(start_preset, 0)
        for _ in ROW_IDS:
            for symbol in (key.RIGHT, key.LEFT):
                for modifiers in (0, key.MOD_SHIFT):
                    window.on_key_press(symbol, modifiers)
                    frame()
            window.on_key_press(key.DOWN, 0)
        window.on_key_press(key.UP, 0)
        frame()

    for dx, dy in ((12, 0), (-30, 8), (5, -20), (40, 40)):
        window.on_mouse_drag(200, 150, dx, dy, mouse.LEFT, 0)
        frame()
    window.on_key_press(key.B, 0)
    frame()
    window.on_mouse_drag(200, 150, 10, 0, mouse.LEFT, 0)
    frame()
    return actions, len(displayed)


def max_channel_diff(a: bytes, b: bytes) -> int:
    return max((abs(x - y) for x, y in zip(a, b)), default=0)


def render_rgba(window, rig_uniforms=None) -> bytes:
    from viewport_shading_lab.lab_scene import read_rgba

    window.scene.draw(rig_uniforms if rig_uniforms is not None else window.rig_uniforms())
    return read_rgba(EVIDENCE_WIDTH, EVIDENCE_HEIGHT)


def production_scene(window):
    from viewport.gl_render_store import GLRenderStore

    from viewport_shading_lab.lab_scene import build_scene

    return build_scene(window.scene.asset_name, GLRenderStore,
                       aspect=EVIDENCE_WIDTH / EVIDENCE_HEIGHT, camera=window.scene.camera)


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_").lower()


def bench(window, prod, frames: int) -> None:
    from pyglet import gl

    def measure(draw) -> tuple[float, float]:
        for _ in range(10):
            draw()
        gl.glFinish()
        samples = []
        for _ in range(frames):
            t0 = time.perf_counter()
            draw()
            gl.glFinish()
            samples.append((time.perf_counter() - t0) * 1000.0)
        return statistics.mean(samples), statistics.median(samples)

    print()
    print(f"--bench {frames}: Frame-Zeit pro Zeichnung (Mesh + resolve + glFinish)")
    print("  ACHTUNG: Software-GL (" + gl.gl_info.get_renderer() + ") — nur relative Angabe,")
    print("  keine Aussage über Hardware (Manus PC).")
    rows = [("Production GLRenderStore", lambda: prod.draw())]
    for name in PRESET_ORDER:
        def draw(name=name):
            window.state.apply_preset(name)
            window.draw_mesh()
        rows.append((f"Lab: {name}", draw))
    base_mean = None
    for label, draw in rows:
        mean, median = measure(draw)
        if label == f"Lab: {PRESET_HEUTE}":
            base_mean = mean
        rel = f"{mean / base_mean:5.2f}× Heute" if base_mean else "          "
        print(f"  {label:<28} Mittel {mean:7.3f} ms   Median {median:7.3f} ms   {rel}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Viewport Shading Lab — headless evidence")
    parser.add_argument("--bench", type=int, default=0, metavar="N",
                        help="N Frames pro Preset messen (Software-GL, nur relativ)")
    args = parser.parse_args(argv)

    from pyglet import gl

    window = open_hidden_window()
    print(f"GL: {gl.gl_info.get_version_string()} — {gl.gl_info.get_renderer()}")
    print(f"Mesh: {window.scene.asset_name}, {EVIDENCE_WIDTH}x{EVIDENCE_HEIGHT}")

    # T1 — baseline identity against the production store, same camera and size.
    prod = production_scene(window)
    window.state.apply_preset(PRESET_HEUTE)
    lab_pixels = render_rgba(window)
    prod.draw()
    from viewport_shading_lab.lab_scene import read_rgba, save_color_buffer_png

    prod_pixels = read_rgba(EVIDENCE_WIDTH, EVIDENCE_HEIGHT)
    print(f"T1 Baseline: max. Kanal-Differenz Production vs. „Heute“ = "
          f"{max_channel_diff(lab_pixels, prod_pixels)} (Grenze ≤ 1)")

    # T2 — zero upload across the full control workload.
    window.state.apply_preset(PRESET_HEUTE)
    window.on_draw()
    before = upload_snapshot(window)
    actions, distinct = exercise_all_controls(window)
    after = upload_snapshot(window)
    print(f"T2 Zero-Upload nach {actions} Aktionen (+ je ein Frame), "
          f"{distinct} verschiedene Rigs gezeichnet:")
    print(f"  resource_ids unverändert        = {before['resource_ids'] == after['resource_ids']}"
          f"  {after['resource_ids']}")
    print(f"  VertexList-Identität unverändert = {before['vertex_list_id'] == after['vertex_list_id']}")
    print(f"  Zähler unverändert               = {before['counters'] == after['counters']}"
          f"  {dict(sorted(after['counters'].items()))}")
    print(f"  uploaded_bytes unverändert       = {before['uploaded_bytes'] == after['uploaded_bytes']}"
          f"  ({after['uploaded_bytes']} B, alle aus dem initialen sync())")
    print(f"  Ressourcen-Snapshots unverändert = {before['resources'] == after['resources']}")
    print(f"  glGetError()                     = {gl.glGetError()}")

    # One PNG per preset (+ production reference).
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    prod.draw()
    save_color_buffer_png(str(EVIDENCE_DIR / "production_glrenderstore.png"))
    for index, name in enumerate(PRESET_ORDER, start=1):
        window.state.apply_preset(name)
        window.draw_mesh()
        path = EVIDENCE_DIR / f"f{index}_{_slug(name)}.png"
        save_color_buffer_png(str(path))
        print(f"PNG: {path.relative_to(_EXPERIMENTS_DIR.parent)}")

    if args.bench > 0:
        bench(window, prod, args.bench)

    window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
