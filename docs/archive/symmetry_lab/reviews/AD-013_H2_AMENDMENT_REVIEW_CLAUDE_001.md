# Independent review — AD-013 H2 amendment G-2 (PROPOSED, 2026-10-08)

**Object:** `docs/architecture/AD-013-CAPABILITY-PROMOTION-UX-OWNERSHIP.md`, § "Addendum (2026-10-08, AD-SYM-03
slice 3 — H2 amendment G-2: context-keyed refusal for `C`, fail-closed BLOCK row)".
**Branch / commit:** `claude/funny-curie-vhvi6a` @ `42aa4ea` (= `origin/main` at review time; `b1cedee`, the
commit the amendment reads, is its parent and also on `main`).
**Session:** fresh; earlier review answers (H2 CLAUDE-001/002, AD-SYM-03 CLAUDE-001) were not read. The H2
addendum of 2026-10-03 was read only for its Decision, Limits of G, H2-R1…R6, Required tests (and the text
around them in the same section).
**Checked against:** H2 addendum (2026-10-03); AD-SYM-03 §2.5, §3 item 7, §4, §5, §6 (A1–A3 verdicts), §7 slice 3;
code at `42aa4ea`: `src/mirai/application.py`, `src/mirai/topology/contextual_c.py`,
`src/mirai/interaction/commands.py`, `bindings.py`, `input.py`, `routing.py`, `src/mirai/symmetry_coordination.py`,
`experiments/symmetry_lab/lab_app.py`, `lab_symmetry.py`, `run.py`.
**Mode:** review only. No code or existing document changed. Probes ran from the scratchpad against the real
`Application` and the real Lab (`build_app_lab`, `lab_key_press`); the full probe script is in the appendix.
G-2 does not exist in code, so the probes *emulate* it (a `CommandGate` subclass with `refused_contexts`, and a
wrapper around `_connect_command` that does the one `resolve_c_context`, checks the mapping, then runs the
original body with the resolver pinned to that value). They are evidence for placement and wiring, not for the
future code.

---

## Summary

G-2 is the right shape: one data field, one lookup after the one resolution, no callback, no per-press row. The
emulation reproduces every behaviour the amendment claims (T-G2a–e equivalents pass; the order identity →
armed-check → context holds; a Knife session is untouched). The fail-closed row names every command
`Application` handles today; no NON_OPERATION entry is wrong. No blocker.

Four SHOULDs, all about what the text leaves implicit: the open A2 question under "Not decided here" is
coupled to G-2's own "one resolution" invariant and to the G-3 boundary, so it cannot wait for slice 3; the
H2-R2 sentence "outside the preview the gate refuses only commands that start an interaction or change the
mesh" is contradicted by the fail-closed row and must be amended, not declared to "hold"; nothing tests the G-3
boundary from the Production side; and "no selection change" on a context refusal is claimed but not tested,
which matters once canonicalisation runs before the check.

**Verdict: ACCEPT WITH CHANGES** (details at the end).

---

## Verification table — every file:line claim re-checked at `42aa4ea`

`application.py` is unchanged since `b1cedee` (the amendment commit is docs only), so the line numbers apply.

| Row | Claim | Checked | Result |
|---|---|---|---|
| a | `key_press` `:1145`; Knife routing `:1151-1152`; GLOBAL resolve `:1153`; `_gate_refuses(command)` `:1154` | lines 1145, 1151-1152, 1153, 1154 | ✓ |
| a | `_execute_click` `:1702`, gate `:1704`, `select_at` `:1706`; `_SELECT_COMMANDS` `:80-85` (four commands) | 1702, 1704, 1706; 80-85 | ✓ |
| a | one `_gate_refuses` `:1524-1534`, one `command_gate` `:335` | 1524-1534, 335 | ✓ |
| a | click during a Knife session never reaches `_execute_click` `:1584-1589` | 1584-1589 (`pointer_release` returns False first) | ✓ |
| a | `ClearSelection` = Alt+A `bindings.py:127`, no branch, falls to `return False` `:1185` | bindings 127; application 1185 | ✓ (and no `_execute_click` path: it is not a click command) |
| b | one `resolve_c_context` `:565`; branches `:567`, `:580`, `:597`, `:614`→`_knife_begin` `:615`, NONE `:617-620` | 565, 567, 580, 597, 614-615, 617-620 | ✓ |
| b | only other occurrence in `src/` and the Lab is a docstring `:1502` | grep: also the import at `:63` and two comments at `:366`, `:370` naming `_connect_command` | ✓ (no other *call*) |
| b | `_connect_command` has one caller `dispatch_command` `:527-528`; `dispatch_command(CONNECT)` one caller `key_press` `:1170-1175`, after the gate and after the armed check `:1173-1174` | 527-528, 1170-1175, 1173-1174 | ✓ in `src/`. **Precision:** `tests/test_topology_transaction_seam.py:183,190,198,206,209` call `app._connect_command` directly (test code, private; no effect on the claim). `playground/window.py:2405` has its own `resolve_c_context` call (Playground, not `Application`) |
| c | `sync_gate` early return `lab_app.py:331`; `interaction_owner == "knife"` `application.py:1119-1120`; forward then `sync_gate` `lab_app.py:507-508` | 331, 1119-1120, 507-508 | ✓ |
| d | `SplitEdge` `:97`, `Collapse` `:98`, `LoopInsert` `:101`, `LoopSlide` `:102`, `Extrude` `:103`, `ArticulationRestore` `:106`; no branch in `key_press` `:1153-1185`; `routing.py:25-29` maps only Move/Rotate/Scale; `Collapse` K and `Extrude` Alt+E only in `TOPOLOGY_CONTEXT` `bindings.py:168,172`; `EdgeLoop` `:99`, `EdgeRing` `:100`, `ClearSelection` `:51` | all lines | ✓ (`EdgeLoop`/`EdgeRing` are also TOPOLOGY-only, `bindings.py:169-170`) |
| Proposal | `CommandGate` `:248`; `MappingProxyType` `:262-264`; `refusal` `:267-273`; `C: nothing to do here` `:619` | 248, 263 (inside 262-265), 267-273, 619 | ✓ |
| Proposal | `block_row` `lab_app.py:202-207` (block-list), `==` compare `:335`, `_install_row` `:340`, Lab commands before `Application` `:503-504`, `e5_warning_text` `:582-603` | all lines | ✓ |

