# Symmetry Evolution — vom V1-Kern zur Character-Pipeline

**Status:** Discovery / Research. **Keine** Architecture Decision, **keine** Roadmap-Zusage.
**Datum:** 2026-09-24
**Ort (vorgeschlagen):** `docs/research/symmetry/SYMMETRY_EVOLUTION_RESEARCH.md`
**Modus (M5):** Discovery

**Baut auf (unverändert, nur verlinkt):**
- **R1** [`EDIT_MODE_SYMMETRY_RESEARCH.md`](EDIT_MODE_SYMMETRY_RESEARCH.md)
- **R2** [`SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md`](SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md)
- **DB** [`docs/design/SYMMETRY_DESIGN_BRIEF.md`](../../design/SYMMETRY_DESIGN_BRIEF.md) — Invarianten INV-1…13

**Mirai-Kontext (History Awareness, M1) [FAKT]:**
- `src/core` vergibt **stabile IDs** über einen monotonen Zähler, ohne Wiederverwendung (AD-001, `src/core/ids.py`).
- **AD-017 B5**: Provenance (ARCH-02) ist eine *Randbedingung*, kein Feature; der verlässliche Weg ist der **Operationskontext** (der Aufrufer weiß, welche Edge bei welchem `t` geteilt wurde).
- **FINDINGS-3C** (Rigging-Experiment): Die Eltern-Edge eines neuen Vertex ist aus Vorher/Nachher-Snapshots nur **geometrisch erschließbar**, nicht garantiert; Weight-Merge- und Morph-Transfer-Semantik sind **offen** und laut DEVELOPMENT_SYSTEM §9 M4-Fälle.
- README-Vision: *model → rig → test deformation → back to modeling → change topology.*
- Commits WP-STAB-07/-12: abgeleiteter Cache wurde nach einzelnen Topologie-Operationen vergessen → Absturz.

Markierungen: **[FAKT] [FAKT·Code] [ANWENDER] [INTERPRETATION] [SCHLUSS] [OFFEN]**. Quellen in §14 als `[E#]`.

---

## 1. Purpose

Dieses Dokument beantwortet zwei Fragen:

1. **Was ist der kleinste Symmetrie-Kern,** mit dem Mirai heute sinnvoll modellieren und lernen kann — der aber dieselben Wahrheiten bewahrt, die Morphing, Rigging, Skinning und Deformation später brauchen?
2. **Was darf V1 bewusst nicht lösen,** ohne dass wir uns dadurch festfahren?

Versionen sind hier **Reifegrade des Symmetrie-Modells**, nicht Feature-Pakete:

| Stufe | Reifegrad | Kernaussage |
|---|---|---|
| **V1** | Symmetrie ist *erklärt, sichtbar und ehrlich* | „Ich kann symmetrisch modellieren und sehe immer, ob es stimmt." |
| **V2** | Symmetrie ist *robust gegenüber Topologie und Form* | „Symmetrie überlebt, was ich beim Modellieren tue — auch wenn es nicht perfekt ist." |
| **V3+** | Symmetrie ist *eine Wahrheit, auf die andere Systeme bauen* | „Weights, Morphs, Knochen und Posen nutzen dieselbe Symmetrie-Aussage." |

---

## 2. Long-Term Ideal (A)

Wenn technische Kosten keine Rolle spielten [SCHLUSS, abgeleitet aus R1/R2 und der Mirai-Vision]:

