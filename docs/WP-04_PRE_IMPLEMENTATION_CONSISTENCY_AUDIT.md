# WP-04 — Pre-Implementation Consistency Audit

**Date:** 2026-09-04
**Type:** Planungs-Audit (Consistency Check) — **keine Implementierung, keine Architekturänderung**
**Scope:** WP-04-Gate-Plan rückwärts vom letzten geplanten Gate bis zum frühesten Gate geprüft gegen aktuellen Repo-Stand, WP-04-Dokumentation/ADRs, Gate-4-Architecture-Amendment, Viewport-V0.2-Architektur und aktuelle UX-/Interaction-Entscheidungen
**Auditbasis-Branches:** `main` @ `197443f`, `wp/04-production-foundation` (Tip bereits auf `main`), `experiment/viewport-v0.2` (`main` + V0.2-Experiment + V0.2-Architekturdokument)

---

## 1. Auditbasis

Geprüfte Dokumente und Zustände:

| Quelle | Rolle im Audit |
|---|---|
| `docs/WP-04_GATE_PLANNING.md` v1.0 (2026-09-01) | Auditiertes Objekt: Gates 2–12 mit Tasks/Acceptance Criteria |
| `main` @ `197443f` (`merge: consolidate WP-04 documentation`) | Aktueller Repo-Stand (`src/core/` nur; **kein** `src/mirai/`) |
| `wp/04-production-foundation` (Tip `cc7fa81`, enthalten in `main`) | WP-04-Branch — enthält ebenfalls **keine** Gate-3/4-Implementierung |
| `experiment/viewport-v0.2` (+2 Commits) | V0.2-Experiment (PROVEN) + `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` |
| `WP-04_GATE_4_ARCHITECTURE_AMENDMENT.md` (2026-09-02) | Ersetzt Gate-4-Planungsannahmen (Pattern A/B, entkoppelte Layer) |
| `WP-04_GATE_4_ARCHITECTURE_DECISIONS.md` (ADR-G4-001…007, APPROVED) | Kanonische Gate-4-Interaktionsarchitektur |
| `WP-04_GATE_3_COMPLETION_REPORT.md`, `WP-04_GATE_4_SESSION_1/2_COMPLETION.md`, `WP-04_GATE_4_KICKOFF_REVISED.md` | Berichtete Ausführung von Gate 3/4 |
| `docs/viewport/VIEWPORT_V02_ARCHITECTURE.md` + `experiments/mirai_bastel_viewport_V02/README.md` | Verifizierte V0.2-Architektur (Dirty-State, RenderMesh, Overlay, CPU-Picker, Counter/Benchmarks) |
| `docs/ADR-001-core-v1-reassessment.md` (Accepted) | Core-Freeze gelockert; Transform-Ops als Core-Funktionalität autorisiert |
| `docs/architecture/CORE_V1_FREEZE.md` | Enthält **keine** §7.1-Precedent-Dokumentation; Status weiter „FROZEN“ |
| `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md` | Kanonischer Input→Command→Tool→Operation→History-Vertrag |
| `docs/design/WORKFLOW.md` | UX-Prinzipien („See → Hover → Grab → Move“, Tweak, wenige Modi) |
| `docs/architecture/ROADMAP.md` | WP-Nummerierung (führt WP-04 noch als „Deformation Foundation“) |
| `WP-04_OPEN_QUESTIONS.md`, `WP-04_EXECUTIVE_SUMMARY_AND_DECISION_RECORD.md`, `WP-04_IMPLEMENTATION_IMPACT_OPTION_C.md`, `WP-04_GATE_2_FINAL_DELIVERY.md`, `WP-04_ANALYSIS_INDEX.md` | Gate-2-Entscheidungspaket (Q1–Q4, Option C) |

**Vorbemerkung zu „Gate 1“:** Im WP-04-Plan existiert kein Gate 1 — die Nummerierung beginnt bei Gate 2 (Discovery, ✓ DONE). Der Rückwärtslauf deckt daher **Gate 12 → Gate 2** ab.

