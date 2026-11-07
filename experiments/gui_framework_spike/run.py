"""Production-Fenster mit dem imgui-Outliner (GUI-Framework-Spike). Start: `python experiments/gui_framework_spike/run.py [Szene]`.

Komponiert `src/main.py` (Fenster, Szene, Handler) und hängt den Layer an. `main.py` bleibt unverändert."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
for p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "examples"), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import main as production  # noqa: E402


def build(window=None, argv=None, with_panel: bool = True, **layer_kwargs):
    """Wie `production.main()`, aber ohne `run()`: gibt (window, app, layer) zurück. Die Szene bekommt für den Spike
    einen Zahn-Satz (Gruppe aus zwei Würfeln), damit der Outliner etwas zeigt."""
    from imgui_layer import ImguiLayer
    from mirai.interaction import commands

    argv = list(sys.argv[1:] if argv is None else argv)
    window = window or production.create_window("Mirai — Stage B + imgui spike")
    app = production.Application(keymap_path=production.KEYMAP_PATH)
    app.gizmo_enabled = True
    arg = argv[0] if argv else None
    path = Path(arg) if arg else production._DEFAULT_HEAD_OBJ
    if arg and not path.exists() and (_ROOT / "examples" / "meshes" / arg).exists():
        path = _ROOT / "examples" / "meshes" / arg
    if arg == "cube":
        app.init_scene("cube", **production.GL_TYPES)
    else:
        app.init_scene("obj", obj_path=path, **production.GL_TYPES)
    app.frame_scene()
    app.set_viewport_size(window.width, window.height)
    production.install_handlers(window, app, hud=production.Hud(app.bindings), triad=production.OrientationTriad(),
                                bone_tag=production.BoneTag())
    layer = ImguiLayer(window, app, open_panel=with_panel, **layer_kwargs) if with_panel is not None else None
    if layer is not None:
        layer.attach()
    return window, app, layer


def render_frame(window) -> None:
    """Ein Frame ohne Event-Loop (Messung, Screenshot). pyglet reiht Ereignisse außerhalb von `app.run()` in eine Queue:
    ohne `dispatch_pending_events` läuft `on_draw` nie."""
    window.switch_to()
    window.dispatch_event("on_draw")
    window.dispatch_pending_events()
    window.flip()


def add_demo_objects(app) -> None:
    from mirai.interaction import commands

    teeth = [app.add_primitive("cube", name=f"Zahn {i + 1}").id for i in range(4)]
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.selection.objects = set(teeth[:2])
    app.dispatch_command(commands.GROUP_OBJECTS)
    app.selection.objects = set()


def main() -> None:
    window, app, layer = build()
    add_demo_objects(app)
    production.run(window, app)


if __name__ == "__main__":
    main()
