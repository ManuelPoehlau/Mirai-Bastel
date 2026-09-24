# Symmetry Lab (WP-SYM-LAB-01)

Eigenständiges Forschungsfenster für die Symmetrie-Arbeit. **Stand: Slice 3** — das Lab zeigt
ein Mesh (shaded + Edges + Vertices), navigiert mit Orbit/Pan/Zoom, wählt per Klick einen
Vertex aus, schaltet mit Shift+S die Symmetrie-Ebene durch (aus → X → Y → Z → aus), zeigt
Ebene, Seam, Vertices ohne Partner und den gespiegelten Partner der Auswahl, und verschiebt mit
Q + LMB-Drag einen Vertex symmetrisch. Jede Handlung (Symmetrie-Schritt oder Move) ist genau ein
Undo-Schritt.

Handoffs:
[Slice 2](../../docs/architecture/WP-SYM-LAB-01_SLICE2_CLAUDE_CODE_HANDOFF.md) (Rendering/Kamera, §2),
[Slice 3](../../docs/architecture/WP-SYM-LAB-01_SLICE3_CLAUDE_CODE_HANDOFF.md) (Symmetrie + Move, Entscheidungen A1/A2, E1–E6 in §2).

> **Importiert nicht aus `playground/`.** Benötigte Draw-Stücke sind kopiert/adaptiert, mit
> Herkunftsvermerk im jeweiligen Docstring (Präzedenz AD-010). Abgesichert durch
> `tests/test_import_boundary.py`.

## Start

Vom Repo-Root aus (Windows-Eingabeaufforderung/PowerShell und Linux identisch):

```
python experiments/symmetry_lab/run.py                          # subd_cube (Default)
python experiments/symmetry_lab/run.py head_basemesh
python experiments/symmetry_lab/run.py man_with_shoes_basemesh
```

Gültige Namen sind die Registry-Namen aus `examples/loaders/assets.py` (`asset_names()`).
Ein unbekannter Name bricht **vor** dem Öffnen des Fensters mit der Liste der gültigen Namen ab
(Exit-Code 2). Voraussetzung wie beim Playground: `pyglet` ist installiert
(`python -m pip install pyglet`). Beim Start listet die Konsole die aktiven Lab-Overrides.
Schließen: ESC (wenn kein Move scharf ist oder läuft) oder Fenster-X.

### Manuelle Prüfung Slice 3 (Manu, Windows) — offen

Noch **nicht** vom Artist validiert. Vorschlag für die Prüfung:

1. Terminal öffnen, in den Repo-Ordner wechseln (`cd <pfad>\Mirai-Bastel`).
2. `python experiments/symmetry_lab/run.py head_basemesh` starten. Die Konsole listet jetzt
   zusätzlich `key:Shift+s -> SymmetryCycle`. Statuszeile unten links:
   `Symmetrie: aus (off) | Move: bereit | Auswahl: —`.
3. **Shift+S** drücken → hellblauer Rechteck-Umriss in der Ebene x = 0 um den Kopf, grüne
   Punkte auf der Mittellinie (Seam). Statuszeile: `Symmetrie: X (valid) | ohne Partner: 0`.
4. Weiter **Shift+S** → `Y (partial)`, dann `Z (partial)`: Umriss liegt jeweils in der anderen
   Ebene, alle Vertices werden magenta (ohne Partner — der Kopf ist dort nicht symmetrisch).
   Noch einmal **Shift+S** → `aus`, Umriss und Markierungen verschwinden. Wieder auf **X**
   schalten.
5. LMB-Klick auf einen Vertex seitlich am Kopf → Vertex rot, der gespiegelte Partner auf der
   anderen Seite türkis (Vorschau, noch nichts bewegt).
6. **Q** drücken → Statuszeile `Move: scharf`. Optional vorher noch mit Alt+LMB die Ansicht
   drehen — das geht, solange Move scharf ist. Dann **LMB gedrückt halten und ziehen** →
   Vertex und Partner bewegen sich spiegelbildlich (`Move: zieht`). Loslassen →
   `Move übernommen`, `Move: bereit`.
