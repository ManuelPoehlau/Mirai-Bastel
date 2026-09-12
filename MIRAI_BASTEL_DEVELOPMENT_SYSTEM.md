# Mirai-Bastel Development System

**Status:** Erster produktiver Entwurf — in Benutzung, noch nicht bewährt
**Datum:** 2026-09-12
**Gilt für:** Artist und alle AI-Agenten, die an diesem Repository arbeiten

---

## 1. Zweck

Mirai-Bastel wird von einem Artist und mehreren spezialisierten AI-Agenten gemeinsam entwickelt. Dieses Dokument beschreibt, wie diese Zusammenarbeit funktioniert.

Es ist kein Projektmanagementsystem. Es ist ein Satz Verhaltensregeln, der vier Fehler verhindern soll:

1. Neubau von Bestehendem
2. Ignorieren vorhandener Architektur
3. Verwechslung von Experiment und Produkt
4. Verlust der künstlerischen Absicht

---

## 2. Leitsatz

> **So viel autonome AI-Arbeit wie möglich, bei so wenig notwendiger Artist-Aufmerksamkeit wie möglich, ohne Intent und Erkenntnisqualität zu verlieren.**

Das ist gleichzeitig das Bewertungskriterium für dieses System selbst. Jeder Mechanismus, der Artist-Aufmerksamkeit kostet, muss einen entsprechend großen Fehler verhindern. Mechanismen, die das nicht leisten, werden gestrichen.

---

## 3. Was bereits existiert

Das meiste ist vorhanden und wird nicht ersetzt. Dieses Dokument verbindet die Teile, es führt keine neue Dokumentationsstruktur ein.

| Schicht | vorhanden als |
|---|---|
| Intent / Vision | `docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md`, AD-004 |
| Entscheidungen | AD-001, AD-004, AD-005, ADR-001 (append-only) |
| Architektur-Realität | `docs/architecture/SOURCE_ARCHITECTURE.md`, `CORE_API_AUDIT.md` |
| Reifegrad-Grenze | `experiments/` ↔ `src/core` ↔ `src/mirai` (strukturell, nicht dokumentarisch) |
| Technische Wahrheit | Tests, Gates, Fehlerregel in `tests/README.md` |
| Erkenntnisdisziplin | FINDINGS-Praxis: leer starten, Observation ≠ Interpretation, Mechanical ≠ Semantic |
| Artist-Wahrheit (Interaction) | Three-Role UX System, `docs/design/artist_playground/UX_RESEARCH.md` |
| Agent-Regeln | `AGENTS.md` |

---

## 4. Die fünf Mechanismen

### M1 — History Awareness

> Bevor etwas neu gebaut wird, muss bekannt sein, was bereits existiert, was bewusst verworfen wurde und unter welchen Bedingungen Bestehendes ersetzt werden darf.

**Existenz.** Vor dem Entwerfen von Lösung, Architektur oder Code prüft der Agent: Existiert das schon? Existiert ein Experiment dazu? Existiert eine Entscheidung? Existiert ein verworfener Ansatz? Existiert benachbarter Code, der adaptierbar ist? Ergebnis in zwei Zeilen, dann erst der Vorschlag.

**Geschichte.** Wenn ein Ansatz verworfen wird, wird er in der Form `X wird nicht verwendet, weil Y` in der zuständigen Entscheidung festgehalten. Ohne das findet die Existenzprüfung nur Vorhandenes und nie Verworfenes — und derselbe Ansatz wird in drei Monaten wieder erfunden.

**Evidenz.** Ein validiertes, dokumentiertes, funktionierendes System darf ersetzt werden. Aber nur mit der Angabe, welche Annahme widerlegt ist oder welche neue Evidenz vorliegt.

> `Validated` begründet eine Vermutung für Wiederverwendung, kein Verbot der Ersetzung.

Damit werden zwei gegensätzliche Fehler vermieden: blindes Neubauen und dogmatisches Nicht-Anfassen.

Ablauf: **Existenz → Geschichte → Evidenz → Entscheidung.**

*Kosten: keine. Reine Agentenarbeit.*

---

### M2 — Context Check

Wenn ein Agent in unbekanntes Terrain eintritt, **legt er seine relevante Annahme über den aktuellen Stand offen. Der Artist korrigiert sie nur, wenn sie falsch ist.**

Der Default ist also nicht „Artist, bitte bestätige meinen Projektstatus", sondern „Ich arbeite mit dieser Annahme — falls sie falsch ist, korrigiere mich."

Unbekanntes Terrain heißt: neuer Bereich, längere Pause, Übernahme fremder Arbeit, oder der Agent bemerkt selbst eine Lücke. Nicht bei jeder Session. Kein Statusbericht zum Abnicken. Wenn der Agent sicher im Kontext ist, entfällt der Check.

*Kosten: nahe null, da keine Antwort erforderlich ist.*
*Abschaltbedingung: Wenn dieser Mechanismus nach mehreren Anwendungen nie eine falsche Annahme aufgedeckt hat, ist er Ritual und wird gestrichen.*

---

### M3 — Promotion Boundary

