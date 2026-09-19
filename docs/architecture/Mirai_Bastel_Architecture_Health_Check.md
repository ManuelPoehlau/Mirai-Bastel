I have completed the forensic trace. I am in plan mode, so I have made **zero changes** to the repository — the full report follows below. If you want it persisted as a file (e.g. `docs/ARCHITECTURE_HEALTH_CHECK_2026-09-19.md`), toggle to Act mode and I will write it verbatim.

---

# MIRAI-BASTEL — ARCHITECTURE HEALTH CHECK

**Date:** 2026-09-19 · **Mode:** Read-only forensic audit · **Head commit:** `86c8d9c`
**Method:** Runtime code-path tracing (window.py, command_handler.py, input_adapter.py, bindings.py, input.py, commands.py, routing.py, transformer.py, app.py, slot.py), git history analysis (`54e9840` → `aac474e` → `4d7fdb7` → `86c8d9c`), and documentation cross-reference. No code was run live; dynamic claims are static traces flagged accordingly.

---

## 1. Executive Summary

**Answer to the primary question: Yes — but the drift is concentrated, not general.**

Mirai-Bastel's *production* architecture (`src/core`, `src/viewport`, `src/mirai/interaction`) is in good health: small modules, a real contract (`INPUT_COMMAND_TOOL_CONTRACT.md`), validated keymap loading, 449 passing tests. That is not where the pain is.

The pain is in **one specific structural decision made during WP-AP Input Wiring**: the Playground now has **two parallel key-dispatch systems that are merged at a single choke point with a runtime whitelist**, and the de-facto owner of "what a key does" is a 1,587-line god-module (`playground/window.py`) that the new infrastructure reaches into via private attributes. A rebinding today must be consistent across up to **7 locations** (bindings.py, window.py's hardcoded elif chain, window.py's tweak key-maps, window.py's axis-constraint keys, command_handler.py's whitelist, 4 user/decision documents, and 2 test files). No document maps this.

The audit found **evidence that the failure class the Artist has been experiencing is not historical — it is currently live in the code**:

1. **A case/token mismatch between the two dispatch layers.** The command handler writes key tokens `'m'/'r'/'s'` into `window._transform_key_down` (`command_handler.py:168,176,184`), while `window.py`'s release handler only accepts `'q'/'w'/'e'` (`window.py:1538`). Press-Mode and Press-Drag-Click variants commit on key release — which can never match. *(OBSERVED, static trace)*
2. **The exact regression that WP-AP-INPUT-FIX-01 §1 fixed was re-introduced by §2–§4 three commits later.** §1 removed MOVE/ROTATE/SCALE from the handler whitelist because they "interfere with Tweak V1/V3 arming" (commit `aac474e` message). §2–§4 re-enabled them (`4d7fdb7`). Since the handler runs **before** window.py's tweak-arming block and always returns `True` for these commands, Tweak V1/V3 arming on Q/W/E is again preempted. *(OBSERVED, static trace — flagged for live verification)*
3. **A topology-context key can destroy the scene.** With `focused_family == "topology"`, `C` resolves via BindingSet to `cmd.CONNECT` (`bindings.py:91`), which is **not whitelisted** → handler returns `False` → fall-through hits window.py's first hardcoded branch: `symbol == _key.C → load_cube()` (`window.py:1149`). The intended "Connect Edges" loads a Cube instead. *(OBSERVED, static trace)*

The recent Claude Code failures are therefore **not primarily agent carelessness**. The pattern in the git log (three consecutive fix commits for one work package, each fixing keys the previous commit broke) is the signature of an architecture where the correct change location is *undiscoverable in advance* and where edits in one layer silently no-op, silently override, or silently break another layer — with a test suite that passes throughout because its wiring tests are mock-based and never execute both layers together.

One additional Product-Truth finding: the Artist's own `INPUT_WIRING_MAP.md` states desired inputs **Move = W, Rotate = E**; the implemented and thrice-fixed result is **Move = Q, Rotate = W, Scale = E**. The final keys do not match the documented Artist decision. *(OBSERVED — requires Artist confirmation, M4 case)*

---

## 2. Current Architecture Shape

**Implemented structure (OBSERVED):**

```text
src/core/       Domain: Scene, Mesh, Selection, Operations, History  (frozen, healthy)
src/viewport/   Render data, stores, facade                          (healthy)
src/mirai/      Application, interaction/{input,bindings,commands,
                routing,tool,tool_manager,tools/}, viewport/{camera,
                picking,display}                                     (healthy, partially unused)
playground/     The ONLY runnable application (AD-011: deliberately
                not "the application")                               (DRIFT ZONE)
experiments/    mirai_bastel_core_V1, mirai_bastel_viewport_V02,
                topology, rigging-skinning-morphing                  (research, fine)
```

