# AD-035 — The sclera's colour map (Eye LookDev, M1)

**Status:** **DECIDED (Manu, 2026-11-17)**: M1 approved for implementation with decisions S-1 … S-13 (§1), the
additive Core change and scene format v12 included. **IMPLEMENTED M1 (2026-11-17, container: TESTED)**, as built in §2,
with the deviations in §5. **Reference-PC cost: NOT YET MEASURED** (§6; the command is ready). **Practical test:
pending** (§7).
**Basis:** the research and architecture audit
[`EYE_LOOKDEV_SCLERA_SURFACE_ASSESSMENT_2026-11-17.md`](../research/EYE_LOOKDEV_SCLERA_SURFACE_ASSESSMENT_2026-11-17.md)
(`main` @ `5187c31`; its §3 mapping, §6 ownership, §7 UI, §9 M1 acceptance tests). Implemented on `main` @ `5187c31`
(verified as the working branch's base and `origin/main` before the change).
**Extends:** [AD-033](AD-033-EYE-PREVIEW-IN-THE-WORKLIGHT.md) (the eye object and the eye pass), AD-026 §7 addendum /
phase 5 (scene-relative texture paths, copies in `<scene>_textures/`), [CORE_V1_FREEZE](CORE_V1_FREEZE.md) §7.1.

## Kurzfassung (Deutsch)

Jedes Auge kann jetzt ein eigenes **Lederhaut-Farbbild** haben (`EyeSpec.sclera_texture`). Das Bild zeigt das Auge **von
vorn**: Mitte = Hornhautmitte, rechts = +X, oben = +Y, der Limbus liegt fest auf ¼ der halben Bildbreite, der Bildrand
130° von der Hornhautmitte (dahinter wird die Randfarbe gehalten). Es ersetzt die Grundfarbe der Lederhaut – auf der
Lederhaut **und** im Limbusgewebe, das man durch die Hornhaut sieht, mit derselben Abbildung (keine Stufe am Ring). Nasser
Film, Spiegelungen, Lidschatten, Lidband und Iris rechnen unverändert weiter. Laden / Ersetzen / Entfernen im Eye Lab
(Abschnitt „Lederhaut“), je ein Undo-Schritt; Speichern relativ zur Szene, „Speichern unter“ kopiert das Bild nach
`<Szene>_textures/`, Vorlagen lassen es in Ruhe; Szenenformat v12 nur mit Bild. Im Eye Lab bekommen Augen keinen gelben
Auswahl-Schimmer mehr (F-1). Ohne Bild ist das Shader-Programm Zeichen für Zeichen das bisherige (Test gepinnt).
Offen: die Messung auf deinem PC (§6) und dein Praxistest (§7).

## 1. Decisions (Manu, 2026-11-17)

| # | Decision |
|---|---|
| S-1 | The limbus-anchored **front disc** (variant B): `R_L` = 0.25 of half the image width at the anatomy's limbus, the rim at θ = 130°. |
| S-2 | The optional path lives in **`EyeSpec.sclera_texture`**; scene format **v12**. |
| S-3 | The map draws in **both** tiers ("schnell" and "voll"). |
| S-4 | **No selection tint on eyes while the Eye Lab is open**; outside it the tint applies over the map as before. |
| S-5 | Each eye its own image; no automatic left/right mirroring, no mirror flag in M1. |
| S-6 | Alpha is ignored: the map is an opaque RGB colour. |
| S-7 | The map **replaces** the sclera's base colour; the material colour is the fallback (no map, or a map that is not usable). No strength slider. |
| S-8 | 1024² recommended, up to 2048² accepted; larger is refused, never loaded silently. |
| S-9 | Eye look presets leave the map untouched (like the iris image). |
| S-10 | Save As copies the map into the new scene's `<SceneName>_textures/` under its content name. |
| S-11 | Automated frontal-photo import is M2; M1 loads a prepared front-disc image. |
| S-12 | The generated synthetic map and the painting template are in the repository; personal photos stay local. |
| S-13 | Beyond the 130° rim the mapping is **clamped** (the rim colour is held). |

## 2. As built (M1)

**Core (additive; CORE_V1_FREEZE §7.1 entry 2026-11-17).** `EyeSpec.sclera_texture: str | None = None` (the 19th
field, beside `look`): `None` = no map; otherwise a non-empty string without NUL (anything else is a `ValueError`). A
plain path string like `SceneObject.texture`; what it means is decided in `src/mirai`. `to_dict` writes it only when set,
`from_dict` accepts it as optional (absent or `null` = none). `core.serialization` writes **version 12**
(`EYE_SCLERA_FORMAT_VERSION`) only when an eye has a map (else 4–11 as before) and reads 2–12; 13 is the first unknown
version, so an older build refuses a v12 file instead of dropping the map. `EyeLook`, `EyeIris`, `SceneObject` and
every other field are unchanged. `SceneObject.texture` stays the iris image.

**The mapping** (`viewport.eye_optics.sclera_st`, GLSL `SCLERA_LIB_SRC.sclera_st`, parity-tested). For an eye-local
point `p` (the sclera hit, or the cornea's entry point where the limbal tissue is shaded): ρ = |p.xy|, θ = atan(ρ, p.z),
θ_L = asin(limbus radius) (the eye's `u_theta_ring`);
r = R_L · θ / θ_L inside the ring, R_L + (1 − R_L) · (θ − θ_L) / (θ_rim − θ_L) outside, clamped to 1;
st = 0.5 + 0.5 · r · p.xy / ρ (direction (1, 0) for ρ ≤ 1e-6: at the front pole r is 0, at the back pole every
direction lands on the rim). One formula on both sides of the ring; the knot follows θ_L, so the painted limbus stays
on the anatomy's limbus when the limbus radius changes. Eye-local, so it turns with the gaze and is independent of the
camera.

**The eye pass** (`viewport.eye_pass`, `eye_shaders`). A new define `SCLERA_MAP` (program cache key + 1 bool): the
two albedo reads - the sclera's and the limbal tissue's at the cornea's entry point - read `sclera_albedo(point)` =
`mix(texture(map, sclera_st(point)).rgb, tint.rgb, tint.a)`, each at the top level of its per-triangle branch (implicit
derivatives defined; trilinear mips). No other term reads the albedo: the wet film, the reflections, the irregularity,
roughness, lid shadow, lid band, the Worklight highlight and the iris are unchanged. The map is loaded through the
shared `GLRenderStore.texture` cache (no second cache) and bound to **unit 4** with the pass's own **sampler object**
(trilinear when the loader made mips, CLAMP_TO_EDGE), so the cached texture keeps its own REPEAT parameters; sampler and
texture are unbound after the draw. A loaded map above 2048 on either side is not drawn (`SCLERA_MAX_SIZE`: a file
replaced on disk between two view syncs; the app refuses such a file on assignment). Units while an eye draws: 1 iris,
2 noise, 3 key table, 4 sclera map. Drawn in both
tiers (S-3). **Without a usable map the program is the one before AD-035, character for character** (the `#ifdef
SCLERA_MAP` blocks resolve to the old lines; `test_gl_eye_pass.py` pins every variant's source).

**The app** (`src/mirai`).
- `mirai.sclera_map` (new, stdlib): the image layout constants and hint, a header reader (PNG / JPEG / BMP, no decode),
  the size policy (S-8: `MAX_SIZE` 2048 on either side, 1024² recommended; non-square or other sizes give a note), and
  `drawable(path)` - the path when the file exists and passes the policy, cached per (path, mtime, size).
- `ObjectController.set_eye_sclera_image` / `Application.set_eye_sclera_image(path | None)`: through `set_eye`, so
  assign, replace and remove are each **one** `ObjectEyeCommand`; refused with the reason (missing, unknown format, too
  large) without a step. Duplicate, mirror copy, `replace_scene` and the morph-view twins carry the path with the spec.
- `EyeDraw` gains `sclera_texture` (only a drawable path; else None = the base colour) and `sclera_tint`.
- **S-4:** `sync_views` draws an eye untinted while `display.eye_lab` is set (colour and map; the Worklight colour for
  "preview off" too); other objects keep the tint; opening / closing the lab re-syncs the entries at once (the highlight
  signature includes the lab).
- **Storage:** on load a relative `sclera_texture` is resolved against the scene's directory; on save it is written
  relative when inside the scene directory. `_copy_iris_images` became `_copy_eye_images`: an eye's iris image **and**
  sclera map that are not in `<stem>_textures/` are copied there byte for byte under their content name
  (`texture_files.copy_into`: the source's stem + 10 hex of SHA-256; never overwrites, never deletes), and the eye is
  repointed after the file is written (no Undo step, as for the iris). A missing file keeps its path ("image not found,
  path kept: …") and the eye draws its base colour.
- **Presets:** `sclera_texture` is in `eye_presets.IMAGE_FIELDS`: never written into a preset, never applied, and a
  preset file that contains it is refused as unknown.

**Eye Lab** (`gui.eye_model`, `gui.eye_panel`): a section **"Lederhaut (Farbbild, gespeichert)"** after "Iris": the
status line ("Lederhaut: Grundfarbe (kein Bild)" / the file name / "… (nicht gefunden) - Grundfarbe" / "… (zu groß …)"
/ a size note), the full path as a tooltip, a path field with **"Lederhaut-Bild laden"** and **"Bild entfernen"**, and
the persistent hint (image = the eye from the front, limbus at ¼ of half the width, rim 130°, 1024² recommended, at most
2048², the template's folder). The compact panel "Auge" is unchanged. `PROVISIONAL` layout.

**Assets** (S-12, unchanged from the research commit): `docs/research/eye_sclera_assets_2026-11-17/` -
`front_disc_template_1024.png` (painting template: red limbus, blue 90°, black 130° rim, grey rings every 2 mm),
`synthetic_sclera_front_disc_1024.png` (generated technical test map; not a look target), `sclera_mapping_study.py`.
The GL tests and the probe use the synthetic map. `.gitignore` gains `scenes/**/sclera_custom_*` (as for
`iris_custom_*`): name personal maps `sclera_custom….png` and their copies beside a scene stay out of Git.

**Probe:** `experiments/drag_cost/probe_eye_preview.py` rows `sclera fast` / `sclera look` / `sclera iris` (= `L3` /
`look full` / `iris full` with a 1024² map on both eyes) and the column `vs base` (the map's own cost against the same
row without it); `--memory` reports a map's texture memory at 512² / 1024² / 2048².

## 3. Files

Core: `src/core/scene.py`, `src/core/serialization.py`. App: `src/mirai/sclera_map.py` (new),
`src/mirai/controllers/objects.py`, `src/mirai/application.py`, `src/mirai/eye_presets.py`. Viewport:
`src/viewport/eye_optics.py`, `src/viewport/eye_shaders.py`, `src/viewport/eye_pass.py`. GUI: `src/gui/eye_model.py`,
`src/gui/eye_panel.py`. Tests: `tests/test_eye_sclera.py` (new), `tests/test_gl_eye_pass.py`,
`tests/test_gui_imgui_window.py`, `tests/test_rig.py` (first unknown version 12 → 13). Probe:
`experiments/drag_cost/probe_eye_preview.py`. Docs: this file, CORE_V1_FREEZE, the research report's status, the
indexes.

## 4. Tests (container, 2026-11-17)

Headless `tests/test_eye_sclera.py` (18; the pass's size guard equals the app's limit): the field's contract (optional, validated, written only when set, `null` =
none, unknown keys refused); v9 / v10 / v11 written and read as before (same file on the round trip); v12 only with a
map, back to the older version without it, 13 refused, an invalid path invalidates the file; the header reader (PNG,
BMP, JPEG) and the size policy (2048² accepted, 4096² and 2049 refused, unknown format, notes); assign / replace / remove
one Undo step each, Undo / Redo restore the path, removing nothing adds no step; refusals add no step; iris image, fit,
look, iris values and relief source untouched by every sclera operation and vice versa; two eyes two maps, mirror copy
and duplicate carry the path (no flip), the scene load (`replace_scene`) and a morph-view twin; the entry carries a
usable map only (missing, or replaced on disk by a 4096² image → base colour, path kept); S-4 in and out of the Eye
Lab (the eye stays selected); save copies / writes relative / reopens absolute / copies once; Save As independent, an
existing file of the copy's name is not overwritten, Undo deletes nothing; a missing map keeps its path through save
and load and the Eye Lab says "nicht gefunden"; presets neither write, replace, remove nor restore it; the Eye Lab's
model (status texts, path field with quotes, hint).

GL `tests/test_gl_eye_pass.py` (+33, 106 in all; xvfb / Mesa llvmpipe): every variant's source without a map equals the pinned
digest of `5187c31`; the map variant carries the two reads; `sclera_st` GLSL = NumPy (both poles, beyond the rim,
points off the sphere); the disc anchored to the limbus for three limbus radii and the axes' orientation; **the map is
sampled where the NumPy twin says** - the albedo each pixel read is recovered as (M − K) / (W − K) from three frames
(a gradient map, white, black; everything not proportional to the albedo cancels) and compared per pixel with
`sclera_st` of the CPU-traced eye-local point, on the sclera and on the cornea's side of the ring, frontal at rest and
under a gaze, three-quarter at rest and under a gaze (with the wet film, irregularity, lid shadow and band), side and
back (rim held); **no step at the limbus** (neighbour pixels across the ring differ no more than neighbours elsewhere);
the synthetic map reads as painted in the Eye Lab close-up; a uniform map draws the same pixels as that base colour
without a map (L0 / L3, fast and full with look and iris values); **reflections independent of the map** (the
reflection-only frame with a black map equals the one with a black base colour, wet film at 1; the map's contribution
with the film is at most the one without it); the selection tint over the map, none = the map as it is; a missing
file draws the base colour with the program before AD-035; every map program (level × reflection × refraction × tier,
look and iris on) draws and leaves the GL state as found (no sampler or texture on unit 4, unit 0 active, the cached
texture still REPEAT). Mutation check during development: a mirrored lookup on either side of the ring fails the twin
and no-step tests. `tests/test_gui_imgui_window.py`: the Eye Lab open with the synthetic map drawn, the GL state as
found.

## 5. Deviations from the authorization (each with its reason)

1. **"Keep the normal selection outline":** objects in mode 4 have **no** selection outline in the current code; the
   selection is shown by the tint itself (`selected_color`), the outliner row and the Eye Lab's header. S-4 therefore
   removes the only in-viewport highlight of the edited eye while the lab is open; the eye stays selected (outliner,
   header, every lab action). No outline was built (a new overlay is outside M1). If an outline is wanted, it is a
   separate change.
2. **`sclera_albedo()` exists only in the `SCLERA_MAP` variant.** Routing the no-map variant through a wrapper function
   would change its source, which §6 forbids; the two reads stay textually as before there.
3. **A sampler object** (CLAMP_TO_EDGE) instead of the shared texture's REPEAT: the disc reaches the image's edge at the
   rim (and coarse mips sample beyond it); setting CLAMP on the cached texture would change it for every other user of
   the same file. No second cache.
4. **Formats for the size check:** PNG, JPEG, BMP (the header is read without decoding). Other formats pyglet could
   decode on some systems (e.g. TIFF on Windows) are refused at assignment with the reason, because S-8 forbids loading
   an image of unknown size. A non-square image is accepted with a note ("die Scheibe wird verzerrt").
5. **Copy names** keep the source's stem (`<source stem>_<hash>.png`), the iris image's existing convention, rather than
   the audit's sketched `<stem>_sclera_<hash>`.
6. **"Preview off"** (the eye drawn by the Worklight) shows the base colour, not the map: the map is part of the eye
   pass in both of its tiers; "preview off" is the Worklight's own draw and stays unchanged.
7. **The probe** puts one map (the synthetic 1024²) on both eyes; per-eye maps cost the same per pixel.

## 6. Performance and memory

**Container (Mesa llvmpipe, CPU rasteriser): a functional smoke run only, not evidence.** The probe ran end to end
(`--draws 3 --memory`); its timings are CPU-rasteriser numbers and are not reported as a cost.

**Texture memory, computed** from the GL texture's levels as loaded through the shared cache (container; the internal
format pyglet chooses is unsized `GL_RGBA`, 4 bytes per texel; mips +⅓): **512²: 1.3 MiB, 1024²: 5.3 MiB, 2048²:
21.3 MiB** per map (two eyes with separate maps: twice). The driver-reported drop of free video memory
(`GL_NVX_gpu_memory_info`) is meaningful only on the reference PC.

**Reference PC (Q9550, 9800 GTX+, Windows 10, Python 3.12.10): NOT YET MEASURED.** Target: at most about +0.2 ms GPU
per frame in the Eye Lab views (column `vs base` in the `lab` view), "fast" without a map unchanged within noise.
Commands (driver: "prefer maximum performance"):

```
python experiments/drag_cost/probe_eye_preview.py --memory
python experiments/drag_cost/probe_eye_preview.py --size 1920 1080 --memory
```

Views `head` (modelling distance), `close`, `lab` (Eye Lab frontal); rows `sclera fast` (fast tier) and `sclera look`
/ `sclera iris` (full tier). Results go to `experiments/drag_cost/RESULTS_EYE_SCLERA_REFERENCE_PC_<date>.md`. If the
target is exceeded: investigate first (mip level, sampler, the second sample on cornea pixels), never lower the
artist's resolution silently.

## 7. Praxistest für Manu (Deutsch, ca. 20 Minuten)

Vorab: dein `Gollum_Head_03` im Repository bleibt, wie es ist. Arbeite mit deiner lokalen Gollum-Szene und speichere
sie zuerst unter einem neuen Namen (z. B. `Gollum_Sclera_M1.mirai.json`, „Speichern unter“) – sobald ein Auge ein
Lederhaut-Bild hat, ist die Datei v12 und ältere Mirai-Stände lehnen sie ab. Eigene Bilder bitte `sclera_custom….png`
nennen, dann bleiben ihre Kopien neben der Szene aus Git.

1. **Testbild:** Szene öffnen, ein Auge wählen (Modus 4), „Im Eye Lab öffnen“. Im Abschnitt „Lederhaut“ steht
   „Lederhaut: Grundfarbe (kein Bild)“. Pfad zu
   `docs/research/eye_sclera_assets_2026-11-17/synthetic_sclera_front_disc_1024.png` eintragen → „Lederhaut-Bild
   laden“. Die Adern laufen vom Rand zur Mitte und enden vor dem Limbus. Strg+Z / Strg+Y: je ein Schritt.
2. **Vorlage:** `front_disc_template_1024.png` laden (= Ersetzen). Der rote Kreis muss **genau auf dem Limbus** liegen
   (frontal, „Frontal einrahmen“), der blaue Kreis ist der Äquator, der schwarze Rand liegt 130° weit hinten. Limbus-Radius
   im Eye Lab ändern: der rote Kreis wandert mit. Danach wieder das Testbild.
3. **Ansichten**, Qualität „voll“ und „schnell“: frontal nah, Dreiviertel nah, seitlich, normale Modellierdistanz. Keine
   Naht, kein Zusammenziehen, keine Farbstufe am Limbusring (zwischen dem Gewebe durch die Hornhaut und der Lederhaut).
4. **Licht:** Key-Licht mit L-Ziehen an drei Stellen (Standard, hoch links, tief rechts). Die Adern sind Farbe, kein
   Relief; Glanz und Spiegelung bleiben, wo sie waren.
5. **Nasse Reflexe an, Bild an/aus:** mit „Reflexe (Startwerte)“ das Bild entfernen und wieder laden: nur die Farbe
   unter dem Glanz ändert sich, die Spiegelungen nicht.
6. **Blick und Orbit:** Blick-Pad bewegen – die Adern drehen mit dem Auge, Lidschatten und Lidband bleiben am Kopf.
   Kamera um das Auge kreisen: das Bild bleibt am Auge.
7. **Beide Augen:** das andere Auge wählen, ein eigenes Bild laden (oder dasselbe). Beide Augen im Bild: jedes zeigt
   sein Bild; es wird nicht automatisch gespiegelt (gleiches Bild = nasal links wird beim anderen Auge temporal).
8. **Auswahl:** im Eye Lab kein gelber Schimmer auf dem Auge, Farbe = Bild. Eye Lab schließen: das gewählte Auge ist
   wieder gelblich getönt, ein nicht gewähltes zeigt das Bild unverändert.
9. **Dein Bild** (falls vorhanden, lokal): gemalt oder vorbereitet im Frontscheiben-Layout. Ziel: organisches Gewebe,
   feine Adern, natürliche Farbvariation – nicht blutunterlaufen, nicht schmutzig oder rau. Das Testbild ist **kein**
   Gollum-Look.
10. **Speichern / Öffnen:** Strg+S. In der Statuszeile „sclera image copied to <Name>_textures/“; Szene schließen und
    wieder öffnen: das Bild ist da. Eine Look-Vorlage anwenden: das Bild bleibt. Datei umbenennen/verschieben, Szene
    öffnen: „Lederhaut: … (nicht gefunden) - Grundfarbe“, der Pfad bleibt gespeichert.
11. **Messung:** die beiden Befehle aus §6 auf dem Referenz-PC, Ausgabe an mich.

Verdikt: KEEP / ITERATE / REJECT, gern je Punkt.

## 8. Not in M1 (explicit non-goals, unchanged)

Frontal-photo import / de-warping, landmark detection, lighting removal (M2, S-11); normal or roughness maps; alpha /
transparency; a strength slider; automatic or flagged left/right mirroring; an image editor or layer system; procedural
vessels; sclera geometry; iris / pupil / cornea rendering; shadow, SSS or transmission systems; Worklight, morph, rig
and skinning changes. M3 candidates only on a visible need: anisotropic filtering on the map, S3TC compression.
