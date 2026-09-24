# Mirai Symmetry Design Brief

**Status:** Discovery / Design-Artefakt. **Keine** Architecture Decision, **keine** Implementierungsentscheidung.
**Datum:** 2026-09-24
**Ort (vorgeschlagen):** `docs/design/SYMMETRY_DESIGN_BRIEF.md` (Design = gewünschtes Verhalten, laut `docs/design/README.md`)
**Modus (M5):** Discovery
**Grundlage (unverändert, nur verlinkt):**
- [`EDIT_MODE_SYMMETRY_RESEARCH.md`](../research/symmetry/EDIT_MODE_SYMMETRY_RESEARCH.md) — im Folgenden **R1**
- [`SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md`](../research/symmetry/SYMMETRY_TOPOLOGY_OPERATIONS_RESEARCH.md) — im Folgenden **R2**

**Zweck:** Brücke zwischen Research und einer späteren Architecture Decision. Der Brief legt fest, **was wahr sein muss** — nicht, wie es gebaut wird. Datenstrukturen, Caches, Events, Replays und Modul- oder Tool-Zuschnitte sind ausdrücklich nicht Teil dieses Dokuments.

---

## 1. Was „Edit-Mode Symmetry" in Mirai für den Artist bedeuten soll

> Der Artist erklärt ein Objekt (oder einen Teil davon) für symmetrisch. Ab dann darf er so arbeiten, als hätte er nur eine Hälfte vor sich. Jede unterstützte Handlung wirkt verlässlich und vorhersehbar auch auf der Gegenseite. Wenn das irgendwo nicht mehr garantiert ist, **sieht** er es, bevor er sich darauf verlässt.

Drei Versprechen, in dieser Reihenfolge:

1. **Verlässlich:** Was gespiegelt wird, wird richtig gespiegelt.
2. **Ehrlich:** Was nicht (mehr) gespiegelt werden kann, wird als solches erkennbar — nie stillschweigend halb.
3. **Leicht:** Der Artist muss die Symmetrie nicht pflegen, reparieren oder im Kopf behalten.

Wenn diese Versprechen kollidieren, gilt: **Ehrlich vor leicht.** (Begründung: R1 §7 und R2 §6 zeigen, dass stille Fehlzustände das teuerste Problem historischer Systeme waren.)

---

## 2. Begriffe und Verantwortungsbereiche

| Begriff | Bedeutung | Wer ist verantwortlich / Source of Truth |
|---|---|---|
| **Symmetry Definition** | Die Erklärung des Artists: *dieses* Objekt/diese Insel ist symmetrisch, bezogen auf *diese* Ebene, mit *dieser* Naht. Der dauerhafte, gewollte Zustand. | Der Artist (erklärt, ändert, hebt auf). Das System bewahrt sie. |
| **Symmetry Plane** | Die geometrische Referenz, an der gespiegelt wird. Ein mathematisches Objekt, keine Geometrie im Netz. | Teil der Definition. |
| **Symmetry Seam** | Die konkreten Netz-Elemente, die als „auf der Mitte liegend / ihr eigenes Gegenstück" **deklariert** sind. Ein topologisches Objekt, keine Positionsvermutung. | Teil der Definition. Muss Topologie-Operationen überleben oder erkennbar ungültig werden. |
| **Symmetry Region / editable side** | Die Hälfte, die in einem gerichteten Vorgang als Quelle gilt (z. B. Re-Symmetrize). Bei normalem Arbeiten sind beide Seiten bearbeitbar. | Der Artist, wenn eine Richtung nötig ist. Das System erfindet keine Richtung still. |
| **Correspondence** | Die Zuordnung Element ↔ Gegenstück für den **aktuellen** Netzzustand. Jedes Element ist *gepaart*, *selbst-gepaart* (Naht), *ungepaart* oder *mehrdeutig*. | Abgeleitet aus Definition + aktuellem Netz. **Keine** eigenständige Wahrheit. |
| **Symmetry State** | Die für den Artist sichtbare Gesamtaussage: gültig / teilweise / mehrdeutig / verletzt / aus. | Abgeleitet. Muss jederzeit erkennbar sein. |
| **Symmetric Operation** | Eine Artist-Handlung, die mit ihrem Spiegelbild als **eine** Handlung ausgeführt wird: ein Ergebnis, ein Undo-Schritt, ein Abbruch. | Die Operation liefert ihr gespiegeltes Ergebnis selbst; es wird nicht nachträglich erraten. |
| **Symmetric Interaction** | Die Spiegelung der **Eingabe und Absicht** des Artists: Hover, Cursorpfade, Schnittpunkte, Vorschauen, Snaps. | Eigenständig. Sie ist nicht dasselbe wie gespiegelte Geometrie. |