**Production input chain (DOCUMENTED + OBSERVED, clean):**
`Input` → `BindingSet.command_for()` → `Command` → `Application.dispatch_command()` → `ToolManager`/`tool_for_command()` → `Tool` → `Operation` → History.

**Playground input chain (OBSERVED, the actual runtime path):**

```text
pyglet event
  → playground/input_adapter.py  (_key_from_pyglet, determine_input_context)
  → src BindingSet (production, shared)         ← the ONE shared layer
  → playground/command_handler.py::handle_command
        ├─ command ∈ SAFE_COMMANDS whitelist? → handle here
        │     (reaching into window._transform_*, window._hud, window._rebuild_*)
        └─ otherwise return False
  → FALL THROUGH to playground/window.py::on_key_press
        → 29 hardcoded `elif symbol == ...` branches
        → inline modifier tests, tweak key-maps, axis-constraint keys
        → window-owned state machines (_transform_*, _tweak_*, _articulation_*,
          _extrude_tool, _loop_slide_tool)
```

The fork point is `window.py:1140–1147`: the handler gets first refusal on **every** key; everything it declines lands in the elif chain. Which of the two systems "owns" a given key is determined by **whitelist membership + active experiment variant + focused family** — a fact documented nowhere.

---

## 3. Input Wiring Forensic Analysis

Trace of representative interactions. "Owner" = where behavior is actually implemented today.

| Interaction | Resolution source | Actual owner | Hidden overrides / notes | Confidence |
|---|---|---|---|---|
| **Orbit (Alt+LMB drag)** | none (BindingSet has `RIGHT→ORBIT`, unused) | `window.py:940–955` hardcoded, modifiers inline | BindingSet `ORBIT` binding is decorative for drag | OBSERVED |
| **Pan (MMB / Shift+LMB)** | none (`MIDDLE→PAN` unused) | `window.py:946–951` | same | OBSERVED |
| **Zoom (wheel)** | none (`ZOOM` binding unused) | `window.py:1059–1062` | same | OBSERVED |
| **Select (LMB click)** | none (`LEFT→SELECT` unused) | `window.py:1044–1058` → `selector.py::dispatch_click` | `input_map.select_button` consulted here (2nd source) | OBSERVED |
| **Ctrl+Z / Ctrl+Y** | BindingSet → `UNDO`/`REDO` | **command_handler** (whitelisted, `command_handler.py:119–130`) | window.py's own Ctrl+Z/Ctrl+Y branches (`window.py:1174–1186`) are **unreachable dead code** — exact duplicates incl. the same selection-clear side effect | OBSERVED |
| **1 / 2 / V / 3 (modes)** | BindingSet → `SET_*_MODE` | command_handler (`command_handler.py:552–578`) | **V conflict:** BindingSet maps `v→SET_VERTEX_MODE` AND `input_map.show_vertices = key.V` maps V→vertex *display* toggle (`window.py:1272`). Handler wins; the documented "V = Vertices" (MANUAL.md, README) is dead | OBSERVED (static) |
| **D / O / Z / Shift+D (display)** | BindingSet: `o→CYCLE_DISPLAY_MODE`, `shift+d→TOGGLE_WIREFRAME_OVERLAY`; input_map: `display_cycle=D`, `wire_overlay=Z` | **both layers** — D/Z via window elif, O/Shift+D via handler | Two functions, four keys, two owners; wireframe toggle reachable two ways | OBSERVED |
| **Q / W / E (transform)** | BindingSet (`bindings.py:69–71`) → `MOVE/ROTATE/SCALE` | **Ambiguous — this is the hotspot.** Handler handles them (whitelisted) and writes token `'m'/'r'/'s'`; window.py has a full parallel implementation (`window.py:1403–1441`) writing `'q'/'w'/'e'`, which is preempted — except its tweak-arming half is *supposed* to own these keys under tweak V1/V3 | Token mismatch `'m'` vs `'q'` breaks release matching; V1/V3 preemption regression (see §10) | OBSERVED |
| **X / Y / Z (+Shift) axis constraints** | **nowhere in BindingSet** | window.py:1383–1401 (4th key layer inside window.py) | Keys that *used to be* Move/Rotate — the historic source of "X is double-bound" | OBSERVED |
| **K (split edge)** | topology-context binding `s→SPLIT_EDGE`; global: no binding | **both layers**: handler (whitelisted) + window.py:1189 elif — near-duplicate logic | Harmless duplication today, drift risk tomorrow | OBSERVED |
| **C (connect — topology ctx)** | BindingSet `c→CONNECT` (topology ctx) | **neither**: not whitelisted → falls to window.py:1149 `load_cube()` | **Scene-destroying hidden fallback** (see §10) | OBSERVED (static) |
| **L / bare R (topology ctx)** | BindingSet `l→EDGE_LOOP`, `r→EDGE_RING` | **neither** — not whitelisted; window's branches require Shift+L / Shift+R or Face-mode | Bare L and bare R in topology focus do nothing / do the wrong thing | OBSERVED (static) |
| **Shift+L / Shift+R / I / G / F** | none in BindingSet (G had `LOOP_SLIDE` per WP-AP report — binding absent today) | window.py:1345,1362,1205,1221,1444 | WP-AP report documents Shift+L/Shift+R/G as "wired via production commands" — false today | OBSERVED |
| **ESC** | BindingSet `ESCAPE→CANCEL` | window.py cascade (`window.py:1450–1494`) — intentional per §1 | `command_handler._handle_cancel` duplicates the whole cascade and is **dead** (CANCEL not whitelisted) | OBSERVED |
| **M / Shift+M (variant/method cycling)** | none (deliberate, Playground-only) | window.py:1286–1300 | Clean — but invisible to BindingSet, so future rebinding of M by a production-minded agent will silently shadow it | OBSERVED |