All factual claims hold. The amendment's own precision under (a) is correct.

---

## Q1 — Does G-2 lift only the "context" item of § Limits of G?

**Yes, with two precisions the text should state.**

§ Limits of G lists three things G cannot do: (1) refusals depending on more than the command (click position,
part of the selection, mirror side); (2) refusing input inside a Knife session; (3) "instead of" reactions.
G-2 adds one key type (`CContext`) for one command. It does not touch (2) — the check is unreachable inside a
session (probe P3: a gate listing every context leaves Enter/Esc/E/Ctrl+Z/C in a session byte-identical) — nor (3)
(no Lab code runs instead of anything; `Application` posts its own status). Of (1) it lifts "part of the
selection", only as far as `resolve_c_context` sees it (count and mode), and only for `Connect`.

**Precision 1 — mirror pairing enters through canonicalisation (NIT, see also S1).** After slice 3 the value the
check keys on is resolved from the *canonicalised* selection (A2 = A). The effective refusal then depends on
whether the selected elements are mirror partners: probe P5 on `subd_cube`, X symmetry, edges `{0, 10}` (a mirror
pair sharing no face): literal context `EDGE_CONNECT` (declared → runs), canonical context `SPLIT` (undeclared →
refused with the Split text). That is still "the context `Application` resolves", and the gate data stays keyed on
`CContext` only, so it is not the "mirror side" item. The amendment should say so in one sentence, so a later
reader does not count it as a second lifted Limit.

**Precision 2 — a third gate site (NIT).** H2 § Decision names exactly two sites (`key_press`, `_execute_click`) and
says "deliberately no gate checks in … `dispatch_command`". G-2 adds a third site *below* `dispatch_command`. The
amendment records the resulting asymmetry (a direct `dispatch_command(CONNECT)` is context-gated but not
identity-gated) as theoretical, which is true today (verification b). It should also state that the H2 call-site
list grows by one, so the 2026-10-03 Decision text is not read as complete.

Nothing else in the amendment lifts a Limit. G-9 (mode-keyed removal) is correctly left out.

---

## Q2 — Does NON_OPERATION name every click and non-operation command that must stay usable under BLOCK?

**Yes for every command `Application` handles today; nothing listed is wrong.** Probe P4 enumerates all 42
command constants in `commands.py`: 22 are NON_OPERATION, 3 removal + `Connect` + 3 transforms are covered by
declarations / `supports_symmetry`, the 3 Lab commands are handled before `Application`, and the remaining 13 are
refused by the emulated row. The four click commands reach `_execute_click` and are not refused (P4b: `select_at`
reached, return `True`, no refusal status); Esc still disarms W (`Move disarmed`); 1/2/3, X/Y/Z, Shift+X/Y/Z, D,
Shift+D, Ctrl+Y give the same return value and status as with symmetry off. (Ctrl+Z differs in P4b only because the
probe's symmetry-on fixture has the Shift+S step on the stack, so Undo has something to undo — a fixture artefact,
not a gate effect.) `ClearSelection` is listed although `Application` ignores it today; correct, because it is a
selection command and listing it costs nothing.

Nothing listed should be removed. `Undo`/`Redo` under BLOCK can restore an earlier one-sided state, but they are not
operations and must stay (H2-R2 relies on Undo restoring the definition).

**N2 (NIT) — "never reach the gate" is true only for the default keymap.** The amendment excludes `Orbit`/`Pan`/
`Zoom` and `KnifeCommit`/`KnifeLift` "because they never reach the gate". `BindingSet.command_for` accepts any
user GLOBAL binding, and `key_press` gates every resolved command. Probe P4 binds each to F9 in GLOBAL:

| Command (F9, GLOBAL user binding) | symmetry off | symmetry on, emulated fail-closed BLOCK |
|---|---|---|
| `Orbit`, `Pan`, `Zoom`, `KnifeCommit`, `KnifeLift` | `False`, no status | `False`, status `Symmetrie aktiv — Befehl nicht koordiniert (BLOCK: nicht gestartet)` |
| `EdgeLoop`, `EdgeRing` | `False`, no status | same generic text |
| `SplitEdge`, `Collapse`, `LoopInsert`, `LoopSlide`, `Extrude`, `ArticulationRestore` | `False`, no status | named `… spiegelt nicht (BLOCK: … nicht gestartet)` |

