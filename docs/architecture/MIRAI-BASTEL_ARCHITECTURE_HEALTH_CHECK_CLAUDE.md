# MIRAI-BASTEL — ARCHITECTURE HEALTH CHECK

**Type:** Read-only forensic audit
**Date:** 2026-09-19
**Audited commit:** `4d7fdb7` (*WP-AP-INPUT-FIX-01 Complete: Command Handler Fix + Axis Constraint Wiring + Key Rebinding*)
**Mode:** Discovery (M5). Nothing was changed, refactored, renamed or fixed. `git status --short` is empty.

**Method.** Full clone of `ManuelPoehlau/Mirai-Bastel@main`, static reading of the real runtime paths, AST extraction of the dispatch chains in `playground/window.py`, executable resolution of the real `BindingSet` against the real `SAFE_COMMANDS` set, and read-only test runs (`PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`). Documentation was read **after** the code, and was not treated as authoritative.

**History awareness (M1).** A repository-wide structural audit already exists: `docs/Repository_Wide Structural_Codebase_Health_Audit.md` (committed `5701563`, 2026-09-17). It is good, it is still largely accurate, and this report does **not** repeat it. Its findings D1–D6, O1–O4, AI-H1–AI-H7 are referenced by ID where relevant. The decisive difference: that audit predates the Input Wiring work (`54e9840`, 2026-09-18) and the Input Fix (`aac474e`/`4d7fdb7`, 2026-09-19). Everything in §3 of this report describes a state that did not exist when the previous audit was written. Also read: `AD-009`, `AD-010`, `AD-011`, `AD-012`, `INPUT_COMMAND_TOOL_CONTRACT.md`, `CLAUDE.md`, `AGENTS.md`, `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md`, `INPUT_WIRING_MAP.md`, `WP-AP_INPUT_WIRING_REPORT.md`, `playground/MANUAL.md`.

**Evidence labels:** **OBSERVED** (verified in code or by execution) · **DOCUMENTED** (stated in project documentation) · **INFERRED** · **UNKNOWN**.

---

## 1. Executive Summary

**Answer to the primary question: the architecture has drifted — but not everywhere, and not in the way the symptom suggests.**

`src/core`, `src/mirai/interaction/{input,bindings,commands,routing}`, `src/mirai/interaction/tools` and `src/viewport` are in good shape. The production input layer in particular is small, pyglet-free, well documented and fully tested. It is not the problem.

The damage is concentrated in exactly one place: **the keyboard dispatch inside `playground/window.py` + `playground/command_handler.py`**. There, five independent authorities now decide what a physical key means, in sequence, with no arbitration model and with silent fall-through at every seam:

1. `BindingSet` (production defaults, `src/mirai/interaction/bindings.py`)
2. `SAFE_COMMANDS` whitelist (`playground/command_handler.py:62-68`)
3. a 26-branch `elif` chain (`playground/window.py:1150-1385`)
4. an always-executed axis-constraint block (`:1387`)
5. a transform/tweak activation block whose behaviour is decided by *two* experiment slots (`:1407-1446`)

This is not "coupling" in the abstract. It produces measurable, verified breakage **at the current HEAD**:

- **Rotate and Scale cannot be activated at all.** `W` resolves to `ToggleWireframeOverlay`, `E` resolves to `SetEdgeMode`; both are whitelisted, both return early, and the rebinding block that would activate Rotate/Scale is never reached. *(OBSERVED, executed)*
- **Move cannot be committed by key release.** In `on_key_release`, `elif symbol in (X, Y, Z)` at `:1529` shadows `elif symbol in (X, W, E)` at `:1540`. The transform-commit branch is unreachable for `X`. *(OBSERVED, AST)*
- **Ring Select is unreachable.** `elif symbol == _key.R` (`:1235`) catches `Shift+R` and swallows it; the ring branch at `:1366` is dead. *(OBSERVED, AST)*
- **Pressing `X` at startup does not start Move at all** — it arms Tweak V1, because the tweak slot defaults to index 0 (`TweakV1HoldKey`) and V1 unconditionally claims the transform keys. *(OBSERVED)*
- **The artist's own key request was implemented off-by-one.** `INPUT_WIRING_MAP.md` asks for Move=`W`, Rotate=`E`, Scale=`R`. The code implements Move=`X`, Rotate=`W`, Scale=`E`, Extrude=`R`. *(OBSERVED)*
- **449 + 290 = 739 tests pass green through all of the above.** No test anywhere calls `on_key_press`, `on_key_release` or `on_mouse_press`. The axis-constraint tests re-implement the logic inside the test body and assert against their own copy. *(OBSERVED, executed)*

**Diagnosis for the bug pattern (§10): primarily D + E, with C as the amplifier, and only a small residue of A.** The agent is not mostly guessing. The repository currently contains multiple competing implementations of the same key semantics (D), created by a half-finished migration that was explicitly designed to run both generations side by side (E), in a code shape where the correct change location is genuinely ambiguous (C). An agent — or a human — that changes one of the five authorities has no local way to see the other four, and the test suite confirms success either way.

**One decision-level finding sits above all of this.** `AD-011` (DECIDED, 2026-09-17, Manu) states that the Playground *deliberately diverges* from production bindings and that the production Input→Command→Tool contract *remains unhandled by any running application, and is not expected to be resolved until a real application entry point exists*. One day later, `54e9840` wired the Playground to the production `BindingSet`. No superseding decision was written; `AD-011` is still marked DECIDED and is referenced by nothing except itself and the Development System. Under M1/M5 and `AGENTS.md §5`, this is a silent architecture change — and it is the direct structural cause of every conflict in §3.

**A refactoring phase is justified.** It should be narrow: the key-dispatch path of the Playground and nothing else. §14 and §15 state exactly where, and exactly where not.

---

## 2. Current Architecture Shape

**OBSERVED.** Code volume (Python, excluding `.git`):

