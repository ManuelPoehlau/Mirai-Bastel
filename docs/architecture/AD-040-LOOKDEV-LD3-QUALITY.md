# AD-040 — LookDev LD-3: quality manager with an activity state and idle refinement

**Status:** **ACCEPTED (2026-11-25, Manu):** „OK, ich gebe das Go und starte dann in einer neuen Session“. **LD-3a
built 2026-11-25** (§14: quality manager, block „Qualität“, machine setting; no shader change, every pin kept; Hoch
without refinement bit-identical to `1e5d751`); the reference-PC run (§11.1 / §14.4) and Manu's practical test
(§14.5) are next; Q-LD3-1 … Q-LD3-3 stay open as §12.2 proposes (Q-LD3-1 / -2 decided by the §11.1 run). LD-3b only
after §12.1 point 3.
Proposed 2026-11-25 (Architecture Gate). The number AD-040 follows
AD-039. New class, file and panel names stay `PROVISIONAL` until built.
**Decisions taken into it** (Manu, 2026-11-25, verbatim): „F-R1 bis F-R4 wie vorgeschlagen, F-R5 Bild speichern
jederzeit möglich, schreib das AD“, on the questions of the
[assessment](../research/LOOKDEV_LD3_ADAPTIVE_PROGRESSIVE_ASSESSMENT_2026-11-25.md) §10.3:
- **F-R1:** LD-3 gets an activity state and two budgets, built as LD-3a, then LD-3b.
- **F-R2:** „In Ruhe verfeinern“ is off by default.
- **F-R3:** S9 runs only when idle, now. The jittered key is LD-3b's candidate.
- **F-R4:** a 0.3 s wait and a crossfade of about 0.2 s.
- **F-R5:** „Bild speichern“ works at any time and never waits (§7).
**Why now:** LD-3 follows P3 (Manu, 2026-11-21), and P3 is built through S9 (AD-039 §24). Manu, 2026-11-24, for S9:
„du kannst auch zu Gunsten besserer Qualität unter 30 Fps in Kauf nehmen“. Manu, 2026-11-25 (the assessment's brief):
30 fps stays the target for interactive work and need not limit an optional idle refinement.
**Basis:**
- [proposal §12.3 / §13 LD-3](../design/LOOKDEV_P2_ARCHITECTURE_UX_PROPOSAL_2026-11-19.md);
- [RENDERING_VISION §7](../design/RENDERING_VISION.md);
- [AD-038](AD-038-LOOKDEV-ROOM-M1.md) (the room, I-4, I-10, §18 capture);
- [AD-039](AD-039-LOOKDEV-P3.md) (§2 the shared frame, §2.5 budget, §11 measurements, §16–§24 the built slices);
- the assessment above (§2 code check, §3 other applications, §5 design);
- the reference-PC results in `experiments/drag_cost/` and `experiments/lookdev_pcss/`.
**State inspected:** `main` @ `553da3c` (`src/` as at `1e5d751`, S9). Every [V] statement below was checked there.
**Extends:** AD-038, AD-039. **Core / format / keys:** none. The quality settings are a machine setting outside the
scene (§8).

Evidence tags as in AD-038 §1: **[V]** verified in code, **[M-RPC]** measured on the reference PC, **[M-C]**
container, **[P]** decided by this AD if accepted, **[E]** estimate, **[O]** open for Manu.

---

## Kurzfassung (Deutsch)

- **Was LD-3 wird:** Ein Quality Manager mit drei Teilen.
  - **Aktivitätszustand:** Interaktiv → Beruhigen → Ruhe → Fertig.
  - **Zwei Budgets:**
    - Beim Arbeiten gilt das 30-fps-Ziel mit „Auto“.
    - In Ruhe gibt es kein Bildratenziel, nur eine Obergrenze pro Frame von 50 ms. Damit reagiert ein Klick sofort.
  - **Zwei Einstellungen:** „beim Arbeiten“ und „in Ruhe“. Beide sind nur Masken über deine Effekt-Schalter und die
    vorhandenen Regler. Regionen und Maps fasst der Manager nie an.
- **Woran Ruhe erkannt wird:** an einer **Frame-Signatur**, nicht an Mausereignissen.
  - Die Signatur ist ein Schlüssel aus allem, was das Bild bestimmt: Kamera, Mesh-Revisionen, Studio, Effekte,
    Materialien, Augen, Mal-Textur, Qualitätseinstellung.
  - Ändert sie sich, ist der Raum „interaktiv“. Bleibt sie 0.3 s gleich, beginnt die Ruhe.
  - So wirkt es für Maus, Slider, Morph, Pose, ZBrush-Import und später Animation gleich.
- **LD-3a (zuerst, ohne Shader-Änderung, alle Pins bleiben):**
  - der Zeitmesser (GPU-Zeit) und die Stufen Auto / Hoch / Mittel / Entwurf;
  - beim Ziehen eine Schattenkarte, die eingefroren oder seltener neu gerechnet wird (der Referenz-PC-Lauf entscheidet);
  - mit „In Ruhe verfeinern“: „Weicher Schatten“ nur in Ruhe, dazu die Schattenkarte 2048² und der Cube mit 256
    Samples („Maximal“);
  - alle Shader-Varianten werden beim Betreten vorkompiliert;
  - der Block „Qualität“ im Panel und eine Statuszeile;
  - die Einstellung wird pro Rechner gespeichert, nicht in der Szene.
- **LD-3b (danach, nur nach einer Sonde auf dem Referenz-PC und deinem Go):**
  - echte Verfeinerung durch Mitteln leicht verschobener Frames: Kantenglättung und rauschfreie weiche Schatten;
  - ein weicher Übergang von etwa 0.2 s;
  - ist das Bild fertig, wird nur noch das gespeicherte Bild gezeigt, ohne neue Rechnung.
  - Kandidat für den Schatten: der „wandernde Key“, also viele harte Keys über die Lichtscheibe gemittelt, genau wie die
    Referenz der PCSS-Bewertung.
- **„Bild speichern“ jederzeit (dein F-R5):**
  - Gespeichert wird sofort das, was der Raum gerade zeigt, ohne Warten.
  - Die Statuszeile sagt, in welchem Zustand: „verfeinert 64/64“, „Verfeinerung 24/64“ oder „interaktiv“.
- **Nicht betroffen:**
  - Worklight und Modelling Room (E16), alle Shader-Pins, R-1;
  - Core, Szenenformat, Picking, Morph, Rig, Modellieren;
  - `config/keymap.json` (keine Tasten).
- **Offen für dich (§12):**
  - Q-LD3-1: Schattenkarte beim Ziehen eingefroren oder jedes 2. Frame. Der Referenz-PC-Lauf liefert die Zahlen.
  - Q-LD3-2: die Auto-Schwelle von 12 ms GPU (`PROVISIONAL`, der Lauf kalibriert sie).
  - Q-LD3-3: ob „Maximal“ vor LD-3b schon wählbar sein soll (Vorschlag: ja, als verzögertes Einschalten).

---

## 0. Scope, guardrails, not in scope

### 0.1 In scope [P]

LD-3 of proposal §13, with the assessment's extension (F-R1):
- capability layer (P3's feature report, plus one timer check);
- GPU timing, Auto with hysteresis, and the tiers Auto / Hoch / Mittel / Entwurf;
- the activity state and the frame signature;
- the idle configuration with delayed activation (LD-3a);
- progressive accumulation (LD-3b);
- the panel block „Qualität“, the status line, and capture at any time;
- the machine setting.

### 0.2 Guardrails (binding for LD-3a and LD-3b) [P]

| # | Guardrail | How it is held |
|---|---|---|
| Q1 | **Render-only.** The manager never changes mesh or sculpt resolution, the SubD level, morph weights, pose or deformation accuracy, topology, picking, or artist-authored material values, regions or maps (proposal §12.3, RENDERING_VISION §7, appendix E20) | the configuration is a value of render fields only; a structural test (§10.1 G-5) |
| Q2 | **The effect switches stay the artist's "allowed" set** (AD-039 G2). A configuration can only turn an allowed effect off, or raise a resolution or sample count. It never turns on an effect that is switched off | `resolve(...) ⊆ effective(effects, features)` asserted per configuration |
| Q3 | **Refinement off = today.** With „In Ruhe verfeinern“ off and the tier at Hoch (every effect as switched, the P3 sizes), the frame is pixel-identical to `1e5d751`. With any setting, no shader source changes in LD-3a | the pixel gate and every pin (§10.1 G-1, G-2) |
| Q4 | **The Modelling Room loses nothing** (LD-D10, E16, AD-039 G4): with `shading == "worklight"` no timer, no signature, no configuration, no buffer exists | E16 rows unchanged; a test that the Worklight path creates none of them |
| Q5 | **Pins:** `PINNED_WORKLIGHT_SOURCES_SHA256`, `PINNED_LOOKDEV_SOURCES_SHA256`, `PINNED_SKIN_SOURCES_SHA256` and the eye LD_SHADOW pin are unchanged in LD-3a. LD-3b adds one define (`ACCUM_JITTER`) in the P3 discipline: off = the source before, character for character | AD-039 §2.3 rules, a new pin over the `ACCUM_JITTER` variants in LD-3b |
| Q6 | **R-1 stays**: nothing LD-3 holds is written by a room transition | the quality is machine state (§8), not room or document state |
| Q7 | **No keys** (D-L9) | panel controls only |
| Q8 | **No automatic downgrade of a still image.** Auto changes the tier only on interactive frames; the still image the artist judges never changes because of a timer | §4.3 |
| Q9 | **I-4:** no FBO stays bound across `on_draw` steps; every pass unbinds what it bound | the GL-state tests of AD-039, extended (§10.1 G-8) |

### 0.3 Not in scope

- **Temporal reprojection and denoising** (assessment §3.5). They are excluded, not postponed.
- **Resolution scaling during interaction.** The room is CPU-bound (assessment §2.4).
- **A move of the app loop to render-on-demand.** The 60 Hz redraw stays (§6.4).
- **Quality in the Worklight**, the Paint Room or the Eye Lab.
- P4 (an HDR target, MSAA, skin diffusion tiers) and P5. LD-3b's accumulation takes "a frame texture" as input, so P4
  can feed it a float target later (§6.1).

---

## 1. Code check: what LD-3 builds on [V]

| # | Fact | Where |
|---|---|---|
| V1 | The effect switches are a frozen value; `effective(effects, features)` resolves dependencies and missing features; `Viewport.lookdev_effects(wanted)` is what the frame and the compile use | `lookdev_optics.py:77`, `viewport.py:474–493` |
| V2 | The feature report is computed once per context, by function; "a plain value, so LD-3 can read it" | `lookdev_features.py:1–40` |
| V3 | The programs the next frame needs are enumerated in one place; `prepare_lookdev` compiles them (and the cube) behind „LookDev: Shader werden vorbereitet …“ (I-10) | `viewport.py:555–633`; `application.py:1396–1421` |
| V4 | `KeyShadow(size, maps, flush)` and `EnvCube(size, levels, samples)` take their size and sample count as constructor arguments and re-render only on a key change (`KeyShadow.key`: caster revisions, model, key direction, effective resolution) | `lookdev_shadow.py:61–124`, `lookdev_cube.py:48` |
| V5 | Both passes read the camera from `store.uniform_data("camera_uniforms")` | `lookdev_pass.py:271`; `eye_pass.py:500`, `:527` |
| V6 | The LookDev frame is drawn by `_render_lookdev` into the default framebuffer (RGBA8, no MSAA, no float target); overlays follow after `viewport.render()` in `on_draw` | `viewport.py:1381–1439`; `main.py:712–741`, `:420–426` |
| V7 | Capture: `request_capture(cb)` → one extra mesh render into the back buffer, `read_back_buffer`, clear, then the normal frame | `viewport.py:1288–1316` |
| V8 | The app redraws every window at pyglet's default 1/60 s; `_tick` calls `update_viewport(dt)` at the same rate | `main.py:817–835`; pyglet 2.1 `EventLoop.run` |
| V9 | Interaction signals: an exclusive `interaction.session`, a paint stroke, a held `_gesture`; a held material slider (`MaterialEdit.hold`) | `application.py:1185–1195`; `gui/lookdev_model.py:245–272` |
| V10 | No timer query in `src/` (the probes use `GL_TIME_ELAPSED`) | grep, and `experiments/drag_cost/probe_lookdev_room.py` |
| V11 | The live paint texture has no revision counter: `mark()` and the tile upload change it without a counter | `live_texture.py:23–49` |
| V12 | A per-user state directory exists: `~/.mirai_bastel`, used by the file browser for recent folders | `main.py:939`, `gui/menus.py:98–121` |

---

## 2. The model: allowed effects × tier × activity → render configuration [P]

### 2.1 `RenderConfig`

`viewport/lookdev_quality.py` (new, pure, no GL):

```python
@dataclass(frozen=True)
class RenderConfig:
    effects: LookdevEffects     # ⊆ effective(allowed, features) (Q2)
    shadow_size: int            # 1024 | 2048
    shadow_updates: str         # "every" | "every_2nd" | "frozen" - while Interactive only
    cube_samples: int           # 64 | 256
    samples: int                # 1 (LD-3a) | N (LD-3b accumulation)
    jitter: bool                # LD-3b: sub-pixel camera + rotated taps
```

- It holds render fields only (Q1).
- `resolve(tier, allowed, features, refine, state) -> RenderConfig` is the one function that maps everything to it.
- It is pure and table-tested.

### 2.2 The tiers [P] (`PROVISIONAL` until the LD-3a reference-PC run, §11)

| | Entwurf | Mittel | Hoch (= today's frame) | Maximal (idle only) |
|---|---|---|---|---|
| shadow, eye shadow, thickness, dual lobe | off | as allowed | as allowed | as allowed |
| shadow size | — | 1024 | 1024 | 2048 |
| cube | as allowed (cheaper than off, P3-0 run 5) | as allowed, 64 samples | as allowed, 64 | as allowed, 256 |
| S8 area diffuse | off | as allowed | as allowed | as allowed |
| S9 soft shadow | off | off | as allowed | as allowed |
| `shadow_updates` while Interactive | frozen | Q-LD3-1 | Q-LD3-1 | — |
| LD-3b: samples, jitter | 1 | 1 | 16, jitter | 64, jitter (+ jittered key if chosen, §6.5) |

- **The interactive tier** is Auto / Hoch / Mittel / Entwurf. **The idle tier** is Hoch / Maximal.
- **Auto starts at Hoch** on each room entry, which is today's frame, and steps down only on measured interactive
  frames (§4.3).
- **The idle-only rule** (F-R3): with „In Ruhe verfeinern“ **on**, the interactive configuration never contains S9, the
  2048² map, 256 cube samples or accumulation. They belong to Refine.
- With refinement **off**, the chosen tier is the one configuration in every state. „Hoch“ then includes S9 while
  working, as today's switch does.
- **Note on `shadow_updates`:** while Interactive the map is rendered every frame, every second frame, or not at all.
  „frozen“ keeps the last map: the shadow lags during a drag and is brought up to date in the first Settling frame.
  It applies only while the signature changes because of a *caster* change. A camera move does not re-render the map
  anyway (V4).

### 2.3 Configuration per state

| State | Configuration |
|---|---|
| Interactive, Settling | `resolve(interactive tier, …)` |
| Refine, Converged (refinement on) | `resolve(idle tier, …)` |
| any state, refinement off | `resolve(interactive tier, …)` |

---

## 3. The frame signature and the activity state [P]

### 3.1 `Viewport.lookdev_signature() -> tuple`

The signature is built **next to the draw, from the objects the draw reads** (assessment §5.8 rule 2). It is O(objects),
no GL, and has these parts:
- the camera's `camera_uniforms` (view + projection) and the framebuffer size;
- per drawn `RenderMesh` (edit surface, entries, references in the room): `id`, `layout_revision`,
  `content_revision`, the model matrix (as `KeyShadow.key`);
- `LookdevState` (studio, lights, effects; frozen) and the frame dict's cache key;
- per drawn object its `LookDraw` (frozen: material, region slots, map paths);
- per eye entry the values `EyePass.draw` reads (the eye draw value, its model matrix) and `eye_display`;
- the live paint texture's **revision**: new, `LiveTexture.revision += 1` on every upload (V11). It is the one counter
  LD-3a adds outside the LookDev files;
- the `RenderConfig` in force and the feature report.

The signature is never derived from a separate dirty-flag list: a flag forgotten there would freeze an old image.

### 3.2 `ActivityTracker` (pure, `lookdev_quality.py`)

```
          signature changed / held hint
   ┌──────────────────────────────────────────────┐
   ▼                                              │
Interactive ──quiet──► Settling ──t ≥ wait──► Refine(n) ──n = N──► Converged
   ▲                       │                     │                    │
   └───────────────────────┴─────── change ──────┴────────────────────┘
```

- **Input per tick:** `(signature, held, dt)`.
- **`held`:** true while an interaction session runs, a gesture or paint stroke is held, or `MaterialEdit.held()` (V9).
  A slow drag that leaves one tick unchanged must not count as quiet.
- **`wait`:** 0.3 s by default (F-R4), 0.1–2 s in the panel.
- **N:** 1 in LD-3a. Refine then draws the idle configuration and is Converged after one frame; Converged still draws
  every tick until LD-3b brings the stored image.
- **Ownership:** the tracker lives in the LookDev room (`Application`, beside `room.preparing`). It is advanced in
  `update_viewport(dt)` (V8) after the existing refreshes, so the signature sees this tick's mesh state. It does not
  exist with the room closed (Q4).

### 3.3 Animation and continuous deformation

- **While something changes:** playback, a running morph or pose drag, an animated gaze or a paint stroke changes the
  signature every tick. The room stays Interactive: no refinement and no accumulation, so no ghosting by construction.
- **When it stops:** the room settles and refines the held frame.
- **Future animation:** a later animation system needs nothing from LD-3, as long as its evaluated state reaches the
  `RenderMesh` revisions, which drawing needs anyway.

---

## 4. Auto and the timer [P]

### 4.1 `viewport/gpu_timer.py` (new, GL)

- **What it measures:** a ring of 3 `GL_TIME_ELAPSED` queries around `_render_lookdev` (the meshes, not the overlays,
  which no tier reaches).
- **Read-out:** never blocking: a result is read when `GL_QUERY_RESULT_AVAILABLE` says so, typically 1–2 frames late. A
  synchronous read would add the GPU frame to the CPU frame.
- **Feature check:** `timer_query`, a query begun and ended without a GL error, joins `FeatureReport`. Missing → Auto
  holds Mittel, with the status „Qualität: Auto aus – Zeitmessung nicht verfügbar“.
- **Ownership:** `LookdevPass` owns it and deletes it in `release()`. It is never created for the Worklight (Q4).

### 4.2 The budget

- **Interactive:** the LD-D10 target is ≤ 33.3 ms wall. The room's CPU side is 11.6–12.6 ms [M-RPC], and no tier
  reaches it.
- **Auto's GPU target:** ≤ **12 ms** GPU p50 [P, `PROVISIONAL`, Q-LD3-2]. The rest of the frame belongs to the CPU and
  vsync.
- **Refine:** no frame-rate target. A ceiling of **≤ 50 ms per refine frame** [P] exists so that an input waits at most
  one frame. If the idle configuration's measured frame exceeds it, Refine drops the most expensive idle knob in a fixed
  order: jittered key (LD-3b) → S9 → 2048² map. The status line names it.

### 4.3 Hysteresis

- **What feeds it:** only **Interactive** frames (Q8). Each frame's GPU time goes into a moving p50 over the last 30
  interactive frames of the current tier.
- **Down:** p50 > 12 ms → one tier down (Hoch → Mittel → Entwurf).
- **Up:** p50 < 6 ms over 60 interactive frames, and the next tier's last measured p50 < 12 ms (remembered per tier in
  the session) → one tier up.
- **Pace:** at most one change per 2 s. No change while Settling, Refine or Converged.
- **Compile:** a tier change is instant because every variant is precompiled (§5).
- **Status line:** „Interaktiv – Mittel (Auto: 14 ms > 12 ms)“.

---

## 5. Precompiling and resources [P]

- **Compile:** `Viewport._lookdev_programs()` (V3) is extended to the **union** of the programs of the configurations
  that can occur:
  - with Auto, every interactive tier;
  - with refinement on, the idle tier.
  - `prepare_lookdev` compiles them behind the existing status line on entry and when the allowed effects change
    (I-10). Cost [E]: up to about 2× today's entry compile (0.24–0.6 s per variant cold), once per process.
- **Resources by configuration** (V4):
  - **2048² map (Maximal):** a second `KeyShadow(2048)`, created when Maximal is first reached, deleted in `release()`;
    +16 MiB [E].
  - **256-sample cube:** a second `EnvCube(samples=256)` with the same size, prefiltered on the first Refine frame;
    ≈ 48 ms GPU + 17–24 ms CPU copy [E from P3-0 run 5], once per studio content change.
  - Both stay cached while the room is open.
- **No shader source change in LD-3a:** each configuration selects among existing defines (V1) and existing
  instances (V4). Q3 and Q5 hold structurally.

---

## 6. LD-3b: progressive accumulation [P] (built only after §11.2's probe and Manu's go)

### 6.1 The buffer, without redirecting the renderer

- **Unchanged:** the LookDev step still draws into the default framebuffer (V6).
- **After the meshes, before the overlays:**
  1. copy the frame into an RGBA8 texture (`glBlitFramebuffer` into a texture FBO);
  2. one full-screen pass: `acc = mix(acc, frame, 1/(n+1))` into an **RGBA16F** accumulation texture;
  3. one composite quad draws `shown = mix(last_interactive, acc, min(1, n / F))` back. F = 6–8 frames ≈ 0.2 s
     (F-R4).
- **`last_interactive`:** an RGBA8 copy of the last interactive frame, taken when Refine starts. `acc` holds only idle
  samples, so the converged image carries no bias from the interactive frame.
- **Converged:** step 3 alone. No skin, eye, shadow or cube work runs.
- **Interface:** `Accumulator.add(frame_texture)` / `composite()`. A later P4 float target feeds `add` directly (§0.3).

### 6.2 Jitter

- **Sub-pixel camera offset:** Halton(2,3) per sample, added to the projection on the CPU at the one place both passes
  read (V5), for the LookDev frame only. Picking reads its own state at pick time and is never jittered. No shader
  change.
- **Rotated taps:** a per-sample rotation for the S1 3×3 PCF and the S9 spirals. It is one uniform behind a new define
  `ACCUM_JITTER`, last in the define order (after `SOFT_SHADOW`), with the P3 discipline:
  - off = every earlier source;
  - its library text is a separate string;
  - a new pin over its variants.
  - The eye keeps its lookup; it gets AA through the camera jitter, and its pins stay.

### 6.3 Reset and stop

- **Reset:** a signature change resets n = 0 in the same tick, before drawing (§3.1). A resize also reallocates the
  textures.
- **Stop:** at n = N only the composite runs. The overlays keep drawing every tick (V6).

### 6.4 The loop

- **No change to `main.run`.** Refine renders one sample per tick, Converged one composite per tick.
- **vsync:** with vsync, a 20–30 ms refine frame drops the window to 30 or 20 fps for 1–3 s. The 50 ms ceiling bounds
  the input latency.
- **Not chosen:** render-on-demand (`interval=None`). It would touch every overlay, ImGui and hover.

### 6.5 The shadow in Refine: two candidates

- **(i) S9 with rotated spirals:** 16·N effective taps; the method's systematic error stays (mean 1.83 / 255 against the
  32-key reference).
- **(ii) Jittered key:**
  - each sample re-renders the map from a point on the key's disc and looks it up hard;
  - the mean converges to the 32-key reference itself;
  - no lookup change, and the eye benefits too;
  - ≈ 10–12 ms per sample [E, from the drag rows: the depth pass ≈ 1 ms plus the open stall].
- **Choice:** §11.2's image row compares both against the reference. The better image at a cost within the 50 ms
  ceiling becomes Maximal's shadow. One `RenderConfig` field (`shadow_mode`) is added then.

### 6.6 Features and memory

- **New feature `accum_rgba16f`:** an RGBA16F 2D texture at framebuffer size as an FBO attachment. It must be complete,
  then rendered and sampled in two successive frames without a GL error. The reference PC fails this pattern for an
  FBO-rendered float **cube** (AD-039 §11.1 runs 3–5); 64² 2D works in the eye pass.
- **Missing feature:** Maximal = LD-3a's Maximal, with the status line „Verfeinern aus – Akkumulation nicht verfügbar“.
- **Memory [E]:**

| | 1024×768 | 1920×1080 |
|---|---:|---:|
| accumulation RGBA16F | 6.0 MiB | 15.8 MiB |
| frame copy + `last_interactive` (RGBA8) | 6.0 MiB | 15.8 MiB |
| 2048² map (Maximal, LD-3a; beside the 1024² map) | +16 MiB | +16 MiB |

  Free during LookDev: 242–311 of 512 MiB [M-RPC].

---

## 7. „Bild speichern“ at any time (F-R5) [P]

- **No waiting.** The capture saves at once **what the room shows at that moment**: AD-038 §18's rule "what the room
  shows, at window resolution, without overlays", extended to the states.

| State | What is saved |
|---|---|
| Interactive / Settling | one render of the interactive configuration (today's capture) |
| Refine (LD-3a) / Converged (LD-3a) | one render of the idle configuration |
| Refine(n) (LD-3b) | the current composite: `acc` after n samples, crossfade included, read back |
| Converged (LD-3b) | the converged composite |

- **Status line:** „Bild gespeichert – verfeinert (64/64)“, „… – Verfeinerung 24/64“ or „… – interaktiv“.
- **No state change:** the capture does not reset the accumulation and does not change the signature (no render input
  changes).

---

## 8. Controls and storage [P]

### 8.1 Panel block „Qualität“

The block sits in the LookDev panel below „Effekte“ (`gui/lookdev_model.py`, `gui/lookdev_panel.py`). No keys.

| Control | Values | Default |
|---|---|---|
| Qualität (beim Arbeiten) | Auto / Hoch / Mittel / Entwurf | Auto |
| In Ruhe verfeinern | on / off | **off** (F-R2) |
| Ruhe-Qualität | Hoch / Maximal | Hoch |
| Wartezeit | 0.1–2 s | 0.3 s |

- **Status line:**
  - „Interaktiv – Mittel (Auto: 14 ms > 12 ms)“;
  - „Ruhe – Maximal“ (LD-3a);
  - „Verfeinern 24/64“ / „Fertig – 64 Samples, 1.6 s“ (LD-3b).
- **Effect rows:** they keep their checkbox (allowed). An effect the current configuration holds back says why in its
  tooltip („aktiv in: Hoch, Maximal“ / „in Ruhe“).
- **Setters:** they are Application methods like `set_lookdev_effect`: view state, no Undo, refused like the studio
  setters while an interaction owns the input.

### 8.2 Storage: a machine setting

- **File:** `~/.mirai_bastel/lookdev_quality.json`, the state directory the file browser already uses (V12).
- **Content:** `{"tier": "auto", "refine": false, "idle_tier": "hoch", "wait": 0.3}`.
- **Read and write:** read once at start, written on change, through a small pure module
  `mirai/lookdev_quality_settings.py` (load / save, a missing or bad file = the defaults, an unknown key ignored).
- **Wiring:** `main.py` passes the path; headless tests use a temp directory.
- **Not in `view.lookdev`, not in the scene, not in Undo.** Quality is a property of the PC (F7, assessment §8).

---

## 9. Files [P]

| Layer | LD-3a | LD-3b |
|---|---|---|
| `viewport/lookdev_quality.py` (new, pure) | `RenderConfig`, tiers, `resolve`, `ActivityTracker`, `AutoTier` | `samples`, `jitter`, `shadow_mode` used |
| `viewport/gpu_timer.py` (new) | the query ring | — |
| `viewport/lookdev_features.py` | `timer_query` | `accum_rgba16f` |
| `viewport/viewport.py` | `lookdev_signature()`, `set_lookdev_config()`, `_render_lookdev` reads the config (shadow instance / updates, cube instance, effects), the program union, the capture by state | the accumulator around the meshes, the jitter hook |
| `viewport/lookdev_pass.py` | owns the timer, the second `KeyShadow` / `EnvCube` | owns the accumulator |
| `viewport/lookdev_accum.py` (new) | — | `Accumulator`, the copy / blend / composite programs |
| `viewport/lookdev_shaders.py` | — | `ACCUM_JITTER` (+ pin) |
| `viewport/live_texture.py` | `revision` | — |
| `mirai/application.py` | the room's tracker, Auto, the per-tick step, setters, status | — |
| `mirai/lookdev_quality_settings.py` (new) | load / save | — |
| `gui/lookdev_model.py`, `gui/lookdev_panel.py` | the block „Qualität“ | progress in the status |
| `main.py` | the settings path | — |
| `experiments/drag_cost/probe_lookdev_room.py` | the rows of §11.1 | the rows of §11.2 |

---

## 10. Tests and gates

### 10.1 LD-3a (container: headless, and xvfb in own processes for GL files)

| # | Gate |
|---|---|
| G-1 | **Refinement off, Hoch = today:** the LookDev frame pixel-identical to `1e5d751` (Gollum cage and SubD 1, Portrait / Dramatic) |
| G-2 | every pin unchanged (Worklight, LookDev eye, skin, eye LD_SHADOW); `test_gl_eye_pass.py` green |
| G-3 | `resolve`: per tier × refine × allowed × features — the table of §2.2; the result ⊆ `effective(allowed, features)` (Q2); the idle-only rule |
| G-4 | `ActivityTracker` with a fake clock: every transition; `held` keeps Interactive; a change in Refine / Converged returns in the same tick; `wait` bounds |
| G-5 | Q1 structurally: `RenderConfig` fields are render fields only; no import of Core mesh / morph / pose / material modules in `lookdev_quality.py` |
| G-6 | **Signature completeness:** a table of every `_render_lookdev` input (camera, size, each mesh revision, model, studio, each effect, `LookDraw` fields, region slots, map paths, eye values, `eye_display`, paint revision, config, features) — each mutated, the signature changes; hover over a panel, the status line and the HUD do not change it |
| G-7 | `AutoTier`: down at p50 > 12 ms, up only with the next tier's remembered p50 < 12, ≤ 1 change / 2 s, nothing outside Interactive; the timer unavailable → Mittel + status |
| G-8 | GL state after a frame per configuration (both shadow instances, both cubes): no FBO bound, units 6–8 unbound, unit 0 active (I-4) |
| G-9 | `shadow_updates`: frozen → `KeyShadow.renders` 0 during a caster drag, +1 in the first Settling frame; every_2nd → every second frame |
| G-10 | precompile: entering with Auto + refinement compiles the union; a tier change afterwards compiles nothing (the program caches unchanged) |
| G-11 | capture in each state saves the configuration of §7; the accumulation and signature unchanged by it |
| G-12 | settings: round trip, missing / bad file = defaults, unknown key ignored; nothing in the scene file (`view.lookdev` unchanged) |
| G-13 | E16 / Q4: the Worklight path creates no timer, signature, tracker, config or second instance; the room probe's `modelling` rows unchanged |
| G-14 | `tests/test_room_rule.py` (R-1) unchanged and green |

### 10.2 LD-3b, additionally

- the accumulation of N jittered frames equals the mean of N separate renders (llvmpipe, a tolerance);
- Converged → zero skin / eye / depth draws per tick (counters);
- a camera nudge resets within one tick;
- the crossfade weights;
- `ACCUM_JITTER` off = every earlier source, and its variants pinned;
- picking is never jittered (a pick during Refine equals a pick in Interactive);
- `accum_rgba16f` failure forced through a stub → LD-3a's Maximal + status.

---

## 11. Reference-PC measurements

### 11.1 LD-3a (the S1–S9 run is still open, AD-039 §24.4; it is folded into this one)

NVIDIA „Maximale Leistung bevorzugen“, repository root, `.venv312`:

```
python experiments\drag_cost\probe_lookdev_room.py | Tee-Object -FilePath lookdev_room_ld3a.txt
```

| Rows | Decides |
|---|---|
| every built P3 row (S1–S9) | AD-039's open per-slice checks |
| `tier entwurf / mittel / hoch`, framed / close, 1024 / 1080 | Auto's 12 ms target and the tier table (Q-LD3-2) |
| `drag every / every_2nd / frozen` (+ flush / ping-pong) | Q-LD3-1 |
| `idle hoch / maximal` (S9, 2048², cube 256) | the 50 ms ceiling; the 2048² and 256-sample cost; VRAM (`GL_NVX_gpu_memory_info`) |
| `entry` with Auto + refinement | the precompile time |
| E16 `modelling` / `probe_d3_acceptance.py` | Q4 |

### 11.2 LD-3b probe (in `experiments/`, no `src/`, before LD-3b)

- `accum_rgba16f` stability: 600 frames render → sample at 1024×768 and 1920×1080, GL errors, VRAM;
- the copy + blend + composite cost; the converged per-tick cost;
- time to converge, N = 16 / 64;
- the image of (i) S9 rotated vs (ii) the jittered key vs the 32-key reference (`experiments/lookdev_pcss/compare.py`).

---

## 12. Stop points and open questions

### 12.1 Stop points (Haltepunkte)

1. **This AD:** Manu's go before any `src/` change.
2. **After LD-3a is built:** the reference-PC run (§11.1) and Manu's practical test (about 15 minutes on
   `scenes/Gollum_Head_05.mirai.json`):
   - Auto while orbiting a close-up;
   - a pose drag with each `shadow_updates`;
   - „In Ruhe verfeinern“ with Hoch and Maximal: S9 appears after 0.3 s;
   - „Bild speichern“ in each state.
3. **Before LD-3b:** the probe of §11.2, then Manu's go on its numbers and the shadow candidate.

### 12.2 Open questions for Manu [O], with proposals

| # | Question | Proposal |
|---|---|---|
| Q-LD3-1 | The key map while a caster is dragged: rendered every frame, every second frame, or frozen until settling? | decided on §11.1's drag rows: the cheapest of `every` / `every_2nd` that holds 30 fps for Mittel / Hoch; Entwurf frozen |
| Q-LD3-2 | Auto's GPU target | 12 ms p50 `PROVISIONAL`; §11.1 calibrates |
| Q-LD3-3 | Offer „Maximal“ before LD-3b (as delayed activation: 2048² + 256-sample cube + S9)? | yes; LD-3b adds accumulation to the same name |
| Q-S9-1 (AD-039) | S9 on by default? | becomes „which tiers allow it“: allowed by default once your S9 practical test passes; the tier then decides when |

---

## 13. Deviations from the proposal §12.3 (with reasons)

| # | Proposal §12.3 | This AD | Why |
|---|---|---|---|
| X1 | one Auto over all frames, moving p50 + hysteresis | Auto on interactive frames only; still images never downgraded | Q8: the room is for judging the look (assessment §5.3) |
| X2 | Auto = Full / Balanced / Draft | interactive tier Auto / Hoch / Mittel / Entwurf + idle tier Hoch / Maximal | F-R1: two budgets |
| X3 | knobs: studio specular on skin, rim / backscatter, specular AA, eye tier | the P3 effect masks, shadow size and updates, cube samples, accumulation | the measured costs (AD-039 §2.5, §11; assessment §2.4) |
| X4 | "Qualität: Auto / Hoch / Mittel / Entwurf" with a reason line | the same, plus „In Ruhe verfeinern“, „Ruhe-Qualität“, „Wartezeit“ | F-R1, F-R2, F-R4 |
| X5 | the capture: one render of what the room shows | by state, never waiting | F-R5 |
| X6 | (implicit) view state | a machine setting | F7: quality belongs to the PC |

---

## 14. Implementation note — LD-3a built (2026-11-25)

**Decision:** Manu, 2026-11-25: „LD-3a bauen nach docs/architecture/AD-040-LOOKDEV-LD3-QUALITY.md … Umfang: §2–§5,
§7–§9 für LD-3a, Gates §10.1, Probe-Zeilen §11.1. Keine Shader-Änderung, alle Pins bleiben. LD-3b ist nicht Teil
dieser Session.“ Built on `d744aa3` (`src/` as at `1e5d751`).

**Kurzfassung (Deutsch):**
- Im LookDev-Panel gibt es unter „Effekte“ den neuen Block **„Qualität“**: „Qualität (beim Arbeiten)“ Auto / Hoch /
  Mittel / Entwurf (Standard Auto), **„In Ruhe verfeinern“** (Standard aus), „Ruhe-Qualität“ Hoch / Maximal,
  „Wartezeit“ 0.1–2 s (Standard 0.3 s), darunter eine Statuszeile („Interaktiv – Hoch (Auto: 8 ms)“, „Ruhe – Maximal“).
  Unter „Mehr“ zusätzlich **„Schatten beim Ziehen“** (jedes Frame / jedes 2. Frame / eingefroren) für deinen
  Praxistest zu Q-LD3-1; Standard „jedes Frame“ = heute.
- Die Einstellung wird **pro Rechner** gespeichert (`~/.mirai_bastel/lookdev_quality.json`), nicht in der Szene und
  nicht im Undo.
- Der Raum erkennt Ruhe an der **Frame-Signatur** (Kamera, Mesh-Revisionen, Studio, Effekte, Materialien, Augen,
  Mal-Textur, Qualität). Bleibt sie 0.3 s gleich, gilt die Ruhe; jede Änderung ist im selben Tick wieder „interaktiv“.
- Mit „In Ruhe verfeinern“: „Weicher Schatten“ nur in Ruhe; „Maximal“ dazu Schattenkarte 2048² und der Cube mit 256
  Samples. Auto misst die GPU-Zeit (nie blockierend) und geht nur bei interaktiven Frames eine Stufe herunter.
- **Hoch ohne Verfeinern ist pixelgleich mit vorher** (geprüft gegen `1e5d751`), keine Shader-Änderung, alle Pins
  unverändert. Im Modelling Room entsteht nichts davon.
- „Bild speichern“ speichert sofort, was der Raum gerade zeigt, und nennt den Zustand („– interaktiv (Hoch)“,
  „– Ruhe (Maximal)“).

### 14.1 What is built

| Layer | Built |
|---|---|
| `viewport/lookdev_quality.py` (new, pure) | `RenderConfig` (effects, shadow_size, shadow_updates, cube_samples, samples = 1, jitter = False); `resolve(tier, allowed, features, refine, state, idle_tier, drops, drag_updates)` with the §2.2 table (Entwurf: shadow, eye shadow, thickness, dual lobe, S8, S9 off; Mittel: S9 off; Hoch: as allowed; Maximal: 2048² + 256 samples; refinement on: S9 idle-only; `shadow_updates` the tier's while Interactive, "every" otherwise); `reachable(...)` (the §5 union); `ActivityTracker` (§3.2, N = 1); `AutoTier` (§4.3); `IdleCeiling` (§4.2); `held_back(...)` (the effect tooltips, §8.1); `status_line(...)`; `intersect` / `subset` / `masked` |
| `viewport/gpu_timer.py` (new) | `GpuTimer`: a ring of 3 `GL_TIME_ELAPSED` queries, read only when `GL_QUERY_RESULT_AVAILABLE`; each result returned with the tag of the frame it measured; a frame that begins inside another timer query (a probe's) is skipped, never nested |
| `viewport/lookdev_features.py` | `FeatureReport.timer_query` + its check (a query begun / ended without a GL error) and the status line „Qualität: Auto aus – Zeitmessung nicht verfügbar“ |
| `viewport/lookdev_shadow.py` | `KeyShadow.update(..., defer)`: a change of the casters' content alone (same casters, key, frustum, resolution) may be postponed `defer` times in a row (0 / 1 / None = every / every_2nd / frozen); `deferred` counts them |
| `viewport/lookdev_pass.py` | `key_shadow(size)` / `env_cube(samples)`: Maximal's second `KeyShadow(2048)` and `EnvCube(samples=256)`, created when first drawn; `timer()`; all released in `release()` |
| `viewport/viewport.py` | `set_lookdev_config(config, reachable, tag)`, `set_lookdev_reachable`, `lookdev_config`, `lookdev_timing`; `_render_lookdev` draws `intersect(effects in force, config.effects)`, the config's map instance and defer, the config's cube instance (no config = the AD-039 frame, unchanged); `_lookdev_programs` over `_lookdev_masks()` (the union of the reachable configurations); `lookdev_signature(size, quality)` (§3.1); the timer around `_render_lookdev` (not around the overlays, not around a capture's extra render); `take_lookdev_gpu_times`, `lookdev_timer_available` |
| `viewport/live_texture.py` | `revision` (+1 on `mark`, `mark_all` and a deferred `finish`) |
| `mirai/lookdev_quality_settings.py` (new) | `QualitySettings` (tier, refine, idle_tier, wait, drag_updates), `load` / `save` / `from_dict` / `default_path`; a missing or bad file or value = the default, unknown keys ignored, atomic write |
| `mirai/application.py` | `set_lookdev_quality_path`, `lookdev_quality`, `set_lookdev_quality(**changes)` (machine setting, written at once; refused while an interaction runs; a new union compiles behind the status line, I-10); the room's tracker / Auto / ceiling (`_start_quality` on entry, `_stop_quality` on closing; their state lives on `controllers/lookdev_room.LookdevRoom` - `quality`, `activity`, `auto`, `ceiling`, … - so `Application` gains no field, AD-027 §3.1); `_quality_step(dt)` in `update_viewport` after `Viewport.sync` (feed Auto / the ceiling, the signature, the tracker, `resolve`, `set_lookdev_config`); `lookdev_activity`, `lookdev_quality_status`, `lookdev_effect_tiers`; the capture's status names the state (§7); every effect / studio push goes through `_push_lookdev_effects` (effects + reachable) |
| `gui/lookdev_model.py`, `gui/lookdev_panel.py` | `QualityRow`, the block „Qualität“ (§8.1) with its status line; `EffectRow.held_back` / `tooltip` („… – gerade zurückgehalten, in Ruhe (Maximal)“) |
| `main.py` | `app.set_lookdev_quality_path(default_path())` |
| `experiments/drag_cost/probe_lookdev_room.py` | the §11.1 rows: `tier entwurf / mittel / hoch` framed / close at 1024×768 and 1920×1080 (`--ld3a-sizes`; the hidden window is resized); `drag every / every_2nd / frozen` (+ flush / pingpong) with `KeyShadow.renders` / `deferred`; `idle hoch / maximal` with the first refine frame, the 256-sample cube build and VRAM; the entries with Auto + refinement (Maximal); `--ld3a none` skips them |

Not touched: every shader source and pin (`lookdev_shaders.py`, the eye shaders), Core, the scene format,
`view.lookdev`, picking, morph, rig, modelling, the Worklight path, `main.run` (the 60 Hz loop), `config/keymap.json`.

### 14.2 Where the build differs from the AD, and why

| # | AD | Built | Why |
|---|---|---|---|
| L1 | §3.1: the signature holds „the `RenderConfig` in force“ | it holds the room's quality key (the tier in force, refinement, idle tier, drag policy), not the configuration | the configuration is a function of the activity state; in the signature, every state change would change the signature and send the room back to Interactive (Settling ↔ Interactive forever). The ceiling's drops are left out for the same reason (they are derived from measurements) |
| L2 | §8.1: four controls | a fifth, „Schatten beim Ziehen“, under „Mehr“ (stored as `drag_updates` in the same file) | §12.1's practical test asks for „a pose drag with each `shadow_updates`“; Q-LD3-1 is open, so the policy needs a switch until the reference-PC run decides it. Default "every" = today. It goes (or becomes fixed) with Q-LD3-1's answer |
| L3 | §3.2: `held` = session, gesture, stroke, `MaterialEdit.held()` | the app sees the GUI's held material control as `room.preview` (non-empty while a slider holds a preview); also a held viewport button (`pointer.active`: a slow orbit) | `MaterialEdit` lives in the panel; the app has the same signal without a GUI dependency. A generic „any panel item active“ was rejected: pressing „Bild speichern“ would make the room Interactive and the capture would never show the idle image |
| L4 | §4.2: Refine drops a knob if „the measured frame“ exceeds 50 ms | the p50 of 5 idle frames (`IDLE_CEILING_FRAMES`); a drop stays until the refinement settings change or the room is entered again | the first refine frame holds one-time costs (the 2048² map's creation, the 256-sample prefilter: 245 ms GPU in the container); one frame would always drop. In LD-3a Converged keeps drawing, so the window fills in 5 ticks. Retrying after every settle would stutter each time |
| L5 | §3.1: „`LiveTexture.revision += 1` on every upload“ | on every `mark` / `mark_all` / deferred `finish` | the host's mark is the change; the upload follows in the next draw. Counting the mark also works headless and before the first draw |
| L6 | §4.3 status: „Interaktiv – Mittel (Auto: 14 ms > 12 ms)“ | below Hoch the reason names the tier above's remembered p50 (why Auto is not one tier higher); at Hoch the current p50 | the status explains the tier, not the current tier's own (lower) time |
| L7 | §4.1 feature check | `timer_query` is probed with the other P3 features, the first time the room asks for timing | the room times every LookDev frame (for Auto and the ceiling); the Worklight never probes (Q4) |
| L8 | §11.1 rows | the tier rows' second size by resizing the hidden window in one run (`--ld3a-sizes`) | one command covers 1024 and 1080 as §11.1's table asks |

Q-LD3-3 („Maximal“ before LD-3b) is built as the AD proposes (selectable now, as delayed activation); it stays Manu's to
confirm in the practical test.

### 14.3 Tests (container, llvmpipe, 2026-11-25)

| Gate | Test |
|---|---|
| G-1 | `test_gl_lookdev_quality.py::test_hoch_without_refinement_draws_the_ad039_frame_pixel_for_pixel` (head, posed and morphed; cage / SubD 1 × Portrait / Dramatic; every effect incl. S8 / S9; Interactive and Converged): the room's frame = `set_lookdev_config(None)`. **Across commits** (a scratch worktree at `1e5d751`, the same script in both trees): `Gollum_Head_05` cage / SubD 1 × Portrait / Dramatic × effects as default / all on, with and without overlays — **16 of 16 frames bit-identical** (384², `glGetError` 0) |
| G-2 | `test_lookdev_shaders.py` 19 passed; `test_gl_eye_pass.py` 135 passed; no file under `lookdev_shaders.py` / eye shaders changed |
| G-3 | `test_lookdev_quality.py`: Q2 over tiers × refine × states × idle tiers × drops × 5 feature reports × 12 allowed sets; the §2.2 table; refinement off = one configuration, Hoch = `effective(allowed)`; the idle-only rule; `shadow_updates` per state; the ceiling's order; `reachable`; `held_back` |
| G-4 | the tracker with a fake dt: every transition, a change returns in the same tick from Settling / Refine / Converged, `held` keeps Interactive, `wait` bounds 0.1 / 2 s |
| G-5 | `RenderConfig`'s fields; `lookdev_quality.py` imports only `statistics`, `collections`, `dataclasses`, `.lookdev_optics` (AST) |
| G-6 | `test_gl_lookdev_quality.py::test_every_input_of_the_frame_changes_the_signature_and_nothing_else_does` (camera, aspect, size, mesh content, layout, model, a studio value, a light, the drawn and the wanted effects, LookDraw base colour / roughness / map path / regions / region faces, the paint revision, eye model (gaze), eye value, eye display, quality key, feature report, the edit object shown; a frame, a capture and the overlays leave it); headless: status line, hover and wire leave it |
| G-7 | `AutoTier`: the 30-frame window, down > 12 ms, ≤ 1 change / 2 s, up only with the next tier's remembered p50 < 12 ms after 60 frames < 6 ms, frames of another tier ignored, no timer → Mittel + status (also in GL with the check forced off); the GL timer measures app frames and feeds Auto; inside a probe's query it skips without a GL error |
| G-8 | the GL state after frames of Hoch, Maximal (both 2048² map and 256-sample cube), Mittel frozen, Entwurf: as found, no FBO, units 6 / 7 and the cube on 8 unbound, unit 0 active; `release()` frees the second instances and the timer |
| G-9 | 8 drag frames: every 8 renders, every_2nd 4, frozen 0 — the lagging map renders once in the first Settling frame |
| G-10 | entering with Auto + refinement (Maximal) compiles the union (S9 and Entwurf variants); every tier switch and Auto's step afterwards compile nothing (program caches unchanged) |
| G-11 | the capture in Interactive (Mittel) and Converged (Maximal) equals the frame the room shows in that state, the images differ, the state and the signature unchanged; „Bild speichern“'s status ends „– Ruhe (Maximal)“ |
| G-12 | the settings round trip, bad / partial / unknown files, the default path; the app writes the file and nothing into the scene file, `view.lookdev` or Undo; a second app reads it |
| G-13 | headless and GL: no tracker, configuration, timing, LookDev pass or timer before entering and after closing; nothing timed in the Worklight |
| G-14 | `tests/test_room_rule.py` green |

Runs:

| Command | Result |
|---|---|
| `python -m pytest tests/test_lookdev_quality.py -q` | 37 passed |
| `python -m pytest tests/test_lookdev_room.py tests/test_gui_lookdev_model.py tests/test_lookdev_optics.py tests/test_live_texture.py tests/test_lookdev_session.py tests/test_lookdev_persistence.py tests/test_room_rule.py -q` | 145 passed |
| `xvfb-run -a python -m pytest tests/test_gl_lookdev_quality.py -q` | 20 passed |
| `xvfb-run -a python -m pytest tests/test_gl_lookdev_shadow.py -q` / `…pass` / `…cube` / `…regions` / `…maps` | 47 / 13 / 13 / 9 / 9 passed |
| `xvfb-run -a python -m pytest tests/test_gl_eye_pass.py -q`, `python -m pytest tests/test_lookdev_shaders.py -q` | 135 / 19 passed (every pin unchanged) |
| `python -m pytest experiments/drag_cost/tests/test_probe_lookdev_room.py -q` | 10 passed |
| `xvfb-run -a python -m pytest tests -q --ignore=tests/test_gl_eye_pass.py` | 8,098 passed, 8 skipped; 3 failed, of them 2 pre-existing and failing identically on `d744aa3` (`test_interaction_scenarios.py::test_box_paint_and_lasso_select_and_esc_cancels_a_box` „Paint: 6 vertices selected“ and its purity twin in `test_interaction_structure.py`; `test_scene_menu_local_tmp.py::test_probe_menu_wiring`) - not LD-3a; the third (`test_i_application_init_sets_only_non_modal_fields`) fixed by moving the quality state onto `LookdevRoom` |

### 14.4 Measurement

**Container (llvmpipe, a function check only, no valid times):** `probe_lookdev_room.py --draws 3 --surfaces cage`
ran every row - the S1–S9 rows, `tier …` framed / close at 1024×768 and 1920×1080, `drag every / every_2nd /
frozen` (KeyShadow.renders 8 / 4 / 1 with 0 / 4 / 7 deferred in 8 frames), `idle hoch / maximal` (Converged: S9, map
2048, cube 256), the entry with the union - `glGetError` 0.

**Reference PC (open, §11.1; it also closes AD-039 §24.4's S1–S9 run):** NVIDIA „Maximale Leistung bevorzugen“,
repository root, `.venv312`:

```
python experiments\drag_cost\probe_lookdev_room.py | Tee-Object -FilePath lookdev_room_ld3a.txt
```

It decides Q-LD3-1 (the `drag …` rows: the cheapest of every / every_2nd that holds 30 fps for Mittel / Hoch), Q-LD3-2
(the `tier …` rows calibrate the 12 ms target and the table), the 50 ms ceiling and the 2048² / 256-sample cost (`idle
…`, VRAM), the precompile time (`entry`) and E16 (`modelling`, `modelling after`).

### 14.5 Practical test LD-3a (`scenes/Gollum_Head_05.mirai.json`, about 15 minutes; §12.1 point 2)

LookDev öffnen, Studio Dramatic, SubD 1, „Weicher Schatten“ und „Weiches Licht“ an (Block „Effekte“).
1. **Unverändert:** Qualität Auto, „In Ruhe verfeinern“ aus — das Bild ist das von gestern (Hoch); die Statuszeile
   im Block „Qualität“ zeigt „Interaktiv – Hoch (Auto …)“ beim Drehen und „Ruhe – Hoch“ im Stillstand.
2. **Auto beim Orbit in der Nahansicht:** nah ans Gesicht, länger drehen. Erwartet: bleibt das Bild über 12 ms, geht
   Auto eine Stufe herunter (Statuszeile „Interaktiv – Mittel (Auto: … ms > 12 ms)“); im Stillstand ändert sich das
   Bild nie wegen der Zeitmessung.
3. **Stufen von Hand:** Hoch / Mittel / Entwurf beim Drehen — Mittel ohne Weichen Schatten, Entwurf ohne Schatten,
   Doppel-Glanz, Durchleuchtung und Weiches Licht. Tooltip eines zurückgehaltenen Effekts: „… gerade zurückgehalten,
   aktiv in: …“.
4. **Pose-Drag mit jedem „Schatten beim Ziehen“** (unter „Mehr“): jedes Frame / jedes 2. Frame / eingefroren, je einen
   Kiefer- oder Morph-Drag. Erwartet: eingefroren bleibt der Schatten während des Ziehens stehen und springt beim
   Loslassen nach; jedes 2. Frame ruckelt der Schatten leicht. Was fühlt sich für dich richtig an (Q-LD3-1)?
5. **„In Ruhe verfeinern“ an, Ruhe-Qualität Hoch, dann Maximal:** beim Drehen kein Weicher Schatten; 0.3 s nach dem
   Loslassen erscheint er (Statuszeile „Ruhe – Hoch“ / „Ruhe – Maximal“). Maximal: das erste Mal ein kurzer Hänger
   (2048²-Karte, 256-Sample-Cube), danach nicht mehr. Wartezeit 0.1 s und 2 s ausprobieren.
6. **„Bild speichern“ in jedem Zustand:** beim Drehen (die Meldung endet „– interaktiv (…)“) und in Ruhe („– Ruhe
   (Maximal)“); es wird nie gewartet, und das gespeicherte Bild ist das gezeigte.
7. **Maschinen-Einstellung:** App neu starten — die Qualität ist wie eingestellt; eine Szene speichern / laden ändert sie
   nicht; Undo berührt sie nicht.
8. **Modelling Room:** LookDev schließen — Worklight wie vorher.

**Open for Manu [O]:** Q-LD3-1 and Q-LD3-2 after the reference-PC run; Q-LD3-3 („Maximal“ before LD-3b, built
selectable) and the practical test's verdict; then §12.1 point 3 (the LD-3b probe, §11.2) before any LD-3b work.
