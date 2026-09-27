# Transform Lab — Artist Verdict (WP-AP-04)

**Status:** ENTSCHIEDEN — Aktivierungsmodell KEEP (AD-016), keine offenen Punkte mehr
**Hintergrund:** `research-map-v1.md` §4 (Host §5 Variants), AD-015 (2026-09-21, abgelöst), AD-016 (2026-09-21, aktuell), WP-AP-GIZMO-01/04
**Bedienung:** `Tab` bis `transform` fokussiert ist → `M` wechselt die Aktivierungsvariante.

⚠️ **Tastenhinweis:** Die Variant-Dateien nutzen noch die alten Tasten (X/R/S bzw. Q/W/E je nach Datei). Die Artist Input Truth wurde am 26.09. geändert: **move=W, rotate=E, scale=R**, Q ist unbelegt.

---

## Aktivierungs-/Commit-Varianten

### A — Hold
`X/R/S` halten + Drag = Transform, Loslassen = Commit, ESC während Drag = Cancel

**Verdict:** ITERATE → überholt (Ausgangspunkt, nicht mehr aktiv verfolgt)

---

### B — Press-Mode und D — Hold-Key-Hover — **identisch, ein Mechanismus**
Beim Vergleich hat sich gezeigt: B (`variant_press_mode.py`) und D (`variant_hold_key_hover.py`) verhalten sich tatsächlich gleich — beide funktionieren sowohl mit bestehender Selektion als auch rein über Hover, ohne dass vorher etwas ausgewählt sein muss. Zwei Variant-Dateien für denselben entschiedenen Mechanismus; keine eigenständige B-Frage mehr offen.

Antippen (unter `CLICK_THRESHOLD`) → wählt nur das Werkzeug, keine Ausführung.
Halten + Ziehen + Loslassen → führt aus, committet beim Loslassen.

**Ziel-Regel, für Move/Rotate/Scale gleichermaßen entschieden:**
- Existiert bereits eine Selektion → Transform wirkt auf die bestehende Selektion (wie Blender `G`), unabhängig davon, was gerade gehovert wird.
- Existiert keine Selektion → Transform wirkt auf das gehoverte Element bei Tastendruck (temporäres Ziel, wiederverwendet aus dem Tweak-Mechanismus).

**Verdict:** KEEP — AD-016 (2026-09-21), löst AD-015 ab. Gilt für alle drei Werkzeuge (Move/Rotate/Scale) identisch.

---

### C — Press-Drag-Click
Setzt eine bestehende Selektion voraus (kein Hover-only-Fallback).

**Verdict:** überholt durch B/D — kein eigenständiges Verdict mehr nötig

---

## Werkzeug-Varianten (Move / Rotate / Scale)

Grundfunktion je Achse (`variant_move.py`, `variant_rotate.py`, `variant_scale.py`) — kein eigenständiges Aktivierungs-Urteil, sondern Träger von B/D. Eigene Gizmo-Formen pro Werkzeug (Dreibein für Move, eigene Formen für Rotate und Scale) bereits umgesetzt (WP-AP-GIZMO-04).

**Verdict:** KEEP (Grundfunktion, informiert WP-06 Slice B3 — Move auf `W` + Undo/Redo, noch nicht gebaut)

---

## Kandidaten für Production

- **Press-Mode / Hold-Key-Hover (B/D)** — PROMOTED-Ziel für WP-06 Slice B3 (Move auf `W`, noch nicht gebaut)
- Gizmo-Klick-Verdrahtung (Achsen-Constraint unabhängig vom Tool-Status) — architektonisch entschieden (AD-016)
- Gizmo-Formen (Dreibein/Rotate/Scale) — bereits umgesetzt (WP-AP-GIZMO-04), Artist-Verdict zu den Formen selbst separat in `transform-gizmo.md`

---

## Offene Fragen (kein Verdict)

- **Muster A (Blender): Constraint live während der Bewegung wechseln**, Mehrfachdruck Global→Local→aus. Nicht untersucht; würde den Vertrag „`space` fix ab `begin()`" berühren. (Eingetragen 2026-09-27 mit WP-06 B4.1 — Production übernimmt bis dahin das Playground-Modell: sticky Toggle, wirkt ab der nächsten Geste.)

---

## Aufräum-Hinweis (nicht Teil des Verdicts, sondern eine Code-Beobachtung)

`variant_press_mode.py` und `variant_hold_key_hover.py` implementieren denselben entschiedenen Mechanismus doppelt. Da `experiments/` bewusst Spielwiese bleibt (M3, Promotion Boundary), ist das kein Zwang zum Aufräumen — nur ein Hinweis, falls ihr die Lab-Dateien irgendwann konsolidiert.