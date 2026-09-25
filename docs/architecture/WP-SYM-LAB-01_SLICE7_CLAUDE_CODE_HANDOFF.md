# Handoff: WP-SYM-LAB-01 — Slice 7 (Gespiegelter Knife im Lab-Fenster)

**An:** Claude Code
**Modell/Effort:** Opus, effort `high`
**Modus (M5):** Experiment-Build — Entscheidungen stehen in §2, jetzt wird zuverlässig umgesetzt.
**BUILD darf keine neue Erkenntnis behaupten.** Wenn beim Implementieren etwas
unerwartet anders aussieht als hier beschrieben, nicht still weiterbauen — anhalten
und melden (siehe „Bei Widerspruch" am Ende).

**Stand:** `main` @ `649fff5` (Slice 6 gemergt). Baseline: Lab-Tests +
`playground/tests/test_ad017_knife*.py` → 228 passed; Produktions-Suite 546 passed.

**Ziel:** Manu kann `lab_knife.py` (Slice 6) im Fenster spielen: C startet Knife, der
gespiegelte Pfad ist beim Zeichnen sichtbar, eine nicht auflösbare Spiegelseite zeigt
sich vor dem Klick, Klick ins Leere committet. Erst danach ist ein KEEP/ITERATE/REJECT
möglich.

---

## 1. Referenzdokumente (gelten, nicht neu verhandeln)

- Handoffs Slice 2–6 von `WP-SYM-LAB-01` — alle Entscheidungen gelten weiter (kein
  Import aus `playground/`, keine Änderung an `src/`, E1–E22, A1–A11).
- `docs/architecture/AD-017_FINAL_DECISIONS_2026-09-22.md` §9 — Preview-UX ist offen:
  „Expose the capability; do not hardcode an invented final UX." Slice 7 exponiert die
  Fähigkeit (Hover-Feasibility, gespiegelter Pfad), erfindet aber keine fertige Ziel-UX.
- `docs/research/symmetry/SYMMETRY_DESIGN_BRIEF.md`, Zeile Knife: „Der Schnittpfad wird
  während des Zeichnens gespiegelt sichtbar... Kann der gespiegelte Pfad nicht eindeutig
  abgebildet werden, erfährt der Artist das vor dem Bestätigen." Genau das ist der Kern
  dieses Slices.
- `experiments/symmetry_lab/lab_knife.py` (Slice 6) — Engine, unverändert in ihrer
  Klick-Semantik; dieser Slice liest sie nur an (`start`, `intent_pairs`, `partner()`,
  `last_message`, `last_validation`) und ruft `click()`/`commit()`/`cancel()`.
- Re-Symmetrize-Vorschau (Slice 5, `lab_resymmetrize.py`/`ResymPreviewData` in
  `lab_draw_data.py`) — strukturelles Vorbild für Vorschau-Daten und das Muster
  „während X sind andere Commands gesperrt, mit Hinweis".

## 2. Entscheidungen

### Artist (Manu, 2026-09-25/26)

- **A8** (aus Slice 6, jetzt gebaut): Taste C startet Knife. Klick ins Leere committet.
- **A12 — „Leer" = außerhalb des Mesh, nicht jede Fläche.** Ein Klick auf eine Face
  (`knife_pick` Ergebnis `"face"` — auf dem Mesh, aber kein Vertex/Edge in Reichweite)
  committet nicht, sondern ist wie im Playground ein No-op. Nur `"outside"`
  (Hintergrund) committet. *Annahme, nicht ausdrücklich von Manu bestätigt* — beim
  manuellen Test in §7 als erste Frage markieren: Fühlt sich das richtig an, oder soll
  auch ein Klick auf eine unbeteiligte Face committen?
- **A13 — Kein Enter-Commit in diesem Lab.** AD-017 §8 kennt Enter als zweiten
  Commit-Weg (Playground). Manu hat für das Lab nur „Klick ins Leere" genannt; Enter
  bleibt hier unbelegt (Lab-Override wie M/Shift+S — bewusste Abweichung vom Playground,
  nicht ausdrücklich entschieden, weil nicht gefragt). Fällt beim Testen ein Wunsch nach
  Enter auf, ist das eine Erkenntnis für den nächsten Slice, kein Grund, hier
  stillschweigend Enter zu binden.

### Engineering (in diesem Handoff festgelegt)

- **E23 — Binding.** `KNIFE = "Knife"` als neuer Lab-lokaler Command-String in
  `lab_bindings.py::LAB_OVERRIDES`, Taste `C`, ohne Modifier. `C` ist im Lab-Kontext frei
  (`_VALID_CONTEXTS` in `mirai.interaction.input` kennt nur `global`/`topology`; die
  Production-Bindung von C liegt in `TOPOLOGY_CONTEXT` und greift für `symmetry_lab`
  nie — wie schon bei M/Shift+S).
- **E24 — Session-Zustand im Dispatcher**, analog zur Re-Symmetrize-Vorschau:
  - `LabDispatcher` bekommt `_knife: Optional[LabKnifeTool]` (Property `knife_active` =
    `is not None`).
  - C-Taste: abgelehnt (Statuszeile, kein Zustand), wenn ein Move scharf ist oder läuft,
    eine Re-Symmetrize-Vorschau offen ist, oder bereits eine Knife-Session läuft. Sonst
    `LabKnifeTool().activate(); knife.begin(mesh=..., scene=...)`. Wirft `begin`
    `KnifeRejected` (E20 — Symmetrie nicht `valid`/nicht 2 Seiten) → Meldung aus der
    Exception in die Statuszeile, keine Session. Sonst: Session aktiv, Hover pausiert im
    alten Sinn (E9) und wechselt auf Knife-Hover (siehe E26).
  - Während der Session: Orbit/Pan/Zoom erlaubt (wie Re-Symmetrize-Vorschau). Jedes
    andere Command (`SymmetryCycle`, `Move`, `ReSymmetrize`, `Undo`, `Redo`, `Select`)
    wird mit demselben Hinweis-Muster wie `PREVIEW_HINT` ignoriert (neue Konstante, z. B.
    `KNIFE_HINT = "Knife aktiv — Befehl ignoriert"`).
  - Plain LMB (kein Modifier) läuft während der Session durch dieselbe
    Press/Release-Klick-Schwelle wie `Select` (`CLICK_THRESHOLD_PX`), aber bei Release
    unter der Schwelle geht es an eine neue `_knife_click_at(x, y)` statt an `select_at`
    (E29).
  - ESC: `knife.cancel(); knife.deactivate(); self._knife = None`, Meldung
    „Knife abgebrochen", `Change.MESH` (der Snapshot-Restore kann Positionen/Seam
    ändern). `_cancel()` bekommt dafür einen dritten Zweig vor dem bestehenden
    Move-Zweig.