---

## 2. Querschnittsbefunde (vor der Gate-Bewertung)

### 2.1 Repo-Stand vs. Completion-Reports

Verifiziert per `git ls-tree -r --name-only` auf `main` und `wp/04-production-foundation`:

- `src/mirai/**` existiert **nicht** (weder `application.py` noch `interaction/` noch `viewport/`).
- `src/core/operations/transform.py` existiert **nicht** (`src/core/operations/` enthält nur `move.py`, `topology.py`).
- `tests/test_gate4_*.py`, `tests/test_application.py`, `tests/test_transform_operations.py` existieren **nicht**.
- `tests/` enthält ausschließlich die Core-Suite.

Die Completion-Reports (Gate 3: „47/47“, Gate 4: „56/56“, „APPROVED FOR PRODUCTION“) beschreiben Artefakte, die in keinem Branch dieses Repos vorhanden sind. Sie sind daher **Planungs-/Session-Records, keine Implementierungsnachweise**.

### 2.2 Gate-Nummerierung divergiert

- Gate-Plan: Gate 5 = *Selection & Display Foundation*, Gate 7 = *Camera*.
- Spätere Dokumente (`WP-04_GATE_4_SESSION_2_COMPLETION.md` Option A, `experiments/README.md`, V0.2-Experiment-README §10): „**Gate 5 — Viewport Production/Rendering**“.
- Damit sind zwei inkompatible Gate-5-Bedeutungen im Umlauf.

### 2.3 Statusspalte im Gate-Plan veraltet

`WP-04_GATE_PLANNING.md` markiert Gate 3 weiterhin als „→ NEXT“, obwohl Gate 3/4 laut Reports abgeschlossen sind.

### 2.4 Window/Rendering aus Gate 3 ausgekoppelt

Plan: Window-Adapter (Task 3.9), Entry-Point (Task 3.10), Rendering-Extraktion (Task 3.8) in Gate 3.
Ausführung laut Report: bewusst ausgeschlossen („What’s OUT of Gate 3“). Die V0.2-Architektur definiert inzwischen, wie Rendering gebaut werden soll (RenderMesh, Dirty-State, persistente GPU-Ressourcen).

### 2.5 Doku-Inkonsistenzen um Core-Freeze und Roadmap

- ADR-001 (Accepted) lockert den Freeze; `CORE_V1_FREEZE.md` steht weiterhin auf „Status: FROZEN“ ohne §7.1-Precedent, obwohl die Promotion-Dokumente (u. a. `WP-04_IMPLEMENTATION_IMPACT_OPTION_C.md` Task 3.13.4) diese Dokumentation zusagen.
- `ROADMAP.md` (2026-08-29) führt WP-04 noch als „Deformation Foundation“ und kennt die Re-Scoping-Entscheidung „WP-04 = Production Foundation“ nicht.

### 2.6 Zielstruktur des Produktions-Viewports widersprüchlich

- Gate-3-Plan/Reports: `src/mirai/viewport/`.
- V0.2-Spezifikation §11: „build v0.2 in `src/viewport/`“.
- `SOURCE_ARCHITECTURE.md` hält die finale `src/`-Struktur bewusst offen — die Entscheidung ist aber zu treffen, bevor Gates 5/7 umgesetzt werden.

---

## 3. Gate-by-Gate-Klassifikation (rückwärts, Gate 12 → Gate 2)

Klassifikationsskala: CURRENT / NEEDS UPDATE / SUPERSEDED / BLOCKED / UNCLEAR.