**Per-layer answers to the audit questions:**

- *Where is the information defined?* — Key→command: `bindings.py` (authoritative for resolution). Behavior: `window.py` elif chain + `command_handler.py` handlers, split by whitelist. Activation semantics: `playground/experiments/transform/variant_*.py` (`activation` attribute), interpreted **twice** (window.py:644–650 and command_handler.py:152–190 — duplicated logic). Display/selection keys: `input_map.py`. Axis keys: hardcoded in window.py only.
- *Who owns press/hold/release semantics?* — **Split across modules.** Press logic exists in both command_handler (`_activate_transform`) and window (`window.py:1403–1441`); release logic exists **only** in window.py (`window.py:1536–1584`) and keys off the token written by whichever press path ran — the two paths write different tokens.
- *Are modifiers interpreted consistently?* — No. BindingSet compares frozensets (`{"ctrl","shift","alt"}`); window.py tests raw pyglet bitmasks inline at 6 distinct sites; `input_map.py` stores raw pyglet modifier ints. Three representations of the same concept.
- *Is context/family centralized?* — Half. `determine_input_context()` maps `focused_family=="topology"` → TOPOLOGY_CONTEXT (input_adapter.py:141–156), but window.py separately tests `focused_family == "articulation"` (window.py:777) and the Tab-cycling logic manages `focused_family` (window.py:1279–1284). Context influence is also *asymmetric*: it can only route a command to the handler; if the handler declines, the fall-through ignores context entirely (the C→load_cube failure).
- *Playground vs Production ownership model?* — Deliberately divergent (AD-011), which was tenable when Playground was ad-hoc. WP-AP then grafted the production resolver onto the divergent behavior layer *without* migrating ownership — the current worst-of-both state.
- *Hidden fallbacks?* — Yes, and they are load-bearing: the entire fall-through elif chain is a hidden fallback that overrides the BindingSet wherever the whitelist declines.

---

## 4. Sources of Truth

| # | Source | Domain | Classification |
|---|---|---|---|
| 1 | `src/mirai/interaction/bindings.py::build_default_bindings` | key→command | **Canonical for resolution** — but contradicted by #4–#7 and *shadowed at runtime* by #2/#3 for non-whitelisted commands |
| 2 | `playground/window.py` (29 elif branches, tweak key-maps, axis keys, inline modifiers) | de-facto key→behavior for most keys | **Dangerous** — invisible to anyone editing #1; contains its own docstring claiming X/R/S (stale) |
| 3 | `playground/input_map.py` | D/Z/V/LMB/modifiers | **Transitional** — pre-WP-AP; now overlaps #1 (D vs O, Z vs Shift+D, V conflict) |
| 4 | `INPUT_WIRING_MAP.md` | Artist's binding decision (X/R/S→W/E) | **Ambiguous authority** — dated 2026-09-18, marked "Artist Input Decision", but already contradicted by the shipped code (Q/W/E) |
| 5 | `WP-AP_INPUT_WIRING_REPORT.md` | "what is wired to what" | **Legacy/oversold** — documents X/R/S, K/J/I/Shift+L/Shift+R/G as production-wired; none of that matches current code; "Complete" status contradicted by 3 fix commits |
| 6 | `playground/MANUAL.md` + `playground/README.md` + window.py module docstring | user-facing keys | **Stale** — X/R/S transform, V=vertices, Shift+L/Shift+R framing, Q=quit |
| 7 | Tests (`tests/test_input_binding.py`, `playground/tests/test_input_wiring.py`, `test_input_wiring_whitelist.py`) | current keys | Now aligned with Q/W/E — but only test resolution/mocks, not end-to-end behavior |

