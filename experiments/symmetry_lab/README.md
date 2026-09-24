# Symmetry Lab (WP-SYM-LAB-01)

Eigenständiges Forschungsfenster für die Symmetrie-Arbeit. **Stand: Slice 2** — das Lab zeigt
ein Mesh (shaded + Edges + Vertices), navigiert mit Orbit/Pan/Zoom und wählt per Klick einen
Vertex aus. **Noch keine Symmetrie-Funktion, keine Mutation, kein Move** (kommt ab Slice 3).

Handoff: [`../../docs/architecture/WP-SYM-LAB-01_SLICE2_CLAUDE_CODE_HANDOFF.md`](../../docs/architecture/WP-SYM-LAB-01_SLICE2_CLAUDE_CODE_HANDOFF.md)
(Entscheidung Rendering/Kamera dort §2).

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
Schließen: ESC oder Fenster-X.

### Manuelle Prüfung (Manu, Windows) — offen

Noch **nicht** vom Artist validiert. Vorschlag für die Prüfung:

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

Keine Tastatur-Bindings. Andere global gebundene Commands (z. B. `f` → `SetFaceMode`) lösen
zwar auf, sind im Lab aber No-ops.

**Drag/Klick-Semantik (Lab-lokal, AD-013 A3 bleibt offen):** Der Press bestimmt das Command;
Orbit/Pan laufen bis zum Release derselben Maustaste, auch wenn währenddessen Modifier
losgelassen werden. Select wird beim Release ausgeführt, wenn die Maus weniger als 5 px
(Manhattan-Summe, wie Playground) bewegt wurde; sonst passiert nichts (kein Box-Select).

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
| `lab_dispatch.py` | Command → Kamera-Geste / Vertex-Pick | nein |
| `lab_draw_data.py` | VBO-Daten (Faces/Edges/Vertices/Highlight) | nein |
| `lab_render.py` | Shader + Vertex-Lists, Draw-Reihenfolge | ja |
| `lab_window.py` | pyglet-Fenster: Events übersetzen, zeichnen, Statuszeile | ja |

Zustand ausschließlich über `mirai.application.Application` (`scene`, `scene.selection`,
`camera`, `bindings`). Kamera ist die Production-`OrbitCamera` direkt. Kein `Viewport`, kein
`PygletStore`; bei Änderungen werden die Vertex-Lists komplett neu gebaut.

## Tests

```
python -m pytest experiments/symmetry_lab/tests
```

Headless: GL-freie Module werden direkt getestet. Tests, die `pyglet.window` brauchen
(Import-Grenze, Input-Pfad mit echten pyglet-Konstanten), setzen auf Linux ohne Display
`pyglet.options["headless"] = True` — Details und die Abweichung von Slice 1 in
`tests/_pyglet_headless.py`.

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
