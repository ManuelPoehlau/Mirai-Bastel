# Future Ideas – Modeling

Ideen und Beobachtungen rund um Modeling, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten. Die Prioritäten unten sind ein Vorschlag für die weitere Discovery des Character-Workflows, keine beschlossene Roadmap und keine Implementierungszusage.

Mirais Ziel ist nicht nur, einzelne Topologieoperationen anzubieten. Ein Character-Modeller sollte schnell zwischen Formgebung, kontrollierter Auswahl, Topologiepflege und der Beurteilung der geglätteten Oberfläche wechseln können. Neue Werkzeuge sollen mit der vorhandenen Application, Selection, Soft Selection, Symmetry, History und Viewport-Infrastruktur zusammenarbeiten, statt diese in einem separaten Lab neu aufzubauen.

## Priorität 1 – Charaktere kontrolliert formen

### Relax und Smooth

Zwei getrennte Werkzeuge untersuchen:

- **Relax:** Punkt- und Kantenverteilung lokal verbessern, mit dem Ziel, den beabsichtigten Oberflächenverlauf möglichst gut zu erhalten.
- **Smooth:** Unebenheiten und harte Übergänge reduzieren. Bewusst prüfen, wann klassisches Glätten Volumen verliert oder Silhouette, Nase, Lippen und Augenlider unerwünscht abflacht.

Beide sollen die aktuelle Auswahl oder einen gezielten Bereich berücksichtigen, mit Strength/Iterations kontrollierbar sein und mit Symmetry, Maskierung sowie Undo zusammenarbeiten. Bei SubD-Charakteren muss das Ergebnis an der geglätteten Oberfläche beurteilt werden, nicht nur am Kontrollkäfig. Ob ein volumenbewahrendes Verfahren oder mehrere Varianten nötig sind, ist eine Forschungsfrage.

### Hide/Show Geometry und Isolate

Ein Mesh soll sich lokal leichter bearbeiten lassen:

- ausgewählte Geometrie ausblenden,
- nicht ausgewählte Geometrie isolieren,
- ausgeblendete Geometrie zuverlässig wieder einblenden.

Das ist **nicht** dasselbe wie den vorhandenen Reference/Ghost-Modus für andere Objekte. Hide/Show soll verdeckte oder störende Bereiche desselben Meshes aus dem Weg nehmen. Offene UX-Fragen: Verhalten von Auswahl und Picking, Wiederherstellung der Auswahl und Interaktion mit Topologieoperationen.

### Mask Geometry

Eine Maske schützt Bereiche vor Bearbeitung, ohne die eigentliche Auswahl ersetzen zu müssen. Das ist besonders wichtig bei großen Soft-Selection-Radien und beim Formen von Augenlidern, Lippen, Wangen und Kiefer.

Die Maske muss sichtbar und leicht zu ändern/aufzuheben sein. Zuerst den Scope untersuchen: nur Transform/Soft Selection oder später auch weitere Deformer und bestimmte Modellierwerkzeuge? Maskierung darf nicht stillschweigend die Topologie oder die Auswahl verändern.

### Gespeicherte Regionen / Polygroups

Benannte und wiederverwendbare Gesichtsbereiche untersuchen, etwa Brow, Upper Lip, Lower Lip, Eyelids und Jaw. Benötigte Aktionen: Region auswählen, Auswahl hinzufügen/entfernen, isolieren und gegebenenfalls maskieren.

Das soll kein zweites Selection-System werden. Zu klären ist, wie Regionen Mesh-Elemente referenzieren und wie sie sich bei Split, Collapse, Extrude, Remesh oder anderen Topologieänderungen verhalten. Bis diese Regeln klar sind, keine automatische Erhaltung versprechen. Details zu Auswahlaktionen und Navigation stehen in [SELECTION.md](SELECTION.md).

## Priorität 2 – Topologie-Werkzeuge, die den Character-Workflow schließen

Vor neuen Werkzeugen den Production-Integrationsstand prüfen: Eine Operation kann im Core vorhanden sein, ohne über den normalen App-Pfad verfügbar zu sein. Vorhandene Lab- oder Playground-Arbeit übernehmen, wenn sie bereits validiert wurde; nicht blind kopieren und nicht neu erfinden.