**Verdict:** the same concept (key binding) has **four code locations and at least three documentation locations**. #1 vs #2 is a *dangerous* duplicate (silently diverging behavior). #4 vs #1 is an *ambiguous-authority* duplicate (the Artist's stated desired keys differ from shipped keys). #3 is transitional residue. #5 is a superseded status report sitting at repo root pretending to be current.

Additional, smaller duplicates of the same kind: tool activation models are defined in variant files but *interpreted* in two places; the ESC cascade exists in window.py and (dead) in command_handler; split-edge scope logic exists in both layers; `create_tool_for_type` (playground/transformer.py) and `tool_for_command` (src routing.py) are two parallel command→tool factories using two different vocabularies (`'move'` vs `cmd.MOVE`).

---

## 5. Ownership & Boundaries

**The one-obvious-place test fails for input.** Concretely, "change the Rotate key" has three different correct answers depending on state an agent cannot know without reading everything:

- For a **whitelisted** command with no tweak variant active: `bindings.py` alone suffices (handler follows resolution).
- For **Tweak V1/V3**: `bindings.py` **and** window.py's tweak key-map — but the handler preempts anyway (bug), so today there is *no* correct single place.
- For a **non-whitelisted** behavior (extrude, loop select, articulation): `window.py` only — editing `bindings.py` either misdocuments it or silently creates a dead binding (the C case).

**Boundary violations (OBSERVED):**

- `PlaygroundCommandHandler` (command layer) directly manipulates `window._transform_key_down`, `_transform_mode_on`, `_transform_started`, `_extrude_tool`, `_loop_slide_tool`, `_articulation_state`, `_tweak_*`, `_hud`, `_rebuild_vbo()`, `_update_hud()` — i.e. the command layer *is a second implementation of the window's interaction state machines*, coupled via private attributes in both directions (window calls handler; handler mutates window internals).
- `command_handler.py` duplicates window's hold/press_mode/press_drag_click logic nearly line-for-line (`command_handler.py:152–190` vs `window.py:1417–1441`) — including the divergence that causes the token mismatch.
- `window.py` is a god-module: input dispatch, 5 state machines, VBO building/patching, GL shaders, HUD, camera glue, scene loading, experiment slot registration (1587 lines / 80 KB; the *next largest* playground file is 23 KB).

**What is cleanly owned:** selection behavior (`selector.py`, parameterized by `input_map` and `SelectMode`); the variant/slot system (`slot.py`, `app.py`); the production interaction modules; the pyglet→Input conversion (`input_adapter.py`).

---

## 6. Coupling / Dependency Hotspots

1. **Change-coupling cluster (OBSERVED via commit `86c8d9c`):** one rebinding touched 7 files across 3 layers — `bindings.py`, `window.py`, `command_handler.py`, `tests/test_application.py`, `tests/test_input_binding.py`, `tests/test_tool_integration.py`, `playground/tests/test_input_wiring.py` — and *still* missed MANUAL.md, README.md, INPUT_WIRING_MAP.md, window docstring, and the tweak semantics interplay. This is the single strongest quantitative indicator of harmful coupling: **the change surface of "one key" is ≥ 7 files and no list of them exists anywhere.**
2. **Bidirectional window ↔ handler reach-in** (private-attribute friendship) — any state-machine change in window.py silently invalidates handler assumptions and vice versa. This is exactly the §1→§2-§4 regression mechanism.
3. **Duplicated orchestration:** ESC cascade ×2, transform activation ×2, split-edge ×2, display cycling ×2 (D-slot vs DisplayState fallback in *both* layers).
4. **No circular imports found** between src packages (the `mirai ↔ viewport` boundary is respected; `core` depends on nothing UI-ish). Production dependency discipline is genuinely good.
5. `window.py` fan-out: imports ~20 modules and is imported by run.py, tests, diag scripts — high fan-in/out, but the problem is not size per se; it is that input dispatch and state machines share a file with rendering.

---

## 7. Legacy / Migration Residue

