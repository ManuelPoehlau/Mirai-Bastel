# Research

`docs/research/` ist das **Forschungsarchiv** des Projekts. Hier sammeln und analysieren wir externe Quellen, historische Informationen, technische Rekonstruktionen, Experimente, Hypothesen und daraus abgeleitete Erkenntnisse.

Research ist ausführlich und darf sich mit einzelnen Systemen oder technischen Fragen tiefgehend beschäftigen.

## Abgrenzung zu `references/`

- `references/` = **kuratierter Wegweiser** zu externen Projekten, Original-Repositories, Dokumentationen und relevanten Bereichen. Kurz: *Was ist interessant und warum?*
- `docs/research/` = **unsere eigentliche Untersuchung**. Quellen auswerten, Fakten von Interpretation/Hypothese trennen, technische Zusammenhänge rekonstruieren und Konsequenzen für Mirai-Bastel festhalten.

Eine Reference-Datei sollte daher nicht die Research-Dokumentation duplizieren. Umgekehrt kann eine Research-Datei auf die passende Reference als Einstieg verweisen.

## Empfohlene Unterbereiche

- `mirai/` – Mirai, N-World, Izware, historische Versionen, Systemarchitektur und Workflow
- `bay-raitt/` – Bay Raitt, Demos, Interviews, Workflow
- `weta/` – Weta Digital, LOTR/Gollum und maßgeschneiderte Systeme
- `modelers/` – Wings 3D, Blender, Silo, Nendo und verwandte Modeler
- `subdivision/` – Catmull-Clark und verwandte Verfahren
- `topology/` – Winged Edge, Half Edge, Mesh-Datenstrukturen, Topologieoperationen
- `deformation/` – Skinning, Weight Maps, Morphs, Vertex Maps, nicht-destruktive Deformation und Attribute
- `papers/` – Papers, Patente und technische Spezifikationen

## Recherche-Regeln

Jede externe Quelle sollte möglichst mit URL, Datum, Quelle/Autor und einer kurzen Einordnung dokumentiert werden.

Wo sinnvoll, unterscheiden wir ausdrücklich zwischen:

- **FACT** – durch Quellen belegt
- **OBSERVED** – direkt beobachtetes Verhalten / getesteter Code
- **INTERPRETATION** – Schlussfolgerung aus den verfügbaren Informationen
- **HYPOTHESIS** – noch nicht ausreichend belegte Annahme

## Ziel

Wir wollen nicht eine einzelne Software kopieren. Wir wollen die **Erfahrungen mehrerer Generationen von 3D-Systemen** untersuchen und daraus fundierte Entscheidungen für Mirai-Bastel ableiten.

```text
Quellen / Referenzen
        ↓
   Research & Analyse
        ↓
 Fakten / Trade-offs / offene Fragen
        ↓
 Mirai-Bastel-Entscheidung
```

Besonders bei Core-, Topologie-, Attribut-, Deformations- und Workflow-Fragen sollen etablierte Lösungen, Randfälle und bekannte Trade-offs berücksichtigt werden, bevor wir eine eigene Lösung entwerfen.