- **E25 — Commit/kein Ziel.** Trifft ein Klick (Release unter Schwelle) auf
  `knife_pick(...)["kind"] == "outside"`: `cmd = knife.commit(); knife.deactivate();
  self._knife = None`. Meldung „Knife committet" bzw. „Knife — keine Schnitte"
  (`cmd is None`), `Change.MESH` (Commit kann die Seam geändert haben, auch ohne
  History-Eintrag ist der Mesh-Zustand ggf. schon der Nachher-Zustand — Slice 6 mutiert
  pro Klick sofort, nicht erst beim Commit). Trifft der Klick auf `"vertex"`/`"edge"`:
  `knife.click(target)`; das Ergebnis (`True`/`False`) plus `knife.last_message`
  bestimmt die Meldung, `Change.MESH` in jedem Fall (auch bei Ablehnung kann die
  Statuszeile die Prüfung nennen, die gescheitert ist — `knife.last_validation`, A11).
  Trifft der Klick auf `"face"` (A12): No-op, keine Meldungsänderung.
- **E26 — Knife-Hover.** `motion()` benutzt während der Session eine Lab-Kopie von
  `knife_pick` (siehe E27) statt `pick_nearest_vertex` allein, und ruft zusätzlich
  `knife.hover(target)` aus Slice 6 auf (unverändert, liefert nur
  `valid`/`target`/`start` — reine Ziel-Gültigkeit, keine Spiegel-Information). Das
  Ergebnis plus die neue Feasibility-Prüfung (E28) wird als
  `_knife_hover: Optional[KnifeHoverPreview]` gehalten und über `Change.HOVER` an das
  Fenster gemeldet, wie bisher. Außerhalb einer Session verhält sich `motion()`
  unverändert (E9, Vertex-Hover für Move).
- **E27 — Lab-Kopie von `knife_pick`.** `lab_knife_pick.py`, kopiert und adaptiert aus
  `playground/topology_tools/knife_pick.py` (Herkunftsvermerk wie E16). Es benutzt nur
  `mirai.viewport.picking` (bereits Lab-erreichbar) — keine weitere
  Playground-Abhängigkeit. Übernimmt `ENDPOINT_THRESHOLD`, `knife_pick()` unverändert;
  `debug`-Parameter kann entfallen (das Lab hat kein Äquivalent zu den
  `[KNIFE]`-Konsolen-Traces des Playground — optional, falls es beim manuellen Testen
  hilft, sonst weglassen).