Code in `experiments/` ist Spielwiese. Code in `src/` ist Produkt. **Kein Agent verschiebt etwas über diese Grenze. Kein Agent behauptet, etwas sei vom Artist validiert.**

Promotion bedeutet nicht Merge. Git kann sagen, dass Code in `main` liegt. Das sagt nichts darüber, ob dieses Verhalten das Verhalten ist, das Mirai-Bastel haben soll.

> **Codezustand ≠ Produktzustand.**

Promotion bedeutet: Dieses Verhalten ist gut genug verstanden, dass es dauerhaft Produktverhalten wird. Diese Aussage trifft ausschließlich der Artist.

*Kosten: minimal. Die Grenze existiert schon strukturell.*

---

### M4 — Artist Verdict (Product Truth)

Das Artist-Verdikt ist keine UI-Abnahme. Es ist die Aussage darüber, ob das Produkt für den vorgesehenen kreativen Vorgang richtig ist:

- Fühlt sich eine Selection-Interaktion richtig an?
- Funktioniert ein Extrude-Workflow mental und körperlich?
- Verhält sich ein Rig so, wie ein Artist es erwartet?
- Ist ein Morphing-Mechanismus kontrollierbar?
- Ist eine Animation-Interaktion sinnvoll?
- Unterstützt das Tool den kreativen Gedanken, den es unterstützen soll?

Diese Fragen kann kein Test beantworten und kein Agent. Ein System kann technisch korrekt, performant, getestet und architektonisch sauber sein — und hier trotzdem durchfallen.

Vier Ausgänge: **KEEP / ITERATE / REJECT / UNKNOWN.** `UNKNOWN` ist ein gültiges Ergebnis.

#### Artist-Attention-Filter

> **Ein Agent fragt den Artist nur, wenn die offene Frage Product Truth, Intent, Priorität oder Promotion betrifft — und sie nicht durch vorhandene Evidenz oder einen weiteren autonomen Test beantwortet werden kann.**

Vier Ebenen, in dieser Reihenfolge zu prüfen:

| Situation | Handlung |
|---|---|
| Agent kann selbst entscheiden | entscheiden |
| Agent kann es durch Recherche oder Test herausfinden | recherchieren, testen |
| Es braucht künstlerische/semantische Bewertung | Artist-Test vorbereiten, dann fragen |
| Es braucht eine Produktentscheidung | Artist entscheidet |

„Ich könnte X oder Y machen, was möchtest du?" ist keine legitime Artist-Frage, wenn der Agent es selbst herausfinden könnte.

#### Zwei weitere Regeln

- **Wer ein Verdikt anfragt, hat die Testsituation vorbereitet.** Der Artist bekommt nichts vorgelegt, was er nicht in wenigen Minuten spielen kann.
- **Das Verdikt wird als Aussage des Artists festgehalten**, nicht als Chatnotiz. Sonst wird es in der nächsten Session neu verhandelt.

*Kosten: Hier liegt die gesamte Aufmerksamkeitskostenstelle des Systems. Entsprechend sparsam einsetzen.*

---

### M5 — Discovery ↔ Production

Jede Arbeitseinheit ist entweder Discovery oder Production. Der Modus wird am Anfang benannt.

**Discovery** — Wir wissen noch nicht, was richtig ist. Also experimentieren wir. M1, M2 und M4 greifen.

**Production** — **Die Produktentscheidung ist getroffen. Jetzt wird sie zuverlässig umgesetzt.** M4 greift nicht, weil nichts zu beurteilen ist.

> ## BUILD darf keine neue Erkenntnis behaupten.

Der typische Fehlerverlauf, den dieser Satz verhindert:

```text
Entscheidung: "Wir wollen Verhalten X."
        ↓ Builder
"Beim Implementieren erschien X' irgendwie sinnvoller."
        ↓ Agent entscheidet still
"Also haben wir jetzt X'."
```

Nein. X' ist eine neue Erkenntnis und damit eine neue Entscheidung. Sie wird als offene Frage festgehalten, der Modus wechselt zurück zu Discovery. Sie wird nicht im Bauen nebenbei entschieden.

*Kosten: keine. Dieser Mechanismus schützt das System davor, sich überall aufzuzwingen.*

---

## 5. Autorität

Autorität folgt der Evidenzdomäne. Der Artist entscheidet nicht alles, sondern genau das, was niemand sonst entscheiden kann:

- **Intent** — was gebaut wird
- **Product Truth** — ob ein Verhalten für den vorgesehenen Workflow richtig ist (M4)
- **Priorität** — welche Frage jetzt wichtig ist
- **Promotion** — ob die Evidenz stark genug ist (M3)

Alles andere nicht. Der Artist ist nicht Research Manager, Test Manager, Review Manager oder Integration Manager.

Agenten entscheiden selbstständig in ihrer Evidenzdomäne und fragen dort nicht nach: ein fehlgeschlagener Test, eine verletzte Invariante, drei bereits existierende Implementierungen — das stellt der Agent fest und handelt danach.

### Agentenpflichten