7. **Ctrl+Z** → beide Seiten springen exakt zurück, Auswahl ist leer. **Ctrl+Z** noch einmal →
   Symmetrie ist wieder `aus` (nimmt das letzte Shift+S aus Punkt 4 zurück). **Ctrl+Y** →
   wieder `X`.
8. Abbrechen: Vertex wählen, **Q**, ziehen und **während des Ziehens ESC** → Vertex springt
   zurück, kein Undo-Schritt entsteht. **Q** und dann **ESC** (ohne Ziehen) → nur entschärft,
   Fenster bleibt offen. ESC im Leerlauf schließt wie bisher das Fenster.
9. Seam: einen grünen Vertex wählen, **Q**, ziehen → er gleitet nur entlang der Mittelebene.
10. **Q ohne Auswahl** → Statuszeile meldet `Move: keine Auswahl`, nichts wird scharf.
11. `python experiments/symmetry_lab/run.py man_with_shoes_basemesh`, **Shift+S** →
    `Symmetrie: X (partial) | ohne Partner: 54`; die 54 Vertices sind magenta markiert (siehe
    Befund E4 unten).

### Manuelle Prüfung Slice 2 — von Manu am 2026-09-24 geprüft

Start, Orbit/Pan/Zoom, Vertex-Klick wie beschrieben (laut Slice-3-Handoff). Zur Referenz:

1. Terminal öffnen, in den Repo-Ordner wechseln (`cd <pfad>\Mirai-Bastel`).
2. `python experiments/symmetry_lab/run.py` starten → Fenster „Mirai-Bastel — Symmetry Lab
   [subd_cube]" mit blau-grauem Mesh, dunklen Edges, orangen Vertex-Punkten, Statuszeile unten
   links.
3. Alt+LMB ziehen → Orbit. Shift+LMB ziehen und MMB ziehen → Pan. Mausrad → Zoom.
   RMB ziehen → **nichts** (bewusst ungebunden).
4. LMB-Klick auf einen Vertex → Vertex wird rot und größer, Statuszeile zeigt `Auswahl: v<id>`.
   Klick auf einen anderen Vertex ersetzt die Auswahl. Klick ins Leere leert sie.
5. Dasselbe mit `head_basemesh` und `man_with_shoes_basemesh` wiederholen.

## Steuerung

| Aktion | Input | Command | Herkunft |
|---|---|---|---|
| Orbit | Alt+LMB (Drag) | `Orbit` | Lab-Override — Artist Truth + Playground-Praxis |
| Pan | MMB (Drag) | `Pan` | globaler Default (Fallback) |
| Pan | Shift+LMB (Drag) | `Pan` | Lab-Override — Artist Truth + Playground-Praxis |
| Zoom | Wheel Up/Down | `Zoom` | globaler Default (Fallback) |
| Vertex auswählen | LMB (Klick) | `Select` | globaler Default (Fallback) |
| — | RMB | *explizit ungebunden* | Lab-Override — eine Primärbindung pro Funktion |
| Symmetrie durchschalten (aus → X → Y → Z → aus) | Shift+S | `SymmetryCycle` (Lab-lokal) | Lab-Override — Artist A2 |
| Move scharf schalten | Q | `Move` | globaler Default (Fallback) |
| Move ziehen (wenn scharf) | LMB ohne Modifier (Drag) | — (Lab-Geste, `MoveTool`) | Artist A1, E5 |
| Abbrechen | ESC | `Cancel` | globaler Default (Fallback) |
| Undo / Redo | Ctrl+Z / Ctrl+Y | `Undo` / `Redo` | globaler Default (Fallback) |

`SymmetryCycle` ist im Lab definiert (`lab_bindings.py`), nicht in `mirai.interaction.commands`.
Andere global gebundene Commands (z. B. `f` → `SetFaceMode`) lösen zwar auf, sind im Lab aber
No-ops und gelten als „nicht behandelt".

**Drag/Klick-Semantik (Lab-lokal, AD-013 A3 bleibt offen):** Der Press bestimmt das Command;
Orbit/Pan laufen bis zum Release derselben Maustaste, auch wenn währenddessen Modifier
losgelassen werden. Select wird beim Release ausgeführt, wenn die Maus weniger als 5 px
(Manhattan-Summe, wie Playground) bewegt wurde; sonst passiert nichts (kein Box-Select).