| Area | Files | Lines | Role |
|---|---|---|---|
| `src/` | 42 | 5 230 | Production: core, mirai (app/interaction/tools), viewport |
| `playground/` | 83 | 12 155 | **The only runnable application** (`playground/run.py`) |
| `experiments/` | 43 | 8 013 | Repository-level research; `core_V1`, `viewport_V02`, `rigging-skinning-morphing`, `topology` |
| `tests/` | 42 | 7 627 | Production suite |
| `docs/` | — | 163 `.md` files | 41 of them loose in `docs/` root |

**OBSERVED.** There is no `src/main.py` and no production window. The production stack is window-free by design (`src/mirai/application.py` docstring). Everything the artist can actually run lives under `playground/`, and `playground/window.py` (1 739 lines) is the single largest runtime object in the repository.

**OBSERVED.** Dependency direction is clean at the package level: nothing under `src/` imports `playground` or `experiments`. The Playground imports production (`core`, `mirai`, `viewport`) plus `examples/` and the rigging experiment via `playground/_paths.py`. Previous finding D3 (Playground depending on the Integration Lab) **has been resolved** — `experiments/mirai_bastel_integration_lab` and `experiments/mirai_bastel_viewport_V1` were deleted in `8ef4def`, and `_paths.py` now points at `examples/` per AD-007.

**OBSERVED.** Bare `pytest` from the repo root still fails, but with **9** collection errors, not the 46 reported in the previous audit (D1) — the V1 `viewport` package collision is gone; what remains is `tests/test_extrude_tool.py` and the `playground/tests` display dependency.

**The actual runtime shape of a keystroke today:**

```
pyglet on_key_press(symbol, modifiers)
   │
   ├─(1) determine_input_context(app.focused_family)     playground/input_adapter.py:141
   │     "topology" → TOPOLOGY_CONTEXT, else GLOBAL
   ├─(2) _key_from_pyglet(symbol, modifiers)             playground/input_adapter.py:30
   ├─(3) BindingSet.command_for(input, context)          src/mirai/interaction/input.py:196
   ├─(4) if command in SAFE_COMMANDS and handled  ──►  RETURN   command_handler.py:62
   │                                                    (28 % of the keys never get past here)
   ├─(5) elif-chain, 26 branches                         window.py:1150-1385
   ├─(6) axis-constraint block (always runs)             window.py:1387
   └─(7) transform/tweak activation + F + ESC            window.py:1407-1497
```

Steps 4–7 are four independent decision points, in three files, none of which knows what the others will do.

---

## 3. Input Wiring Forensic Analysis

This is the core of the audit. Everything below is verified against the real code at HEAD.

### 3.1 The production layer (healthy)

**OBSERVED.** `src/mirai/interaction/input.py` (317 lines) defines `Input` (kind/value/modifiers, frozen dataclass) and `BindingSet` with a two-level resolution — user layer over default layer, specific context over `GLOBAL_CONTEXT` — plus a validated `keymap.json` overlay with an explicit-unbind semantic. It is pyglet-free, has a documented contract, and is covered by 51 tests. **This layer is not implicated in any failure found.** Ownership is unambiguous: the binding table owns input→command, `routing.py` owns command→tool, `commands.py` owns the vocabulary.

**OBSERVED.** `build_default_bindings()` (`bindings.py:50-98`) is the only default table in production:

```
v,1 → SetVertexMode    e,2 → SetEdgeMode      f,3 → SetFaceMode
m   → Move             r   → Rotate           s   → Scale
o   → CycleDisplayMode w   → ToggleWireframeOverlay
ctrl+z/ctrl+y → Undo/Redo      ESCAPE → Cancel      alt+a → ClearSelection
LMB → Select   RMB → Orbit   MMB → Pan   Wheel → Zoom
context "topology":  s → SplitEdge  k → Collapse  c → Connect
                     l → EdgeLoop   r → EdgeRing  alt+e → Extrude
```

### 3.2 What the Playground actually does with it

**OBSERVED.** `PlaygroundInputBinding.__init__` (`input_adapter.py:110`) calls `build_default_bindings()` and **never applies a single override**. There is no `keymap.json`, no `bind()` call at runtime, no Playground-specific default table. The Playground therefore inherits the *production* key semantics wholesale, while `window.py` simultaneously implements a *different* set of key semantics by hand.

**OBSERVED.** `_mouse_from_pyglet` and `_wheel_from_pyglet` (`input_adapter.py:68`, `:91`) exist and are **never called anywhere**. The entire mouse and wheel path bypasses `BindingSet` completely and is hardcoded in `window.py` (`on_mouse_press/drag/release/scroll`). The claim in `WP-AP_INPUT_WIRING_REPORT.md` §7 that "no parallel definition" remains is true only for part of the keyboard.

### 3.3 The whitelist gate

**OBSERVED.** `playground/command_handler.py:62-68`:

```python
SAFE_COMMANDS = {UNDO, REDO, SET_VERTEX_MODE, SET_EDGE_MODE, SET_FACE_MODE,
                 CYCLE_DISPLAY_MODE, TOGGLE_WIREFRAME_OVERLAY, SPLIT_EDGE,
                 MOVE, ROTATE, SCALE}
```

Any command in this set is executed and the event returns immediately. Any command not in it returns `False` and falls through to the hardcoded chain. The whitelist is a **third** binding authority: it does not decide what a key means, it decides *which of the two other systems* gets to interpret it. It is keyed on commands, while the conflicts it is meant to arbitrate exist at the level of physical keys.

### 3.4 Verified dispatch table (executed, global context, default variants)

Resolution was computed by running the real `build_default_bindings()` against the real `SAFE_COMMANDS`. The reachability of each `window.py` branch was derived by AST extraction of the dispatch chains.

