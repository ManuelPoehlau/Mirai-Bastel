"""Default-Key- und Mouse-Bindings für den Viewport-Praxistest.

Abgeleitet aus dem bisherigen V1-Verhalten (siehe README/SELECTION_MODES):
- V/1, E/2, F/3  → Selection-Modi (bestehende Konvention, bleibt erhalten)
- Ctrl+Z / Ctrl+Y → Undo / Redo
- Esc             → laufende Interaktion abbrechen
- LMB             → Select (Klick toggelt; Drag startet Move)
- RMB             → Orbit
- Wheel           → Zoom (Dolly)

Neu hinzugekommen (bewusst minimal, keine unnötigen Hotkeys):
- MMB            → Pan (neue Navigation, Modeler-üblich)
- O              → Display-Modus wechseln (Shaded → Flat Shaded → Wireframe)
- W              → Wireframe Overlay AN/AUS

Die Topology-Lab-Keys (S/K/C/Shift+C/L/R) liegen im Kontext "topology" und
gelten nur dort (der GLOBAL_CONTEXT-Fallback greift nicht für sie).

Jede Bindung ist über die optionale `keymap.json` im Experiment-Ordner
überschreibbar (siehe input_binding.BindingSet / load_keymap_overrides).
"""

from __future__ import annotations

from pathlib import Path

from . import commands as cmd
from .input_binding import BindingSet, Input, TOPOLOGY_CONTEXT


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


def _mouse(value: str, *modifiers: str) -> Input:
    return Input("mouse", value, frozenset(modifiers))


def _wheel(direction: str) -> Input:
    return Input("wheel", direction)


def build_default_bindings() -> BindingSet:
    """Erzeugt die Default-Belegung für den Viewport (und das Topology Lab)."""
    bs = BindingSet()

    # --- Selection-Modi (bestehende V1-Konvention) -------------------------
    for value in ("v", "1"):
        bs.set_default(_key(value), cmd.SET_VERTEX_MODE)
    for value in ("e", "2"):
        bs.set_default(_key(value), cmd.SET_EDGE_MODE)
    for value in ("f", "3"):
        bs.set_default(_key(value), cmd.SET_FACE_MODE)

    # --- History / Interaktion ---------------------------------------------
    bs.set_default(_key("z", "ctrl"), cmd.UNDO)
    bs.set_default(_key("y", "ctrl"), cmd.REDO)
    bs.set_default(_key("ESCAPE"), cmd.CANCEL)

    # --- Display ------------------------------------------------------------
    bs.set_default(_key("o"), cmd.CYCLE_DISPLAY_MODE)
    bs.set_default(_key("w"), cmd.TOGGLE_WIREFRAME_OVERLAY)

    # --- Maus ----------------------------------------------------------------
    bs.set_default(_mouse("LEFT"), cmd.SELECT)
    bs.set_default(_mouse("RIGHT"), cmd.ORBIT)
    bs.set_default(_mouse("MIDDLE"), cmd.PAN)
    bs.set_default(_wheel("UP"), cmd.ZOOM)
    bs.set_default(_wheel("DOWN"), cmd.ZOOM)

    # --- Topology Lab (nur im Kontext "topology") ---------------------------
    bs.set_default(_key("s"), cmd.SPLIT_EDGE, context=TOPOLOGY_CONTEXT)
    bs.set_default(_key("k"), cmd.COLLAPSE, context=TOPOLOGY_CONTEXT)
    bs.set_default(_key("c"), cmd.CONNECT_VERTICES, context=TOPOLOGY_CONTEXT)
    bs.set_default(_key("c", "shift"), cmd.CONNECT_EDGES, context=TOPOLOGY_CONTEXT)
    bs.set_default(_key("l"), cmd.EDGE_LOOP, context=TOPOLOGY_CONTEXT)
    bs.set_default(_key("r"), cmd.EDGE_RING, context=TOPOLOGY_CONTEXT)

    return bs


def load_keymap_overrides(
    bindings: BindingSet, path: str | Path
) -> BindingSet:
    """Wendet eine optionale `keymap.json` als User-Overlay an.

    Existiert die Datei nicht, bleibt die Default-Belegung unverändert.
    """
    overlay = BindingSet.from_json_file(path)
    bindings.add_overrides(overlay)
    return bindings