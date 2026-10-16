# Independent review — Morph Lab as the second user of Viewport hook H7 (AD-013), CLAUDE-001

- **Reviewer:** Claude (Claude Code, independent review session)
- **Date:** 2026-10-16
- **Commit read:** `600b3a4` (`main`, "fix(viewport): replacement surface follows the camera every frame (AD-013 H7)")
- **Session:** fresh session, no context from the authoring session
- **Object of review:** proposal P-MORPH-H7 (planning session, main @ 600b3a4, 2026-10-16), as quoted in the review request
- **Mode:** review only. No code was changed. Probes ran in memory (headless `Application`, `TraceStore`) from scripts in
  the session scratchpad; the only file they wrote was a throw-away scene file in that scratchpad. Container timings, not
  the reference PC.

Markers: **[Code]** read in the code at `600b3a4`; **[Doc]** read in a decided document; **[Probe]** reproduced in memory;
**(Reading)** my interpretation.

---

## Verdict

**ACCEPT WITH CHANGES.**

The proposal stays inside H7-R1…R4. Its use of H2-R4 is sound in substance but the proposed note cites the allow-list
too loosely. Nothing in `src/` has to change. Three things the proposal does not cover would produce confusing or
silently wrong results in the first practical test: the status feedback loop (F-1), Apply transform on the placed
target (F-2), and editing the base while the weight is above 0 (F-3). Each fix is a small lab-side rule or a sentence in
the note. The claimed Undo crash (R-5) is real, the proposal avoids it completely, and production cannot reach it today.
It is recorded as a separate finding (F-12).

---

## Findings

