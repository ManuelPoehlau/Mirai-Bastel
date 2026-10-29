# Future Ideas – Modeling

Ideen und Beobachtungen rund um Modeling, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten. Die Prioritäten unten sind ein Vorschlag für die weitere Discovery des Character-Workflows, keine beschlossene Roadmap und keine Implementierungszusage.

Mirais Ziel ist nicht nur, einzelne Topologieoperationen anzubieten. Ein Character-Modeller sollte schnell zwischen Formgebung, kontrollierter Auswahl, Topologiepflege und der Beurteilung der geglätteten Oberfläche wechseln können. Neue Werkzeuge sollen mit der vorhandenen Application, Selection, Soft Selection, Symmetry, History und Viewport-Infrastruktur zusammenarbeiten, statt diese in einem separaten Lab neu aufzubauen.

## Priorität 1 – Charaktere kontrolliert formen

### Relax und Smooth

> Gebaut (2026-10-23): [WP_TOOLBOX_GAPS_PLAN.md](../WP_TOOLBOX_GAPS_PLAN.md) C2 — `S` = Smooth, `Alt+S` = Relax
> (antippen = ein Schritt, halten + ziehen = Stärke live). Volumenerhalt bleibt offen.

Zwei getrennte Werkzeuge untersuchen:

- **Relax:** Punkt- und Kantenverteilung lokal verbessern, mit dem Ziel, den beabsichtigten Oberflächenverlauf möglichst gut zu erhalten.
- **Smooth:** Unebenheiten und harte Übergänge reduzieren. Bewusst prüfen, wann klassisches Glätten Volumen verliert oder Silhouette, Nase, Lippen und Augenlider unerwünscht abflacht.

Beide sollen die aktuelle Auswahl oder einen gezielten Bereich berücksichtigen, mit Strength/Iterations kontrollierbar sein und mit Symmetry, Maskierung sowie Undo zusammenarbeiten. Bei SubD-Charakteren muss das Ergebnis an der geglätteten Oberfläche beurteilt werden, nicht nur am Kontrollkäfig. Ob ein volumenbewahrendes Verfahren oder mehrere Varianten nötig sind, ist eine Forschungsfrage.

### Hide/Show Geometry und Isolate

> Gebaut (2026-10-25, `PROVISIONAL`, `src/mirai/hidden.py`): `Ctrl+H` versteckt die Auswahl (Spiegelpartner mit),
> `Ctrl+Shift+H` isoliert sie (alles andere versteckt), `Alt+H` zeigt alles. Versteckt werden Vertices; eine Face oder
> Kante ist versteckt, sobald eine Ecke es ist (neue Topologie bleibt dadurch konsistent). Versteckte Geometrie wird
> nicht gezeichnet (degenerierte Dreiecke im Index-Buffer, Shading, Tiefe und GPU-Face-ID-Pass sehen dasselbe), nicht
> gepickt (GPU und CPU, Box/Lasso) und verdeckt nichts; die SubD-Fläche und ihre Käfig-/Isolinien blenden die Teile
> versteckter Käfig-Faces aus. Die Auswahl enthält nie Verstecktes (Hide nimmt es heraus, Grow/Shrink/Loop wählen es nicht
> an). Transformationen, Soft Selection und Smooth/Relax behandeln Verstecktes wie voll maskiert. Topologie-Befehle
> (Connect, Knife, Collapse, Delete/Dissolve, Extrude, Loop Insert/Slide, Re-Symmetrize) neben verstecktem werden
> abgelehnt („hidden geometry in the way“). Der Zustand ist flüchtig wie die Maske (kein History-Eintrag, nicht in
> Szenendateien, pro Edit-Objekt, beim Szenenwechsel geleert). Mit dem Objektwechsel behält jetzt auch die Maske ihren
> Zustand pro Objekt (vorher leakte sie). Offen: Speichern in Szenendateien, Hide für weitere Objekte gleichzeitig,
> Verhalten von Shrink an der Grenze zu Verstecktem.

Ein Mesh soll sich lokal leichter bearbeiten lassen:

- ausgewählte Geometrie ausblenden,
- nicht ausgewählte Geometrie isolieren,
- ausgeblendete Geometrie zuverlässig wieder einblenden.