- **Dead handler methods** in `command_handler.py`: `_topology_connect`, `_topology_loop_select`, `_topology_ring_select`, `_topology_loop_insert`, `_topology_loop_slide`, `_topology_extrude`, `_topology_collapse`, `_articulation_restore`, `_handle_cancel` — ~250 lines unreachable via dispatch (not whitelisted), duplicating window.py logic that *is* reachable. They remain architecturally relevant-looking (tests import `_handle_topology_commands` with mocks, giving the illusion of coverage). *(OBSERVED)*
- **Dead window branches:** Ctrl+Z/Ctrl+Y elifs (`window.py:1174–1186`); the transform half of the Q/W/E block for non-tweak variants; possibly the whole `_key_map` at 1404. *(OBSERVED)*
- **The whitelist itself is migration residue promoted to architecture:** a runtime shim encoding "which commands have been migrated off the hardcoded path," undocumented in any architecture doc, encoded in a comment block. *(OBSERVED)*
- **Superseded generation markers:** `playground/experiments/articulation/_old_/` (entire old window), `tests/phase_d.patch`, `tests/full_hardening_d_e.patch`, `run_output.log`, `playground/_diag_screenshot.py`, `experiments/_mt.txt`. *(OBSERVED, low severity)*
- **Two generations of demonstrator key semantics:** `experiments/mirai_bastel_viewport_V02/demonstrator.py` (M=move-vertex, T=topology, K=color, R=reset) — legitimately an experiment, but it is a third key vocabulary in the repo an agent can stumble into. *(OBSERVED, intentional)*
- **Stale architecture decision:** AD-011 consequence 2 states the production Input→Command→Tool contract is "declared-but-unhandled by any running application" — superseded by WP-AP without an AD update. *(DOCUMENTED vs OBSERVED)*
- Root README still points to `experiments/mirai_bastel_viewport_V1/`, which was removed in commit `8ef4def`. *(OBSERVED)*
- `docs/WP-04_*` — 25+ gate reports at `docs/` top level (not archived) — high noise floor for agents doing M1 history checks. *(OBSERVED)*

