# Selection Modes V1 — Checkpoint

**Status:** abgeschlossen / funktional verifiziert  
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
- Linksklick wählt genau **ein** Element.
- Ein neuer Pick ersetzt die bisherige Selection.
- Klick ins Leere löscht die Selection.
- Selection und Hover sind getrennte Zustände.
- Nach dem Pick erhält die Selection **sofort** die Selection-Darstellung, auch wenn der Cursor weiterhin über dem Element liegt.
- Faces werden für den Viewport gefüllt gerendert.
- Face-Hover und Face-Selection verwenden einen kleinen Polygon-Depth-Bias, damit das Highlight über der Basisfläche sichtbar bleibt.
- Face-Picking erfolgt über Ray/Triangle-Hit-Testing; bei mehreren Treffern wird aktuell der nächstgelegene Treffer verwendet.

## Bewusst noch nicht enthalten

- Multi-Selection / Additive Selection
- Subtractive Selection
- Universal / All-in-One Selection Mode
- Object Mode
- Visible-Only vs. Through/X-Ray Selection
- getrennte Farben pro Vertex/Edge/Face-Mode als ausgearbeitetes UI-System
- Box/Lasso/Brush Selection
- Persistente Selection-Visualisierung über den V1-Testumfang hinaus

## Verifikation

Für alle drei Sub-Object-Modi wurde der grundlegende Pfad praktisch getestet:

```text
Hover → Hit-Test → Highlight
Pick  → Selection → Selection-Highlight
```

Face Mode wurde zusätzlich mit dem Raycast-Debug verifiziert. Dabei wurden gültige `FaceId`-Treffer und die zugehörige Hover-Geometrie bestätigt. Der temporäre Debug-Schalter und die Debug-Ausgaben wurden anschließend entfernt.

## Architekturhinweis

Die Selection-Logik bleibt bewusst einfach. Dieser Checkpoint soll nicht bereits die spätere vollständige Modeler-Selection definieren, sondern eine belastbare Grundlage für die nächsten Tests liefern.

Insbesondere soll die spätere Entscheidung zwischen **Visible Only** und **Through/X-Ray** auf dem bestehenden Hit-Test aufbauen können, ohne die aktuellen Selection Modes neu entwerfen zu müssen.

## Nächster sinnvoller Schritt

Vor der Implementierung von Multi-Selection die gewünschte Bedienlogik festlegen (z. B. Modifier-basierte Add/Remove-Selection). Erst danach soll sie als eigener, isolierter Test ergänzt werden.
