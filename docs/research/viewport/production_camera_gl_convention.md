# Production Camera / OpenGL Convention Investigation

**Status:** `INVESTIGATION — UNRESOLVED` (Production-Kamera-Entscheidung offen)
**Date:** 2026-09-10
**Trigger:** Erste Artist-Tests im [`playground/`](../../../playground/README.md) (Branch `experiment/artist-playground-v1`, WP-AP-01) haben den technischen Befund sichtbar gemacht.

> **Update 2026-09-10:** Der Playground hat den Befund an seiner GL-Grenze adapter-artig gelöst
> (`playground/camera.py::PlaygroundCamera`, nur `build_view_matrix()` im gluLookAt-Sinne,
> analog `LabOrbitCamera`). **Die Production-Entscheidung ist damit NICHT entschieden** — siehe
> §5. Keine Änderung an `src/mirai/viewport/camera.py`, `src/core/` oder `src/viewport/`.

> **WICHTIG:** Dies ist eine technische Investigation, KEINE beschlossene Änderung an der Production Camera.
> Es wird ausdrücklich noch NICHT entschieden, ob (1) die Production `OrbitCamera` korrigiert wird,
> (2) die GL-Ausgabe an einer Boundary adaptiert wird, oder (3) eine andere Lösung die richtige
> Architektur ist.

---

## 1. Kontext

Der Artist Playground (AP-01) verbindet die Production `OrbitCamera` direkt mit einem eigenen
pyglet-GL-Draw-Pfad (PlaygroundWindow/Shader). Der erste Artist-Lauf zeigt: Das Mesh wird im
tatsächlichen GL-Pfad vollständig weggeclippt — obwohl Mesh-Geometrie und Kamera-Framing
plausibel sind und der identische Cube im Integration Lab korrekt erscheint.

Der technische Kernbefund ist in der Integration-Lab-Reconciliation **bereits autoritativ
dokumentiert** (Single Source of Truth):

- [`experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md`](../../../experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md) — **§A.1 „Kritischer dokumentierter Befund: View-Matrix-Konvention (nur dokumentiert, NICHT behoben)"**
- [`experiments/mirai_bastel_integration_lab/lab_camera.py`](../../../experiments/mirai_bastel_integration_lab/lab_camera.py)

Dieses Dokument ergänzt die **Playground-Sicht** (Observation, Architektur-Bedeutung, offene
Fragen) und verweist für den Detail-Nachweis auf §A.1, statt ihn zu duplizieren.

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
- `src/core/` bleibt **unverändert**.
- `src/viewport/` bleibt **unverändert**.
- `OrbitCamera` wird in diesem Task **NICHT** verändert.
- `PlaygroundRenderer` bleibt gemäß
  [`docs/design/artist_playground/ARCHITECTURE_MAP.md`](../../design/artist_playground/ARCHITECTURE_MAP.md)
  ein 🔵 **WRAP**/Adapter auf den Production Viewport.
- Experiment-Code (z. B. `LabOrbitCamera`) wird **nicht automatisch** Production-Architektur.

---

## 5. Noch offen (bewusst in diesem Task NICHT entschieden)

Folgende Fragen müssen separat geprüft und entschieden werden:

1. Welche Kamera-Konvention ist tatsächlich als **Production-Konvention** beabsichtigt?
2. Welche anderen Consumer verwenden `OrbitCamera.build_view_matrix()`?
3. Ist die GL-Konvention Bestandteil der **Production Camera API** oder nur des jeweiligen **Renderers**?
4. Sollte die **Production Camera selbst** korrigiert werden?
5. Oder sollte die **GL-Boundary** die bestehende Kamerakonvention adaptieren?

Keine dieser Fragen wird in diesem Task endgültig entschieden. Bis zur Entscheidung bleibt der
Befund **UNRESOLVED.**

---

## 6. Referenzen / Navigation

- Investigation-Auslöser: [`playground/README.md`](../../../playground/README.md)
- Artist Playground Architecture Map: [`docs/design/artist_playground/ARCHITECTURE_MAP.md`](../../design/artist_playground/ARCHITECTURE_MAP.md)
- Artist Playground Roadmap: [`docs/design/artist_playground/ROADMAP.md`](../../design/artist_playground/ROADMAP.md)
- Autoritativer Detail-Befund (SSOT): [`experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md`](../../../experiments/mirai_bastel_integration_lab/docs/ARCHITECTURE_RECONCILIATION_AUDIT.md) §A.1
- Lab-Kamera-Override: [`experiments/mirai_bastel_integration_lab/lab_camera.py`](../../../experiments/mirai_bastel_integration_lab/lab_camera.py)