**Abgrenzung, die ausdrücklich gelten soll:**
- Die Seam ist **nicht** „alle Vertices mit x≈0". Position kann eine Seam *vorschlagen*, aber nicht *sein* (R1 §2.1, §4 M-E; R2 §6).
- Die Plane ist **nicht** aus der Seam „errechnet und dann mitdriftend". Wenn Plane und Seam sich widersprechen, ist das ein **sichtbarer Zustand**, keine stille Neuausrichtung (vgl. Wings-Anker am Vorher-Zustand, R1 §3.5).

---

## 3. Invarianten

Jede Invariante ist eine Aussage, die für den Artist wahr bleiben muss, unabhängig davon, wie sie später erreicht wird.

- **INV-1 — Deklarierte Seam.** Die Seam ist Teil der Definition, nicht das Ergebnis einer Positionsprüfung.
- **INV-2 — Seam liegt auf der Plane.** Solange der State „gültig" ist, liegen alle Seam-Elemente auf der Plane. Weicht ein Seam-Element ab, ist das entweder durch definiertes Verhalten verhindert oder sichtbar gemeldet — nie still toleriert.
- **INV-3 — Korrespondenz ist ableitbar.** Partnerbeziehungen lassen sich jederzeit aus Definition + aktuellem Netz neu gewinnen. Keine Partnerbeziehung ist eine „ewige Wahrheit", die jede Operation von Hand mitschleppen muss (R2 §7).
- **INV-4 — Die Definition überlebt.** Was eine Operation durch das Netz tragen muss, ist die **Definition** (vor allem die Seam), nicht die Partnerliste. Überlebt die Seam eine Operation nicht eindeutig, wird das erkennbar (R2 §3.2, §6).
- **INV-5 — Keine stille falsche Symmetrie.** Das System spiegelt nie auf ein Element, dessen Partner mehrdeutig oder unbekannt ist. Es spiegelt richtig oder erkennbar gar nicht.
- **INV-6 — Deterministische symmetrische Operation.** Eine unterstützte Operation erzeugt ihre Gegenseite aus derselben Absicht. Die Gegenseite ist dadurch das **Spiegelbild der Absicht** — nicht das Ergebnis einer nachträglichen Suche, die hofft, das Richtige zu erkennen (R2 §5).
- **INV-7 — Eine Handlung, ein Schritt.** Die Operation und ihr Spiegelbild sind für Undo/Redo/Cancel untrennbar.
- **INV-8 — Keine halbe Unterstützung.** Eine Operation unterstützt Symmetrie entweder, oder das ist **vor** der Ausführung erkennbar. Kein Werkzeug läuft stillschweigend nur einseitig, während Symmetrie aktiv ist (R2 §6: C4D blendet ab, Blender/Maya/Modo laufen still einseitig).
- **INV-9 — Symmetrie ist eine Querschnittsfähigkeit.** Einzelne Modeling-Tools implementieren keine eigene Spiegel-Logik. Ein Tool muss höchstens erklären, *ob* und *in welcher Form* es symmetrisch wirken kann.
- **INV-10 — Teilweise Symmetrie ist ein legitimer Zustand.** Ungepaarte Elemente sind erlaubt, erkennbar und abfragbar. Sie werden nicht als Fehler, aber auch nicht als symmetrisch behandelt.
- **INV-11 — Symmetrische Interaktion ist Pflicht, nicht Kür.** Für eine pfad- oder cursorbasierte Operation, die als symmetrisch gilt, sieht der Artist *vor* dem Bestätigen, was auf der Gegenseite passieren wird.
- **INV-12 — Wiederherstellung ist eine bewusste Handlung.** Re-Symmetrize hat immer eine erkennbare Quellseite und passiert nie automatisch im Hintergrund.
- **INV-13 — Absichtliche Asymmetrie ist erlaubt.** Der Artist kann Symmetrie jederzeit bewusst brechen, ohne gegen das System zu kämpfen.