Das ist **nicht** dasselbe wie den vorhandenen Reference/Ghost-Modus für andere Objekte. Hide/Show soll verdeckte oder störende Bereiche desselben Meshes aus dem Weg nehmen. Offene UX-Fragen: Verhalten von Auswahl und Picking, Wiederherstellung der Auswahl und Interaktion mit Topologieoperationen.

### Mask Geometry

> Gebaut (2026-10-25, `PROVISIONAL`, `src/mirai/mask.py`, `src/mirai/mask_display.py`): `Ctrl+M` maskiert die Auswahl
> (bei vollständig maskierter Auswahl hebt es die Maske auf; entscheidend ist die Auswahl selbst, nicht ihre Spiegelpartner — Fix 2026-10-25: eine vor dem Einschalten der Symmetrie maskierte Seite wurde sonst gespiegelt nachmaskiert statt freigegeben), `Ctrl+Shift+M` invertiert, `Alt+Shift+M` löscht.
> Scope: Move/Rotate/Scale (plain und Soft) sowie Smooth/Relax; ein voll maskierter Vertex bewegt sich nie, ein
> teilmaskierter dämpft das Soft-Gewicht mit `w * (1 - m)` (Seeds behalten 1.0). Unter Symmetrie wirkt pro
> Spiegelpaar das Maximum. Die Maske ist Schutzzustand, kein Mesh-Datum: kein History-Eintrag (Undo macht sie nicht
> rückgängig), keine Auswahl-/Topologieänderung, beim Szenenwechsel geleert, schwarze Punkte im Viewport.
> Offen: Pinsel/Malen und weiche Werte per UI, Maske für weitere Werkzeuge (Extrude, Knife, Loop Slide), Erhalt über
> Topologieänderungen (neue Vertices starten unmaskiert), Speichern in Szenendateien.

Eine Maske schützt Bereiche vor Bearbeitung, ohne die eigentliche Auswahl ersetzen zu müssen. Das ist besonders wichtig bei großen Soft-Selection-Radien und beim Formen von Augenlidern, Lippen, Wangen und Kiefer.

Die Maske muss sichtbar und leicht zu ändern/aufzuheben sein. Zuerst den Scope untersuchen: nur Transform/Soft Selection oder später auch weitere Deformer und bestimmte Modellierwerkzeuge? Maskierung darf nicht stillschweigend die Topologie oder die Auswahl verändern.

### Gespeicherte Regionen / Polygroups

