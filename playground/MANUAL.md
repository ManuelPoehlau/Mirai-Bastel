# Artist Playground — Bedienungsanleitung

## Start

```bash
python playground/run.py          # Cube (Standard)
python playground/run.py head     # Head-Basemesh
```

Das Fenster öffnet mit dem Playground. Die HUD zeigt oben:
- Kamera-Position (Orbit-Winkel, Zoom-Abstand)
- Mesh-Info (Vertices, Edges, Faces)
- Aktives Experiment + Name
- Display-Modus + Auswahl
- Selection-Count + Modus

---

## Bedienung

### Kamera

| Taste | Aktion |
|---|---|
| LMB + ziehen | Orbit (Winkel ändern) |
| MMB + ziehen | Pan (Translation) |
| Shift + LMB + ziehen | Pan |
| Mausrad hoch/runter | Zoom rein/raus |

### Szene

| Taste | Aktion |
|---|---|
| C | Würfel laden |
| H | Head-Basemesh laden |
| Q, Esc | Fenster schließen |

### Display (Darstellung)

| Taste | Aktion |
|---|---|
| D | Display-Modus cyclen (Shaded → Flat → Wireframe → ...) |
| Z | Wireframe-Overlay an/aus (zusätzliche Kanten über Flächen) |
| V | Vertex-Punkte zeigen/verstecken |

**Modi:**
- **Shaded:** Glatte Schattierung (Standard)
- **Flat Shaded:** Facetten-Schattierung (per Face)
- **Wireframe:** Nur Kanten (keine Flächen)
- **+Wireframe:** Zusätz-Overlay über Shading

### Selection (Auswahl)

**LMB-Click** auf eine Face:
- Wählt die Face aus (orange Hervorhebung)
- Verhalten abhängig vom aktiven Selection-Modus

**Modi:**

| Modus | Verhalten |
|---|---|
| Replace | Click = Select. Andere Faces verlieren Auswahl. |
| Modifier | Click = Select. Shift = Hinzufügen, Ctrl = Entfernen, Alt = Toggle. |
| Toggle | Click = Toggle. Jeder Click wechselt den Zustand. |

**Beispiele:**

```
Replace-Modus:
  Click auf Face A → A selektiert
  Click auf Face B → nur B selektiert
  Click ins Leere → Selection geleert

Modifier-Modus:
  Click auf A → A selektiert
  Shift + Click auf B → A + B selektiert
  Ctrl + Click auf A → nur B selektiert (A entfernt)
  Alt + Click auf B → B wird abgewählt

Toggle-Modus:
  Click auf A → A selektiert
  Click auf A → A abgewählt
  Click auf B → B selektiert (A bleibt weg)
  Click ins Leere → nichts passiert
```

---

## Für Experimente

Checkliste zum Ausprobieren:

1. **Szene laden**
   - [ ] Würfel (C)
   - [ ] Head-Basemesh (H)

2. **Display ausprobieren**
   - [ ] Smooth Shaded (Start)
   - [ ] Flat Shaded (D)
   - [ ] Wireframe (D nochmal)
   - [ ] Flat + Wireframe-Overlay (D + Z)

3. **Selection-Modus testen**
   - [ ] Replace: Ein Click = ein Face selektiert
   - [ ] Shift: Mehrere Faces nacheinander selecten
   - [ ] Ctrl: Selektierte Face abwählen
   - [ ] Alt: Toggle (an/aus/an/...)

4. **Modifier ausprobieren**
   - [ ] Mit Shift mehrere Faces auswählen
   - [ ] Mit Ctrl eine Face wieder abwählen
   - [ ] Mit Alt eine Face togglen
   - [ ] Bare Click: Selection ersetzen

5. **Kamera bewegen**
   - [ ] Orbit (Winkel): LMB ziehen
   - [ ] Pan (verschieben): MMB ziehen
   - [ ] Zoom: Mausrad

6. **Unterschiede beobachten**
   - [ ] Wie wirkt Flat Shading auf dem Head vs. Würfel?
   - [ ] Hilft Wireframe-Overlay die Topologie zu verstehen?
   - [ ] Sind Vertices groß genug, um sie zu sehen?
   - [ ] Fühlt sich Replace vs. Modifier vs. Toggle unterschiedlich an?
   - [ ] Ist Click + Drag deutlich von Click unterschieden?

7. **UX-Verhalten notieren**
   - [ ] Was funktioniert gut?
   - [ ] Was fühlt sich falsch an?
   - [ ] Welcher Modus fühlt sich natürlich an?
   - [ ] Brauchst du Feedback (z.B. Highlight beim Hover)?

---

## Weitere Steuerung (erweitert)

Die Bindings sind konfigurierbar in `playground/input_map.py`:
- Display-Tasten: D, Z, V
- Selection-Button: LMB
- Modifier: Shift, Ctrl, Alt

Experimente können die Selection-Philosophie `SelectMode.REPLACE`, `SelectMode.MODIFIER` oder `SelectMode.TOGGLE` setzen.

---

## Hinweise

- **Production bleibt unverändert:** Der Playground nutzt Production-Code (Camera, Picking, Mesh, Selection), ändert aber nichts daran. Alle Experimente sind isoliert im `playground/`-Verzeichnis.
- **Headless testbar:** Core-Logik für Picking, Selection und Rendering ist rein Python, ohne GL. Tests validieren die Mathematik unabhängig vom Fenster.
- **Varianten statt Copies:** Unterschiedliche UX-Ansätze sind `Experiment`-Varianten im gleichen Playground — nicht mehrere parallele Implementierungen.
