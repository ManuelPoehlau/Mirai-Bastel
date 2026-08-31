WP-03 ist implementiert und vollständig validiert. Hier der Abschlussbericht:

---

# WP-03 — Transform Foundation: Abschlussbericht

## 1. Änderungen

**Neue Dateien (Implementierung, bereits Teil von HEAD durch Fremd-Sweep-Commit 3745b15, siehe §6):**

| Datei | Inhalt |
|---|---|
| `experiments/mirai_bastel_core_V1/mirai_bastel_core/operations/transform.py` | Transform-Foundation: `VertexTransformCommand` (reversibler Start-/Endposition-Entry), `VertexTransformOperation` (gemeinsame Snapshot-/Commit-/Cancel-Maschinerie, fixer Pivot, Soft-Selection-Platzhalter wie `MoveOperation`), `RotateOperation` (Rodrigues, inkrementelle Winkel), `ScaleOperation` (uniform/per-Achse, multiplikativ) |
| `experiments/mirai_bastel_viewport_V1/viewport/transform_tool.py` | `TransformTool`-Basis + `RotateTool` + `ScaleTool` + `selection_pivot()`; Gesten via kumulierte Pixel-Distanz → chunking-unabhängige Zielschritte; Achs-Parameter (`axis=`/`axes=`) |

**Geänderte Dateien:**
- `mirai_bastel_core/operations/__init__.py`, `mirai_bastel_core/__init__.py` — rein additive Exporte
- `viewport/commands.py` — `ROTATE = "Rotate"`, `SCALE = "Scale"`
- `viewport/move_tool.py` — `tool_for_command()` erweitert (ROTATE→RotateTool, SCALE→ScaleTool), gleiche Routing-Stelle wie WP-02
- `viewport/default_bindings.py` — `R` → Rotate, `S` → Scale (globaler Kontext; Topology-Lab-Bindings gewinnen via Kontext-Priorität)
- `viewport/app.py` — nur Docstring-Präzisierung des gemeinsamen Begin-Pfads; **keine strukturellen Window-Änderungen nötig** (generischer `ToolManager.begin(vertex_ids=...)`/`update(dx,dy,width,height)`-Pfad von WP-02 trägt unverändert)

**Neue Tests:** `test_transform_operations.py` (19), `test_transform_tools.py` (25), `test_transform_integration.py` (14 headless Window-Pfad), `test_tool_routing.py` erweitert (+2)