So a key bound to `Orbit` is told it is "not coordinated". Harmless, but the claim is wrong as written. Proposed
change: list the five in NON_OPERATION (they are non-operations; `Application` returns `False` for them in
`key_press` either way, so listing them cannot start anything), and keep "deliberately not listed" for
`EdgeLoop`/`EdgeRing` only. The preview row has the same property today; that is outside this amendment.

**N4 (NIT) — the pseudocode has a second, undefined hand list.** `refused = … for every known operation command
that is not declared` needs a set of "known operation commands" to give named texts; its source is not defined
(my probe had to invent one). Either define it (e.g. all constants minus NON_OPERATION minus Lab commands) or say
that named texts are an optional nicety and the generic text is the contract. Also `block_text(name of ctx)` needs
display names (`Split`, `Knife`), not enum names (P5 shows `SPLIT spiegelt nicht`).

---

## Q3 — Can a runtime refusal in `Application` be mistaken for G-3?

**As specified, no; the boundary is clear in principle but untested and, in one case, thin.**

The criterion in the amendment (item 3): a runtime refusal belongs to the contract of a *declared* operation and
is decided by its coordinator from the operation's input (seam case, both-sides face, D-strict delta); G-3 would
refuse an *undeclared* operation because a definition is set. That separates them if and only if `Application`
runs undeclared operations unchanged when a definition is set and no gate is installed. The amendment states this
("MARK runs … only undeclared ones one-sided") but names no test for it — see **S3**.

Two places where the line is thin:

1. **Canonicalisation for undeclared contexts** (the item under "Not decided here"). If `Application` canonicalises
   a two-sided selection whenever a definition is set, it changes the behaviour of an *undeclared* operation in
   MARK because of the definition (P5: two selected edges become a one-sided Split of one edge). That is not a
   refusal, but it is exactly the G-3 pattern — Production behaviour for an unsupported operation keyed on the
   definition. See **S1**.
2. **Non-exact plane** (AD-SYM-03 §3 item 6). That refusal does not depend on the operation's input; for that
   definition it refuses every declared topology operation, in MARK too — for that state it is G-3 in effect.
   It is unreachable today: Lab planes are axis planes through the origin (`lab_symmetry.definition_for_axis`,
   `plane_point=ORIGIN`), `src/main.py` sets no definition, and AD-SYM-03 §4 records the asymmetry. **N6 (NIT):** give
   the criterion an operational form in item 3 — "a runtime refusal is decided by the coordinator of a declared
   operation from its input; it never reads the gate or the E5 mode" — and name the non-exact plane as the one
   accepted definition-wide refusal, with its §4 pointer.

---

## Q4 — Does anything break H2-R2, R3, R5 or R6?

**H2-R2 — one sentence is broken (S2); the rest holds.** Holds: the context check can only stop `C` from
starting (P1: listed contexts return `False` with mesh, history, selection mode/sets and `knife_active` unchanged);
it runs after the armed check (P2: W armed + C → `False`, resolver called 0 times, status unchanged); it never runs
inside a session (P3); rows remain a function of Lab state (the declarations are static), and `Cancel` stays
allowed (P4b).

**S2 (SHOULD).** H2-R2 says: "Outside the preview the gate refuses only commands that start an interaction or
change the mesh (Connect; transform commands in BLOCK). It never refuses `Cancel`." The fail-closed row refuses,
outside the preview, `EdgeLoop`/`EdgeRing` (selection commands, deliberately), every user-bound navigation/Knife
command (N2), and any future command, mutating or not (P4 table). That is the intended fail-closed property, but
it contradicts the H2-R2 sentence, and § "Consequences for H2-R1 … H2-R6" says "H2-R2 — holds" without amending
it. Proposed change: the amendment replaces that bullet, e.g. "Outside the preview the gate refuses commands that
start an interaction or change the mesh; under BLOCK it additionally refuses every command outside NON_OPERATION
and the declarations (fail-closed). It never refuses `Cancel`."

**H2-R3 — holds, extended correctly.** A context refusal posts through `_set_status` (`status_serial` + 1, twice →
two increments, P1) and returns `False`. The derived row prints through `GateRow.describe`, which would need a
`refused_contexts` clause (T-R1d+ names it). Note that a large `allowed` set prints as one long line; layout is not
a review matter.

**H2-R5 — holds for the gate; the guard is one-sided (S3).** With `command_gate is None` or an empty
`refused_contexts`, the emulation is identical to no gate (P1 "not listed" rows match the baseline for every
context, including `NONE`). T-R5a+/T-R5c+ cover that. They do not cover the other half of "Production unchanged"
that slice 3 touches: `_connect_command` with a definition set and no gate.

**T-R5c+ (N5, NIT).** `tests/_inert_gate_plugin.py` counts `_gate_refuses` consultations to prove the check path
ran. The context check is a different code path; the inert run should count it too, or the positive half of T-R5c+
proves only that an empty mapping is never consulted.

