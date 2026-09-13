# Artist Playground — Experiment Host Audit vs. Research Map V1

**Status:** Technical assessment — no implementation performed
**Date:** 2026-09-13
**Author:** Interaction Dev role
**Scope:** Does the current Experiment Host support the research mode described in `RESEARCH_MAP.md`?
**Method:** Direct inspection of the repository (`ManuelPoehlau/Mirai-Bastel`, `main`), not documentation alone. Headless test subset executed (`playground/tests/test_experiment_slot.py`, `test_playground_app.py`, `test_playground_camera.py`, `test_presentation.py` — 71/71 pass). `test_input_map.py` and `test_selector.py` could not be executed in this sandbox (no X11 display available for pyglet's shadow window) — this is an environment limitation of the audit, not a claim about the project's own test environment.

---

## 1. Current Capability

### Proven (implemented, headless-tested, verified by reading the code)

- `Experiment` (`playground/experiment.py`) — minimal lifecycle interface (`activate`/`deactivate`/`update`/`draw`). Unchanged, exactly as documented.
- `ExperimentSlot` (`playground/slot.py`) — variant container for **one** family: index-based `activate()` with correct `deactivate()`→`activate()` ordering, `Decision` enum (`UNDECIDED/KEEP/ITERATE/REJECT`), `generate_decision_md()` / `write_decision_md()`. All behaviour matches `EXPERIMENT_HOST.md` §6–7. 10 dedicated tests pass.
- `PlaygroundApp.set_slot()` / `activate_variant()` — wired and tested, but only against **one** slot at a time (see Gap A below).
- Concrete variant classes exist for three families and are correctly thin: `playground/experiments/selection/*` (Replace, Toggle, Modifier, BoxSelect, FaceSelect), `playground/experiments/transform/*` (Move, Rotate, Scale), `playground/experiments/presentation/*` (six shading variants, AP-02.5). Each `activate()` only sets shared `PlaygroundApp` state (`select_mode`, `select_method`, `display_state`, `show_vertices`) — no duplicated selection/transform/rendering logic.
- `PlaygroundHUD.update_experiment()` and a dedicated "Experiment:" line exist and are called every frame from `window.py`.

### Documented but not verified at runtime

- None of the Experiment subclasses above are ever instantiated outside tests. `grep`-ing the whole `playground/` tree for `ExperimentSlot(`, `set_slot(`, `activate_variant(` finds **zero** call sites in `app.py`, `run.py`, or `window.py` — only in `playground/tests/`. The Host machinery is a correctly built, tested library that the live Playground currently does not call.
- Consequence: `PlaygroundHUD`'s "Experiment:" line is wired but inert during real play — `app.active_experiment` never leaves its `Experiment()` default, so this line always reads `[none] No Experiment` while the artist is actually working.

### Missing

- Any mechanism inside the Host for more than one `ExperimentSlot`/`Experiment` to be tracked as "active" at the same time. `PlaygroundApp` holds exactly one `_active_slot: ExperimentSlot | None` and one `_active_experiment: Experiment` (singular, not keyed by family).
- Any built-in "what is the whole Setting right now" query. (See Gap C.)

### What the artist actually plays with today (the de-facto Setting)

`PlaygroundWindow` does **not** go through Experiment/ExperimentSlot at all for live interaction. It mutates flat `PlaygroundApp` attributes directly from hardcoded key handlers:

| Key(s) | Effect | Attribute mutated |
|---|---|---|
| `M` | cycle Replace → Modifier → Toggle | `app.select_mode` |
| `Q` | cycle Pick → Box → Lasso → Paint | `app.select_method` |
| `1`/`2`/`3` | Vertex/Edge/Face component mode | `scene.selection.mode` |
| `D` / `Z` / `V` | display mode / wire overlay / vertices | `app.display_state`, `app.show_vertices` |
| `X`/`R`/`S` (held) | arm Move/Rotate/Scale, hold+drag+release | `app.active_tool` |

This is, in effect, already a working answer to Research Map §1 ("simultaneously active, freely changeable"): selection mode, selection method, component mode, display mode and the armed transform tool are five independent pieces of state that can each change at runtime without touching the others or restarting anything. It just does this through ad-hoc attributes on `PlaygroundApp`, not through the Host's own container/decision apparatus — so switching a variant this way leaves no `Decision`, no `decision.md`, and no HUD line identifying it as a tracked Experiment.

Only a subset of these keys is even routed through `PlaygroundInputMap` (`display_cycle`, `wire_overlay`, `show_vertices`, `select_button`, the three selection modifiers). `M`, `Q`, `1`/`2`/`3`, `X`/`R`/`S`, `C`/`H`, `ESC` are hardcoded `pyglet.window.key` constants inside `window.py`, independent of the input map.

---

## 2. Research Map Requirements → Host Capabilities

| Research Map requirement | Concrete Host capability required |
|---|---|
| §1 Multiple experiments active simultaneously | N independently-held "current variant" references, one per research family (Navigate / Select / Transform / Topology / Display), readable together at any moment |
| §2 Independent variant switching | Switching one family's variant must not call `deactivate()`/`activate()` on any other family |
| §3 Runtime switching | Switch while the pyglet loop is running, no restart |
| §4 Navigation + modelling coexistence | Input routing where camera gestures and operation gestures can compose — or a clear, evidenced statement of where they currently can't |
| §5 Technical provenance of the Setting | At any moment: "which variant is active per family?" — answerable without a database |

---

## 3. Gap Analysis

### Gap A — `PlaygroundApp` can only track one active Slot/Experiment

- **What's missing:** a per-family registry instead of a single `_active_slot` / `_active_experiment`.
- **Existing extension point:** `ExperimentSlot` is already scoped to one family by convention (`Experiment.id == "selection"`, `"transform"`, etc.) and has zero coupling to being "the" slot — nothing in its `activate()` touches other slots.
- **Reuse:** Full. `Experiment` and `ExperimentSlot` need no change; neither do any of the eleven existing variant classes.
- **Smallest change:** replace the two singular attributes with `self._slots: dict[str, ExperimentSlot]`, plus `register_slot(slot)` and `activate_variant(family_id, index)`.

### Gap B — The Host machinery and the live window are two disconnected paths

- **What's missing:** nothing new — the variant classes already write to the exact attributes `window.py`'s hardcoded keys write to (`select_mode`, `select_method`, `display_state`). Only the *dispatch* differs.
- **Existing extension point:** `on_key_press`'s existing `M`/`Q`/`D`/`X`/`R`/`S` branches.
- **Reuse:** Full — no duplicate selection/transform/display logic exists anywhere to reconcile.
- **Smallest change:** point those key handlers at `app.activate_variant(family_id, next_index)` (from Gap A) instead of inline enum-cycling. This alone makes every existing variant class live, and gives the HUD "Experiment:" line real content and `decision.md` for free, per family — without writing a single new Experiment.

### Gap C — Provenance/recoverability of the Setting

- **What's missing:** a single "what's active right now" readout across families.
- **Existing extension point:** `PlaygroundHUD` already renders one line per dimension and already calls `update_experiment()` every frame.
- **Reuse:** Full.
- **Smallest change:** once Gap A/B exist, the Setting is just `{family_id: active_variant_name}` from the registry — one compact HUD line, and (if wanted) one line appended to a plain text note next to an observation. No schema, no database — consistent with Research Map §8's explicit rejection of an observation database.

### Gap D — Navigation/Transform composability (finding, not a Host gap)

- `on_mouse_drag` and `on_mouse_motion` check `self._transform_key_down is not None` **first** and `return EVENT_HANDLED` before ever reaching the orbit/pan branch. `on_mouse_press` similarly blocks a Box-Select start while a transform key is held. So today, holding X/R/S makes orbit and pan gesturally impossible for the duration of the hold — not by researched decision, by construction/precedence order.
- This directly answers part of Research Map's "Navigation coexistence — UNKNOWN": the current fact is not unknown, it's **exclusive by construction**. Whether that's the right feel is still an open Focus question — but it's now a known baseline to test against, not a blank.
- **No Host extension recommended here.** This is Research material for the UX Researcher / Playground Spec roles, not an Experiment Host defect.

---

## 4. Architectural Risk

- **Combination-matrix drift.** A per-family registry must store exactly one active index per family and nothing about cross-family compatibility or dependency. Research Map §8 and this task's brief explicitly reject a validity/dependency system — flag, don't build one, if this temptation appears during implementation.
- **HUD panel creep.** The "Setting" readout should stay one compact line, not grow into a permanent multi-line research dashboard.
- **Keymap conflation.** `M`/`Q`/`1`/`2`/`3`/`X`/`R`/`S`/`C`/`H`/`ESC` currently bypass `PlaygroundInputMap` entirely. Routing them through per-family slots is a good moment to *also* route them through the input map — but that's a separate, separable improvement. Don't bundle a keymap redesign into the slot-registry change.
- **Built ≠ decided, regardless of path.** Wiring an existing variant class into the live Host doesn't make its UX validated — it only makes it observable and decidable via `decision.md` instead of silently.

---

## 5. Recommended Minimal Extension

**Problem:** `PlaygroundApp` can only hold one active `ExperimentSlot`/`Experiment`, so Selection/Transform/Display/(future Navigate/Topology) can't be seen or switched as independent, simultaneously-active research dimensions *through the Host's own apparatus* — even though the live window already achieves independent, simultaneous switching today through separate flat attributes, with no decision-tracking attached.

**Existing mechanism:** `Experiment` + `ExperimentSlot` (variant container, `Decision`, `decision.md` generation) already do exactly what's needed per family; the eleven existing Selection/Transform/Presentation variant classes already write to the correct shared app state.

**Smallest extension:**
1. `PlaygroundApp`: singular `_active_slot`/`_active_experiment` → `dict[str, ExperimentSlot]`, with `register_slot()` / `activate_variant(family_id, index)`.
2. `PlaygroundHUD`: one new compact line built from that dict (e.g. `Setting: select=Replace | display=Shaded | transform=—`).
3. `window.py`: re-point the existing `M`/`Q`/`X`/`R`/`S`/`D` handlers at `activate_variant(...)` instead of inline cycling.

**Why:** reuses every existing class unchanged, touches only the two places that currently assume singularity (`PlaygroundApp`'s two attributes) or duplicate dispatch (`window.py`'s key handlers), introduces no new concepts, no persistence, and no combination framework — matching the "smallest enabling extension" mandate exactly.

Not recommended as part of this extension: wiring Navigate or Topology families (no Topology playground experiments exist yet, per `ROADMAP.md` — AP-05 is deferred; Navigate has no variants to switch between yet, only the Gap D finding above).

---

## 6. Dev Handoff Recommendation

### MINIMAL HOST EXTENSION REQUIRED

The Host's core apparatus (`Experiment`, `ExperimentSlot`, decision recording) is sound, tested, and needs no redesign. The gap is narrow and structural: `PlaygroundApp` assumes one active slot where the Research Map needs several concurrent ones, and the live window currently bypasses the Host entirely via hardcoded, per-key flat-state mutation. Both are closed by the change in §5, which is additive and reuses all eleven existing variant classes as-is.

This is not an architectural blocker: the underlying live-switching behaviour the Research Map asks for already exists in practice (§1 "current live setup" above) — it's just not yet expressed through the Host's own tracked, decidable form.

**Stop condition reached. No implementation performed.**
