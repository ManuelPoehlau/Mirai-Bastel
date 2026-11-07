# Outliner — Tastenvorschlag (zur Freigabe durch Manu)

Stand 2026-11-07. Die Objekt-Verwaltungs-Commands (`AD-021 §6.8`) sind implementiert, haben aber **keine Standardtaste**.
Nichts davon steht in `config/keymap.json`; eine Taste kommt erst nach deinem „passt“ (CLAUDE.md, Input).

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
| `DuplicateObjects` | **offen** | – | siehe unten |

Vorteil: Du lernst keine neue Familie. „H = verstecken, G = Gruppe“ gilt in beiden Ebenen.

## Duplizieren: eine echte Entscheidung

Alle `D`-Kombinationen sind durch Display/Licht belegt, `Ctrl+J`-Familie durch Bones, `Shift+D` ist Wireframe.
Optionen:

1. **`Ctrl+C`** — frei, merkbar („kopieren“), aber ohne Einfügen-Schritt: es dupliziert sofort an Ort und Stelle.
2. **Nur im Outliner-Panel** (Rechtsklick / Button), keine Taste — hält die Tastenbelegung klein.

Empfehlung: erst Option 2; eine Taste nachziehen, wenn du im Alltag merkst, dass du sie vermisst.

## Nicht vorgeschlagen
- Keine Taste für Sperren (gibt es noch nicht).
- `H` allein bleibt HUD an/aus (Window-Kontext).