| Key | → Command | Whitelisted | What actually happens | What was intended |
|---|---|---|---|---|
| `X` | *(unbound)* | — | axis constraint `"x"` **and** Tweak-V1 arming | Move |
| `W` | `ToggleWireframeOverlay` | **yes → early return** | wireframe overlay toggles | **Rotate — never runs** |
| `E` | `SetEdgeMode` | **yes → early return** | switches to edge mode | **Scale — never runs** |
| `R` | `Rotate` | **yes → early return** | Rotate tool activated with `_transform_key_down='r'` | **Extrude — never runs** |
| `Shift+R` | *(unbound)* | — | caught by `elif symbol == _key.R` (`:1235`), inner guard rejects → **nothing** | Ring Select |
| `S` | `Scale` | yes | Scale activated with `'s'` | (freed by rebinding) |
| `M` | `Move` | yes | Move activated with `'m'` | documented no-op (`:1300`) |
| `V` | `SetVertexMode` | yes | vertex mode | `show_vertices` toggle (`:1275`) **dead** |
| `F` | `SetFaceMode` | yes | face mode | Articulation Restore (`:1448`) **dead** |
| `Z` | *(unbound)* | — | wireframe overlay (`:1271`) **and** axis constraint `"z"` (`:1387`) — both fire | one of the two |
| `Shift+D` | *(unbound)* | — | caught by `elif symbol == display_cycle` (`:1167`) → cycles presentation | wireframe toggle (`:1271`) **dead** |
| `Ctrl+Z`/`Ctrl+Y` | `Undo`/`Redo` | yes | via handler; `:1174`/`:1182` **dead duplicates** | undo/redo ✓ |
| `1`/`2`/`3` | `Set*Mode` | yes | via handler; `:1312`–`:1326` **dead duplicates** | component modes ✓ |
| `ESCAPE` | `Cancel` | **no** | falls through to legacy cascade `:1457`; `_handle_cancel()` (150 lines) **dead** | cancel ✓ |
| `K`/`I`/`J`/`G`/`Shift+L` | unbound / not whitelisted | — | hardcoded chain ✓ | ✓ |
| `C`/`H`/`Y` | unbound | — | scene loading ✓ | ✓ |
| `Q`/`TAB` | unbound | — | variant / family cycling ✓ | ✓ |

In **topology** context (`focused_family == "topology"`) the table changes again: `R` → `EdgeRing` (not whitelisted) → falls through → Extrude branch; `S` → `SplitEdge` (whitelisted) → split. The same two physical keys mean four different things depending on a family focus that is itself changed by `TAB`.

**Why it matters:** eight of the twenty-six branches in the main chain are unreachable, and three artist-visible capabilities (Rotate, Scale, Ring Select) cannot be triggered at all. None of this is visible from any single file.

**Confidence:** HIGH (executed). **Intentional or accidental:** accidental, produced by an intentional two-generation design.

### 3.5 Press/hold/release is split across three incompatible key alphabets

**OBSERVED.** The same concept — "which transform key is currently held" — is encoded three different ways:

| Location | Alphabet | Set by |
|---|---|---|
| `command_handler.py:166,180,194` | `'m'`, `'r'`, `'s'` (`tool_type[0]`) | command path |
| `window.py:1408`, `:1546` | `'x'`, `'w'`, `'e'` | rebinding block (new) |
| `window.py:810`, `:1079` | `'x'`, `'r'`, `'s'` | Tweak V1/V3 (stale) |

`on_key_release` only understands the second alphabet — and, because of the shadowing at `:1529`, only two thirds of it. Consequences, all OBSERVED:

- Move activated via `M` (command path, `_transform_key_down='m'`) → `on_key_release` has **no branch for `M` at all** → the hold model never commits, `_clear_transform_state()` never runs, the tool stays live.
- Move activated via `X` → release is swallowed by the axis-constraint branch → same result.
- `window.py:1079`: `{"x": "move", "r": "rotate", "s": "scale"}[self._tweak_v1_key]` — `_tweak_v1_key` can now hold `'w'` or `'e'`. Today it cannot, *only because* `W` and `E` are swallowed by the whitelist first. **The moment the whitelist bug is fixed, this line raises `KeyError` on the first Tweak-V1 drag.** Fixing bug A detonates bug B. Same latent defect at `:810` for Tweak V3.

**Confidence:** HIGH. **Intentional or accidental:** accidental; the rebinding pass updated two of the four mapping tables.

### 3.6 Two experiment slots claim the same physical keys, and neither yields

**OBSERVED.** `ExperimentSlot._active_index` defaults to `0` (`playground/slot.py:62`). The tweak slot is registered as `(TweakV1HoldKey, TweakV2Silo, TweakV3HoldClick, TweakV4HoldCtrl)` (`window.py:263-267`) — there is **no "off" variant**. Therefore `_active_tweak_variant()` returns `"v1"` at every startup.

At `window.py:1419-1427`, if `tv == "v1"`, the transform keys arm a Tweak gesture and the comment states explicitly: *"Does NOT run existing transform handling — V1 owns X/R/S when active"*.

**Consequence:** the Transform family's default `HoldActivationVariant` — the workflow that `playground/MANUAL.md` documents as the base interaction — is **unreachable at startup**. It becomes reachable only after focusing the `tweak` family (`TAB`) and cycling it (`Q`) to V2 or V4.

**Why it matters:** this is the deepest structural cause in the input area. The Experiment Host has *slots*, but no concept of **input ownership between slots**. Two families silently contend for one key, and the winner is decided by a hardcoded `if` inside the window rather than by the host. Every future family will add another contender.

**Confidence:** HIGH. **Intentional or accidental:** the V1-owns-the-key rule is intentional and documented in-code; the *global, unconditional* effect of it is accidental.

### 3.7 Silent failure at every seam

**OBSERVED.** The path has no diagnostic surface at all:

- unbound key → `command_for` returns `None` → silent fall-through
- command not whitelisted → `handle_command` returns `False` → silent fall-through
- handler precondition unmet (wrong selection mode, empty selection) → returns `False` → silent, and in `_handle_selection_mode_commands` it returns `True` while doing nothing when `app.viewport is None`
- `playground/transformer.py:63-107` — `begin_transform`, `update_transform`, `commit_transform`, `cancel_transform` each wrap the tool call in `try: ... except Exception: return False`. **Every tool-lifecycle error is swallowed silently.**

