# P1c — soft limbus transition: plan (2026-11-14)

**Status: approved and built the same day** — see README "P1c". Manu's answers to the six questions below: (1) cumulative,
yes; (2) P1b V2 as the baseline, V3 selectable, L0 pixel-identical to P1b V2; (3) L2 shader only, a sulcus later as a
separate task; (4) shader colour by default **and** the image's outer ring as a switch; (5) asymmetry as an independent
switch, initially off, separate from L0–L3; (6) Task 1 "A+H" with `hold_outer_color` as an explicit sidecar key.
Deviation from the plan: the L3 transmission is `(1 − t)^falloff` (reaches 0 at the band edge) instead of
`1 − exp(−σ d)`, which never reaches 0 and would have leaked the iris onto the whole sclera.

Handoff Task 2. Manu: "Dieser weiche Übergang am Limbus ist etwas, was ein Auge nochmal
wesentlich realistischer erscheinen lässt als ein harter Übergang." This plan names the variants, how they are
compared and measured, and the decisions Manu makes before the build. No Artist verdicts here.

## What exists (verified in the code, 2026-11-14)

- **P1:** hard seam. The sclera mesh is open at the limbus ring (r 5.88 mm); the cornea cap shares those vertices; the
  sclera's normal there is 29.3° off the eye's axis and the cornea's 48.9°, so there is a **19.6° kink**: highlights and
  reflections jump at the ring. The sclera is shaded with one albedo (`shaders.SURFACE_FRAGMENT_BODY`, `u_albedo`).
- **P1b (V2 / V3):** rays entering the cornea between the chamber angle (r 5.59 mm) and the rim end in **limbal
  tissue**: opaque, `mix(limbal colour, sclera albedo, limbus_weight)` (smoothstep over the anterior entry radius).
  On Manu's sheet this reads as a thin bright rim, not as a soft grey-blue zone. The sclera side knows nothing of it.
- **Task 1 (done, choice open):** with the radial fit, the custom image's own dark limbal ring sits at its iris edge;
  depending on the target (0.819 / 0.779) P1b shows or hides it.

## Anatomy to aim at (checked against sources, not only memory)

- The visible iris is wider than high: the commonly cited corneal (visible iris) diameter is ~11.7 mm horizontal ×
  ~10.6 mm vertical (one old source), i.e. the sclera/limbus overlaps the cornea ~0.5 mm more at top and bottom.
  The lab's 11.76 mm limbus matches the horizontal value.
- The iris-to-sclera edge is a **grey transition zone**, not a line: visible-iris measurements need a subjective
  threshold for it; the true corneo-limbal diameter is larger than the visible one (white-to-white +0.33 ± 0.24 mm to
  the topographic limbus). The literature reviewed says the limbus width is **not agreed** — the often quoted 1–2 mm is
  a working value here, PROVISIONAL.
- The **limbal ring** (dark ring at the iris edge) gets thinner with age; its width and opacity depend on iris
  pigmentation and on the local optics; observers prefer faces with a distinct ring (one 2011 study).
