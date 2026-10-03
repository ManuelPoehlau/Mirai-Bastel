# Independent Review — AD-013 Addendum "H2" (revised, command gate G)

> **Reviewer:** Claude (fresh session, no prior chat or plan context)
> **Review ID:** CLAUDE-002
> **Target path:** `docs/archive/symmetry_lab/reviews/AD-013_H2_ADDENDUM_REVIEW_CLAUDE_002.md`
> **Repository state reviewed:** `claude/intelligent-ride-irx6ku` @ `366042f` (2026-10-03)
> **Subject:** `docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md`, addendum dated 2026-10-03, revised (lines 425–733)
> **Answers:** [CLAUDE-001](AD-013_H2_ADDENDUM_REVIEW_CLAUDE_001.md) (F1–F15)
> **Type / Mode:** Type B (review only) · Discovery · no source, plan or addendum edited
> **Status:** Archived second independent review — preserved verbatim
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions. Answers to the findings belong in the addendum's "Review" section.

---

## What was read, what was run

Read: the revised addendum and the rest of AD-013, CLAUDE-001 (whole file),
`INPUT_COMMAND_TOOL_CONTRACT.md` (§3, §5), AD-015 (Costs, V1/V3 back-off), AD-016 (grep only),
`src/mirai/application.py` (input path, `_cancel`, Undo/Redo and the selection mirror, hover, Knife
key gate, `dispatch_command`, `_display_command`), `src/mirai/interaction/input.py` (`BindingSet`,
`_VALID_CONTEXTS`), `bindings.py`, `pointer.py`, `src/main.py` (whole file).
**Not read:** `WP-SYM-LAB-03_REBASE_PLAN.md` (as instructed), AD-SYM-01/02, any Lab code
(`experiments/symmetry_lab/`). Every claim that rests on those is marked **UNVERIFIED**.

Run:

- Baseline at `366042f`: `PYTHONPATH=. pytest tests/test_application*.py` → **412 passed**, headless, ~7 s
  (same count as CLAUDE-001 at `bafae30`).
- G does not exist in code, so the probes **emulate** it on an `Application` instance at the exact
  places the Decision names: the key check after the Knife routing and the binding lookup
  (`application.py:997-999`), the click check in `_execute_click` (`:1440`), and the hover flag in
  `_update_hover` (`:1388`). A small `Lab` class emulates the window step (D1) and the Lab-state table.
  "VERIFIED (probe)" below means verified against this emulation on top of the real `Application`. It
  does not cover the future real implementation.
- Probes (all passed, then deleted; code in the appendix):
  - **D1a**: 40 seeds × 400 random events under the open preview → `interaction_owner` stays `None` throughout.
  - **D1b**: 40 seeds × 400 random events on a plain `Application` → Cancel changes nothing whenever the owner is `None`.
  - **F1-under-G**, the **D1 negative path**, and **Lab keys during Knife**.
  - **T-R5c pass-through run** with two allow-list variants, plus a negative control.
  - **N2**: a breaking sequence for D1.
- pyglet is not installed in this container, and the repository pins no pyglet version (no
  requirements/pyproject entry found). F11's pyglet claims are therefore **UNVERIFIED** here; they
  rest on CLAUDE-001.

---

## Verdict

**ACCEPT WITH CHANGES. No blockers.** Three SHOULD findings (N1–N3) must be answered before DECIDED.

The revision is a faithful adoption of G. Both CLAUDE-001 blockers are resolved in substance. F1 is
gone by construction: the probe shows Ctrl+Z and W refused mid-orbit under the preview. F2 has a named
entry and tests.

**D1 is sound**, and the probes confirm both of its premises: the owner stays `None` while the preview
is open, and Application's Cancel is a no-op when idle. One premise is still implicit in the text,
though: the preview's gate row must stay installed for the whole preview. The addendum says the gate
is "replaced as a whole on every Lab state change". It also leaves open what Shift+S and Shift+B do
while the preview is open. A Lab that executes them there breaks D1. Probe N2 shows the result: under
the open preview, Esc closes the preview and leaves an armed Move running (N2).

The second gap is in `record_mesh_change` as specified. It cannot be called without breaking H2-R4,
because `selection_before` has a private format and R4 lists the mesh as read-only. D3 also fires only
after the Lab has already mutated the mesh. So the F2 and F5 answers claim more than the specified
API delivers (N1).

---

## Q1 — Are D1–D3 sound?

### D1 — Esc closes the preview at window level

**Sound, under one implicit premise (N2).**

