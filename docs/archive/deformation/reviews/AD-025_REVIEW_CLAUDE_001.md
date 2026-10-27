# Independent Review — AD-025 "Topology Identity, Provenance and Point Layers" (PROPOSED)

> **Reviewer:** Claude (claude.ai/code, fresh session, no prior chat or plan context)
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/deformation/reviews/AD-025_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** branch `claude/kind-allen-9umqf3` @ `83044a2` (PR #50, base `main` @ `a53c14f`).
> `83044a2` is docs-only; `src/`, `tests/` and `experiments/` are as at `a53c14f`.
> **Subject:** `docs/architecture/AD-025-TOPOLOGY-PROVENANCE-AND-POINT-LAYERS.md` (PROPOSED, 2026-10-27); input
> `docs/research/deformation/MESH_ARCHITECTURE_AUDIT_2026-10-27.md`.
> **Mode:** review only. No source, test, AD or other document edited; this file is the only change.
> **Status:** Archived first-pass review — preserved verbatim; answers belong in AD-025.
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions.

Evidence tags: **VERIFIED (code)** = read at `83044a2`, `file:line`; **VERIFIED (probe X)** = a throwaway probe outside
the repository (scratchpad), code and output in the appendix; **UNVERIFIED** = not checked here; *(reading)* = my
interpretation. Every number I produced is a **container number** (Linux 6.18.44, Intel Xeon @ 2.10 GHz, 4 logical
cores, Python 3.13.17, headless, no GL). **None is a reference-PC number.** Container timings varied up to ~2× between
runs of the same probe; read them as orders of magnitude.

Independence: I did not see the AD author's probes (the AD says they were not kept). My MVC, journal and memory
prototypes are written from the AD's text and the cited papers' formula, not from any prior code.

---

## What was read, what was run

**Read in full:** AD-025; ROADMAP ARCH-02; `src/core/mesh.py` (classes, journal, every primitive, `export_state` /
`load_state`, `_apply_records`); `src/core/operations/collapse.py`; `src/mirai/symmetry_declarations.py`;
`src/mirai/object_mirror.py`; `docs/future_ideas/ANIMATION.md` (morph section); the AD-023 review format
(`docs/archive/viewport_v02/reviews/AD-023_REVIEW_CLAUDE_001.md`).
**Read in part:** audit §G (phases) and section list; AD-023 §2 H1 exactness contract and §9; CORE_V1_FREEZE §1, §4, §7,
start of §7.1; AD-017 addendum K1 (`AD-017_FINAL_DECISIONS_2026-09-22.md:101-172`); AD-021 §4.9; AD-REGIONS-01 (the
~4 MiB / ~55 ms line); `src/core/operations/topology.py`, `transform.py:206-230`, `serialization.py` (version handling);
`src/mirai/topology/knife_resolve.py` (`kept_*`, checkpoints, `SessionStart`, `split_face_path`, `select_bridge`,
`close_loop_with_bridges`, `mesh_content`); `symmetric_knife.py:340-440, 540-600`; `symmetric_ops.py:150-420`;
`topology/extrude.py:160-330, 380-390`; `scene_objects.py:405-417`; `object_space.py:46-72`;
`application.py` (`_connect_command` 2425-2540, `mirror_copy` 1337-1370, Apply transform 1860-1890,
`_symmetry_cycle` 2212-2228, key dispatch 4095-4125, `_apply_undo_redo` 5375-5435, `_mesh_transaction` 5461-5510,
`_gate_refuses` 5595-5607); `interaction/commands.py` (all constants); `scene_menu.py:95-145`; `morph_bridge.py`;
every `Mesh.watch()` consumer (`viewport/render_mesh.py`, `mirai/viewport/picking_cache.py`,
`subdivision/preview.py`, `soft_selection/gl_shading.py`); `viewport/derived.py:70-125`;
`topology/face_geometry.py:75-100`; `viewport/picking.py:287-306`; `regions.py:354-372`;
`tests/test_mesh_change_journal.py:30-160`.
**Grepped:** every `add_vertex(`, `split_edge(`, `split_face(`, `collapse_edge(`, `load_state(`, `from_state(`,
`export_state()`, `set_vertex_position(`, `begin_change()`, `record_mesh_change(`, `_mesh_transaction(`, `MeshDelta(`
and `MeshChange` slot reader in `src/`; every write to `Mesh._vertices` in `src/core/mesh.py`; every test / tool that
filters or iterates `export_state()` keys (`tests/`, `src/`, `experiments/knife_oracle`, `experiments/morph_lab`).
**Not read:** audit §C–§F and addenda in full (I read §G and the headings; the AD's claims were checked against code,
not against the audit); AD-SYM-03 §2.5 text (the declaration module's docstring was read instead); Morph Lab README;
AD-021 §4.5.
**Run:** seven throwaway probes A–G (appendix), headless, outside the repository. **No test suite was run** (review
only, nothing changed; no finding depends on a test result).

---

## Verdict

**ACCEPT WITH CHANGES.** No blocker.

What holds: every fact F-1…F-12 is correct in substance (two are imprecise: m-2, m-3); the inventory of vertex
creation / deletion is complete in `src/` (F-2 / F-3, VERIFIED); F-6 (symmetric Knife 0.5-then-snap) is real; the §3
table matches the code row by row; the journal design follows AD-023's mechanism and meets its six-point contract if the
apply order and the file-ordering rule are tested as proposed; memory and per-write journal cost reproduce (probe A);
the MVC planar claims and the gollum_20k warp distribution reproduce exactly (probe B); the top-level
`"layer_id_counter"` breaks no reader; the six ARCH-02 questions are answered.

What does not hold or is missing: the closed-Knife composition error is 2.5–10× larger than stated and the AD-017
open point "pass the parent corner data in" is not considered (M-1); bulk layer operations journaled per element cost
GiB at the AD's own 50-target scale (M-2); the fail-closed enumeration covers `commands.py` only, not the menu /
method entry points that reach meshes (M-3); moving all interpolation into Phase 2 is the precautionary Core build that
CORE_V1_FREEZE §1 excludes and ANIMATION.md item 5 does not need yet (M-4); H3 `"keep"` is not a well-defined rule
(M-5).

**Blockers:** none. **Major:** M-1 … M-5. **Minor:** m-1 … m-9. **Nit:** n-1 … n-6.

---

## Answers to the review questions (short; details in the findings)

1. **§1 / §3 against the code.** VERIFIED (code): F-1 `mesh.py:157`, `:316`; F-2 `mesh.py:439`, `:568`, `:867`,
   `extrude.py:229`, `scene_factory.py:40-191`, `subdivision/preview.py:442`, `object_mirror.py:84`; F-3
   `mesh.py:733-738`, `:1632-1690`, `load_state :1474-1481`; F-4 `mesh.py:566`, `:629-633`, `collapse.py:83`, `:94`;
   F-5 `mesh.py:865-867`, `picking.py:287-306`, `knife_resolve.py:418-449`; F-6 `symmetric_knife.py:392-397`,
   `symmetric_ops.py:196`; F-7 `scene_objects.py:405-412`, `application.py:1875`, `object_space.py:65-71`,
   `object_mirror.py:84-104`; F-9 `knife_resolve.py:291-313`, `:554`, `regions.py:361`; F-10 the five watches at the
   cited lines. Imprecise: F-5 / §4.1 "ear clipping in the Newell plane" (m-2), F-8 "every commit boundary is one
   journal recording" (m-3), F-10 "up to six logs" (m-4). The §3 rows (kept / created / invalidated) match the
   docstrings and code; Extrude's orphan cleanup is `delete_edges` (`extrude.py:384-389`) as stated.
2. **Every vertex creation / deletion.** Complete: the only writes to `Mesh._vertices` are `add_vertex :444`,
   `_delete_vertex :737`, `load_state :1474/:1481`, `_apply_records :1683/:1688`; nothing outside the Core touches
   the container. Position writes that are frame changes: only `apply_placement` (`scene_objects.py:412`); mirror copy
   builds a new mesh. Two position post-processors after a primitive exist, not one: the symmetric Knife (F-6) and the
   symmetric Collapse snap (`symmetric_ops.py:330-343`, harmless for `"average"`, relevant for `"keep"`, M-5).
3. **§4.2 vs AD-023 §2 H1.** Points (1)–(3), (5), (6) hold as designed. (4) holds only if the export ordering is tested
   with an order-sensitive comparison — the snapshot oracle compares dicts, which are order-blind (m-7). Apply order
   (meta create → values → meta remove) is correct for Undo and Redo of add / remove layer (traced by hand; *reading*).
   `revert_change` on a Knife checkpoint: same mechanics as positions (`mesh.py:1565-1580`), fine if the layer slots are
   reset there too (T-2 must check it). `load_state` under a journal: fine; without a journal it must also drop the old
   layers (m-7). Counters: fine. Export keys: fine (below). `MeshChange` internal readers: only `SessionStart`
   (`knife_resolve.py:291-313`) and `regions.candidate_parents`; no reader of `MeshDelta` fields outside the Core.
4. **Measurements.** Memory: holds exactly (0.57 / 4.09 MiB at 20k, 2.26 / 16.35 MiB at 87.5k; AD 0.57 / 3.96,
   2.14 / 16.22). Per-write journal cost: holds as an upper bound (my lean prototype 0.2 / 0.5 / 0.8 / 1.2–1.3 µs with
   0 / 1 / 3 / 5 logs; AD 0.4–3.6 µs). Dense rewrite: same order (11–34 ms 20k, 35–191 ms 87.5k under one log; noisy,
   GC-sensitive). Warp distribution on gollum_20k: exact (p50 0.36 %, p99 3.88 %, max 20.6 %). MVC planar: holds
   (≤ 1.1e-14 of spread; L-hexagon min weight −0.0099). MVC on warped data: same order, but the AD's metric is
   ill-conditioned (m-1). Nested vs direct: **does not hold** — 2.4–10.4 % of the spread with the resolver's own bridge
   rule, up to 21–30 % with opposite-corner bridges, vs. the AD's ≤ 1.1 / ≤ 3.0 % (M-1). MVC cost: 14 µs (quad), 26 µs
   (8-gon) — holds.
5. **Gate coverage of `commands.py`.** Every constant that reaches a mesh mutation is classifiable: position-only TWEAK,
   MOVE, ROTATE, SCALE, LOOP_SLIDE, SMOOTH, RELAX, RESYMMETRIZE; declared / locked CONNECT (per `CContext`),
   LOOP_INSERT, EXTRUDE, COLLAPSE, APPLY_TRANSFORM; allowed DELETE, DISSOLVE, DISSOLVE_NO_CLEANUP, CAP; non-point
   SYMMETRY_CYCLE (`application.py:2212-2228`), REGION_*, KNIFE_COMMIT / KNIFE_LIFT (inside the gated session),
   SPLIT_EDGE (no production binding found). **Not covered:** entry points that are not commands — mirror copy is a
   menu method (`scene_menu.py:119-122` → `Application.mirror_copy`), `apply_mesh_change` (hosts), Morph Lab send
   (copies layers) — and Apply transform acts on every placed object's mesh, not "the mesh" (M-3).
6. **§8 smallest? §9 catches a wrong implementation?** §8 is the smallest extension *for the AD's chosen scope*; the
   scope itself is larger than Phase 2 needs (M-4). §9 catches the listed mutations; it would not catch an unsorted
   export, a non-journal `load_state` that keeps stale layers, or a per-element bulk journal blowing memory (m-7, M-2).
   T-6 as written locks the per-call composition in golden tests (M-1).
7. **ARCH-02 questions and H1–H5.** All six answered in §2. H1, H2, H4, H5 are real parameters. H3 is a parameter with
   an ill-defined option (M-5). Silently decided: the component-mode rotate / scale rule (labelled "keine Frage",
   m-9) and the Kurzfassung's Ctrl+A promise, which contradicts the H1 default (m-5). Each H answerable in one line:
   yes, except H5, which bundles three questions (n-3).

**Questions to challenge:**

- **Interpolation in Phase 2 (X-11).** Right for the exact, trivially specified rules (`split_edge`, `collapse_*`
  average, `add_vertex(origin)`, deletion). Wrong for `split_face` interior points: its rule is not settled (M-1), it has
  no consumer before Phase 5, and ANIMATION.md item 5 allows the lock. Split it (M-4).
- **MVC vs. barycentric (X-10).** For realistic smooth offsets MVC is good enough (probe C2: the new target point lies
  p99 0.1–3.3 % of the bump amplitude off the target's drawn surface). The rejection reason is incomplete: barycentric
  on the drawn triangle puts the new point exactly on the target's drawn surface (probe C: 1e-13), and the Core need
  not depend on the viewport for it — the Knife already knows the triangle and can pass the origin (AD-017 open point).
  The per-call composition rule is not "small" (M-1).
- **`add_vertex` without origin: raise or defaults?** Raise (fail-closed; a zero offset is a silent dent). Condition:
  inside `split_edge` / `split_face` the origin is computed and validated before the first mutation — today both
  mutate before calling `add_vertex` (`mesh.py:563` before `:568`, `:865` before `:867`).
- **Per-layer H2 / H3 vs. mesh-wide.** Per-layer is fine and costs nothing; a weights layer must never accept `"zero"`
  (an unbound vertex) — validate rules per kind. Drop or redefine `"keep"` (M-5).
- **Edit vs. frame change for whole-mesh rotate / scale in `1`/`2`/`3`.** Consistent with J-3 and with relative shape
  keys; but it is artist-facing behaviour — ask it in one line (m-9).
- **One symmetric gate key (Knife)?** Enough for the plain coordinators under `"average"` (each side runs its own
  primitive). Not enough under `"keep"` (symmetric Collapse picks non-partner survivors, probe F) — another reason for
  M-5. Better than more keys: the declared-entry rule test runs every entry on a plain *and* a symmetric fixture.
- **`MeshChange` / `MeshDelta` consumers on a layer-only change.** None misbehaves: render mesh (`render_mesh.py:618-652`),
  pick cache (`picking_cache.py:137`, `:169`, `:293`), SubD (`preview.py:266-284`) and soft shading
  (`gl_shading.py:134`) read element slots only. Cost side effects: `_mesh_transaction` takes the topology path when
  `moved_of` is None (`application.py:5498-5500`), a full rebuild below `INCREMENTAL_MIN_ELEMENTS = 2048`
  (`render_mesh.py:114`, `:267`); `_apply_undo_redo` runs `_sync_object_views` for a mesh step (`:5430-5431`) (m-8).
- **Top-level `"layer_id_counter"`.** Breaks nothing: every content filter drops it (`_counter` / `_id_counter`
  suffix: `knife_resolve.py:554`, `tests/test_mesh_change_journal.py:38` and 20 more); the explicit three-key filters
  (`test_symmetric_ops.py:59`, `test_symmetric_removal.py:576`, `test_scene_serialization.py:98`) keep it but compare
  states with equal counters; `tests/knife_kept_replay.py:96` iterates all `_counter` keys with `>=` — holds, the Knife
  never moves the layer counter. No test pins the export key set (grep), so T-4's exception is empty (n-5).

---

## Findings

### M-1 — The closed-Knife composition error is understated, and the tool-supplied origin is not considered (MAJOR)

**Evidence.**
- VERIFIED (probe D, D2): two real `close_loop_with_bridges` calls, values by the per-call MVC rule vs. one direct MVC
  over the root face. Affine data: ≤ 1.5e-15 relative (holds). With the resolver's own `select_bridge`: unit quad
  smooth 2.7 %, random corners 2.4 %; 8-gon smooth 0.8 %, random corners **10.4 %** of the spread. With bridges to
  opposite quad corners (a legal `select_bridge` result for some loops): smooth **20.8 %**, random **29.7 %**. AD §4.1:
  "≤ 1.1 % (smooth) / ≤ 3.0 % (random corner data)". The error depends on where the bridges land — an internal
  "LAB DEFAULT rule" (`knife_resolve.py:379-395`), so a later bridge-rule change changes target values.
- VERIFIED (probe C): on a planar base face with non-affine offsets, the MVC-placed new point lies up to 75 % of the
  offset magnitude off the target's drawn surface; barycentric on the base's drawn triangle lies on it (≤ 1e-13).
  VERIFIED (probe C2): for smooth Gaussian bumps on gollum_20k the MVC deviation is small (p99 0.1–3.3 %, max
  0.8–7.6 % of the amplitude). So MVC is acceptable on realistic data, but the AD's X-10 argument omits the criterion
  that matters visually (does the cut move the target surface?).
- VERIFIED (code): AD-017's own open point, `AD-017_FINAL_DECISIONS_2026-09-22.md:167`: "whether a later provenance
  layer wants the interior vertex's 'parent corner data at creation time' passed in". AD-025 introduces exactly that
  mechanism for `add_vertex` (`origin=`) but not for `split_face`. The Knife knows each interior point's hit triangle
  (`picking.py:295-305`) and the root face's corners stay live through both calls (`split_face` keeps all boundary
  vertices, `mesh.py` docstring), so an origin over the root corners is expressible with the AD's own `VertexOrigin`.

**Proposed change.** (a) Correct the §4.1 composition numbers and say they depend on bridge placement. (b) Add
`split_face(..., origins=None)` (one `VertexOrigin` per interior position; keyword with default, additive like
`add_vertex`) as the tool path; MVC stays the fallback for callers without origins. The Knife passes the barycentric
weights of its hit triangle over the *root* face's corners, which removes the composition error and the
off-target-surface error and keeps the Core free of the viewport's triangulation. (c) T-6 then compares with that
direct rule, not with a replay of the per-call rule. (d) If (b) is not taken, record why in §5 (X-10 row) and accept
the measured composition error explicitly.

### M-2 — Bulk layer operations journaled per element cost GiB at the AD's own target scale (MAJOR)

**Evidence.** VERIFIED (probe G): Apply transform's `map_vector_layers` on gollum (87.5k V) with 5 dense layers, journaled
per element: peak 133 MiB with one recording, **258 MiB** with one recording plus the 5 watches of an edited mesh
(F-10); held afterwards (journals, delta pairs, new values) 130 / 255 MiB. Linear in layers → 50 dense layers
≈ 1.3 / 2.5 GiB transient, a large share retained in the history entry. VERIFIED (probe A): the journal per log is
≈ 2.5 MiB (20k) / 10 MiB (87.5k) per dense layer, i.e. 5 watches multiply it by 5 although no watch reads layer values
(answer 7 above). Same pattern: `remove_point_layer` of a dense layer (§4.2, "O(values)") and `load_state` replacing
layers under a journal. The AD lists the whole-layer record only as a time follow-up (§4.3) and §12's guard is a
per-watch opt-out "if Phase 3 measures it" — but Phase 2 freezes the `MeshChange` / `MeshDelta` layer slots, so adding
a second record shape later is another Core change.

**Proposed change.** In Phase 2: (a) a whole-layer record for bulk operations — `map_vector_layers`,
`remove_point_layer`, a layer replaced by `load_state` — that keeps a reference to the old value dict and builds a new
one (O(1) journal memory, one layer copy), beside the per-element record for sparse edits; (b) `MeshWatch` records only
the set of layer-touched vertex IDs (or nothing) instead of before-values; recordings keep before-values. Add one row to
§9's measured list: Apply transform with 50 sparse and 10 dense layers at 87.5k, peak memory under five watches.

### M-3 — The fail-closed enumeration covers `commands.py`, not the other entry points that reach a mesh (MAJOR)

**Evidence.** VERIFIED (code): mirror copy is not a command constant; it is a menu entry
(`scene_menu.py:119-122`, `run_mirror_entry :136-141`) calling `Application.mirror_copy` (`application.py:1337`), which
builds the copy with `mirror_mesh` through the public API (`object_mirror.py:84-104`) — with layers it would silently
create a copy without targets. §4.4's enumeration test "classifies every command that can reach a mesh mutation"; a
test over `commands.py` cannot see this path, nor `apply_mesh_change` (hosts, `application.py:5436`), nor
`morph_bridge.write_object_scene` (`morph_bridge.py:58`, copies layers into the lab). Apply transform bakes every placed
object (`application.py:1872-1876`), so "consults the gate only when the mesh has layers" must mean *each target mesh*,
not the edit mesh. The existing `_gate_refuses` (`application.py:5595`) is keyed by command string only.

**Proposed change.** Define the gate's key space as "every `Application` method and command that can reach
`_mesh_transaction`, `record_mesh_change`, `begin_change` or a new mesh built from an existing one", enumerate it from
the code (commands, `scene_menu.MIRROR_ENTRIES`, the public mutating methods), and check per target mesh. The
enumeration test fails on an unclassified method, not only on an unclassified command. State that hosts
(`apply_mesh_change`) get the backstop only (already in §4.4) and that the Morph Lab copy carries layers (n-1).

### M-4 — Phase 2 builds interpolation ahead of any consumer; CORE_V1_FREEZE §1 / §4 and ANIMATION.md item 5 not reconciled (MAJOR)

**Evidence.** VERIFIED (code): CORE_V1_FREEZE §1 "Zukünftige Systeme werden nicht vorsorglich in den Core eingebaut";
§4 lists "Morph Targets" and "Herkunfts-/Provenance-Metadaten" as not part of the freeze. ANIMATION.md item 5 (Manu
2026-10-20): topology edits after targets "darf … gesperrt bleiben (muss jetzt noch nicht funktionieren)", the lock must
only not block the later transfer. AD-025's H1 default locks every vertex-creating or merging tool until Phase 5
(§10), so in Phases 2–4 the Core interpolation (MVC, collapse merge rules, `map_vector_layers`) has no production
caller; only tests exercise it. X-11's argument ("one §7 exception and one oracle") is a cost argument, not a
requirement under §7 step 1. The riskiest piece (the `split_face` rule) is the one not settled (M-1).

**Proposed change.** Phase 2 = layers, journal (incl. M-2), file, deletion, `add_vertex(origin)` + backstop, gate, and
the exact rules whose specification is the position's own expression (`split_edge`, `collapse_edge` / `collapse_elements`
average). `split_face` with k > 0 on a layered mesh raises `MeshError` before the first mutation until Phase 5 (it is
unreachable through the gate anyway), and Phase 5 adds the interior rule with the Knife wiring and the artist test
(origins per M-1, or MVC). Alternatively keep X-11 but argue it against §1 explicitly. In both cases update CORE_V1_FREEZE
§4 ("Morph Targets", "Provenance") in the implementing commit — §8 does not mention it.

### M-5 — H3 `"keep"` is not a well-defined rule and is not mirror-consistent (MAJOR)

**Evidence.** VERIFIED (code): `collapse_edge` keeps the edge's stored `v0` (`mesh.py:629`); `_merge_group` collapses
in candidate-ID order and keeps whatever survives (`collapse.py:163-180`). Which vertex keeps its value therefore
depends on edge orientation and ID order, not on anything the artist sees. VERIFIED (probe F): on a 6×6 plane with an X
symmetry, 6 of 6 symmetric edge collapses keep a survivor on the mirror side that is **not** the partner of the source
side's survivor — under `"keep"` the target becomes asymmetric. The Kurzfassung's H3 alternative ("die eines der
Punkte") hides that "which one" is arbitrary.

**Proposed change.** Drop `"keep"` from Phase 2 (H3 = `"average"` only, the other answer to be specified when Manu asks
for it), or define it on something visible (e.g. the value of the group vertex nearest the centroid, ties by mirrored
position) and add a symmetric-fixture rule test. Reword H3 in the Kurzfassung.

### m-1 — The MVC error metric "% of the face's value spread" is ill-conditioned (MINOR)

VERIFIED (probe B): with random gradients the worst case on gollum_20k is 233 % of the spread (a gradient almost along
the face normal makes the spread ~0). Worst-gradient warped quads: 3.9 / 17.7 / 40.5 % of the spread at warp
0.05 / 0.2 / 0.5 (AD: 2 / 9 / 16 %). A stable metric is error / (|∇f| · face size): gollum_20k p50 0.18 %, p99 2.4 %,
max 39 %. For a 5 mm offset change across a face along the worst direction: p99 ≈ 0.12 mm (AD: 0.09 mm). The AD's
conclusion survives; restate the numbers in a stable metric and say which gradient was used.

### m-2 — The viewport triangulation projects onto a dominant axis plane, not the Newell plane (MINOR)

VERIFIED (code): `viewport/derived.py:86-98` (`_polygon_plane_axes`) drops one coordinate by the dominant Newell
component; only `FaceFrame` (`mirai/topology/face_geometry.py:75-100`) uses the true Newell plane. F-5 and §4.1 ("the
plane `FaceFrame` and the viewport triangulation use") are half wrong. Also: the Core cannot import `FaceFrame`
(`src/mirai`), so §4.1 means a third Newell-plane implementation in `core/mesh.py` — say so in §8.

### m-3 — F-8: transforms are position snapshots, not journal recordings (MINOR)

VERIFIED (code): Move / Rotate / Scale / Tweak commit `VertexTransformCommand` start / end positions
(`core/operations/transform.py:206-226`, `:359-365`). Harmless for layers (position-only, edit rule), but the H4
editing view will need its own command that writes layer values (a gesture on the view is not a position write).
Correct F-8 and note it under H4.

### m-4 — F-10 / §12: more than six logs are active in real paths (MINOR)

VERIFIED (code): a Knife commit holds the 5 watches + `SessionStart` (`knife_resolve.py:275`) + nested checkpoints
(`:238`, one per bridge candidate / run / closed shape); Collapse holds `_mesh_transaction`'s recording + its own
(`collapse.py:85`); the Morph Lab adds a watch (`experiments/morph_lab/morph.py:100`). Cost per extra log ≈ 0.15–0.2 µs
per first-touch write (probe A). Replace "up to six" by the real bound or by "one per nesting level".

### m-5 — The Kurzfassung promises Ctrl+A carries the targets, while the H1 default locks Apply transform (MINOR)

AD §10 H1: "locked … (and Apply transform / mirror copy until wired)", §7 Phase 3 only "recommended". Kurzfassung
"Zur Kenntnis": "übernimmst den Transform (`Strg+A`) — das nimmt die Ziele mit". Its H1 line also omits Apply / mirror
copy from the locked list. Make the two agree (wire Apply with Phase 3 as a decision, or say "bis dahin gesperrt").

### m-6 — Old builds silently drop `"point_layers"` (MINOR)

VERIFIED (code): `serialization.py:58-76` accepts versions 2, 3, 4 and reads mesh state via `Mesh.from_state`; an older
build ignores unknown keys, so opening a layered file there and saving deletes every target without a message. The
`"symmetry"` / `"face_regions"` precedent has the same property but loses far less work. Either write
`FORMAT_VERSION` 5 only when a mesh has layers (old builds then refuse, fail-closed; files without layers stay 4), or
list the risk in §12.

### m-7 — §9 misses three mutation checks (MINOR)

(a) Export order: the oracle compares dicts (`tests/test_mesh_change_journal.py:35-38`), which ignore order, so an
unsorted `"values"` export passes; add an order-sensitive check (JSON text or key lists). (b) `load_state` without a
journal must clear old layers (`mesh.py:1473-1481` clears only the three containers today); add a mutation check
"stale layer survives a non-journal load". (c) State and test that `set_point_layer_info` cannot change `kind`, and
that `load_state` validates layers before its first write (an invalid file must leave the mesh unchanged).

### m-8 — Layer-only changes take the topology notification path (MINOR)

VERIFIED (code): `_mesh_transaction` calls `_notify_topology_changed()` when `moved_of` is None
(`application.py:5498-5500`); below 2048 elements that is a full rebuild (`render_mesh.py:114`, `:267`).
`_apply_undo_redo` runs `_sync_object_views` for a mesh step (`:5430-5431`). Correct but wasteful for Phase 3 offset
edits; record in §4.2 "Consumers" that layer-only transactions pass `moved_of → set()` and that the selection-mirror
entry marks them as non-topology. T-9 covers Undo only.

### m-9 — Missing alternative and one silent artist decision (MINOR)

(a) §5 lacks "values inside the vertex record" (`_VertexData` / `VertexRecord` carries the layer values, so `_touch_v`,
`_apply_records`, deletion and `load_state` handle layers for free). Not used, plausibly, because `VertexRecord` is read
as a position (`knife_resolve.py:309`, `SessionStart.state()`), every position write would rebuild a larger record, and
one layer write would journal all layers of the vertex — say so. (b) The component-mode whole-mesh rotate / scale rule
(§4.3, Kurzfassung "keine Frage") is artist-facing behaviour; it follows from J-3, but ask it as one confirmation line.

### n-1 — `Mesh.from_state(export_state())` copies in the Morph Lab (`lab_scene.py:78-79`, `morph.py:391`) and in `morph_bridge.py:58` will carry the base's layers into base, target and surface copies. Harmless; mention.
### n-2 — Re-Symmetrize (`resymmetrize.py:180`, positions only) leaves targets asymmetric under the edit rule; one line in §6.
### n-3 — H5 bundles three questions (order, morph + SubD from Phase 4, "flüssig / benutzbar"); a "nein" is ambiguous. Split or let Manu answer per part.
### n-4 — `map_vector_layers` with an identity placement should record nothing, as `to_world` returns `p` unchanged for identity (`object_space.py:48-49`).
### n-5 — T-4 "except the assertions that pin the export key set": none exists (grep); drop the clause or name the test.
### n-6 — §4.2 "The Core … does not interpret them": it interprets per kind (combination, `map_vector_layers`, H2 / H3 rules). Say "does not interpret their meaning".

---

## What I could not check

- Reference-PC behaviour of anything here (no reference-PC run; none needed for a docs review).
- The AD author's own probes (not kept), so differences in numbers are explained by my reading of the AD's text.
- Audit §C–§F in full; AD-SYM-03 §2.5 text; AD-021 §4.5; Morph Lab README. The AD's claims depending on them were
  checked against code instead where possible.
- Whether `select_bridge` in real sessions produces opposite-corner bridges often (probe D forces them; D2 uses the
  real rule on random loops).
- Any test run: none was needed for the findings.

---

## Appendix — review probes (container, throwaway, not in the repo)

All files lived in the session scratchpad (`…/scratchpad/probes/`), run with `python3` from there; `objload.py` adds
`/home/user/Mirai-Bastel/src` to `sys.path`. Outputs are verbatim.

### Shared helpers

OBJ loader (`v` / `f` lines only) and the review's own MVC (Hormann & Floater 2006, unit-Newell plane, corner / edge cases decided before the formula as AD §4.1 describes).

`objload.py`:

```python
import sys
sys.path.insert(0, "/home/user/Mirai-Bastel/src")
from core.mesh import Mesh

def load(path, mesh_cls=Mesh):
    pos, faces = [], []
    with open(path) as f:
        for line in f:
            if line.startswith("v "):
                x, y, z = line.split()[1:4]
                pos.append((float(x), float(y), float(z)))
            elif line.startswith("f "):
                faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
    m = mesh_cls()
    ids = [m.add_vertex(p) for p in pos]
    for fc in faces:
        m.add_face([ids[i] for i in fc])
    return m
```

`mvc.py`:

```python
"""Independent MVC (Hormann & Floater 2006) in the unit-Newell plane, written for this review."""
import math

def sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a): return math.sqrt(dot(a, a))

def newell(pts):
    nx = ny = nz = 0.0
    for i, a in enumerate(pts):
        b = pts[(i+1) % len(pts)]
        nx += (a[1]-b[1])*(a[2]+b[2]); ny += (a[2]-b[2])*(a[0]+b[0]); nz += (a[0]-b[0])*(a[1]+b[1])
    return (nx, ny, nz)

def frame(pts):
    n = newell(pts); L = norm(n); n = (n[0]/L, n[1]/L, n[2]/L)
    e = sub(pts[1], pts[0]); e = sub(e, tuple(dot(e, n)*c for c in n)); le = norm(e)
    u = (e[0]/le, e[1]/le, e[2]/le); v = cross(n, u)
    c = tuple(sum(p[k] for p in pts)/len(pts) for k in range(3))
    return n, u, v, c

def mvc(pts, x, eps=1e-12):
    n, u, v, c = frame(pts)
    P = [(dot(sub(p, c), u), dot(sub(p, c), v)) for p in pts]
    X = (dot(sub(x, c), u), dot(sub(x, c), v))
    k = len(P)
    s = [(p[0]-X[0], p[1]-X[1]) for p in P]
    r = [math.hypot(*q) for q in s]
    size = max(max(abs(a[0]-b[0]), abs(a[1]-b[1])) for a in P for b in P)
    for i in range(k):
        if r[i] <= eps*size:
            w = [0.0]*k; w[i] = 1.0; return w
    tan = []
    for i in range(k):
        j = (i+1) % k
        det = s[i][0]*s[j][1]-s[i][1]*s[j][0]
        D = s[i][0]*s[j][0]+s[i][1]*s[j][1]
        if abs(det) <= eps*r[i]*r[j] and D < 0:   # on edge i..j
            w = [0.0]*k; t = r[i]/(r[i]+r[j]); w[i] = 1-t; w[j] = t; return w
        tan.append((r[i]*r[j]-D)/det)
    w = [(tan[i-1]+tan[i])/r[i] for i in range(k)]
    S = sum(w)
    return [wi/S for wi in w]

def fan(pts):
    return [(pts[0], pts[i], pts[i+1]) for i in range(1, len(pts)-1)]

def tri_point(t, a, b):
    s = math.sqrt(a)
    w0, w1, w2 = 1-s, s*(1-b), s*b
    return tuple(w0*t[0][k]+w1*t[1][k]+w2*t[2][k] for k in range(3))
```


### Probe A — layer memory and per-write journal cost (`probe_a_journal_mem.py`)

Prototype subclass of the real `Mesh` with a side table per log. The dense-rewrite rows here ran under `tracemalloc` (slower); probe A2 has the timing without it.

`probe_a_journal_mem.py`:

```python
"""Probe A: layer storage memory and per-write journal cost (prototype subclass, side table per log)."""
import gc, random, sys, time, tracemalloc
from objload import load
from core.mesh import Mesh

class LMesh(Mesh):
    def __init__(self):
        super().__init__()
        self._layer_values = {}
        self._side = {}          # id(log) -> {lid: {vid: before}}
    def begin_change(self):
        ch = super().begin_change(); self._side[id(ch)] = {}; return ch
    def watch(self):
        w = super().watch(); self._side[id(w.peek())] = {}; return w
    def set_layer_value(self, lid, vid, value):
        vals = self._layer_values[lid]
        if self._logs:
            cur = vals.get(vid)
            for log in self._logs:
                rec = self._side.setdefault(id(log), {}).setdefault(lid, {})
                if vid not in rec:
                    rec[vid] = cur
        if value == (0.0, 0.0, 0.0):
            vals.pop(vid, None)
        else:
            vals[vid] = value

def mem_of_layer(vids, frac, seed=1):
    rnd = random.Random(seed)
    chosen = vids if frac >= 1.0 else rnd.sample(vids, int(len(vids) * frac))
    gc.collect(); tracemalloc.start()
    d = {v: (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)) for v in chosen}
    cur, _ = tracemalloc.get_traced_memory(); tracemalloc.stop()
    return cur / 2**20, d

for path in sys.argv[1:]:
    m = load(path, LMesh)
    vids = m.all_vertex_ids()
    print(f"== {path.split('/')[-1]}: {len(vids)} V, {len(m.all_face_ids())} F")
    for frac in (0.15, 1.0):
        mib, _ = mem_of_layer(vids, frac)
        print(f"memory one layer {int(frac*100):3d}%: {mib:.2f} MiB")
    m._layer_values[1] = {}
    rnd = random.Random(2)
    sample = rnd.sample(vids, 5000)
    for nlogs in (0, 1, 3, 5):
        logs = []
        for i in range(nlogs):
            logs.append(m.begin_change())
        vals = [(rnd.random(), rnd.random(), rnd.random()) for _ in sample]
        best = 1e9
        for rep in range(3):
            for log in logs:
                m._side[id(log)] = {}
            t = time.perf_counter()
            for v, val in zip(sample, vals):
                m.set_layer_value(1, v, val)
            best = min(best, (time.perf_counter() - t) / len(sample) * 1e6)
        for log in reversed(logs):
            m.release_change(log)
        print(f"set_layer_value, {nlogs} active logs: {best:.2f} us/write (first touch, best of 3)")
    # dense layer rewrite under 1 and 5 logs
    m._layer_values[2] = {}
    for nlogs in (1, 5):
        logs = [m.begin_change() for _ in range(nlogs)]
        gc.collect(); tracemalloc.start()
        t = time.perf_counter()
        for v in vids:
            m.set_layer_value(2, v, (0.1, 0.2, 0.3))
        dt = time.perf_counter() - t
        cur, _ = tracemalloc.get_traced_memory(); tracemalloc.stop()
        for log in reversed(logs):
            m.release_change(log)
        print(f"dense rewrite under {nlogs} logs: {dt*1e3:.0f} ms, traced alloc {cur/2**20:.1f} MiB (layer+journal)")
        m._layer_values[2] = {}
```

Run: `python3 probe_a_journal_mem.py …/gollum_20k.obj …/gollum.obj`

Output:

```text
== gollum_20k.obj: 21875 V, 21875 F
memory one layer  15%: 0.57 MiB
memory one layer 100%: 4.09 MiB
set_layer_value, 0 active logs: 0.20 us/write (first touch, best of 3)
set_layer_value, 1 active logs: 0.49 us/write (first touch, best of 3)
set_layer_value, 3 active logs: 0.85 us/write (first touch, best of 3)
set_layer_value, 5 active logs: 1.20 us/write (first touch, best of 3)
dense rewrite under 1 logs: 34 ms, traced alloc 2.5 MiB (layer+journal)
dense rewrite under 5 logs: 142 ms, traced alloc 7.5 MiB (layer+journal)
== gollum.obj: 87500 V, 87500 F
memory one layer  15%: 2.26 MiB
memory one layer 100%: 16.35 MiB
set_layer_value, 0 active logs: 0.20 us/write (first touch, best of 3)
set_layer_value, 1 active logs: 0.46 us/write (first touch, best of 3)
set_layer_value, 3 active logs: 0.81 us/write (first touch, best of 3)
set_layer_value, 5 active logs: 1.27 us/write (first touch, best of 3)
dense rewrite under 1 logs: 191 ms, traced alloc 10.0 MiB (layer+journal)
dense rewrite under 5 logs: 674 ms, traced alloc 30.0 MiB (layer+journal)
```

### Probe A2 — dense layer rewrite timing (`probe_a2_dense.py`)

`probe_a2_dense.py`:

```python
"""Probe A2: dense layer rewrite (every vertex once) under 0/1/5 logs, GC on (as in the app) and off; best of 3."""
import gc, sys, time
sys.argv = ["x"]
exec(open("probe_a_journal_mem.py").read().split("def mem_of_layer")[0])
from objload import load
for path in ["/home/user/Mirai-Bastel/examples/meshes/gollum_20k.obj", "/home/user/Mirai-Bastel/examples/meshes/gollum.obj"]:
    m = load(path, LMesh); vids = m.all_vertex_ids()
    for gc_on in (True, False):
        for nlogs in (0, 1, 5):
            best = 1e9
            for rep in range(3):
                m._layer_values[2] = {}
                logs = [m.begin_change() for _ in range(nlogs)]
                gc.collect()
                if not gc_on: gc.disable()
                t = time.perf_counter()
                for v in vids:
                    m.set_layer_value(2, v, (0.1, 0.2, 0.3))
                best = min(best, time.perf_counter() - t)
                gc.enable()
                for log in reversed(logs): m.release_change(log)
                for log in logs: m._side.pop(id(log), None)
            print(f"{path.split('/')[-1]}: dense rewrite, {nlogs} logs, gc {'on ' if gc_on else 'off'}: {best*1e3:.0f} ms")
```

Output:

```text
gollum_20k.obj: dense rewrite, 0 logs, gc on : 3 ms
gollum_20k.obj: dense rewrite, 1 logs, gc on : 11 ms
gollum_20k.obj: dense rewrite, 5 logs, gc on : 30 ms
gollum_20k.obj: dense rewrite, 0 logs, gc off: 3 ms
gollum_20k.obj: dense rewrite, 1 logs, gc off: 10 ms
gollum_20k.obj: dense rewrite, 5 logs, gc off: 50 ms
gollum.obj: dense rewrite, 0 logs, gc on : 14 ms
gollum.obj: dense rewrite, 1 logs, gc on : 35 ms
gollum.obj: dense rewrite, 5 logs, gc on : 170 ms
gollum.obj: dense rewrite, 0 logs, gc off: 13 ms
gollum.obj: dense rewrite, 1 logs, gc off: 43 ms
gollum.obj: dense rewrite, 5 logs, gc off: 113 ms
```

### Probe B — MVC accuracy, planar / warped quad / gollum_20k (`probe_b_mvc.py`)

err/spread = |MVC(f) − f(x)| / (max − min of f over the corners), f affine with a random unit gradient; err/size = the same error / face diameter (per unit gradient). x sampled on the fan triangles (the drawn surface, as Knife ray hits are).

`probe_b_mvc.py`:

```python
"""Probe B: MVC accuracy (affine 3D data) on warped unit quads and real gollum_20k faces;
reference check against barycentric-on-drawn-triangle (X-10)."""
import math, random, sys
from mvc import *
from objload import load

rnd = random.Random(7)
def rand_dir():
    while True:
        g = (rnd.gauss(0,1), rnd.gauss(0,1), rnd.gauss(0,1)); L = norm(g)
        if L > 1e-6: return (g[0]/L, g[1]/L, g[2]/L)

def face_errors(pts, samples=40, grads=8):
    """max over samples of |MVC(f) - f(x)|, per gradient; normalised by f's corner spread and by face size."""
    gs = [rand_dir() for _ in range(grads)]
    size = max(norm(sub(a, b)) for a in pts for b in pts)
    worst_spread, worst_size = 0.0, 0.0
    for _ in range(samples):
        tri = rnd.choice(fan(pts)); x = tri_point(tri, rnd.random(), rnd.random())
        w = mvc(pts, x)
        for g in gs:
            f = [dot(g, p) for p in pts]; fx = dot(g, x)
            err = abs(sum(wi*fi for wi, fi in zip(w, f)) - fx)
            spread = max(f) - min(f)
            worst_spread = max(worst_spread, err/spread)
            worst_size = max(worst_size, err/size)
    return worst_spread, worst_size

print("-- planar sanity (affine reproduction, ideally ~1e-15)")
for name, pts in [("convex quad", [(0,0,0),(1,0,0),(1.2,0.9,0),(0.1,1,0)]),
                  ("L-hexagon", [(0,0,0),(2,0,0),(2,1,0),(1,1,0),(1,2,0),(0,2,0)]),
                  ("tilted pentagon", [tuple(dot(r,p) for r in ((0.8,0,0.6),(0,1,0),(-0.6,0,0.8))) for p in [(0,0,0),(1,0,0),(1.3,0.8,0),(0.5,1.4,0),(-0.2,0.8,0)]])]:
    e = 0.0; mn = 0.0
    for _ in range(2000):
        tri = rnd.choice(fan(pts)) if name != "L-hexagon" else None
        if name == "L-hexagon":
            while True:
                x = (rnd.uniform(0,2), rnd.uniform(0,2), 0.0)
                if not (x[0] > 1 and x[1] > 1): break
        else:
            x = tri_point(tri, rnd.random(), rnd.random())
        w = mvc(pts, x); mn = min(mn, min(w))
        for g in (rand_dir(),):
            f = [dot(g,p) for p in pts]
            e = max(e, abs(sum(a*b for a,b in zip(w,f)) - dot(g,x))/(max(f)-min(f)))
    print(f"{name}: max err/spread {e:.1e}, min weight {mn:.4f}")

print("-- warped unit quad, corner (1,1) lifted by w")
for w in (0.05, 0.2, 0.5):
    pts = [(0,0,0),(1,0,0),(1,1,w),(0,1,0)]
    sp, sz = face_errors(pts, samples=400, grads=32)
    print(f"warp {w}: max err/spread {sp*100:.1f} %, max err/size {sz*100:.2f} %")

print("-- gollum_20k faces")
m = load(sys.argv[1])
warps, e_sp, e_sz = [], [], []
for fid in m.all_face_ids():
    pts = [m.vertex_position(v) for v in m.face_vertices(fid)]
    if len(pts) < 4:
        continue
    n, u, v, c = frame(pts)
    size = max(norm(sub(a, b)) for a in pts for b in pts)
    warps.append(max(abs(dot(sub(p, c), n)) for p in pts)/size)
    sp, sz = face_errors(pts, samples=6, grads=4)
    e_sp.append(sp); e_sz.append(sz)
def q(a, p): a = sorted(a); return a[min(len(a)-1, int(p*len(a)))]
print(f"faces (>=4 corners): {len(warps)}")
print(f"warp p50 {q(warps,.5)*100:.2f} %  p99 {q(warps,.99)*100:.2f} %  max {max(warps)*100:.1f} %")
print(f"err/spread p50 {q(e_sp,.5)*100:.2f} %  p99 {q(e_sp,.99)*100:.2f} %  max {max(e_sp)*100:.1f} %")
print(f"err/size   p50 {q(e_sz,.5)*100:.3f} %  p99 {q(e_sz,.99)*100:.3f} %  max {max(e_sz)*100:.2f} %")
```

Run: `python3 probe_b_mvc.py …/gollum_20k.obj`

Output:

```text
-- planar sanity (affine reproduction, ideally ~1e-15)
convex quad: max err/spread 2.8e-16, min weight 0.0000
L-hexagon: max err/spread 1.1e-14, min weight -0.0099
tilted pentagon: max err/spread 6.5e-16, min weight 0.0000
-- warped unit quad, corner (1,1) lifted by w
warp 0.05: max err/spread 3.9 %, max err/size 0.85 %
warp 0.2: max err/spread 17.7 %, max err/size 3.41 %
warp 0.5: max err/spread 40.5 %, max err/size 7.89 %
-- gollum_20k faces
faces (>=4 corners): 21875
warp p50 0.36 %  p99 3.88 %  max 20.6 %
err/spread p50 0.47 %  p99 11.93 %  max 233.4 %
err/size   p50 0.184 %  p99 2.412 %  max 39.15 %
```

### Probe C — new point vs. the target's drawn surface, random corner offsets (`probe_c_target_surface.py`)

`probe_c_target_surface.py`:

```python
"""Probe C: where does the new point land in the *target* (base + offsets)? Distance of the interpolated target
point from the target face's drawn surface (fan from corner 0, as the viewport draws convex faces), relative to
the offset magnitude. Barycentric weights on the base's drawn triangle (X-10) vs MVC (AD-025 4.1).
Offsets are random per corner (non-affine), magnitude d."""
import math, random, sys
from mvc import *
from objload import load

rnd = random.Random(11)

def closest_on_tri(p, a, b, c):
    # Ericson, Real-Time Collision Detection 5.1.5
    ab, ac, ap = sub(b, a), sub(c, a), sub(p, a)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    if d1 <= 0 and d2 <= 0: return a
    bp = sub(p, b); d3, d4 = dot(ab, bp), dot(ac, bp)
    if d3 >= 0 and d4 <= d3: return b
    vc = d1*d4 - d3*d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        v = d1/(d1-d3); return tuple(a[k]+v*ab[k] for k in range(3))
    cp = sub(p, c); d5, d6 = dot(ab, cp), dot(ac, cp)
    if d6 >= 0 and d5 <= d6: return c
    vb = d5*d2 - d1*d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        w = d2/(d2-d6); return tuple(a[k]+w*ac[k] for k in range(3))
    va = d3*d6 - d5*d4
    if va <= 0 and (d4-d3) >= 0 and (d5-d6) >= 0:
        w = (d4-d3)/((d4-d3)+(d5-d6)); return tuple(b[k]+w*(c[k]-b[k]) for k in range(3))
    denom = 1.0/(va+vb+vc); v, w = vb*denom, vc*denom
    return tuple(a[k]+ab[k]*v+ac[k]*w for k in range(3))

def dist_to_surface(p, tris):
    return min(norm(sub(p, closest_on_tri(p, *t))) for t in tris)

def run(pts, d, samples):
    k = len(pts)
    offs = [tuple(rnd.uniform(-d, d) for _ in range(3)) for _ in range(k)]
    tgt = [tuple(p[i]+o[i] for i in range(3)) for p, o in zip(pts, offs)]
    ttris = fan(tgt)
    e_mvc = e_bar = 0.0
    for _ in range(samples):
        ti = rnd.randrange(k-2); a, b = rnd.random(), rnd.random()
        s = math.sqrt(a); beta = (1-s, s*(1-b), s*b)
        idx = (0, ti+1, ti+2)
        x = tuple(sum(beta[j]*pts[idx[j]][c] for j in range(3)) for c in range(3))
        w = mvc(pts, x)
        o_m = tuple(sum(w[i]*offs[i][c] for i in range(k)) for c in range(3))
        o_b = tuple(sum(beta[j]*offs[idx[j]][c] for j in range(3)) for c in range(3))
        e_mvc = max(e_mvc, dist_to_surface(tuple(x[c]+o_m[c] for c in range(3)), ttris))
        e_bar = max(e_bar, dist_to_surface(tuple(x[c]+o_b[c] for c in range(3)), ttris))
    return e_mvc/d, e_bar/d

print("-- planar unit quad, random corner offsets of magnitude d (relative to the face size 1)")
quad = [(0,0,0),(1,0,0),(1,1,0),(0,1,0)]
for d in (0.05, 0.2, 0.5):
    em = eb = 0.0
    for _ in range(200):
        a, b = run(quad, d, 20); em = max(em, a); eb = max(eb, b)
    print(f"d = {d}: off-target-surface max, MVC {em*100:.1f} % of d, barycentric {eb*100:.1e} % of d")

print("-- gollum_20k faces, offsets of magnitude d = 0.5 x face size")
m = load(sys.argv[1])
em_all, eb_all = [], []
fids = m.all_face_ids()
for fid in rnd.sample(fids, 3000):
    pts = [m.vertex_position(v) for v in m.face_vertices(fid)]
    size = max(norm(sub(a, b)) for a in pts for b in pts)
    a, b = run(pts, 0.5*size, 8)
    em_all.append(a); eb_all.append(b)
def q(a, p): a = sorted(a); return a[min(len(a)-1, int(p*len(a)))]
print(f"MVC: p50 {q(em_all,.5)*100:.1f} %  p99 {q(em_all,.99)*100:.1f} %  max {max(em_all)*100:.1f} % of d")
print(f"bary: max {max(eb_all)*100:.1e} % of d")
```

Output:

```text
-- planar unit quad, random corner offsets of magnitude d (relative to the face size 1)
d = 0.05: off-target-surface max, MVC 74.7 % of d, barycentric 8.0e-13 % of d
d = 0.2: off-target-surface max, MVC 74.6 % of d, barycentric 2.5e-13 % of d
d = 0.5: off-target-surface max, MVC 45.8 % of d, barycentric 4.0e-12 % of d
-- gollum_20k faces, offsets of magnitude d = 0.5 x face size
MVC: p50 10.9 %  p99 37.3 %  max 57.4 % of d
bary: max 2.3e-11 % of d
```

### Probe C2 — same, smooth Gaussian offset fields on gollum_20k (`probe_c2_smooth_target.py`)

Importing probe C's helpers re-ran probe C's module body, so its lines repeat at the top of this output.

`probe_c2_smooth_target.py`:

```python
"""Probe C2: a smooth, realistic offset field on gollum_20k (a Gaussian bump along +Y, amplitude A, radius r,
centred on a surface vertex): the distance of the new point from the target's drawn surface, MVC vs barycentric,
in absolute units relative to A, over the faces inside the bump (offset > 1 % of A at a corner)."""
import math, random, sys
from mvc import *
from objload import load
from probe_c_target_surface import closest_on_tri, dist_to_surface

rnd = random.Random(5)
m = load(sys.argv[1])
P = {v: m.vertex_position(v) for v in m.all_vertex_ids()}
lo = [min(p[k] for p in P.values()) for k in range(3)]; hi = [max(p[k] for p in P.values()) for k in range(3)]
H = max(hi[k]-lo[k] for k in range(3))
for A_rel, r_rel in ((0.05, 0.10), (0.05, 0.04), (0.02, 0.02)):
    A, r = A_rel*H, r_rel*H
    worst_m, worst_b, errs = 0.0, 0.0, []
    for trial in range(3):
        c0 = P[rnd.choice(list(P))]
        off = lambda p: (0.0, A*math.exp(-sum((p[k]-c0[k])**2 for k in range(3))/r**2), 0.0)
        for fid in m.all_face_ids():
            pts = [P[v] for v in m.face_vertices(fid)]
            o = [off(p) for p in pts]
            if max(oo[1] for oo in o) < 0.01*A:
                continue
            tgt = [tuple(p[i]+q[i] for i in range(3)) for p, q in zip(pts, o)]
            ttris = fan(tgt); k = len(pts)
            for _ in range(4):
                ti = rnd.randrange(k-2); a, b = rnd.random(), rnd.random(); s = math.sqrt(a)
                beta = (1-s, s*(1-b), s*b); idx = (0, ti+1, ti+2)
                x = tuple(sum(beta[j]*pts[idx[j]][c] for j in range(3)) for c in range(3))
                w = mvc(pts, x)
                om = tuple(sum(w[i]*o[i][c] for i in range(k)) for c in range(3))
                ob = tuple(sum(beta[j]*o[idx[j]][c] for j in range(3)) for c in range(3))
                em = dist_to_surface(tuple(x[c]+om[c] for c in range(3)), ttris)
                eb = dist_to_surface(tuple(x[c]+ob[c] for c in range(3)), ttris)
                errs.append(em/A); worst_m = max(worst_m, em/A); worst_b = max(worst_b, eb/A)
    errs.sort()
    print(f"A = {A_rel*100:.0f} % of model size, r = {r_rel*100:.0f} %: MVC off-target-surface p50 {errs[len(errs)//2]*100:.3f} %, "
          f"p99 {errs[int(.99*len(errs))]*100:.2f} %, max {worst_m*100:.2f} % of A; barycentric max {worst_b*100:.1e} % of A "
          f"({len(errs)} samples)")
print(f"model size H = {H:.4f} (scene units)")
```

Output:

```text
-- planar unit quad, random corner offsets of magnitude d (relative to the face size 1)
d = 0.05: off-target-surface max, MVC 74.7 % of d, barycentric 8.0e-13 % of d
d = 0.2: off-target-surface max, MVC 74.6 % of d, barycentric 2.5e-13 % of d
d = 0.5: off-target-surface max, MVC 45.8 % of d, barycentric 4.0e-12 % of d
-- gollum_20k faces, offsets of magnitude d = 0.5 x face size
MVC: p50 10.9 %  p99 37.3 %  max 57.4 % of d
bary: max 2.3e-11 % of d
A = 5 % of model size, r = 10 %: MVC off-target-surface p50 0.002 %, p99 0.11 %, max 0.82 % of A; barycentric max 3.8e-13 % of A (26916 samples)
A = 5 % of model size, r = 4 %: MVC off-target-surface p50 0.009 %, p99 0.32 %, max 0.97 % of A; barycentric max 4.2e-13 % of A (5276 samples)
A = 2 % of model size, r = 2 %: MVC off-target-surface p50 0.046 %, p99 3.27 %, max 7.59 % of A; barycentric max 6.5e-13 % of A (1068 samples)
model size H = 1.2054 (scene units)
```

### Probe D — closed Knife shape, nested (per-call) vs. direct MVC (`probe_d_nested.py`)

Uses the real `close_loop_with_bridges`; bridges forced to corner 0 and the opposite corner. The `select_bridge` import was added after this run, for D2; it does not change D.

`probe_d_nested.py`:

```python
"""Probe D: a Knife closed shape = two split_face calls (the real `close_loop_with_bridges`); values of the loop
vertices by the per-call MVC rule (over each call's parent, using values the first call created) vs one direct
MVC over the root face. Scalar data; error as a fraction of the root corners' value spread (max over trials)."""
import math, random, sys
sys.path.insert(0, "/home/user/Mirai-Bastel/src")
from mvc import mvc
from core.mesh import Mesh
from mirai.topology.knife_resolve import close_loop_with_bridges, select_bridge

class VMesh(Mesh):
    """Mesh + one scalar layer, interpolated per split_face call (the AD-025 4.1 rule)."""
    def __init__(self):
        super().__init__(); self.val = {}
    def split_face(self, face_id, a, b, positions=()):
        corners = self.face_vertices(face_id)
        cp = [self.vertex_position(v) for v in corners]; cv = [self.val[v] for v in corners]
        res = super().split_face(face_id, a, b, positions)
        for v, p in zip(res[0], positions):
            w = mvc(cp, tuple(p)); self.val[v] = sum(wi*fi for wi, fi in zip(w, cv))
        return res

rnd = random.Random(3)
fields = {
    "affine": lambda p, r: 0.3 + 1.7*p[0] - 0.9*p[1] + 0.4*p[2],
    "smooth": lambda p, r: math.sin(2.5*p[0]) * math.cos(1.7*p[1]),
    "random corners": None,
}
shapes = {
    "unit quad": [(0,0,0),(1,0,0),(1,1,0),(0,1,0)],
    "8-gon": [(math.cos(2*math.pi*i/8), math.sin(2*math.pi*i/8), 0.0) for i in range(8)],
}
for sname, root in shapes.items():
    for fname, f in fields.items():
        worst = 0.0
        for trial in range(300):
            m = VMesh(); vs = [m.add_vertex(p) for p in root]; fid = m.add_face(vs)
            rv = [f(p, rnd) if f else rnd.uniform(-1, 1) for p in root]
            for v, x in zip(vs, rv): m.val[v] = x
            # a loop of 3..6 points around a random centre well inside the face
            c = (rnd.uniform(0.35, 0.65), rnd.uniform(0.35, 0.65), 0.0) if sname == "unit quad" else (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0.0)
            k = rnd.randint(3, 6); rad = rnd.uniform(0.08, 0.25)
            loop = [(c[0]+rad*math.cos(2*math.pi*j/k+0.3), c[1]+rad*math.sin(2*math.pi*j/k+0.3), 0.0) for j in range(k)]
            try:
                loop_vs, *_ = close_loop_with_bridges(m, fid, loop, 0, vs[0], k//2, vs[len(vs)//2])
            except Exception as exc:
                continue
            spread = max(rv) - min(rv)
            for v, p in zip(loop_vs, loop):
                w = mvc(root, p); direct = sum(wi*fi for wi, fi in zip(w, rv))
                worst = max(worst, abs(m.val[v] - direct)/spread)
        print(f"{sname:9s} {fname:15s}: nested vs direct, max {worst*100:.2e} % of the spread")
```

Output:

```text
unit quad affine         : nested vs direct, max 3.42e-14 % of the spread
unit quad smooth         : nested vs direct, max 2.08e+01 % of the spread
unit quad random corners : nested vs direct, max 2.97e+01 % of the spread
8-gon     affine         : nested vs direct, max 5.13e-14 % of the spread
8-gon     smooth         : nested vs direct, max 3.36e-01 % of the spread
8-gon     random corners : nested vs direct, max 4.01e+00 % of the spread
```

### Probe D2 — same with the resolver's `select_bridge` (`probe_d2_select_bridge.py`)

Re-run gave identical output (seeded).

`probe_d2_select_bridge.py`:

```python
# Probe D2: as probe D, but the bridges chosen by the resolver's own rule (`select_bridge`), as the Knife does.
src = open("probe_d_nested.py").read()
src = src.replace("loop_vs, *_ = close_loop_with_bridges(m, fid, loop, 0, vs[0], k//2, vs[len(vs)//2])",
                  "i1, b1, i2, b2 = select_bridge(m, m.face_vertices(fid), loop); loop_vs, *_ = close_loop_with_bridges(m, fid, loop, i1, b1, i2, b2)")
src = src.replace('print(f"{sname:9s}', 'print(f"[select_bridge] {sname:9s}')
exec(compile(src, "probe_d2", "exec"))
```

Output:

```text
[select_bridge] unit quad affine         : nested vs direct, max 1.49e-13 % of the spread
[select_bridge] unit quad smooth         : nested vs direct, max 2.70e+00 % of the spread
[select_bridge] unit quad random corners : nested vs direct, max 2.39e+00 % of the spread
[select_bridge] 8-gon     affine         : nested vs direct, max 1.01e-13 % of the spread
[select_bridge] 8-gon     smooth         : nested vs direct, max 7.90e-01 % of the spread
[select_bridge] 8-gon     random corners : nested vs direct, max 1.04e+01 % of the spread
```

### Probe E — MVC cost (`probe_e_cost.py`)

`probe_e_cost.py`:

```python
# Probe E: cost of one MVC evaluation (this review's pure-Python mvc.py), quad and 8-gon.
import math, time
from mvc import mvc
for name, pts in (("quad", [(0,0,0),(1,0,0),(1,1,0.1),(0,1,0)]),
                  ("8-gon", [(math.cos(2*math.pi*i/8), math.sin(2*math.pi*i/8), 0.0) for i in range(8)])):
    x = (0.3, 0.4, 0.0); n = 20000
    best = 1e9
    for _ in range(3):
        t = time.perf_counter()
        for _ in range(n): mvc(pts, x)
        best = min(best, (time.perf_counter()-t)/n*1e6)
    print(f"mvc {name}: {best:.1f} us per point")
```

Output:

```text
mvc quad: 14.2 us per point
mvc 8-gon: 25.9 us per point
```

### Probe F — survivors of symmetric Collapse (`probe_f_keep.py`)

The sphere row found no collapsible edge with both ends at x > 0 under the probe's filter; the plane row is the evidence.

`probe_f_keep.py`:

```python
"""Probe F: under symmetric Collapse, is the survivor of a group the mirror partner of the survivor of its image
group? If not, an H3 "keep" rule (survivor keeps its own value) is not mirror-consistent."""
import sys
sys.path.insert(0, "/home/user/Mirai-Bastel/src")
from core import SelectionMode
from mirai.scene_factory import create_plane, create_sphere
from mirai.symmetry_axis import set_symmetry_axis
from mirai.symmetry_coordination import SymmetryIndex
from mirai.symmetric_ops import coordinate_collapse
from core.operations.collapse import collapse_groups

def run(make, label):
    bad = total = 0
    base = make()
    set_symmetry_axis(base, "X")
    idx0 = SymmetryIndex(base)
    edges = [e for e in base.all_edge_ids()
             if all(base.vertex_position(v)[0] > 1e-9 for v in base.edge_vertices(e))]
    for e in edges[:60]:
        m = make(); set_symmetry_axis(m, "X")
        idx = SymmetryIndex(m)
        a, b = m.edge_vertices(e)
        pa, pb = idx.vertex_partner(a), idx.vertex_partner(b)
        try:
            survivors = coordinate_collapse(m, SelectionMode.EDGE, [e])
        except Exception:
            continue
        s_src = a if m.is_valid_vertex(a) else b
        s_img = pa if m.is_valid_vertex(pa) else pb
        total += 1
        # mirror-consistent iff the image survivor is the partner of the source survivor
        if (s_src == a) != (s_img == pa):
            bad += 1
    print(f"{label}: {bad} of {total} symmetric edge collapses keep a non-partner survivor on the mirror side")

run(lambda: create_plane(2.0, 6), "plane 6x6")
run(lambda: create_sphere(), "sphere")
```

Output:

```text
plane 6x6: 6 of 6 symmetric edge collapses keep a non-partner survivor on the mirror side
sphere: 0 of 0 symmetric edge collapses keep a non-partner survivor on the mirror side
```

### Probe G — Apply transform's per-element layer journal, memory (`probe_g_apply_mem.py`)

`probe_g_apply_mem.py`:

```python
"""Probe G: memory of Apply transform's `map_vector_layers` journaled per element (AD-025 4.3) on gollum (87.5k V),
L dense vector layers, under 1 recording + W watches (the app's edited mesh has 5, F-10). Peak traced memory of the
rewrite plus the delta (before, after) pairs end_change would build for the history entry."""
import gc, random, sys, time, tracemalloc
sys.argv = ["x"]
exec(open("probe_a_journal_mem.py").read().split("def mem_of_layer")[0])
from objload import load

m = load("/home/user/Mirai-Bastel/examples/meshes/gollum.obj", LMesh)
vids = m.all_vertex_ids()
rnd = random.Random(1)
L = 5
for lid in range(L):
    m._layer_values[lid] = {v: (rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)) for v in vids}
s = 1.7
for watches in (0, 5):
    gc.collect()
    tracemalloc.start()
    logs = [m.begin_change() for _ in range(1 + watches)]
    t = time.perf_counter()
    for lid in range(L):
        vals = m._layer_values[lid]
        for v in list(vals):
            x, y, z = vals[v]
            m.set_layer_value(lid, v, (s * -y, s * x, s * z))       # s * R(90 deg about Z)
    rec = m._side[id(logs[0])]
    delta = {lid: {v: (b, m._layer_values[lid].get(v)) for v, b in d.items()} for lid, d in rec.items()}
    dt = time.perf_counter() - t
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"{L} dense layers x {len(vids)} V, 1 recording + {watches} watches: peak {peak/2**20:.0f} MiB, "
          f"held after (journals + delta + new values) {cur/2**20:.0f} MiB, {dt:.1f} s under tracemalloc "
          f"-> 50 layers ~ {peak/2**20*50/L/1024:.1f} GiB peak")
    for log in reversed(logs):
        m.release_change(log)
    m._side.clear(); del delta, rec
```

Output:

```text
5 dense layers x 87500 V, 1 recording + 0 watches: peak 133 MiB, held after (journals + delta + new values) 130 MiB, 5.8 s under tracemalloc -> 50 layers ~ 1.3 GiB peak
5 dense layers x 87500 V, 1 recording + 5 watches: peak 258 MiB, held after (journals + delta + new values) 255 MiB, 7.5 s under tracemalloc -> 50 layers ~ 2.5 GiB peak
```

---

## Kurzfassung für Manu (Deutsch)

**Urteil:** annehmen mit Änderungen, kein Blocker. Die Fakten im Code stimmen, Speicher- und Journal-Messungen lassen
sich nachmessen, die sechs ARCH-02-Fragen sind beantwortet.

**Was geändert werden sollte (je eine Zeile):**

- **M-1** Ein geschlossener Knife-Schnitt verfälscht die Zielwerte stärker als angegeben (bis ~10 %, in Randfällen
  ~30 %); besser gibt der Knife die genaue Herkunft jedes neuen Punkts selbst mit.
- **M-2** „Apply transform“ mit vielen Zielen würde pro Punkt protokolliert und bräuchte bei 50 dichten Zielen auf
  gollum 1–2,5 GB; ganze Ebenen sollten als ein Eintrag ins Undo gehen.
- **M-3** Die Sperre prüft nur Tastenbefehle; Menü-Aktionen wie „Mirror copy“ würden durchrutschen.
- **M-4** Das Mitwandern neuer Punkte bei Knife/Split in Phase 2 einzubauen ist Vorratsbau (du hast gesagt, das darf
  vorerst gesperrt bleiben); die einfachen Regeln ja, den Knife-Teil erst in Phase 5.
- **M-5** Die H3-Antwort „einer der Punkte“ ist nicht festgelegt, welcher, und wird unter Symmetrie schief; streichen
  oder genau definieren.
- **Klein:** Die Kurzfassung verspricht, dass `Strg+A` die Ziele mitnimmt, während die Standard-Sperre genau das
  verbietet — das muss zusammenpassen.
