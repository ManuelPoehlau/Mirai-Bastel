## Mirai-Bastel — WP-04 / Core Architecture Reassessment

Wir befinden uns aktuell vor der eigentlichen WP-04-Implementierung.

Dein bisheriger Discovery Report und dein Gate-Plan wurden geprüft. Dabei ist eine Architekturfrage aufgekommen, die wir **vor Beginn der Production-Implementierung nochmals unabhängig untersuchen möchten**.

### Ausgangslage

`src/core` wurde nach der frühen Entwicklungs-/Experimentierphase bewusst als **Core V1 eingefroren**.

Dieser Freeze war eine Schutzmaßnahme gegen unkontrollierte Änderungen während der Research-Phase.

Mirai-Bastel entwickelt sich nun jedoch weiter:

```text
Experimente
    ↓
validierte Systeme
    ↓
Production Foundation
    ↓
brauchbarer Modeler
```

Daher stellt sich jetzt die grundsätzliche Frage:

> Ist es weiterhin sinnvoll, `src/core` unverändert zu lassen, oder ist der Zeitpunkt gekommen, Core V1 kontrolliert weiterzuentwickeln?

### Besonders wichtig

Deine frühere Empfehlung, `RotateOperation` und `ScaleOperation` nach `src/core` zu verschieben, ist **keine vorgegebene Entscheidung**.

Bitte analysiere diese Frage erneut und ergebnisoffen.

---

# Deine Aufgabe

Führe eine **Core Architecture Reassessment** anhand des tatsächlichen aktuellen Repository-Zustands durch.

Noch **keinen Code verändern**.

Noch **keine Commits**.

Noch **keine Core-Änderungen**.

## Untersuche mindestens:

### 1. Aktueller Core

Analysiere:

* `src/core`
* vorhandene APIs
* Mesh-/Topology-Datenstrukturen
* bestehende Transform-Funktionalität
* bestehende Operationen
* History-/Undo-/Redo-Unterstützung
* Tests
* Abhängigkeiten

Bewerte, wie stabil und ausgereift Core V1 tatsächlich ist.

### 2. WP-04-Anforderungen

Prüfe insbesondere:

* Move
* Rotate
* Scale
* Constraints
* Commit
* Cancel
* Undo
* Redo
* Selection
* Picking

Welche dieser Anforderungen sind bereits durch Core V1 abgedeckt?

Welche benötigen zusätzliche Fähigkeiten?

### 3. Production-vs-Core Boundary

Bewerte für Move/Rotate/Scale jeweils:

> Sollte die eigentliche Operation im Core liegen oder im Production Layer?

Begründe dies anhand der tatsächlichen Architektur, nicht nur anhand allgemeiner Software-Engineering-Prinzipien.

### 4. Core-Erweiterung

Falls Core erweitert werden sollte:

* Welche konkreten APIs/Operationen wären nötig?
* Wie klein könnte die Änderung gehalten werden?
* Welche bestehenden APIs könnten wiederverwendet werden?
* Welche Regressionen wären möglich?
* Welche Tests wären erforderlich?

Bitte **keinen allgemeinen „Core V2“-Umbau vorschlagen**, wenn er nicht notwendig ist.

### 5. Auswirkungen auf Experimente

Prüfe:

* Welche Experimente hängen vom aktuellen Core ab?
* Würden Änderungen kompatibel bleiben?
* Welche Regressionen wären zu erwarten?

### 6. Alternative

Vergleiche explizit:

**Option A**
Core V1 weiterhin vollständig einfrieren und Transform-Operationen außerhalb des Core integrieren.

**Option B**
Core kontrolliert erweitern und notwendige Transform-Operationen in den Core aufnehmen.

**Option C**
Falls sinnvoll: ein anderer Zwischenweg.

Bewerte jeweils:

* technisches Risiko
* Architekturqualität
* Wartbarkeit
* Wiederverwendbarkeit
* Produktionsnutzen
* Testaufwand
* Auswirkungen auf zukünftige WPs

### 7. Empfehlung

Gib am Ende eine klare Empfehlung:

```text
RECOMMENDATION:
A / B / C

WHY:
...

SCOPE:
...

RISKS:
...

REQUIRED TESTS:
...

IMPACT ON WP-04:
...
```

Wenn du der Meinung bist, dass Core jetzt kontrolliert erweitert werden sollte, beschreibe **die kleinstmögliche sinnvolle Erweiterung**.

Wenn du der Meinung bist, dass der Freeze weiterhin richtig ist, erkläre konkret, warum.

---

# Entscheidungsprinzip

Bitte nicht automatisch nach dem Prinzip handeln:

> „Core ist eingefroren, also darf Core nicht geändert werden.“

Der ursprüngliche Freeze ist eine Architekturentscheidung aus einer früheren Projektphase.

Wir wollen prüfen, ob diese Entscheidung für den **aktuellen Entwicklungsstand** noch angemessen ist.

Genauso wenig soll gelten:

> „Production braucht Rotate/Scale, also müssen sie in den Core.“

Die Entscheidung soll aus der tatsächlichen Architektur abgeleitet werden.

### Priorität

```text
Korrektheit
>
klare Architekturgrenzen
>
geringes Risiko
>
Wiederverwendbarkeit
>
Einfachheit
>
Eleganz
```

Und weiterhin gilt:

> Keine unnötige Architektur erfinden.

Bitte liefere ausschließlich den **Architecture Reassessment Report** und ändere noch keine Dateien.
