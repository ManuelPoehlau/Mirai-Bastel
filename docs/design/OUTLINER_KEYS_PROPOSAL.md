# Outliner — Tasten (Hide/Gruppe freigegeben 2026-11-07)

Stand 2026-11-07. Manu: „ja, die Tasten sind ok“ — die sechs Hide/Gruppen-Tasten unten sind verdrahtet (Modus `4` lenkt sie auf Objekte,
`ObjectController.OBJECT_MODE_ROUTES`) und mit `"set": "2026-11-07"` in `config/keymap.json`. Duplizieren hat **keine Taste**
(`Ctrl+C`/`Ctrl+V` kopieren/einfügen; `DuplicateObjects` bleibt tastenlos für das Panel).

## Prinzip: keine neuen Tasten, wo es schon die passende Familie gibt

Der Bestand kennt das Muster schon: **Delete** löscht in Modus `4` Objekte statt Punkte. Gleiches Muster für Hide und Gruppen —
die Taste behält ihre Bedeutung, nur das Ziel folgt dem Modus (`1/2/3` = Komponenten, `4` = Objekte).

| Command | Taste | heute auf Komponenten | Bemerkung |
|---|---|---|---|
| `HideObjects` | `Ctrl+H` | Hide Selection | Modus `4`: ausgewählte Objekte/Gruppen ausblenden |
| `IsolateObjects` | `Ctrl+Shift+H` | Isolate Selection | Modus `4`: nur die Auswahl (+ Edit-Objekt) bleibt |
| `ShowAllObjects` | `Alt+H` | Show All | Modus `4`: alle Objekte wieder zeigen |
| `GroupObjects` | `Ctrl+G` | neue Region/Polygroup | Modus `4`: Auswahl in neue Gruppe |
| `SelectObjectGroup` | `Alt+G` | Region auswählen | Modus `4`: Gruppe des gewählten Objekts auswählen |
| `UngroupObjects` | `Ctrl+Alt+G` | Region entfernen | Modus `4`: Gruppe auflösen / Objekt herausnehmen |
| `CopyObjects` / `PasteObjects` | `Ctrl+C` / `Ctrl+V` | – | Modus `4` (Manu 2026-11-07: „der Klassiker“): C merkt sich die Auswahl, V fügt eine unabhängige Kopie am selben Ort ein, jeder Einfügeschritt ist ein Undo-Schritt |
| `DuplicateObjects` | keine Taste | – | gleiche Logik wie Ctrl+V auf der aktuellen Auswahl; für Panel/Rechtsklick |

Vorteil: Du lernst keine neue Familie. „H = verstecken, G = Gruppe“ gilt in beiden Ebenen.

## Duplizieren

Manu: Auswahl in Modus `4`, `Ctrl+C` / `Ctrl+V`. Eine Gruppe wird samt Mitgliedern kopiert; Objekte mit Morph-Zielen oder Gewichten
werden (noch) abgelehnt. Kopien sind ungepaart und liegen am selben Ort (W verschiebt die ausgewählte Kopie).

## Nicht vorgeschlagen
- Keine Taste für Sperren (gibt es noch nicht).
- `H` allein bleibt HUD an/aus (Window-Kontext).