| Claim in D1 | Check | Result |
|---|---|---|
| G as proposed cannot close the preview with Esc | `Cancel` is GLOBAL (`bindings.py:103`). It is not in the preview allow-list, so the gate would refuse it before `_cancel` | VERIFIED (code) |
| Esc cannot get a Lab-context entry | It resolves in GLOBAL, and the H2-R1 start-up assert requires the three Lab inputs to resolve to `None` there. A permanent Lab Esc would shadow `_cancel` for armed transforms | VERIFIED (code, `input.py:212-219` context priority) |
| `interaction_owner` is `None` the whole time the preview is open | Transforms arm only through `key_press` → `_transform_arm` (`:1001`, `:1073-1074`). A Knife session starts only through `CONNECT` → `_connect_command` → `_knife_begin` (`:1019`, `:546`). Both are refused by the preview allow-list. Display commands (`_display_command`, `:925`) start nothing. `key_release` is a no-op when nothing is armed (`:1036`). Pointer paths start neither interaction outside a Knife session | **VERIFIED (code + probe D1a)**: 40 seeds × 400 random events under the open preview (all bound keys incl. KNIFE/TOPOLOGY/Lab keys, presses/releases in random order, clicks with every modifier set, drags of 1–30 px, wheel, motion, leave; half the seeds start with a non-empty selection and history). After every event: owner `None`, no active tool, hover `None`, and selection, history, mirror stacks, mesh and constraint unchanged. Negative control: with the gate removed, the owner leaves `None` in 39/40 seeds |
| Application's Cancel is a no-op when idle | `_cancel` returns `False` immediately when `_transform_key is None` (`:1148-1149`); the Knife's Esc goes through `_knife_key`, not `_cancel` (`:997-998`, `:661-662`) | **VERIFIED (code + probe D1b)**: 40 seeds × 400 random events on a plain `Application`, 11 059 idle states reached (also mid-orbit, with sticky constraints, after Knife sessions and committed transforms). In each, `key_press(Esc)` returns `False` and a 19-field state snapshot (selection, hover, history and redo, mesh state, constraint, status text and serial, active tool, display, mirror stacks) is unchanged. The fuzz also confirms `_transform_key is None ⇔ _transform_command is None` in every reached state, so `transform_command` is a faithful owner predicate for `_cancel` |
| Meaning still comes from the one `BindingSet` (I4) | The Lab resolves `command_for(input, "symmetry_lab")`. For any non-Lab input this equals the GLOBAL resolution, because the Lab context holds only the three asserted-free entries. A user rebinding of Cancel moves the preview's cancel with it | VERIFIED (code) |
| Esc mid-orbit | It closes the preview, and the orbit keeps running | VERIFIED (probe F1-under-G) |
| "only while the preview is open" | Without a preview, Esc goes through the Lab step to `Application` and disarms an armed Move ("Move disarmed"). During a Knife session it ends the session | VERIFIED (probes D1-negative, Lab-keys-during-Knife). **No required test covers this path (N3)** |

**The implicit premise.** All of the above holds only while the gate carries the preview row. The
addendum does not state that the preview row dominates every other Lab state. N2 explains why that
matters.

### D2 — the start-up assert also covers KNIFE

**Sound, and strictly tighter.** `command_for(inp, KNIFE_CONTEXT)` falls back to GLOBAL
(`input.py:212`), so a single KNIFE lookup covers both layers.

During a Knife session the Lab step resolves Lab keys before `_knife_key` does. It refuses them
visibly (owner `"knife"`), so they never reach the Knife. The probe confirmed this: Shift+S during
Knife is refused, `knife_active` stays `True`, `status_serial` + 1, and the following Esc ends the
session. Without D2, a future KNIFE binding on M, Shift+S or Shift+B would be shadowed silently.
D2 makes that a start-up failure. All three inputs are free in GLOBAL and KNIFE today (VERIFIED,
`bindings.py:93-160`).

### D3 — `record_mesh_change` raises while an owner is set

**Sound in intent, but it fires too late.** The signature `record_mesh_change(command,
selection_before, moved=None)` implies that the Lab has already mutated the mesh and built a
`MeshStateCommand` before the call. When the guard raises, the mesh is already changed with no history
entry: a corrupt state, not just a loud failure. See N1 for the fix.

---

## Q2 — Do H2-R1..R6 uphold I1, I3, I4, I6?

| Invariant | Rule(s) | Assessment |
|---|---|---|
| **I1** one capability home | R4, R5 | **Upheld for app input.** The Lab calls only `key_press`/`pointer_*`, so gestures, arming, constraints, hover, picking and undo are `Application`'s. **Weak spot (N1):** Lab mesh changes are the one place where the Lab must work next to `Application`'s bookkeeping, and the specified entry cannot be used without a private format or a mesh write that R4 does not permit |
| **I3** one authority owns start and end | R2, D1, D3 | **Upheld, given N2.** `Application` starts and ends transform and Knife. The Lab starts (M) and ends (M / Esc / window close) the preview. Owner predicate verified (above). The two never overlap *only* while the preview row holds. If Shift+S or Shift+B are allowed to rewrite the gate during the preview, `Application` can arm under the open preview, and D1 then takes Esc away from the armed transform. That is exactly the "END → authority B" split the § Activation and Termination rule forbids (N2, VERIFIED by probe) |
| **I4** one binding authority | R1, D1, D2 | **Upheld.** The Lab reads the one `BindingSet`, and the start-up assert guarantees that the Lab and `Application` resolutions agree for every non-Lab input (Q1). Precedence between the gate and `Application`'s own gates is `Application`'s branch order. VERIFIED: the T-R5c emulation leaves all 412 `Application` tests unchanged. R4(a) allows `set_default` "for its own context" only; no required test checks that GLOBAL/KNIFE stay unchanged by Lab start-up (N7) |
| **I6** overrides visible | R1, R3 | **Upheld.** The three entries and the gate table are printed (T-R1d), and every refusal posts a status. Minor: D1's re-targeting of Cancel during the preview is not part of the listing (N8) |