**Why it matters:** when a change is wrong, nothing says so. The artist sees "the key does nothing", the agent sees green tests, and neither gets a stack trace. This is the single cheapest thing to fix and probably the highest-leverage one.

**Confidence:** HIGH. **Intentional or accidental:** the bare `except Exception` is intentional defensiveness with accidental consequences.

---

## 4. Sources of Truth

| Concept | Places it is defined | Classification |
|---|---|---|
| **Key → command** | `src/mirai/interaction/bindings.py`; `playground/input_map.py` (D/Z/V + modifiers); `playground/window.py` hardcoded chain; `SAFE_COMMANDS` as arbiter | **DANGEROUS** — four, none authoritative |
| **Which transform key is held** | `'m/r/s'` (handler) vs `'x/w/e'` (window, ×2) vs `'x/r/s'` (tweak, ×2) | **DANGEROUS** |
| **Topology ops orchestration** | `window.py:1189-1381` and `command_handler.py:342-536` — near-verbatim duplicates | **DANGEROUS** (whichever runs depends on two other files) |
| **ESC cancel cascade** | `window.py:1457-1497` (live) and `command_handler.py:199-270` (dead) | **DANGEROUS** — two copies, one unreachable, both maintained |
| **Undo/Redo** | `command_handler.py:110` (live) and `window.py:1174/1182` (dead) | **AMBIGUOUS** |
| **Component mode 1/2/3** | `command_handler.py:552` (live) and `window.py:1312-1331` (dead) | **AMBIGUOUS** |
| **Active tool** | `ToolManager` (production, unused) · `PlaygroundApp.active_tool` · `_extrude_tool` · `_loop_slide_tool` · `_tweak_tool` · `PlaygroundCommandHandler.tool_manager` (constructed at `:41`, **never used**) | **DANGEROUS** — previously O2, now worse by one |
| **Documented key list** | `playground/MANUAL.md` (stale) · `INPUT_WIRING_MAP.md` (desired) · `WP-AP_INPUT_WIRING_REPORT.md` (claimed) · `bindings.py` docstring · `input_map.py` | **DANGEROUS** — five, all mutually inconsistent |
| **Axis/plane constraint** | `window.py:1387` (`_axis_constraint`) and `_resolve_space()` in `src/mirai/interaction/tools/transform.py:172` with flat-string backward-compat aliases | **TRANSITIONAL** (AD-009/AD-012, acceptable) |
| Topology primitives, Core copy, camera matrix | as in prior audit §3 | **INTENTIONAL / already documented** |

**The decisive point:** a duplicate source of truth is tolerable when one copy is obviously authoritative. Here, for any given key, *which* copy is authoritative depends on a set literal in a third file and on a runtime family focus. That is what makes it dangerous rather than merely untidy.

---

## 5. Ownership & Boundaries

> **"If I wanted to change ONE interaction, is there one obvious place where that behavior belongs?"**

**For production tools: yes.** Changing what Rotate *does* → `src/mirai/interaction/tools/rotate.py`. Changing command→tool routing → `routing.py`. Adding a command name → `commands.py`. These boundaries hold. **OBSERVED.**

**For anything the artist can actually press: no.** Changing what the `R` key does requires a decision across, minimally:

`bindings.py` (does a production default already claim it?) → `SAFE_COMMANDS` (will the handler swallow it?) → `determine_input_context` (does the topology family change the meaning?) → the elif chain (is there an earlier branch that shadows it?) → the axis block (does it also fire?) → the tweak/transform block (does V1/V3 own it?) → `on_key_release` (is the release branch reachable?) → four key-alphabet tables → `MANUAL.md` + `INPUT_WIRING_MAP.md`.

**Unclear ownership, concretely:**

- **Input ownership between experiment families** — no owner. Not in `ExperimentSlot`, not in `Experiment` (`playground/experiment.py` is 31 lines and has no input contract), not in the host. Decided by `if tv == "v1"` inside the window. *(OBSERVED; extends prior O1.)*
- **Tool lifecycle** — the production `ToolManager` contract (cancel-before-switch, `INTERACTING` guards) is bypassed by every live path. Prior O2 noted two authorities; there are now six. *(OBSERVED.)*
- **Selection behaviour** — unchanged from prior O3; state in Core, behaviour in `playground/selector.py`, mode written from Core, selector, window and command handler. **This one is intentional and should stay open** (see §15).
- **`command_handler` ↔ `window`** — the handler reaches into **22 distinct private members** of the window (`self.window._update_hud` ×25, `_hud` ×20, `_rebuild_vbo` ×10, `_transform_key_down`, `_tweak_*`, `_articulation_state`, …) while the window imports and owns the handler. They are one object split across two files, and the split hid the dispatch rather than separating it. *(OBSERVED.)*

---

## 6. Coupling / Dependency Hotspots

**OBSERVED.** No circular *imports* exist. The problem is change coupling, not import cycles.

**Hotspot 1 — the `window.py` ↔ `command_handler.py` pair.** Bidirectional reference, 22 private members crossed, duplicated orchestration for six operations. **Any change to one requires reading the other.** This is the highest-fan-in node in the repository; `window.py` imports 30+ modules including every experiment variant class.

**Hotspot 2 — the whitelist as a global coupler.** `SAFE_COMMANDS` is a set of eleven strings that silently determines the reachability of eight branches spread over 250 lines in another file. There is no reference from those branches back to the whitelist. Adding one entry can kill a feature; removing one can resurrect a latent `KeyError` (§3.5). **This is the single most harmful coupling found.**

**Hotspot 3 — key-alphabet tables.** Four tables, three alphabets, updated independently. Change coupling of degree 4 for a one-line change.

