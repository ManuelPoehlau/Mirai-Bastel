"""Living Mesh Research — Viewport-V1-Launcher des Rigging-Experiments.

Startet den vorhandenen All-Tools-Playground des Viewport-V1-Experiments mit
dem echten Head-Basemesh als Szene:

    meshes/head_basemesh.obj → loaders/obj_loader.py
                             → Mesh (mirai_bastel_core) → Scene
                             → AllToolsWindow (Viewport V1)

Kein Viewport-Fork und keine Viewport-Änderung: Die Fenster-Unterklasse
tauscht nur die Testszene (TopologyWindow besitzt bereits einen
scene-Parameter), richtet die Kamera auf die Mesh-Bounds aus und setzt den
Caption-Titel. Alle vorhandenen Tools laufen unverändert weiter (V/E/F
Selection, M Move, Shift+R Rotate, Shift+S Scale, X/Y/Z Achse, S Split,
R Ring, K Collapse, C Connect, L Loop, Alt+A, O Display, W Wire, Ctrl+Z/Y,
Esc).

Start: python run_viewport.py   (aus diesem Ordner)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap: Experiment-Ordner (viewport_adapter, loaders) + Viewport-V1-Ordner
# (viewport-Paket). Der Core-V1-Ordner wird von viewport_adapter selbst gesetzt.
_THIS_DIR = Path(__file__).resolve().parent
_VIEWPORT_V1_DIR = _THIS_DIR.parent / "mirai_bastel_viewport_V1"
for _path in (str(_THIS_DIR), str(_VIEWPORT_V1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import pyglet  # noqa: E402

# WICHTIG: viewport_adapter VOR den viewport-Modulen importieren — sein
# Bootstrap setzt experiments/mirai_bastel_core_V1 auf sys.path, das die
# viewport-Module (all_tools_app/topology_app) für mirai_bastel_core brauchen.
from viewport_adapter import (  # noqa: E402
    DEFAULT_HEAD_ASSET,
    build_scene_from_obj,
    format_debug_report,
    frame_camera_on_bounds,
)

from viewport.all_tools_app import AllToolsWindow  # noqa: E402
from viewport.topology_app import TopologyWindow  # noqa: E402


class LivingMeshResearchWindow(AllToolsWindow):
    """AllToolsWindow mit OBJ-Head-Szene statt Würfel-Testszene.

    Minimaler experimenteller Adapter ohne Änderung am Viewport-Code:
    AllToolsWindow.__init__ baut seine Würfel-Szene selbst, während
    TopologyWindow.__init__ bereits einen externen scene-Parameter besitzt.
    Deshalb wird TopologyWindow.__init__ explizit mit der OBJ-Szene
    aufgerufen und danach exakt derselbe Playground-State (_init_all_tools)
    aktiviert, den auch AllToolsWindow.__init__ nutzt. Falls sich der
    Initialisierungsablauf des Playgrounds ändert, muss nur dieser Adapter
    nachgezogen werden — nicht die Szene, nicht der Viewport.
    """

    # Klassen-Default wie in AllToolsWindow: _set_topology_caption läuft
    # bereits während TopologyWindow.__init__, BEVOR _init_all_tools die
    # Instanz-Variable setzt.
    _pending_axis: str | None = None

    def __init__(self, scene) -> None:
        TopologyWindow.__init__(self, scene=scene)
        self._init_all_tools()
        frame_camera_on_bounds(self.camera, self.scene.mesh)

    def _set_topology_caption(self, message: str | None = None) -> None:
        """Caption mit Living-Mesh-Research-Titel, sonst identische Belegung."""
        axis_text = self._pending_axis.upper() if self._pending_axis else "frei"
        text = (
            f"Mirai-Bastel — Living Mesh Research | {self.display_state.label} | "
            f"Achse: {axis_text} | "
            "V/E/F | M Move | Shift+R Rotate | Shift+S Scale | X/Y/Z Achse | "
            "S Split | R Ring | K Collapse | C Connect | L Loop | "
            "Alt+A None | Ctrl+Z/Y | O Display | W Wire | Esc Cancel"
        )
        if message:
            text += f" | {message}"
        self.set_caption(text)


def main() -> None:
    scene = build_scene_from_obj(DEFAULT_HEAD_ASSET)
    print(format_debug_report(DEFAULT_HEAD_ASSET.name, scene.mesh))
    LivingMeshResearchWindow(scene)
    pyglet.app.run()


if __name__ == "__main__":
    main()
