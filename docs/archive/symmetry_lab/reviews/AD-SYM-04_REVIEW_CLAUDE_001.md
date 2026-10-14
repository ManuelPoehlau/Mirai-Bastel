# Independent Review — AD-SYM-04 "Symmetry in the Production app, then symmetric Soft" (PROPOSED)

> **Reviewer:** Claude (claude.ai/code, fresh session, no prior chat or plan context)
> **Review ID:** CLAUDE-001
> **Target path:** `docs/archive/symmetry_lab/reviews/AD-SYM-04_REVIEW_CLAUDE_001.md`
> **Repository state reviewed:** `claude/sweet-ritchie-tfv9xq` @ `2da6d11` (code read at `54de6ee`, as the AD does)
> **Subject:** `docs/architecture/AD-SYM-04-SYMMETRY-IN-PRODUCTION-APP.md` (PROPOSED, 2026-10-14)
> **Type / Mode:** Type B (review only) · Discovery · no source, plan or AD edited
> **Status:** Archived first-pass review — preserved verbatim
>
> This document is intentionally preserved as the original independent review. Do not edit it to
> reflect later decisions. Answers to the findings belong in the AD's §9 "Review".

---

## What was read, what was run

Read: AD-SYM-04 (whole), AD-013 (Artist Decisions A1–A5, Invariants I1–I8, Addendum H2 rules
H2-R1…H2-R6 and the G-2 amendment's "Consequences" and test table), `src/mirai/application.py`
(`dispatch_command`, `key_press`, `_knife_key`, the symmetry sites the AD cites),
`src/mirai/interaction/routing.py`, `bindings.py`, `src/core/operations/transform.py`
(`VertexTransformOperation`, `_PivotTransformOperation`, `rotation_keeps_plane`, `scale_keeps_plane`,
`_check_seam_step`), `src/core/mesh.py` (definition storage), `src/main.py` (imports, `GL_TYPES`,
status line), `tests/test_command_gate_contexts.py` (T-G3b), `experiments/symmetry_lab/lab_app.py`
(`NON_OPERATION`, `block_row`), `lab_overlays.py` (class bases), `lab_symmetry.py` (E3),
`playground/input_adapter.py`, `playground/command_handler.py` (`SAFE_COMMANDS`).

**Not read:** AD-SYM-01/02/03 beyond what AD-SYM-04 quotes, AD-020, CORE_V1_FREEZE,
REFERENCE_HARDWARE. Claims that rest only on those are not checked here.

**Run:** nothing. No test was run; every check below is by reading code at the cited lines.

---

## Verdict

**ACCEPT WITH CHANGES.** The inventory is accurate and the central reading holds. Setting a
definition is mesh state, not gate data, so H2-R6 needs no change. H2-R5's G-2 half does need an
amendment. Three findings should be fixed **before Manu answers Q-1…Q-4**, because they change
what he is asked or what the amendment says: R-1 (Q-4 is incomplete), R-2 (the T-G3b wording is
false under S-2/S-3) and R-3 (the Lab's BLOCK row would refuse the app's own toggle). The rest can
go into the slice plans.

---

## Confirmed

| AD item | Check | Result |
|---|---|---|
| §1.1 consequence (I-5…I-8) | `dispatch_command` routes only MOVE/ROTATE/SCALE/EXTRUDE to tools (`routing.py:26-31`), plus Undo/Redo, display, soft, mode, Connect and removal commands; everything else ends in `return False`. Each mutating path is coordinated or refused with a definition set. | **Holds.** No handled command runs one-sided today. |
| I-11 | `grep -c "Shift+S" src/mirai` | **17**, in `symmetric_ops.py`, `symmetric_extrude.py`, `symmetric_knife.py`. |
| I-1 | `core/mesh.py:121`, `:1098`, `:1163` | Holds. |
| G-1 / G-3 | H2-R5 defines "gate data" as `command_gate`, `hover_suspended`; H2-R6 (both versions) speaks only of that value. | **Holds.** Writing `mesh.symmetry_definition` is not writing the gate. |
| G-2 | Separate `Application` instances; with `command_gate is None` H2-R5's default case applies. | Holds. |
| G-4 | T-G3b scans only `src/main.py` (`tests/test_command_gate_contexts.py:502-506`). | **Holds**, and the point that moving the writer into `Application` would pass the guard while defeating its purpose is correct. See R-2 for the consequence the AD misses. |
| G-5 | AD-013 `:434-436`, `:476` | Text as quoted. |
| G-6 | H2-R1's start-up assert | Holds. R-3 adds the BLOCK-row half that G-6 does not cover. |
| A5 / I7 | AD-013 `:197-201`, `:239-241` | The citation is correct: promotion carries no keys or UX. |
| §4 "stops before a design" | §4.2 names locations and §4.3 names risks; neither proposes a mechanism. | **Holds**, except that option P-a in D-3 implies a Core rule change §4 does not list (R-1). |

---

## Findings

### R-1 (major) — Q-4 and C-4 omit the seam *axis/factor* rule; P-a is a Core rule change

The AD treats "seam vertex affected" as a pivot question only. But `_PivotTransformOperation`
refuses in two places:

- `_on_begin`: any seam id with the pivot off the plane → `SeamConstraintError` (`transform.py:338-341`).
- `_on_update` → `_check_seam_step` on **every step**: Rotate is refused unless the axis is parallel to
  the plane normal (`rotation_keeps_plane`, `:160-166`, `:382-387`). Scale is refused unless it is
  uniform or aligned with the normal (`scale_keeps_plane`, `:169-185`, `:411-416`).

Under Soft, any gesture whose falloff reaches the middle carries seam ids. So:

- **P-b** ("the pivot jumps to the pair midpoint") still refuses every soft Rotate whose axis is not
  the plane normal, and every non-uniform soft Scale that is not along the normal. That covers most
  rotations once the radius crosses the middle. Q-4 as worded hides this; Manu would choose P-b
  expecting the gesture to run.
- **P-a** ("falloff-reached seam vertices slide in the plane") needs those vertices exempt from
  **both** checks. C-4's statement "`_check_seam_step` stays valid" is true only for P-b/P-c. P-a
  therefore changes the Core's seam rule, not only its weighting. That belongs in SS1's scope and its
  review (R-5), and in §4.2's "smallest opening".

The symmetry argument for P-a holds. A seam vertex p is its own mirror, and the projections of
R(p) and mirror(R(p)) onto the plane are identical. So projection without the axis check stays
exactly symmetric.

**Change:** in C-4, name the step check as well. In D-3, say that P-a exempts falloff-reached seam
vertices from the begin check and the step check (a Core rule change in SS1). Reword Q-4 so that P-b
reads as "the pivot jumps to the middle, and rotating about any axis other than the mirror axis is
refused".

### R-2 (major) — T-G3b cannot just be "re-labelled" under S-2/S-3

§2.3 proposes: "`src/main.py` itself still … contains no symmetry code; T-G3b keeps guarding
`src/main.py` and is re-labelled accordingly". A2 follows the soft-band precedent: a GL type handed in
through `GL_TYPES` in `src/main.py` (`main.py:157`, `:167-173`). The Lab's overlays are GL subclasses
(`SymmetryPlaneOverlay` draws with pyglet GL; `SymmetryStateOverlay(GLPointOverlay)`,
`lab_overlays.py:179`, `:306`). Moved into `src/`, the new type has to be imported in `src/main.py`.
T-G3b then fails, because it flags any `ImportFrom` whose module or imported name contains
"symmetry" (`test_command_gate_contexts.py:492-497`).

The AD's own G-4 rule applies here. Renaming the module so that it avoids the word would pass the
guard without keeping the rule.

**Change:** under S-2/S-3, the amendment says T-G3b is **narrowed**, and states to what. Proposed:
`src/main.py` never assigns `symmetry_definition` and calls no correspondence or coordination
function; importing one GL overlay type for `GL_TYPES` is allowed. The sentence "contains no symmetry
code" is dropped. Under S-1 the AD's wording stands.

### R-3 (major) — the Lab's BLOCK row would refuse the app's symmetry command

Under E-1 (and with any app key), the toggle becomes a `mirai.interaction.commands` constant that
`Application.key_press` dispatches. The Lab's `block_row()` (`lab_app.py:306-336`) allows only
`NON_OPERATION` ∪ declared removal/extrude commands ∪ `Connect` ∪ transforms with
`supports_symmetry`. The new command is in none of these, so it gets `BLOCK_NOT_ALLOWED_TEXT`.
BLOCK is the Lab's default whenever symmetry is on, so in the Lab Shift+S could switch symmetry on
but never cycle it or switch it off. T-FC1 also iterates "every command constant … in neither
`NON_OPERATION` nor the declarations nor the Lab commands" and would expect the command refused.

G-6 covers only the binding assert (H2-R1), not the row.

**Change:** add a constraint K-6. The Lab's BLOCK and MARK rows allow the app's symmetry command
explicitly; the preview row keeps refusing it (H2-R2). T-FC1 and T-R1a are adjusted in A1. The command
should not go into `NON_OPERATION` silently, because it changes mesh state. Either the constant's
comment says why it is allowed, or it gets its own named entry in the row.

### R-4 (medium) — A1's tests miss the interaction gates of the new command

`key_press` ignores `C`, Delete, Backspace and the mode keys while W/E/R/T is armed
(`application.py:1587-1603`, the `_transform_key is not None` branches). A definition toggled between arm and
`begin()` would change the partner sets that the armed tool resolves at `begin()`. The new command
needs the same gate, and A1 should test it: it is ignored while a transform is armed or running, and
the status says so. During a Knife session it is already ignored (`_knife_key` returns `False` for
unknown commands, `:1129-1146`); a test should pin that too. With Soft armed, the existing refusal at
`begin()` (`:1715`) covers the case, which is worth one test.

### R-5 (medium) — F-a is a test, not a governance mechanism, but its oracle needs work

F-a writes and reads no gate, so it is not a new mechanism. As specified, though, it has three
problems:

1. **It needs a command classification.** The only one is the Lab's `NON_OPERATION`
   (`lab_app.py:132`). If `tests/` imports it, Production depends on the Lab; a copy would be a second
   list, which the G-2 amendment rules out.
2. **Unhandled commands fail its oracle.** `Application` returns `False` and posts no status for the
   constants it does not handle (Collapse, EdgeLoop, SplitEdge, …; `dispatch_command` ends in
   `return False`). "Nothing changed and a refusal status posted" fails for them at once.
3. **It sees only the key path.** Host calls to `dispatch_command(…, context=…)` (Pattern B) and
   `apply_mesh_change` are outside it.

**Suggestion:** use an oracle that needs no classification. For every command constant bound by a
test GLOBAL binding, on a symmetric fixture with a definition set: if the mesh changed, completeness
is unchanged; and if the command was handled and refused, a status was posted. A newly wired
one-sided tool fails this, and no command list exists. The coverage limit (selection-dependent paths)
stays as the AD states it. Point 3 should be stated as a known gap.

### R-6 (minor) — the geodesic half of the D-1 reading needs a precondition

The Euclidean argument is sound. The geodesic one ("reflect the part of a path beyond the plane")
holds only if every edge path across the plane passes through a vertex **on** the plane. Take an edge
(a, b) that straddles the plane, with neither end on it (an odd segment count across the axis).
Reflecting the s→a part of a path s→a→b→p gives s'→a', but a'–b need not be an edge, so the mirrored
seed's path is not guaranteed to be no longer. The one-weight-per-pair rule keeps the result
symmetric anyway, but "the field equals each side's own field" can fail.

**Change:** state the precondition. SS0 should include a mesh with straddling edges, or record that
E3 meshes always have a seam loop.

### R-7 (minor) — C-3: the Core loop already combines category and weight

"Neither side does both" is not quite right. `VertexTransformOperation._on_update` calls
`_transform_position` (conjugate, projection) and then blends with `_weights`
(`transform.py:261-270`). Because mirroring is affine, the blend of a partner's conjugate step is the
conjugate of the blended step. For a seam vertex, the blend of two on-plane points stays on the plane.

What is missing is semantics, not composition. The placeholder blends positions linearly, while
AD-020's soft ops use w·θ, 1 + w(F−1) and absolute Scale. Saying this narrows SS1: it replaces the
placeholder's blend; it does not have to invent the meeting point.

### R-8 (minor) — the Playground is out of reach, but say so

A new constant with a default binding in `build_default_bindings()` also reaches the Playground's
resolver (`playground/input_adapter.py:107`). Its `SAFE_COMMANDS` whitelist
(`command_handler.py:62-68`) drops the command, so the Playground cannot set a definition. That is
correct and should be stated as a constraint. The Playground's topology tools mutate the mesh outside
the coordinators; adding the command to `SAFE_COMMANDS` would make them run one-sided. That would be
the "second user" H2-R6 asks to review.

### R-9 (nit) — one line reference

I-2 cites `init_scene`/`load_scene` as `application.py:629-680`. `init_scene` is at `:537`, and
629-680 is `load_scene` only. The other `application.py` line numbers checked (277, 419, 874, 897,
913, 1073, 1522, 1652, 1715, 1856, 1928, 2087, 2222, 2234) match.

---

## Answers to §9's four questions

1. **G-1…G-6 against AD-013:** they hold (table above). G-4 has an unlisted consequence under
   S-2/S-3 (R-2), and G-6 has a row half (R-3).
2. **Is F-a "a new governance mechanism"?** No, it is a test. As specified, though, it needs either a
   second command list or a Lab import (R-5). The suggested oracle avoids both.
3. **The D-1 reading:** sound for Euclidean distance. For geodesic distance it needs the
   "no straddling edges" precondition (R-6). Symmetry of the result is safe either way through the
   one-weight-per-pair rule.
4. **Does §4 stop before a design?** Yes. But D-3's P-a implies a Core seam-rule change that §4 does
   not list (R-1), and C-3 understates what the Core loop already does (R-7).
