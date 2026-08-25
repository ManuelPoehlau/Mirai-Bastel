# Claude Review — V1 Core Architecture Draft 0.1

> **Reviewer:** Claude
> **Review ID:** CLAUDE-001
> **Reviewed document:** `docs/architecture/V1_CORE.md`
> **Status:** Archived first-pass review — preserved verbatim
>
> This document is intentionally preserved as the original first substantive review. Do not edit it to reflect later team decisions. Any assessment or response belongs in a separate document/commit.

---

## Original Review

Solide Grundstruktur, gute Trennung Core/UI. Hier die kritischen Punkte, geordnet nach Relevanz für zukünftige Sackgassen.

### 1. Fehlende Abstraktion: ID-Schema (Abschnitt 2.4)

Das Dokument sagt "stabile IDs" aber legt sich nicht auf ein Schema fest — das ist der teuerste Punkt zum Nachträglich-Ändern. Ein naiver Incrementing-Counter + Dict führt zu zwei Problemen:

Undo-Interaktion: Wird ein gelöschter Vertex beim Undo mit alter oder neuer ID wiederhergestellt? Das betrifft sofort History, Selection und Serialisierung.

Performance/Validity: Ohne Generation-Counter kann eine "tote" ID unbemerkt auf recycelten Speicher zeigen.

Empfehlung: Jetzt auf Generational Indices (ID = (slot_index, generation)) festlegen — Slotmap-Pattern, wie es moderne ECS-Systeme (Rust/Bevy) und aktuelle BMesh-Ansätze nutzen. Das ist O(1), erkennt invalide Referenzen und bleibt stabil über Undo/Redo. Retrofit später ist schmerzhaft, weil es Mesh, Selection, History und Serialisierung gleichzeitig anfasst.

### 2. Inkonsistenz: Domain-Modell vs. Topologie-Richtung (Abschnitt 3 vs. 4)

Abschnitt 3 zeigt Mesh -> Vertices/Edges/Faces als flache Struktur. Abschnitt 4 fordert aber Loop/Ring-Traversal und half-edge-artige Topologie — die braucht ein viertes Primitiv (Half-Edge/Loop), das Kanten pro Face repräsentiert. Ohne dieses Element sind Ring-Traversal, geordnete Face-Boundaries und saubere Euler-Operatoren nicht sauber machbar.

Empfehlung: Abschnitt 3 explizit offenlassen ("3 oder 4 Primitive, abhängig von Abschnitt 4") statt eine Struktur zu suggerieren, die die spätere Entscheidung vorwegnimmt.

### 3. Fehlende Abstraktion: Mutation-Layer zwischen Operations und Mesh (Abschnitt 2.3, 7)

Operation.apply(mesh, ...) klingt sauber, aber ohne eine explizite Schicht aus primitiven Euler-Operatoren (split_edge, collapse_edge, flip_edge, merge_vertex, ...) wird jede High-Level-Operation ihre eigene Topologie-Mutation neu erfinden. Das führt zu inkonsistenter Invarianten-Prüfung und macht "topology-safe editing" (dein eigenes Requirement in Abschnitt 4) faktisch unmöglich zu garantieren.

Empfehlung: Layer explizit machen:

Code

### 4. Fehlende Abstraktion: Interactive-Operation-Lifecycle

Das ist der größte konkrete Lückenpunkt. apply() als Einzelschritt passt für Extrude/Inset, aber nicht für Move/Tweak/Rotate mit Live-Drag über 60 Mausereignisse. Zwei Fallen drohen, wenn das jetzt nicht entschieden wird:

Naive Umsetzung feuert 60 History-Einträge pro Drag.

Naive Umsetzung feuert 60 volle Change-Events pro Frame → Viewport-Performance bricht ein.

Empfehlung: Operation-Lifecycle jetzt konzipieren, nicht erst bei Undo-Kapitel (11) implizit lassen:

Code

Das ist eine fundamentale Interaktions-Abstraktion, keine Detailfrage — sie bestimmt, wie Tweak/Move/Soft-Selection sich anfühlen.

### 5. Event-Batching fehlt (Abschnitt 12)

Direkt verwandt mit Punkt 4: Wenn eine Operation intern mehrere Mesh-Mutationen auslöst, sollte es eine Transaktionsgrenze geben ("Change-Batch"), damit UI/Renderer nicht pro Einzelmutation neu reagieren. Sonst bekommst du bei komplexeren Operationen (z. B. Inset mit Topologie-Split) N Events statt 1 zusammengefasstem MeshTopologyChanged.

### 6. Unentschiedener Status: Ist Selection undo-fähig? (Abschnitt 5 vs. 11)

Nicht spezifiziert, ob Selektionsänderungen im History-Stack landen. Die meisten 3D-Tools trennen das bewusst (separater, leichter Undo-Stack oder gar keiner), weil sonst jeder Klick einen Undo-Schritt frisst. Sollte in Abschnitt 19 als explizite offene Frage ergänzt werden — ist es momentan nicht.

### 7. Umfangs-Warnung: V1 ist bereits "Mini-Blender"

Abschnitt 2.1 will explizit kein Mini-Blender sein, aber die Summe der Anforderungen (generisches Extension-System, pluggable Falloff-Strategy-Interface, versionierte Serialisierung, Subdivision-Display-Layer, AI-Scripting-Surface, half-edge Topologie) ist in der Summe genau das. Diese Einzelanforderungen sind alle vernünftig, aber "generalisiert jetzt bauen" ist ein klassischer Architektur-Fallstrick.

Empfehlung: Rule-of-Three anwenden — Extension-Mechanismus und Serialisierungsformat bewusst primitiv für V1 bauen (z. B. Extensions = einfache Python-Module mit Registrierungsfunktion, kein Manifest/Discovery-System), und erst verallgemeinern, nachdem 3 echte Extensions existieren. Das reduziert das Risiko, eine falsche Abstraktion einzufrieren, bevor genug Anwendungsfälle bekannt sind.

### 8. Historische Anmerkung: Tweak ist keine "eine von vielen" Operationen

Bei Nendo/Mirai war Tweak/Soft-Selection das zentrale Interaktionsparadigma, nicht ein Tool neben anderen — die meisten Modellierschritte liefen über direkte Manipulation mit Magnet-Falloff, nicht über diskrete Operationen mit Parametern. Abschnitt 7 listet Tweak gleichrangig neben Move/Rotate/Scale. Das mag für V1 pragmatisch sein, aber falls "Mirai-Feeling" das eigentliche Ziel ist, verdient die Tweak-Interaktion eine privilegierte Position in Abschnitt 8 (Interaction Layer), nicht nur in der Operations-Liste.

### Ergänzungen zu Abschnitt 19 (offene Fragen)

Sollte ergänzt werden um:

13. ID-Schema: Generational Index vs. einfacher Counter?
14. Interactive-Operation-Lifecycle: begin/update/commit/cancel?
15. Ist Selektion Teil des Undo-Stacks?
16. Braucht Mesh ein viertes Primitiv (Loop/Half-Edge) neben V/E/F?

---

## Archive note

This file is the **unaltered first-pass review** supplied by Claude to the project team. The review has not been merged into `V1_CORE.md` at this stage. The team should evaluate each recommendation independently and record accepted/rejected/deferred decisions separately.