- M1 anwenden, bevor etwas erzeugt wird
- kennzeichnen, ob eine Aussage belegt oder angenommen ist
- eine eigene Inferenz nie später als Artist-Aussage zitieren
- Artist-Tests vorbereiten, nicht nur anfordern
- den Artist-Attention-Filter aus M4 anwenden, bevor gefragt wird

Zwei Dinge darf ein Agent nie: **promovieren** und **Artist-Validierung behaupten**.

---

## 6. Das Three-Role UX System

Bleibt unverändert. Es behält seinen eigenen Wissensspeicher (`docs/design/artist_playground/UX_RESEARCH.md`), seine drei Rollen und seine eigene Schleife.

Es ist die erste und bisher einzige Instanz von M4. Seine Verdikte laufen in den Entscheidungs-Layer des Projekts ein.

Sein eigentlicher Wert liegt nicht in der Dreizahl der Rollen, sondern in zwei Dingen: dem funktionierenden Erkenntniszyklus, und der Trennung von Erzeuger und Bewerter. Ein Agent, der etwas gebaut hat, ist ein schlechter Bewerter derselben Sache.

> Wo unabhängige Bewertung nötig ist, müssen Erzeugung und Bewertung getrennt sein.

Eine zweite Instanz (Rigging, Morphing, Animation) wird gebaut, wenn die erste Ergebnisse geliefert hat. Nicht vorher, und nicht durch Ausweiten der bestehenden.

---

## 7. Der Kreislauf in der Praxis

Beispiel: „Selection soll verbessert werden."

```text
M1   Was existiert? Was wurde probiert? Was wurde verworfen?
      ↓
M5   Discovery oder Production?
      ↓
      Discovery:  kleinstes sinnvolles Experiment
      ↓
      technische Evidenz: Tests, Performance, Architektur
      ↓
M4   Product Truth offen? → Artist-Test vorbereiten → fragen
      ↓
      KEEP / ITERATE / REJECT / UNKNOWN
      ↓
      Entscheidung (append-only)
      ↓
M3   Promotion durch Artist
      ↓
      Production
```

Und falls beim Bauen etwas Neues auftaucht: zurück zu Discovery (M5).

---

## 8. Was ausdrücklich nicht gebaut wird

- keine `REALITY.md`, keine Projektzustands-Datenbank
- kein Claim-Schema, kein Knowledge Graph, keine Provenienz-Felder
- keine Status-Taxonomie über die vorhandene Verzeichnisstruktur hinaus
- keine Rollen-Prompts pro Fachbereich
- keine Handoff-Protokolle, Registries, Dashboards, Metriken
- kein Backlog, keine Tickets, keine Sprints
- keine permanenten Agentenrollen auf Projektebene

Regel für alles Weitere:

> **Ein Prozessmechanismus muss einen eingetretenen Fehler lösen, nicht einen erwarteten.**

---

## 9. Offene Punkte

**Blockiert nicht:**

- Ob M2 wirkt oder Ritual ist. Steht auf Bewährung (Abschaltbedingung siehe M2).
- Ob M3 und M5 dieselbe Regel sind. M5 gilt pro Arbeitseinheit, M3 pro Artefakt. Falls sich das in der Praxis als identisch erweist, werden sie verschmolzen.
- Wann die zweite M4-Instanz gebaut wird und für welchen Bereich.
- Weight-Merge- und Morph-Transfer-Semantik aus Phase 3C. Das sind Product-Truth-Fragen, also M4-Fälle — und damit die ersten echten Tests dieses Systems außerhalb von UX.

**Könnte das System ändern:**

- Retro-Test: drei bis fünf echte Driftfälle rekonstruieren und prüfen, woran es jeweils lag. Falls sich zeigt, dass die Information meist vorhanden, aber nicht angesehen wurde, ist das Problem Auffindbarkeit und nicht Kontext — dann wäre M2 der falsche Mechanismus und es bräuchte stattdessen einen Index. Einmalig, etwa eine Stunde.

**Ehrliche Unsicherheit:** Mirai-Bastel hat viel Dokumentation relativ zu ausgelieferten Features. Fünf Mechanismen sind für ein Ein-Personen-Projekt an der Obergrenze. Wenn dieses Dokument jemals überarbeitet werden muss, dann durch Streichen.

---

## 10. Status dieses Dokuments

Dieses System ist entworfen, aber nicht bewährt. Es folgt selbst dem Prinzip, das es beschreibt:

> **Build → Play → Observe → Decide → Integrate.**

Der nächste Schritt ist nicht, es weiter zu verbessern. Der nächste Schritt ist, es zu benutzen — und dabei zu beobachten, ob M1 bis M5 tatsächlich tragen.

---

## Verwandte Dokumente

- `AGENTS.md` — repository-weite Agentenregeln (sollte auf dieses Dokument verweisen)
- `docs/architecture/PROJECT_VISION_AND_V1_PRINCIPLE.md` — Intent
- `docs/architecture/SOURCE_ARCHITECTURE.md` — Architektur-Realität
- `docs/design/artist_playground/UX_RESEARCH.md` — UX-Subsystem, erste M4-Instanz
- `tests/README.md` — Fehler-Entscheidungsregel
