# Alpha Brush & Stroke System — Architecture and UX Proposal for AD-037 Phase 4 (2026-11-25)

**Status:** **PROPOSAL — research and architecture only; decisions P-18 … P-28 DECIDED (Manu, 2026-11-25: „P-18 bis P-28 zugestimmt“), §10. Slice 4a BUILT 2026-11-25: [AD-037 §12](../architecture/AD-037-TEXTURE-PAINT.md) (the wrap projection of §4.3 built as its fallback; deviations there).** No change to `src/`, `tests/`, the keymap,
the scene format or the dependencies. Every value marked `PROVISIONAL` is an agent proposal; decisions P-18 … P-28
(§10) are decided as recommended (Manu, 2026-11-25).
**State audited:** `main` @ `e583cee` (AD-037 Phases 1–3 built; P-8 lifted 2026-11-25).
**Brief:** Manu, 2026-11-25, „AD-037 Phase 4 — Alpha-Based Brush & Stroke System, Architecture and UX Assessment —
Planning Only“ (sections 1–10).
**Decided in this session (Manu, 2026-11-25):** user alphas and presets live in `~/.mirai_bastel/paint/` (not in the
repo); the built-in starter alphas come from a committed procedural generator, CC0 alphas maybe later with a checked,
recorded licence per file.
**Review:** an external review (ChatGPT, forwarded by Manu 2026-11-25) of the plan behind this report is archived
verbatim in [`ALPHA_BRUSH_STROKE_SYSTEM_PROPOSAL_2026-11-25_REVIEW_CHATGPT_001.md`](ALPHA_BRUSH_STROKE_SYSTEM_PROPOSAL_2026-11-25_REVIEW_CHATGPT_001.md).
Its six corrections are folded in (§4.3 curvature validation, §4.4 Kreismaske default, §5.4 bounded release, §5.1
terms, §6.3 import modes, §6.5 generator contact sheet, §9 test alphas in 4a); its decision recommendations stand in
§10 as recommendations, not decisions.
**Basis:** [AD-037](../architecture/AD-037-TEXTURE-PAINT.md) (§10 the Paint Room, §11 layers),
[Texture Paint audit](TEXTURE_PAINT_ROOM_ARCHITECTURE_AUDIT_2026-11-18.md) (§4.2 principles, §6 brush integration,
§9 UX, §10 roadmap), [Brush research](BRUSH_SYSTEM_FEASIBILITY_AND_ARCHITECTURE_RESEARCH_2026-11-18.md) (§6 layer A),
[AD-039](../architecture/AD-039-LOOKDEV-P3.md) §10 (maps as paths; painted channels a later AD-037 phase).

**Labels.** **[V]** verified in the code at `e583cee` (file:line) · **[C]** measured in a cloud container (taken from
AD-037 §10.7, nothing new measured for this report) · **[RPC]** reference PC result already in the repo ·
**[H]** assumption or estimate (reference-PC estimates = [C] × 3, the factor of the 2026-11-10 audit) · **[O]** an
Artist decision for Manu · **[E]** established practice in other tools (named).

---

## Kurzfassung für Manu (Deutsch)

- **Kein Neubau.** Texel-Karte, Treffer, Fußabdruck, Strich-Puffer, Kacheln, Live-Textur, Undo, Esc, Spiegeln, Naht-
  Auffüllung und Speichern bleiben genau so. Neu kommt eine Schicht **zwischen** Mausweg und Pixel-Schreiben dazu:
  *wo* gestempelt wird (Strich), *welche Form* der Stempel hat (Alpha) und *wie viele* (Einzeln / Spray).
- **Vier getrennte Begriffe:** **Alpha** = das Graustufenbild (die Form). **Pinsel** = gespeicherte Einstellungen
  (Alpha, Radius, Deckkraft, Fluss, Abstand, Streuung …). **Strich** = wie die Stempel entlang Deiner Bewegung verteilt
  werden. **Mal-Kanal** = welches Bild sich ändert – in Phase 4 nur die Farbe (Albedo). Rauheit/Normal kommen später,
  passen aber schon in das Modell (der Stempel liefert nur „wie viel“, nicht „welche Farbe“).
- **Wie das Alpha auf die Haut kommt:** Am Stempelpunkt wird eine kleine Tangentialebene der Oberfläche bestimmt
  (gemittelte Normale der inneren Hälfte des Stempels); jeder Pixel im Umkreis bekommt dort eine 2D-Koordinate und
  liest das Alpha. Weil das auf der echten 3D-Fläche geschieht, läuft ein Stempel ohne Bruch über UV-Nähte und
  funktioniert auf Käfig, SubD, Morph-Mischung und Pose. Gegen Durchmalen und Verzerrung: der bestehende
  Blickrichtungs-Test, ein Tiefenfenster und ein Ausblenden an steilen Flanken. **Ob das an Nase, Lippen, Mundwinkel,
  Lid und Naht stabil bleibt, wird in 4a gemessen und Dir als Bildbogen gezeigt** – nicht vorausgesetzt.
- **Abstand** wird in Weltmaß entlang des Strichs gemessen (nicht mehr in Bildschirm-Pixeln) und ist einstellbar.
  **Streuung** = Abweichung von der Strichlinie. **Spray** = mehrere kleine Stempel in der Pinselfläche. Schnelle
  Striche bekommen keine Lücken mehr: die Stempel kommen in eine Warteschlange mit Zeitbudget pro Bild; beim Loslassen
  wird der kleine Rest über die nächsten Bilder fertig gemalt – nie ein Einfrieren im Loslassen.
- **Zufall ist reproduzierbar:** ein Zufallswert je Strich; jeder Stempel leitet seine Zufallswerte aus seiner Nummer
  ab. Wie schnell Du ziehst oder wie die Bilder aufgeteilt werden, ändert das Muster nicht. Undo/Redo stellen die
  gespeicherten Pixel her, nichts wird neu gewürfelt.
- **Bibliothek:** eingebaute Alphas und Pinsel im Repo (vom Generator erzeugt, erst nach Deinem Blick auf einen
  Bildbogen übernommen), Deine eigenen in `~/.mirai_bastel/paint/`. Szenen speichern nie Alphas – Striche sind Pixel.
  Fehlt ein Alpha, malt der Pinsel rund und sagt es; der Verweis bleibt erhalten.
- **Bedienung:** eine Pinsel-Zeile mit Vorschau öffnet eine Auswahl (Pinsel / Alphas, Kategorien, Favoriten, Suche,
  Import). Darunter nur, was zum gewählten Pinsel gehört; „Strich“, „Streuung“, „Spray“ sind eingeklappt. **Keine neue
  Taste.**