R5 (Production unchanged) is sound and well tested (Q5). R6 is correctly stated as governance.

---

## Q3 — Does the Review table answer F1–F15?

| Finding | Answer in the table | Assessment |
|---|---|---|
| F1 | Fixed (gate after resolution, camera gestures own no keys) | **Fixed.** VERIFIED (probe F1-under-G): the CLAUDE-001 P1 sequence under the preview → Ctrl+Z `False`, history unchanged, `status_serial` + 1; W `False`, `transform_command is None` |
| F2 | Fixed (`record_mesh_change`, R4 forbids `history.push`, D3) | **Only partly fixed — the answer claims more than the API delivers (N1).** The mirror/pick-cache/viewport duties are named correctly. But `selection_before` must come from `_selection_snapshot` (private, `:1220`), and `_restore_selection` unpacks it blindly (`:1233`). R4(a) lists `scene`/mesh as read-only, yet the Lab must mutate it to have a change to record. D3 raises after the mutation |
| F3 | Fixed (`hover_suspended` in `_update_hover`) | **Fixed.** VERIFIED (code): every non-`None` write of `selection.hovered` goes through `_update_hover` (`:1392`). All other writes set `None` (`:479`, `:646`, `:1080`, `:1272-1276`, `:1386`, `:1437`). VERIFIED (probe D1a): hover stays `None` through motion, wheel and display changes under the preview |
| F4 | Fixed (`interaction_owner`) | **Fixed.** The predicate matches every `Application` key gate (`:997`, `:1011`, `:1017`, `:1023` ⊂ armed). VERIFIED (probe D1b): `_transform_key` and `_transform_command` are always both set or both unset |
| F5 | Fixed (allow-list) | **Fixed for dispatch/select/history.** Leaves the mesh-mutation hole of N1 |
| F6 | Fixed (three key entries, pointer overrides impossible) | **Fixed in text.** "Old `run.py` unchanged until Slice 5" and "MMB pan loss recorded in plan §4.3" are **UNVERIFIED** (plan and Lab not read) |
| F7 | Fixed (preview allow-list) | **Fixed for app commands only.** CLAUDE-001 F7 asked for an allow-list of "camera navigation, display commands, and the preview's own keys (M, Esc). Everything else that resolves to a command is refused". The Lab's own Shift+S and Shift+B also resolve to commands but bypass the gate (window step), and nothing says they are refused during the preview. Need 3 explicitly lists Shift+S as ignored (N2) |
| F8 | Fixed (start-up listing) | **Fixed.** Test T-R1d |
| F9 | Adopted | **Adopted.** "F is not used because …" and § Limits of G are present and accurate |
| F10 | Fixed (H4 precondition, Slice 1) | **Fixed** in the addendum; the plan move is **UNVERIFIED** (plan not read) |
| F11 | Fixed (cost line replaced) | **Fixed in text**; the pyglet facts are **UNVERIFIED** in this review (pyglet not installed). "No pin" VERIFIED |
| F12 | Fixed in text, not in code (pre-existing) | **Adequate answer** (not-fixed with reason). `on_deactivate` resets only Shift — VERIFIED (`main.py:180-185`) |
| F13 | Fixed (H2-R3 return contract) | **Fixed, with one gap:** the return value of the window step when it interprets Cancel (D1) is not stated (N4) |
| F14 | Fixed (R6 as governance) | **Fixed** |
| F15 | Fixed (start-up assert + D2) | **Fixed.** `"symmetry_lab"` is still not in `_VALID_CONTEXTS` (`input.py:60`), so `keymap.json` cannot address the Lab context. The assert is the only guard, and that is enough |

Answers that **only claim a fix**: **F2** (N1) and, for the Lab-key half, **F7** (N2). Everything
else is either actually fixed in the text or not fixed with a stated reason.

---

## Q4 — Are the required tests sufficient and feasible headless?

**Feasible: yes.** The emulation already runs the core of T-R2c, T-R2e, T-H's mechanism and T-R5c
headless through the public entry points in under 2 s. T-R5c in particular: re-running all 15
`tests/test_application_*.py` files with an inert-but-active gate gives **412 passed** for the
addendum's allow-list ("every command the default bindings can resolve") and also for "every constant
in `mirai.interaction.commands`". Negative control: an empty allow-list makes 303 fail, which proves
the gate was active. VERIFIED (probe).