| Gate | Klassifikation | Begründung (kurz) |
|---|---|---|
| **12 – Merge** | **NEEDS UPDATE** | Merge-Scope undefiniert: Gate-3/4-Implementierung existiert in keinem Branch; V0.2-Dokumente nur auf Experiment-Branch; `wp/04-production-foundation`-Tip ist bereits auf `main`. „Plan WP-05“ kollidiert mit alter ROADMAP-Nummerierung (dort: WP-04 = Deformation). |
| **11 – Architecture Review** | **NEEDS UPDATE** | Review-Umfang erweitert: Amendment, ADR-G4-001…007, V0.2-Spezifikation, ADR-001 und Doku-Rekonziliation (Freeze/Roadmap) gehören in den Prüfkatalog; zusätzlich Verifikation Completion-Reports ↔ Repo-Stand. |
| **10 – E2E Test** | **BLOCKED** | E2E setzt einen sichtbaren Viewport voraus. Window/Rendering wurde aus Gate 3 ausgekoppelt und „Viewport Production“ (V0.2 → `src/`) ist in der Gate-Sequenz nirgends eingeplant. Voraussetzung fehlt. |
| **9 – AI Review** | **NEEDS UPDATE** (klein) | Unabhängige Prüfung muss neue Entscheidungsmenge abdecken (Amendment, ADR-G4-00x, V0.2-Arch, ADR-001) und die Diskrepanz Completion-Reports ↔ Repo-Stand. |
| **8 – Validation (150+ Tests, ≥85 %)** | **NEEDS UPDATE** | „56/56“ und „80+“ sind repo-seitig nicht verifizierbar. Testzahl muss auf tatsächlichen Repo-Stand bezogen werden; V0.2-Counter-/Benchmark-Kriterien (Spec §8/§13) sind noch nirgends verankert. |
| **7 – Camera** | **NEEDS UPDATE** | Ziel (Orbit/Pan/Zoom stabil) bleibt; Implementierungsbasis überholt: V0.2 verbietet Geometrie-Invalidierung bei Kamera (Uniform-Only, Dirty-State-Kategorie „camera“). V1-`camera.py`-Extraktion „as-is“ konserviert den nachgewiesenen Anti-Pattern (Orbit = 87 % Rebuild-Zeit). |
| **6 – Input Config (keymap.json)** | **CURRENT** | Unabhängig von V0.2; konsistent mit ADR-G4-007 (Bindings read-only) und `INPUT_COMMAND_TOOL_CONTRACT.md`. Kleinigkeit: ADR-G4-006-Befehlssatz in Defaults spiegeln. |
| **5 – Selection & Display** | **NEEDS UPDATE** | Funktionale Ziele (V/E/F, Hover, Resolver, Display-Modi) gültig und deckungsgleich mit `WORKFLOW.md` („See → Hover → Grab → Move“). Aber: Visualisierung muss Overlay-basiert sein (Selection invalidiert nie Base-Mesh), Picker nach V0.2-CPU-Kriterien, Hover ohne Rebuild; „Rendering-Tests“ setzen einen Renderer voraus, den kein Gate liefert. |
| **4 – Interaction & Tools** | **SUPERSEDED** | Ersetzt durch Amendment + ADR-G4-001…007 + Kickoff Revised: Kontext-Parameter, `on_activate`, Pattern A/B, parameterlose Tools, `ToolManager` in `tool.py`, 3-stufiges Dispatch, Selection-Gating, Bindings read-only. Q1 über ADR-001 entschieden (Promotion, Option C). Vorbehalt: der „vollendete“ Zustand ist repo-seitig nicht vorhanden (siehe §2.1). |
| **3 – App Foundation** | **SUPERSEDED** | Abweichend ausgeführt: 1 Session statt 3–4, Window/Rendering (Tasks 3.9/3.10) bewusst ausgeschlossen, Task 3.13 (Promotion) neu, `ToolManager` in `tool.py` statt `tool_manager.py`. **Task 3.8 (V1-Rendering nach `render.py` extrahieren) ist durch V0.2-RenderMesh obsolet** und darf nicht stillschweigend weitergeschleppt werden. Offen: `src/mirai/viewport/` vs. `src/viewport/` (§2.6). |
| **2 – Discovery** | **CURRENT** | Als Analyse-/Entscheidungsgrundlage weiterhin gültig (Q1–Q4 entschieden; Interaktionskomponenten korrekt als „production-grade“ klassifiziert). Nicht mehr maßgeblich für die Render-Pfad-Empfehlung — das korrigiert V0.2. |

