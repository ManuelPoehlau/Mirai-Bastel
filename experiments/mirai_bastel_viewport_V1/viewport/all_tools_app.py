"""All-Tools Playground: alle vorhandenen Viewport-Werkzeuge in einem Fenster.

Reines Experiment-Tool (kein WP-04, keine Production-UX): Dieser Launcher
führt die bereits vorhandenen und validierten Werkzeuge des
viewport_V1-Experiments — Selection, Topology-Werkzeuge
(Split/Collapse/Connect/Loop/Ring) und die modalen Transform-Tools
(Move/Rotate/Scale) — in einer einzigen kleinen Testanwendung zusammen.
Es wird keine neue Tool-Architektur gebaut; bestehende Module werden
unverändert weiterverwendet.

Integration (minimaler Adapter, keine Änderung an bestehenden Dateien):

- Basis ist der TopologyWindow (topology_app.py), damit S → Split und
  R → Ring ihre vorhandenen Hotkeys behalten. Der Playground ERGÄNZT im
  Kontext "topology" ausschließlich freie Bindings (Shift+R → Rotate,
  Shift+S → Scale, X/Y/Z → Achsen-Auswahl) und überschreibt keine
  bestehende Belegung. M → Move greift über den globalen Fallback.
- Achsen-Constraints: Die Transform-Tools unterstützen die Achsen-Auswahl
  bereits als begin()-Parameter (WP-03: axis=/axes=). Der Playground macht
  diesen vorhandenen Parameter über X/Y/Z wählbar, BEVOR eine Interaktion
  beginnt. Die Tool-Semantik bleibt unverändert: Die Achse wird im
  begin()-Moment fixiert; eine Umschaltung während eines laufenden Drags
  ist (wie bisher) nicht vorgesehen. X/Y/Z toggeln die Achse; die erneut
  gedrückte aktive Achse hebt die Beschränkung auf.
- Move besitzt in V1 keinen Achsen-Constraint (freie Kamera-Ebenen-Bewegung,
  siehe camera.screen_delta_to_world). AxisConstrainedMoveTool ist ein
  minimaler experimenteller MoveTool-Adapter, der das vorhandene
  pro-Event-Welt-Delta auf die gewählte Weltachse projiziert. Die
  MoveOperation bleibt unverändert (inkrementelle Deltas; die Projektion
  einzelner Deltas ist wegen der Linearität äquivalent zur Projektion des
  Gesamtdeltas).

Start: python run_all_tools.py   (aus dem Experiment-Ordner)
"""

from __future__ import annotations

from pathlib import Path

import pyglet

from mirai_bastel_core import SelectionMode, Scene

from . import commands as cmd
from . import vecmath as v
from .camera import OrbitCamera
from .default_bindings import build_default_bindings, load_keymap_overrides
from .demo_scene import build_cube_scene
from .input_binding import BindingSet, TOPOLOGY_CONTEXT, Input
from .move_tool import MoveTool
from .topology_app import TopologyWindow

# Optionale keymap.json im Experiment-Ordner (identisch zu app.py) bleibt
# als User-Overlay wirksam.
_KEYMAP_PATH = Path(__file__).resolve().parent.parent / "keymap.json"

# ---------------------------------------------------------------------------
# Playground-lokale Commands (bewusst NICHT in commands.py: nur der
# Playground kennt die Achsen-Vorwahl; bestehende Dateien bleiben unberührt)
# ---------------------------------------------------------------------------

AXIS_X = "PlaygroundAxisX"
AXIS_Y = "PlaygroundAxisY"
AXIS_Z = "PlaygroundAxisZ"

_AXIS_COMMANDS = {AXIS_X: "x", AXIS_Y: "y", AXIS_Z: "z"}

_WORLD_AXES = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


def build_all_tools_bindings() -> BindingSet:
    """Default-Belegung + Playground-Ergänzungen (nur freie Tasten).

    Basis ist vollständig build_default_bindings(); ergänzt werden im
    Kontext "topology" ausschließlich Belegungen, die dort frei sind:

        Shift+R → Rotate   (R bleibt EdgeRing, S bleibt SplitEdge)
        Shift+S → Scale
        X/Y/Z   → Achsen-Vorwahl für die nächste Transform-Interaktion

    M → Move wirkt über den globalen Fallback weiter.
    """
    bs = build_default_bindings()
    bs.set_default(
        Input("key", "r", frozenset({"shift"})), cmd.ROTATE, context=TOPOLOGY_CONTEXT
    )
    bs.set_default(
        Input("key", "s", frozenset({"shift"})), cmd.SCALE, context=TOPOLOGY_CONTEXT
    )
    bs.set_default(Input("key", "x"), AXIS_X, context=TOPOLOGY_CONTEXT)
    bs.set_default(Input("key", "y"), AXIS_Y, context=TOPOLOGY_CONTEXT)
    bs.set_default(Input("key", "z"), AXIS_Z, context=TOPOLOGY_CONTEXT)
    return bs


