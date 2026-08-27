# Future Ideas – Selection

Ideen und Beobachtungen rund um Selection, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten.

## Post-Operation Selection / Mode Behavior

Bei Topologieoperationen kann sich durch die Aktion die Art der sinnvollen Auswahl ändern. Das Verhalten nach einer Operation ist deshalb ein wichtiger Bestandteil des späteren Modeling-Workflows und nicht nur ein UI-Detail.

### Warum das wichtig ist

Ein „intelligenter“ Modeler unterscheidet sich nicht nur dadurch, **welche** Topologieoperationen er anbietet, sondern auch dadurch, wie gut eine Operation in die nächste Aktion überleitet. Systeme wie Mirai, Wings 3D oder Silo zeigen beispielhaft, wie stark solche kleinen Workflow-Entscheidungen das eigentliche Modelliergefühl prägen können.

Diese Beobachtungen sollen deshalb ausdrücklich gesammelt werden, bevor wir ein endgültiges Selection-/Workflow-System entwerfen.

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

Vorteil: Das Ergebnis kann unmittelbar weiterbearbeitet werden, z. B.
verschieben, splitten oder weitere Edge-Operationen.

**B – Ausgangsmodus beibehalten**

```text
→ neue Edge entsteht
→ Vertex Mode bleibt aktiv
```

Vorteil: Besonders bei repetitiven Aktionen können direkt weitere Vertices
verbunden werden, ohne ständig den Selection Mode zurückzuschalten.

### Collapse Edge

Analog entsteht beim Collapse aus einer Edge-Auswahl typischerweise ein
verbleibender Vertex:

```text
Edge Mode
  ↓
1 Edge auswählen
  ↓
Collapse
  ↓
Vertex entsteht/bleibt übrig
```

Auch hier gibt es zwei sinnvolle Workflows:

- **Ergebnis aktiv:** Vertex auswählen und in Vertex Mode wechseln → direkt
  verschieben oder weiter bearbeiten.
- **Ausgangsmodus beibehalten:** Edge Mode bleibt aktiv → direkt weitere
  Edges collapsen.

### Split Edge – wichtiger Sonderfall

Split zeigt bereits im Experiment, dass es keine einfache globale Regel
„nach einer Operation immer das neu entstandene Element auswählen“ gibt:

```text
Edge Mode
  ↓
1 Edge auswählen
  ↓
Split
  ↓
1 Vertex + 2 Edges entstehen
  ↓
aktuell: beide neuen Edges ausgewählt
```

Das aktuelle Verhalten ist für einen Edge-orientierten Workflow sinnvoll:
Die beiden neuen Edges können direkt weiter bearbeitet, erneut gesplittet
oder für andere Edge-Operationen verwendet werden.

Gleichzeitig wäre auch ein Vertex-orientierter Workflow denkbar, bei dem der
neu eingefügte Vertex aktiv wird, etwa um ihn unmittelbar zu verschieben.

Damit zeigt Split besonders deutlich, dass das **Operationsergebnis mehrere
Elementtypen enthalten kann** und die Frage nach dem „sinnvollsten nächsten
Arbeitsschritt“ nicht rein technisch beantwortet werden kann.

### Allgemeine Fragestellung

Das Verhalten sollte **nicht vorschnell global festgelegt** werden.
Jede Topologieoperation kann ein anderes sinnvolles Folgeelement erzeugen:

```text
Operation
    ↓
welche Elemente entstehen / bleiben übrig?
    ↓
welche davon sind für den nächsten Arbeitsschritt wahrscheinlich relevant?
    ↓
Auswahl und/oder Selection Mode entsprechend vorbereiten
```

Zu untersuchen ist insbesondere, ob ein zukünftiges System:

- grundsätzlich das Operationsergebnis auswählt,
- grundsätzlich im aktuellen Mode bleibt,
- das Verhalten je Operation definiert,
- den vorherigen Mode und das Ergebnis gleichzeitig erhält,
- oder dem Benutzer später eine konfigurierbare Workflow-Präferenz anbietet.

Möglicherweise ist die beste Lösung auch **kontextabhängig**: Bei einer
repetitiven Modeling-Aktion kann das Beibehalten des aktuellen Modes besser
sein, während bei einer Operation mit einem klaren neuen Ergebnis der
automatische Wechsel auf den Ergebnis-Typ produktiver sein kann.

### Forschungsgrundsatz

Bei den Experimenten soll deshalb nicht nur geprüft werden, **ob eine
Operation technisch funktioniert**, sondern auch:

> **„Was möchte der Benutzer unmittelbar danach wahrscheinlich tun?“**

Diese Frage soll für jede neue Topologieoperation erneut gestellt werden.
Die Antworten werden zunächst beobachtet und dokumentiert; eine endgültige
Workflow-Regel entsteht erst, wenn genügend praktische Erfahrung vorliegt.

**Noch keine Entscheidung.**
