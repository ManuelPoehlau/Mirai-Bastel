"""Messung für das AD (Kriterien 2 und 3): Frame-Zeit mit/ohne imgui-Panel, Startzeit, Speicher, GL-Zustandslecks.

    xvfb-run -a python experiments/gui_framework_spike/bench.py [Mesh] [--frames N]

Unter xvfb läuft Mesa/llvmpipe (Software-GL): die absoluten Zeiten gelten nicht für den Referenz-PC, aussagekräftig ist
der Abstand zwischen den Varianten und die imgui-eigene Zeit (`layer.frame_ms`). Auf dem Referenz-PC mit echter GPU
dasselbe Skript ohne xvfb laufen lassen.
"""

from __future__ import annotations

import argparse
import resource
import statistics
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

t_import = time.perf_counter()
import run  # noqa: E402

from pyglet import gl  # noqa: E402
from pyglet.window import key, mouse  # noqa: E402

IMPORT_S = time.perf_counter() - t_import


def rss_mb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def timed_frames(window, n, orbit: bool) -> list[float]:
    out = []
    x, y = 700, 400
    if orbit:
        window.dispatch_event("on_mouse_press", x, y, mouse.LEFT, key.MOD_ALT)
    for i in range(n):
        if orbit:
            window.dispatch_event("on_mouse_drag", x + (i % 40), y, 1, 0, mouse.LEFT, key.MOD_ALT)
        t0 = time.perf_counter()
        window.switch_to()
        window.dispatch_event("on_draw")
        window.dispatch_pending_events()
        gl.glFinish()
        out.append((time.perf_counter() - t0) * 1000.0)
        window.flip()
    if orbit:
        window.dispatch_event("on_mouse_release", x, y, mouse.LEFT, key.MOD_ALT)
        window.dispatch_pending_events()
    return out


def variant(label, mesh, frames, panel: bool | None, open_panel=True, guard=True):
    t0 = time.perf_counter()
    window, app, layer = run.build(argv=[mesh], with_panel=open_panel, guard_gl=guard) if panel else _build_plain(mesh)
    if panel:
        run.add_demo_objects(app)  # (_build_plain tut dasselbe)
    for _ in range(5):
        run.render_frame(window)
    start_s = time.perf_counter() - t0
    result = {"label": label, "start_s": start_s}
    for mode in ("idle", "orbit"):
        t = timed_frames(window, frames, orbit=(mode == "orbit"))
        t = t[10:]
        result[mode] = (statistics.median(t), sorted(t)[int(len(t) * 0.95)])
    if layer is not None:
        ms = layer.frame_ms[15:]
        result["imgui_ms"] = (statistics.median(ms), sorted(ms)[int(len(ms) * 0.95)])
    result["rss_mb"] = rss_mb()
    if layer is not None:
        layer.close()
    window.close()
    return result


def _build_plain(mesh):
    import main as production

    window = production.create_window()
    app = production.Application(keymap_path=production.KEYMAP_PATH)
    app.gizmo_enabled = True
    app.init_scene("obj", obj_path=_mesh_path(mesh), **production.GL_TYPES) if mesh != "cube" else app.init_scene(
        "cube", **production.GL_TYPES)
    app.frame_scene()
    app.set_viewport_size(window.width, window.height)
    production.install_handlers(window, app, hud=production.Hud(app.bindings), triad=production.OrientationTriad(),
                                bone_tag=production.BoneTag())
    run.add_demo_objects(app)  # gleiche Szene wie die imgui-Varianten, sonst misst der Vergleich die Zusatzobjekte
    return window, app, None


def _mesh_path(name: str):
    p = Path(name)
    return p if p.exists() else run._ROOT / "examples" / "meshes" / name