- **Reihenfolge:** 4a Alpha-Stempel + Projektion + Abstand + Warteschlange (mit ein paar Test-Alphas zum Ausprobieren am
  Gollum-Kopf) → 4b Zufall, Streuung, Spray → 4c Bibliothek, Presets, Import, Starter-Sammlung. Jede Stufe mit
  Leistungs-Grenzen für Deinen PC und einem Praxistest.
- **Alpha ist eine Eigenschaft der Pinselspitze**, kein eigener Pinsel-Modus: rund (wie heute) oder Alpha; Einzeln /
  Spray sind davon unabhängig. So gibt es Abstand, Zufall, Streuung und Spiegeln nur einmal.
- **Deine Entscheidungen:** P-18 … P-28 in §10 — **zugestimmt 2026-11-25**.

---

## 0. Answers to the brief's questions (§9) at a glance

| Question | Short answer | Section |
|---|---|---|
| What can be reused directly? | The whole paint foundation: gather, stroke buffer, blends, recorder/Undo, seam pad, mirror, tile composite and upload, surfaces for cage/SubD/morph/pose, PNG codec, preset and thumbnail patterns | §1 |
| What needs extending or replacing? | Extend `BrushSettings` and `_dab`; replace screen-px `SPACING` with world arc length and the 24-dab spread with a bounded stamp queue | §2 |
| Data model? | Alpha · Brush (preset) · Stroke (dynamics + runtime state) · Paint channel (target), four separate types | §3 |
| Alpha projection and sampling? | Per-placement planar tangent frame from an inner-disc normal, depth window, facing fade, uint8 mip chain, bilinear, vectorised | §4 |
| Alpha as a brush mode or a stamp type? | Neither: a **tip** property (round tip or alpha tip); Single / Spray are emitters, orthogonal to the tip | §4.7 |
| Spacing, randomisation, scatter, spray? | One pipeline: path sampler → placements → emitter (Single/Spray) → cluster evaluation in one gather → order-independent combine; counter-based RNG | §5 |
| Alpha assets and presets? | Built-ins in the repo, user assets in `~/.mirai_bastel/paint/`, hash IDs, JSON presets, LRU cache, lazy thumbnails | §6 |
| UI? | Five areas, a picker popup, collapsed stroke sections, no new keys | §7 |
| Reference-PC risks? | CPU dab cost at large radii and dense spray; release backlog; thumbnail and tile uploads are small | §8 |
| First, and what can wait? | 4a → 4b → 4c; 4d (colour jitter, export bundle, CC0, wrap projection) later | §9 |

---

## 1. What is reused directly [V]

| Component | Where | Role in Phase 4 |
|---|---|---|
| Gather of texels around a point, on the shown surface | `PaintSurface.footprint` `src/mirai/paint/surface.py:241`; cached float32 texel surface points `:173`; facing test `FACING_MIN` `:36` | The one gather per placement. It already returns the texels within a world radius, culled by triangle clusters, only on triangles facing the hit's way. Phase 4 only re-expresses the gathered points in a local 2D frame |
| Surface hit | `PaintSurface.hit` `surface.py:206` | Placement centres; unchanged |
| Stroke buffer (opacity vs. flow) | `PaintStroke.dab` `src/mirai/paint/brush.py:181`, accumulation `:192`, opacity cap `:194` | `S ← S + (1−S)·flow·c` is a probabilistic OR: **order-independent**. K stamps of one placement combine as `S ← 1 − (1−S)·Π(1 − flowₖ·cₖ)`, which is one write per placement, the same result in any order (§5.6) |
| Blends | `blend_paint` `brush.py:145`, `blend_erase` `:160` | The albedo channel's write; unchanged |
| Exact Esc, one Undo step per stroke | `StrokeRecorder` `src/mirai/paint/store.py:343` (`write_texels` `:375`, `cancel` `:387`, `commit` `:400`), `PaintStrokeCommand` `:410` | Undo/Redo restore **pixels**; they never re-run the stroke, so randomness cannot change on Undo/Redo |
| Seam padding | `seam_pad` `surface.py:353`, `pad_width` `:41`, run at release `paint_room.py:550` | Unchanged; runs when the queue is empty (§5.4) |
| Mirror | `mirror` `surface.py:341`, `_mirror_definition` in the controller | The reflected placement; Phase 4 also reflects the frame's handedness (§5.7) |
| Incremental display | `PaintDisplay.update` `src/mirai/paint/display.py:265`, called per frame `src/mirai/application.py:7009` | Dirty tiles only, never a full recomposite; spray only touches more tiles |
| Shown surface: cage, SubD, morph mix, pose | `PaintRoomController.surface` `src/mirai/controllers/paint_room.py:250`; texel map reads any position source (`TexelMap` `texel_map.py:235`, `surface_points` `:558`) | The frame is computed from the shown positions, so Phase 4 inherits P-8/P-10 behaviour |
| Falloff curves | `falloff` `brush.py:135` | The round tip unchanged; the optional Kreismaske of an alpha tip |
| PNG decode / luminance | `decode_png` `src/mirai/iris_import.py:157` (8/16-bit, grey, palette; 16 bit keeps the high byte), `read_rgba` `:223`, `has_alpha` `:237`, `luminance` `:244` (Rec.709 `LUMA` `:52`) | Alpha import (§6.3) |
| Decoded-image cache pattern | `paint.files._CACHE` `src/mirai/paint/files.py:50`, `read_image` `:60` | The alpha LRU follows the same (path, mtime, size) key idea |
| Content hash | `texture_files.content_hash` `src/mirai/texture_files.py:81` | User alpha IDs (§6.2) |
| Preset files | `eye_presets.load_presets` `src/mirai/eye_presets.py:110` (bad files skipped with a reason), `file_name` `:131`, atomic `save_preset` `:139` | The pattern for brush presets (not the module) |
| Per-user state folder | `state_dir=Path.home() / ".mirai_bastel"` `src/main.py:943` | `~/.mirai_bastel/paint/` (Manu 2026-11-25) |
| ImGui image from pixels | `EyePanel._set_texture` `src/gui/eye_panel.py:306`, `imgui.image(ImTextureRef)` `:395` | Thumbnails and the import preview |
| File browser | `gui.file_browser` / `LastDirs` purpose `image` | Alpha import |
| Cursor overlay | `_show_cursor` `paint_room.py:435` (`set_tool_overlay(segments=…)`) | An oriented rectangle for alpha tips, drawn as segments: no new GL |

