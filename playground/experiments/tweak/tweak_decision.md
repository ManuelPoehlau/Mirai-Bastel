# Tweak Lab — Artist Verdict

**Status:** OFFEN — noch nicht gespielt

---

## Forschungsfrage

Welche Aktivierungsgeste für Tweak ist bei häufiger Nutzung angenehmer —
eine gehaltene Tastatur-Taste oder Ctrl+Maustaste (mit früh loslassbarem Ctrl)?

**Fokus:** Activation (physische Ergonomie bei längerer Nutzung)
**Konstant gehalten (nicht Teil des Vergleichs):** Zielauflösung-Regel (siehe unten),
welcher Transform-Typ aktiv ist (Move/Rotate/Scale)

---

## Zielauflösung-Regel (für beide Varianten identisch)

Übernommen aus Silo, gilt für beide Varianten unverändert:

- **Selection vorhanden** → Tweak transformiert die komplette Selection.
  Der Press-Point muss nichts treffen — Tweak funktioniert überall auf dem Screen.
- **Keine Selection vorhanden** → Press-Point braucht einen Hit-Test-Treffer.
  Das getroffene Element wird temporäres Ziel, transformiert während des Drags,
  und wieder deselektiert bei Release.

Diese Regel ist bewusst in beiden Varianten identisch, damit ein Unterschied in der
Beobachtung eindeutig der Aktivierungsgeste zugeschrieben werden kann — nicht einer
Mischung aus Aktivierung und Zielauflösung.

---

## Struktur der Varianten

Die vier Varianten unten kreuzen zwei Achsen der Aktivierung:

|  | Ohne Klick (reines Hold+Drag) | Mit Klick (Click+Drag) |
|---|---|---|
| **Tool-spezifische Taste (X/R/S)** | Variante 1 | Variante 3 |
| **Generischer Modifier (Ctrl)** | Variante 4 | Variante 2 (Silo) |

Das erlaubt nach dem Spielen eine Zuordnung: Fühlen sich z.B. 1 und 4 ähnlich an,
aber 2 und 3 beide schwächer — dann liegt der Unterschied an der Klick-Komponente,
nicht an der gewählten Taste. Diese Struktur ist bewusst auf vier benannte Varianten
begrenzt, keine systematische Kombinationssuche.

---

## Varianten

### Variante 1 — Hold Key (kein Klick)

Press `X`/`R`/`S` = Key-Down → Key-Up ohne Drag dazwischen → Mode-Toggle
(persistenter Move/Rotate/Scale-Modus an/aus, siehe technische Voraussetzung
unten).

Passiert zwischen Key-Down und Key-Up eine Mausbewegung über dem
Click-Threshold (gleicher Mechanismus wie `_drag_moved`/`CLICK_THRESHOLD` in
`window.py`), wird die Geste rückwirkend zu **Tweak** statt zum Mode-Toggle:
Tweak mit dem entsprechenden Transform läuft, bis die Taste losgelassen wird
(Commit). ESC während des Drags = Cancel.

Die Geste entscheidet sich also selbst, je nachdem ob eine Bewegung dazwischenkommt
— keine Vorab-Festlegung "war das ein Tap oder ein Hold gemeint".

**Zu beobachten (potenzielle Probleme, absichtlich nicht vorab gelöst):**
- Führt ein leichtes Zittern beim Loslassen zu ungewollten Tweak-Aktivierungen
  bei eigentlich als Tap gemeinten Presses?
- Was soll passieren, wenn aus einem Press ein Tweak wird — wird der
  Mode-Toggle trotzdem ausgeführt (Modus bleibt danach an) oder komplett
  verworfen (nur die Tweak-Geste zählt)? Diese Frage bewusst beim Spielen
  klären, nicht vorher festlegen.

**Fühlt sich an:**

**Ermüdung nach längerer Session:**

**Versehentliche Aktivierungen:**

**Verdict:** KEEP / ITERATE / REJECT

---

### Variante 2 — Silo-Style (Ctrl + LMB, generischer Modifier + Klick)