**Move (Slice 3, one-shot — E5):** Q schaltet nur mit Auswahl scharf. Solange scharf, startet
ausschließlich LMB ohne Modifier den Move; Alt+LMB, Shift+LMB, MMB und Wheel navigieren weiter,
ein Klick wählt nichts aus. Release unter 5 px Bewegung → `cancel()` (kein Undo-Schritt), sonst
`commit()` (genau ein Undo-Schritt); in beiden Fällen ist Move danach entschärft — für den
nächsten Move erneut Q. Während eines Move-Drags werden Shift+S, Q, Ctrl+Z/Ctrl+Y und weitere
Maus-Presses ignoriert; nur ESC bricht ab.

**ESC-Regel:** Move-Drag läuft → Abbruch auf den exakten Vorzustand, kein History-Eintrag;
Move nur scharf → entschärfen; sonst nicht behandelt → pyglet-Standard (Fenster schließt).

**Undo/Redo** leeren danach die Auswahl (wie Playground — ein Snapshot-Load kann Vertex-IDs
ungültig machen) und entschärfen einen scharfen Move.

## Farblegende

| Farbe | Bedeutung |
|---|---|
| blau-grau (shaded) | Faces |
| dunkelgrau | Edges |
| orange, klein | Vertex |
| rot, groß | ausgewählter Vertex |
| türkis, groß | gespiegelter Partner der Auswahl (`mirrored_selection`, Vorschau — INV-11) |
| grün, mittel | Seam-Vertex (Endpunkt einer deklarierten Seam-Edge) — nur bei aktiver Symmetrie |
| magenta, mittel | Vertex ohne Partner (`UNPAIRED`) — nur bei aktiver Symmetrie (INV-10) |
| weiß, mittel | Vertex mit mehrdeutigem Partner (`AMBIGUOUS`) — nur bei aktiver Symmetrie |
| hellblau, Linien | Umriss der Symmetrie-Ebene, auf die Mesh-Bounds + 10 % bemessen |

Punkte werden ohne Depth-Test gezeichnet (wie Slice 2): Rückseiten-Markierungen sind sichtbar.
Die Auswahl liegt über den Symmetrie-Markierungen.

## Symmetrie im Lab

- **Ebene (E1):** immer durch den Welt-Ursprung `(0, 0, 0)`, Normale exakt `(1,0,0)`, `(0,1,0)`
  oder `(0,0,1)`. Kein Mesh-Zentrum, keine freie Ebene.
- **Speicherort:** die Definition lebt im Mesh (`mesh.symmetry_definition`, AD-SYM-01), nicht im
  Lab. Jeder Shift+S-Schritt ist ein `MeshStateCommand` (Snapshot vorher/nachher, E2) — genau
  ein Undo-Schritt, keine neue History-Mechanik.
- **Lab-Annahme E3 (keine Capability-Regel):** Beim Wechsel auf eine Ebene wird die Seam
  **einmal** festgelegt als alle Edges, deren beide Endpunkte auf der Achse exakt `0.0` haben.
  Danach ist sie gespeicherte Deklaration (INV-1) und wird nicht laufend neu geprüft. Verlässt
  ein Seam-Vertex später die Ebene, zeigt die Capability das als `violated`.
- **Befund E4 (keine Toleranz):** `man_with_shoes_basemesh` auf X ergibt `partial` mit genau
  **54** Vertices ohne Partner — sie liegen ca. `1e-6` neben der Spiegelposition
  (OBJ-Rundung). Das Lab markiert sie magenta, korrigiert sie aber nicht und führt keinen
  Toleranzwert ein.
- **Move:** Das Lab reicht nur `scene`, `camera` und die Auswahl an `MoveTool`; ob und wie
  gespiegelt wird (Partner gespiegelt, Seam-Vertex auf die Ebene projiziert), entscheidet
  `MoveTool`/`MoveOperation` selbst aus der Definition im Mesh.

Charakterisierung der heutigen Assets (Tests in `tests/test_lab_symmetry.py`):

