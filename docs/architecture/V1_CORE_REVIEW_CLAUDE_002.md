# Claude — Second Architecture Review

> **Source:** Claude
> **Review target:** `docs/architecture/V1_CORE.md`
> **Review type:** Second architecture consideration / classification
> **Status:** Original response archived verbatim

Zweite Architekturbetrachtung — Klassifikation
1. Generational IDs / Slotmap — A
Relevanz: Jede stabile Referenz im System (Selection-Sets, History-Diffs, Serialisierung, Scripting-API) hängt an diesem Schema.
Gefahr bei falscher/fehlender Entscheidung: Retrofit betrifft alle Subsysteme gleichzeitig, nicht nur Mesh — das ist der teuerste denkbare nachträgliche Umbau im gesamten Dokument.
Kleinstmögliche V1-Lösung: ID = (slot_index, generation) als Typ jetzt festlegen, dahinter simple Array/Dict-Container. Kein vollständiges ECS nötig.
Explizit NICHT bauen: generisches ECS-Framework, Multithreaded-Arena-Allocator, Component-System-Generalisierung.
Irreversibilität: Höchste im gesamten Set. Muss vor der ersten Zeile Mesh-Code stehen.
2. Half-Edge/Loop als Topologie-Primitiv — A (konzeptuell) / C (Implementierungstiefe)
Relevanz: Bestimmt, ob Face-Boundaries als geordnete Loops oder ungeordnete Edge-Sets modelliert werden — das ist eine Struktur-, keine Optimierungsfrage.
Gefahr: Wird jetzt eine ungeordnete V/E/F-Struktur gebaut, müssen später alle Operatoren, die Face-Grenzen berühren, umgeschrieben werden, sobald Ring-Traversal gebraucht wird.
Kleinstmögliche V1-Lösung: Nur die Repräsentationsentscheidung jetzt treffen — Face-Boundary ist eine geordnete Liste von Edge-IDs, nicht ein Set. Volle Winged-Edge/Radial-Edge-Mechanik ist NICHT nötig.
Explizit NICHT bauen: vollständige Winged-Edge-Struktur mit radialen Zyklen, Quad-Edge-Struktur, Non-Manifold-Multi-Shell-Unterstützung.
Irreversibilität: Hoch auf konzeptueller Ebene (Datenlayout), niedrig auf Implementierungsebene (Details austauschbar, solange Adjacency-Queries als API stabil bleiben).
3. Euler-/Mutation-Layer — A
Relevanz: Einzige Garantiestelle für "topology-safe editing" — ohne sie ist dieses selbstgesetzte Requirement aus Abschnitt 4 nicht einlösbar.
Gefahr: Ohne diese Schicht mutiert jede Operation Mesh-Internals direkt → Invarianten-Verletzungen, Code-Duplikation. Retrofit bedeutet: jede bereits existierende Operation umschreiben.
Kleinstmögliche V1-Lösung: Handvoll primitive Funktionen (add_vertex, split_edge, collapse_edge, connect_verts, add_face, remove_face) als einzig sanktionierter Mutationsweg.
Explizit NICHT bauen: formale Euler-Operator-Algebra mit Genus-Tracking, Non-Manifold-Handling.
Irreversibilität: Hoch, aber kleiner Blast-Radius als Punkt 1 — betrifft "nur" Operations-Schicht, nicht Selection/Serialisierung/Scripting direkt.
4. Interactive Operation Lifecycle — A
Relevanz: Bestimmt, wie Move/Tweak/Rotate als Live-Drag funktionieren, ohne History und Events zu fluten.
Gefahr: Wird apply() als Single-Shot-Contract etabliert, muss beim Nachrüsten jede existierende Operation und jeder Interaction-Layer-Call-Site angepasst werden — Interface-Bruch mit maximaler Verbreitung im Code.
Kleinstmögliche V1-Lösung: Vier-Phasen-Contract (begin/update/commit/cancel) jetzt als Operation-Basisinterface, auch wenn V1 nur Move damit implementiert. Single-Click-Operationen (Extrude) rufen einfach begin→update(1×)→commit.
Explizit NICHT bauen: Operation-Graph, prädiktive/asynchrone Pipelines, OT/CRDT für Kollaboration.
Irreversibilität: Sehr hoch — Interface-Verträge sind teuer zu ändern, sobald mehrere Operationen darauf aufbauen. Vor der ersten Operation entscheiden.
5. Change Batching — B
Relevanz: Verhindert Event-Sturm bei Multi-Mutation-Operationen.
Gefahr bei Verzögerung: Gering — reiner Performance-/Sauberkeitsaspekt, kein struktureller Blocker. Führt im schlimmsten Fall zu Frame-Drops in Demos, nicht zu Architekturbruch.
Kleinstmögliche V1-Lösung: Ergibt sich fast automatisch aus Punkt 3+4: begin_batch()/end_batch() um die Spanne zwischen begin() und commit() legen, Events erst am Ende coalescen.
Explizit NICHT bauen: differenzielle/patch-basierte Event-Payloads, deferred Rendering-Pipeline.
Irreversibilität: Niedrig — kann nachgerüstet werden, solange Mutation durch einen einzigen Trichter läuft (was Punkt 3 ohnehin sicherstellt).
6. Selection + Undo — B
Relevanz: Bestimmt Undo-Granularität und UX-Gefühl.
Gefahr: Mild — falscher Default nervt UX-technisch, ist aber kein Strukturbruch, da Selection (Abschnitt 5) bereits als eigenständiges Domain-Objekt getrennt von Mesh modelliert ist.
Kleinstmögliche V1-Lösung: Selektionsänderungen für V1 bewusst NICHT im Haupt-History-Stack führen (üblicher Default in vergleichbaren Tools).
Explizit NICHT bauen: dedizierter Selection-History-Stack, Selection-Undo-Scripting-Hooks.
Irreversibilität: Niedrig — Selection ist architektonisch bereits isoliert, spätere Änderung berührt kaum andere Systeme.
7. Gefahr der Überarchitektur / Rule of Three — C
Relevanz: Schützt davor, falsche Abstraktionen (Extension-API, Serialisierungsformat, Falloff-Strategy-Interface) einzufrieren, bevor genug reale Anwendungsfälle existieren.
Gefahr bei Ignorieren (hier: Gefahr des zu früh Verallgemeinerns): Verschwendeter Aufwand, falsche Abstraktion blockiert spätere Iteration stärker als gar keine.
Kleinstmögliche V1-Lösung: Extensions = einfache registrierte Funktionen/Module ohne Manifest; Serialisierung = simples JSON ohne Migrationsmaschinerie; Falloff = eine hartkodierte Funktion, kein Interface.
Explizit NICHT bauen: generisches Plugin-Discovery-System, versioniertes Migrations-Framework, Strategy-Pattern mit nur einer Implementierung.
Kein technischer Irreversibilitätsfall — Prozess-/Meta-Prinzip, bewusst offenlassen bis 3 echte Extensions bzw. 2–3 Falloff-Varianten existieren.
8. Tweak als zentrales Interaktionsparadigma — C
Relevanz: UX-Gewichtung, keine Strukturfrage — sofern Punkt 4 (Lifecycle) und Abschnitt 6 (Influence) sauber stehen, ist Tweak einfach "eine Operation, die den interaktiven Lifecycle + Influence-Map nutzt".
Gefahr bei Offenlassen: Keine strukturelle — nur ein Gestaltungsrisiko im Interaction-Mapping (Abschnitt 8), jederzeit nachjustierbar.
Kleinstmögliche V1-Lösung: Tweak als normale Operation über den in Punkt 4 definierten Lifecycle implementieren, keine separate TweakMode-Subsystem-Logik.
Explizit NICHT bauen: dedizierte Tweak-State-Machine, spezialisierter Rendering-Pfad.
Bewusst spät entscheidbar, da es aus bereits fixierten Punkten (4, 6) kompositional folgt.
Irreversibilitäts-Ranking (Punkte 1–5, teuerste zuerst)
Rang
Punkt
Warum so teuer/günstig
1
ID-Schema (1)
Blast-Radius = gesamtes System (Mesh, Selection, History, Serialisierung, Scripting)
2
Interactive Lifecycle (4)
Interface-Vertrag, den jede zukünftige Operation + jeder Interaction-Call-Site nutzt
3
Mutation-Layer (3)
Interface-Vertrag, aber Blast-Radius auf Operations-Schicht begrenzt
4
Half-Edge/Loop-Konzept (2)
Teuer auf Datenlayout-Ebene, aber isolierbar hinter stabiler Adjacency-API
5
Change Batching (5)
Reines Wrapping um bestehenden Mutationstrichter — jederzeit nachrüstbar
Kernaussage: Punkte 1, 3 und 4 sind die einzigen echten "jetzt-oder-teuer"-Entscheidungen. Punkt 2 ist nur auf konzeptueller Ebene jetzt zu klären (nicht implementieren). Punkte 5, 6 sind pragmatisch mit einem einfachen Default lösbar. Punkte 7, 8 sind bewusst vertagbar und sollten es auch bleiben, um Überarchitektur zu vermeiden.