**Multiple generations of the same architecture?** For input specifically: yes — Generation 1 (window.py elif chain, pre-WP-AP), Generation 2 (BindingSet + handler with whitelist), coexisting, with Generation 2 only partially covering Generation 1 and no retirement plan for Generation 1 (the WP-AP report's own "Next Steps #5: gradually remove hardcoded handlers … safe to defer" — DOCUMENTED, not executed).

---

## 8. AI-Agent Change-Cost Analysis

Estimated context cost for representative small tasks (files that must be *understood*, not just edited):

| Task | Files to understand | Correct location obvious? | Trap |
|---|---|---|---|
| Change one key binding (whitelisted cmd) | bindings.py, command_handler.py (whitelist), window.py (check for parallel branch + tweak maps), 2 test files, 4 docs | **No** | Editing only bindings.py passes tests but leaves window branch/docstring stale; editing window.py instead silently no-ops |
| Change one key binding (non-whitelisted) | window.py + decide whether bindings.py should change at all + docs | **No** | Adding a BindingSet entry creates a binding that resolves then falls through — misleading |
| Add one command | commands.py, bindings.py, command_handler (whitelist + handler *or* window elif) + decision "does it need a state machine?" requiring reading all 5 state machines | **No** | The whitelist decision is the hidden hard part |
| Change selection behavior | selector.py + input_map.py + window call sites | Mostly yes | Modifier semantics split bitmask/frozenset |
| Add one topology operation | core operations + window.py branch + (handler duplicate?) + docs | Partially | Two plausible homes (handler/window) with a whitelist gate |
| **Modify Tweak or transform activation** | window.py state machines + command_handler duplicates + 3 variant files + transformer.py + 2 test files | **No** | Two vocabularies for tool tokens; two interpretations of `activation` |

**Why Claude Code specifically fails here (evidence-based):**

1. **The most authoritative-looking file is the wrong first edit.** `src/mirai/interaction/bindings.py` is production, tested, documented as "exchangeable mapping" — an agent correctly gravitates there, changes keys, runs the (passing) tests, and ships. Runtime behavior for half the keys lives elsewhere. Three of the four recent commits show exactly this signature.
2. **Fall-through makes edits unverifiable by tests.** A binding that resolves to a non-whitelisted command silently does nothing; a whitelisted command silently preempts a state machine. Both failure modes are invisible to the mock-based wiring tests (`test_input_wiring_whitelist.py` mocks every handler; `test_input_wiring.py` never touches window state machines). "All 739 tests pass" was reported in every fix commit — while reintroducing regressions.
3. **Docs actively lie.** An agent that reads MANUAL.md/README/docstring/INPUT_WIRING_MAP/WP-AP report (per AGENTS.md §1, which *requires* reading the local docs) receives 4 contradictory key maps. Whichever it trusts, it will be wrong somewhere.
4. **Magic 1-char tokens across module boundaries** (`'m'` vs `'q'`, `tool_type[0]`) fail silently at runtime with zero static or test detection.
5. **Commit-message provenance is misleading:** "WP-AP-INPUT-FIX-01 Complete" (4d7fdb7) followed by "Fixes three categories of issues introduced in commit 4d7fdb7" (86c8d9c) — an agent doing M1 history awareness gets *confident but wrong* history.

---

## 9. Documentation vs Implementation

| Document | Claim | Reality | Verdict |
|---|---|---|---|
| `INPUT_COMMAND_TOOL_CONTRACT.md` | Input→Context→Binding→Command→Tool, rebinding touches only mapping layer | True in `src/`; **false in Playground** (binding changes touch behavior layers) | Accurate as contract; violated by Playground structure |
| `INPUT_WIRING_MAP.md` (2026-09-18) | Desired: Move=W, Rotate=E; "do not change Interaction Behavior" | Shipped: Move=Q, Rotate=W, Scale=E; interaction behavior *was* changed twice | **Contradicts implementation; authority ambiguous** — M4 question for Artist |
| `WP-AP_INPUT_WIRING_REPORT.md` | "Complete", "single BindingSet used, no parallel system", K/J/I/Shift+L/Shift+R/G wired via production commands | Topology commands mostly *not* routed (whitelist), Shift+L/Shift+R still window-elif, G binding absent; 3 fix commits followed | **Oversold status report, now stale** |
| `playground/MANUAL.md`, `README.md`, window.py docstring | X/R/S transform, V=vertices, Q=quit | Q/W/E transform, V=mode (V-vertices overridden), Q=Move | **Stale** |
| `AD-011` | production contract unused by any running app | Playground handler now uses it (partially) | **Superseded, not updated** |
| `SOURCE_ARCHITECTURE.md` | responsibility boundaries, no production window | Matches | Healthy |
| Root `README.md` | Viewport V1 experiment exists under experiments/ | Removed in `8ef4def` | Stale |
| `AGENTS.md` / dev system | doc hierarchy, single source of truth per fact | Violated for input by the multiplicity above | The system is fine; this area breaks it |

**Terminology drift:** "binding" means (a) key→command in src, (b) pyglet int field in input_map, (c) hardcoded elif in window-speak. "Command" means a string constant in src but colloquially "a key press" in playground docs. "Variant" means experiment variant everywhere except command_handler where "variant-aware" means activation-model-aware.

---

## 10. Evidence from Recent Input-Wiring Failures

Git sequence (all within ~3 days):

```text
54e9840  WP-AP: Input Wiring — "Complete", 688 tests pass
aac474e  FIX-01 §1: whitelist fix — MOVE/ROTATE/SCALE removed as "unsafe
         (interfere with Tweak V1/V3 arming)"
4d7fdb7  FIX-01 "Complete": axis wiring + rebinding X/W/E→(first attempt) +
         MOVE/ROTATE/SCALE re-enabled ("safe after rebinding")
86c8d9c  FIX-01 §2–§4: "Fixes three categories of issues introduced in 4d7fdb7"
         — X double-bound, W/Shift+D conflict, M/Shift+M lost, E mode conflict
```

Classification against the audit's categories — **F, combination, in this order of contribution:**

- **D (competing implementations) — primary.** window.py elif chain and command_handler both implement transform activation; the whitelist decides which runs *per command*, and §1's fix (de-whitelist) was undone by §2–§4 (re-whitelist) because each commit optimized one layer against the other. The token mismatch (`'m'/'r'/'s'` vs `'q'/'w'/'e'`) is a direct artifact of having two writers to one state machine.
- **C (ambiguous correct location) — primary.** There is no place where "the Rotate key" is defined once. The correct edit set depends on whitelist membership, active tweak variant, and focused family — none visible from any single file.
- **E (migration/legacy complexity) — significant.** The whitelist, the dead handler methods, the dead window branches, and the stale WP-AP report are all un-retired Generation-1 artifacts that misinform every subsequent edit.
- **B (agent misunderstanding despite clear architecture)** — *not* supported: the architecture is not clear on this topic; the agent behavior (edit bindings.py + tests, trust green suite) is locally rational.
- **A (isolated mistakes)** — present but secondary (Shift+D/W collision, M/Shift+M loss); these were *caught* and fixed, which shows the agent's iteration loop works when the problem is a single contradiction.

**Predicted live defects from current code (static trace, high confidence, flagged for live verification — deliberately NOT fixed, per audit constraints):**

1. Press-Mode / Press-Drag-Click: second press commits only if `window._transform_key_down == 'q'/'w'/'e'` (window.py:1568), but the handler set it to `'m'/'r'/'s'` (command_handler.py:168/176/184) → commit/exit never fires for handler-initiated press-mode; state clears only via ESC path.
2. Tweak V1/V3 arming on Q/W/E is preempted by the whitelisted MOVE/ROTATE/SCALE handler (regression of §1).
3. Topology focus + `C` → `load_cube()` instead of Connect Edges (scene replacement).
4. Topology focus + bare `L` / bare `R` → no-op / Extrude respectively, despite documented topology bindings.
5. `V` no longer toggles vertex display (overridden by SET_VERTEX_MODE).

---

## 11. Findings by Severity

**S1 — Critical (behavior-visible now)**
- F1: Dual-dispatch token mismatch `'m'/'r'/'s'` vs `'q'/'w'/'e'` across handler→window boundary. `command_handler.py:152–190`, `window.py:1536–1584`. OBSERVED. Accidental (artifact of duplicate implementation).
- F2: Tweak V1/V3 arming preempted by whitelisted transform commands — the §1 regression re-introduced. `window.py:1140–1147` + `window.py:1403` + whitelist `command_handler.py:62–68`. OBSERVED (static). Accidental.
- F3: Topology-context `C` falls through to `load_cube()`. `bindings.py:91`, `command_handler.py:62–68`, `window.py:1149`. OBSERVED (static). Accidental — hidden fallback + missing whitelist entry.
- F4: Four contradictory binding sources (bindings.py vs window.py vs docs vs WP-AP report) + Artist decision doc (INPUT_WIRING_MAP: Move=W, Rotate=E) not matching shipped keys (Q/W/E). OBSERVED. Mix of accidental drift and an unresolved M4 question.

**S2 — High (structure that generates the next S1)**
- F5: window.py god-module owning dispatch + 5 state machines + rendering + HUD. OBSERVED. Intentional growth, now accidental harm.
- F6: command_handler ↔ window private-attribute reach-in + duplicated activation logic. OBSERVED. Accidental (WP-AP constraint "do not redesign").
- F7: Whitelist shim as implicit architecture; not in any contract doc; mock-tested only. OBSERVED. Transitional, never closed out.
- F8: No end-to-end input tests; wiring tests are resolution- or mock-level, so layer-interaction regressions pass CI. OBSERVED. Gap.

**S3 — Medium**
- F9: Dead code mass in command_handler (9 methods) and window (Ctrl+Z/Y branches, transform half of Q/W/E block). OBSERVED. Legacy residue.
- F10: `input_map.py` vs BindingSet overlap (D/Z/V/O/Shift+D) with a live V conflict. OBSERVED. Transitional.
- F11: Stale user docs (MANUAL, README, docstrings) and stale root README path. OBSERVED. Accidental.
- F12: Inline bitmask modifiers (6 sites) vs BindingSet frozensets. OBSERVED. Accidental.

**S4 — Low**
- F13: `_old_/` dirs, `.patch` files in tests/, `run_output.log`, `_diag_screenshot.py`, `experiments/_mt.txt`. OBSERVED. Housekeeping.
- F14: 25+ WP-04 gate docs at docs/ top level (noise for M1 checks). OBSERVED. Housekeeping.
- F15: AD-011 consequence 2 and root README experiment path outdated. OBSERVED. Doc maintenance.

---

## 12. What Appears Healthy

- **`src/core`** — frozen, invariant-tested, zero UI coupling (OBSERVED).
- **`src/mirai/interaction` core design** — `Input`/`BindingSet`/`commands`/`routing`/keymap schema (Gate 6) is small, validated, well-tested, and genuinely rebinding-safe *within its own layer* (OBSERVED). Do not touch it.
- **`input_adapter.py`** — clean, single-purpose pyglet→Input conversion with tests (OBSERVED).
- **`selector.py` + `slot.py` + experiment-variant pattern** — the variant-as-data idea works; `activation` as a variant attribute is a good idea undermined only by double interpretation (OBSERVED).
- **Decision discipline (ADs)** — AD-006/010/011 show honest, append-only decision hygiene, including candid "Execution Update" records (DOCUMENTED).
- **Test culture at large** — 739 tests, real invariants in core/viewport/transform tests (OBSERVED). The gap is specific: layer-interaction input tests.
- **`docs/architecture/INPUT_COMMAND_TOOL_CONTRACT.md`** — still the correct contract; the Playground violates it, not the other way around (DOCUMENTED).

## 13. What Appears Structurally Risky

- `playground/window.py` (everything about it that concerns input dispatch and state machines — **not** its rendering).
- The handler↔window private-attribute interface (the *implicit contract* is the risk, more than either file alone).
- The whitelist as the sole merge point of two generations.
- The input-documentation set (4 contradicting sources; no canonical "current bindings" artifact).
- The absence of any test that drives a key press through **both** layers to a committed operation.

## 14. Refactoring Candidates

(Where a refactoring phase is justified — targeted, not a plan:)

1. **Single dispatch owner for Playground keys** — make the fall-through elif chain either fully migrate behind the command layer or explicitly declare window.py the only owner and demote BindingSet to documentation. The current half-merge is the root cause of F1–F3. Evidence: §10 defect list.
2. **Unify the tool-token vocabulary** — replace `tool_type[0]` magic chars with the `cmd.MOVE/ROTATE/SCALE` constants (or full names) at every writer/reader. Eliminates the silent-rename failure class.
3. **Delete or activate the dead handler methods and window branches** after (1) decides ownership — each is a false lead for the next agent.
4. **One generated canonical bindings map** (doc or test) derived from `build_default_bindings()` + window inventory, referenced by MANUAL/README — kills the doc-contradiction class (F4/F11).
5. **End-to-end input tests**: simulate pyglet events through `on_key_press`/`on_key_release` against a real window-shaped fixture, asserting state-machine outcomes (would have caught F1–F3).
6. **Extract state machines** (`_transform_*`, `_tweak_*`, articulation, extrude, loop-slide) from window.py into small owner objects, so "modify one interaction" stops requiring 1,587 lines of context.
7. **Close out `input_map.py` vs BindingSet overlap** once (1) settles which layer owns display/selection keys.

## 15. Things That Should NOT Be Refactored

- **`src/core/**`** — frozen by decision (CORE_V1_FREEZE); untouched by this entire problem. Any refactor here is out of scope by the project's own rules.
- **`src/mirai/interaction/input.py` / keymap schema / Gate 6** — validated, tested, contract-backed; the failures all occur *downstream* of it. Rewriting it would destroy the one clean layer.
- **The Experiment/Slot/variant system and the variant files** — working research infrastructure; the fix is single interpretation of `activation`, not redesign.
- **`experiments/**`** — including V02's different key semantics; that is deliberate research variance (AGENTS.md §7 scope discipline).
- **AD-006…AD-012 and archived reports** — append-only decision memory; supersede with new ADs, never rewrite.
- **`selector.py` selection behavior** — recently validated, parameterized cleanly; not implicated in the failures.
- **The production `Application.dispatch_command`/ToolManager path** — small and correct; the Playground should converge toward it, not the reverse.

## 16. Recommended Next Investigation

1. **Live-verify the five predicted defects (§10)** in a real window session — one playtest pass covering: Press-Mode second press, Tweak V1 with Q, topology-focus `C`, topology-focus bare `L`/`R`, and `V`. If confirmed, that is the concrete case file for the refactoring phase.
2. **Resolve the M4 question first (Artist, cheap):** do the shipped Q/W/E bindings reflect your intent, or was INPUT_WIRING_MAP.md (Move=W, Rotate=E) the intent? Every further input change compounds on this unresolved Product Truth.
3. **Revisit AD-011 explicitly:** the dual-dispatch architecture exists because "is the Playground the application?" was deliberately left open. The WP-AP wiring silently made a de-facto choice (production resolver + playground behavior). That choice should be named, confirmed or reversed, and written down — it is the decision that unlocks refactoring candidate #1.
4. **Test-inventory gap analysis:** enumerate which input behaviors currently have zero end-to-end coverage; this defines the safety net the refactoring must build before moving anything.
5. **Archive pass (cheap, high agent-ergonomics yield):** move WP-04 gate reports and the superseded WP-AP report into `docs/archive/`, and add a single pointer document "Current input behavior lives in X" — this directly attacks the false-lead problem the recent Claude Code sessions kept hitting.

---

**Bottom line:** The production architecture is healthy and should not be touched. The harm is localized to the Playground input merge created by WP-AP, where two generations of dispatch coexist behind an undocumented whitelist, ownership of a key depends on runtime state, and four documents contradict the code. The recent Claude Code failures map directly onto that structure (categories D + C + E, with A/B as amplifiers) — and at least three of the failure signatures the Artist has been experiencing are still statically present in the code today. A bounded refactoring phase targeting the Playground dispatch boundary is justified; a broader cleanup is not.