---

## 4. Konzeptioneller Layer: Definition → Correspondence → Operation → Interaction

Nur als Denkmodell. Es sagt nichts über Module, Klassen oder Dateien.

```text
  Interaction      spiegelt Eingabe, Vorschau, Hover, Pfade
       │           (nutzt Correspondence + Plane; darf nichts Eigenes „wissen")
       ▼
  Operation        führt Absicht + Spiegelabsicht als EINE Handlung aus
       │           (liefert Ergebnis beider Seiten; erklärt ihren Unterstützungsgrad)
       ▼
  Correspondence   leitet Partner für den aktuellen Zustand ab
       │           (gepaart / selbst-gepaart / ungepaart / mehrdeutig → State)
       ▼
  Definition       vom Artist erklärt: Plane + Seam + Geltungsbereich
                   (einziger dauerhafter Zustand)
```

**Leserichtung:**
- **Nach unten** wird *benutzt*: Die Interaction fragt die Correspondence, die Correspondence liest die Definition.
- **Nach oben** wird *gemeldet*: Ein ungültiger Zustand unten (mehrdeutig, Seam verletzt) muss oben sichtbar werden, spätestens in der Interaction.
- **Dauerhaft** ist nur die unterste Ebene. Alles darüber ist ein Ergebnis der Ebene darunter plus des aktuellen Netzes.

**Die Kernspannung, die dieser Layer offen benennt:** INV-3 sagt „Partner sind ableitbar". INV-6 sagt „die Gegenseite entsteht aus der Absicht, nicht aus einer Suche". Beides zusammen heißt: Die Operation erzeugt beide Seiten deterministisch, und die anschließende Ableitung **bestätigt** die Symmetrie, statt sie zu erfinden. Weicht die Bestätigung vom Erwarteten ab, ist das ein meldepflichtiger Zustand und keine neue Wahrheit.

---

## 5. Szenarien — was muss wahr sein?

Jede Zeile beschreibt die erwartete Semantik für Artist und System, nicht die Umsetzung.

| Szenario | Was muss wahr sein? |
|---|---|
| **Normales Editieren einer Hälfte** (Move/Rotate/Scale/Tweak) | Jedes gepaarte Element bewegt sich gespiegelt mit. Selbst-gepaarte (Seam-)Elemente bleiben auf der Plane. Ungepaarte Elemente bewegen sich nur selbst, und das ist erkennbar. |
| **Extrude** | Beide Seiten erhalten das gespiegelte Extrude als eine Handlung. Grenzt die Auswahl an die Seam, entsteht keine Innenwand auf der Mitte, und die Seam verläuft danach eindeutig (vgl. R1 §3.5 Wings, R2 §3.1 Blender). |
| **Bevel** | Gespiegeltes Ergebnis beidseitig. Berührt das Bevel die Seam selbst, ist das Ergebnis entweder eindeutig definiert (die Seam bleibt eine gültige Seam) oder vor der Ausführung als nicht unterstützt erkennbar. |
| **Inset** | Wie Extrude. Ein Inset einer Fläche, die über der Seam liegt, ist ein Seam-Fall mit definiertem Ergebnis oder erkennbar nicht unterstützt. |
| **Loop Insert** | Die Vorschau zeigt beide Loops *vor* dem Bestätigen. Ein Loop, der die Plane kreuzt, ist sein eigenes Gegenstück (ein Loop, nicht zwei). Ein Loop *auf* der Seam ist ein definierter Sonderfall. |
| **Connect** | Gespiegelte Verbindungen beidseitig. Eine Verbindung, deren Spiegelbild sie selbst ist (über die Mitte), entsteht genau einmal. Wird die Seam berührt, ist die neue Seam eindeutig oder der Vorgang erkennbar nicht symmetrisch. |
| **Knife** | Der Schnittpfad wird *während* des Zeichnens gespiegelt sichtbar. Schnittpunkte auf der Seam sind eindeutig definiert. Kann der gespiegelte Pfad nicht eindeutig abgebildet werden, erfährt der Artist das vor dem Bestätigen. |
| **Delete** | Löschen auf einer Seite löscht das Gegenstück mit. Löschen von Seam-Elementen verändert die Definition: Entweder bleibt eine eindeutige Seam übrig, oder der State wechselt erkennbar. |
| **Merge/Weld** | Gespiegelt beidseitig. Merge über die Mitte (zwei Partner zu einem Seam-Element) ist eine legitime, definierte Operation. Merge, das Partner zerstört, führt erkennbar zu „teilweise". |
| **Verschieben von Seam-Elementen** | Seam-Elemente bewegen sich nur innerhalb der Plane — oder der Artist löst sie bewusst aus der Seam. Ein Seam-Element neben der Plane ist nie ein stiller Zustand (INV-2). |
| **Topologieänderung, die Symmetrie eindeutig erhält** | Nach der Operation ist der State wieder „gültig", ohne Zutun des Artists. Die Ableitung bestätigt, was die Operation erzeugt hat. |
| **Topologieänderung, die Symmetrie mehrdeutig macht** | Der State wird erkennbar „mehrdeutig" oder „teilweise". Mehrdeutige Elemente werden nicht gespiegelt. Der Artist sieht, wo. |
| **Absichtliches Brechen der Symmetrie** | Möglich ohne Umwege (Symmetrie aus, einseitig arbeiten). Beim Wiedereinschalten zeigt das System den tatsächlichen Zustand und behauptet keine Symmetrie, die nicht mehr besteht. |
| **Wiederherstellung / Re-Symmetrize** | Eine bewusste, gerichtete Handlung mit erkennbarer Quellseite. Vorher ist sichtbar, was sich ändern wird. Eine Variante, die Topologie und Reihenfolge des Netzes erhält, ist als Bedarf festgehalten (R1 §7 Punkt 6), aber nicht zugesagt. |

