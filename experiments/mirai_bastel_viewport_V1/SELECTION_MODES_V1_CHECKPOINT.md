# Selection Modes V1 — Checkpoint

**Status:** Selection + experimentelle Multi-Selection + Sub-Object-Move implementiert  
**Branch:** `main`  
**Experiment:** `experiments/mirai_bastel_viewport_V1`

## Ziel

Praxistest der klassischen Sub-Object-Selection-Modes im isolierten V1-Viewport, bevor weitere Selection-Funktionen aufgebaut werden.

## Implementiert

- **Vertex Mode** — nur Vertices sind pickbar.
- **Edge Mode** — nur Edges sind pickbar.
- **Face Mode** — nur Faces sind pickbar.
- Umschalten der Modi über `V`/`1`, `E`/`2` und `F`/`3`.
- Hover-Pick als visuelle Vorschau.
- Faces werden für den Viewport gefüllt gerendert.
- Face-Hover und Face-Selection verwenden einen kleinen Polygon-Depth-Bias, damit das Highlight über der Basisfläche sichtbar bleibt.
- Face-Picking erfolgt über Ray/Triangle-Hit-Testing; bei mehreren Treffern wird aktuell der nächstgelegene Treffer verwendet.
- Selection und Hover sind getrennte Zustände.
- Selection-Darstellung hat Vorrang vor der Hover-Darstellung.
- Klick ins Leere löscht die gesamte Selection.

## Experimentelle Multi-Selection

Für Vertex, Edge und Face gilt aktuell testweise eine einfache Toggle-Selection nach dem Vorbild des von uns gewünschten Wings-artigen Verhaltens:

- Klick auf ein **nicht ausgewähltes** Element → Element wird zur Selection hinzugefügt.
- Klick auf ein **bereits ausgewähltes** Element → Element wird aus der Selection entfernt.
- Klick auf ein weiteres Element → bisherige Selection bleibt bestehen.
- Klick ins Leere → gesamte Selection wird gelöscht.
- Keine Modifier-Tasten erforderlich.

Diese Logik ist ausdrücklich **experimentell** und noch keine endgültige Mirai-Selection-Spezifikation.

Beispiel:

```text
Face A klicken  → [A]
Face B klicken  → [A, B]
Face A klicken  → [B]
ins Leere       → []
```

## Sub-Object Move

Die aktuell ausgewählten Sub-Objects können über dieselbe vorhandene Core-`MoveOperation` verschoben werden:

- **Vertex Selection** → ausgewählte Vertices werden bewegt.
- **Edge Selection** → die beiden End-Vertices jeder ausgewählten Edge werden bewegt.
- **Face Selection** → alle Boundary-Vertices jeder ausgewählten Face werden bewegt.
- Bei mehreren Edges/Faces wird die betroffene Vertex-Menge als Union gebildet; gemeinsame Vertices werden dadurch nur einmal bewegt.
- Die bestehende Core-`MoveOperation` bleibt unverändert und erhält für das Viewport-Experiment lediglich eine aufgelöste Vertex-Selection.
- Undo/Redo läuft weiterhin über den vorhandenen History-Lifecycle der Move-Operation.

Damit ist der erste kleine praktische Modeling-Milestone erreicht:

```text
Selection → Multi-Selection → Move
Vertex     → Edge/Face       → Geometrie verschieben
```

## Bewusst noch nicht enthalten

- endgültig festgelegtes Multi-Selection-/Modifier-Verhalten
- Universal / All-in-One Selection Mode
- Object Mode
- Visible-Only vs. Through/X-Ray Selection
- ausgearbeitetes Farbsystem pro Vertex/Edge/Face-Mode
- Box/Lasso/Brush Selection
- Loop-/Ring-Selection und weitere Selection-Kommandos
- persistente Selection-Visualisierung über den V1-Testumfang hinaus

## Verifikation

Für die drei Sub-Object-Modi wurde der grundlegende Pfad praktisch getestet:

```text
Hover → Hit-Test → Highlight
Pick  → Selection → Selection-Highlight
```

Face Mode wurde zusätzlich mit Raycast-Debug verifiziert. Dabei wurden gültige `FaceId`-Treffer und die zugehörige Hover-Geometrie bestätigt. Der temporäre Debug-Schalter und die Debug-Ausgaben wurden anschließend entfernt.

Die direkte Darstellung nach dem Pick wurde ebenfalls geprüft: Bleibt der Cursor auf dem Element, wechselt die Darstellung unmittelbar von Hover zu Selection.

Die Toggle-Multi-Selection funktioniert inzwischen in allen drei Sub-Object-Modi.

Der Sub-Object-Move ist implementiert und nutzt für Edge/Face die Topologie-Query-API des Core-V1-Meshes zur Auflösung der betroffenen Vertices. Die praktische Verifikation von Vertex-, Edge- und Face-Move einschließlich Multi-Selection steht als nächster manueller Test an.

## Architekturhinweis

Die Selection-Logik bleibt bewusst einfach. Dieser Checkpoint soll nicht bereits die spätere vollständige Modeler-Selection definieren, sondern eine belastbare Grundlage für weitere Tests liefern.

Insbesondere soll die spätere Entscheidung zwischen **Visible Only** und **Through/X-Ray** auf dem bestehenden Hit-Test aufbauen können, ohne die aktuellen Selection Modes neu entwerfen zu müssen.

Auch die aktuelle Toggle-Selection darf später ersetzt oder erweitert werden, wenn Tests mit verschiedenen Modeler-Konzepten eine bessere Bedienlogik nahelegen.

## Nächster Test

Den kleinen Modeling-Milestone praktisch prüfen:

1. einzelne Vertices bewegen
2. mehrere Vertices gemeinsam bewegen
3. einzelne Edges bewegen
4. mehrere Edges gemeinsam bewegen, inklusive gemeinsamer Vertices
5. einzelne Faces bewegen
6. mehrere Faces gemeinsam bewegen
7. Undo/Redo nach den Moves prüfen

Erst danach entscheiden, welcher nächste Baustein sinnvoll ist.
