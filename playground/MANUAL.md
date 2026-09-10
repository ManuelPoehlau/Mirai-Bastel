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

### Transform (Bearbeitung)

| Taste + Aktion | Effekt |
|---|---|
| X gedrückt halten + ziehen | Move (verschieben) |
| R gedrückt halten + ziehen | Rotate (drehen, Z-Achse) |
| S gedrückt halten + ziehen | Scale (skalieren, Z-Achse) |
| Losgelassen | Commit (Änderung speichern, ein History-Eintrag) |
| ESC während Drag | Cancel (Vorzustand wiederherstellen) |

**Workflow:**
1. Face(s) auswählen (LMB-Click, siehe Selection-Modus)
2. X/R/S gedrückt halten → Tool wird aktiviert
3. Während gedrückt: Mit der Maus ziehen → Live-Preview
4. Losgelassen → Commit (exakt ein Undo-Schritt)
5. Oder ESC vor Losgelassen → Cancel (keine Änderung)

**Modi:**
- **Shaded:** Glatte Schattierung (Standard)
- **Flat Shaded:** Facetten-Schattierung (per Face)
- **Wireframe:** Nur Kanten (keine Flächen)
- **+Wireframe:** Zusätz-Overlay über Shading

### Selection (Auswahl)

| Taste | Aktion |
|---|---|
| M | Selection-Modus cyclen (Replace → Modifier → Toggle) |
| LMB-Click | Face selecten (Verhalten hängt vom Modus ab) |
| Shift+LMB | Zur Selektion hinzufügen (nur im Modifier-Modus) |
| Ctrl+LMB | Aus Selektion entfernen (nur im Modifier-Modus) |
| Alt+LMB | Toggle (nur im Modifier-Modus) |

**LMB-Click** auf eine Face:
- Wählt die Face aus (orange Hervorhebung)
- Verhalten abhängig vom aktiven Selection-Modus (siehe HUD Zeile 5)

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
   - [ ] **Replace** (M um zu cyclen): Ein Click = ein Face, Andere verlieren Auswahl
   - [ ] **Modifier** (M nochmal): Shift = Hinzufügen, Ctrl = Entfernen, Alt = Toggle
   - [ ] **Toggle** (M nochmal): Jeder Click wechselt den Zustand

4. **Modifier ausprobieren**
   - [ ] Mit Shift mehrere Faces auswählen
   - [ ] Mit Ctrl eine Face wieder abwählen
   - [ ] Mit Alt eine Face togglen
   - [ ] Bare Click: Selection ersetzen

5. **Kamera bewegen**
   - [ ] Orbit (Winkel): LMB ziehen
   - [ ] Pan (verschieben): MMB ziehen
   - [ ] Zoom: Mausrad

6. **Transform ausprobieren (AP-04 Phase 1)**
   - [ ] Face(s) auswählen
   - [ ] X gedrückt halten + ziehen: Move (Vertex verschiebt sich live)
   - [ ] Losgelassen: Commit
   - [ ] Undo (Strg+Z): Änderung rückgängig? (Falls Production-History vorhanden)
   - [ ] R gedrückt halten + ziehen: Rotate (Vertex dreht sich)
   - [ ] S gedrückt halten + ziehen: Scale (Vertex skaliert)
   - [ ] ESC während Drag: Cancel (Änderung wird nicht gespeichert)

7. **Unterschiede beobachten**
   - [ ] Wie wirkt Flat Shading auf dem Head vs. Würfel?
   - [ ] Hilft Wireframe-Overlay die Topologie zu verstehen?
   - [ ] Sind Vertices groß genug, um sie zu sehen?
   - [ ] Fühlt sich Replace vs. Modifier vs. Toggle unterschiedlich an?
   - [ ] Ist Click + Drag deutlich von Click unterschieden?
   - [ ] Sind Drag-Bewegungen intuitiv (Move up = Vertex up)?
   - [ ] Ist der Zoom-Punkt korrekt (wo ist der Rotation-Pivot)?

8. **UX-Verhalten notieren**
   - [ ] Was funktioniert gut?
   - [ ] Was fühlt sich falsch an?
   - [ ] Welcher Modus fühlt sich natürlich an?
   - [ ] Brauchst du Feedback (z.B. Highlight beim Hover)?
   - [ ] Sollte die Transformation smoothed sein oder sofort?

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
