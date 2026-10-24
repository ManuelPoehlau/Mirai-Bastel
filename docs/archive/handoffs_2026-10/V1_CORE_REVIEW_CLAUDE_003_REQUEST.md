# Claude Architecture Review 003 — Request

> This document preserves the exact request sent to Claude for the next architecture review round.
>
> **Status:** Awaiting response

## Architecture Decision Review — nächste Runde

Danke für die zweite Betrachtung. Die Klassifikation ist sehr hilfreich. Wir wollen jetzt aus deinen Erkenntnissen **noch keine Implementierung ableiten**, sondern die drei wahrscheinlich fundamentalsten Architekturentscheidungen technisch sauber verstehen.

Bitte analysiere deshalb die folgenden drei Punkte noch einmal detaillierter.

### AD-001 — Stable Element IDs

Du empfiehlst:

> `ID = (slot_index, generation)` / Slotmap-Pattern.

Bitte erkläre konkret:

1. Wie würde das für `VertexId`, `EdgeId` und `FaceId` aussehen?
2. Wie verhält sich eine ID bei:
   - Löschen
   - Undo
   - Redo
   - Topology-Operationen?
3. Warum ist ein einfacher monotoner ID-Counter für unser Projekt problematisch?
4. Welche minimale Python-Implementierung würdest du für V1 verwenden?
5. Gibt es einen einfacheren Ansatz, der dieselben Eigenschaften liefert?
6. Welche Auswirkungen hätte die Entscheidung auf Serialisierung und spätere Scripting-/AI-APIs?

Wichtig: **kein ECS und kein übergeneralisiertes Framework.** Wir suchen die kleinste robuste Lösung.

---

### AD-002 — Topology / Half-Edge / Loop

Hier möchten wir besonders gründlich sein.

Du sagst:

> Face-Boundary sollte konzeptuell eine geordnete Liste von Edge-IDs sein; volle Half-/Winged-Edge-Mechanik muss V1 noch nicht implementieren.

Bitte erkläre das anhand eines einfachen Quad-Meshes.

Wir möchten verstehen:

```text
Vertex
Edge
Face
Loop / Half-Edge
```

Welche Rolle spielt jedes dieser Konzepte?

Und insbesondere:

1. Reicht für V1 tatsächlich

```text
Vertex
Edge
Face
    └── ordered boundary
```

oder brauchen wir bereits ein echtes `HalfEdge`-Objekt?

2. Welche Modeling-Operationen würden später ohne Half-Edges schwierig oder unsauber?

3. Welche Operationen brauchen wir für unser geplantes V1 tatsächlich?

4. Wie würdest du die kleinste Topology-API gestalten, die später eine Half-Edge-artige interne Struktur zulässt, **ohne dass wir sie jetzt vollständig bauen müssen**?

5. Was genau meinst du mit:

> „Adjacency-Queries als API stabil halten“?

Bitte möglichst konkret.

Unser Ziel ist nicht historische Authentizität, sondern:

> **Mirai-artige direkte Modellierung + moderne, robuste Architektur.**

---

### AD-003 — Interactive Operation Lifecycle

Das scheint uns besonders wichtig für das gewünschte Mirai-Feeling.

Bitte beschreibe den vorgeschlagenen Lifecycle:

```text
begin()
update()
commit()
cancel()
```

anhand eines echten Beispiels:

```text
Vertex auswählen
→ Maus drücken
→ Vertex ziehen
→ mehrere Updates während des Drag
→ Maus loslassen
```

Wie sieht dabei aus:

- Selection
- Soft Selection / Influence
- Mesh Mutation
- History
- Events
- Viewport Update

?

Und wie unterscheidet sich das von einer klassischen `apply()`-Operation?

Bitte zeige einen **minimalen konkreten Ablauf**, aber noch keinen vollständigen Code.

Besonders wichtig:

- Wann entsteht der History-Eintrag?
- Was passiert bei `cancel()`?
- Wird während `update()` direkt am Mesh gearbeitet?
- Wie verhindert man 60 History-Einträge?
- Wie verhindert man unnötige Event-Fluten?
- Wie könnte später ein interaktiver Extrude oder Tweak darauf aufbauen?

---

## Übergeordnetes Ziel

Wir möchten aus diesen drei Entscheidungen **keinen großen Framework-Unterbau** bauen.

Bitte bewerte deshalb jede Entscheidung zusätzlich nach:

```text
Muss jetzt festgelegt werden?
Muss jetzt implementiert werden?
Kann zunächst minimal implementiert werden?
Was sollte ausdrücklich NICHT gebaut werden?
```

Und ganz wichtig:

> **Wenn du bei einem Punkt der Meinung bist, dass wir deine vorherige Empfehlung zu stark interpretieren, korrigiere sie ausdrücklich.**

Wir wollen keine künstliche Komplexität erzeugen, nur weil eine Architektur „professionell“ aussieht.

Das Ziel für V1 bleibt:

**klein, intuitiv, schnell, robust, Mirai-/Nendo-inspiriertes Modeling – aber mit einer modernen Grundlage, die später wachsen kann.**

Noch **keine Änderungen am Repository und keinen Produktionscode**. Wir möchten zunächst nur die technischen Grundlagen dieser drei Architecture Decisions verstehen.