**Hotspot 4 — hidden global state in the window.** Eleven `_tweak_*` flags, `_transform_key_down` / `_transform_mode_on` / `_transform_started`, `_axis_constraint`, `_articulation_*`, `_drag_*`, `_box_*`, plus four tool fields. The state machine is implicit; correctness of a branch depends on flags set in three other methods. Prior O1 already flagged the concentration; the WP-AP work added two more cross-cutting flags and an external mutator.

**Not a hotspot, explicitly:** `src/core` (504-line `mesh.py` is cohesive, invariant-tested), `src/viewport` (dirty-state design is intentional complexity), `src/mirai/interaction/tools/transform.py` (362 lines, one concept, documented under AD-012).

---

## 7. Legacy / Migration Residue

**Resolved since the previous audit (good news, OBSERVED):**
- `experiments/mirai_bastel_viewport_V1/` and `experiments/mirai_bastel_integration_lab/` deleted (`8ef4def`) → prior D1 reduced from 46 to 9 collection errors, prior D3 gone, AI-H1's old `window.py` duplicate under `playground/experiments/articulation/_old_/` is now the only remaining window twin.
- `playground/_paths.py` now points at `examples/` per AD-007.

**Still present:**

| Item | Location | Class |
|---|---|---|
| `playground/experiments/articulation/_old_/` — 1 881 lines incl. a second `PlaygroundWindow` | committed as "old files", imported by nothing | **LEGACY** — an agent grepping for `PlaygroundWindow` or a key handler still gets two plausible hits |
| `elif False:` placeholder with a live-looking body | `window.py:1304-1311` | **DEAD, marked** |
| `elif symbol == _key.M: pass` | `window.py:1300` | **DEAD, marked** |
| Six dead duplicate branches (Ctrl+Z, Ctrl+Y, V, 1, 2, 3, F) | `window.py` | **DEAD, unmarked** |
| Two dead shadowed branches (Shift+R ring, Shift+D wireframe) | `window.py:1366`, `:1271` | **DEAD, unmarked, feature-losing** |
| `PlaygroundCommandHandler._handle_cancel()` — 150 lines | `command_handler.py:199` | **DEAD** (ESC never whitelisted) |
| `PlaygroundCommandHandler.tool_manager` | `command_handler.py:41` | **DEAD** |
| `_mouse_from_pyglet` / `_wheel_from_pyglet` | `input_adapter.py:68,91` | **DEAD** |
| `playground/input_map.py` — partly superseded | `display_cycle`/`wire_overlay` live, `show_vertices` dead, selection modifiers still used | **TRANSITIONAL** |
| `_measure_coverage.py`, `tests/mesh.py`, `tests/history.py`, `tests/*.patch` | root / `tests/` | **POSSIBLY DEAD** — unchanged from prior audit |

**Does the repository contain multiple generations of the same architecture?** For input: **yes, three.** (a) the hardcoded Playground chain, (b) the production BindingSet/Command layer, (c) the whitelist arbiter added to make (a) and (b) coexist. `WP-AP_INPUT_WIRING_REPORT.md` §"Next Steps" item 5 names this explicitly: *"Gradually remove hardcoded handlers from window.py now that command handler exists (safe to defer)."* It was deferred; the two generations then drifted within one day.

---

## 8. AI-Agent Change-Cost Analysis

Estimated files/layers an agent must correctly understand before a change is *safe* (not merely plausible):

| Task | Files | Hidden decision points | Is the correct location obvious? |
|---|---|---|---|
| **Change one key binding** | 5–9 | binding table, whitelist, context function, chain order, axis block, tweak/transform block, release chain, 4 alphabet tables, 2 docs | **No.** Highest-context-cost task in the repository. |
| **Add one command** | 4 | `commands.py`, `bindings.py`, `SAFE_COMMANDS`, handler method — *plus* whether a hardcoded branch already implements it | Partly — the production half is obvious, the Playground half is not |
| **Modify one interaction** (e.g. "Extrude should commit on click") | 3–6 | `window.py` chain + release + variant class + possibly handler duplicate | No |
| **Change selection behaviour** | 2–3 | `playground/selector.py` + variant class | **Yes** — this area is clean |
| **Add one topology operation** | 3–4 | `topology_tools/*.py` + a chain branch (+ its duplicate in the handler) | Mostly yes for the algorithm, no for the trigger |
| **Change a transform tool's math** | 1–2 | `src/mirai/interaction/tools/*` | **Yes** — clean |
| **Change Core mesh behaviour** | 1–2 + freeze doc | invariants, ADR | **Yes** — clean and deliberately gated |

**The pattern is sharp.** Everything *below* the input layer is cheap to change and has an obvious home. The input layer alone is expensive, and it is expensive in the specific way that defeats agents: the information needed to make a correct change is **negatively correlated with locality**. The branch you are editing gives no hint that a whitelist in another file decides whether it runs.

**Three additional agent-specific traps, all OBSERVED:**

1. **The tests give a false green.** No test drives an event handler. `playground/tests/test_axis_constraint_wiring.py:29-200` copies the production `if` statements into the test body and asserts on its own copy — these tests cannot fail no matter what `window.py` does. An agent that runs the suite is *actively misinformed*.
2. **`test_input_wiring.py:88-108` pins the old scheme** (`M → MOVE`, `R → ROTATE`) while the code comments claim the new one (`W/E/R`). An agent reading tests to learn the intended mapping learns the wrong one.
3. **`WP-AP_INPUT_WIRING_REPORT.md` §1 is inaccurate.** It states `K → cmd.SPLIT_EDGE`, `J → cmd.CONNECT`, `I → cmd.LOOP_INSERT`, `E → cmd.EXTRUDE`, `Shift+L → EDGE_LOOP`, `Shift+R → EDGE_RING` are routed via commands. **None of those bindings exist** — `bindings.py` binds `s→SplitEdge`, `c→Connect`, `alt+e→Extrude`, `l→EdgeLoop`, `r→EdgeRing`, and no `LoopInsert` binding exists at all. §3 of the same report says *"No Conflicts Encountered"*. An agent that trusts this document builds on a false model.

