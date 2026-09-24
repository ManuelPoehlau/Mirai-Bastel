# Examples

Beispielmodelle und kleine reproduzierbare Szenarien für Entwicklung und Tests.

## Inhalt

- **`meshes/`** — Test-/Beispiel-Assets. Geteilte Ressourcen (AD-007) — sie gehören weder dem
  Playground noch einem Experiment allein; Konsumenten laden sie von hier.

  | Registry-Name (`loaders.assets`) | Datei | Stand |
  |---|---|---|
  | `head_basemesh` | `head_basemesh.obj` (+ `.mtl`, `.blend`-Quelle) | 326 V / 324 Quads, geschlossen — Rigging-Kopf |
  | `man_with_shoes_basemesh` | `Man_With_Shoes_basemesh.obj` (+ `.mtl`) | 928 V / 926 Quads, geschlossen, ca. 1,88 Einheiten hoch — Charakter-Basemesh |
  | `subd_cube` | `SubD_Cube.obj` (+ `.mtl`) | 26 V / 24 Quads, geschlossen — Würfel mit je 4 Quads pro Fläche, Testasset für SubD-/Topologie-Arbeit |

- **`loaders/`** — zwei Bausteine ohne Core-/Viewport-/pyglet-Abhängigkeit (headless testbar),
  geteilt aus demselben Grund wie die Assets, die sie laden (AD-007):
  - `obj_loader.py` — minimaler, reiner OBJ-Parser (`load_obj(pfad)`, `parse_obj(text)`);
    kennt keine Assets, nur Pfade.
  - `assets.py` — die eine Stelle, an der Asset-*Namen* auf Pfade abgebildet werden
    (`load_asset("subd_cube")`, `asset_path(...)`, `asset_names()`). Damit brauchen Konsumenten
    keine eigenen Pfadkonstanten je Datei. Unbekannte Namen und fehlende Dateien fliegen laut
    (`KeyError` bzw. `ObjLoadError`).

  Import aus Konsumenten: `from loaders.obj_loader import load_obj` bzw.
  `from loaders.assets import asset_path, load_asset`.

Siehe [`docs/architecture/AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md`](../docs/architecture/AD-007-SHARED-ASSET-LOADER-OWNERSHIP.md)
für die Entscheidung dahinter (Asset + Loader als eine Kette, neutrale Ablage in `examples/`).
