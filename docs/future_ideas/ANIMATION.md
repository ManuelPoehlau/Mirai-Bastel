# Future Ideas – Animation

Ideen und Beobachtungen rund um Animation und Character-Formänderungen, die bewusst noch nicht als vollständiges Produktionssystem umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten. Das ist keine Animations-Roadmap.

## Morph Targets als Teil der Character-Pipeline

Das Morph Lab ist bereits ein Prototyp: Basis und Ziel können mit den normalen App-Werkzeugen geformt werden, und der Viewport zeigt ihre interpolierte Oberfläche. Es ist noch kein persistentes Morph-Target-System in Production. Aktuell sind das Ziel ein gewöhnliches Objekt, die Mischung ein abgeleiteter Viewport-Zustand und das Gewicht nicht dauerhaft als Morph-Daten gespeichert. Topologieinkompatibilität schaltet die Vorschau ab, statt eine ungültige Mischung zu zeigen. Der aktuelle Stand und offene Entscheidungen stehen in [Morph Lab README](../../experiments/morph_lab/README.md).

Für eine belastbare Character-Pipeline später untersuchen:

1. **Persistente, benannte Targets:** Ausdrucks- oder Formziele an einer Basis speichern, umbenennen, vergleichen und erneut öffnen können.
2. **Gewichte interaktiv bearbeiten:** der im Lab gewünschte Slider soll die Mischung live steuern; die UI-Idee steht in [UI_UX.md](UI_UX.md).
3. **Gezieltes Target-Shaping:** Basis und Ziel mit denselben Modeling-Werkzeugen bearbeiten können, dabei klar zeigen, welches Objekt bearbeitet wird und welche Form gerade angezeigt wird.
4. **Mehrere Targets:** erst nach dem robusten Einzel-Target untersuchen, wie mehrere Gewichte kombiniert werden, wie sie normiert werden und wie die Artist-Absicht sichtbar bleibt. Nicht als erstes ein komplexes Blendshape-Framework bauen.
5. **Topologie-Abhängigkeiten:** Topologieänderungen an Basis oder Ziel müssen erkannt werden. Später ist zu entscheiden, ob Mirai Änderungen übertragen, ein Target als inkompatibel markieren oder eine gezielte Reparatur/Remap-Funktion anbieten soll. Nie stillschweigend falsche Korrespondenzen verwenden.
6. **Ausdrucks-Bibliothek:** benannte, wiederverwendbare Gesichtsaktionen als gestaltbare Formen vergleichen und kombinieren können. FACS-/Action-Unit-orientierte Namen könnten als optionale Organisationshilfe dienen, ohne die Anatomie oder künstlerische Interpretation durch ein starres Schema vorzuschreiben.

## Reihenfolge

Zuerst ein persistentes, zuverlässig speicherbares Einzel-Target mit intuitivem Gewichtungsregler und verständlicher Fehleranzeige. Danach erst mehrere Targets und eine Ausdrucks-Bibliothek. Das hängt eng mit Mask Geometry und gespeicherten Gesichtsregionen zusammen; diese sind in [MODELING.md](MODELING.md) notiert.

## Nicht jetzt

- Kein umfassendes Animationssystem nur für das Morph Lab bauen.
- Kein automatisches Retargeting/Remapping von Morphs über beliebige Topologieänderungen versprechen.
- Rigging, Skinning, Deformer-Reihenfolge und Timeline bleiben eigenständige Themen und benötigen eigene Forschung/Entscheidungen.
