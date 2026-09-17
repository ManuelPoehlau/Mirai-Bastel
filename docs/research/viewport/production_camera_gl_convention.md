# Production Camera / OpenGL Convention Investigation

**Status:** `RESOLVED — Production `OrbitCamera` corrected` (siehe Update 2026-09-12)
**Date:** 2026-09-10 (investigation), resolved 2026-09-12
**Trigger:** Erste Artist-Tests im [`playground/`](../../../playground/README.md) (Branch `experiment/artist-playground-v1`, WP-AP-01) haben den technischen Befund sichtbar gemacht.

> **Update 2026-09-12 (Auflösung):** Commit `bbeef97` ("docs/core(viewport): reconcile production
> architecture and camera convention") hat `src/mirai/viewport/camera.py` geändert:
> `build_view_matrix()` nutzt jetzt `-forward` in Zeile 3 mit `tz = +dot(eye, forward)` (gluLookAt-
> Konvention) und ist damit identisch zu `LabOrbitCamera`/`PlaygroundCamera`. Regressionstest:
> `tests/test_camera_gate5_matrices.py::test_front_point_has_negative_view_z_and_positive_clip_w`.
> Die drei Fragen aus §5 sind damit beantwortet: Die Production Camera wurde korrigiert (Frage 4),
> nicht die GL-Boundary adaptiert (Frage 5). Die Lab-/Playground-Overrides (`LabOrbitCamera`,
> `PlaygroundCamera`) sind seither **redundant** (byte-identische Formel), aber noch nicht entfernt
> — ihr Entfernen ist eine offene, eigene Entscheidung (siehe Repository-Wide Structural Health
> Audit, 2026-09-17, Finding D2), keine technische Frage mehr.

> **Update 2026-09-10:** Der Playground hat den Befund an seiner GL-Grenze adapter-artig gelöst
> (`playground/camera.py::PlaygroundCamera`, nur `build_view_matrix()` im gluLookAt-Sinne,
> analog `LabOrbitCamera`) — historisch, bevor die Production-Kamera selbst korrigiert wurde.

---

## 1. Kontext

Der Artist Playground (AP-01) verbindet die Production `OrbitCamera` direkt mit einem eigenen
pyglet-GL-Draw-Pfad (PlaygroundWindow/Shader). Der erste Artist-Lauf zeigt: Das Mesh wird im
tatsächlichen GL-Pfad vollständig weggeclippt — obwohl Mesh-Geometrie und Kamera-Framing
plausibel sind und der identische Cube im Integration Lab korrekt erscheint.

Der technische Kernbefund wurde ursprünglich in der Integration-Lab-Reconciliation dokumentiert:

- [`experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md`](../../../experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md) — §A.1 „Kritischer dokumentierter Befund: View-Matrix-Konvention (nur dokumentiert, NICHT behoben)"
- [`experiments/mirai_bastel_integration_lab/lab_camera.py`](../../../experiments/mirai_bastel_integration_lab/lab_camera.py)

**Hinweis (seit 2026-09-12):** §A.1 des Reconciliation-Audits ist historisches Belegmaterial vom
Stand 2026-09-08 (vor dem Fix) und wird hier nicht mehr als aktuelle SSOT geführt — der Fund war
zum Zeitpunkt der Aufnahme korrekt, ist inzwischen aber durch `bbeef97` überholt. Das Audit-Dokument
selbst bleibt unverändert als Beleg stehen (`AGENTS.md` §6: unabhängige Reviews werden nicht
nachträglich an spätere Entscheidungen angeglichen); **dieses** Dokument hier ist ab jetzt die
aktuelle Quelle für den Kamera-Konventions-Status.

Dieses Dokument ergänzt die **Playground-Sicht** (Observation, Architektur-Bedeutung, offene
Fragen) und verweist für den historischen Detail-Nachweis auf §A.1, statt ihn zu duplizieren.

---

## 2. Beobachtung

### Playground mit Production `OrbitCamera` (`src/mirai/viewport/camera.py`)

- Mesh-Geometrie und Framing-Werte sind plausibel (headless identisch zum Integration Lab).
- Kamera-Input (Orbit/Pan/Zoom) funktioniert.
- Die tatsächliche GL-Darstellung clippt das Objekt (schwarzer Viewport / unsichtbares Mesh).
- Headless-Messung: Ein sichtbarer Punkt (Cube-Ecke) erhält **negatives `clip.w`** → komplettes Clipping.

### Integration Lab (`experiments/mirai_bastel_integration_lab/`)

- Verwendet denselben grundlegenden GL-Shader-Pfad wie der Playground.
- Verwendet jedoch `LabOrbitCamera` (Production-`OrbitCamera` + View-Matrix-Override).
- Dort ist `view.z` für Punkte vor der Kamera **negativ** und `clip.w` **positiv**.
- Objekt ist sichtbar.

---

## 3. Technischer Befund

### `src/mirai/viewport/camera.py` — Production

| Methode | Verhalten |
|---|---|
| `build_view_matrix()` | Spalten-Hauptreihenfolge, **Zeile 3 = `+forward`** (`tz = -dot(eye, forward)`). Front-Punkte liegen auf **positivem** Kamera-Z (Links-Hand-Konvention). |
| `build_projection_matrix(aspect)` | Standard-OpenGL-Perspektivprojektion, `m23 = -1.0` → **`clip.w = -view.z`** (erwartet Front-Punkte auf **negativem** Kamera-Z, gluLookAt-Konvention). |

**Kombination:** Geometrie **vor** der Kamera erhält `view.z > 0` → `clip.w < 0` → wird komplett
geclippt. Detaillierter Nachweis inkl. Zeilen: [§A.1 des Reconciliation-Audits](../../../experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md).

### `experiments/mirai_bastel_integration_lab/lab_camera.py` — Lab-Abweichung

- `LabOrbitCamera.build_view_matrix()` überschreibt die Production-Matrix mit der
  **gluLookAt-Konvention** (`-forward` in Zeile 3, `tz = +dot(eye, forward)`).
- Dadurch: Front-Punkte → `view.z < 0` → `clip.w > 0` → sichtbar.
- Picking und Kamera-Uniforms lesen dieselbe Instanz → konventionell konsistent.

### Headless-Messung (Cube-Ecke (1,1,1), identische Geometrie/Framing)

| Kamera | `view.z` | `clip.w` | Ergebnis |
|---|---|---|---|
| Production `OrbitCamera` | `+3.496` | `-3.496` | GECLIPPT (unsichtbar) |
| `LabOrbitCamera` | `-3.482` | `+3.482` | im Clip-Volumen |

---

## 4. Architektur-Bedeutung

- Der **Playground** hat den Befund sichtbar gemacht; das bedeutet nicht automatisch, dass der
  Playground fehlerhaft ist — es handelt sich möglicherweise um einen bereits vorhandenen
  **Production-Grenzfall** (siehe §A.1).
- `src/core/` bleibt unverändert.
- `src/viewport/` bleibt unverändert.
- `OrbitCamera` wurde **nicht** in diesem Investigation-Task, sondern in einem separaten, späteren
  Schritt (`bbeef97`, 2026-09-12) korrigiert — siehe Update oben.
- `PlaygroundRenderer` bleibt gemäß
  [`docs/design/artist_playground/ARCHITECTURE_MAP.md`](../../design/artist_playground/ARCHITECTURE_MAP.md)
  ein 🔵 **WRAP**/Adapter auf den Production Viewport.
- Experiment-Code (z. B. `LabOrbitCamera`) wird **nicht automatisch** Production-Architektur.

---

## 5. Damals offen, seit 2026-09-12 entschieden

Die ursprünglichen fünf Fragen (Konvention, Consumer, API- vs. Renderer-Zugehörigkeit, Fix-Ort)
wurden mit `bbeef97` beantwortet: **Die Production `OrbitCamera` selbst wurde auf die
gluLookAt-Konvention korrigiert** (nicht die GL-Boundary adaptiert). Damit ist die GL-Konvention
Bestandteil der Production Camera API, nicht nur des Renderers.

**Neu offen** (Folgefrage, kein technisches Investigation-Thema mehr, sondern eine
Cleanup-Entscheidung): Dürfen `LabOrbitCamera.build_view_matrix()` und
`PlaygroundCamera.build_view_matrix()` gelöscht werden, jetzt wo sie redundant sind? Siehe
Repository-Wide Structural Health Audit (2026-09-17), Finding D2.

---

## 6. Referenzen / Navigation

- Investigation-Auslöser: [`playground/README.md`](../../../playground/README.md)
- Artist Playground Architecture Map: [`docs/design/artist_playground/ARCHITECTURE_MAP.md`](../../design/artist_playground/ARCHITECTURE_MAP.md)
- Artist Playground Roadmap: [`docs/design/artist_playground/ROADMAP.md`](../../design/artist_playground/ROADMAP.md)
- Autoritativer Detail-Befund (SSOT): [`experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md`](../../../experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md) §A.1
- Lab-Kamera-Override: [`experiments/mirai_bastel_integration_lab/lab_camera.py`](../../../experiments/mirai_bastel_integration_lab/lab_camera.py)