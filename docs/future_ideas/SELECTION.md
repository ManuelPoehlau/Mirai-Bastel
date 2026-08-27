# Future Ideas – Selection

Ideen und Beobachtungen rund um Selection, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten.

## Post-Operation Selection / Mode Behavior

Bei Topologieoperationen kann sich durch die Aktion die Art der sinnvollen
Auswahl ändern. Beispiele:

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

**Noch keine Entscheidung.** Die Experimente sollen zunächst zeigen, welches
Verhalten sich beim tatsächlichen Modellieren am natürlichsten und
produktivsten anfühlt.

Dieses Thema betrifft zugleich **Workflow / Modeling UX** und wird deshalb
hier unter Selection festgehalten.