---

## 6. Abgleich mit der Research

| Anforderung | Research-Befund | Bewertung |
|---|---|---|
| INV-1 deklarierte Seam | R1 §4 M-E, R2 §7: Maya Seam-Edge, C4D-Tag, Modo Selection Set, Wings Naht-Fläche | **Gestützt.** Alle stabilen Systeme deklarieren die Naht. |
| INV-3 Korrespondenz ableitbar | R2 §1, §7: kein System pflegt Partner-Tabellen durch Operationen | **Gestützt.** Das ist der Branchenweg, nicht nur eine Wunschvorstellung. |
| INV-4 Definition überlebt | R2 §3.2 Wings (Naht-Pflege von Hand pro Operation), §3.3 Maya (Naht-Änderung → Symmetrie aus) | **Gestützt, aber als Schwachstelle.** Genau hier investieren oder scheitern die Systeme. |
| INV-6 deterministisch statt erraten | R2 §2 (Maya/C4D spiegeln die Auswahl vor der Operation), §5 (Partner nie zum Entstehungszeitpunkt vergeben) | **Teilweise gestützt.** Die Systeme erzeugen beide Seiten gemeinsam, erkennen sie danach aber per Suche wieder. Mirai würde hier etwas strenger formulieren als die gefundenen Systeme. |
| INV-5 / INV-8 keine stille Falschheit | R2 §6: nur C4D macht Nicht-Unterstützung vorab sichtbar; Maya/Blender/Modo laufen still einseitig; Wings schaltet still ab | **Strenger als die Research.** Die meisten Systeme erfüllen das nicht. Das ist eine bewusste Mirai-Anforderung, keine Nachahmung. |
| INV-9 keine Tool-eigene Mirror-Logik | R2 §3.2 Wings, R2 §4 (Tool-Abdeckung als Dauerbaustelle, C4D-Fixliste) | **Gestützt als Warnung.** |
| INV-11 symmetrische Interaktion | R2 §4: pfad- und cursorbasierte Tools sind die häufigsten Bruchstellen; Maya sperrt den Cut-Start auf der Naht | **Gestützt.** Interaktion ist die eigentliche Lücke. |
| INV-10 teilweise Symmetrie | R2 §6: Maya und C4D, partiell | **Gestützt.** |
| INV-12 bewusste Wiederherstellung | R1 §3.1 / §3.2 (Symmetrize, Symmetry Tools), R1 §7 Punkt 6 (Erhalt der Reihenfolge fehlt) | **Gestützt.** Der Erhalt der Reihenfolge bleibt offen. |

