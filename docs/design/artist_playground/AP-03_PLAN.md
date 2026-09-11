# AP-03 — Selection Lab: Plan

**Branch:** `main`
**Basis:** Commit `b9b7ea6` (AP-02.5 Viewport Presentation Lab, eingefroren)
**Datum:** 2026-09-11

---

## Kontext

Die Presentation-Basis (AP-02.5) ist bereit: Smooth, Flat, Wireframe, Edges, Vertices, Kombinationen
sind kontrollierbar im Playground verfügbar. Bevor Selection implementiert wird, bauen wir zuerst
einen minimalen Input-Konfigurations-Baustein (Phase 0), damit die Selection-Experimente von Anfang
an frei umkonfigurierbar sind.

---

## Phase 0 — Playground Controls (Input-Config)

### Warum Phase 0?

Hardcodierte Tastenbindungen (wie `D`, `Z`, `V` in AP-02.5) sind für Darstellungs-Shortcuts
akzeptabel. Für Selection ist das anders: Welche Taste was auslöst, ist selbst Teil der Frage.
Wir wollen nicht erst Selection bauen und dann merken, dass wir die Bindings nicht tauschen können.

Phase 0 gibt uns einen **frei konfigurierbaren Experimentier-Werkzeugkasten** — kein neuer
Production-Input-Manager, nur eine einfache Mapping-Tabelle, die das Playground-Fenster konsultiert.

### Scope

Ein `PlaygroundInputMap`-Objekt (data class oder einfaches Dict-Wrapper):

```
Aktion              Default         Beschreibung
─────────────────────────────────────────────────
display_cycle       D               Display-Mode cyclen
wire_overlay        Z               Wireframe-Overlay togglen
show_vertices       V               Vertex-Darstellung togglen
select              LMB             Primary Select
add_select          Shift+LMB       Zur Selektion hinzufügen
remove_select       Ctrl+LMB        Aus Selektion entfernen
toggle_select       Alt+LMB         Selektion togglen
```

Spätere Erweiterungen (Phase 1+):

```
marquee_start       LMB drag        Box-Select starten
lasso_start         ?               Lasso-Select starten
paint_select        ?               Paint-Select
```

### Was Phase 0 NICHT ist

- Kein Production-Input-Manager
- Kein Event-Bus
- Kein Command-Pattern-Layer
- Keine Abstraktion über Modifier-Keys (die Bindings sind erst mal konkret)
- Keine UI zum Umkonfigurieren zur Laufzeit (Konfig passiert im Code)

### Implementierungsskizze

```python
# playground/input_map.py

from dataclasses import dataclass, field
from pyglet.window import key, mouse

@dataclass
class PlaygroundInputMap:
    # Display-Controls (AP-02.5)
    display_cycle:    int = key.D
    wire_overlay:     int = key.Z
    show_vertices:    int = key.V

    # Selection-Controls (AP-03)
    select_button:    int = mouse.LEFT
    add_modifier:     int = key.MOD_SHIFT
    remove_modifier:  int = key.MOD_CTRL
    toggle_modifier:  int = key.MOD_ALT
```

`PlaygroundWindow` bekommt ein `input_map: PlaygroundInputMap`-Feld.
`on_key_press` und `on_mouse_press` konsultieren die Map statt hardcodierter Konstanten.

Kein Refactoring der AP-02.5-Logik nötig — nur die existierenden `_key.D`/`_key.Z`/`_key.V`
gegen `self.input_map.display_cycle` etc. ersetzen.

### Tests Phase 0

Headless:
- `input_map` defaultet auf die erwarteten Werte
- `PlaygroundApp` hat kein `input_map` (liegt im Window, nicht im App-State)
- Beliebige Rebindung konfigurierbar (z.B. `E` statt `D`)

---

## Phase 1 — Single Select (Baseline)

### Forschungsfrage

> Was passiert, wenn der Artist auf ein Face/Vertex/Edge klickt?

### Was gebaut wird

1. **Picking-Bridge**: `picking.pick_nearest_face(ray)` → `scene.selection.set_selection([fid])`
   - Picking-Math existiert bereits (`src/mirai/viewport/picking.py`)
   - `core.Selection` existiert bereits
   - Die Verbindung Click → Ray → Hit → Selection-Update fehlt noch

