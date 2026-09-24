# AD-SYM-02 — Symmetric Operation / History Contract

**Status:** PROPOSED — Architekturreview ausstehend
**Datum:** 2026-09-24
**Modus (M5):** Production-Planung. Keine Implementierung.
**Gehört zu:** WP-SYM-01 (Symmetry V1 Kern)
**Grundlage (unverändert, nur verlinkt):**
- `docs/research/symmetry/SYMMETRY_DESIGN_BRIEF.md` — INV-6, INV-7, INV-8, INV-9
- `docs/research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md` — AR-9, AR-10, §10 Punkt 4
- `docs/research/symmetry/SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md` — §2 (zwei Ausführungsmodelle), §5, §6
- AD-003 (Operation-Lifecycle), `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md`

**Frage:** Welche kleinste Erweiterung des bestehenden Operation-/History-Vertrags
ist nötig, damit eine künftige symmetrische Operation eine Artist-Absicht ist, beide
Seiten als zusammengehörige Wirkung behandelt, genau einen Undo-Schritt erzeugt und
bei Cancel nichts committet?

---

## 1. Bestehender Fakt

Alles nachgelesen in `src/core/operation.py`, `src/core/history.py`,
`src/core/operations/transform.py`, `src/core/operations/topology.py`,
`src/mirai/interaction/tool.py`.

**[FAKT·Code] Drei der vier geforderten Eigenschaften sind bereits erzwungen.**
`Operation.commit()` ist die einzige Stelle, die `history.push()` aufruft;
`update()` und `cancel()` berühren die History nie. Der Vertrag ist in der
Basisklasse zentralisiert, nicht in den konkreten Operationen. `Tool` spiegelt
denselben Lifecycle eine Ebene höher und verbietet `deactivate()` während einer
laufenden Interaktion.

> Daraus folgt: **„eine Absicht → genau ein Undo-Schritt" und „Cancel → kein
> Commit" brauchen keine Erweiterung**, solange die symmetrische Wirkung innerhalb
> *einer* Operation-Instanz entsteht. Der bestehende Vertrag leistet das bereits.

**[FAKT·Code] `OperationContext`** trägt `target: Any` (bewusst nicht `mesh: Mesh`),
`selection`, `history` und ein freies `params: dict`. `params` ist der dokumentierte,
bereits benutzte generische Erweiterungspunkt — `pivot` reist heute genau so
(`transform.py`: `context.params.get("pivot")`).

**[FAKT·Code] `VertexTransformOperation._on_update()`** ist **eine einzige
Per-Vertex-Schleife**, die von Move, Rotate und Scale gemeinsam benutzt wird.
Sie hält bereits ein per-Vertex-Dict (`self._weights`) als Platzhalter für ein
späteres Influence-System. Konkrete Transformationen implementieren nur
`_transform_position()`.