**H2-R6 — holds.** `refused_contexts` is a field of the one `command_gate`; `_install_row` (`lab_app.py:340`) stays
the only writer. The D-b mapping is read, never written at runtime; reading it from `Application` (dispatch) and
the Lab (row derivation) does not create a second writer.

**H2-R4 (not asked, adjacent) — N3 (NIT).** The amendment's own "new evidence" against G-4 is that the Lab would
have to repeat the canonicalisation. T-R4a+ forbids `resolve_c_context` in Lab modules but not
`mirai.symmetry_coordination.canonical_vertices/edges/faces`, which exist since slice 1
(`symmetry_coordination.py:108-118`). Add them to the scan, or the G-4 route stays open by a different name.

---

## Q5 — What is missing (including "Not decided here")?

**S1 (SHOULD) — the A2/MARK question is coupled to G-2 itself; decide it in this amendment, not in slice 3.**
"Not decided here: whether A2 canonicalisation also applies, in MARK, to a context without a coordinator." The
two answers have different consequences for G-2:

- *Canonicalise always (definition set):* one resolution, as T-G2b requires. But in MARK an undeclared context is
  changed by the definition (P5: `{0, 10}` → one-sided Split of edge 0 instead of today's
  `Keine verbindbaren Kanten …`), which is the G-3 pattern for unsupported operations (Q3.1).
- *Canonicalise only for declared contexts:* `Application` must know the canonical context to know whether it is
  declared, and if it is not, resolve the literal selection — **two** `resolve_c_context` calls. That contradicts
  T-G2b ("exactly one call … also with a definition set") and the Proposal's "one resolution" bullet, and the G-2
  key would then be the literal context in one branch and the canonical one in the other.

Under BLOCK both answers agree for P5 (Split refused with the Split text, which is A2 = A read correctly), so the
question is indeed MARK-only in behaviour — but not in mechanism. Proposed change: decide it here (my
recommendation: canonicalise always when a definition is set, and record in item 3 why that is not G-3 — the A2
verdict is about what `C` *means* under symmetry, not a support policy), or make the one-resolution invariant and
T-G2b explicitly conditional on the answer.

**S3 (SHOULD) — no test guards the G-3 boundary.** Add a named `src` test: with `command_gate is None` and a
definition set (exact X plane), `C` on each *undeclared* context (Split and Knife after slice 3) behaves as with no
definition: same return value, same one-sided mesh result, no refusal status (modulo the S1 answer for two-sided
selections). Optionally a guard like T-R5b that `src/main.py` never assigns `symmetry_definition` — today that is
the only thing keeping coordinators and runtime refusals out of the running app, and nothing tests it.

**S4 (SHOULD) — "no selection change" on refusal is claimed but not tested.** The Proposal says a context refusal
causes "no selection change". Today that is trivially true (P1). After slice 3, canonicalisation runs before the
check; if it writes `app.selection` (the A2 note says coordinators "canonicalise the selection"), a refused `C` would
leave the selection reduced to one side. Proposed change: state that canonicalisation works on a value (a
temporary `Selection` or id sets passed to the resolver), and add to T-G2a: `selection` mode and id sets unchanged
on a refusal, including the two-sided case.

**NITs, collected:** N1 (Precision 2: name the third gate site), N2 (list navigation/Knife commands in
NON_OPERATION or reword), N3 (T-R4a+ scans `canonical_*`), N4 (define "known operation commands"; display names
in context texts), N5 (count the context check in T-R5c+), N6 (operational form of the runtime-refusal criterion;
name the non-exact plane), Precision 1 (mirror pairing via canonicalisation is part of the context item).

Points under "Not decided here" that are fine to leave open: Python shape and names; `EdgeLoop`/`EdgeRing` (they
fail closed until decided, which is the safe default); mode-keyed removal (G-9; the amendment correctly says an
undecidable removal command stays undeclared, which ends the interim for it — consistent with O1 in AD-SYM-03 §4).

---

## Probes (results)

Run with the repo's pytest interpreter (`/root/.local/share/uv/tools/pytest/bin/python -I probe_g2.py`; the system
`python3` has no pytest). Assets: `cube` (`Application.init_scene("cube")`) and the Lab's `subd_cube`
(`build_app_lab`). The appendix holds the script verbatim.

| Probe | What | Result |
|---|---|---|
| P1 | G-2 emulation, each operation context listed / not listed (others listed), `C` via `key_press` | Listed: `False`, `status_serial` + 1, text = row text, `export_state`, history, selection and `knife_active` unchanged, resolver called once; second press +1 again. Not listed: identical to no gate (`Split`, `Connect Edges`, `Vertex Connect`, Knife begins), resolver once. `NONE` → `C: nothing to do here`. Listing `NONE` raises at construction |
| P2 | order | `Connect` in `refused` + context listed → identity text, resolver 0 calls; `Connect` outside `allowed` → `not_allowed_text`, 0 calls; W armed + C → `False`, status unchanged, 0 calls |
| P3 | Knife session started without gate, then a gate listing every context | E, Ctrl+Z, C, Enter, Esc: identical return values, statuses and `knife_active` with and without the gate |
| P4 | emulated fail-closed BLOCK row in the Lab (illustration declarations: Edge/Vertex Connect, Delete, Dissolve, DissolveNoCleanup), every non-covered command bound to F9 in GLOBAL | 13 commands refused visibly under BLOCK (table in Q2); all silent `False` with symmetry off |
| P4b | NON_OPERATION keys, Esc-disarm, click under the emulated row | Same results as with symmetry off (Ctrl+Z: fixture artefact, see Q2); Esc → `Move disarmed`; click not refused |
| P5 | `subd_cube`, X, mirror edge pair `{0, 10}` | literal `EDGE_CONNECT`, canonical `[0]` → `SPLIT`; G-2 on canonical → Split text; today without gate → `Keine verbindbaren Kanten: ausgewählte Kanten teilen sich keine Face.` |