Feasibility needs one thing the addendum does not state: the Lab's window step must be a pyglet-free
function taking an `Input`, as `main.py`'s handlers convert first and then call `app.key_press`
(`main.py:163-170`). Otherwise T-R1b..T-R2e can test only the `Application` half (N4).

**Sufficient: not yet.**

- **Missing (N3):** the D1 negative path. With no preview, Esc through the Lab step must still disarm
  an armed transform and end a Knife session. This is the condition D1 itself names ("only while the
  preview is open"), and no test pins it.
- **Missing (N2/N3):** Lab commands during the preview. T-R2e's list omits Shift+S and Shift+B. Add
  them as refused, with the gate unchanged and the owner `None`.
- **Recommended:** adopt the seeded fuzz D1a as a companion to T-R2e. It found nothing at `366042f`,
  but it is the only test that checks the D1 premise over many sequences rather than one.
- **Precision fixes (N5, N6, N7):**
  - T-R2b must run with symmetry **off**: the Slice 1 row refuses C, so no Knife session can start under symmetry.
  - T-H must enter Face mode *before* opening the preview, because 3 is refused under it (CLAUDE-001 P2 needs Face mode).
  - T-R4e should also cover a Knife session and assert the mesh is unchanged when the guard raises.
  - T-R4b must check the *immediate* caller frame: `key_press` legitimately calls `dispatch_command` (`:1008`, `:1013`, `:1019`) with a Lab frame further up the stack.
  - T-R1a should assert that GLOBAL/KNIFE are unchanged by Lab start-up.
  - T-R5c should prefer the all-constants allow-list (robust against tests that bind non-default commands).

---

## Q5 — Risk to `src/main.py`

**Low.** VERIFIED (code):

- `main.py` touches `Application` only through the public entry points and `status_serial`/`status_message` (`main.py:160-236`).
- It ignores return values and never calls `dispatch_command`, `select_at` or a private member.
- None of the new names (`command_gate`, `hover_suspended`, `interaction_owner`, `set_status`, `record_mesh_change`) exists in `src/` today, so nothing can collide.

With the defaults, the runtime cost is one `is not None` check per key press and per click, plus one
bool check per hover pick.

T-R5a/T-R5b/T-R5c cover the rest. The emulated T-R5c is green (Q4). That is evidence for the
*placement*, not for the future code.

Two implementation notes (not findings against the addendum):

- Keep `_set_status` as the internal name, with `set_status` as the public alias, so the 30 internal call sites stay untouched.
- Initialise `hover_suspended` through its backing field in `__init__`, not through a side-effecting setter, because `viewport` is `None` until `init_scene()`.

Indirect risk (Lab, not `main.py`): `main.py:168-170` always returns `EVENT_HANDLED` because "pyglet's
default handler would close the window on Esc". The Lab's window step must do the same in *every*
branch, including D1. Otherwise Esc could close the Lab window instead of only the preview. This is
pyglet behaviour **UNVERIFIED** here; it is taken from the code comment (N4).

---

## Findings

### N1 — SHOULD — `record_mesh_change` cannot be used as specified without breaking H2-R4; D3 fires after the damage

**Evidence (code):**

- The selection-mirror entry is a private 4-tuple `(mode, vertices, edges, faces)` produced only by `_selection_snapshot` (`:1220`) and unpacked without validation by `_restore_selection` (`:1233`).
- H2-R4 forbids underscore members, so the Lab must hand-build the tuple, duplicating a private format. A wrong shape then crashes at the next Ctrl+Z, far from the cause.
- H2-R4(a) lists `scene`/mesh as **read-only**, but Re-Symmetrize and the symmetry cycle must mutate the mesh before there is anything to record. The allow-list has no entry for that write.
- D3 checks the owner *after* the Lab has mutated the mesh and built the command, so a violation leaves an unrecorded mesh change behind.

**Change:**

- Make Application own the before-and-after, e.g. `apply_mesh_change(description, mutate: Callable[[], set[VertexId] | None])`. In order, Application:
  1. raises if `interaction_owner` is set (D3 before any damage);
  2. snapshots the selection and `mesh.export_state()`;
  3. calls `mutate()` (the Lab's core-capability calls: I1);
  4. pushes one `MeshStateCommand`;
  5. records the mirror entry;
  6. invalidates the pick cache;
  7. notifies the viewport (`on_vertices_moved(moved)` or `on_topology_changed()`);
  8. re-picks hover.
- Minimal alternative: a public `selection_snapshot()`, plus an explicit R4 entry: "mesh writes only through core operations, immediately before `record_mesh_change`, after checking `interaction_owner`".
- Either way, T-R4e must assert that the mesh is unchanged when the guard raises.

### N2 — SHOULD — Lab commands during the preview are unspecified, and D1's safety depends on them

**Evidence:**

- Need 3 lists Shift+S as ignored while the preview is open.
- H2-R2 constrains Lab commands only "while `interaction_owner` is not `None`".
- The gate covers app commands only, and the Lab's keys bypass it at window level.
- The gate is "replaced as a whole on every Lab state change", and the table has a "symmetry off" row, a "BLOCK" row and a "preview open" row with no stated precedence.

**Breaking sequence, VERIFIED (probe N2)** with a Lab that executes Shift+S during the preview by
writing its idle row: select a vertex → M (preview) → Shift+S (gate = idle row, preview still open) →
W (**arms**, owner `"transform"` under the open preview) → Esc. D1 closes the preview and the Move
**stays armed**. Cancel has been taken from `Application`'s interaction (I3, § Activation and
Termination), and the "two never overlap" claim in H2-R2 is false.

**Change:**

- Add to H2-R2: "While the preview is open, the Lab executes no Lab command except M (execute); Shift+S and Shift+B are refused visibly (`set_status`), and the gate stays on the preview row until the preview ends."
- Add Shift+S and Shift+B to T-R2e with the assertion "`command_gate` unchanged".
- Optionally add an assert in the Lab: writing a non-preview row while the preview is open is a programming error.

### N3 — SHOULD — D1 has no negative-path test

D1 says "only while the preview is open", but every listed D1 test (T-R2e) has the preview open.
A Lab that intercepted Cancel unconditionally would pass all required tests and steal Esc from every
armed transform and every Knife session.

**Change:** add T-R2f, run through the Lab window step without a preview:

- Arm W (selection or hover), then Esc → `transform_command is None`, status "Move disarmed".
- C with empty selection (symmetry off), then Esc → `knife_active is False`.

Both are VERIFIED (probe) against the emulation.

### N4 — NIT — The window step's contract is not written down

H2-R3's return contract covers gate refusals and Lab commands, but not the Cancel that D1 interprets.
It also does not say that the step is a pyglet-free function (needed for headless tests, Q4) or that
it returns `EVENT_HANDLED` for Esc in every branch (`main.py:168-170`).

**Change:** "the Lab's key step is a pyglet-free function `(app, lab_state, input) -> bool`; Esc that
closes the preview returns `True`; the pyglet handler always returns `EVENT_HANDLED`."

### N5 — NIT — Test preconditions

- T-R2b needs symmetry off (the Slice 1 row refuses C).
- T-H needs Face mode set before the preview opens.
- T-R4e should also cover a Knife session and assert the mesh is unchanged (N1).

### N6 — NIT — T-R4b caller check

"Called from a Lab module" must mean the immediate caller (`sys._getframe(1)`). `Application.key_press`
calls `dispatch_command` itself (`:1008`, `:1013`, `:1019`), with the Lab window step further up the
stack. A whole-stack check would fail on every D press.

### N7 — NIT — T-R1a / T-R5c robustness

- T-R1a: also assert that GLOBAL and KNIFE resolve exactly as `build_default_bindings()` after Lab start-up. R4(a) allows `set_default` only for the Lab context, and nothing tests that.
- T-R5c: both allow-list variants pass today (probe). The "every command constant in `mirai.interaction.commands`" variant does not post a refusal status for a test that binds a non-default command through `keymap.json`, so it is the safer choice.

### N8 — NIT — I6 listing of D1

The start-up listing prints the three entries and the gate table. D1 re-targets Cancel during the
preview, a contextual meaning of an app command. One listing line ("Cancel (Esc): closes the
Re-Symmetrize preview while it is open") would make it visible like the other overrides.

### Outside H2 (observation, UNVERIFIED)

A Lab mesh change recorded through H3 is undone by `Application`'s Ctrl+Z (mesh and selection). Lab
state is not part of history (symmetry mode, and whether the change came from a cycle or a
Re-Symmetrize). Whether that can leave Lab state and mesh inconsistent depends on Lab code, which was
not read. It is worth one sentence in the plan's Slice 1 scope, not in this addendum.

---

## Appendix — probe code (run against `366042f`, then deleted)

Placed temporarily as `tests/_tmp_h2r2_probe_test.py`, `tests/_tmp_h2r2_gate_plugin.py` and
`tests/_tmp_h2r2_n2_test.py`. Run with `PYTHONPATH=. pytest tests/_tmp_h2r2_probe_test.py` (83 passed),
`H2_ALLOWED=<variant> PYTHONPATH=. pytest tests/test_application*.py -p tests._tmp_h2r2_gate_plugin`
(default/all_constants: 412 passed; empty: 303 failed, the negative control), and
`pytest tests/_tmp_h2r2_n2_test.py` (1 passed: the breaking sequence of N2 is reproduced).
The coverage counts quoted in Q1 come from a scratch script that replays the same seeds through
`random_event` and counts the states reached; for the D1a negative control it sets `command_gate = None`
right after M.

### `tests/_tmp_h2r2_probe_test.py`

```python
"""THROWAWAY probe for review CLAUDE-002 (AD-013 H2 addendum). Deleted after the run.

G does not exist yet. `install_gate` emulates the addendum's Decision on an
`Application` instance, at the stated places: the key check after the Knife
routing and the binding lookup, the click check in `_execute_click`, the hover
flag in `_update_hover`. `Lab` emulates the window step (D1) and the
Lab-state table.
"""
import random

import pytest

import tests._bootstrap  # noqa: F401
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input, KNIFE_CONTEXT
from mirai.viewport.picking import pick_nearest_vertex

W, H = 800, 600
LAB = "symmetry_lab"
SYM_CYCLE, RESYM, GATE_MODE = "SymmetryCycle", "ReSymmetrize", "SymmetryGateMode"
LAB_CMDS = {SYM_CYCLE, RESYM, GATE_MODE}
DISPLAY = frozenset({commands.CYCLE_DISPLAY_MODE, commands.TOGGLE_WIREFRAME_OVERLAY,
                     commands.SET_SHADED, commands.SET_FLAT_SHADED, commands.SET_WIREFRAME})
PREVIEW_TEXT = "Vorschau aktiv - Befehl ignoriert"


def key(v, *m): return Input("key", v, frozenset(m))
def mouse(v, *m): return Input("mouse", v, frozenset(m))


def owner(app):
    if app.transform_command is not None:
        return "transform"
    return "knife" if app.knife_active else None


def install_gate(app):
    app.command_gate = None          # dict(refused=..., allowed=..., text=...) or None
    app.hover_suspended = False
    orig_key, orig_click, orig_hover = app.key_press, app._execute_click, app._update_hover

    def refusal(cmd):
        g = app.command_gate
        if g is None or cmd is None:
            return None
        if cmd in g["refused"]:
            return g["refused"][cmd]
        if g["allowed"] is not None and cmd not in g["allowed"]:
            return g["text"]
        return None

    def key_press(inp):
        if app._knife is None:                       # after the Knife routing
            text = refusal(app.bindings.command_for(inp))
            if text is not None:
                app._set_status(text)
                return False
        return orig_key(inp)

    def execute_click(click):
        text = refusal(click.command)
        if text is not None:
            app._set_status(text)
            return False
        return orig_click(click)

    def update_hover(x, y):
        if app.hover_suspended:
            return app._set_hovered(None)
        return orig_hover(x, y)

    app.key_press, app._execute_click, app._update_hover = key_press, execute_click, update_hover
    return app


class Lab:
    def __init__(self, app):
        self.app, self.preview, self.symmetry = app, False, False
        for inp, cmd in ((key("s", "shift"), SYM_CYCLE), (key("m"), RESYM), (key("b", "shift"), GATE_MODE)):
            assert app.bindings.command_for(inp) is None
            assert app.bindings.command_for(inp, KNIFE_CONTEXT) is None
            app.bindings.set_default(inp, cmd, context=LAB)

    def _write_idle_row(self):
        self.app.command_gate = (dict(refused={commands.CONNECT: "Symmetrie aktiv"}, allowed=None, text="")
                                 if self.symmetry else None)

    def key(self, inp):
        app = self.app
        cmd = app.bindings.command_for(inp, LAB)
        if cmd in LAB_CMDS:
            if owner(app) is not None:
                app._set_status("Lab: refused, interaction running")
                return False
            if cmd == RESYM:
                return self._close() if self.preview else self._open()
            if self.preview:            # unspecified by the addendum; emulated as refused
                app._set_status(PREVIEW_TEXT)
                return False
            if cmd == SYM_CYCLE:
                self.symmetry = not self.symmetry
                self._write_idle_row()
            return True
        if self.preview and cmd == commands.CANCEL:     # D1
            return self._close()
        return app.key_press(inp)

    def _open(self):
        assert owner(self.app) is None
        self.preview = True
        self.app.command_gate = dict(refused={}, allowed=DISPLAY, text=PREVIEW_TEXT)
        self.app.hover_suspended = True
        self.app._set_hovered(None)
        return True

    def _close(self):
        self.preview = False
        self._write_idle_row()
        self.app.hover_suspended = False
        self.app._refresh_hover()
        return True


def mk():
    app = Application(); app.init_scene("cube"); app.frame_scene(); app.set_viewport_size(W, H)
    return app


def targets(app):
    out = []
    for vid in sorted(app.scene.mesh.all_vertex_ids()):
        sx, sy = app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), W, H)
        if pick_nearest_vertex(app.camera, app.scene.mesh, sx, sy, W, H, occlusion=True) == vid:
            out.append((vid, sx, sy))
    return out


def click(app, x, y, *m):
    app.pointer_press(mouse("LEFT", *m), x, y)
    return app.pointer_release("LEFT", x, y)


def all_bound_keys(app):
    keys = {inp for (_ctx, inp) in app.bindings._defaults if inp.kind == "key"}
    return sorted(keys | {key("q"), key("a"), key("b"), key("enter", "shift")},
                  key=lambda i: (i.value, sorted(i.modifiers)))


def snapshot(app):
    s = app.selection
    return (s.mode, frozenset(s.vertices), frozenset(s.edges), frozenset(s.faces),
            type(s.hovered), s.hovered, len(app.history), app.history.can_redo(),
            app.scene.mesh.export_state(), app.axis_constraint, app.status_serial,
            app.status_message, app.tool_manager.active_tool, app.display.mode,
            app.display.show_edges, app.transform_command, app.knife_active,
            len(app._selection_undo_stack), len(app._selection_redo_stack))


def random_event(rng, app, lab, keys, tgts, held, allow_lab_esc=True):
    """One random input event, routed like the Lab window (keys through `lab.key`)."""
    r = rng.random()
    if r < 0.35:
        inp = rng.choice(keys)
        if not allow_lab_esc and (inp.value in ("m", "ESCAPE") and not inp.modifiers):
            return
        (lab.key(inp) if lab else app.key_press(inp)); held.add(inp)
    elif r < 0.5 and held:
        inp = rng.choice(sorted(held, key=lambda i: (i.value, sorted(i.modifiers))))
        held.discard(inp); app.key_release(inp)
    elif r < 0.62:
        mods = rng.choice([(), ("shift",), ("ctrl",), ("alt",), ("alt", "shift")])
        btn = rng.choice(["LEFT", "LEFT", "LEFT", "RIGHT", "MIDDLE"])
        _, x, y = rng.choice(tgts) if tgts and rng.random() < 0.7 else (None, rng.uniform(0, W), rng.uniform(0, H))
        app.pointer_press(mouse(btn, *mods), x, y)
    elif r < 0.72:
        d = rng.choice([1, 2, 10, 30])
        app.pointer_drag(rng.choice([-d, d]), rng.choice([-d, 0, d]), rng.uniform(0, W), rng.uniform(0, H))
    elif r < 0.82:
        app.pointer_release(rng.choice(["LEFT", "RIGHT", "MIDDLE"]), rng.uniform(0, W), rng.uniform(0, H))
    elif r < 0.94:
        _, x, y = rng.choice(tgts) if tgts and rng.random() < 0.6 else (None, rng.uniform(0, W), rng.uniform(0, H))
        app.pointer_motion(x, y, rng.uniform(-8, 8), rng.uniform(-8, 8))
    elif r < 0.98:
        app.pointer_scroll(Input("wheel", rng.choice(["UP", "DOWN"])))
    else:
        app.pointer_leave()


# --- D1: interaction_owner stays None for the whole time the preview is open ---------------

@pytest.mark.parametrize("seed", range(40))
def test_D1a_owner_none_while_preview_open(seed):
    rng = random.Random(seed)
    app = install_gate(mk()); lab = Lab(app)
    tgts = targets(app)
    # random warm-up outside the preview (selection, history, constraint, display, symmetry on/off)
    held = set()
    for _ in range(rng.randint(0, 60)):
        random_event(rng, app, lab, all_bound_keys(app), tgts, held, allow_lab_esc=False)
    for inp in list(held):
        app.key_release(inp)
    if app.knife_active:
        lab.key(key("ESCAPE"))
    while app.pointer.active:
        app.pointer_release(app.pointer.active_button, 0, 0)
    assert owner(app) is None
    if seed % 2:                                     # non-empty selection + history before M
        app.key_press(key("1"))
        tgts = targets(app)
        (_a, ax, ay), (_b, bx, by), *_ = tgts
        click(app, ax, ay)
        app.key_press(key("w")); app.pointer_motion(ax + 5, ay + 5, 5, 5); app.key_release(key("w"))
        click(app, bx, by, "shift")
        assert app.history.can_undo() and app.selection.vertices
    assert lab.key(key("m")) is True and lab.preview
    before = snapshot(app)
    keys = all_bound_keys(app)
    held = set()
    for _ in range(400):
        random_event(rng, app, lab, keys, tgts, held, allow_lab_esc=False)
        assert lab.preview
        assert owner(app) is None, "Application started an interaction under the open preview"
        assert app.tool_manager.active_tool is None
        assert app.selection.hovered is None
        now = snapshot(app)
        # model, selection, history, mirror stacks, constraint unchanged; display/status may change
        assert now[0:4] == before[0:4] and now[6:10] == before[6:10] and now[15:] == before[15:]
    # Esc via the window step closes the preview; Application sees nothing
    serial = app.status_serial
    assert lab.key(key("ESCAPE")) is True and not lab.preview
    assert app.status_serial == serial
    assert app.hover_suspended is False


# --- D1: Application's Cancel is a no-op whenever interaction_owner is None -----------------

@pytest.mark.parametrize("seed", range(40))
def test_D1b_cancel_is_noop_when_idle(seed):
    rng = random.Random(1000 + seed)
    app = mk()                                    # plain Application, no gate
    tgts = targets(app)
    keys = all_bound_keys(app)
    held, checked = set(), 0
    for _ in range(400):
        random_event(rng, app, None, keys, tgts, held)
        assert (app._transform_key is None) == (app._transform_command is None)
        if owner(app) is None:
            before = snapshot(app)
            assert app.key_press(key("ESCAPE")) is False
            assert snapshot(app) == before
            checked += 1
    assert checked > 50


# --- F1 under G (T-R2c) and the D1 negative path ---------------------------------------------

def test_F1_under_G_orbit_inside_preview():
    app = install_gate(mk()); lab = Lab(app)
    (a, ax, ay), *_ = targets(app)
    click(app, ax, ay)
    app.key_press(key("w")); app.pointer_motion(ax + 5, ay + 5, 5, 5); app.key_release(key("w"))
    assert app.history.can_undo()
    lab.key(key("m"))
    app.pointer_press(mouse("LEFT", "alt"), ax, ay); app.pointer_drag(10, 0, ax + 10, ay)
    assert app.pointer.active
    serial = app.status_serial
    assert lab.key(key("z", "ctrl")) is False and app.history.can_undo() and app.status_serial == serial + 1
    assert lab.key(key("w")) is False and app.transform_command is None
    # Esc mid-orbit closes the preview, the orbit keeps running
    assert lab.key(key("ESCAPE")) is True and not lab.preview and app.pointer.active
    yaw = app.camera.yaw
    app.pointer_drag(10, 0, ax + 20, ay)
    assert app.camera.yaw != yaw


def test_D1_negative_esc_reaches_application_without_preview():
    app = install_gate(mk()); lab = Lab(app)
    lab.key(key("s", "shift"))                     # symmetry on: idle row refuses Connect only
    (a, ax, ay), *_ = targets(app)
    click(app, ax, ay)
    assert lab.key(key("w")) is True and app.transform_command == commands.MOVE
    assert lab.key(key("ESCAPE")) is True
    assert app.transform_command is None and app.status_message == "Move disarmed"


def test_lab_key_during_knife_is_refused_by_the_lab_not_routed():
    app = install_gate(mk()); lab = Lab(app)
    assert lab.key(key("c")) is True and app.knife_active
    serial = app.status_serial
    assert lab.key(key("s", "shift")) is False and app.knife_active and app.status_serial == serial + 1
    assert lab.key(key("ESCAPE")) is True and not app.knife_active   # no preview: Esc is the Knife's
```

### `tests/_tmp_h2r2_gate_plugin.py`

```python
"""THROWAWAY (review CLAUDE-002): installs an inert-but-active emulated gate on every Application."""
import os
import tests._bootstrap  # noqa: F401
from mirai import application as A
from mirai.interaction import commands
from mirai.interaction.bindings import build_default_bindings
from tests._tmp_h2r2_probe_test import install_gate

_orig_init = A.Application.__init__
if os.environ.get("H2_ALLOWED") == "all_constants":
    ALLOWED = frozenset(v for k, v in vars(commands).items() if k.isupper() and isinstance(v, str))
elif os.environ.get("H2_ALLOWED") == "empty":
    ALLOWED = frozenset()
else:  # the addendum's wording: every command the default bindings can resolve
    ALLOWED = frozenset(build_default_bindings()._defaults.values())

def _init(self, *a, **kw):
    _orig_init(self, *a, **kw)
    install_gate(self)
    self.command_gate = dict(refused={"__sentinel__": "never"}, allowed=ALLOWED, text="REFUSED-BY-INERT-GATE")

A.Application.__init__ = _init
```

### `tests/_tmp_h2r2_n2_test.py`

```python
"""THROWAWAY (CLAUDE-002, N2): a Lab that executes Shift+S during the preview by writing its idle row."""
import tests._bootstrap  # noqa: F401
from tests._tmp_h2r2_probe_test import Lab, install_gate, mk, targets, click, key, owner, SYM_CYCLE, LAB
from mirai.interaction import commands


class LabShiftSInPreview(Lab):
    def key(self, inp):
        if self.preview and self.app.bindings.command_for(inp, LAB) == SYM_CYCLE and owner(self.app) is None:
            self.symmetry = not self.symmetry
            self._write_idle_row()          # "replaced as a whole on every Lab state change"
            return True
        return super().key(inp)


def test_N2_esc_is_stolen_from_an_armed_transform():
    app = install_gate(mk()); lab = LabShiftSInPreview(app)
    (a, ax, ay), *_ = targets(app)
    click(app, ax, ay)
    assert lab.key(key("m")) and lab.preview
    assert lab.key(key("s", "shift"))                 # preview still open, gate now the idle row
    assert lab.key(key("w")) is True and owner(app) == "transform"   # arms under the open preview
    assert lab.key(key("ESCAPE")) is True              # D1: the Lab closes the preview ...
    assert not lab.preview and app.transform_command == commands.MOVE   # ... the transform stays armed
```