> Gebaut (2026-10-25, `PROVISIONAL`, [AD-REGIONS-01](../architecture/AD-REGIONS-01-FACE-REGIONS-STORAGE.md),
> `src/mirai/regions.py`, Core: `Mesh.face_regions`): Regionen sind benannte, auch überlappende Face-Mengen **im Mesh**
> (Undo/Redo, Knife-Rollback und Szenendatei kommen mit; additiver Schlüssel `"face_regions"`). Die App hat keine
> Texteingabe. **Erst gruppieren, dann benennen (Manu 2026-10-25):** `Ctrl+G` macht die Faces der Auswahl (alle Ecken
> ausgewählt; unter Symmetrie mit den Spiegelpartnern) zu einer **neuen** Gruppe `Group N` und überschreibt nie eine andere;
> eine Face gehört zu einer Gruppe (sie verlässt ihre alte, eine leer gewordene Gruppe verschwindet), die neue Gruppe wird
> aktiv. `Shift+G` / `Shift+Alt+G` wechseln durch die vorhandenen Gruppen, `Ctrl+Alt+N` speichert die aktive Gruppe als
> benanntes Set (Brow, Upper Lip, Lower Lip, Eyelids, Jaw; erneut = nächster freier Name, danach zurück zu `Group N`),
> `Ctrl+Shift+G` fügt hinzu, `Ctrl+Alt+G` entfernt, `Alt+G` wählt die Gruppe im aktiven Modus aus (`Ctrl+Alt+Shift+G` zur
> Auswahl hinzu, nie Verstecktes), `Ctrl+Alt+H` isoliert, `Ctrl+Alt+M` maskiert sie (beides die ganze Gruppe, auch
> versteckte Teile), `Ctrl+Alt+Backspace` löscht sie. **Vererbung (Slice 3, 2026-10-25):** eine neue Face tritt einer Region bei, wenn alle ihre
> Eltern darin waren (Split, Connect, Loop Insert, Knife, Dissolve; Dissolve über eine Regionsgrenze erbt nicht; Extrude-
> Deckel und -Wände erben von der extrudierten Face), sonst keiner Region; Undo setzt Mesh und Regionen zusammen zurück
> (siehe AD-REGIONS-01 §1.6). **Farben:** jede Region hat eine eigene entsättigte Farbe auf ihren Faces (auch auf der SubD-
> Fläche), `Ctrl+Alt+D` blendet sie ein/aus (Standard an). **Shift+Ctrl+Klick** (ZBrush-artig, Manu 2026-10-25) nimmt die
> Gruppen unter dem Cursor (Vertex/Edge im Vertex-/Edge-Modus: alle Gruppen, die er berührt): Ist nichts versteckt, werden sie
> isoliert; sind nur sie sichtbar, kehrt sich die Sichtbarkeit um (Rest sichtbar, sie versteckt); ist schon etwas anderes
> versteckt, werden sie zusätzlich versteckt. Ins Leere zeigt alles.
> **Mask by Polygroup** (`Ctrl+Alt+Shift+M`, Schalter, Standard aus, Manu 2026-10-25, ZBrush-artig): Solange an, wirken W/E/R
> (auch Soft), Smooth/Relax und die Soft-Vorschau nur auf die Gruppen der Auswahl (ohne Auswahl: des gehoverten Elements);
> alles außerhalb ist für diese Geste maskiert, die eigene Maske bleibt unberührt. Gruppen der Auswahl = die der Faces, die
> ganz in der Auswahl liegen, sonst aller berührten Faces (ein Rand-Vertex gibt beide Gruppen frei); Faces ohne Gruppe zählen
> als eine Gruppe; der Gruppenrand bleibt maskiert, außer er ist selbst ausgewählt (Soft endet am Rand). `mirai.regions.group_lock`.
> **Loops und Hide:** Loop Insert, Loop/Ring-Auswahl und die Loop-Schritte enden an versteckter Geometrie (z. B. Nase isolieren,
> dann Loop Insert schneidet nur die sichtbaren Quads); Loop Slide bleibt neben Verstecktem abgelehnt. Offen: Mirror-Copy-
> Remap, OBJ-Gruppen, Auswahl per Klick (ohne Isolieren), Umbenennen.

Benannte und wiederverwendbare Gesichtsbereiche untersuchen, etwa Brow, Upper Lip, Lower Lip, Eyelids und Jaw. Benötigte Aktionen: Region auswählen, Auswahl hinzufügen/entfernen, isolieren und gegebenenfalls maskieren.

Das soll kein zweites Selection-System werden. Zu klären ist, wie Regionen Mesh-Elemente referenzieren und wie sie sich bei Split, Collapse, Extrude, Remesh oder anderen Topologieänderungen verhalten. Bis diese Regeln klar sind, keine automatische Erhaltung versprechen. Details zu Auswahlaktionen und Navigation stehen in [SELECTION.md](SELECTION.md).

## Priorität 2 – Topologie-Werkzeuge, die den Character-Workflow schließen

Vor neuen Werkzeugen den Production-Integrationsstand prüfen: Eine Operation kann im Core vorhanden sein, ohne über den normalen App-Pfad verfügbar zu sein. Vorhandene Lab- oder Playground-Arbeit übernehmen, wenn sie bereits validiert wurde; nicht blind kopieren und nicht neu erfinden.

- **Collapse:** Production-Command/Integration prüfen und fehlende Verdrahtung abschließen. Nicht nur den Core-Primitive als „Tool vorhanden“ zählen.
  *Erledigt 2026-10-23:* [WP_TOOLBOX_GAPS_PLAN.md](../WP_TOOLBOX_GAPS_PLAN.md) B1 — Collapse V/E/F auf `Shift+C`
  (`core.operations.collapse`, `Application._collapse_command`, mit Symmetrie).
