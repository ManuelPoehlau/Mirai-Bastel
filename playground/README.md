# Mirai-Bastel — Artist Playground

Experimentier-Host für UX-Fragen (Viewport-Display, Selection-Philosophie, Interaction) vor Production-Entscheidungen.

## Start

```bash
python playground/run.py                        # Cube
python playground/run.py head                   # Head-Basemesh
python playground/run.py subd_cube              # SubD-Cube (statt Default-Würfel)
python playground/run.py man_with_shoes_basemesh  # Charakter-Basemesh
python playground/run.py grid                   # flaches 8x8-Quad-Raster (Connect Lab)
```

Als Startszene gültig ist jeder Registry-Name der geteilten OBJ-Assets
(`examples/loaders/assets.py`, AD-007); unbekannte Argumente fallen auf den Würfel zurück.

Fenster öffnet mit HUD (Kamera, Mesh-Info, aktuelles Experiment, Display-Modus, Selection-Count).

**Session-State:** Beim Neustart stellt das Playground die zuletzt benutzte Einrichtung wieder her —
fokussierte Family (Tab), aktive Variante je Family (M) sowie Display-Modus und Wireframe-Overlay.
Gespeichert wird in `playground/.session_state.json` (user-lokal, nicht in git) bei jedem Wechsel und beim
Schließen; Varianten werden über ihren Klassennamen identifiziert. Nicht gespeichert: Komponenten-Modus (1/2/3),
Selection-Method (Shift+M), Mesh, Selection, Undo, Kamera. Unbekannte oder kaputte Einträge fallen einzeln auf die
Registry-Defaults zurück (eine Logzeile). Zurück zu den reinen Defaults: `python playground/run.py --reset-state`
(die Datei wird beim nächsten Wechsel bzw. Schließen überschrieben). Reine Session-Bequemlichkeit — keine Entscheidung,
keine Promotion. Der Selection-Default ist Modifier (`experiments/selection/decision.md`).

## Bedienung

→ **[MANUAL.md](MANUAL.md)** für alle Tasten und Bedienung

**Schnell-Übersicht:**
- **Kamera:** LMB = Orbit, MMB = Pan, Mausrad = Zoom
- **Display:** D = Modus cyclen, Z = Wireframe-Overlay, V = Vertices
- **Selection:** LMB-Click = Face selecten (abhängig vom Modus)
- **Szene:** C = Cube, H = Head (weitere geteilte Assets per Startparameter, s. oben)
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

### Weitere Familien (Stand 2026-09-29)

`transform/`, `connect/`, `knife/`, `knife_face/`, `topology/`, `tweak/`, `articulation/` — jeweils unter
`playground/experiments/<familie>/`. Verdikte stehen in der `decision.md` der Familie (vorhanden für
`selection`, `transform`, `connect`, `knife_face`; Tweak: `tweak_decision.md`). Ein Lab-Verdikt ist keine Promotion;
entschiedene Ergebnisse gelangen einzeln in die Production-App (WP-06, siehe `docs/architecture/ROADMAP.md` §7).

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
- Der frühere Referenz-Harness `experiments/mirai_bastel_integration_lab/` wurde entfernt; seine Funktionen sind nach `src/mirai/` übergegangen ([AD-008](../docs/architecture/AD-008-IMPORT-FRAMING-PRODUCTION.md))