- Sources: [Mean shape of the human limbus (arXiv 1906.09149)](https://arxiv.org/pdf/1906.09149),
  [corneo-limbal diameter review (PubMed 28868754)](https://www.pubmed.gov/28868754/),
  [limbal ring and attractiveness, Peshek et al. 2011](https://escholarship.org/uc/item/0964610k).

## Variants (cumulative, so each step's effect and cost is visible on its own)

All on top of **P1b** (refractive cornea; V2 by default, V3 switchable — V2 vs V3 stays Manu's open decision), drawn
from new P1c files; P1 / P1b code paths unchanged (or byte-identical defaults, tested).

| | What changes | Where | Expected cost |
|---|---|---|---|
| **L0** | nothing: P1b V2 / V3 as today (P1 V1 seam as a second reference) | — | baseline |
| **L1** colour band | sclera fragments within a band outside the ring are tinted from the limbal colour to the sclera albedo (smoothstep over the angle from the axis); the cornea's tissue blend is re-graded so both sides form **one** gradient (no bright rim at the seam). Optional vertical asymmetry: the band reaches ~0.5 mm further over the cornea at top and bottom | sclera program (new), tissue blend in the cornea pass | ~0 (a few ALU) |
| **L2** = L1 + normal blend | across ±w around the ring the shading normal is blended from the cornea sphere's normal to the sclera's, on both passes, so highlights and reflections move continuously over the 19.6° kink. Shader-only; the meshes stay. A geometric sulcus/fillet (new lab meshes, also needs the refraction's analytic surface changed) is kept as a later option, not in P1c | both passes | ~0 |
| **L3** = L2 + translucent limbus | in the band, the limbus becomes semi-translucent: a sclera fragment refracts its view ray into the eye (P1b's ray code: refraction, `iris_cone_hit`) and sees the iris edge / chamber angle; opacity grows with the tissue thickness toward the sclera (`1 − exp(−σ d)`); the cornea's tissue rays likewise continue instead of stopping opaque. The iris shows through the limbus as a soft grey-blue ring | sclera program shares P1b's ray library + the iris texture (fit included) | one short ray trace per band fragment; measured |

Parameters (all PROVISIONAL, lab-local keys / HUD, no `config/keymap.json` entry — D-L9): band width (default 1.0 mm
outside the ring), limbal colour, strength, asymmetry on/off, normal-blend width w, L3 opacity σ.

**Who owns the limbal darkening** (texture vs shader) — proposed: a switch. *Shader*: the limbal colour is a parameter
(default the procedural iris's outer colour, as P1b). *Image*: the colour is the custom image's mean colour in its own
outer ring (shares `limbus − 0.05 … limbus`, read once at load), so a texture with a strong limbal ring drives the band.
With L3 the image's ring can also show physically through the translucent zone (target A hides it behind tissue today).

## Comparison, measurements, views

- **Views:** front, ¾, profile, steep 75° (as P1b's sheet), plus a **highlight sweep**: the key light's azimuth moved so
  its highlight crosses the limbus (shows the L2 effect; the seam jump in L0/L1).
- **Sheet:** limbus crops ×3, columns L0 | L1 | L2 | L3, rows = views; full-eye shots per variant (procedural iris and,
  if present, the custom one with its fit).
- **Numbers (probe `probe_limbus.py`, same format as P1/P1b):**
  - [P] parity of every new GLSL function vs its NumPy twin;
  - [C] continuity: along radial lines across the ring, the largest pixel-to-pixel luminance step and the highlight
    position jump in the sweep, per variant (L0 should show the jump, L2/L3 should not — a measured check, no verdict);
  - [K] ray classes unchanged against the CPU model where the variant does not change them;
  - [V] GPU time per variant (GL_TIME_ELAPSED, T-B / T-C / T-D, V2 and V3), on the reference PC as before
    (MEASURED [RPC]); container numbers only as TESTED [C];
  - [R] GL state left as found (incl. pixel-store state).
- **Tests:** L0 = P1b pixel for pixel (V2, V3, every technique); P1 / P1b suites unchanged and green; parity; a band
  test (pixels just outside the ring darker than the plain sclera in L1–L3, unchanged beyond the band); the custom
  image and sidecar left untouched.

## Files (planned)

`limbus_model.py` (NumPy twins: band weight, normal blend, translucency), `limbus_shaders.py`, `limbus_gl.py`
(`LimbusState(RefractionState)`, `LimbusRenderer(RefractionRenderer)`, a sclera program), `limbus_parity.py`,
`probe_limbus.py`, `run_limbus.py` (P1b's window and keys + one key to cycle L0…L3 and the parameter keys; free keys
checked against `lab_state.KEYS` and P1b's), `tests/test_limbus_*.py`, README section "P1c", results files after the
runs.

## Decisions for Manu before the build

1. Variants L0–L3 as above, cumulative (L2 includes L1, L3 includes L2)? Or separate (each alone)?
2. Base P1b V2 with V3 switchable — fine?
3. L2 shader-only now, geometric sulcus later — fine?
4. Limbal colour: the switch shader / image as proposed (default shader)?
5. Vertical asymmetry: as a toggle (default off, so L1–L3 first compare round), or on by default?
6. The Task 1 choice (target A/B, hold or not) — L3 interacts with it (A + L3 lets the hidden band shine through).

Order after the OK: L0 + L1 (+ tests) → L2 → L3 → probe and sheet in the container → commands for the reference PC.