---

## 9. Documentation vs. Implementation

| Document | Claim | Reality | Class |
|---|---|---|---|
| `docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md` | *"implementiert und praktisch validiert im Viewport-V1-Experiment (`experiments/mirai_bastel_viewport_V1/`)"* | that directory was deleted in `8ef4def` | **OUTDATED** — canonical input contract cites a non-existent validation |
| `docs/architecture/AD-011` (DECIDED) | Playground *deliberately diverges*; production input contract *remains unhandled* and is *not expected to be resolved* yet | `54e9840` wired the Playground to production `BindingSet` one day later; no superseding AD exists | **VIOLATED, silently** — see §10 |
| `playground/MANUAL.md` (last touched 2026-09-14) | LMB-drag = Orbit; `Q`/`Esc` = close window; `X/R/S` = transform; `M` = selection-mode cycle; `V` = show vertices | Orbit requires `Alt+LMB` (`window.py:942`); `Q` cycles variants; `X` arms Tweak; `M` activates Move; `V` sets vertex mode | **OUTDATED** — the artist's own key reference does not describe the running program |
| `WP-AP_INPUT_WIRING_REPORT.md` | six command routes that do not exist; "No Conflicts Encountered" | see §8 trap 3 | **FACTUALLY WRONG**, and it is a root-level document |
| `CLAUDE.md` | Playground depends on `experiments/mirai_bastel_integration_lab`; bare `pytest` yields 46 errors | those dirs are deleted; 9 errors | **OUTDATED** (minor, cheap fix) |
| `command_handler.py` module docstring | *"ToolManager for modal tools"*, *"ESC cascades…"* | ToolManager unused; ESC cascade dead | **OUTDATED** |
| `src/mirai/application.py` docstring | the full Input→Command→Tool→Operation path | `dispatch_command` handles only Move/Rotate/Scale/Undo/Redo | **prior D4, unchanged** |
| `docs/` root | 41 loose `.md` files, incl. two byte-identical duplicates and two WP revision pairs | — | prior finding, unchanged |
| `AGENTS.md`, `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md`, `AD-009/010/011/012`, `bindings.py`, `input.py` docstrings | — | accurate | **HEALTHY** |

**Terminology drift, OBSERVED:** "experiments" still means two things (prior AI-H6); "Input Wiring" now means three things (the binding table, the adapter, and the whitelist); "the fix" in `WP-AP-INPUT-FIX-01` covers three unrelated work items (whitelist, axis constraints, rebinding) in one commit, which makes the history hard to bisect.

---

## 10. Evidence from Recent Input-Wiring Failures

Reconstructed sequence, all **OBSERVED** from git:

1. **2026-09-17** — `AD-011` decides: Playground keeps diverging; the production input contract stays unhandled. Prior audit records AI-H2 ("three input authorities with conflicting key semantics") and warns, verbatim: *"An agent 'aligning the Playground with the production bindings' would silently break the artist's muscle memory — the very thing the Playground exists to research."*
2. **2026-09-18** — `54e9840` does exactly that. The WP report declares success on the basis of 688 green tests and explicitly notes *"Live Window Testing: Not performed in this session (no X11/display available)."*
3. **2026-09-19** — `aac474e` repairs the resulting damage with a whitelist, whose commit message documents the failure mode precisely: *"Fixes precedence bug from 54e9840 that silenced Playground state machines."*
4. **2026-09-19** — `4d7fdb7` bundles three further changes (axis constraints, key rebinding, whitelist re-expansion), re-adds `MOVE/ROTATE/SCALE` to the whitelist on the stated assumption that *"their new keys (W/E/R) don't conflict"* — which is false for `W` (`ToggleWireframeOverlay`) and `E` (`SetEdgeMode`) — and introduces the `on_key_release` shadowing that kills Move's commit.

**Category assessment:**

- **A (isolated implementation mistakes)** — present but minor. The `elif` ordering errors are ordinary bugs; the off-by-one against `INPUT_WIRING_MAP.md` is an ordinary misreading.
- **B (agent misunderstanding despite a clear architecture)** — **rejected.** The architecture is not clear at this point. No document states which of the five authorities wins.
- **C (architecture makes the correct location ambiguous)** — **strongly present.** For `R` there are five defensible edit sites and no rule for choosing.
- **D (competing implementations / sources of truth)** — **strongly present, dominant.** §4 lists eight dangerous duplications in the input path alone.
- **E (accumulated migration/legacy complexity)** — **strongly present, dominant.** The dual-path design was adopted deliberately (*"Gradual migration path. Old code still works; new code takes precedence when wired."*) and then not completed.

**Verdict: F — combination, weighted D + E > C > A.** The agent's reported reasoning is not confused; it is *locally correct and globally wrong*, which is the signature of a structural problem rather than a capability problem. Two further accelerants are structural, not agential: the test suite cannot detect input regressions (§8 trap 1), and no live-window verification is possible in the agent's environment, so "green" is the only available success signal and it is the wrong one.

**One honest caveat (UNKNOWN):** the off-by-one against the artist's desired mapping, and bundling three work items into one commit, are agent-side errors that better architecture would not have prevented. They are a minority of the observed damage, not its cause.

---

## 11. Findings by Severity

### CRITICAL — user-visible capability loss at HEAD

| # | Finding | Evidence | Confidence |
|---|---|---|---|
| C1 | Rotate and Scale cannot be activated; `W`/`E` are swallowed by the whitelist | `bindings.py:76-80` + `command_handler.py:62` + `window.py:1407`; executed | HIGH / accidental |
| C2 | Move never commits on key release (`:1529` shadows `:1540`) | AST | HIGH / accidental |
| C3 | Ring Select unreachable (`:1235` shadows `:1366`) | AST | HIGH / accidental |
| C4 | Transform "hold" variant unreachable at startup — Tweak V1 owns the keys unconditionally | `slot.py:62` + `window.py:263,1419` | HIGH / partly intentional, globally accidental |
| C5 | Implemented key mapping contradicts the artist's `INPUT_WIRING_MAP.md` (off-by-one) | `window.py:1408` vs map §4 | HIGH / accidental |