**Dokumentation:** beide Experiment-READMEs aktualisiert (Bedienung R/S, Struktur, „Rotate/Scale nicht enthalten"-Aussage im Fork-README korrigiert)

## 2. Tests

| Suite | Ergebnis |
|---|---|
| Viewport-Experiment (`unittest discover`) | **88/88 OK** (58 neue WP-03 + alle WP-01A/WP-02-Regressions) |
| Core-Fork (`python -m tests.test_core`) | Alle Architekturverträge PASS |
| Produktions-Core (`python -m tests.run_core_suite`) | 29/29 unittest + Verträge **PASS**, `src/core` unverändert |
| `git diff --check` | sauber |
| Abgedeckt: | Rotate/Scale-Mathematik, fixer Pivot = Selection Center, Multi-Selection, inkrementelle Semantik (Winkel addieren/Faktoren multiplizieren), Chunking-Unabhängigkeit, No-op-Commit→kein History, Commit→genau 1 Eintrag, Cancel→exakte Wiederherstellung+kein History, Undo/Redo exakt, Achsen-Constraints, Min-Clamp, leere Selection, R/S-Aktivierung, Tool-Wechsel, Tweak-Move-Regression, Topology-Kontext-Vorrang |

## 3. Diff (Arbeitsverzeichnis vs. HEAD)

```text
 experiments/mirai_bastel_core_V1/README.md                    |  3 +-
 .../mirai_bastel_core/operations/transform.py                 | 20 ++++----
 experiments/mirai_bastel_viewport_V1/README.md                | 53 +++++++++++++++++++++-
 .../tests/test_tool_routing.py                                | 17 +++++--
 4 files changed, 74 insertions(+), 19 deletions(-)
 + 3 neue Testdateien (untracked)
```

**Kein Commit/Push durchgeführt** (wie angewiesen).

## 4. Core-Auswirkungen

**`src/core/` ist vollständig unverändert** (Production-Suite grün als Nachweis). Begründung:
- Der gefrorene V1-Vertrag (Operation-Lifecycle, generische History, `Command`-Protocol) ist für Transform **ausreichend** — es liegt keine Vertragslücke vor; `CORE_V1_FREEZE` §7 fordert eine solche für Core-Änderungen.
- Beide `move.py`-Docstrings und der Fork-README dokumentieren Rotate/Scale ausdrücklich als dem Move-Muster folgend, bewusst nicht in V1 dupliziert.
- Der Viewport-Praxistest läuft auf dem lokalen Core-Fork; eine Produktion-Platzierung wäre für den real getesteten Pfad unsichtbar. Promotion nach `src/core` bleibt eine explizite Architekturentscheidung (gleicher Fluss wie `add_edge` beim Connect-Edges-Experiment) — passend zum WP-03-Zeitraum vor der WP-01-Produktionsableitung.

## 5. Architektur

Der Zielbild-Pfad ist exakt implementiert: `Input → Command → Tool → Transform Interaction (TransformTool) → Preview (Live-State-Update, kein History) → Commit (eine Operation = eine History-Aktion) / Cancel (exakter Restore, keine History)`. Preview folgt dem dokumentierten V1-Modell (update direkt am Live-Zustand, `operation.py`); kein paralleles Undo-System; keine Topology-/Selection-Architektur vorweggenommen; keine Abstraktion über den tatsächlich getesteten Bedarf hinaus (Achsen-Constraints als Foundation-Parameter, **nicht** als interaktive Hotkeys — bewusst offen).

## 6. Wichtiger Nebenbefund — Repository hat sich während der Sitzung bewegt

Während der Arbeit sind auf `main` vier fremde Commits gelandet (`3745b15` … `b00ba3e`, Rigging-Track + ein `Phase 3C Test Execution — Final Report.md`, plus Stash `stash@{0}`). Der Commit **3745b15 hat den Arbeitsbaum eingecheckt und dabei meinen unfertigen WP-03-Zwischenstand mitgenommen** — dadurch sind die Implementierungsdateien bereits Teil von HEAD, und zwar **in defektem Zustand**: HEADs `transform.py` wirft einen `PyCompileError` (Bodyless-`_cross`, verwaistes `_length` am Dateiende). **Die verbleibende 20-Zeilen-Diff repariert genau diesen Syntaxfehler** — ohne die Reparatur ist der Fork auf `main` nicht importierbar. Fremde Änderungen wurden nicht überschrieben; die Rigging-Dateien bleiben unberührt. Empfehlung für den Review: die Reparatur zeitnah committen, da `main` aktuell einen nicht-kompilierbaren Experiment-Core enthält.

## 7. Offene Punkte

1. **Interaktive Achsen-Constraints** (X/Y/Z-Hotkeys während einer Rotation/Scale, Nutzung des vorhandenen `constraints.py`-Moduls) — UX-Entscheidung offen, Foundation/Tools bereits vorbereitet (`begin(axis=…/axes=…)`).
2. **Vereinheitlichung `MoveOperation` ↔ `VertexTransformOperation`** — bewusst nicht gemacht (WP-02-Basis unangetastet, „keine opportunistischen Core-Refactorings"); als explizite spätere Entscheidung dokumentiert.
3. **Gesten-Feinschliff** (z. B. absolute Winkel zur Pivot-Screen-Position statt kumulierter Deltas) — Tool-seitig austauschbar, ohne Foundation zu berühren.
4. **UX-Beobachtung aus WP-02** (Selection bleibt nach Tweak-Move bestehen) — laut Auftrag nicht angefasst.
5. **ROADMAP §14-Statusupdate** (WP-03 „Completed") — dem Review/Commit-Schritt vorbehalten, da erst nach Freigabe abschließend.