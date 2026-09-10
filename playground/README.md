# Mirai-Bastel — Artist Playground

Experimentier-Host für UX-Fragen (Viewport-Display, Selection-Philosophie, Interaction) vor Production-Entscheidungen.

## Start

```bash
python playground/run.py          # Cube
python playground/run.py head     # Head-Basemesh
```

Fenster öffnet mit HUD (Kamera, Mesh-Info, aktuelles Experiment, Display-Modus, Selection-Count).

## Bedienung

→ **[MANUAL.md](MANUAL.md)** für alle Tasten und Bedienung

**Schnell-Übersicht:**
- **Kamera:** LMB = Orbit, MMB = Pan, Mausrad = Zoom
- **Display:** D = Modus cyclen, Z = Wireframe-Overlay, V = Vertices
- **Selection:** LMB-Click = Face selecten (abhängig vom Modus)
- **Szene:** C = Cube, H = Head
- **Ende:** Q oder Esc

## Experimente

Aktuell verfügbar:

### Presentation (AP-02.5)
- Shaded, Flat Shaded, Wireframe, + Kombinationen
- 6 Varianten zum Durchklicken

### Selection (AP-03)
- **Replace:** Click = Select (wie Phase 1)
- **Modifier:** Shift=Add, Ctrl=Remove, Alt=Toggle
- **Toggle:** Jeder Click togglet (Max-ähnlich)

## Für Anpassungen

**Bindings konfigurieren:**
```python
from playground.input_map import PlaygroundInputMap
from pyglet.window import key, mouse

imap = PlaygroundInputMap(display_cycle=key.M, select_button=mouse.RIGHT)
window = PlaygroundWindow(app, input_map=imap)
```

**Neue Experiment-Varianten:**
```
playground/experiments/<experiment_id>/
    variant_a.py    # erbt von Experiment
    variant_b.py
```

**Selection-Modus ändern:**
```python
from playground.selector import SelectMode
app.select_mode = SelectMode.MODIFIER  # oder REPLACE, TOGGLE
```

## Architektur-Prinzipien

- **Kein Production-Code verändert:** Playground wrapped `src/core`, `src/viewport`, `src/mirai` — ändert nichts
- **Headless:** Picking, Selection, Rendering sind pure Python, nicht GL-abhängig
- **Varianten statt Copies:** Unterschiedliche UX-Ansätze sind `Experiment`-Instanzen, nicht separate Codebäume

## Siehe auch

- [MANUAL.md](MANUAL.md) — Vollständige Bedienungsanleitung
- [docs/design/artist_playground/](../docs/design/artist_playground/) — Architektur & Plan
- [experiments/mirai_bastel_integration_lab/](../experiments/mirai_bastel_integration_lab/) — Referenz-Harness