### HIGH — structural causes

| # | Finding | Evidence | Confidence |
|---|---|---|---|
| H1 | `SAFE_COMMANDS` is a non-local, invisible reachability switch over 250 lines in another file | `command_handler.py:62` | HIGH / intentional, harmful |
| H2 | Three incompatible key alphabets (`m/r/s`, `x/w/e`, `x/r/s`) across four tables | §3.5 | HIGH / accidental |
| H3 | No input-ownership model between experiment families | `experiment.py`, `slot.py` | HIGH / gap, not error |
| H4 | Input tests do not test input; axis tests are tautological | `test_axis_constraint_wiring.py:29+` | HIGH / accidental |
| H5 | `AD-011` overridden without a superseding decision (M1/M5, `AGENTS.md §5`) | git + AD-011 | HIGH / accidental |
| H6 | Silent failure at four seams incl. blanket `except Exception` in `transformer.py` | `transformer.py:63-107` | HIGH / intentional, harmful |
| H7 | ~300 lines of duplicated orchestration between window chain and handler | §4 | HIGH / transitional |
| H8 | `WP-AP_INPUT_WIRING_REPORT.md` states six non-existent bindings and "no conflicts" | §8 | HIGH / accidental |

### MEDIUM

| # | Finding | Confidence |
|---|---|---|
| M1 | `Z` triggers wireframe overlay *and* Z-axis constraint; `Shift+D` shadowed | HIGH / accidental |
| M2 | Six dead duplicate branches + two dead handler blocks (`_handle_cancel`, `tool_manager`) | HIGH / transitional |
| M3 | Latent `KeyError` at `window.py:1079` / `:810`, currently masked by C1 | HIGH / accidental |
| M4 | `MANUAL.md` — the artist's key reference — is wrong in at least six rows | HIGH |
| M5 | `INPUT_COMMAND_TOOL_CONTRACT.md` cites a deleted experiment as its validation | HIGH |
| M6 | `command_handler` crosses 22 private members of `window` | HIGH / accidental |
| M7 | Mouse/wheel path never reaches `BindingSet`; adapters dead | HIGH / transitional |

### LOW
`CLAUDE.md` stale paths and error count; 41 loose docs incl. duplicates; `_old_/` legacy window; `_measure_coverage.py`; dead `tests/mesh.py`/`history.py`; `elif False` placeholder.

---

## 12. What Appears Healthy

**OBSERVED, and worth stating plainly — most of this repository is in good condition.**

- **`src/core`** — cohesive, invariant-tested, frozen with a real exception procedure. 449 production tests pass in 0.46 s. The `MeshStateCommand` snapshot decision (AD-001) is documented and holds.
- **`src/mirai/interaction/{input,bindings,commands,routing}`** — genuinely well designed: small, pyglet-free, layered, validated config, explicit unbind, 51 tests. **The production input architecture is not the problem and should not be touched.**
- **`src/mirai/interaction/tools/`** — Move/Rotate/Scale share one lifecycle contract; the WP-03B/C `space`/`axis` unification (AD-012) with backward-compat aliases is a clean, documented migration and a good counter-example to §3.
- **`src/viewport`** — dirty-state/incremental design is intentional complexity, documented, and not implicated.
- **Package-level boundaries** — `src/` does not import `playground/` or `experiments/`. The Promotion Boundary holds structurally.
- **`playground/topology_tools/`, `selector.py`, `slot.py`, `experiment.py`** — small, single-purpose, well tested. Adding a topology algorithm or a selection variant is cheap.
- **The Development System documents themselves** — `AGENTS.md`, `MIRAI_BASTEL_DEVELOPMENT_SYSTEM.md`, the AD series and `CLAUDE.md` are unusually honest and useful. `CLAUDE.md` naming the Playground as the only runnable application is exactly the kind of statement that saves an agent an hour.
- **Cleanup already executed** — V1 and the Integration Lab were removed cleanly; prior findings D1 and D3 are largely resolved. The project *does* act on its audits.

---

## 13. What Appears Structurally Risky

1. **One key press is decided by five authorities in three files with no arbitration rule.** (§3) This is the finding. Everything else in this section follows from it.
2. **The Experiment Host has no input-ownership concept.** Families are isolated for *state* but contend for *keys*. Each new family adds a contender, and the resolution lives in the window's `if`-chain. This will get worse with Rigging/Morphing (the planned second M4 instance).
3. **`window.py` is the single highest-risk node and it is still growing.** Prior O1 counted 1 411 lines and nine responsibilities; it is now 1 739 lines with an external mutator. Every WP-AP work package adds to it.
4. **The verification signal for interaction work is broken.** Green tests + no live-window capability = a success criterion that cannot detect the failures that actually occur. This is why three consecutive input commits each reported success.
5. **A half-finished migration left running.** The dual-path design assumed a later cleanup pass; without one, the two generations drift within days.
6. **Decision-level drift.** `AD-011` was overridden by an implementation WP. If a DECIDED architecture document can be superseded by a commit, the AD series stops functioning as project memory — which is the mechanism the whole Development System rests on.

---

## 14. Refactoring Candidates

**This audit's mandate stops at establishing whether a refactoring phase is justified. It is — for one narrowly bounded area.** The following are candidates, in dependency order, not a plan. Each should get its own WP spec per `ROADMAP.md §9`.

**Before any of it: a Discovery/decision step, not a build step.** The question *"Who owns a physical key in the Playground — the production BindingSet, the Experiment Host, or the window?"* is a Product-Truth-adjacent architecture question that `AD-011` answered for a different situation and that the WP-AP work implicitly re-answered without writing it down. It needs an AD (amending or superseding AD-011) **before** any code moves. Without it, the next pass will re-create the same ambiguity.

Then, in order:

