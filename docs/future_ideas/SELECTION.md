# Future Ideas – Selection

Ideen und Beobachtungen rund um Selection, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten. Die Prioritäten in diesem Dokument sind ein Vorschlag für die Character-Modelling-Discovery, keine beschlossene Roadmap.

> **AD-017 Entscheidung (2026-09-22):** Die Residue-Regeln für Split, Edge Connect,
> Vertex Connect und Knife sind ENTSCHIEDEN — siehe
> `docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md` Tabelle "Selection residue (mode-specific)".
> Die offenen Fragen in diesem Dokument bleiben als Forschungsgrundlage erhalten.

## Priorität 1 – Auswahl ausbauen und durch Topologie navigieren

### Grow / Shrink Selection

> Geplant (2026-10-23): [WP_TOOLBOX_GAPS_PLAN.md](../WP_TOOLBOX_GAPS_PLAN.md), Slice A1.

Die Auswahl mode-aware schrittweise vergrößern oder verkleinern:

- Vertex Mode: benachbarte Vertices entlang der Mesh-Adjazenz hinzufügen bzw. zurücknehmen.
- Edge Mode: über topologisch angrenzende Kanten erweitern bzw. verkleinern.
- Face Mode: angrenzende Faces ergänzen bzw. entfernen.

Das Wachstum soll der Topologie folgen, nicht der Bildschirmnähe. Mehrere Iterationen sollten möglich sein, ohne die Ausgangsauswahl jedes Mal neu aufzubauen. Zu definieren sind Randverhalten, getrennte Auswahlinseln, Symmetrie und der Umgang mit ausgeblendeter bzw. maskierter Geometrie. Selection Growth darf nicht mit Soft Selection verwechselt werden: Das eine ändert, welche Elemente ausgewählt sind; das andere beeinflusst die Reichweite einer Transformation.

### Loop Selection: Extend in beide Richtungen

> Geplant (2026-10-23): [WP_TOOLBOX_GAPS_PLAN.md](../WP_TOOLBOX_GAPS_PLAN.md), Slice A1.

Die bestehende Loop-Auswahl über `Shift+L` erkennt bereits einen kompletten unterstützten Edge Loop. Eine zusätzliche Extend-Geste soll deshalb nicht einfach dieselbe Traversierung duplizieren.

Zu untersuchen ist eine schrittweise Erweiterung einer partiellen Loop-Auswahl von ihren offenen Enden aus: beide Richtungen gleichzeitig, soweit die Topologie eindeutig fortsetzbar ist. Das wäre bei offenen Loops, Grenzen und absichtlich partiellen Auswahlen nützlich. Verhalten bei Poles, Non-Quads, Mesh-Grenzen oder mehreren möglichen Fortsetzungen muss explizit und vorhersagbar sein.

### Next / Previous Parallel Loop – innerhalb eines Rings bzw. Quad-Strips navigieren

> Geplant (2026-10-23): [WP_TOOLBOX_GAPS_PLAN.md](../WP_TOOLBOX_GAPS_PLAN.md), Slice A1.

Von einem Loop zum nächsten parallelen Loop wechseln, ohne den nächsten Loop im Viewport neu anklicken zu müssen. Der Ausgangspunkt ist der aktuelle Loop; die Navigation folgt dem angrenzenden Quad-Strip bzw. der Ring-Richtung. Mehrere Schritte vor/zurück könnten ein schnelles Durchwandern von Gesichtsloops ermöglichen.

Das ist **nicht** dasselbe wie die bestehende Edge-Ring-Auswahl (`Shift+R`), die gegenüberliegende Kanten sammelt. Der neue Befehl soll zwischen benachbarten parallelen Loops navigieren bzw. sie gezielt auswählen. Interaktion mit einer vorhandenen Mehrfachauswahl ist noch zu untersuchen.

## Weitere nützliche Selection-Fähigkeiten

- **Select Linked / Connected:** die verbundene Mesh-Komponente unter dem Cursor auswählen.
- **Boundary / Non-Manifold / Isolated:** offene Ränder, nicht-manifold Elemente und isolierte Elemente gezielt auffinden – besonders zur Reparatur vor Deformation.
- **Face Loop / Face Ring:** zur bestehenden Edge-Loop-/Ring-Unterstützung passend untersuchen.
- **Select Similar:** nach nachvollziehbaren Kriterien wie Topologie/Attributen auswählen, sofern es einen echten Workflow-Bedarf gibt.

