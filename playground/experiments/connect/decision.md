# Connect Lab — Artist Verdict

**Status:** ENTSCHIEDEN (2026-09-21) — Baseline REJECT, Pro Face KEEP
**Hintergrund:** `docs/research/topology/CONNECT_NONQUAD_DISCOVERY.md` (§6 Testaufbau, D1–D8)
**Bedienung:** `Tab` bis `connect` fokussiert ist → `M` wechselt die Variante (HUD: `Setting: … connect=…`).
Kanten-Modus (`2`), Kanten wählen, `C` = Connect. `Ctrl+Z` = Undo.

Start: `python playground/run.py grid` (flaches 8×8-Quad-Raster) oder `python playground/run.py head`.

---

## Aufgaben (je Variante, zusammen ca. 5 Minuten)

1. Schnitt über zwei Quads, danach noch ein Quad weiter verlängern.
2. Eine Ecke abschneiden (zwei benachbarte Kanten eines Quads).
3. Einen Schnitt um eine Ecke herumführen (Knick).
4. In einer gedachten Zone mehr Kontrolle schaffen, ohne dass Loops die Zone verlassen.

Erwartet: Aufgabe 1 hakt in **beiden** Varianten (Befund A2 — Weiterschneiden braucht einen Vertex).
Das ist ein Befund für Designfrage D5, kein Urteil über die Variante.

---

### Streifen (nur Quads) — Baseline

**Verdict:** REJECT

---

### Pro Face (Wings-artig)

**Verdict:** KEEP

---

## Beobachtungen, die nicht zur Frage gehören

(Incidental evidence — hebt Priorität anderer Fragen, entscheidet sie nicht.)

- Aufgabe 1 (Weiterschneiden) hakte wie erwartet in beiden Varianten — bestätigt D5
  (Weiterschneiden braucht einen Vertex-Anteil in der Auswahl, keine reine Kanten-Auswahl).
  Kein Urteil über die Varianten selbst.
- Manu bringt im Anschluss Silo als Referenzmodell ein (Split/Connect/Knife über Auswahltyp
  und -anzahl statt über getrennte Werkzeuge) — siehe Folgegespräch, noch ungebaut.
