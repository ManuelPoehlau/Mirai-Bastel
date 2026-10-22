# Future Ideas – Transform

Ideen und Beobachtungen rund um Transform, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten. Pivot-Ausbau ist für den Character-Workflow sinnvoll, steht aber hinter kontrollierter Formgebung, Maskierung und Topologie-Navigation.

## Pivot-System: später gezielt erweitern

Mirai hat bereits einen Auswahlmittelpunkt als Komponenten-Pivot und einen Objektursprung für Objekttransformationen. Der Pivot bleibt während einer laufenden Geste fest. Ein frei platzierbares Pivot-System ist eine spätere Erweiterung, keine fehlende Voraussetzung für die nächsten Character-Shaping-Schritte.

Für die spätere Untersuchung sind diese Möglichkeiten relevant:

- **Pivot Mode:** Selection/Median, Bounding-Box-Zentrum, aktives Element, Objektursprung und individuelle Origins.
- **Custom Pivot:** Pivot an einer frei gewählten Position platzieren und optional an einer gewünschten Orientierung ausrichten.
- **Pivot sichtbar machen:** klare Anzeige von Position und Achsen, damit der Artist weiß, worum die Auswahl rotiert oder skaliert.
- **Per-Object Pivot:** bei getrennten Character-Objekten wie Augen, Kiefer, Zähnen oder Zubehör soll ein eigener Pivot möglich sein, ohne den Mesh-Inhalt versehentlich zu verschieben.

Ein einfacher erster Praxistest sollte beantworten, welche zwei oder drei Pivot-Modi im täglichen Modellieren tatsächlich gebraucht werden. Nicht alle Blender-Modi automatisch übernehmen.

## Soft Selection: Radius live während des Ziehens ändern

**Status: umgesetzt (2026-10-22, `PROVISIONAL`), Praxistest offen** (ATELIER B12). Während einer laufenden Soft-Geste
(Move/Rotate/Scale, auch per Gizmo oder Tweak) ändert das Mausrad – und weiterhin Shift+Mausrad – den Radius dieser Geste
um eine Stufe; das Rad zoomt dann nicht. Die Geste wird von ihrer Startgeometrie aus mit dem neuen Einfluss und der bisherigen
Bewegung neu ausgewertet (kein Aufaddieren, kein Drift); eine Geste bleibt ein History-Eintrag. Ctrl+Mausrad und alle anderen
Soft-Einstellungen gelten weiter ab der nächsten Geste. Semantik und Tests: AD-020, „Live radius during a running gesture“.
Core unverändert.

Früherer Stand (S2c-Verdikt): Radius pro Geste fest, Idee zurückgestellt. Kosten wurden nicht gemessen: eine
Influence-Berechnung pro Rad-Raste, wie beim Start der Geste; gemessen wird nur, wenn es sich im Praxistest träge anfühlt
(`experiments/drag_cost/README.md`).

## Multi-Element Tangent-Basis Derivation (deferred per AD-012 Amendment, WP-03C)

WP-03C implements tangent basis derivation for **single-face selections only**: `space="normal", axis="x"/"y"` works for exactly one selected face and raises `ValueError` for multi-face or non-face selections.

Multi-element selections fall back to `selection_normal()`'s existing averaging:
- `space="normal", axis="z"` / `None`: works (returns averaged normal)
- `space="normal", axis="x"` / `"y"`: raises (no stable tangent for multiple faces)

**Why deferred:**
- Blender's own multi-element Normal orientation has a long-standing UX complaint (reference: https://developer.blender.org/T62124).
- There is no settled convention for a multi-face tangent basis.
- A stable rule should come from practical Playground research, not hypothetical design.

**Next step:** gather use cases during experimentation with single-face basis. Revisit after concrete patterns emerge.

## Tangent-Plane Movement (deferred per AD-012)

Move perpendicular to the selection normal (within the tangent plane):

```python
space="tangent"
```

The normal resolution and single-face tangent-basis infrastructure exist, but the meaning of constrained tangent movement remains ambiguous: one tangent axis, both axes, or free movement in the plane? No clear use case is settled yet. Revisit after practical use cases emerge.