**Not reused from the Brush research:** the Soft field, seeds and position plans. Layer A's *semantics* are shared
(sampling along the path, the hit, spacing relative to the radius, cursor, lifecycle), as the audit §6.1 said; the alpha,
emitters, jitter and the coverage combine are paint-specific and stay in `mirai/paint/`.

## 2. What is extended or replaced

**Extended**
- `BrushSettings` (`brush.py:74`) gains two frozen sub-objects, `tip: TipSettings` and `dynamics: StrokeDynamics`,
  with defaults that mean "today's round brush". All existing fields, `with_`, `status_text` and the panel's calls keep
  working.
- `PaintRoomController._dab` (`paint_room.py:537`) becomes "evaluate one placement cluster" (§5.5), which calls the
  same `PaintStroke` and `footprint`.

**Replaced**
- `brush.SPACING = 0.25` (`brush.py:44`), a constant in screen pixels (`paint_room.py:516`) → a brush parameter in
  **world arc length** (§5.2).
- The 24-dab cap that spreads the remainder evenly (`MAX_DABS_PER_EVENT` `paint_room.py:73`, `:522`–`:532`). A fast
  stroke then stretches the spacing and leaves gaps. It is replaced by a **stamp queue with a bounded backlog** (§5.4).

**New modules (proposed names)**

| Module | Content | Depends on |
|---|---|---|
| `mirai/paint/alpha.py` | `AlphaImage`, the mip chain, bilinear sampling, import normalisation | NumPy, `iris_import` |
| `mirai/paint/stamp.py` | the placement frame, cluster evaluation, coverage combine | `surface`, `alpha` |
| `mirai/paint/dynamics.py` | `StrokeDynamics`, `StrokeState`, the path sampler and queue, the emitters, counter-based RNG | `stamp` |
| `mirai/paint/library.py` | built-in and user alphas and presets on disk, IDs, resolution, favourites | `alpha`, stdlib JSON |
| `gui/brush_picker_model.py` / `gui/brush_picker.py` | the picker's headless logic / its drawing (AD-030 split) | `library` |

**Regression gate (from the first commit of 4a):** the new pipeline with no alpha, one stamp and no jitter must
reproduce today's dab **bit for bit** (an equivalence test against the current `_dab` on the Gollum head, cage and SubD
1, with and without mirror).

## 3. Data model — four separate concepts (brief §8)

```
Alpha  (shape)            Brush (reusable settings)                Stroke (distribution)          Paint channel (target)
───────────────           ─────────────────────────                ─────────────────────          ──────────────────────
AlphaImage                BrushPreset (JSON, scene-independent)    StrokeDynamics (in the brush)   PaintTarget
 id, name, category        name, category                           spacing                         "albedo": blend_paint /
 source builtin|user       tip: TipSettings                         emitter single|spray              blend_erase on the
 pixels uint8 (h, w)         alpha ref {id, name, hash} | None        density, stamp size            active layer (today)
 mips  uint8 chain           source mode, invert, contrast            orientation mode + offset     later: roughness,
 aspect                      kreismaske                               jitter rotation/scale/flow       normal, translucency
 immutable, cached         radius %, opacity, flow,                   (colour: 4d)                   (AD-039 §10) - not
                           hardness, curve                          scatter along/across             in Phase 4
                           dynamics: StrokeDynamics
                           NOT: colour, tool, mirror, layer,      StrokeState (runtime only)
                                channel (session state)            seed, placement counter,
                                                                    arc-length remainder,
                                                                    smoothed direction, queue
```

- **Coverage is the interface.** The stamp engine returns `(texels, coverage)` with scalar coverage only. The paint
  channel decides what that coverage does: the albedo channel calls `blend_paint`/`blend_erase` as today. A later
  roughness channel would blend a grey value into its own stack (AD-039 §10: "a channel-aware Paint Room") without
  touching alpha, brush or stroke. Phase 4 builds only the albedo target.
- **Session state stays out of the preset:** colour, tool (Paint/Erase), mirror, active layer and channel belong to
  the room. A preset is used for painting and erasing alike.
- **Out of scope (brief §8):** vertex paint, weight paint, a sculpt framework.

## 4. Alpha projection and stamp sampling

### 4.1 Frame per placement

At each placement centre `c` (a surface hit):
1. **Gather** with `footprint(c, R, facing)`, where `R = r · √(1 + aspect²) · scale_max + scatter_reach`, so a rotated
   rectangular alpha's corners are not clipped (`r` = the world radius of P-7).
2. **Normal `n`:** the area-weighted mean of the triangle normals in an **inner disc** (`PROVISIONAL` 0.5 r around `c`),
   not the hit triangle's normal. On the cage and on SubD 1 the hit triangle is a facet, and its normal jumps from facet
   to facet, which would rotate and shear successive stamps. Not the whole stamp's mean either: a stamp reaching over the
   nose ridge would tilt its own frame. The triangle normals exist (`_tri_normal`, `surface.py`); the inner disc reuses
   the gather.
3. **Tangent `t`** from the orientation mode (§5.3), projected into the plane ⟂ `n` and normalised; `b = n × t`.
4. **Local coordinates** of every gathered texel point `p`: `a = (p−c)·t / r`, `β = (p−c)·b / r`, `h = (p−c)·n / r`.