def leak_report():
    """Zustandslecks in beide Richtungen: (a) was der Layer ohne Sicherung am GL-Zustand ändert, (b) ob der Zustand, den
    Production hinterlässt, den Layer stört (Zeichnen mit absichtlich 'schmutzigem' Zustand, Pixelvergleich)."""
    from imgui_layer import snapshot_gl_state

    window, app, layer = run.build(argv=["cube"], guard_gl=False)
    run.add_demo_objects(app)
    for _ in range(3):
        run.render_frame(window)
    window.switch_to()
    before = snapshot_gl_state()
    layer.draw()
    after = snapshot_gl_state()
    diff = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    layer.close()
    window.close()
    return diff


def dirty_state_report() -> str:
    """Richtung Production -> Layer: Zeichnen mit absichtlich verdrecktem GL-Zustand (Depth, Cull, Linien-Modus, Scissor,
    Depth-Maske aus, Blend aus) muss dieselben Pixel liefern wie mit sauberem Zustand."""
    import pyglet

    window, app, layer = run.build(argv=["cube"])
    run.add_demo_objects(app)
    for _ in range(3):
        run.render_frame(window)
    window.switch_to()

    def shot():
        gl.glFinish()
        img = pyglet.image.get_buffer_manager().get_color_buffer().get_image_data()
        return img.get_data("RGBA", img.width * 4)

    def clear():
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.7, 0.7, 0.7, 1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

    for _ in range(3):  # imgui passt Fenstergröße und Atlas in den ersten Frames an
        clear()
        layer.draw()
    clean = shot()
    clear()
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_CULL_FACE)
    gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_LINE)
    gl.glEnable(gl.GL_SCISSOR_TEST)
    gl.glScissor(0, 0, 3, 3)
    gl.glDepthMask(gl.GL_FALSE)
    gl.glDisable(gl.GL_BLEND)
    layer.draw()
    dirty_after = shot()
    leaked = bool(gl.glIsEnabled(gl.GL_DEPTH_TEST)) and bool(gl.glIsEnabled(gl.GL_SCISSOR_TEST))
    gl.glPolygonMode(gl.GL_FRONT_AND_BACK, gl.GL_FILL)
    gl.glDisable(gl.GL_SCISSOR_TEST)
    gl.glDepthMask(gl.GL_TRUE)
    layer.close()
    window.close()
    diff = sum(1 for a, b in zip(clean, dirty_after) if a != b)
    same = diff == 0
    same = f"{same} ({diff} Bytes verschieden)"
    return f"Pixel gleich bei verdrecktem Zustand: {same}; verdreckter Zustand nach dem Layer wiederhergestellt: {leaked}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mesh", nargs="?", default="gollum_20k.obj")
    ap.add_argument("--frames", type=int, default=150)
    ap.add_argument("--variant", choices=("plain", "open", "closed", "leaks"), required=True,
                    help="je Variante ein eigener Prozess (maxRSS und Startzeit sind sonst vermischt)")
    args = ap.parse_args()
    if args.variant == "leaks":
        print("GL-Zustand, den der Layer OHNE eigene Sicherung ändert:", leak_report() or "nichts")
        print(dirty_state_report())
        return
    if args.variant == "plain":
        r = variant("ohne imgui", args.mesh, args.frames, panel=False)
    else:
        r = variant("imgui, Panel " + ("offen" if args.variant == "open" else "zu (nur Knopf)"), args.mesh, args.frames,
                    panel=True, open_panel=args.variant == "open")
    extra = f"  imgui CPU {r['imgui_ms'][0]:.2f}/{r['imgui_ms'][1]:.2f}" if "imgui_ms" in r else ""
    print(f"{r['label']:<28} idle {r['idle'][0]:.2f}/{r['idle'][1]:.2f}  orbit {r['orbit'][0]:.2f}/{r['orbit'][1]:.2f}"
          f"  Start {r['start_s']:.2f}s  maxRSS {r['rss_mb']:.0f} MB{extra}   (Import {IMPORT_S * 1000:.0f} ms)")


if __name__ == "__main__":
    main()
