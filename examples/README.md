# Examples

Beispielmodelle und kleine reproduzierbare Szenarien für Entwicklung und Tests.

## Inhalt

- **`meshes/`** — Test-/Beispiel-Assets. Aktuell: `head_basemesh.obj` (+ `.mtl`, `.blend`-Quelle),
  der Rigging-Kopf. Geteilte Ressource (AD-007) — gehört weder dem Playground noch dem
  Rigging-Experiment allein; beide (plus das Integration Lab) laden ihn von hier.
- **`loaders/`** — `obj_loader.py`: minimaler, reiner OBJ-Parser ohne Core-/Viewport-/
  pyglet-Abhängigkeit (headless testbar). Geteilt aus demselben Grund wie die Assets, die er lädt
  (AD-007) — Playground, Lab und Rigging importieren ihn von hier (`from loaders.obj_loader import ...`).

Siehe [`docs/architecture/AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md`](../docs/architecture/AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md)
für die Entscheidung dahinter.