> Daraus folgt: Für die gesamte Transform-Familie existiert **genau eine Stelle**,
> an der Symmetrie eingehängt werden kann — was INV-9/AR-10 („keine Spiegel-Logik
> pro Tool") strukturell begünstigt statt nur appelliert.

**[FAKT·Code] Topologie-Mutationen laufen ohne Operation-Lifecycle** (atomare
Aufrufe), ihr Undo ist `MeshStateCommand` mit Vorher-/Nachher-Snapshot des ganzen
Mesh.

> Daraus folgt: Eine symmetrische Topologie-Mutation, die beide Seiten **innerhalb
> eines** Before/After-Paars erledigt, ist bereits exakt ein Undo-Schritt. Auch hier
> keine Erweiterung nötig.

**[FAKT·Code] `description`** ist ein Klassenattribut auf den Operation-Unterklassen
(`"Move Vertices"`, `"Rotate Vertices"`, …). Es gibt also einen Präzedenzfall dafür,
einer Operation Metadaten mitzugeben, **ohne** den Lifecycle anzufassen.

**[FAKT·Code] Extrude existiert in `src/` nicht.** Der V1-Kernfall „Extrude
symmetrisch, keine Innenwand an der Seam" hat heute keinen Produktionscode, an dem
er hängen könnte.

**[FAKT — Research, R2 §5]** Kein untersuchtes DCC vergibt Partnerschaft zum
Entstehungszeitpunkt eines Elements. Partnerschaft wird immer nachträglich
erschlossen. Mirai formuliert mit INV-6 bewusst strenger als der Stand der Technik:
die Gegenseite entsteht aus der *Absicht*, nicht aus einer Suche.

---

## 2. Notwendige Erweiterung

Aus §1 bleibt sehr wenig übrig. Drei Punkte, von denen **nur einer neu ist**.

### 2.1 Keine Erweiterung — nur eine ausgesprochene Regel

> **Eine symmetrische Operation ist eine Operation-Instanz, nicht zwei.**
> Die Gegenseite wird niemals als zweite, eigenständige Operation oder als zweiter
> History-Eintrag ausgeführt.

Das ist AR-9 und INV-6/INV-7, und es ist der Grund, warum der bestehende Vertrag
ausreicht: Er erzwingt bereits einen Eintrag pro Operation. Die Regel stellt sicher,
dass niemand auf die Idee kommt, sie zu umgehen.

### 2.2 Keine Erweiterung — bestehender Kanal wird benutzt

> **Der Symmetrie-Kontext einer Interaktion reist über das vorhandene
> `OperationContext.params`**, wie `pivot` heute.

`OperationContext` wird dafür **nicht** geändert. Kein neues Feld, keine neue
Dataclass, keine `MirrorResult`-Struktur.

### 2.3 Die einzige echte Erweiterung — Unterstützungsgrad

INV-8 und Experiment E5 verlangen, dass sichtbar ist, ob ein Tool symmetrisch wirken
kann, **bevor** es läuft. Der heutige Operation-Vertrag kennt dafür nichts: Eine
Operation kann ihren Unterstützungsgrad nicht aussagen, ein Aufrufer kann ihn nicht
abfragen.

> **Eine Operation muss vor `begin()` aussagen können, ob und in welcher Form sie
> symmetrisch wirken kann.**

Das ist genau die Fehlerklasse, die R2 §6 als den häufigsten realen Fall beschreibt —
ein Werkzeug, das einfach still einseitig läuft (Blender, Maya-Alttools, Modo).
Einzig C4D macht Nicht-Unterstützung vorab sichtbar. Diese Erweiterung ist damit
bewusst **strenger als die untersuchten Systeme**, nicht deren Nachahmung.

Die Form folgt dem bestehenden `description`-Präzedenzfall: eine Aussage auf
Klassenebene, die den Lifecycle nicht berührt.

### 2.4 Semantik der Gegenseite

> **Die Gegenseite ist dieselbe Absicht, gespiegelt angewendet — nicht ein zweites
> Ergebnis, das nachträglich zugeordnet wird.**

Für die Transform-Familie heißt das konkret: die Absicht wird für ein Element der
Gegenseite an der Plane konjugiert angewendet, statt das Element schlicht in die
Auswahl aufzunehmen. Das ist der Punkt, an dem R2 §2a (Maya/C4D: Symmetrie erweitert
die *Auswahl*) für Transforms **nicht** ausreicht: Eine erweiterte Auswahl bekäme
denselben Delta und würde die Gegenseite parallel statt gespiegelt bewegen.

Für auswahlbasierte Topologie-Operationen ist die gespiegelte Auswahl dagegen der
naheliegende Weg (R2 §2a). Dass beide Fälle dieselbe Semantik („eine Absicht, zwei
Seiten") erfüllen, aber unterschiedliche Mechanik brauchen, ist hier ausdrücklich
festgehalten — und **nicht** vorschnell zu einer gemeinsamen Mechanik vereinheitlicht.

**[Beobachtung, keine Entscheidung]** `VertexTransformOperation._on_update()` ist
die einzige Stelle, an der die Transform-Familie das einlösen müsste. Wo genau der
Haken sitzt, entscheidet die Implementierung in WP-SYM-01, nicht dieses Dokument.

---

## 3. Entscheidung

1. Eine symmetrische Operation ist **eine** Operation-Instanz und erzeugt **einen**
   History-Eintrag. Die bestehende Lifecycle-Garantie aus AD-003 wird
   wiederverwendet und nicht ersetzt.
2. `OperationContext` und `HistoryStack` werden **nicht** geändert. Der
   Symmetrie-Kontext reist über das vorhandene `params`.
3. Es wird **keine** Mirror-Result-Datenstruktur eingeführt.
4. Der Operation-Vertrag wird um **genau eine** Aussage erweitert: den vor `begin()`
   abfragbaren Unterstützungsgrad für Symmetrie.
5. Die Gegenseite entsteht aus der gespiegelten Absicht (INV-6), nicht aus einer
   nachträglichen Zuordnung. Transform-Familie und auswahlbasierte
   Topologie-Operationen erfüllen das mit unterschiedlicher Mechanik und werden
   nicht vereinheitlicht.

---

## 4. Bewusst NICHT entschieden

- Form des Unterstützungsgrads: Boolean, Enum oder abgestufte Aussage
  (z. B. „ja / nur abseits der Seam / nein"). Erst E5 zeigt, was der Artist braucht.
- Ob Nicht-Unterstützung **blockiert** oder nur **markiert** — das ist eine
  Product-Truth-Frage und gehört zu E5 (M4), nicht in eine Architekturentscheidung.
- Wo Correspondence berechnet wird und ob sie innerhalb einer Interaktion einmal
  oder pro `update()` abgeleitet wird.
- Ob und wie eine Operation die Seam **aktualisiert** (Wings-Muster, R2 §3.2), oder
  ob die Seam unverändert bleibt und der State erkennbar degradiert (Maya-Muster,
  R2 §6). Das ist die teuerste offene Frage von WP-SYM-01 und ausdrücklich hier
  nicht vorentschieden.
- Ob der Seam-Constraint (Seam-Elemente bleiben auf der Plane) im Operation-Layer
  oder im Transform-Space-Layer (AD-012/AD-014) sitzt. Der Design Brief nennt diesen
  Bezug als offene Frage; er ist nicht untersucht.
- Ob Extrude als `Operation` mit Lifecycle oder als atomare Mutation mit
  `MeshStateCommand` in `src/` landet. Betrifft, welcher der beiden in §1 gezeigten
  Wege für den wichtigsten V1-Topologiefall gilt.
- Jede Tastenbelegung, Anzeigeform und UI-Darstellung.

---

## 5. Kopplung mit AD-SYM-01 — geprüft

**Ergebnis: Die beiden Entscheidungen sind nicht unabhängig. Der bestehende Code
erzwingt eine Kopplung in genau einer Richtung.**

AD-SYM-01 §1.1 zeigt gemessen: Sobald eine Operation die Seam mitführt, muss die
Definition am Undo teilnehmen. Daraus folgt:

| Ausgang AD-SYM-01 | Folge für AD-SYM-02 |
|---|---|
| Definition **im Mesh**, Teil von `export_state()`/`load_state()` | `MeshStateCommand` trägt die Definition ohne Zutun mit. AD-SYM-02 braucht **keine** History-Erweiterung — es bleibt bei der einen Aussage aus §2.3. |
| Definition **an der Scene** | AD-SYM-02 müsste zusätzlich ein zusammengesetztes Command einführen, das Mesh-Snapshot und Definition gemeinsam zurücknimmt — also neue History-Maschinerie, die es heute nicht gibt. |

**Umgekehrt besteht keine Kopplung:** AD-SYM-02 §2.1–§2.4 gilt unverändert, egal wo
die Definition liegt. Nur der *History-Umfang* hängt an AD-SYM-01.

> **Reihenfolge: AD-SYM-01 zuerst, dann AD-SYM-02.**

Eine zweite, schwächere Kopplung über die Correspondence besteht **nicht**:
Correspondence ist abgeleitet (INV-3) und hat keinen gespeicherten Zustand, der
mit der History synchronisiert werden müsste.