`Ctrl` + LMB drücken, `Ctrl` kann sofort losgelassen werden, LMB gedrückt halten
während Drag → Tweak. LMB-Release = Commit.

Semantik: Ctrl ist reiner Aktivierungs-Trigger für die Geste, keine dauerhaft
gehaltene Taste nötig — nur ein kurzer Tastendruck zu Beginn. Welches Tool
(Move/Rotate/Scale) tweaked wird, ist der aktuell **gewählte** Transform-Modus
(siehe technische Voraussetzung unten) — nicht an eine bestimmte Taste gebunden.

**Fühlt sich an:**

**Ermüdung nach längerer Session:**

**Versehentliche Aktivierungen:**

**Verdict:** KEEP / ITERATE / REJECT

---

### Variante 3 — Hold X/R/S + Klick, früh loslassbar (Tool-spezifisch + Klick)

`X`/`R`/`S` gedrückt halten UND LMB drücken → Drag startet Tweak mit dem
entsprechenden Transform. `X`/`R`/`S` kann während des Drags losgelassen werden,
ohne die Geste abzubrechen — LMB bleibt gedrückt und bestimmt die Dauer der
Interaktion. LMB-Release = Commit. ESC während Drag = Cancel.

Semantik: Kombiniert die Tool-Eindeutigkeit von Variante 1 (die Taste legt fest,
welches Tool gemeint ist) mit der Ergonomie von Variante 2 (die Taste muss nicht
die ganze Geste über gehalten werden).

**Fühlt sich an:**

**Ermüdung nach längerer Session:**

**Versehentliche Aktivierungen:**

**Verdict:** KEEP / ITERATE / REJECT

---

### Variante 4 — Hold Ctrl + Drag, kein Klick nötig (generischer Modifier, kein Klick)

`Ctrl` gedrückt halten + Drag → Tweak mit dem aktuell **gewählten** Transform-Modus
(Move/Rotate/Scale — siehe technische Voraussetzung unten). Kein LMB-Klick nötig.
Release von `Ctrl` = Commit. ESC während Drag = Cancel.

Semantik: Kombiniert die Ergonomie von Variante 1 (kein Maustasten-Druck während
des Ziehens) mit der Tool-Unabhängigkeit von Variante 2 (ein generischer Modifier
statt dreier tool-spezifischer Tasten).

---

## Technische Voraussetzung für Variante 2 und 4

Beide Ctrl-Varianten brauchen einen **persistenten** "aktuell gewählter
Transform-Modus"-Zustand (analog Silos "current manipulator") — unabhängig von
der momentanen Interaktion.

**Bereits vorhanden, nicht neu erfinden:** `experiments/mirai_bastel_viewport_V1/viewport/app.py`
hat dieses Muster bereits vollständig implementiert (WP-02/WP-03):

- `_activate_tool(tool_cls)` — aktiviert ein Tool persistent über den
  `ToolManager`. Bleibt aktiv (modal), bis ein anderes Tool aktiviert oder
  explizit deaktiviert wird. Das ist die persistente Mode-Semantik für
  Press `X`/`R`/`S`.
- `_start_move_interaction()` + `self._tweak_tool`-Flag — löst die
  Fallback-Frage bereits sauber: **Ist bereits ein Tool persistent aktiv** →
  die Drag-Geste nutzt dieses Tool, es bleibt danach aktiv, kein Cleanup nötig.
  **Ist kein Tool aktiv** → das benötigte Tool wird nur für diese eine Geste
  implizit aktiviert (`_tweak_tool = True`) und in `_finish_drag()` danach
  automatisch wieder deaktiviert.
- `_handle_cancel_command()` — unterscheidet ESC während eines geborgten
  (Tweak-)Tools (komplett beenden) von ESC während eines explizit gewählten,
  modalen Tools (nur die laufende Interaktion abbrechen, Tool bleibt aktiv).