class AxisConstrainedMoveTool(MoveTool):
    """Experimenteller MoveTool-Adapter mit Weltachsen-Constraint.

    Ohne Achse (axis=None) verhält sich das Tool exakt wie das MoveTool
    (freie Bewegung entlang der Kamera-Bildebene). Mit Achse ("x"/"y"/"z")
    wird das vorhandene per-Event-Welt-Delta aus
    camera.screen_delta_to_world auf diese Achse projiziert und der
    bestehenden MoveOperation übergeben — es entsteht keine zweite
    Move-Mutationslogik (WP-02 §4.4).
    """

    def __init__(self, scene: Scene, camera: OrbitCamera) -> None:
        super().__init__(scene, camera)
        self._axis: v.Vec3 | None = None

    @property
    def axis(self) -> v.Vec3 | None:
        """Achse dieser Interaktion (None = frei, wie MoveTool)."""
        return self._axis

    def _on_begin(self, vertex_ids, axis=None, **params) -> None:
        super()._on_begin(vertex_ids, **params)
        if axis is None:
            self._axis = None
        else:
            self._axis = v.normalize(_WORLD_AXES[str(axis).lower()])

    def _on_update(self, dx: float, dy: float, width: int, height: int) -> None:
        if self._axis is None:
            super()._on_update(dx, dy, width, height)
            return
        # Identische Delta-Herkunft wie MoveTool, danach Achsen-Projektion.
        anchor_pos = self._scene.mesh.vertex_position(self._anchor_vertex)
        world_delta = self._camera.screen_delta_to_world(
            anchor_pos, dx, dy, width, height
        )
        constrained = v.scale(self._axis, v.dot(world_delta, self._axis))
        self._operation.update(delta=constrained)


class AllToolsWindow(TopologyWindow):
    """Testfenster: Cube-Szene + Selection + Topology-Tools + Transform-Tools."""

    # Klassen-Default, damit die Caption schon während TopologyWindow.__init__
    # (vor _init_all_tools) gefahrlos auf die Achsen-Vorwahl zugreifen kann.
    _pending_axis: str | None = None

    def __init__(self) -> None:
        # Testszene: ein sichtbarer Würfel (bewusst keine Topology-Grid-Szene).
        super().__init__(scene=build_cube_scene(size=2.0))
        self._init_all_tools()

    def _init_all_tools(self) -> None:
        """Pyglet-freier Playground-Zustand (headless testbar, WP-02-Muster)."""
        self._pending_axis = None
        # Default + Playground-Ergänzungen + optionales keymap.json-Overlay.
        self.bindings = load_keymap_overrides(
            build_all_tools_bindings(), _KEYMAP_PATH
        )
        # Start im Vertex-Mode: Transform-Tests zuerst, Topology-Tools melden
        # falschen Mode/Selection über die Caption (bestehendes Verhalten).
        self._set_selection_mode(SelectionMode.VERTEX)
        self._set_topology_caption()

    # -- Bindings/Commands ---------------------------------------------------

    def _dispatch_command(self, command) -> bool:
        if command == cmd.MOVE:
            # Playground-Routing: Move immer über den Achsen-Adapter
            # (ohne Achse exakt das MoveTool-Verhalten).
            self._activate_tool(AxisConstrainedMoveTool)
            return True
        axis = _AXIS_COMMANDS.get(command)
        if axis is not None:
            # Toggle: aktive Achse erneut drücken hebt die Beschränkung auf.
            self._pending_axis = None if self._pending_axis == axis else axis
            self._set_topology_caption()
            return True
        return super()._dispatch_command(command)

    def _start_move_interaction(self, vertex_ids) -> None:
        """Tweak-/Modal-Begin mit vorhandener Achsen-Vorwahl.

        Wie ModelerWindow._start_move_interaction, aktiviert aber den
        Playground-Adapter und übergibt die Achse als begin()-Parameter:
        RotateTool liest axis=, ScaleTool axes=, der Move-Adapter axis=.
        Andere aktive Tools ignorieren die Extra-Parameter (**params).
        """
        if self._tool_manager.active_tool is None:
            self._tool_manager.activate(
                AxisConstrainedMoveTool(self.scene, self.camera)
            )
            self._tweak_tool = True
        else:
            self._tweak_tool = False
        params: dict = {"vertex_ids": vertex_ids}
        if self._pending_axis is not None:
            params["axis"] = self._pending_axis
            params["axes"] = self._pending_axis
        self._tool_manager.begin(**params)
        self._drag_mode = "tool"

    # -- Caption (komplette Playground-Belegung) ------------------------------

    def _set_topology_caption(self, message: str | None = None) -> None:
        axis_text = self._pending_axis.upper() if self._pending_axis else "frei"
        text = (
            f"All-Tools Playground | {self.display_state.label} | Achse: {axis_text} | "
            "V/E/F | M Move | Shift+R Rotate | Shift+S Scale | X/Y/Z Achse | "
            "S Split | R Ring | K Collapse | C Connect | L Loop | "
            "Alt+A None | Ctrl+Z/Y | O Display | W Wire | Esc Cancel"
        )
        if message:
            text += f" | {message}"
        self.set_caption(text)


def main() -> None:
    AllToolsWindow()
    pyglet.app.run()


if __name__ == "__main__":
    main()
