"""PlaygroundInputMap — frei konfigurierbares Input-Binding für den Playground.

Kein Production-Input-Manager. Eine einfache Dataclass, die das Playground-
Fenster konsultiert statt hardcodierter Konstanten. Erlaubt, Bindings pro
Experiment-Session frei zu tauschen.

Felder für AP-02.5 Display-Controls und AP-03 Selection-Controls sind bereits
definiert; der Selection-Code selbst kommt in AP-03 Phase 1.

Verwendung (run.py oder Experiment-Setup):
    from playground.input_map import PlaygroundInputMap
    from pyglet.window import key, mouse
    imap = PlaygroundInputMap(display_cycle=key.M, select_button=mouse.LEFT)
    window = PlaygroundWindow(app, input_map=imap)
"""

from __future__ import annotations

from dataclasses import dataclass

from pyglet.window import key, mouse


@dataclass
class PlaygroundInputMap:
    # -- Display-Controls (AP-02.5) ------------------------------------------
    display_cycle: int = key.D       # Display-Mode cyclen (Shaded → Flat → Wire)
    wire_overlay:  int = key.Z       # Wireframe-Overlay togglen
    show_vertices: int = key.V       # Vertex-Darstellung togglen

    # -- Selection-Controls (AP-03 Phase 1+) ---------------------------------
    # Felder bereits definiert; Wiring kommt in AP-03 Phase 1.
    select_button:    int = mouse.LEFT    # Primary Select
    add_modifier:     int = key.MOD_SHIFT   # Zur Selektion hinzufügen
    remove_modifier:  int = key.MOD_CTRL    # Aus Selektion entfernen
    toggle_modifier:  int = key.MOD_ALT     # Selektion togglen