---

## 4. Spezialprüfungen

### 4.1 Haben Gates noch Abhängigkeiten zur alten V1-Viewport-Architektur?

Ja, drei:

1. **Gate 3** — Extraktionsquellen `camera.py`, `picking.py`, `display_state.py`, `app.py` (Rendering) aus `experiments/mirai_bastel_viewport_V1/viewport/`.
2. **Gate 5** — Visualisierung setzt V1-artigen Renderpfad voraus.
3. **Gate 7** — Kamera-Extraktion aus V1.

Die **Interaktionskomponenten** von V1 (Tool/Input/Binding/Commands) bleiben valide; der **Renderpfad** von V1 ist durch V0.2 ersetzt (Research-Nachweis: „rebuild everything“-Modell, `VIEWPORT_V02_RESEARCH.md` §4–8).

### 4.2 Passen die Gates zur Gate-4-Interaction-Architektur?

Ja — das Amendment wurde bewusst so gebaut (Pattern A/B offen, kein UX-Hardcoding, `Application.dispatch_command()` als universeller Einstiegspunkt). Gates 5–7 konsumieren genau diese Schnittstellen. Auch `WORKFLOW.md` („Tweak ohne Tool-Schritt“) bleibt möglich (Nicht-Tool-Commands via Dispatch). **Kein Konflikt.**

### 4.3 Sind Schnittstellen/Abhängigkeiten zwischen den Gates noch konsistent?

Fast — drei Brüche:

1. Gate 5/7 setzen einen Renderer voraus, den kein Gate liefert (Rendering wurde aus Gate 3 ausgekoppelt, „Viewport Production“ ist nicht eingeplant).
2. Zielstruktur `src/mirai/viewport/` (Gate 3) vs. `src/viewport/` (V0.2-Spec §11) widersprüchlich.
3. Gate-Nummerierung: „Gate 5 — Viewport Production“ (spätere Docs) vs. „Gate 5 — Selection & Display“ (Plan).

### 4.4 Gibt es spätere Entscheidungen, die frühere Pläne unwirksam machen?

Ja:

1. **ADR-001** (Freeze gelockert → Q1-Pfad entschieden: Promotion).
2. **Gate-4-Amendment + ADR-G4-001…007** (ersetzt Task 4.1–4.7 im Detail).
3. **V0.2-Architektur** (ersetzt Task 3.8; ändert Implementierungsbasis von Gate 5/7).
4. **Completion-Reports** (rescopen Gate 3: Window/Rendering/Kamera-Kontrolle ausgeschlossen, Task 3.13 neu).

### 4.5 Sind die „Completion“-Dokumente korrekt als Planung und nicht als Implementierungsnachweis zu verstehen?

**Nein, sie sind als Nachweis ungeeignet — sie sind Planungs-/Session-Records.**

Verifiziert per `git ls-tree`: Weder `main` noch `wp/04-production-foundation` noch `experiment/viewport-v0.2` enthalten `src/mirai/**`, `src/core/operations/transform.py`, `src/main.py`, `tests/test_gate4_*.py` oder Transform-Tests. Die Häkchen („[x]“, „56/56“, „APPROVED FOR PRODUCTION“) sind repo-seitig unbelegbar — vermutlich in einem anderen Workspace entstanden und nie committed. Gate 8/9/11/12 müssen repo-verifizierbare Artefakte fordern.

**Zusatzbefund:** ADR-001 hat den Freeze gelockert, aber `CORE_V1_FREEZE.md` steht weiterhin auf „Status: FROZEN“ und enthält **keine** §7.1-Precedent-Dokumentation, obwohl die Promotion-Dokumente sie zusagen. `ROADMAP.md` führt WP-04 noch als „Deformation Foundation“.