| ID | Severity | Finding | Evidence | Proposed change |
|---|---|---|---|---|
| F-1 | **major** | **Status wake-up feedback loop.** The provider uses a `status_serial` change as its dirty signal, and it also posts its own refusal ("topology differs") through `set_status`, which bumps `status_serial`. If the provider records the serial *before* it posts, which is the natural "consume the wake-up first" order, and posts on every sync, it wakes itself every frame. Even in the safe order it re-posts on every hover sync, and `src/main.py:run` prints every status change to the console. | [Probe] diverged topology, provider records the serial before posting with no transition guard: **30 posts in 30 idle frames**. In the other order: 1 post. [Code] `viewport.py:526-528` (provider polled every frame via `dirty`), `main.py:469-479` (console print per serial) | Post a refusal only when the text changes, as the SubD Lab's `_set_message` does (`lab_surface.py:142-147`). Record the serial *after* the provider's own `set_status`. Add a lab test: diverged topology plus 30 idle `update_viewport` calls gives exactly one status. |
| F-2 | **major** | **Ctrl+A on the placed target bakes its offset into T.** The morph reads T in object space, so a placement does not matter. Apply transform turns the placement into vertex positions (`_apply_transform`), so from then on every weight above 0 shifts the whole surface towards the target's place. Ctrl+S persists this. Undo restores it. | [Probe] target placed at +3 in x, Ctrl+A in mode `4` → `T[v]−B[v] = 3.0` for every vertex. Surface at k = 100 offset by 3.0. Ctrl+Z → 0.0. [Code] `application.py:1124-1170`, `1172-1180` | Name it in the README and the practical test. HUD/status check (`PROVISIONAL`): if the centroid of T − B exceeds a small share of the base bounds, post once "Ziel enthält einen Versatz (Strg+A?) — Strg+Z". Do not try to correct it in the provider (H7-R2: display only). |
| F-3 | **major** | **Editing the base while the weight is above 0 is not addressed.** The faces show S. Wire, hover and selection points, face/edge highlights, soft bands, tool overlays and **picking** all stay on B's rest positions (H7 by design: the cage stays authoritative). A click on the visible surface picks whatever B vertex lies under the cursor, or nothing. A W-move moves the drawn surface by only (1−w)·Δ. This is behaviour the Artist feels, and the proposal says nothing about it. | [Code] `viewport.py:88-98` (overlays and picking on the edit mesh), `render`: `viewport.py:577-611`. (Reading) for SubD the cage-vs-surface gap is the expected look; for a morph it is a gap of up to the full target delta | Make one `PROVISIONAL` rule and put it in the practical test as a question: **k = 0 → `surface_mesh = None`** (the base is drawn as itself, bit-exact, no cost), plus a HUD line "Gewicht k % — Käfig/Auswahl = Basis-Ruhelage" whenever k > 0 and the base is the edit object. The Artist then decides whether the lab should do more (e.g. a key to jump to 0 % and back). |
| F-4 | minor (required for the note) | **The note cites H2-R4 (f) for more than it lists.** (f) names `init_scene`, `frame_scene`, `set_viewport_size`. `SceneFiles.load` calls **`Application.load_scene`** (`scene_files.py:126-135`), which is not in the list (it calls `init_scene`, resets history and selection, frames). `save=` makes the H6 wiring call `Application.save_scene_file` on Ctrl+S, which is not in the list either. Both are harmless: `src/main.py:492-493` does exactly this, and `save_scene_file` refuses during an interaction. They are still additions. | [Doc] AD-013 H2-R4 (f), l.666-668. [Code] `application.py:1304-1359`, `1361-1380`; `main.py:283-356` | Phrase the note as: "one-time set-up in `run.py`: `init_scene` + `SceneFiles.load` (→ `load_scene`), as `src/main.py:492-493`; Ctrl+S through the H6 parameter `save=` (→ `save_scene_file`, window wiring, user key). These two are named here for this host; H2-R4's text is not changed." Do not edit H2-R4 itself (see Haltepunkt). |
| F-5 | minor | **Attach order and load errors.** `load_scene` → `init_scene` builds a **new** `Viewport`, so a provider attached before the load is lost. `SceneFiles.load` turns every exception into a status line and returns `False`. | [Probe] attached before the load: `app.viewport.surface_provider is prov` → `False`; after the load → `True`. [Code] `application.py:799-806`, `scene_files.py:126-135` | `run.py`: load first, then `set_surface_provider`. On `False`, print the status and exit with a non-zero code, naming `--neu`. A headless test for both. |
| F-6 | minor | **Resolving objects by name.** `Scene` does not enforce unique names, and ObjectIds are session-local (`replace_scene` re-allocates them). The lab file lives in the shared `scenes/` folder, so it appears in the production SPACE menu. There it can be loaded, extended with `add_reference` of the same asset (default name = file stem = the base's name) and overwritten with Ctrl+S, because `SceneFiles.current` is set on load. The next lab start then finds two objects named `<asset>`. | [Code] `scene.py:215-225` (no uniqueness), `scene_objects.py:52-76`, `scene_files.py:66-72` (lists only direct files of its folder), `application.py:843-871`. [Probe] loaded IDs were 2/3, not the file's 1/2 | Resolve once after the load. Exactly one match per name, else refuse at start-up with a clear message. Keep the two ObjectIds for the session (no runtime add/remove exists in the lab). Store the file in `scenes/morph_lab/` (`SceneFiles(app, directory=…)`): production's menu lists only direct files of `scenes/`, so it no longer shows the lab file. |
| F-7 | minor | **Edit-object switch gesture as stated does not always work.** In `4`, a plain click on a non-edit object **toggles Normal ↔ Reference** (an Undo step). "Shift+click, 1" switches only when the object selection is empty. After a first switch the previous object is still selected, so Shift+click selects two and `1` keeps the edit object ("2 objects selected"). | [Probe] P4b: status `Mode: Vertex · 2 objects selected - still editing '… · Ziel 1'`. P8: plain click → target `REFERENCE`. [Code] `application.py:972-1018`, `1490-1510` | HUD/README: "4 · Klick ins Leere · Shift+Klick aufs Objekt · 1". A click into empty space in `4` clears the object selection (`application.py:986-988`). |
| F-8 | minor | **Numerics of `(1−w)·b + w·t`.** It is exact at w = 0 and w = 1 and exactly mirrored. It is **not** exact where B = T: (1−w)·b + w·b ≠ b for many inputs, so unchanged regions move by one ulp and "return exactly the changed IDs" becomes "almost all IDs". | [Probe] head, k = 1…99, B = T: **8 930 of 32 274** vertex samples change. With `b + w·(t−b)`: 0. Mirror mismatches over 20 000 random pairs: 0 for both. `b + 1.0·(t−b) ≠ t` in 83 846 of 200 000 wide-range samples | Use `b + w·(t−b)` for 0 < k < 100, `t` itself at k = 100, and `surface_mesh = None` at k = 0 (F-3). Exact at both ends, exact where B = T, exactly mirrored (R-7). |
| F-9 | minor | **Cost.** A weight step with a fully sculpted target moves every vertex through `RenderMesh._sync_geometry` (per-vertex `store.update` for positions and normals, plus every touched face row). Every hover change also runs a full provider pass (two signatures + blend), because hover is an H7 trigger. | [Probe, container, TraceStore] weight step, every vertex moved: head (326 V) **6.5 ms** p50 (provider 2.3 + geometry 4.2). Body (928 V) **42-44 ms** p50, max 62-79 ms (provider ~17 + geometry ~24-26). Full rebuild instead: 5.8 / 30.4 ms, no better. No-change provider pass (every hover change): **4.9 / 15.9 ms**. One signature: 1.2 / 2.6 ms | Acceptable for discrete key steps in a Discovery lab, not for scrubbing. Measure it in the HUD like the SubD Lab. Skip all work at k = 0. Cache the base/target signature behind a cheap pre-key (`PROVISIONAL`, the agent decides). Faster partial uploads are the Viewport performance topic Manu already set apart, not this lab's. |
| F-10 | minor | **`status_serial` as wake-up is a heuristic, not a contract.** H7 tells the provider nothing when a *non-edit* object's mesh changes (`_object_meshes_changed` marks only that object's render entry). Today every such path posts a status: Apply transform, its Undo/Redo, state toggles, scene load. A future silent path would leave a stale surface (display only, no data loss). | [Code] `application.py:1172-1180`, `3062-3082` (`_undo_redo` → `_set_status(command)`). [Probe] P7/P7b: Ctrl+A and its Undo reach the provider only through the serial; the surface was correct afterwards | Allowed by H2-R4 (a). Pin it with a lab test (Ctrl+A on the target, Undo, Redo with the base as edit object → surface matches). Add one sentence to the note's Limits (below). |
| F-11 | minor | **Wireframe hides the morph completely.** The surface is drawn only with `show_faces`. The target, a NORMAL object, is not drawn in Wireframe either (`entry_drawn`). With Shift+D the wire is the rest cage over the morphed faces. | [Code] `viewport.py:307-310`, `585-586` | One HUD hint ("Wireframe: Morph nicht sichtbar"). Nothing else needed. |
| F-12 | minor (latent; separate finding) | **R-5 confirmed: Undo of "Add object" crashes when the added object is the edit object.** `_apply_undo_redo` calls `history.undo()` before `_restore_selection`. `AddObjectCommand.undo` → `Scene.remove_object` refuses the edit object with `ValueError`. `HistoryStack.undo` has already popped the command, so the step is **lost from both stacks** while the selection mirror's redo stack holds one entry (desync). Production cannot reach it today: `add_reference` adds a REFERENCE, and before it can become the edit object it needs an `ObjectStateCommand`, whose Undo (stacked above the Add) switches the edit object back first. | [Probe] NORMAL object + `AddObjectCommand` + mirror entry, `4`, select, `1`, Ctrl+Z → `ValueError: Das Edit-Objekt 2 kann nicht entfernt werden`; afterwards undo 0, redo 0, mirror-redo 1. Production path (`add_reference`, toggle, switch, Ctrl+Z ×3) → no error. [Code] `application.py:3084-3136`, `3226-3245`, `scene_objects.py:79-94`, `scene.py:227-235`, `core/history.py:60-65` | Not this lab's business: the proposal avoids the path completely (no `AddObjectCommand`; `load_scene` starts with a fresh history). Record it in AD-021's open items so the first host that adds NORMAL objects fixes it first (e.g. restore the step's edit object before `history.undo()` for object steps). Related, harmless while the mirror is intact: between `history.undo()` and `_restore_selection` an `ObjectStateCommand` undo can leave the edit object a REFERENCE for a moment (RF-2/RF-5). |
| F-13 | nit | `--neu` overwrites the lab file, including a sculpted target, without asking. | (Reading) | Keep one backup (`….bak`) or refuse if the file exists and `--neu --ja` is not given (`PROVISIONAL`). |
| F-14 | nit | M1: the existing morph experiment (`experiments/rigging-skinning-morphing`, AD-005: `RigController.morph_targets = {name: {vertex_id: delta}}`) is not mentioned. | [Code/Doc] AD-005 l.33-38, `living_mesh_harness.py:136` | One line in the lab README: why a full target *object* (sculpting with the app's tools) instead of AD-005's delta dict, and that neither is the decided home (AD-021 §4.9). |
| F-15 | nit | Signature details. The sorted signature is right for comparing two meshes (the SubD Lab's `topology_signature` is unsorted, `lab_surface.py:47-53`, which is fine for its own use). A rotated face loop or a swapped `v0/v1` reads as divergence: a false refusal, on the safe side. With forward-only counters, once one mesh has undone a topology step, the same later step on both meshes hands out different IDs, so the pair cannot converge again. | [Code] `mesh.py:1111-1159` (forward-only `restore_counter`) | README sentence: topology changes on base or target end the morph until they are undone on the same mesh. Same topology edits on both are not supported. |

---

## Answers

**R-1 — Rules.**
Reading other objects' meshes is covered by H2-R4 (a): "`scene`/mesh read-only". The scene includes `scene.objects`
[Doc]. AD-021 RF-2 keeps References out of *component* paths, and a display provider is not one (Reading).
`SceneFiles.load` in `run.py` is one-time set-up exactly as `src/main.py:492-493` does it [Code]. However, it runs
`load_scene`, which (f) does not name (F-4). `save=` is acceptable: the H6 window wiring calls it on a user's key, like
(e) "event entry points from the window adapter", and `save_scene_file` refuses during interactions [Code]. It is
still not on the list, so the note must name it. Reading `status_serial` is explicitly in (a) [Doc]. Using it as a
wake-up is acceptable if F-1 and F-10 are handled. The H7 note should say all of this explicitly. H2-R4's text itself
should not change.

**R-2 — H7 contract.**
The triggers reach the provider in every case that matters [Code, Probe]:
- `set_edit_mesh` sets `_extra_overlays_dirty` (`viewport.py:347`). Switching to the target gives `surface_mesh = None`; switching back rebuilds the surface.
- Undo/Redo of a mesh step calls `on_topology_changed`. Q-8 switches back to the step's object through `set_edit_mesh` (P6).
- Object steps on the non-edit target, and their Undo, carry no viewport signal. Only the status reaches the provider (P7/P7b), see F-10.
- Hover-only changes trigger a sync (13 calls in 20 motions, P2). They are correct but costly (F-9).
- Wireframe: the provider still syncs, but the surface is not drawn (F-11).

"Return exactly the changed IDs" is the right usage, provided the formula makes unchanged vertices truly unchanged
(F-8). "A new mesh object means rebuild" is used correctly: a new `S` on a signature change, ignored return value on a
rebuild (`viewport.py:397-411`) [Code].

**R-3 — Identity.**
Acceptable as a `PROVISIONAL` lab representation. N-3 forbids inferring an *object* from an element ID. The lab
resolves objects by name and pairs element IDs only between two meshes it created as an ID-identical copy
(`from_state(export_state())`), checked by the signature [Doc, Reading]. Equal vertex IDs, equal edge endpoints and
equal face loops amount to an ID-preserving isomorphism of the whole topology. So equal signatures do give a
well-defined per-vertex correspondence, and positions are free by definition. Divergent independent topology edits
are caught, because new IDs come from per-mesh forward counters and their edges and faces differ. The remaining
errors are false refusals only (F-15). The note must say that this pairing is a lab convention, not a morph format
(R-6).

**R-4 — Missed risks.**
- Apply transform on the placed target bakes its offset (F-2).
- Editing the base at k > 0 separates picking and overlays from the drawn faces (F-3).
- The switch gesture toggles Normal ↔ Reference on a plain click and fails while two objects are selected (F-7).
- Name collisions are possible through the production SPACE menu, because the file sits in `scenes/` (F-6).
- Cost: head 6.5 ms per weight step, body 42-44 ms per step, plus 5/16 ms per hover change (F-9).
- Also missed: the status feedback loop (F-1), attach order and load errors (F-5), and Wireframe (F-11).

**R-5 — Claim to verify.**
Reproduced [Probe]: `ValueError` from `Scene.remove_object`, and the step is lost from both history stacks while the
mirror holds a redo entry. The proposal avoids the path completely: no `AddObjectCommand`, and the history is fresh
after `load_scene` (P1: history length 0). Production does not reach it today [Probe]. Recorded separately as F-12.

**R-6 — Decisions.**
No contradiction:
- AD-021 §4.9 puts *ID-keyed morph data* on the Mesh and says evaluated geometry is not serialized and not in
  History. The lab stores no morph data structure. The target is an ordinary object in a v2 file, and
  `scene.morph_targets` stays `null` [Code: `serialization.py:35-45`]. The surface `S` is derived, never written,
  never in History (H7-R2), and the weight is view state.
- AD-005 is an experiment with delta dicts and is not touched (F-14).
- CORE_V1_FREEZE §4 keeps morph targets out of Core, and nothing enters Core [Doc].

Condition: the note and README must say that "target = second object, paired by equal IDs" is a lab representation.
It must not become the file format for morph targets (Reading). This review is enough under H7-R4, see Haltepunkt.

**R-7 — Numerics.**
- `(1−w)·b + w·t` is bit-exact at w = 0 and at w = 1. It is exactly mirrored, because negation is exact and
  round-to-nearest is sign-symmetric [Probe: 0 of 20 000].
- It is not exact where b = t: 8 930 of 32 274 samples drift by an ulp [Probe].
- `b + w·(t−b)` is exact at w = 0, exact where b = t, and exactly mirrored, but **not** exact at w = 1
  (83 846 of 200 000 wide-range samples).
- Best: `b + w·(t−b)` in between, `t` at k = 100, and no surface at k = 0 (F-8).
- `w = k/100` is not exact for most k. That does not matter, because both mirror sides use the same w.

**R-8 — Simpler alternative.**
None is clearly better (Reading). Creating the target at runtime with `add_reference` would give the same IDs, but it
needs a SPACE menu or a non-listed call, adds an undoable "Add object", and loses persistence. A zero-H7 path (show
only T) cannot show a blend. The proposal's path reuses the most (scene files, the H6 wiring, the app's tools for
sculpting). The simplification worth taking is k = 0 → no surface.

---

## Haltepunkt?

**Nein.** No file in `src/` changes, nothing is promoted, and Core is untouched. H7-R4 asks for exactly this review.
The one behaviour the Artist must feel (editing the base at k > 0, F-3) can be set as `PROVISIONAL` and put into the
practical test. *Condition:* the addition to AD-013 stays a dated second-user note under H7 that names `load_scene`
and `save=` for this host (F-4). Rewriting H2-R4's rule text would be a change to a decided rule and would need
Manu's go. Fixing F-12 in `src/mirai/application.py` is a separate `src` change with its own work package.

### Proposed wording of the note (for the author; not added by this review)

> *Second user (Morph Lab, 2026-10-16, review CLAUDE-001 ACCEPT WITH CHANGES).* `experiments/morph_lab/` uses H7 under
> H7-R1…R4 unchanged: one provider per app instance, display only. The provider reads the base's and the target's meshes
> read-only (H2-R4 (a)) and pairs their vertices by equal IDs. This is a lab convention, not a morph-target format; AD-021
> §4.9 decides that home. One-time set-up in `run.py`: `init_scene` + `SceneFiles.load` (→ `load_scene`), as
> `src/main.py:492-493`, provider attached after the load; Ctrl+S through `install_handlers(..., save=)` (H6 →
> `save_scene_file`). Both are named here for this host; H2-R4's text is unchanged. Limit: H7 reports no change of a
> non-edit object's mesh; the lab wakes on `status_serial`. Nothing in `src/` changes.

---

## Kurzfassung für Manu (Deutsch)

Das Morph Lab kann so gebaut werden, mit Änderungen (ACCEPT WITH CHANGES). Es braucht keine Änderung in `src/` und
keinen Haltepunkt, solange der Zusatz zu AD-013 eine Notiz unter H7 bleibt, die `load_scene` und `save=` ausdrücklich
nennt. Drei Punkte sollten vor dem Praxistest geklärt sein:
- Der Provider darf seine eigene Statusmeldung nicht als Weckruf lesen, sonst meldet er sich jeden Frame neu.
- Strg+A auf dem verschobenen Ziel brennt den Versatz in die Form ein. Das Lab soll das melden.
- Wenn du bei einem Gewicht über 0 % an der Basis arbeitest, liegen Auswahl, Hover und Picking auf der Ruheform,
  nicht auf der sichtbaren Fläche. Vorschlag: bei 0 % keine Ersatzfläche, darüber ein HUD-Hinweis; das prüfst du im
  Praxistest.

Der vermutete Undo-Absturz beim Hinzufügen eines Objekts als Normal ist echt, betrifft das Lab aber nicht und ist in
der App heute nicht erreichbar. Er ist als eigener Befund notiert.