Der aktuelle Playground-Code (`playground/window.py`) setzt `active_tool` dagegen
bei jedem Release/Cancel auf `None` zurück — hat also (noch) keinen persistenten
Modus. Für Variante 2/4 sollte das V1-Muster adaptiert werden (Playground-Code
darf dabei quick-and-dirty sein), statt einen neuen Mechanismus zu entwerfen.

**Offene Frage durch diese Ergänzung:** Variante 1 definiert Press/Tweak jetzt
über das Ausbleiben bzw. Auftreten von Drag zwischen Key-Down und Key-Up (siehe
Variante 1 oben) — die Geste entscheidet sich also selbst. Was noch unklar ist:
ob der Mode-Toggle (persistenter Modus) trotzdem ausgeführt werden soll, wenn ein
Press nachträglich zu Tweak wird. Siehe Beobachtungspunkte bei Variante 1.

**Fühlt sich an:**

**Ermüdung nach längerer Session:**

**Versehentliche Aktivierungen:**

**Verdict:** KEEP / ITERATE / REJECT

---

## Mögliche weitere Varianten (noch nicht gebaut)

*(Platz für Variante 5+, falls beim Spielen weitere Aktivierungsideen auftauchen)*

---

## Pro / Contra (nach dem Spielen ausfüllen)

### Variante 1 — Hold Key

**Pro:**
-

**Contra:**
-

### Variante 2 — Silo-Style

**Pro:**
-

**Contra:**
-

### Variante 3 — Hold X/R/S + Klick, früh loslassbar

**Pro:**
-

**Contra:**
-

### Variante 4 — Hold Ctrl + Drag, kein Klick

**Pro:**
-

**Contra:**
-

---

## Offene Fragen nach dem Spielen

- Welche Hand/welcher Finger ermüdet zuerst, bei welcher Variante?
- Gibt es einen Unterschied bei kurzen vs. langen Arbeits-Sessions?
- Erzeugt eine der beiden Varianten mehr versehentliche Aktivierungen?
- Fühlt sich die Selection-Fallback-Regel (Tweak wirkt überall bei vorhandener
  Selection) in der Praxis richtig an, unabhängig von der Aktivierungsgeste?
- **Achsen-Zuordnung:** Liegt ein gefühlter Unterschied eher an der gewählten
  Taste (tool-spezifisch vs. generisch) oder an der Klick-Komponente (nötig vs.
  nicht nötig)? Vergleiche dazu gezielt 1↔4 und 2↔3 (gleiche Klick-Achse,
  unterschiedliche Taste) sowie 1↔3 und 4↔2 (gleiche Taste-Achse, unterschiedliche
  Klick-Komponente).
- Braucht der gewählte Transform-Modus (für Variante 2/4) eine sichtbare
  HUD-Anzeige, damit klar ist, was gerade tweaked wird, bevor man die Geste
  startet?

---

## Production Migration Notes

*(Bewusst leer bis ein Verdict vorliegt — built ≠ decided.)*

*Playground-Code für dieses Experiment darf quick-and-dirty sein; die folgenden
Punkte werden erst relevant, sobald eine Variante ein KEEP-Verdict hat und der
Übergang in `src/mirai/` ansteht (Promotion Boundary, AGENTS.md §7/M3):*

- Welche Production-Klassen/Module wären betroffen? (`mirai.interaction.tools.*`,
  ggf. Input-Binding-System)
- Muss die Zielauflösung-Regel (Selection-Fallback) als eigene, wiederverwendbare
  Funktion extrahiert werden, oder bleibt sie Tool-lokal?
- Ist ein sauberer Cancel/Undo-Pfad für die temporäre Zielauswahl (kein-Selection-Fall)
  bereits vorhanden, oder muss das separat geprüft werden?
- Konflikte mit bestehenden Bindings (aktuell nutzt X/R/S bereits Press für Move/Rotate/
  Scale-Mode — muss geprüft werden, ob Hold-Semantik dort sauber koexistiert)

*(nach dem Spielen und einer Entscheidung ausfüllen — nicht vorher)*