**Beobachtung aus dem Mirai-Repo selbst [FAKT]:** Commit `24ff921` (WP-STAB-12, 2026-09-24): Extrude und Knife hatten vergessen, einen abgeleiteten Cache nach Commit/Cancel neu zu berechnen. Die Folge war ein Absturz beim nächsten Tweak. Das spiegelt denselben Fix für Loop-Insert/Split/Collapse/Connect (WP-STAB-07).
- **[INTERPRETATION]** Das ist dieselbe Fehlerklasse, die R2 §3.2 bei Wings beschreibt: Pflege, die jede Operation einzeln leisten muss, wird irgendwann vergessen. Für INV-4 und INV-9 ist das ein konkreter Hinweis aus dem eigenen Code. Es ist kein Architekturargument für eine bestimmte Lösung, sondern ein **eingetretener Fehler** im Sinne von DEVELOPMENT_SYSTEM §8.

---

## 7. Einordnung

### Gesicherte Erkenntnisse (aus R1/R2 belegt)
- Stabile Systeme deklarieren die Naht.
- Partner werden abgeleitet, nicht mitgeschleppt.
- Pfad- und cursorbasierte Werkzeuge sind die häufigsten Bruchstellen.
- Stille Einseitigkeit ist in den meisten DCCs weiterhin Realität.
- Teilweise Symmetrie ist ein notwendiger Zustand.
- Das Toleranz-Dilemma ist nirgends gelöst, nur eingegrenzt.

### Design-Anforderungen (dieser Brief)
INV-1 bis INV-13 sowie die Szenario-Semantik in §5.

### Offene Fragen
- **Was löst den „mehrdeutig"-Zustand aus, und wie reagiert das System?** Symmetrie aus? Nur betroffene Elemente ausnehmen? Den Artist fragen? (Mehrere Reaktionen denkbar; eine muss definiert sein.)
- **Soll der Artist beide Seiten gleichberechtigt bearbeiten?** Oder gibt es während der Arbeit eine führende Seite? → Product-Truth-Frage, später M4.
- **Wie sichtbar ist „teilweise" im Alltag?** Permanente Anzeige oder nur bei Bedarf? → M4.
- **Welche Operationen müssen für eine erste nutzbare Symmetrie unterstützt sein?** → Priorität, Artist.
- **Mehrere Inseln, mehrere Planes, radiale Symmetrie:** gehören sie zum selben Begriffsmodell? → erst, wenn ein Use Case da ist.
- **Verhältnis zu ARCH-02 (Provenance):** Braucht INV-4 Provenance-Information aus Operationen oder nicht?
- **Wie verhält sich Seam-Schutz zu Tweak und Transform Space** (AD-012/AD-014, Tweak-Design)? Nur benannt, nicht untersucht.

### Bewusst NICHT entschieden
- Ob Mirai eine gespeicherte oder gecachte Korrespondenz hat, und wann sie neu aufgebaut wird.
- Ob symmetrische Operationen über gespiegelte Auswahl, gespiegelte Eingabe, Operation-Replay oder etwas anderes umgesetzt werden.
- Ob es zusätzlich einen Modus mit abgeleiteter Hälfte (Modifier/Virtual Mirror) gibt.
- Wie genau die Seam gespeichert und durch Operationen getragen wird.
- Konkrete Toleranzwerte oder ob Toleranzen überhaupt nötig sind.
- Welche Tools zuerst symmetrie-fähig werden.
- Jegliche Tastenbelegung, HUD- oder Anzeigeform.

---

## 8. Symmetry Design Principles für Mirai

1. **Der Artist erklärt Symmetrie — das System errät sie nicht.**
2. **Die Naht ist ein Ding, keine Koordinate.**
3. **Nur die Definition ist dauerhaft; Partner sind abgeleitet.**
4. **Die Gegenseite entsteht aus der Absicht, nicht aus einer Suche.**
5. **Richtig gespiegelt oder erkennbar nicht gespiegelt — nie still halb.**
6. **Teilweise Symmetrie ist ein ehrlicher Zustand, kein Fehler.**
7. **Gespiegelte Interaktion ist so wichtig wie gespiegelte Geometrie.**
8. **Symmetrie ist eine Fähigkeit des Systems, nicht jedes einzelnen Tools.**
9. **Asymmetrie ist erlaubt; Reparatur ist eine bewusste Handlung mit Richtung.**