This is the planar "tangent" projection of the established painters [E: Substance Painter's brush alignment "Tangent |
Planar"; Mudbox and ZBrush stamp the alpha in the plane of the surface under the cursor]. It is evaluated on the true
3D surface, so **a stamp crosses UV seams without a break** (texels of both islands are gathered by their 3D position,
audit principle 3).

### 4.2 Against projection through the surface and stretching
- **Facing test** (existing, `FACING_MIN`): triangles facing away from the hit are not gathered (the inside of a lid or a lip).
- **Depth window:** `|h| ≤ h_max` (`PROVISIONAL` 0.5) with a soft edge. It stops a stamp reaching a nearby surface
  that faces the same way (the lower lip under the upper lip, the nostril wing over the cheek).
- **Facing fade:** the coverage is multiplied by `smoothstep(f0, f1, n · n_tri)` (`PROVISIONAL` f0 = 0.2, f1 = 0.5). Where
  the surface turns steeply away from the frame, the planar projection would smear the alpha by 1/cos; the fade lets it
  fade out instead.

### 4.3 Curvature validation — part of 4a's acceptance, not an assumption (review point 1)

Planar projection is exact on flat skin and stretches where the surface curves within the stamp. Whether the inner-disc
frame, the depth window and the fade keep that acceptable on the Gollum head is **measured in 4a**, at fixed probe
placements, on the cage and SubD 1:
- the nose tip and ridge, a nostril wing, the lip edge, a corner of the mouth, the cheek, a lid, and a point on the UV seam.

Automated metrics, run as tests and a probe row:
- **Stretch:** the stamp's painted area and its principal-axis aspect on the surface, compared with the planar ideal
  (π r² and the alpha's aspect for a round alpha). `PROVISIONAL` gate: area within ±25 %, aspect ≤ 1.3 at 3 % radius.
- **Frame jump:** the angle change of `n` and `t` between successive placements of a scripted stroke across the nose
  ridge and over the lip edge. `PROVISIONAL` gate: ≤ 15° per placement at 100 % spacing.
- **Leak:** no texel is painted on a surface behind the stamp (the inner lip, the inside of the nostril), checked
  against the texel map.
- **Seam:** a stamp centred on the seam paints both islands with coverage continuous in 3D (texel test; the
  Phase 2 tests already pin this for the round dab).

Manu gets a **contact sheet**: renders of each probe region with a test alpha (pores, a vein, a scratch), for the visual
check (AGENTS.md §7a: feel and visual quality are the Artist's).
**Fallback**, documented now: if a region fails, a per-placement **wrap projection** becomes a 4a sub-step instead of
"later". The wrap projection uses geodesic polar coordinates over the gathered triangles [E: Substance "Tangent | Wrap";
the discrete exponential map]. It costs more per placement and is therefore not the default.

### 4.4 Sampling the alpha
- **Representation:** uint8 grey `(h, w)`, white = paint, with a **mip chain** (2×2 box halving down to 4 px) built once
  at load.
- **Level choice** per placement: the stamp's diameter in texels is `d ≈ 2·√(n_inside/π)` from the gather count. The
  level is the one whose size is closest to `d` (`level = clamp(log2(alpha_size / d), 0, last)`). A 512² pore alpha
  stamped over 20 texels would alias into noise without it.
- **Bilinear** on that level, vectorised over the gathered texels: four `take`s and a lerp; uint8 is converted to float32
  only for the gathered texels. Outside the alpha's rectangle the value is 0.
- **Coverage per stamp:**

  `c = alpha(a′, β′) · [Kreismaske ? falloff(x, hardness, curve) : 1] · facing_fade · depth_window`,

  where `(a′, β′)` are the local coordinates rotated by the stamp's angle and scaled by its scale and aspect, and `x` is
  the existing `d / r`.
- **Kreismaske off by default for imported alphas (review point 2):** an alpha defines its own shape (a vein, a scar, a
  scratch reaches to its rectangle's ends); a circular mask would cut it. It can be switched on per brush. The import
  card warns when an alpha's border is not black (a visible square edge). **The round tip (no alpha) keeps today's
  falloff unchanged.**
- **Radius:** the world radius (P-7) is the half-extent of the alpha's **long** side; the short side follows the image's
  aspect. Radius steps, Shift+wheel and the cursor stay; the cursor draws the oriented rectangle (plus the circle,
  dimmed) for an alpha tip.
- **Opacity, flow, falloff together:** coverage → `flow · flow_jitter` per stamp into the stroke buffer → the layer
  shows `opacity · S` (the Phase 2 rule). Opacity stays the per-stroke cap. **"Opacity jitter" is a per-stamp flow
  jitter** (labelled "Deckkraft-Streuung (pro Stempel)").
- **Texel density across UV islands** (×3.4 spread on the Gollum head, audit §2.2) changes only which mip fits; the
  level is chosen per placement from all gathered texels. Documented limitation, no visible break expected [H].

### 4.5 Surfaces (and what stays untouched)
**Unaffected by Phase 4** (brief §7):
- symmetry (the mirror cluster, §5.7);
- seam padding (runs at the end of the stroke as today);
- picking and the surface hit (`PaintSurface.hit` unchanged);
- Pick (§4.7);
- scene persistence (no format change: strokes stay layer pixels; brushes and alphas are never saved in a scene).

Cage, SubD (the shown level, P-10), a morph mix and a pose (P-8) all reach the gather as positions of the same texel map.
The frame is computed from the shown positions, so an alpha is painted in the shape the artist sees. Nothing in Phase 4
depends on which surface it is.

### 4.6 Not chosen
- **Camera (screen) projection** for brushes: it stretches at grazing angles and depends on the view. It belongs to the
  later **stencil / image projection** feature (audit §10 Phase 4 list), not to brushes.
- **Pre-rasterised transformed stamps** (a cached stamp image per rotation/scale): rotation and scale jitter differ per
  stamp, so the cache would rarely hit. Direct sampling in local coordinates is O(texels) either way.

### 4.7 Alpha stamping: a tip property, not a separate brush mode (brief §2, last question)
- **Recommendation:** the alpha is a property of the **tip** (`TipSettings.alpha`), and every brush has a tip: the
  **round tip** (no alpha: today's falloff) or an **alpha tip**. The pipeline is the same for both. Stroke modes
  (Single / Spray) are **emitters**, orthogonal to the tip: a round spray and an alpha single stamp are equally valid.
- **Why not "alpha mode" as a separate brush type:** spacing, jitter, scatter, spray, mirror and the opacity/flow rule
  would all have to exist twice, the "disconnected special cases" the brief warns against. The equivalence gate (§2)
  shows that the round tip is just the case "no alpha".
- **Extensible:** a later stamp type (a procedural tip, a texture-colour stamp, a stencil) is another tip kind that
  returns coverage (and, for a colour stamp, a colour) per local coordinate. The stroke and the channel do not change.
- Tools stay separate from tips: Paint and Erase use any tip; **Pick (eyedropper) does not use the tip at all and stays
  unchanged**.

## 5. Stroke engine — spacing, randomisation, scatter, spray

### 5.1 Terms (review point 4; the UI tooltips use these exact definitions)

| Term (UI) | Meaning | Unit |
|---|---|---|
| **Abstand** (spacing) | distance between successive **placements along the stroke** | % of the stamp diameter, world arc length |
| **Streuung** (scatter) | offset of each stamp **from the stroke line**: "quer" = across the stroke (the brief's *horizontal* scatter, perpendicular to the path), "längs" = along it (the brief's *vertical* scatter, forward/back on the path); two separate sliders | multiples of the radius |
| **Spray** | **several small stamps inside the brush disc** at each placement | density (stamps per placement), stamp size (% of the radius), intensity (the spray stamps' flow, % of the brush flow) |
| **Zufall** (jitter) | per-stamp variation of rotation, scale, flow (and later colour) | ± degrees / ± % |
| **Ausrichtung** (orientation) | where a stamp's "up" points | mode + offset |

### 5.2 Path sampler and spacing
- Between two input events the screen segment is sampled finely, and each sample is hit on the shown surface (as today).
  Successive hits form a **surface path**; its **world arc length** places the placements every
  `spacing · 2r · scale` (`PROVISIONAL` range 2–300 %; default 25 % for the round tip, about today's look at a frontal
  view; about 100 % for alpha brushes).
- The arc-length remainder is carried across events (`StrokeState`), so the spacing is exact across event boundaries.
- **Why world arc length** (P-18): the radius is already world (P-7). Screen spacing makes the stamp density change with
  zoom and viewing angle; world spacing keeps a pore brush's density on the skin constant.
- A hit gap (the path leaves the object) ends the run; the next hit starts a new run with the remainder reset
  (no stamp interpolated across the gap).

### 5.3 Orientation
- **Strich folgen** (default, P-21): `t` = the path tangent at the placement, projected into the plane and smoothed
  (exponential average over the last placements, `PROVISIONAL` α = 0.5) so mouse jitter does not rotate the stamps. The
  first placement of a stroke waits until the path has a direction (one spacing of movement); a click without movement
  uses the view-fixed rule.
- **Ansicht** (fixed to the view): `t` = the camera's screen-up projected into the plane (the established "camera"
  alignment [E]).
- **Fläche** (fixed to the surface): `t` = the UV-u tangent at the hit (∂p/∂u of the hit triangle), stable on the model
  whatever the view.
- **Zufall:** a random angle per stamp.
- Plus an **angle offset** and **rotation jitter** (± degrees) for every mode.

### 5.4 The stamp queue with a bounded backlog (review point 3)
- The path sampler **produces** placements; a per-frame **consumer** evaluates them within a time budget (`PROVISIONAL`
  10 ms per frame), called from the frame update next to `paint_display.update()` (`application.py:7009`). A fast
  stroke therefore never stretches the spacing (no gaps) and never blocks a frame for long.
- **Bounded backlog:** the queue holds at most `PROVISIONAL` ≈ 150 ms of estimated work, estimated from the running mean
  cost per placement. While it is full, the sampler pauses reading new path samples: the paint visibly trails the cursor
  on a very fast stroke and catches up (catch-up, [E] Krita's stroke queue behaves similarly). Work never piles up.
- **Release never evaluates the queue inside the event.** The stroke enters a short **finishing** state: the
  remaining (bounded) queue is drained over the next frames; then the seams are padded and the History step is pushed
  (today's `end` logic). While finishing, a new press, Undo/Redo and the SubD keys wait, as they do while stroking
  (`_NOT_WHILE_STROKING`). Esc in the finishing state drops the queue and restores the stroke exactly
  (`StrokeRecorder.cancel`).
- Gates: release → History step ≤ 250 ms; no frame above 50 ms during finishing (RPC).

### 5.5 Emitters and the cluster evaluation
- **Single:** one stamp per placement, offset by scatter.
- **Spray:** `N` stamps per placement (density), each of size `s · r` (`PROVISIONAL` s = 10–30 %), uniformly placed in the
  brush disc (area-uniform: `ρ = r·√u`), each with flow `flow · intensity · flow_jitter`. A **click without movement**
  emits one placement (one spray burst); holding still adds nothing (no time-based emission). A time-based "airbrush"
  would make the pattern depend on timing, against §5.7.
- **One gather per placement for all its stamps.** The cluster's texels get their local `(a, β, h)` once. Per stamp, only
  the texels inside that stamp's own bounding square are selected (a boolean mask on `(a, β)`), the alpha is sampled
  there, and `1 − flowₖ·cₖ` is multiplied into a per-cluster product. The loop runs over stamps (`K ≤ 64`,
  `PROVISIONAL` cap), **never over texels**.
- Scattered and spray stamps lie in the placement's tangent plane. That is a planar approximation over the cluster, so
  scatter is capped (`PROVISIONAL` 2 r) and spray stays inside the disc.

### 5.6 Combining stamps in the stroke buffer
`PaintStroke.dab` today does `S ← S + (1 − S)·flow·c`. For a cluster, the product `P = Π(1 − flowₖ·cₖ)` per texel gives
`S ← 1 − (1 − S)·P`: **one** `write_texels` per cluster, identical to applying the stamps one by one in any order
(floating-point rounding aside; pinned by a test with a tolerance and bit-identical for K = 1). The mirror cluster joins
the same write (`merge_coverage` takes the larger coverage at the plane, as today).

### 5.7 Determinism (brief §7)
- **Where the seed lives:** drawn at stroke begin, stored in `StrokeState` and in the stroke's `PaintStrokeCommand`
  (for diagnostics and replay tests). It is **not** stored in the scene: the scene stores pixels.
- **Counter-based randomness:** the random values of placement `i`, stamp `k` come from
  `np.random.Generator(PCG64(SeedSequence([seed, i, k])))` (or one generator per placement that draws a fixed number of
  values in a fixed order). They depend only on `(seed, i, k)`, so **mouse speed, event rate, queue chunking and frame
  timing cannot change the pattern**. Placements themselves are defined by arc length, not by time.
- **Undo/Redo** restore the recorded tiles (`PaintStrokeCommand`) and never re-run the RNG.
- **Mirror:** the mirrored cluster uses the **same** random values with the frame's handedness flipped: the reflected
  frame `(t′, b′, n′)` comes from `mirror()`. A scattered stamp at `+β` lands at the mirrored position, and an asymmetric
  alpha appears mirrored. The result is symmetric, which is what symmetric painting means.
- **Replay test:** the same recorded hit samples + the same seed give identical pixels for budgets of 1 ms, 10 ms and
  unlimited.

### 5.8 Colour variation (later slice, 4d)
Colour jitter breaks the stroke buffer's single colour: each stamp would lay down its own colour. That needs a per-texel
**stroke colour buffer** (float16 RGB, allocated lazily per touched 256² tile, ≈ 0.4 MiB per tile), blended
"over" in stamp order. The data model reserves the fields (`jitter.colour_hsv`); the buffer comes in 4d.

### 5.9 Shared and mode-specific settings

| Setting | Round tip | Alpha tip | Spray |
|---|:-:|:-:|:-:|
| radius, opacity, flow | ✓ | ✓ | ✓ |
| hardness, curve | ✓ | only with Kreismaske | only with Kreismaske |
| alpha, source mode, invert, contrast, Kreismaske | – | ✓ | ✓ (per stamp) |
| spacing | ✓ | ✓ | ✓ |
| orientation, rotation jitter | – | ✓ | ✓ |
| scale jitter, flow jitter, scatter | ✓ | ✓ | ✓ |
| density, stamp size | – | – | ✓ |

Pressure (P-15: no tablet) and lazy mouse / stroke smoothing stay out of Phase 4. Both would plug into the path sampler
later without changing the model.

## 6. Alpha assets and brush presets

### 6.1 Where things live (Manu 2026-11-25: user assets in `~/.mirai_bastel/paint/`)
```
repo (built-in, read-only, in git)              ~/.mirai_bastel/paint/ (user, not in git, independent of scenes)
assets/paint/alphas/<category>/<stem>.png        alphas/<slug>_<hash12>.png      (normalised 8-bit grey)
assets/paint/brushes/<slug>.json                 brushes/<slug>.json
assets/paint/LICENSES.md                         library.json   (favourites, user categories, last brush)
tools/make_starter_alphas.py                     (the room's last used brush may be remembered there: view state)
```
- **Scenes never reference alphas or presets.** A stroke is baked into layer pixels, so a scene shared with another
  machine needs no brush asset. This satisfies "do not embed alphas into every scene" by construction.
- A PNG dropped into the user `alphas/` folder is picked up by a directory scan (category "Unsortiert", the name from
  the file name); `library.json` only adds metadata.

### 6.2 Stable references
- IDs: `builtin:<category>/<stem>`; `user:<sha256-12 of the normalised pixels>` (`texture_files.content_hash`). The same
  image imported twice is the same alpha (dedup).
- A preset stores `{"id", "name", "hash"}` for its alpha. Resolution order: **id → hash** (the same pixels under another
  file name or on another machine) **→ name → missing**.
- **Missing:** the brush paints with the round tip; the panel shows "Alpha fehlt: Poren 02"; the preset keeps its
  reference unchanged (saving it does not drop it). No exception, no data loss.
- **Portability:** a preset JSON copied to another machine finds its alpha by hash if that machine has it. A later
  **export bundle** (preset + its alphas in one folder or zip, 4d) is dedup-safe on import through the hashes.

### 6.3 Import (review point 5)
- PNG first (the repo's own decoder, `decode_png`; `read_rgba` also reads what pyglet can). Three **source modes**:
  - **Alphakanal**: the PNG's alpha channel (brush-tip PNGs are often a black shape on transparency);
  - **Luminanz**: Rec.709 luminance of RGB (display values, P-16);
  - **Luminanz × Alphakanal**: both (a grey structure inside a cut-out shape).
- Plus **Invert** and **Kontrast** (a gamma around 0.5).
- **Auto-preselection, only a suggestion** (P-26):
  - no alpha channel → Luminanz;
  - RGB uniform and alpha varying → Alphakanal;
  - both varying → Luminanz × Alphakanal;
  - a bright border (mean > 0.5) → Invert suggested.
- The **import card** shows the live preview of the result; the artist corrects the mode before "Importieren".
- Normalisation: the longest side is clamped to `PROVISIONAL` 1024 px (box downsample), and the result is stored as an
  8-bit grey PNG; the hash is taken from those pixels. A 16-bit PNG keeps its high byte (the decoder's rule; enough for
  a stamp). An image < 8 px or empty is refused with the reason.

### 6.4 Presets
- JSON (`"format": "mirai.paint.brush/1"`), one file per preset; the `eye_presets` rules: a bad or foreign file is
  skipped with its reason in the status line, names are slugged, saves are atomic (tmp → replace).
- **Operations:** select · change (a "geändert" marker; the preset file is unchanged until saved) · Speichern (user
  presets) · Speichern als … · Duplizieren · Umbenennen · Löschen (user only) · category · favourite (★). Built-ins are
  read-only ("Speichern als" only).
- **Size in presets (P-20):** a preset stores its radius. A "Größe behalten" toggle in the picker keeps the current
  radius when switching (view state). Recommendation: the preset's size is applied by default.

Example:
```json
{
  "format": "mirai.paint.brush/1",
  "name": "Poren-Spray",
  "category": "Haut",
  "tip": {"alpha": {"id": "builtin:organic/pores_01", "name": "Poren 01", "hash": "3f9a1c2b7d10"},
          "source": "luminance", "invert": false, "contrast": 0.0, "kreismaske": false},
  "radius_percent": 2.0, "opacity": 0.6, "flow": 0.35, "hardness": 0.5, "curve": "smooth",
  "dynamics": {"spacing": 1.0, "emitter": "spray", "density": 12, "stamp_size": 0.2,
               "orientation": "random", "angle": 0.0,
               "jitter": {"rotation_deg": 180.0, "scale": 0.3, "flow": 0.4},
               "scatter": {"along": 0.0, "across": 0.0}}
}
```

### 6.5 Built-in starter set — procedural, reviewed before adoption
- `tools/make_starter_alphas.py`: deterministic (fixed seeds), NumPy only, our own work. Licence: the repository's terms;
  `assets/paint/LICENSES.md` names the generator as the source of each file. CC0 alphas may be added later **only** with
  the source, the licence text and the date per file recorded after checking (Manu 2026-11-25); nothing external is
  bundled before that.
- Categories and first contents (P-22):
  - **Organisch**: pores (fine, coarse, clustered), wrinkles (short creases, a crow's-foot fan);
  - **Adern**: branching veins, capillaries;
  - **Sprenkel**: freckles, scattered dots, a soft speckle;
  - **Schmutz**: stains, grime, deposits;
  - **Schaden**: scratches, scars, cracks;
  - **Oberfläche**: grain, irregular noise;
  - **Formen**: circle, square, soft ring, line.
- Generation methods: pores and dots from jittered Poisson-disc points with soft radial kernels; veins and capillaries
  from a branching random walk with tapering width; stains and grime from thresholded fBm noise with soft edges;
  cracks from Voronoi cell edges with width noise; scratches from noisy polylines; grain from band-limited noise.
  Every alpha gets a black border.
- **A contact sheet first** (review point 6): the generator writes a labelled sheet of every alpha and, for each, a
  stamped strip (single and spray) on a neutral shaded sphere. **Manu judges per category; only accepted alphas are
  committed.** Technically correct is not the same as a good artist tool.
- About eight starter presets combine them ("Poren-Spray", "Feine Falten", "Adern folgen", "Sommersprossen",
  "Schmutz streuen", "Kratzer", "Körnung", "Runder Pinsel").

### 6.6 Caching
- **Alphas:** an LRU of decoded `AlphaImage` (pixels + mips) by id, capped by bytes (`PROVISIONAL` 64 MiB). A 1024²
  alpha with its mips is about 1.4 MiB in uint8.
- **Thumbnails:** 64² RGBA (16 KiB each), created as GL textures **only while the picker is open**, freed when the room
  closes. A 32² preview of the current brush stays while the room is open.
- **Per stroke:** the alpha level chosen for the current radius is held by `StrokeState`, so a placement does not look
  it up again.

## 7. UI (brief §6)

The current panel is a prototype list of sliders (`gui/paint_panel.py`). Phase 4 organises the brush part into
**areas that show only what applies**; the layer part (Phase 3) stays as it is. Everything is `PROVISIONAL` until P-23;
P-17 (a compact text strip in the room, no icon toolbar) is respected.

```
┌ Paint Room ─ Gollum_Head - malt auf der SubD-Fläche (Stufe 1), 2048² ────────────┐
│ (•) Malen  ( ) Radieren  ( ) Pipette        Farbe [■■■]   [x] Spiegeln (X-Ebene)  │  ← area 5: tools, as today
│ ┌──┐ Poren-Spray  • geändert             [▾ Pinsel …]  [Speichern] [Zurück]       │  ← area 1: brush row
│ └──┘ Haut ★                                                                       │
│ Spitze: [▣ Poren 01]  Quelle Luminanz  [ ] Invert  Kontrast ──●──  [ ] Kreismaske │  ← area 2: only with an alpha
│ Radius ──●── 2 %   Deckkraft ──●── 60 %   Fluss ──●── 35 %                       │  ← area 3: properties
│ ▸ Strich    Abstand 100 %, zufällig                                               │  ← area 4: collapsed headers
│ ▸ Streuung  Drehung ±180°, Größe ±30 %, Fluss ±40 %                               │     with one-line summaries
│ ▾ Spray     Dichte ──●── 12   Stempelgröße ──●── 20 %                             │     (Spray only in Spray mode)
│ ─────────────────────────────────────────────────────────────────────────────────  │
│ Auflösung … / Ebenen …  (unchanged, Phase 3)                                       │  ← area 5: layers
└───────────────────────────────────────────────────────────────────────────────────┘
```

- **Area 1, brush row:** the 32² preview of the current brush, its name, its category and ★, a "geändert" marker,
  `[▾ Pinsel …]` opens the **picker popup**; Speichern / Speichern als / Zurücksetzen appear only when changed.
- **Picker popup** (an ImGui popup, closed by Esc or a click outside):
  - tabs **Pinsel** and **Alphas**; a category combo, a search field, favourites first;
  - a grid of 64² thumbnails with name tooltips; right-click → Duplizieren, Umbenennen, Löschen, Favorit, Kategorie;
  - on the Alphas tab `[Alpha importieren …]`: the file browser (purpose `image`) → the import card (live preview,
    source mode, invert, contrast, name, category, the border warning) → Importieren.
  - Choosing an alpha on the Alphas tab sets the current brush's tip (the brush becomes "geändert").
- **Area 2, tip:** shown only with an alpha: the alpha's thumbnail (opens the Alphas tab), source mode, invert,
  contrast, Kreismaske. Hardness and curve appear in area 3 only when the Kreismaske is on, or for the round tip.
- **Area 3, properties:** radius (the steps of P-7), opacity, flow, plus hardness and curve where they apply.
- **Area 4, stroke:** collapsing headers, **closed by default**, each with a one-line summary while closed:
  - "Strich": spacing, orientation mode and offset, emitter Single/Spray;
  - "Streuung": rotation, scale and flow jitter, scatter along/across;
  - "Spray": density and stamp size, shown only with the Spray emitter.
- **Area 5:** tools, colour, mirror, resolution and layers stay as they are.
- **Keys:** none new (CLAUDE.md, AGENTS.md §7). Shift+wheel (radius) and Alt+wheel (opacity) stay. A key for the picker or
  brush cycling would be a proposal for Manu's "Taste passt" after the practical test.
- **Cursor:** an alpha tip draws its oriented rectangle (and the dimmed circle); spray draws the brush circle. A projected
  preview of the alpha image under the cursor would need a GL pass: not in Phase 4.

## 8. Reference-PC risks and limits (Q9550, 9800 GTX OpenGL 3.3, 512 MiB, Python 3.12)

| Risk | Evidence | Mitigation | Gate (§9) |
|---|---|---|---|
| CPU cost per placement grows with the radius | the dab today: 1.7–2.4 / 2.6–3.3 / 4.3–5.1 / 11.4–12.6 ms p50 at 1 / 3 / 5 / 10 % [C], ≈ ×3 [H]; the 10 % dab already misses a frame on the RPC (AD-037 §10.8e) | one gather per placement; alpha sampling is four `take`s per texel (vectorised); uint8 → float only on gathered texels | 4a |
| Dense spray on long strokes | K stamps × their texel subsets per placement; long strokes multiply the placements | one gather per cluster, per-stamp masks, the K cap, the queue budget and the bounded backlog | 4b |
| Release freeze | an unbounded queue drained in the release event | finishing over frames, a capped backlog | 4a |
| Python loops | per texel would be fatal | loops only per stamp (≤ 64) and per placement; no loop per texel anywhere | code review + gates |
| Large alpha images | a 4096² PNG decodes slowly and aliases | import clamp to 1024 px, mips, decoding at import (once) not at painting | 4c |
| CPU memory | alphas, the stroke buffer (`cover`, 16 MiB at 2048², exists), the colour buffer (4d) | the alpha LRU at 64 MiB; the colour buffer lazy per tile and only in 4d | 4c / 4d |
| GPU memory | 512 MiB; the live texture exists | thumbnails 16 KiB each (200 ≈ 3 MiB), only while the picker is open; no new full-size textures | 4c |
| Upload / composite | spray touches more tiles per frame; mip regeneration costs ~+6 ms per uploading frame [C, llvmpipe, AD-037 §7; the RPC run passed P-B] | unchanged dirty-tile composite and tile upload; the queue spreads the work over frames | 4b |
| Full recomposite | a stack value change recomposites everything (exists) | painting never triggers it; only tile updates | – |

## 9. Roadmap, acceptance criteria and performance gates

Each slice is size M, ends with tests in the container, a probe row for the reference PC (`probe_paint.py`) and a
Praxistest for Manu. Gates are for the **reference PC at 2048²** unless marked; `PROVISIONAL` until the first run.

### 4a — alpha tip, projection, world spacing, queue (with test alphas)
- **Content:**
  - the alpha tip (no library yet);
  - the projection of §4 with the inner-disc frame, depth window and fade;
  - world arc-length spacing;
  - the stamp queue with the bounded backlog and the finishing state;
  - the oriented rectangle cursor;
  - a **test-alpha chooser**: a plain combo over five or six generated test alphas (pores, a vein, a scratch, a stain,
    dots, a square), so the visual trial on the Gollum head starts here and does not wait for 4c.
- **Acceptance (tests):**
  - the round tip through the new pipeline is **bit-identical** to today's dab (cage, SubD 1, mirror on/off);
  - the curvature validation of §4.3 passes (stretch, frame jump, leak, seam), or its fallback is built;
  - a stamp is symmetric under mirror;
  - a synthetic fast stroke has **no gaps** (the largest gap between placements ≤ 110 % of the spacing);
  - Esc during stroking and during finishing is exact; one Undo step per stroke; Undo/Redo pixels are identical.
- **Gates:**
  - a 3 % alpha placement (dab + composite + frame) p95 ≤ 16.7 ms on the cage and on SubD 1; 5 % ≤ 33 ms;
  - a 2 s fast stroke: frame p95 ≤ 33 ms; release → History ≤ 250 ms; no frame above 50 ms while finishing.
- **Praxistest (Manu):** the contact sheet of §4.3; pores and a vein on the nose, lips, corner of the mouth, cheek, lid
  and across the seam.

### 4b — dynamics and spray
- **Content:** rotation, scale and flow jitter; scatter; the orientation modes; the Spray emitter; counter-based RNG.
- **Acceptance:**
  - **determinism**: the same samples and seed give identical pixels for 1 ms, 10 ms and unlimited budgets;
  - jitter values stay inside their bounds (property test over many seeds);
  - mirror reuses the same random values;
  - spray density per area is independent of stroke speed (a test at two speeds).
- **Gates:** a 3 % spray placement with 20 stamps p95 ≤ 33 ms; a 10 s spray stroke with no frame above 50 ms.

### 4c — library, presets, picker, import, starter set
- **Content:**
  - `library.py`; presets (save, save as, duplicate, rename, delete, categories, favourites);
  - the picker popup and the areas of §7;
  - the import card with the three source modes;
  - the generator and its contact sheet; the accepted starter alphas and presets.
- **Acceptance:**
  - a missing alpha falls back to the round tip and keeps its reference;
  - the same image imported twice gives one alpha (hash);
  - a broken JSON is skipped with its reason;
  - built-ins are read-only;
  - presets carry no colour, tool or mirror;
  - user assets go to `~/.mirai_bastel/paint/` only.
- **Gates:** a 1024² import ≤ 0.5 s; the picker's first open with 50 thumbnails ≤ 150 ms and no per-frame cost
  afterwards; the alpha cache ≤ 64 MiB.

### 4d — later (each its own decision)
- colour jitter with the stroke colour buffer (§5.8);
- the preset export bundle;
- CC0 alphas with a recorded licence;
- the wrap projection (only if §4.3 or the practical test asks for it);
- lazy mouse / stroke smoothing.

### Not in Phase 4
Roughness / normal / translucency painting (a later AD-037 phase; the coverage interface of §3 is ready for it),
vertex paint, weight paint, a sculpt framework, pressure (P-15), stencil / image projection, smudge / blur / clone.

## 10. Decisions for Manu — **decided 2026-11-25**

**Manu, 2026-11-25 (session chat, verbatim):** „P-18 bis P-28 zugestimmt“ — every recommendation below is the decision.

| # | Question | Recommendation | Source | Status |
|---|---|---|---|---|
| P-18 | How is spacing measured? | **World arc length** along the surface, % of the stamp diameter | agent; review agrees | **entschieden 2026-11-25** |
| P-19 | Kreismaske default for imported alphas? | **Off** (the alpha defines its shape); the round tip keeps its falloff | review (changed the agent's first proposal "on") | **entschieden 2026-11-25** |
| P-20 | Do presets carry the brush size? | **Yes**, with a "Größe behalten" option | agent; review agrees | **entschieden 2026-11-25** |
| P-21 | Default orientation of alpha brushes? | **Strich folgen** | agent; review agrees | **entschieden 2026-11-25** |
| P-22 | Starter categories and import size limit | the categories of §6.5; **1024 px** at first; starter alphas adopted only after the contact-sheet check | agent + review | **entschieden 2026-11-25** |
| P-23 | UI layout | the compact layout of §7 with collapsed sections and the picker popup | agent; review agrees | **entschieden 2026-11-25** |
| P-24 | Slice order | **4a → 4b → 4c**, test alphas already in 4a | agent + review | **entschieden 2026-11-25** |
| P-25 | Is the colour part of a preset? | **No** | agent; review agrees | **entschieden 2026-11-25** |
| P-26 | Import source modes | **Alphakanal / Luminanz / Luminanz × Alphakanal**, auto-preselected, correctable in the preview | review | **entschieden 2026-11-25** |
| P-27 | Very fast strokes: catch-up or gaps? | **Catch-up** (the paint may trail the cursor briefly); never gaps, never a freeze on release | agent; review asked for the bounded release | **entschieden 2026-11-25** |
| P-28 | Spray while the mouse stands still? | **No** time-based „Airbrush“ emission: a click is one burst, holding still adds nothing (keeps the pattern independent of timing) | agent | **entschieden 2026-11-25** |

Not a question for Manu (technical, agent-owned): the inner-disc frame, the depth window and fade values, the queue
budgets, the cache sizes and the mip rule. They are `PROVISIONAL`, tuned against the gates and the §4.3 metrics, and
reported in AD-037 when built.

## 11. What this report did not verify
- No new measurement. All costs are from AD-037 §10.7 / §10.8e [C, RPC] or estimates [H]; the gates decide.
- The stability of the planar frame on the Gollum head's curved regions is the main technical uncertainty (§4.3). It is
  measured as part of 4a, not assumed.
- The visual quality of procedurally generated alphas is unknown until Manu has seen the contact sheet.
- The ImGui thumbnail grid's cost on the 9800 GTX with 50–200 small textures is not measured (gate in 4c).
- The exact frame hook for the queue consumer (the update path at `application.py:7009`) is to be confirmed in 4a.

## Sources (code at `e583cee`)
`src/mirai/paint/brush.py`, `surface.py`, `texel_map.py`, `store.py`, `display.py`, `files.py`;
`src/mirai/controllers/paint_room.py`; `src/gui/paint_panel.py`, `paint_model.py`, `eye_panel.py`,
`file_browser_model.py`; `src/mirai/iris_import.py`, `texture_files.py`, `eye_presets.py`, `look_maps.py`;
`src/mirai/viewport/box_select.py` (`stroke_samples`); `src/main.py` (`state_dir`); `requirements.txt` (NumPy 2.2.6).