---

## Test suites (once, as CLAUDE.md lists them)

| Suite | Result | Amendment commit message |
|---|---|---|
| `pytest tests --ignore=tests/test_extrude_tool.py` | 1710 passed, 8 skipped (68 subtests passed) | 1710 passed / 8 skipped ✓ |
| `pytest experiments/symmetry_lab/tests` | 311 passed, 4 skipped, 1 failed (`test_app_lab_partners.py::test_lab_overlays_are_drawn_before_the_app_point_overlay`, `ModuleNotFoundError` at `src/viewport/gl_line_overlay.py:178`, pyglet missing) | 311 / 4 / 1 failed (pyglet missing) ✓ |
| `pytest playground/tests` | 8 errors during collection; with `--continue-on-collection-errors`: 701 passed, 11 failed, 47 errors | 8 collection errors; 701 / 11 / 47 ✓ |

---

## Findings

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| S1 | SHOULD | The open A2/MARK canonicalisation question decides whether G-2's "one resolution" (T-G2b) can hold and whether MARK changes an undeclared operation because of the definition (G-3 pattern). Decide it here or make the invariant conditional | Q5; P5; Proposal "One resolution"; T-G2b |
| S2 | SHOULD | H2-R2 bullet "outside the preview the gate refuses only commands that start an interaction or change the mesh" is contradicted by the fail-closed row; the amendment says "holds" instead of replacing it | Q4; P4 table; H2-R2 |
| S3 | SHOULD | No test for the G-3 boundary from the Production side: no gate + definition set → undeclared contexts unchanged. Nothing tests that `src/main.py` sets no definition | Q3; Q5; T-R5a+ covers only the no-definition case |
| S4 | SHOULD | "No selection change" on a context refusal is claimed, not tested; canonicalisation before the check must not write `app.selection` | Q5; Proposal table; T-G2a |
| N1 | NIT | Name the third gate site (below `dispatch_command`) as a change to H2 § Decision's call-site list | Q1 Precision 2 |
| N2 | NIT | "Never reach the gate" holds only for the default keymap; list `Orbit`/`Pan`/`Zoom`/`KnifeCommit`/`KnifeLift` in NON_OPERATION or reword | Q2; P4 |
| N3 | NIT | T-R4a+ should also forbid `canonical_*` from `mirai.symmetry_coordination` in Lab modules | Q4 (H2-R4) |
| N4 | NIT | "Known operation commands" is an undefined second list; context texts need display names | Q2; P5 output |
| N5 | NIT | T-R5c+ inert run should count context-check consultations | Q4 (H2-R5) |
| N6 | NIT | Operational form of "runtime refusals are not G-3"; name the non-exact plane as the one definition-wide refusal | Q3 |
| P1 | NIT | One sentence: mirror pairing via canonicalisation is part of the context item, not the "mirror side" Limit | Q1 Precision 1 |

No BLOCKER. Every file:line claim in the Verification table holds.

## Verdict

**ACCEPT WITH CHANGES.** G-2 lifts exactly the "context" item of § Limits of G, keeps H2's data-only, no-callback
property, and the fail-closed row covers today's command set completely. Before DECIDED: answer S1 in the text (or
make T-G2b conditional), replace the H2-R2 bullet (S2), and add the tests named in S3 and S4. The NITs can be
taken in the same revision or in slice 3.

---

## Appendix — probe script (verbatim, as run)