- **E28 — Dry-Run-Feasibility, ohne Mutation.** Neue reine Funktion(en) in
  `lab_knife.py` (oder einem neuen `lab_knife_preview.py`, Implementierungsentscheidung),
  die für ein Hover-Ziel ohne `split_edge`/`connect_vertices` aufzurufen bestimmen:
  - Quellpunkt: bei `"vertex"` die vorhandene Position; bei `"edge"` die interpolierte
    Position bei `t` (wie `split_edge` sie berechnen würde — reine Arithmetik, keine
    Mutation).
  - Spiegelziel auflösbar? Dieselbe Reihenfolge wie `partner()` (E17): Ist der
    Quellpunkt ein bestehender Vertex → `knife.partner(vid)`. Ist er ein Edge-Punkt →
    liegt die Edge auf der Seam → Quellpunkt ist sein eigener Partner (kein Spiegelpunkt
    zu zeigen, Achsenkomponente wird bei echtem Split exakt `0.0`); sonst Partner-Edge
    über `partner(a)`/`partner(b)` der Edge-Endpunkte auflösen (wie in `_split`) —
    existiert sie und ist sie nicht die Quell-Edge selbst → Spiegelpunkt =
    `mirror_position(Quellpunkt)`; sonst nicht auflösbar.
  - Seam-Sehnen-Fall: Ist ein Start gesetzt und sowohl Start als auch das Hover-Ziel
    sind Seam-Vertices (bzw. würde ein Edge-Split auf der Seam landen, während der Start
    schon ein Seam-Vertex ist) → nicht auflösbar, gleicher Grund wie beim echten Klick.
  - Ergebnis als `KnifeHoverPreview`-Dataclass: `source_position`,
    `mirror_position: Optional[Vec3]`, `resolvable: bool`, `reason: Optional[str]`
    (kurzer Text für die Statuszeile, z. B. „kein Spiegelpartner", „Schnitt entlang der
    Seam").
  - Wichtig: Diese Logik dupliziert die Auflösungsreihenfolge aus Slice 6 absichtlich
    nur so weit wie nötig — wo sinnvoll, die bestehenden privaten Methoden (`partner`,
    `_seam_edges`, `_seam_vertices`, `edge_between`) direkt wiederverwenden statt sie zu
    kopieren. Kein zweiter, abweichender Algorithmus.
- **E29 — Klick-Routing.** `press()` erweitert die bestehende
  `allowed = (ORBIT, PAN) if self._move_armed else (...)`-Fallunterscheidung um einen
  Zweig für `self._knife is not None`: dann `allowed = (ORBIT, PAN)` und zusätzlich wird
  `Select`-artiges plain-LMB als eigene Geste erkannt (gleiche `_Gesture`-Mechanik,
  gleicher `CLICK_THRESHOLD_PX`), deren `release()`-Branch auf `_knife_click_at` statt
  `select_at` zeigt (E25).
- **E30 — Darstellung** (Farben Implementierungsdetail, README-Legende ergänzen wie in
  Slice 5 verlangt):
  - Start-Vertex der laufenden Session und sein Spiegelpartner: eigene Marker
    (Vorschlag: gleiche Semantik wie Auswahl/Hover — Start in einer Session-eigenen
    Farbe, Partner türkis wie überall sonst die gespiegelte Vorschau).
  - Hover-Ziel (Vertex oder interpolierter Edge-Punkt) und sein Spiegelpunkt, wenn
    auflösbar: Hover-Farbe (gelb, wie E9) bzw. türkis für den Spiegelpunkt — dieselbe
    Farbsprache wie überall im Lab „türkis = gespiegelte Vorschau".
  - Nicht auflösbar (E28 `resolvable == False`): eigene Farbe für den Hover-Punkt selbst
    (Vorschlag: die schon etablierte „ohne Partner"-Farbe, magenta) — vor dem Klick
    sichtbar, wie es der Design Brief verlangt. Kein Spiegelpunkt gezeichnet.
  - Committeter Pfad: Jeder angenommene Klick mutiert das Mesh sofort (Slice 6); neue
    Vertices/Edges erscheinen also automatisch über die normale
    `Change.MESH`-Aktualisierung. Keine zusätzliche Pfad-Overlay-Struktur nötig, außer
    dem Start-Marker.
  - Statuszeile: wie `move_target_label` ein Textbaustein „Knife: aktiv (Start v<id> /
    kein Start)"; bei abgelehntem Klick oder Rollback die Meldung aus
    `knife.last_message` (E25). Wenn `knife.last_validation` vorliegt und nicht `ok` ist,
    zusätzlich `knife.last_validation.summary()` (Slice 6 liefert das schon fertig
    formatiert).

## 3. Ziel dieses Slices

Manu drückt C, sieht ab dem ersten Hover, ob und wohin gespiegelt wird — inklusive der
Fälle, in denen es nicht geht — schneidet mehrere Schritte, sieht bei einer Ablehnung
sofort, welche Prüfung gescheitert ist, und committet mit einem Klick ins Leere. ESC
bricht jederzeit sauber ab. Danach der erste Artist-Durchgang (KEEP/ITERATE/REJECT, §7).

## 4. Scope

1. `lab_knife_pick.py` (E27).
2. Dispatcher-Erweiterung (E24–E26, E29) in `lab_dispatch.py`, GL-frei, testbar wie
   Re-Symmetrize.
3. Feasibility-Dry-Run (E28), reine Funktion(en), eigene Charakterisierungstests.
4. Darstellung (E30) in `lab_draw_data.py` (neue `KnifePreviewData`-artige Struktur,
   analog `ResymPreviewData`) und `lab_render.py`/`lab_window.py` (neue VBOs,
   `Change`-Flag wiederverwenden oder — falls sauberer — `Change.HOVER` um Knife
   erweitern statt eines neuen Flags; Implementierungsentscheidung).
5. `lab_status.py`: Knife-Zeile wie beschrieben.
6. README: Steuerung (C / LMB / Klick-ins-Leere / ESC), Farblegende ergänzt,
   Prüfanleitung für Manu (§7, Schritte 1–N), Abschnitt „Gespiegelter Knife im Fenster
   (Slice 7)" — keine Artist-Validierung behaupten, das kommt erst nach dem echten
   Durchgang.

## 5. Not in scope

- Jede Änderung an `lab_knife.py`s Klick-Semantik selbst (E16–E22 aus Slice 6 bleiben,
  wie sie sind) — Slice 7 liest und ruft nur.
- Face-Cut (AD-017 §6 weiterhin offen).
- Knife bei `partial` (A10 weiterhin gültig).
- Enter-Commit (A13).
- Promotion nach `src/`, Änderungen am Playground-Knife.
- Ein zweites, eigenes Preview-„Undo" — die Vorschau ist reine Anzeige, kein Zustand,
  der zurückgenommen werden müsste (anders als Re-Symmetrize, das einen offenen Plan
  hält). In-Session-Undo/Redo bleiben die aus Slice 6 (ganze Schritte); es gibt in
  Slice 7 nichts Neues zu undoen.

## 6. Must NOT change (Diff muss hier leer sein)

- `src/**`, `playground/**`, `tools/**`, `examples/**`, Tests außerhalb von
  `experiments/symmetry_lab/tests/`, `experiments/symmetry_lab/lab_knife.py` (nur
  lesen/aufrufen, keine Verhaltensänderung — falls eine Erweiterung dort doch nötig wird,
  z. B. weil `partner()` für den Dry-Run eine öffentlichere Signatur braucht, ist das
  erlaubt, aber additiv und ohne bestehende Tests aus `test_lab_knife.py` zu brechen;
  anhalten, wenn unklar).

**Erwarteter Diff:** `experiments/symmetry_lab/**` (inkl. README), dieses
Handoff-Dokument.

## 7. Erwartete Tests (headless) und manuelle Prüfung

**Headless** (Dispatcher/Preview, wie `test_lab_move.py`/`test_lab_resymmetrize.py`):

- C startet Knife bei `valid` + 2 Seiten; abgelehnt bei `partial`, bei laufendem Move,
  bei offener Re-Symmetrize-Vorschau, bei schon aktiver Knife-Session.
- Hover über eine +X-Edge zeigt einen auflösbaren Spiegelpunkt exakt bei
  `mirror_position(Quellpunkt)` (Vergleich gegen `lab_knife`s eigene Berechnung beim
  echten Split — beide müssen übereinstimmen, sonst zeigt die Vorschau etwas anderes als
  das Ergebnis).
- Hover über eine Seam-Edge zeigt keinen Spiegelpunkt, `resolvable=True`,
  `mirror_position=None` (Sonderfall, kein Fehler).
- Hover, bei dem kein Partner auflösbar ist (z. B. `partial`-Zustand künstlich
  erzwungen, oder eine Situation aus dem Seam-Sehnen-Fall): `resolvable=False`, ein
  `reason`.
- Klick auf `outside` ohne begonnenen Schnitt: `commit()` liefert `None` (kein
  History-Eintrag), Session endet, Meldung „keine Schnitte".
- Klick-Sequenz Vertex → Edge → `outside`: zwei Schritte, ein History-Eintrag, Session
  endet.
- Klick auf `"face"`: Session bleibt aktiv, kein Schnitt, keine Meldungsänderung (A12).
- Während der Session: `SymmetryCycle`/`Move`/`ReSymmetrize`/`Undo`/`Redo` per Taste
  ignoriert mit Hinweis; Orbit/Pan/Zoom funktionieren unverändert.
- ESC während der Session: Mesh bitgleich zum Zustand vor `begin()`, kein
  History-Eintrag, Session beendet.
- Ein abgelehnter Klick (Rollback-Fall aus Slice 6, z. B. per Monkeypatch reproduziert):
  `knife.last_validation.summary()` erscheint in der Statuszeile.
- Import-Grenze bleibt grün; alle Lab- und Playground-Knife-Tests bleiben grün.

**Manuelle Prüfung für Manu** (README, wie bei den vorherigen Slices formuliert):

1. `head_basemesh`, Shift+S auf X (`valid`), C drücken → Statuszeile zeigt
   „Knife: aktiv".
2. Maus über eine Kante seitlich am Kopf bewegen (nicht auf der Seam) → gelber
   Hover-Punkt auf der Kante, türkiser Spiegelpunkt auf der anderen Seite.
3. Klicken → Punkt wird real (Split beider Seiten), Statuszeile bleibt „aktiv".
4. Maus über eine zweite Kante in einer Nachbar-Face bewegen, klicken → Verbindung
   entsteht beidseitig.
5. Maus auf eine Seam-Kante bewegen → Hover-Punkt ohne Spiegelpunkt (Sonderfall).
6. Absichtlich eine Situation ansteuern, in der kein Partner auflösbar ist (z. B.
   zweiter Schnitt Richtung eines schon erzeugten Spiegelpunkts, siehe
   Slice-6-Befund „Beobachtet, nicht entschieden") → magenta Hover-Punkt, kein Klick
   möglich oder Klick abgelehnt mit Meldung — das ist die erste offene Frage an dich:
   stört das den Fluss, oder ist es erwartbar?
7. Klick auf freien Hintergrund → Commit, Session endet, Statuszeile zurück auf normal.
8. Wiederholen mit ESC statt Schritt 7 → Mesh wie vor Schritt 1.
9. Frage A12: Klick auf eine unbeteiligte Face (nicht Hintergrund) während einer
   Session — fühlt sich „No-op" richtig an, oder hättest du erwartet, dass auch das
   committet?

## 8. Done-Kriterien

- Lab-Tests grün; Produktions-Suite unverändert grün
  (`pytest tests --ignore=tests/test_extrude_tool.py`); Playground-Knife-Tests
  unverändert grün.
- `git diff --stat` enthält nur Dateien aus §6 „Erwarteter Diff".
- README: Steuerungstabelle ergänzt, Farblegende ergänzt, Abschnitt „Gespiegelter Knife
  im Fenster (Slice 7)", Prüfanleitung wie §7. Keine Artist-Validierung behaupten — das
  trägt erst Manu nach.
- Commit-Message-Vorschlag: `WP-SYM-LAB-01 Slice 7: mirrored Knife in the lab window
  (hover feasibility, C to start, click-outside to commit)`

## 9. Bei Widerspruch

Anhalten und melden, nicht still lösen, insbesondere wenn:

- die Dry-Run-Vorschau (E28) für einen Fall einen anderen Spiegelpunkt berechnet als der
  spätere echte Klick (E18/Slice 6) — das wäre eine Vorschau, die lügt,
- `partner()` oder eine andere Slice-6-Methode für den Dry-Run erweitert werden muss und
  dabei ihr bestehendes Verhalten für echte Klicks anfasst,
- Enter sich beim Testen als notwendig herausstellt, um das Tool bedienbar zu machen
  (dann ist A13 falsch entschieden, keine Sache, die man nebenbei still ändert),
- sich Hover/Preview nur mit Import aus `playground/` sauber lösen lässt.
