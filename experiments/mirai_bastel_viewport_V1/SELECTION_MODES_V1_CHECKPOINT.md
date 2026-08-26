# Selection Modes V1 — Checkpoint

**Status:** funktional verifiziert + experimentelle Multi-Selection  
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

Die neue Toggle-Multi-Selection ist als nächster **Praxisversuch** eingebaut und muss noch manuell gegen Vertex, Edge und Face geprüft werden.

## Architekturhinweis

Die Selection-Logik bleibt bewusst einfach. Dieser Checkpoint soll nicht bereits die spätere vollständige Modeler-Selection definieren, sondern eine belastbare Grundlage für weitere Tests liefern.

Insbesondere soll die spätere Entscheidung zwischen **Visible Only** und **Through/X-Ray** auf dem bestehenden Hit-Test aufbauen können, ohne die aktuellen Selection Modes neu entwerfen zu müssen.

Auch die aktuelle Toggle-Selection darf später ersetzt oder erweitert werden, wenn Tests mit verschiedenen Modeler-Konzepten eine bessere Bedienlogik nahelegen.

## Nächster Test

Multi-Selection praktisch in allen drei Modi prüfen:

1. mehrere unterschiedliche Elemente anklicken
2. ein bereits ausgewähltes Element erneut anklicken
3. ins Leere klicken
4. zwischen Vertex / Edge / Face wechseln

Erst danach entscheiden, ob diese experimentelle Interaktion als Grundlage für die nächste Selection-Stufe taugt.