- **Weld / Target Weld:** Vertices bzw. Kanten kontrolliert verbinden; Verhalten, Toleranz und Undo eindeutig machen.
- **Bridge und Close Holes/Gaps:** ausgewählte Randloops verbinden und geeignete Öffnungen schließen. Randanzahl, Reihenfolge, Richtung und nicht unterstützte Fälle klar behandeln.
  *Close erledigt 2026-10-25:* Cap auf `Shift+B` ([WP_TOOLBOX_GAPS_PLAN.md](../WP_TOOLBOX_GAPS_PLAN.md), Nachtrag D); Bridge offen.
- **Edge- und Vertex-Extrude:** gezielte lokale Topologie aufbauen, wo Face-Extrude nicht die passende Absicht ausdrückt.
- **Bevel/Chamfer:** bestehende Bevel-Fähigkeit und ihre tatsächliche Production-Abdeckung auditieren; später gezielt Edge-/Vertex-Bevel ergänzen, falls der Character-Workflow es verlangt.
  *Grundfunktion gebaut 2026-10-29* (Manu: „Inset, Chamfer/Bevel, Slide (Vertices)“): Edge-/Vertex-Bevel mit einem
  Segment auf `Ctrl+B`, dazu Inset (`I` im Face-Modus) und Vertex Slide (`G` im Vertex-Modus) —
  [WP_INSET_BEVEL_SLIDE.md](../WP_INSET_BEVEL_SLIDE.md); Segmente, Profil, Inset-Tiefe offen.
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
- **Winkelbeschränkung:** in WP-KNIFE-01 UX2 zunächst ausgelassen. Referenz Blender 2.79: Bildschirmraum-Snap auf 45°-Schritte mit Führungslinie. Offene Fragen sind Raumbezug und die Interaktion mit vorhandenen Snap-/Midpoint-Regeln. Siehe `docs/research/topology/KNIFE_FACE_DECISIONS.md`, „WP-KNIFE-01 UX2“.

### Deformer / Modifier (Bend, Twist, Lattice o. ä.)

**Manu, 2026-10-21 (Chat, vom Agenten eingetragen):** ein Thema für später. Die einzige Vorarbeit ist die Articulation-Probe (EX-A,
„Bend Probe“, nicht für die App vorgesehen). Sie ist mit dem Playground am 2026-10-24 entfernt worden (Konsolidierung, Manus
Entscheidung): Code im Stand `61ebe77` unter `playground/experiments/articulation/` (dazu `deformation.Transform` aus
`experiments/rigging-skinning-morphing/`), Handoffs in [`archive/experiments_2026-10/playground/`](../archive/experiments_2026-10/playground/experiments/articulation/).
Ebenso dort: die Self-Shadowing-Studie `playground/shadow_map.py` (Tiefenkarte, Discovery; die App hat kein Schatten-Rendering).

### UVs, Baking und Split Normals (Retopo-Raum)

**Stand 2026-10-29:** UVs aus einer OBJ-Datei samt Textur importieren, anzeigen und beim Modellieren mitführen ist gebaut ([AD-026](../architecture/AD-026-FACE-CORNER-UVS-AND-TEXTURE.md)); UV-Editor, Texture Painting und Baking bleiben hier (Manu 2026-10-29: „brauche ich noch nicht“).

**Manu, 2026-10-20 (Chat, vom Agenten eingetragen):** UVs: ja. Split Normals: unsicher, ob nötig. Falls später im Retopo-Raum Displacements oder Normal Maps gebacken werden sollen, könnten sie nötig werden. Offene Fragen: ob harte Kanten als Kantenmarkierung genügen oder echte pro-Ecke-Normalen gebraucht werden, wo UV-Daten am Mesh wohnen (Ecken-Domäne, siehe [Audit 2](../research/viewport/ARCHITECTURE_AUDIT_2026-10-20_FUTURE_REQUIREMENTS.md) K2) und wie ein Bake auf dem Referenz-PC läuft (Strahlen auf die Quellfläche, Zielbild). Keine Implementierungszusage.

## Grundsatz

Die Reihenfolge ist bewusst auf den tatsächlichen Artist-Workflow ausgerichtet: zuerst die bestehende Form kontrolliert bearbeiten, dann typische Topologie-Lücken schließen und erst danach seltenere Spezialwerkzeuge ausbauen. Änderungen am Core oder an Architekturgrenzen brauchen weiterhin ihre eigenen Reviews und Entscheidungen.