---

## 5. Kompakte Liste der notwendigen Änderungen

Ohne neue Architektur, ohne neue Gates, ohne neue großen Dokumente — ausschließlich Plan- und Doku-Anpassungen anhand bereits getroffener Entscheidungen:

1. **`WP-04_GATE_PLANNING.md`**: Status-Spalte aktualisieren (Gate 3/4 = „reported complete, repo-unverifiziert“ statt „→ NEXT“); Kopfverweis einfügen, dass Gate 3/4-Details durch Amendment/ADR-G4-00x/Completion-Reports ersetzt sind; **Task 3.8 streichen/annullieren** (V0.2-RenderMesh).
2. **Gate-Nummernkonflikt auflösen**: Festlegen, wo „Viewport Production“ (V0.2 → `src/`) in der bestehenden Sequenz sitzt (Verweis statt neues Gate) — hartes Prerequisit für Gates 5, 7, 10.
3. **Gate 5 + Gate 7** um V0.2-Constraints ergänzen: Overlay-Selection (keine Base-Mesh-Invalidierung), CPU-Picker-Grenzen, Kamera ohne Geometrie-Upload, Dirty-State-Kategorien.
4. **Gate 8**: V0.2-Counter-/Benchmark-Kriterien (Spec §8/§13) referenzieren; Test-Baselines auf realen Repo-Stand umstellen.
5. **Gate 10**: Abhängigkeit „existierender Rendering-Viewport“ explizit markieren (aktuell BLOCKED).
6. **Gate 11**: Review-Umfang erweitern (Amendment, ADR-G4-00x, V0.2-Spec, ADR-001, Doku-Rekonziliation, Completion-vs-Repo-Verifikation).
7. **Gate 12**: Merge-Scope definieren (welche Branches/Artefakte, inkl. Nachholen der fehlenden `src/mirai`-Implementierung **oder** Neuausführung der Gates 3/4) und Merge an repo-verifizierbare Tests koppeln.
8. **Doku-Rekonziliation (kanonisch, klein)**: `CORE_V1_FREEZE.md` ↔ ADR-001 (§7.1-Precedent nachtragen oder Freeze-Status ändern); `ROADMAP.md` WP-Nummerierung an WP-04-Production-Foundation anpassen; `docs/README.md` WP-04-Working-Set um Amendment/ADRs/Completion-Dokumente erweitern.
9. **Completion-Dokumente kennzeichnen**: Statuszeile „Planungs-/Session-Record — kein Implementierungsnachweis im Repo“ ergänzen, damit sie nicht als GO-Kriterium gelesen werden.
10. **Strukturentscheid dokumentieren** (wenn gefallen): `src/mirai/…` vs. `src/viewport/…` in `SOURCE_ARCHITECTURE.md` — dort ist die finale Struktur bewusst noch offen.

---

## 6. Ergebnis-Zusammenfassung

| Klassifikation | Gates |
|---|---|
| CURRENT | 6, 2 |
| NEEDS UPDATE | 12, 11, 9, 8, 7, 5 |
| SUPERSEDED | 4, 3 |
| BLOCKED | 10 |
| UNCLEAR | — (Strukturfrage `src/mirai/` vs. `src/viewport/` ist als Änderung Nr. 10 erfasst, kein eigenes Gate betroffen) |

Kernaussage: Spätere Erkenntnisse (Gate-4-Amendment, ADR-001, V0.2-Architektur) haben die Annahmen der Gates 3–5 und 7–10 tatsächlich überholt oder ihre Voraussetzungen entzogen. Der Gate-Plan selbst bleibt als Rahmen nutzbar, benötigt aber die in §5 gelisteten Anpassungen, bevor mit Gate 5+ (bzw. der neu einzuordnenden Viewport Production) fortgefahren werden kann.

---

**Ende des Audits.** Keine Implementierung vorgenommen; keine Architektur geändert; keine neuen Gates definiert.
