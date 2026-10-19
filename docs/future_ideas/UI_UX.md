# Future Ideas – UI / UX

Ideen und Beobachtungen rund um UI / UX, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten. UI-Ideen sollen die bestehenden App-Werkzeuge sichtbar machen, nicht in Labs neu implementieren.

## Character Editing: Zustand klar sichtbar machen

Masken und gespeicherte Gesichtsregionen bringen nur dann einen echten Workflow-Gewinn, wenn der Artist jederzeit unterscheiden kann, was **ausgewählt**, was **maskiert** und was nur **ausgeblendet** ist.

Später untersuchen:

- eine gut lesbare Masken-Überlagerung mit klarer Möglichkeit, Maske zu invertieren, zu lockern und zu löschen,
- sichtbare Kennzeichnung der aktiven benannten Region/Selection Set,
- eindeutige Rückmeldung beim Isolieren und beim Wieder-Einblenden,
- Soft-Selection-Einfluss unabhängig von der eigentlichen Auswahl visualisieren,
- klare Warnung, wenn Masken, Symmetrie oder Topologiegrenzen eine Aktion einschränken.

Das sind UX-Anforderungen an die künftigen Modeling-Funktionen, keine eigene parallele Auswahl- oder Transform-Implementierung.

## Soft Selection: kleiner Curve-Shape-Editor mit der GUI (Idee, Manu S2c 2026-10-11)

**Status:** Bewusst zurückgestellt; wartet auf die GUI. Aus dem S2c-Verdikt (AD-020, „S2c verdict“): „später, wenn GUI dazukommt evtl. noch einen kleinen Curve-Shape-Editor, aber noch nicht jetzt.“

Heute formt `Ctrl`+Mausrad die Kurve `custom` (`t^p` auf einer festen Schrittliste, rund ↔ spitz), und `Shift+O` schaltet durch die Kurven Smooth, Sphere, Root, Sharp, Linear und Custom. Ein Editor wäre eine GUI-Fläche, in der man die Falloff-Kurve direkt sieht und formt, statt per Mausrad blind zu stufen.

**Next step:** erst bewerten, wenn es eine GUI-Schicht gibt. Bis dahin zählt, ob Mausrad-Stufen und die sechs Kurven in der Praxis reichen (Praxistest S2d).

## Morph-Gewicht bedienen

Der Gewichtungsregler für das Morph Lab ist ein offener Artist-Wunsch und steht im Lab-README als offen. Ein späterer Slider soll das Gewicht direkt ziehen lassen und den Viewport kontinuierlich aktualisieren. Die eigentliche Morph-Datenhaltung und das Verhalten mehrerer Targets gehören nach [ANIMATION.md](ANIMATION.md), nicht in eine zweite UI-Spezifikation.