| Asset | X | Y | Z |
|---|---|---|---|
| `subd_cube` | 8 Seam-Edges, `valid` | 0 Seam-Edges, `partial` (26 ohne Partner) | 8 Seam-Edges, `valid` |
| `head_basemesh` | 36 Seam-Edges, `valid` | `partial` | `partial` |
| `man_with_shoes_basemesh` | 44 Seam-Edges, `partial`, 54 ohne Partner | `partial` | `partial` |

## Aufbau

```
pyglet-Event → mirai.pyglet_input → app.bindings.command_for(input, "symmetry_lab") → LabDispatcher
```

| Datei | Inhalt | GL nötig |
|---|---|---|
| `run.py` | Einstieg: Argument prüfen, `Application` + Lab-Bindings, Fenster, Event-Loop | – |
| `_paths.py` | sys.path-Bootstrap (`src/` vor Repo-Root, `examples/`, `experiments/`) | nein |
| `lab_bindings.py` | `SYMMETRY_LAB_CONTEXT`, `LAB_OVERRIDES` (einzige Quelle der Overrides) | nein |
| `lab_scene.py` | Asset per Registry-Name laden, Auswahl leeren, Kamera rahmen | nein |
| `lab_dispatch.py` | Command → Kamera-Geste / Vertex-Pick / Symmetrie-Zyklus / Move / Undo | nein |
| `lab_symmetry.py` | Ebene (E1), Seam-Ableitung (E3), Zyklus als `MeshStateCommand` (E2), Befund | nein |
| `lab_status.py` | Text der Statuszeile | nein |
| `lab_draw_data.py` | VBO-Daten (Faces/Edges/Vertices/Highlight/Ebenen-Umriss) | nein |
| `lab_render.py` | Shader + Vertex-Lists, Draw-Reihenfolge | ja |
| `lab_window.py` | pyglet-Fenster: Events übersetzen, zeichnen, Statuszeile | ja |

Zustand ausschließlich über `mirai.application.Application` (`scene`, `scene.selection`,
`camera`, `bindings`, `tool_manager`, `history`). Move läuft über `app.tool_manager` (Pattern A:
`activate` → `begin_current_interaction` → `update`* → `commit`/`cancel` → `deactivate`). Kamera ist die Production-`OrbitCamera` direkt. Kein `Viewport`, kein
`PygletStore`; bei Änderungen werden die Vertex-Lists komplett neu gebaut.

## Tests

```
python -m pytest experiments/symmetry_lab/tests
```

Headless: GL-freie Module werden direkt getestet. Tests, die `pyglet.window` brauchen
(Import-Grenze, Input-Pfad mit echten pyglet-Konstanten), setzen auf Linux ohne Display
`pyglet.options["headless"] = True` — Details und die Abweichung von Slice 1 in
`tests/_pyglet_headless.py`. Symmetrie-Zyklus und Move laufen headless über den Dispatcher
(`tests/test_lab_symmetry.py`, `tests/test_lab_move.py`).

## Beobachtungen aus Slice 2 (nicht gelöst, zur Einordnung)

- **Verdeckte Edges bei `subd_cube`:** Ein Teil der Edges wird von den Faces verdeckt. Ursache:
  stark nicht-planare Quads (Fan-Triangulierung) gegen den Depth-Test. Das Playground zeigt mit
  Wireframe-Overlay exakt dasselbe Bild — übernommenes Verhalten, kein Lab-Fehler. Bei
  `head_basemesh`/`man_with_shoes_basemesh` nicht auffällig.
- **Picking und Vertex-Punkte sind verdeckungsfrei** (wie Playground/`pick_nearest_vertex`):
  Rückseiten-Vertices sind sichtbar und anklickbar.
- **Shift+LMB-Konflikt:** In `artist_input_truth.json` ist Shift+LMB sowohl Pan als auch
  `selection.add`. Das Lab folgt der Playground-Praxis (Pan); die Auflösung ist eine
  Artist-Entscheidung.
- **Lab-Kontext nicht per `keymap.json` konfigurierbar:** `BindingSet.from_dict` akzeptiert nur
  die Kontexte `global`/`topology` (`_VALID_CONTEXTS` in `mirai.interaction.input`). Für dieses
  Slice egal; relevant, falls Lab-Bindings später extern überschreibbar sein sollen.