2. **Click-Erkennung**: Im `on_mouse_release`-Handler (nach `drag_moved < threshold`):
   - Ray aus Screen-Koordinaten bauen (Camera.screen_to_ray)
   - Nächstes Hit ermitteln
   - `scene.selection` aktualisieren

3. **Selection-Feedback**: Sichtbare Darstellung der aktiven Selektion
   - Im Face-Modus: selektierte Faces farblich hervorheben
   - Basiert auf AP-02.5-Darstellungs-Infrastruktur (Overlay-Pass)
   - Noch kein Hover-Feedback (gehört in Phase 2)

### Experiment-Varianten

```
playground/experiments/selection/
    variant_face_select.py    ← Click → Face (Baseline)
    variant_vertex_select.py  ← Click → Vertex
    variant_edge_select.py    ← Click → Edge
    decision.md
```

---

## Phase 2 — Replace / Add / Remove / Toggle

### Forschungsfrage

> Was fühlt sich richtig an: Shift zum Hinzufügen, oder ist eine andere Philosophie besser?

### Varianten

| Variant | Semantik |
|---|---|
| A | Shift = Add, Ctrl = Remove, Alt = Toggle (Blender-ähnlich) |
| B | Click = Toggle (Max-ähnlich — kein Modifier nötig) |
| C | Click = Replace, Shift = Extend-to-nearest (Silo-ähnlich) |

Jede Variante = ein `Experiment` mit konfigurierter `InputMap`.

---

## Phase 3 — Marquee (Box-Select)

### Forschungsfrage

> Wie verhält sich Box-Select? Threshold für Drag vs. Click?

- Click < threshold → Single Select (Phase 1)
- Click + Drag > threshold → Marquee beginnt
- Marquee-Feedback: 2D-Rechteck-Overlay (reine 2D-Zeichnung im HUD-Layer)
- Hit-Test: Alle Faces/Vertices/Edges, deren projected center im Rechteck liegt

---

## Phase 4 — Lasso / Paint (optional)

Abhängig von Phase-3-Verdict. Lasso = Polygon-Marquee. Paint = kontinuierlicher
Hit-Test bei gedrückter Maustaste.

---

## Phase 5 — Vertex / Edge / Face Component Mode

### Forschungsfrage

> Wie wechselt der Artist zwischen den Komponenten-Modi?

- Separate Taste (z.B. `1`/`2`/`3` wie in Blender)?
- Kontextmenü?
- Automatisch aus Picking-Ergebnis?

---

## Phase 6 — Selection Feedback

### Forschungsfragen

- Wie groß/sichtbar müssen Vertices dargestellt werden?
- Welche Farbe/Intensität für Hover vs. Selected vs. Active?
- Brauchen wir zwei Highlight-Zustände (selected + active-element)?
- Wie verändert sich Feedback bei Wireframe vs. Shaded?

Diese Phase kann teilweise parallel zu Phase 2–4 laufen.

---

## Integration-Track (nach Phase 1–3)

Sobald Phase 1 (Single Select) und Phase 2 (Add/Remove) erste Kandidaten haben,
können wir die ersten kleinen Workflows testen:

```
Workflow 1: Face Select → Move → Undo
Workflow 2: Marquee → Add → Move → Undo
```

Workflow-Tests gehen ins Integration Lab, nicht in den Playground.

---

## Invarianten

```
src/core/      →  nie ändern
src/viewport/  →  nie direkt ändern (nur WRAP)
tests/         →  immer grün (383 Production-Tests)
```

Selection in AP-03 basiert ausschließlich auf:
- `core.Selection.set_selection()` / `add_to_selection()` / `remove_from_selection()`
- `picking.pick_nearest_*()` (bereits headless validiert)
- `Camera.screen_to_ray()` (bereits headless validiert)

Kein neues Selection-System bauen — Production-API direkt nutzen.

---

## Startreihenfolge

```
Phase 0 — Input-Config       ← als nächstes
Phase 1 — Single Select
Phase 6 — Feedback (parallel, minimal)
Phase 2 — Add / Remove / Toggle
Phase 3 — Marquee
Phase 4/5 — nach Artist-Verdict aus Phase 1–3
```