Benannte Gesichtsregionen bzw. Polygroups sind eine verwandte, aber eigene Fähigkeit: Sie speichern wiederverwendbare Regionen und werden in [MODELING.md](MODELING.md) behandelt.

## Post-Operation Selection / Mode Behavior

Bei Topologieoperationen kann sich durch die Aktion die Art der sinnvollen Auswahl ändern. Das Verhalten nach einer Operation ist deshalb ein wichtiger Bestandteil des Modeling-Workflows und nicht nur ein UI-Detail.

### Connect Vertices

Ausgangslage:

```text
Vertex Mode
  ↓
2 Vertices auswählen
  ↓
Connect
```

Danach existiert eine neue Edge. Zwei sinnvolle Verhaltensweisen:

**A – Ergebnis übernehmen**

```text
→ neue Edge wird ausgewählt
→ Selection Mode wechselt zu Edge
```

Vorteil: Das Ergebnis kann unmittelbar weiterbearbeitet werden, z. B. verschieben, splitten oder weitere Edge-Operationen.

**B – Ausgangsmodus beibehalten**

```text
→ neue Edge entsteht
→ Vertex Mode bleibt aktiv
```

Vorteil: Besonders bei repetitiven Aktionen können direkt weitere Vertices verbunden werden, ohne ständig den Selection Mode zurückzuschalten.

### Collapse Edge

> Geplant (2026-10-23): [WP_TOOLBOX_GAPS_PLAN.md](../WP_TOOLBOX_GAPS_PLAN.md), Slice B1.

Analog entsteht beim Collapse aus einer Edge-Auswahl typischerweise ein verbleibender Vertex. Auch hier gibt es zwei sinnvolle Workflows:

- **Ergebnis aktiv:** Vertex auswählen und in Vertex Mode wechseln → direkt verschieben oder weiter bearbeiten.
- **Ausgangsmodus beibehalten:** Edge Mode bleibt aktiv → direkt weitere Edges collapsen.

### Split Edge – wichtiger Sonderfall

Split zeigt, dass es keine einfache globale Regel „nach einer Operation immer das neu entstandene Element auswählen“ gibt. Aus einer Edge entstehen ein Vertex und zwei Edges; das aktuelle Verhalten, beide neuen Edges auszuwählen, ist für einen Edge-orientierten Workflow sinnvoll. Ein Vertex-orientierter Workflow könnte dagegen den neuen Vertex aktivieren.

Das **Operationsergebnis kann mehrere Elementtypen enthalten**. Die sinnvollste Folgeauswahl ist deshalb nicht rein technisch zu beantworten.

### Allgemeine Fragestellung

Für jede Topologieoperation ist zu untersuchen:

- grundsätzlich das Operationsergebnis auswählen,
- grundsätzlich im aktuellen Mode bleiben,
- das Verhalten je Operation definieren,
- vorherigen Mode und Ergebnis gleichzeitig erhalten,
- oder später eine konfigurierbare Workflow-Präferenz anbieten.

Möglicherweise ist die beste Lösung kontextabhängig: Bei repetitiven Aktionen kann das Beibehalten des Modes produktiver sein, während bei einem klaren neuen Ergebnis ein automatischer Wechsel hilft.

### Forschungsgrundsatz

Bei Experimenten soll nicht nur geprüft werden, **ob eine Operation technisch funktioniert**, sondern:

> **Was möchte der Benutzer unmittelbar danach wahrscheinlich tun?**

**Noch keine Entscheidung.** AD-017s entschiedene Residue-Regeln bleiben davon unberührt.

## X-ray / select-through as a user toggle

> Geplant (2026-10-23): [WP_TOOLBOX_GAPS_PLAN.md](../WP_TOOLBOX_GAPS_PLAN.md), Slice A2.

WP-06 B8 gab Production einen Occlusion-Test: verdeckte Vertices/Edges sind bei angezeigten Flächen nicht pickbar. Außerhalb von B8 lag die benutzerseitige Wahlmöglichkeit. Ein künftiger X-ray-/Select-through-Schalter könnte dieses Verhalten bei sichtbaren Flächen bewusst übersteuern, ohne in Wireframe wechseln zu müssen. Nicht entschieden, nicht gebaut.