```python
"""Review probes for the AD-013 H2 amendment G-2 (emulation on the real Application, headless).

G-2 does not exist in code; it is emulated by (1) a CommandGate subclass with a
`refused_contexts` field and (2) a wrapper around `Application._connect_command` that
performs the one `resolve_c_context`, checks the mapping, and then runs the original
body with `resolve_c_context` pinned to the already-resolved value (so the body does
not resolve a second time). Evidence for placement and wiring only, not for the
future code.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

REPO = Path("/home/user/Mirai-Bastel")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "experiments"))
import tests._bootstrap  # noqa: E402,F401
from symmetry_lab._paths import ensure_paths  # noqa: E402

ensure_paths()

import mirai.application as appmod  # noqa: E402
from core.selection import SelectionMode  # noqa: E402
from mirai.application import Application, CommandGate  # noqa: E402
from mirai.interaction import commands as cmd  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.symmetry_coordination import build_index, canonical_edges  # noqa: E402
from mirai.topology.contextual_c import CContext, resolve_c_context  # noqa: E402

import symmetry_lab.lab_app as lab_app  # noqa: E402
from symmetry_lab.lab_app import lab_key_press  # noqa: E402
from symmetry_lab.run import build_app_lab  # noqa: E402

W, H = 800, 600


# -- G-2 emulation ----------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class G2Gate(CommandGate):
    refused_contexts: Mapping[CContext, str] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__post_init__()
        if CContext.NONE in self.refused_contexts:
            raise ValueError("CContext.NONE may not be listed")
        object.__setattr__(self, "refused_contexts", MappingProxyType(dict(self.refused_contexts)))


RESOLVE_CALLS = [0]
_real_resolve = resolve_c_context


def counting_resolve(selection):
    RESOLVE_CALLS[0] += 1
    return _real_resolve(selection)


_orig_connect = Application._connect_command


def g2_connect(self) -> bool:
    ctx = counting_resolve(self.selection)  # the one resolution
    gate = self.command_gate
    texts = getattr(gate, "refused_contexts", {}) if gate is not None else {}
    if ctx in texts:
        self._set_status(texts[ctx])
        return False
    saved = appmod.resolve_c_context
    appmod.resolve_c_context = lambda _sel: ctx  # body uses the same value, no 2nd call
    try:
        return _orig_connect(self)
    finally:
        appmod.resolve_c_context = saved


Application._connect_command = g2_connect


# -- helpers ------------------------------------------------------------------------------


def key(value, *mods):
    return Input("key", value, frozenset(mods))


C = key("c")
ESC = key("ESCAPE")
WKEY = key("w")


def snapshot(app):
    s = app.selection
    return (
        app.scene.mesh.export_state(),
        len(app.history._undo_stack) if hasattr(app.history, "_undo_stack") else app.history.can_undo(),
        s.mode,
        frozenset(s.vertices),
        frozenset(s.edges),
        frozenset(s.faces),
        app.knife_active,
    )


def fresh_cube():
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(W, H)
    return app


def select(app, mode, ids):
    s = app.selection
    s.mode = mode
    s.clear()
    if ids:
        s.add(set(ids))


def face_edges_opposite(mesh):
    f = sorted(mesh.all_face_ids())[0]
    verts = list(mesh.face_vertices(f))
    edges = []
    for i in range(len(verts)):
        a, b = verts[i], verts[(i + 1) % len(verts)]
        edges.append(mesh.find_edge(a, b) if hasattr(mesh, "find_edge") else None)
    return verts, edges


def context_selections(app):
    mesh = app.scene.mesh
    verts, edges = face_edges_opposite(mesh)
    if edges[0] is None:
        # fall back: edges of the face via mesh API
        f = sorted(mesh.all_face_ids())[0]
        edges = list(mesh.face_edges(f))
    return {
        CContext.SPLIT: (SelectionMode.EDGE, [edges[0]]),
        CContext.EDGE_CONNECT: (SelectionMode.EDGE, [edges[0], edges[2]]),
        CContext.VERTEX_CONNECT: (SelectionMode.VERTEX, [verts[0], verts[2]]),
        CContext.KNIFE: (SelectionMode.VERTEX, []),
        CContext.NONE: (SelectionMode.VERTEX, [verts[0]]),
    }


OPS = [CContext.SPLIT, CContext.EDGE_CONNECT, CContext.VERTEX_CONNECT, CContext.KNIFE]


def report(name, ok, detail=""):
    print(f"[{'OK ' if ok else 'BAD'}] {name}{(' — ' + detail) if detail else ''}")


# -- P1: T-G2a/b/d on the real Application ------------------------------------------------


def p1():
    print("\n== P1 G-2 emulation: listed / unlisted per context (T-G2a, T-G2b, T-G2d)")
    for ctx in OPS + [CContext.NONE]:
        for listed in (True, False):
            if ctx is CContext.NONE and listed:
                continue
            # baseline without gate
            base = fresh_cube()
            mode, ids = context_selections(base)[ctx]
            select(base, mode, ids)
            assert _real_resolve(base.selection) is ctx, (ctx, _real_resolve(base.selection))
            rb = base.key_press(C)
            base_after = (rb, base.status_message, snapshot(base))

            app = fresh_cube()
            select(app, mode, ids)
            texts = {c: f"refused {c.name}" for c in OPS} if listed else {}
            if not listed:
                texts = {c: f"refused {c.name}" for c in OPS if c is not ctx}
            app.command_gate = G2Gate(refused_contexts=texts)
            before = snapshot(app)
            serial = app.status_serial
            RESOLVE_CALLS[0] = 0
            r = app.key_press(C)
            calls = RESOLVE_CALLS[0]
            if listed:
                ok = (
                    r is False
                    and app.status_serial == serial + 1
                    and app.status_message == f"refused {ctx.name}"
                    and snapshot(app) == before
                    and calls == 1
                )
                r2_serial = app.status_serial
                app.key_press(C)
                ok = ok and app.status_serial == r2_serial + 1
                report(f"{ctx.name} listed", ok, f"ret={r} calls={calls} knife={app.knife_active}")
            else:
                same = (r, app.status_message) == base_after[:2] and snapshot(app)[2:] == base_after[2][2:]
                report(f"{ctx.name} not listed (others listed)", same and calls == 1,
                       f"ret={r} status={app.status_message!r} calls={calls}")
    try:
        G2Gate(refused_contexts={CContext.NONE: "x"})
        report("NONE construction raises", False)
    except ValueError:
        report("NONE construction raises", True)


# -- P2: order (T-G2c) ----------------------------------------------------------------------


def p2():
    print("\n== P2 order: identity before context, armed check before context (T-G2c)")
    app = fresh_cube()
    mode, ids = context_selections(app)[CContext.SPLIT]
    select(app, mode, ids)
    app.command_gate = G2Gate(refused={cmd.CONNECT: "identity"}, refused_contexts={CContext.SPLIT: "ctx"})
    RESOLVE_CALLS[0] = 0
    r = app.key_press(C)
    report("Connect in refused + ctx listed → identity text", r is False and app.status_message == "identity" and RESOLVE_CALLS[0] == 0)

    app.command_gate = G2Gate(allowed=frozenset({cmd.MOVE}), not_allowed_text="na", refused_contexts={CContext.SPLIT: "ctx"})
    RESOLVE_CALLS[0] = 0
    r = app.key_press(C)
    report("Connect outside allowed → not_allowed_text", r is False and app.status_message == "na" and RESOLVE_CALLS[0] == 0)

    app.command_gate = G2Gate(refused_contexts={CContext.SPLIT: "ctx"})
    armed = app.key_press(WKEY)
    status = app.status_message
    RESOLVE_CALLS[0] = 0
    r = app.key_press(C)
    report("W armed + C → armed check first", armed and r is False and app.status_message == status and RESOLVE_CALLS[0] == 0,
           f"armed={armed} owner={app.interaction_owner}")


# -- P3: Knife session unaffected (T-G2e) ----------------------------------------------------


def p3():
    print("\n== P3 Knife session: a gate listing every context changes nothing (T-G2e)")
    results = []
    for gated in (False, True):
        app = fresh_cube()
        select(app, SelectionMode.VERTEX, [])
        app.key_press(C)
        assert app.knife_active
        if gated:
            app.command_gate = G2Gate(refused_contexts={c: "x" for c in OPS})
        seq = [key("e"), key("z", "ctrl"), C, key("ENTER"), ESC]
        out = []
        for k in seq:
            out.append((app.key_press(k), app.status_message, app.knife_active))
        results.append(out)
    report("Knife key sequence identical with and without gate", results[0] == results[1], str(results[1]))


# -- P4: fail-closed BLOCK row in the Lab (T-FC1, T-FC2) --------------------------------------

NON_OPERATION = frozenset({
    cmd.CYCLE_DISPLAY_MODE, cmd.TOGGLE_WIREFRAME_OVERLAY, cmd.SET_SHADED, cmd.SET_FLAT_SHADED, cmd.SET_WIREFRAME,
    cmd.SELECT, cmd.SELECT_ADD, cmd.SELECT_REMOVE, cmd.SELECT_TOGGLE, cmd.CLEAR_SELECTION,
    cmd.SET_VERTEX_MODE, cmd.SET_EDGE_MODE, cmd.SET_FACE_MODE,
    cmd.UNDO, cmd.REDO, cmd.CANCEL,
    cmd.CONSTRAIN_AXIS_X, cmd.CONSTRAIN_AXIS_Y, cmd.CONSTRAIN_AXIS_Z,
    cmd.CONSTRAIN_PLANE_XY, cmd.CONSTRAIN_PLANE_XZ, cmd.CONSTRAIN_PLANE_YZ,
})
DECLARED_COMMANDS = frozenset({cmd.DELETE, cmd.DISSOLVE, cmd.DISSOLVE_NO_CLEANUP})  # illustration
DECLARED_CONTEXTS = frozenset({CContext.EDGE_CONNECT, CContext.VERTEX_CONNECT})       # illustration
GENERIC = "Symmetrie aktiv — Befehl nicht koordiniert (BLOCK: nicht gestartet)"
OPERATION_COMMANDS = frozenset({  # "known operation commands" — my reading of the pseudocode
    cmd.CONNECT, cmd.DELETE, cmd.DISSOLVE, cmd.DISSOLVE_NO_CLEANUP, cmd.MOVE, cmd.ROTATE, cmd.SCALE,
    cmd.SPLIT_EDGE, cmd.COLLAPSE, cmd.LOOP_INSERT, cmd.LOOP_SLIDE, cmd.EXTRUDE, cmd.ARTICULATION_RESTORE,
})


def all_commands():
    return sorted(v for n, v in vars(cmd).items() if n.isupper() and isinstance(v, str))


def fail_closed_row():
    transforms = {c for c in lab_app.TRANSFORM_OPERATIONS if lab_app.supports_symmetry(c)}
    allowed = set(NON_OPERATION) | DECLARED_COMMANDS | transforms
    if DECLARED_CONTEXTS:
        allowed.add(cmd.CONNECT)
    refused = {c: lab_app.block_text(c) for c in OPERATION_COMMANDS - allowed}
    if not DECLARED_CONTEXTS:
        refused[cmd.CONNECT] = lab_app.block_text("C")
    rc = {c: lab_app.block_text(c.name) for c in OPS if c not in DECLARED_CONTEXTS}
    gate = G2Gate(refused=refused, allowed=frozenset(allowed), not_allowed_text=GENERIC, refused_contexts=rc)
    return lab_app.GateRow("BLOCK fail-closed (emulated)", gate)


def p4():
    print("\n== P4 fail-closed BLOCK row (emulated) in the Lab")
    lab_app.block_row = fail_closed_row  # gate_row_for() looks it up at call time
    unbound_key = key("F9")
    print("  commands refused by the allow-list (not in NON_OPERATION ∪ declared ∪ Lab), bound to F9 in GLOBAL:")
    for command in all_commands():
        if command in NON_OPERATION | DECLARED_COMMANDS | {cmd.CONNECT, cmd.MOVE, cmd.ROTATE, cmd.SCALE}:
            continue
        rows = {}
        for sym in (False, True):
            app, lab = build_app_lab("subd_cube", W, H)
            if sym:
                lab_key_press(app, lab, key("s", "shift"))  # → X, BLOCK by default
                assert lab.axis == "X" and lab.gate_mode is lab_app.GateMode.BLOCK
            app.bindings.bind(unbound_key, command)
            serial = app.status_serial
            r = lab_key_press(app, lab, unbound_key)
            rows[sym] = (r, app.status_serial - serial, app.status_message if app.status_serial != serial else "")
        print(f"    {command:22s} sym off: {rows[False]}   sym on BLOCK: {rows[True]}")


def p4b():
    print("\n== P4b NON_OPERATION behaves as with symmetry off (T-FC2 subset, keys)")
    keys = [
        ("1", ()), ("2", ()), ("3", ()), ("a", ("alt",)), ("z", ("ctrl",)), ("y", ("ctrl",)),
        ("x", ()), ("y", ()), ("z", ()), ("x", ("shift",)), ("y", ("shift",)), ("z", ("shift",)),
        ("d", ()), ("d", ("shift",)),
    ]
    for value, mods in keys:
        out = {}
        for sym in (False, True):
            app, lab = build_app_lab("subd_cube", W, H)
            if sym:
                lab_key_press(app, lab, key("s", "shift"))
            k = key(value, *mods)
            command = app.bindings.command_for(k)
            r = lab_key_press(app, lab, k)
            out[sym] = (command, r, app.status_message if sym else app.status_message)
        same = out[False][1] == out[True][1]
        print(f"    {'+'.join(mods + (value,)):10s} {out[False][0]!s:22s} off={out[False][1:]} on={out[True][1:]} {'' if same else '  <-- differs'}")
    # Esc disarming W under BLOCK
    app, lab = build_app_lab("subd_cube", W, H)
    lab_key_press(app, lab, key("s", "shift"))
    vid = sorted(app.scene.mesh.all_vertex_ids())[0]
    app.selection.add({vid})
    armed = lab_key_press(app, lab, WKEY)
    r = lab_key_press(app, lab, ESC)
    report("Esc disarms W under emulated fail-closed BLOCK", armed and r and app.transform_command is None,
           f"status={app.status_message!r}")
    # click select under BLOCK
    sx, sy = app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), W, H)
    lmb = Input("mouse", "LEFT")
    app.key_release(WKEY)
    app.selection.clear()
    app.pointer_press(lmb)
    r = app.pointer_release("LEFT", sx, sy)
    report("LMB click selects under emulated fail-closed BLOCK", True,
           f"ret={r} selection={sorted(app.selection.vertices)[:3]} status={app.status_message!r}")


# -- P5: A2 canonicalisation decides the G-2 key and text -----------------------------------


def p5():
    print("\n== P5 two-sided edge selection: literal vs. canonical context (A2 = A)")
    app, lab = build_app_lab("subd_cube", W, H)
    lab_key_press(app, lab, key("s", "shift"))
    mesh = app.scene.mesh
    index = build_index(mesh)
    pair = None
    for e in sorted(mesh.all_edge_ids()):
        p = index.edge_partner(e) if callable(getattr(index, "edge_partner", None)) else None
        if p is not None and p != e:
            fa = set(mesh.edge_faces(e)) if hasattr(mesh, "edge_faces") else set()
            fb = set(mesh.edge_faces(p)) if hasattr(mesh, "edge_faces") else set()
            if not (fa & fb):
                pair = (e, p)
                break
    select(app, SelectionMode.EDGE, pair)
    literal = _real_resolve(app.selection)
    canon = canonical_edges(index, pair)
    tmp = type(app.selection)()
    tmp.mode = SelectionMode.EDGE
    tmp.add(set(canon))
    canonical = _real_resolve(tmp)
    print(f"    edges {pair}: literal context {literal.name}, canonical {sorted(canon)} → {canonical.name}")
    row = fail_closed_row().gate
    print(f"    G-2 on literal  → {'refused: ' + row.refused_contexts[literal] if literal in row.refused_contexts else 'runs (declared)'}")
    print(f"    G-2 on canonical→ {'refused: ' + row.refused_contexts[canonical] if canonical in row.refused_contexts else 'runs (declared)'}")
    print(f"    today (no G-2, MARK/without gate): key_press(C) → ", end="")
    app.command_gate = None
    print(app.key_press(C), repr(app.status_message))


if __name__ == "__main__":
    p1()
    p2()
    p3()
    p4()
    p4b()
    p5()
```