1. **Make the failure surface visible** (cheapest, highest leverage, no architecture change). Replace the blanket `except Exception` in `transformer.py` with narrow catches; add a one-line HUD/stderr trace at each fall-through seam saying *which* authority consumed the key. This alone would have caught C1, C2, C3 within seconds of play.
2. **Write one executable key-dispatch table.** A headless test that, for each (key, modifiers, context, active variants), asserts the resulting action by driving the real `on_key_press`/`on_key_release`. This is the missing verification layer; it makes every subsequent step safe and it is the only thing that turns "all tests pass" back into a meaningful sentence.
3. **Collapse the two generations into one.** Either the chain or the handler owns dispatch — not both. The whitelist is a symptom and should disappear with the duplication, not be extended.
4. **One key alphabet.** A single `KEY → tool_type` table consumed by press, release, tweak V1 and V3.
5. **Give the Experiment Host an input-ownership contract** (e.g. `Experiment.claims_key(input) -> bool`, or an explicit per-slot precedence order), so family contention is resolved by the host rather than by an `if` in the window.
6. **Reconcile the key documentation to exactly one source** — probably `INPUT_WIRING_MAP.md` as artist intent plus a generated table; `MANUAL.md` then quotes it rather than restating it.
7. **Only afterwards:** extract per-family interpreters out of `window.py` (prior O1's suggestion). Doing this first would move the ambiguity rather than remove it.

**Explicitly out of scope for this refactoring phase:** everything not in the keyboard/mouse dispatch path.

---

## 15. Things That Should NOT Be Refactored

- **`src/core`** — frozen, invariant-tested, working. No evidence of drift. Changes only via the documented exception procedure.
- **`src/mirai/interaction/input.py` / `bindings.py` / `commands.py` / `routing.py`** — the production input layer is the *good* design here. It should not be "simplified", merged into the Playground, or made Playground-aware. The Playground should stop half-adopting it, not the reverse.
- **`src/mirai/interaction/tools/*` and the AD-012 `space`/`axis` work** — recent, documented, tested, with a clean backward-compat path. Leave it.
- **`src/viewport`'s dirty-state/incremental design** — intentional complexity for a known future requirement. Not implicated in any finding.
- **The Playground↔experiments topology/rendering overlaps** — prior audit's explicit non-recommendation stands: these encode the project's method (prototype → port against production → decide). Not duplication to merge.
- **Selection behaviour ownership (prior O3)** — deliberately un-promoted; `RESEARCH_MAP.md §5A` makes Target Resolution the *central open research question*. Resolving this ambiguity by refactoring would pre-empt a Product-Truth decision that only Manu can make. **Leave open.**
- **The variant/slot experiment model itself** — it works and it is the point of the Playground. Only its *input contention* needs an owner (§14.5); the model does not need replacing.
- **`playground/camera.py`'s `PlaygroundCamera`** — prior D2 suggested the override may now be redundant; that is a separate question with its own evidence chain. Do not fold it into an input refactor.
- **Anything justified by "while we're in there".** The repository's own rule applies: *a process mechanism must solve an error that occurred, not one that is expected.*

---

## 16. Recommended Next Investigation

In priority order. Items 1–3 are cheap and should precede any decision about scope.

1. **Live-window confirmation of C1–C4 (≈15 minutes, artist).** Start `python playground/run.py` and press, in order: `W`, `E`, `R`, `X` (+drag+release), `Shift+R`, `Z`. Predicted: `W` toggles wireframe, `E` switches to edge mode, `R` activates Rotate, `X`+drag performs a Tweak that does not commit on release, `Shift+R` does nothing, `Z` toggles wireframe *and* shows a Z constraint in the HUD. **This is the one thing this audit cannot do from a headless container**, and it converts every CRITICAL finding from OBSERVED-static to OBSERVED-live. If the predictions hold, the diagnosis in §10 is confirmed outright.
2. **Decide the input-ownership question (AD, Manu + one agent analysis).** Who owns a physical key in the Playground? This is the blocking decision for §14. It should either amend `AD-011` or supersede it explicitly — and it should record *why* the WP-AP direction was taken, so the next agent finds the reasoning rather than the contradiction (M1: "X wird nicht verwendet, weil Y").
3. **Build the executable dispatch table test (§14.2) before any cleanup.** Without it, any refactor of this area is unverifiable and will repeat the last three commits.
4. **Retro-test the last three input commits against M1/M5** — the previous audit's §9 "could change the system" item. Three real drift cases now exist with full git evidence. The specific question: was the information *missing*, or *present but not looked at*? Evidence here leans "present but contradicted by a newer, wrong document" (`WP-AP_INPUT_WIRING_REPORT.md` vs `AD-011`), which would suggest the fix is document *authority*, not document *quantity* — and that M2 (Context Check) is not the mechanism that would have caught it.
5. **Decide how independent AI reports enter the repository.** `WP-AP_INPUT_WIRING_REPORT.md` sits at root, claims completion, and is factually wrong in three places. Under `AGENTS.md §6` an archived review must not be edited to agree with later findings — but a *self-reported completion report* is not an independent review, and it currently outranks an AD by position and recency alone. Worth one explicit rule.
6. **Smaller, unblocked:** reconcile `INPUT_COMMAND_TOOL_CONTRACT.md` (deleted-experiment citation), `CLAUDE.md` (stale paths, error count), `MANUAL.md` (six wrong rows) — each a one-commit documentation fix, none of which requires a decision.

---

## Appendix — verified environment facts

| Check | Result |
|---|---|
| `pytest tests --ignore=tests/test_extrude_tool.py` | **449 passed** (0.46 s) |
| `PYGLET_HEADLESS=1 pytest playground/tests` | **290 passed** (0.78 s) |
| bare `pytest` from repo root | **9 collection errors** (was 46 before the V1 removal) |
| Tests calling `on_key_press` / `on_key_release` / `on_mouse_press` | **0** |
| `git status --short` after audit | empty — repository unmodified |

*End of report. No code, documentation, configuration or history was changed.*