- **Collapse:** Production-Command/Integration prüfen und fehlende Verdrahtung abschließen. Nicht nur den Core-Primitive als „Tool vorhanden“ zählen.
- **Weld / Target Weld:** Vertices bzw. Kanten kontrolliert verbinden; Verhalten, Toleranz und Undo eindeutig machen.
- **Bridge und Close Holes/Gaps:** ausgewählte Randloops verbinden und geeignete Öffnungen schließen. Randanzahl, Reihenfolge, Richtung und nicht unterstützte Fälle klar behandeln.
- **Edge- und Vertex-Extrude:** gezielte lokale Topologie aufbauen, wo Face-Extrude nicht die passende Absicht ausdrückt.
- **Bevel/Chamfer:** bestehende Bevel-Fähigkeit und ihre tatsächliche Production-Abdeckung auditieren; später gezielt Edge-/Vertex-Bevel ergänzen, falls der Character-Workflow es verlangt.
- **Set Flow / Loop Flow:** untersuchen, wie eine Folge bestehender Kanten zwischen angrenzenden Loops gleichmäßiger oder gezielter verteilt werden kann.
- **Spin Edge / Spin Vertex:** nützliches ergänzendes Topologie-Werkzeug, aber hinter Relax, Maskierung, Loop-Navigation und den Reparaturoperationen priorisieren.

Die Loop-/Ring-Erkennung und -Auswahl ist bereits vorhanden. Die nächsten Ideen dazu liegen in [SELECTION.md](SELECTION.md): Grow/Shrink, Loop-Extend und Navigation zum nächsten parallelen Loop. Das ist eine Erweiterung der bestehenden Fähigkeiten, kein Neubau.

## Priorität 3 – Formkontrolle und Character-Workflow

- **SubD-Käfig und Oberfläche gemeinsam beurteilen:** die Kontrolltopologie muss gut sichtbar bleiben, während die geglättete Form für Silhouette und Volumenbeurteilung im Blick ist. Vorhandene SubD-App-/Lab-Fähigkeiten weiterverwenden und echte offene Lücken ergänzen.
- **Symmetrie als durchgängiger Workflow:** Symmetrie soll zu Formgebung und unterstützten Topologieoperationen passen. Seams, unpaarige Elemente und Ablehnungen müssen nachvollziehbar bleiben; asymmetrische Korrekturen sollen bewusst möglich sein.
- **Gezielte Formvergleiche:** Basisform und geänderte Form schnell A/B vergleichen können, ohne dass Arbeitszustand, Auswahl oder Kamera ungewollt verloren gehen.
- **Morphs und Ausdrucksformen:** persistente Targets, Gewichtung und Ausdrucks-Bibliotheken gehören zur zusammenhängenden Character-Pipeline; siehe [ANIMATION.md](ANIMATION.md). Topologieabhängigkeiten müssen ausdrücklich behandelt werden.

## Später / explorativ

### Mesh aus Bones erzeugen

Schneller Weg zu einem posebaren, editierbaren Mannequin: eine einfache humanoide Knochenstruktur aufbauen und darum ein Mesh erzeugen. Mögliche Ergebnisse: normales Mesh oder direkt rigged/skinned Mesh. Ähnlich der ZSphere-Idee. Das ist eine größere Funktion und keine Voraussetzung für den aktuellen Character-Modeller.

### Knife-Erweiterungen

- **Cut Through:** optional auch verdeckte Flächen schneiden, analog zu Blenders Cut Through. Manu, 2026-09-29: eventuell später als zusätzlicher Modus. Siehe [KNIFE_CROSS_FACE_DISCOVERY.md §1.1](../research/topology/KNIFE_CROSS_FACE_DISCOVERY.md).
- **Start im leeren Raum:** von Manu am 2026-10-09 bewusst offen gelassen; später separat untersuchen. Siehe [Symmetry Knife Discovery §6, F6](../research/symmetry/SYMMETRY_KNIFE_DISCOVERY.md).
- **Winkelbeschränkung:** in WP-KNIFE-01 UX2 zunächst ausgelassen. Referenz Blender 2.79: Bildschirmraum-Snap auf 45°-Schritte mit Führungslinie. Offene Fragen sind Raumbezug und die Interaktion mit vorhandenen Snap-/Midpoint-Regeln. Siehe `playground/experiments/knife_face/decision.md`, „WP-KNIFE-01 UX2“.

## Grundsatz

Die Reihenfolge ist bewusst auf den tatsächlichen Artist-Workflow ausgerichtet: zuerst die bestehende Form kontrolliert bearbeiten, dann typische Topologie-Lücken schließen und erst danach seltenere Spezialwerkzeuge ausbauen. Änderungen am Core oder an Architekturgrenzen brauchen weiterhin ihre eigenen Reviews und Entscheidungen.