- **Einmal erklärt, überall gültig.** Der Artist erklärt die Symmetrie eines Characters einmal. Modeling, Weight Painting, Morph-Erstellung, Knochen-Setup und Posing verstehen dieselbe Aussage.
- **Topologie bleibt lebendig.** Nach Rigging und Morph-Erstellung kann weiter modelliert werden. Weights und Morphs folgen der Topologie *auf beiden Seiten gleich*.
- **Symmetrie auch in der Pose.** Ein gebeugter Arm ist weiterhin „der linke Arm". Symmetrisches Arbeiten am posierten Character ist möglich (vgl. ZBrush Poseable, C4D T-Rex-Beispiel; R1 §3.6, R2 §3.4).
- **Asymmetrie als Ebene, nicht als Unfall.** Eine Narbe, ein gescheitelter Haaransatz, ein asymmetrischer Morph sind bewusst *auf* einer symmetrischen Basis möglich, ohne die Basis zu zerstören (vgl. „Symmetrie pro Layer" in CHARACTER_SYSTEMS_RESEARCH, O-Eintrag Zeile ~196).
- **Reparatur ohne Datenverlust.** Re-Symmetrize bewahrt bestehende Weights, Morphs und UVs.
- **Immer ehrlich.** Jeder Zustand ist sichtbar; nichts ist still halb symmetrisch (DB §1).

Dieses Ideal ist **Orientierung**, keine Anforderung an V1 (vgl. Projektprinzip „Implement little. Assume much.").

---

## 3. Symmetry V1 — Minimum Viable Symmetry (B)

### 3.1 Leitfrage

> Was muss V1 können, damit Manu damit *echte* Modellieraufgaben lösen kann — und dabei etwas lernt, das die Frage für V2 beantwortet?

[SCHLUSS] Die Antwort ist nicht „möglichst viele Tools". Sie lautet: **Der tägliche Modellierweg eines symmetrischen Objekts muss durchgehend funktionieren, und jeder Ort, an dem er es nicht tut, muss sichtbar sein.** Ein V1, das zehn Tools spiegelt, aber still einseitig werden kann, lehrt weniger als eines, das vier Tools spiegelt und ehrlich ist.

### 3.2 Was V1 wirklich können muss

| Fähigkeit | Warum unverzichtbar | Research-Basis |
|---|---|---|
| **Eine Symmetry Definition pro Mesh-Objekt**, eine Ebene | Ohne Definition keine Wahrheit; mehrere Ebenen bringen keinen Lernwert für V1 | DB INV-1 |
| **Deklarierte Seam**, die auf Element-*Identität* verweist, nicht auf Positionen. Eine positionsbasierte **Vorschlagshilfe** beim Erklären ist erlaubt, danach zählt die Deklaration. | Die fundamentale Wahrheit, die V3 braucht; billig zu haben, weil die Core-IDs stabil sind | R1 §4 M-E, R2 §7, AD-001 |
| **Abgeleitete Korrespondenz** mit den vier Zuständen *gepaart / Seam / ungepaart / mehrdeutig* | Partner nie als ewige Wahrheit; teilweise Symmetrie ist von Anfang an ein Zustand | DB INV-3, INV-10 |
| **Symmetrische Auswahl-Vorschau** (Gegenseite sichtbar markiert) | Die billigste Form symmetrischer Interaktion und Grundlage für alles Weitere | R2 §2 (C4D virtuelle Selektion) |
| **Move / Rotate / Scale / Tweak** symmetrisch; Seam-Elemente bleiben auf der Ebene | Ohne das kein Modellieren | DB §5 |
| **Extrude** symmetrisch, inklusive „keine Innenwand an der Seam" | Der häufigste Modellierschritt; historisch klassischer Seam-Stressfall | R1 §3.5 Wings, R2 §3.1 Blender |
| **Loop Insert** symmetrisch, inklusive Loop *über* die Seam (ein Loop, sein eigenes Gegenstück) | Alltag beim Character-Modelling; gleichzeitig der einfachste *cursorbasierte* Fall | R2 §4 |
| **Genau ein schwerer Pfad-Fall:** Connect *oder* Knife (Auswahl in §5, Experiment E4) | Die Research zeigt: Hier brechen DCCs. V1 muss daran lernen, nicht alles lösen. | R2 §4, §6 |
| **Delete** symmetrisch; Löschen von Seam-Elementen ändert erkennbar den State | Das Löschen einer Hälfte bzw. einzelner Bereiche ist Alltag | DB §5 |
| **Sichtbarer Symmetry State** (gültig / teilweise / mehrdeutig / verletzt / aus) und sichtbare **ungepaarte Elemente** | Ehrlichkeit ist das V1-Versprechen | DB INV-5, INV-10 |
| **Sichtbare Nicht-Unterstützung**: Ein Tool, das nicht symmetrisch kann, ist bei aktiver Symmetrie *vorab* als solches erkennbar | Verhindert die häufigste reale Fehlerklasse (still einseitig) | R2 §6, DB INV-8 |
| **Seam-Prüfung nach jeder Topologie-Operation**, deren Ergebnis im State sichtbar wird | Vergessene Pflege pro Operation (Wings-Muster, WP-STAB-07/12) wird *entdeckt*, statt still zu wirken | R2 §3.2, Mirai-Commits |
| **Bewusstes Aus-/Einschalten**; beim Einschalten wird der tatsächliche Zustand gezeigt | Absichtliche Asymmetrie ist legitim | DB INV-13 |
| **Re-Symmetrize, nur Positionen, gerichtet** (Quellseite wählbar; gepaarte Elemente angleichen, Seam auf die Ebene) | Reparatur *ohne* Identitätsverlust — genau die Variante, die später Weights/Morphs überlebt | R1 §3.1 (Snap to Symmetry), §8 |
| **Eine Handlung = ein Undo-Schritt**, beidseitig | Grundvertrauen | DB INV-7 |

### 3.3 Offen gelassene V1-Frage mit Entscheidungsbedarf durch den Artist

- **Beide Seiten gleichberechtigt oder eine führende Seite während des Modellierens?** DB lässt das offen. [INTERPRETATION] V1 braucht eine Quellseite nur für Re-Symmetrize. Ob der Artist beim Arbeiten eine führende Seite *will*, ist eine Product-Truth-Frage → Experiment E1/E6.

---

## 4. V1 Explicit Non-Goals

| Nicht in V1 | Warum nicht jetzt | Warum das nicht festfährt |
|---|---|---|
| Bevel, Inset, Bridge, Merge/Weld **über** die Seam, freie Knife-Pfade (falls Connect gewählt) | Jeder zusätzliche Seam-Fall braucht eigene Artist-Semantik; erst aus V1 lernen | Sichtbare Nicht-Unterstützung (§3.2) hält die Wahrheit sauber, bis sie kommen |
| Mehrere Ebenen, radiale Symmetrie, mehrere Inseln mit eigenen Seams | Kein V1-Use-Case; C4D zeigt, dass es pro Insel eigene Loops braucht (R2 §3.4) | Definition ist pro Objekt formuliert; eine Erweiterung auf mehrere Geltungsbereiche widerspricht nichts |
| Korrespondenz, die **Posen/Deformation** übersteht | Braucht Character-Pipeline, die es noch nicht gibt | V1-Korrespondenz ist *abgeleitet* → später austauschbar, ohne gespeicherte Daten zu migrieren |
| Re-Symmetrize **mit Topologie-Kopie** (Hälfte löschen + spiegeln) | Zerstört die Identität der Gegenseite; ist später gefährlich für Weights/Morphs | Wird nicht zur Grundgewohnheit; kann später als bewusst identitätszerstörende Aktion kommen |
| **Abgeleitete Hälfte** (Modifier / Virtual Mirror) als Modus | Zweites Modell; R1 zeigt Konflikte mit Character-Daten | Die Definition ist unabhängig vom Modus formuliert; ein Virtual-Mode kann später dieselbe Definition nutzen |
| Symmetrie für Weights, Morphs, Knochen | Diese Systeme existieren nicht in Produktion | Die Seam-Identität und die abgeleitete Korrespondenz sind genau die Bausteine, die sie brauchen (§8) |
| Automatische Wiederherstellung, automatisches „Fixen" | Widerspricht DB INV-12 | — |
| Toleranz als Wahrheit (Partner nur per Abstand) | R1 §7: Toleranz-Dilemma ungelöst | Position darf in V1 höchstens *vorschlagen* und *bestätigen*, nicht *definieren* |

---

## 5. V1 Artist Experiments

Jedes Experiment ist so geschnitten, dass Manu es in wenigen Minuten spielen und mit **KEEP / ITERATE / REJECT / UNKNOWN** bewerten kann (M4). Die Reihenfolge ist zugleich eine Priorität.

| # | Experiment | Was wird gelernt? | Beobachtung |
|---|---|---|---|
| **E1** | **Box → symmetrischer Torso** (Symmetrie erklären, mehrstufiges Extrude, Loops, Tweak) | Trägt V1 einen echten Alltags-Workflow? | Wie oft schaut Manu auf den State? Vertraut er ihm? Arbeitet er einseitig oder beidseitig? |
| **E2** | **Seam-Druck**: Seam-Vertices ziehen, Tweak nahe der Mitte, Extrude an der Seam | Fühlt sich der Seam-Schutz richtig an (hart vs. störend)? | Kämpft er gegen die Seam? Erwartet er etwas anderes? |
| **E3** | **Loop Insert**: parallel zur Seam, quer über die Seam, direkt neben der Seam | Ist die symmetrische Vorschau verständlich? Ist „ein Loop über die Mitte" intuitiv? | Überraschungen bei der Vorschau oder beim Ergebnis? |
| **E4** | **Pfad-Fall**: Connect (bevorzugt, weil AD-017 kontextuelles C bereits Artist-Verdikte hat) *oder* Knife, jeweils über/an der Seam | Wie muss gespiegelte **Interaktion** aussehen, bevor wir sie verallgemeinern? | Liest er den gespiegelten Pfad richtig? Wo ist er unsicher? |
| **E5** | **Nicht unterstütztes Tool** bei aktiver Symmetrie | Ist sichtbare Nicht-Unterstützung hilfreich oder lästig? | Ignoriert er den Hinweis? Wünscht er Blockieren statt Hinweis? |
| **E6** | **Absichtlich brechen**: Symmetrie aus, einseitig ändern, wieder ein | Ist „teilweise" verständlich? Reicht die Anzeige ungepaarter Elemente? | Weiß er danach, wo die Symmetrie noch gilt? |
| **E7** | **Re-Symmetrize nach Drift** (nur Positionen, mit Quellseite) | Reicht die identitätserhaltende Reparatur im Alltag? | Vermisst er „Hälfte löschen + spiegeln"? |
| **E8** | **Lange Session** (~30 Min. freies Modellieren) | Bleibt der State vertrauenswürdig? | Gab es einen Moment „das stimmt nicht mehr" — und hat V1 ihn angezeigt? |

**Erfolgskriterium von V1** [SCHLUSS]: nicht „alle Experimente KEEP", sondern **kein Experiment endet mit stiller falscher Symmetrie**, und E1 ist mindestens ITERATE.

---

## 6. V2 Candidate Capabilities — Robust Topology Symmetry

**Reifegrad:** Die Symmetrie überlebt die Modellierarbeit, auch wenn sie nicht ideal verläuft.

| Neue Fähigkeit | Löst welches V1-Problem? | Warum nicht in V1? |
|---|---|---|
| Weitere symmetrische Operationen (Bevel, Inset, Merge/Weld über die Seam, zweiter Pfad-Fall) | V1 deckt nur den Kernweg ab | Jede Operation braucht Seam-Semantik aus V1-Erfahrung (E2–E4) |
| Topologiebasierte Korrespondenz, robust gegen Drift | V1 ist anfällig, wenn die Form leicht asymmetrisch wird | Braucht Klarheit, was „mehrdeutig" auslöst (DB offene Frage) |
| Werkzeuge für teilweise Symmetrie (ungepaarte Bereiche finden, gezielt paaren oder bewusst asymmetrisch markieren) | V1 zeigt ungepaarte Bereiche nur an | Erst wissen, ob Manu das braucht (E6) |
| Re-Symmetrize mit Topologie-Übernahme — als bewusst identitätsbrechende Aktion mit klarer Anzeige, was verloren geht | V1 kann nur Positionen angleichen | Gefahr für spätere Character-Daten; erst Identitäts-Politik klären (§8) |
| Mehrere Inseln / Objekte mit eigener Definition | V1 kennt nur eine Definition pro Objekt | Kein Use Case bisher |
| Optional ein Modus mit abgeleiteter Hälfte | Manche Aufgaben sind so schneller (R1 M-A) | Zweites Modell; nur, wenn Experimente es verlangen |

- **Invarianten, die unverändert bleiben:** INV-1 (deklarierte Seam), INV-3 (abgeleitete Korrespondenz), INV-5 (nie still falsch), INV-9 (Symmetrie ist Systemfähigkeit).
- **Neue Risiken:**
  - Topologische Korrespondenz scheitert an regelmäßigen Netzen (R2 §3.1: Blender-Hashing).
  - Mehr Tools bedeuten mehr Seam-Sonderfälle (C4D-Fixliste, R2 §3.4).
  - Identitätsbrechendes Re-Symmetrize kann zur bequemen Standardgewohnheit werden.

---

## 7. V3+ Candidate Capabilities — Advanced Symmetry / Character Pipeline

**Reifegrad:** Die Symmetrie-Aussage wird von anderen Systemen *konsumiert*.

| Neue Fähigkeit | Löst welches Problem? | Warum nicht früher? |
|---|---|---|
| Weight-Mirroring auf Basis der Mesh-Korrespondenz **plus** einer Knochen-Korrespondenz | Symmetrisches Skinning | Braucht Rigging in Produktion (WP-05+), ARCH-01 |
| Morph-Mirroring und L/R-Split mit einer Übergangszone an der Seam | Symmetrische und halbseitige Morphs | Braucht Morph-System; Morph-Transfer-Semantik offen (FINDINGS-3C) |
| Knochen-/Joint-Symmetrie | Symmetrisches Rigging | Eigene Korrespondenz (Namen, Labels, Struktur), nicht Mesh (§9) |
| Symmetrie am posierten Character | Sculpt/Tweak in der Pose | Braucht Korrespondenz auf einem Referenzzustand, nicht auf der aktuellen Form |
| Topologieänderung nach Rigging/Morphs mit **spiegelkonsistenter** Datenübernahme | Die README-Vision „back to modeling" | Hängt an ARCH-02 (Provenance/Remapping) |
| Re-Symmetrize, das Weights/Morphs/UVs mitnimmt | Reparatur ohne Datenverlust | Braucht alle obigen |

- **Invarianten, die unverändert bleiben:** INV-1, INV-3, INV-4 (die Definition überlebt), INV-12 (Wiederherstellung ist bewusst).
- **Neue Risiken:**
  - Mehrere Korrespondenzen (Mesh, Knochen) können sich widersprechen.
  - Asymmetrische Absicht (Narbe, halbseitiger Morph) muss von „kaputter Symmetrie" unterscheidbar sein.
  - Remap-Fehler wirken dann auf Animationsdaten, nicht nur auf Geometrie.

---

## 8. Character Pipeline Implications

Für jedes Thema: Was sagen DCCs? Was wäre eine heute hilfreiche Grundhaltung? Was wäre heute schädlich?

### 8.1 Vertex Identity / Vertex Order / Stable Ordering

- [FAKT] ZBrush Poseable Symmetry verlangt topologische Symmetrie (R1 §3.6); ein Händler-Tutorial nennt identische Vertex-Anzahl und -Reihenfolge als Voraussetzung und rät nach Posen von Remesh-Operationen ab [E1].
- [FAKT] Max Symmetry Tools übertragen Symmetrie nur auf Modelle mit **gleicher Vertex-Anzahl** (R1 §3.2).
- [FAKT] Blender: „New from Objects Flipped" für Shape Keys verlangt übereinstimmende Topologie [E2].
- [ANWENDER] Maya: Topologieänderung nach Blendshape-Setup gilt als „ruinös", weil die Punktzuordnung bricht [E3].
- [FAKT] Mirai hat stabile, nicht wiederverwendete IDs (AD-001).
- **Hilfreich [SCHLUSS]:** Symmetrie und alle späteren Daten beziehen sich auf **Identität**, nie auf Reihenfolge oder Anzahl.
- **Schädlich [SCHLUSS]:** Jede Symmetrie-Funktion, die Reihenfolge als Partnerschaft benutzt (z. B. „Vertex i ↔ Vertex i + n/2"). Sie funktioniert in V1 bequem und ist spätestens nach dem ersten einseitigen Schnitt falsch.

### 8.2 Topology Identity / neue Elemente

- [FAKT] FINDINGS-3C: Die Herkunft neuer Elemente ist aus Snapshots nur erschließbar; der Operationskontext ist der verlässliche Weg (AD-017 B5).
- [SCHLUSS] R2 §5: Kein DCC vergibt Partnerschaft zum Entstehungszeitpunkt.
- **Hilfreich:** Eine symmetrische Operation bleibt **eine Absicht mit zwei Seiten**. Dann kann ein späteres Remapping (ARCH-02) beide Seiten gleich behandeln, ohne sie nachträglich zu erraten. Das ist eine Anforderung an die *Semantik*, nicht an eine Datenstruktur.
- **Schädlich:** Die Gegenseite als *zweite, unabhängige Operation* denken. Dann gibt es später zwei Herkunftsgeschichten, die sich unterschiedlich entwickeln können.

### 8.3 Correspondence

- [FAKT] Maya spiegelt Skin Weights über **zwei getrennte Zuordnungen**: eine Oberflächen-Zuordnung (nächster Punkt, Raycast, nächste Komponente, UV-Raum) und eine Einfluss-Zuordnung (nächster Joint, Knochenstruktur, Label u. a., in mehreren Durchgängen) [E4][E5].
- [FAKT] Blender spiegelt Weights über **Mesh-Spiegelung plus Namenskonvention** der Gruppen (.L/.R, _L/_R). Eine Gruppe ohne Gegenstück wird in sich selbst gespiegelt. „Mirror Vertex Group" setzt ein perfekt symmetrisches Netz voraus, Vertices ohne Gegenstück bleiben unberührt [E6][E7].
- [FAKT] Blender Shape-Key-Flip: Die positionsbasierte Variante verlangt perfekt symmetrische Vertices; eine topologische Variante existiert [E2].
- [INTERPRETATION] Korrespondenz ist in Character-Pipelines **zusammengesetzt**: Mesh-Partner × Influence-/Knochen-Partner. Die Mesh-Korrespondenz ist dabei die gemeinsame Basis.
- **Hilfreich:** Mesh-Korrespondenz als eigenständige, abfragbare, ableitbare Größe (DB INV-3), die andere Systeme später *benutzen* können.
- **Schädlich:** Mesh-Korrespondenz so zu formulieren, dass sie nur für die aktuelle Form gilt. Morphs und Posen brauchen Partner auf einem **Referenzzustand** (Basis/Rest), nicht auf der deformierten Form. Das Blender-Add-on „Shape Key Mirror Plus" arbeitet ausdrücklich auf Basis einer symmetrischen Grundform [E8].

### 8.4 Seam Identity

- [INTERPRETATION] Für Weights und Morphs ist die Seam mehr als „liegt auf der Ebene":
  - Ein symmetrischer Morph muss Seam-Vertices auf der Ebene halten.
  - Ein halbseitiger (L/R-)Morph braucht an der Seam eine **Übergangszone**. Das ähnelt Mayas Seam-Falloff beim Modellieren (R1 §3.8).
  - Ein Weight-Mirror muss Seam-Vertices mit sich selbst paaren.
- **Hilfreich:** Die Seam als Identitätsmenge, die auch *anderen* Systemen als Ort „Mitte" dient.
- **Schädlich:** Die Seam als reine Modellier-Hilfe, die nur das Transform-System kennt (Blender-Clipping ist ein Transform-Constraint, R1 §3.1).

### 8.5 Topologieänderung nach Rigging / Skinning / Morph-Erstellung

- [FAKT] Blender-Handbuch: Die meisten Edit-Mode-Operationen, die Topologie ändern, prüfen Shape-Key-Sperren nicht, **weil die Topologie normalerweise vor dem Erstellen von Shape Keys finalisiert sein soll** [E2].
- [ANWENDER] Maya/Max: Übliche Lösung für Edge Loops nach dem Skinning ist, das Modell zu duplizieren, zu ändern und die Weights per Nähe zurückzukopieren; Weights über UVs übertragen sei bei Topologieänderung unsicher [E9][E10].
- [ANWENDER] Blender: Ein Mirror Modifier ließ sich wegen vorhandener Shape Keys nicht anwenden [E11].
- [SCHLUSS] Die Branche geht überwiegend von „Topologie zuerst, dann Character-Daten" aus und behandelt spätere Änderungen mit Umwegen. Mirais README-Vision will diesen Zyklus ausdrücklich offen halten.
- **Hilfreich:** Symmetrische Topologie-Operationen, die **auf beiden Seiten dasselbe Ergebnis mit derselben Absicht** erzeugen (DB INV-6). Dann kann ein späteres Weight-/Morph-Remapping spiegelkonsistent sein.
- **Schädlich:**
  - Topologieänderung nach Rigging grundsätzlich zu verbieten (widerspricht der Vision).
  - Symmetrie so zu bauen, dass sie Topologie nur als *Einbahnstraße vor* dem Rigging versteht.

### 8.6 Re-Symmetrize, wenn Deformationsdaten existieren

- [SCHLUSS] Positions-Re-Symmetrize (V1) erhält die Identität; Weights und Morphs bleiben an ihren Vertices.
- [SCHLUSS] Topologie-kopierendes Re-Symmetrize (Hälfte löschen + spiegeln, R1 §3.1, §3.6) erzeugt auf einer Seite **neue** Elemente. Alle daran hängenden Daten sind weg oder müssen übertragen werden.
- **Hilfreich:** Identitätserhalt als Standard; Identitätsbruch nur als ausdrückliche, sichtbare Handlung.

### 8.7 Bone / Joint Symmetry

- [FAKT] Blender: Knochen-Symmetrie über **Namenskonvention**. Das Symmetrize der Armature spiegelt anhand der Namen; Knochen, die sich nicht links/rechts zuordnen lassen, werden ignoriert [E12][E13].
- [FAKT] Maya: Einfluss-Zuordnung beim Weight-Mirror über Nähe, Struktur oder Labels; Rigging Dojo empfiehlt Labels bei übereinanderliegenden Gesichts-Joints (Hersteller-nahe Trainingsseite) [E5][E14].
- [SCHLUSS] Knochen-Symmetrie ist eine **andere Korrespondenz**: über Struktur und Benennung, nicht über Mesh-Topologie.

### 8.8 Deformation Symmetry

- [INTERPRETATION] „Die Pose ist symmetrisch" und „das Netz ist symmetrisch" sind verschiedene Aussagen. Eine symmetrische Deformation verlangt symmetrische Weights, Knochen und Posen. Ein symmetrisches Netz ist dafür notwendig, aber nicht hinreichend.

---

## 9. Mesh Symmetry vs Character Symmetry

| Art | Was wird zugeordnet? | Übliche Grundlage in DCCs | Braucht Mesh-Korrespondenz? |
|---|---|---|---|
| **Geometric / Edit Symmetry** | Vertices/Edges/Faces beim Modellieren | Position oder Topologie + Seam (R1/R2) | *ist* sie |
| **Topology Symmetry** | Struktur beider Hälften | Seam + Netzstruktur (Maya, C4D) | Grundlage für robuste Mesh-Korrespondenz |
| **Morph Symmetry** | Offsets pro Vertex | Mesh-Korrespondenz **auf der Basisform** [E2][E8] | ja, auf Referenzzustand |
| **Weight Symmetry** | Weight pro Vertex **und** Einfluss | Mesh-Korrespondenz × Influence-Zuordnung [E4][E6] | ja, plus Knochen-Korrespondenz |
| **Rig / Bone Symmetry** | Knochen, Constraints | Namen, Labels, Struktur [E12][E13] | nein |
| **Deformation Symmetry** | Pose, Ergebnis | Ergebnis der obigen | indirekt |

**[SCHLUSS] Nicht vorschnell vereinheitlichen.** Die Research spricht für:

- **Gemeinsam:** die **Symmetry Definition** (Ebene/Geltungsbereich) und die **Mesh-Korrespondenz** als geteilte Grundlage für alles, was am Netz hängt (Edit, Morph, der Vertex-Teil von Weights).
- **Getrennt:** die **Knochen-/Einfluss-Korrespondenz** und die **Absicht** (symmetrischer Morph vs. halbseitiger Morph vs. bewusste Asymmetrie). DCCs lösen das jeweils eigenständig und kombinieren es erst bei der Anwendung.
- **Warnsignal:** Blender hat heute mindestens drei nebeneinander stehende Mechanismen (Mesh-X-Mirror, Topology-Mirror-Optionen an mehreren Stellen, Namenskonvention). [INTERPRETATION] Das zeigt die Kosten *ungeteilter* Grundlagen, nicht die Notwendigkeit *einer* großen Einheitslösung.

---

## 10. Future-Proofing Principles

Grundhaltungen, die V1 billig einnehmen kann und die später nicht teuer werden:

1. **Identität, nicht Reihenfolge.** Seam und Partner beziehen sich auf Element-Identität (passt zu AD-001).
2. **Korrespondenz ist abgeleitet und neu berechenbar** — und prinzipiell auch auf einem Referenzzustand berechenbar, nicht nur auf der aktuellen Form.
3. **Die Definition ist der dauerhafte Zustand;** sie ist so formuliert, dass später andere Systeme sie abfragen können (nicht nur das Edit-Mode-Tool).
4. **Eine symmetrische Operation ist eine Absicht mit zwei Seiten,** nicht zwei Operationen (anschlussfähig an AD-017 B5 / ARCH-02).
5. **Identitätserhalt ist der Standard,** Identitätsbruch ist eine ausdrückliche Handlung.
6. **Teilweise Symmetrie ist ein Zustand erster Klasse,** denn Characters sind selten perfekt symmetrisch.
7. **Kein Topologie-Freeze als Annahme.** Nichts in V1 darf voraussetzen, dass Topologie irgendwann „fertig" ist.
8. **Symmetrie-Arten getrennt denken, Grundlage teilen:** Definition + Mesh-Korrespondenz teilen, Knochen und Absicht getrennt.

---

## 11. Architectural Risks to Avoid

Jeweils: scheinbar einfache V1-Entscheidung → warum sie später teuer wird → Beleg.

| # | Scheinbar einfach | Warum später teuer | Beleg |
|---|---|---|---|
| **AR-1** | Partner dauerhaft speichern | Muss durch jede Operation gepflegt werden → vergessene Pflege, veraltete Tabellen | R2 §7 (kein DCC tut es); Blender-Cache mit groben Zählerprüfungen (R2 §3.1); Mirai WP-STAB-07/12 |
| **AR-2** | Vertex-Reihenfolge als Symmetrie-Identität | Bricht beim ersten einseitigen Schnitt; blockiert Morphs/Weights | ZBrush-Voraussetzungen [E1], Max Symmetry Tools (R1), Maya-Blendshape-Berichte [E3] |
| **AR-3** | Seam über Position erkennen | Toleranz-Dilemma, Drift, keine Identität für spätere Systeme | R1 §2.1, §7 |
| **AR-4** | Symmetrie nur als einmalige Spiegel-Operation | Erzeugt neue Identitäten auf der Gegenseite; Character-Daten gehen verloren | R1 §3.1 (Symmetrize), §3.6 (Mirror & Weld), [E11] |
| **AR-5** | Topologie-Korrespondenz = Morph-Korrespondenz | Morphs brauchen Partner auf der Basisform, auch wenn die aktuelle Form posiert oder asymmetrisch ist | [E2], [E8], C4D T-Rex-Beispiel (R2) |
| **AR-6** | Symmetrie nur als Modifier/abgeleitete Hälfte | Keine Arbeit am ganzen Netz; Konflikte mit Shape Keys; Weight Painting über die Mitte schwierig | [E11], R1 §4 M-A |
| **AR-7** | Symmetrie nur als Edit-Mode-Tool-Einstellung | Keine abfragbare Definition → jedes spätere System erfindet eigene Heuristiken | Blender: drei getrennte Mechanismen (§9) |
| **AR-8** | Topologieänderung nach Rigging verbieten | Widerspricht der Mirai-Vision; die Branche zahlt mit Umwegen (Duplizieren + Weights zurückkopieren) | [E2], [E9], [E10], README |
| **AR-9** | Die Gegenseite als zweite, eigenständige Operation ausführen | Zwei Herkunftsgeschichten → spiegelinkonsistentes Remapping später | FINDINGS-3C, AD-017 B5, R2 §5 |
| **AR-10** | Spiegel-Logik pro Tool | Tool-Abdeckung wird Dauerbaustelle; stille Einseitigkeit | R2 §4 (C4D-Fixliste, Maya-Toolkit vs. alte Tools) |
| **AR-11** | Re-Symmetrize per „Hälfte löschen + spiegeln" als Standard | Wird zur Gewohnheit, bevor es Character-Daten gibt → später Datenverlust | §8.6 |
| **AR-12** | Nur ein globaler Symmetrie-Schalter ohne Geltungsbereich | Mehrere Objekte/Inseln/Characters später nicht ausdrückbar | C4D: eine Loop pro Insel (R2 §3.4) |

---

## 12. Open Questions

- **Artist (M4):**
  - Führende Seite beim Modellieren? (E1/E6)
  - Seam-Schutz hart oder mit Übergangszone? (E2)
  - Nicht unterstützte Tools blockieren oder nur markieren? (E5)
- **Priorität:** Connect oder Knife als V1-Pfad-Fall? Vorschlag Connect (AD-017-Kontext), aber das entscheidet der Artist. Artist-Entscheidung 2026-09-25: Knife (A8, WP-SYM-LAB-01 Slice 6).
- **Referenzzustand:** Auf welcher Form wird Korrespondenz später berechnet — Rest, Basis, Modellierzustand? Relevant erst in V3, aber V1 soll es nicht ausschließen.
- **ARCH-02-Schnittstelle:** Reicht „eine Absicht mit zwei Seiten" als Semantik, oder braucht Remapping mehr? Offen.
- **ARCH-01:** Ist die Definition an Objekt, Mesh oder Geltungsbereich gebunden? Hängt am Object/Component-Modell.
- **Absichtliche Asymmetrie:** Braucht sie ein eigenes Konzept (Layer, Markierung) oder genügt „teilweise"? V2/V3.
- **Nicht untersucht:** Radiale Symmetrie für Characters (Spinnen, Oktopus), UV-Symmetrie.
- **Seam-Deklaration bei nicht exakter Mitte (V2+, Artist-Frage, 2026-09-25):** Wie erklärt der
  Artist die Seam, wenn Mittel-Vertices nicht exakt auf der Ebene liegen (z. B. OBJ-Rundung, von
  Hand verschoben)? Anlass: Symmetry Lab Slice 5 (KEEP). Dort wird die Seam beim Einschalten aus
  exakten Positionen abgeleitet (Lab-Annahme E3); ein Mittel-Vertex neben der Ebene reißt eine
  Lücke, und Re-Symmetrize lehnt ab. Das ist für V1 gewollt (keine Toleranz, A5), berührt aber den
  Grundsatz des Design Brief, dass Position die Seam nur *vorschlagen*, nicht *definieren* darf.
  Mögliche Richtungen (nicht bewertet): Seam explizit wählen/korrigieren, Vorschlag mit Bestätigung,
  Toleranz nur als Vorschlagshilfe.

---

## 13. Suggested Evolution Path

Kein Zeitplan; Übergänge sind an **Evidenz** gebunden, nicht an Features.

```text
V1  Erklärt · sichtbar · ehrlich
    Definition + deklarierte Seam (Identität) + abgeleitete Korrespondenz
    Transform/Tweak · Extrude · Loop Insert · Delete · ein Pfad-Fall
    State sichtbar · Nicht-Unterstützung sichtbar · Positions-Re-Symmetrize
        │
        │  Übergang, wenn: E1 ≥ ITERATE, keine stille Falschheit in E1–E8,
        │  Seam-Semantik für Extrude/Loop/Pfad-Fall als Artist-Verdikt festgehalten
        ▼
V2  Robust gegenüber Topologie und Form
    weitere Operationen · topologische Korrespondenz · Werkzeuge für teilweise Symmetrie
    identitätsbrechendes Re-Symmetrize (explizit) · mehrere Geltungsbereiche · ggf. abgeleitete Hälfte
        │
        │  Übergang, wenn: Character-Systeme in Produktion (WP-05+),
        │  ARCH-01 und ARCH-02 entschieden, Weight-/Morph-Semantik (FINDINGS-3C) als M4-Verdikt
        ▼
V3+ Symmetrie als geteilte Wahrheit
    Mesh-Korrespondenz auf Referenzzustand · Weight-/Morph-Mirroring · Knochen-Korrespondenz
    Symmetrie in der Pose · spiegelkonsistente Topologieänderung nach Rigging
```

**Kernantworten [SCHLUSS]:**
- **Kleinster Kern:** Definition mit deklarierter Seam (über Identität), abgeleitete Korrespondenz mit ehrlichem Zustand, symmetrisches Arbeiten auf dem Alltagsweg, identitätserhaltende Reparatur.
- **Bewusst ungelöst, ohne sich festzufahren:** Bevel/Inset/Merge über die Seam, Posen-Robustheit, mehrere Geltungsbereiche, Character-Daten, topologie-kopierendes Re-Symmetrize, abgeleitete Hälfte. Keines davon verlangt, eine V1-Wahrheit zurückzunehmen — solange V1 die Risiken AR-1 bis AR-12 meidet.

---

## 14. Quellen

Abgerufen 2026-09-24.

**Mirai-Repo (Stand `24ff921`)** — `src/core/ids.py`; `docs/architecture/AD-017-CUT-ENGINE-CONTEXTUAL-C.md` §B5; `docs/design/artist_playground/WP-AP-CUT_PLAN.md` §1.1; `experiments/rigging-skinning-morphing/FINDINGS-3C.md` und „Phase 3C Test Execution — Final Report.md"; `docs/research/CHARACTER_SYSTEMS_RESEARCH.md`; README; Commits WP-STAB-07/-12.

- [E1] [Händler-Tutorial] Novedge 2026 — Poseable Symmetry. https://novedge.com/blogs/design-news/zbrush-tip-poseable-symmetry-for-symmetric-sculpting-on-posed-models
- [E2] Blender 5.2 LTS Manual — Shape Keys Panel. https://docs.blender.org/manual/en/latest/animation/shape_keys/shape_keys_panel.html
- [E3] [ANWENDER] tech-artists.org 2018 — Modifying topology after blendShape set-up. https://www.tech-artists.org/t/maya-modifying-topology-i-e-adding-edges-after-the-blendshape-set-up-am-i-screwed/10708
- [E4] Autodesk Maya 2025 — Copy Skin Weights Options. https://help.autodesk.com/cloudhelp/2025/ENU/Maya-CharacterAnimation/files/GUID-23A76179-A77B-4595-823D-59EA028F0298.htm · Maya 2018: https://knowledge.autodesk.com/support/maya/learn-explore/caas/CloudHelp/cloudhelp/2018/ENU/Maya-CharacterAnimation/files/GUID-23A76179-A77B-4595-823D-59EA028F0298-htm.html
- [E5] Autodesk Maya 2024 — Mirror Skin Weights Options. https://help.autodesk.com/cloudhelp/2024/ENU/Maya-CharacterAnimation/files/GUID-27FE7EDB-4078-473A-B001-C9AFAB3A77A3.htm
- [E6] Blender Manual (2.82) — Weight Paint Options (X Mirror). https://docs.blender.org/manual/ja/2.82/sculpt_paint/weight_paint/tool_settings/options.html
- [E7] Blender Manual — Editing Weight Paint (Mirror Vertex Group). https://docs.blender.org/manual/ja/dev/sculpt_paint/weight_paint/editing.html
- [E8] [Drittanbieter] Shape Key Mirror Plus — Blender Extensions. https://extensions.blender.org/add-ons/shape-key-mirror-plus/
- [E9] [ANWENDER] Autodesk Community 2025 — Adding edge loop after skinning. https://forums.autodesk.com/t5/maya-animation-and-rigging-forum/adding-edge-loop-after-skinning/td-p/13634525
- [E10] [ANWENDER] polycount 2019 — Best ways to alter mesh after paint weights. https://polycount.com/discussion/210147/maya-best-ways-to-alter-mesh-after-paint-weights-rigging-etc
- [E11] [ANWENDER] Steam Community 2022 — How to mirror weight paint properly. https://steamcommunity.com/app/365670/discussions/0/3731827719866321852/
- [E12] Blender 5.2 LTS Manual — Bone Naming. https://docs.blender.org/manual/en/latest/animation/armatures/bones/editing/naming.html
- [E13] Blender Manual (dev) — Armature Symmetrize. https://docs.blender.org/manual/it/dev/animation/armatures/bones/editing/symmetrize.html
- [E14] Rigging Dojo — Recommended Mirror Skin Weights Options. https://www.riggingdojo.com/2015/01/08/maya-mirror-settings-for-skin-weights/
