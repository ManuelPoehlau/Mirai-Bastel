# AD-016 — Transform Owns Q/W/E, One Current Tool, Gizmo as Entry Point

**Status:** DECIDED ✓ (ownership model) · the new activation variant is a Playground experiment awaiting Artist verdict
**Date:** 2026-09-21
**Owner:** Manu (Project Owner)
**Supersedes:** AD-015 (partial fix, see its addendum)
**Evidence:** `docs/design/artist_playground/INPUT_OWNERSHIP_AUDIT.md`
**Relates to:** AD-013 (I3, I4, I5; A3 remains open)
**Scope:** Artist Playground only (`playground/`). No `src/` changes.

---

## Problem (from the audit)

1. Tweak V1/V3 claim Q/W/E. Because they never set `app.active_tool`, the AD-015 back-off never fires. Transform is unreachable by keyboard under V1/V3 — by omission, not by policy.
2. There are two independent "current tool" states: `_tweak_persistent_mode` (Tweak) and `app.active_tool` (Transform).
3. The Gizmo cannot start an interaction. It only sets a constraint on an already-armed transform, and is dead under V1/V3.
4. Input winners are largely decided by branch order and incidental flags.

## External precedent

- **Blender:** keys choose the transform tool (Industry Compatible: W/E/R = Move/Rotate/Scale tools, Q = select tools); the Tweak tool lives on the mouse (press = select, drag = move). Dragging a gizmo arrow moves along that axis.
- **Wings3D:** regular transforms via RMB menu; Tweak is a toggled mode on LMB, the tweak tool chosen by Ctrl/Shift/Alt combinations.
- Neither puts Tweak on the transform tool keys.

## Decision

### D1 — Transform is the single owner of Q/W/E
No Tweak variant claims Q/W/E. (AD-013 I3/I4.)

### D2 — One current tool
There is exactly one "current transform tool" state (move / rotate / scale). Q/W/E set it. Transform, Gizmo and Tweak all read the same state. `_tweak_persistent_mode` is merged into it; no parallel copy remains.

### D3 — Gizmo is an entry point (Artist verdict, 2026-09-21)
- **LMB click on an axis handle (no drag):** sets the axis constraint only — equivalent to pressing X/Y/Z. Works whether or not a tool is armed.
- **LMB click + drag on an axis handle:** sets the constraint and executes the **current tool** along it; **LMB release commits**.
- If no tool has been chosen yet, the current tool defaults to Move *(engineering default, not an Artist statement)*.
- A hit on a gizmo handle takes priority over selection clicks at that position; a miss falls through unchanged.

*Addendum 2026-09-23 (WP-STAB-03 Session Gate):* while a Transform session is already live, a handle
click sets the constraint only — the running Transform executes the drag (and Press-Drag-Click's LMB
release commits it); no second Gizmo tool is armed. Outside a Transform the behavior above is unchanged.
See `docs/design/artist_playground/INPUT_OWNERSHIP_AUDIT.md` (Addendum 2026-09-23).

This lifts the WP-AP-GIZMO Phase-1 boundary ("a Gizmo click does not choose/start a tool") by explicit Artist decision.

*Addendum 2026-10-21 (Manu: "Gizmo nach `src/` heben"):* D3 is implemented in the production app — `mirai.viewport.gizmo`, `Application` (press / drag / release as the Tweak machinery on the selection, world frame only; hidden while a gesture runs; no modifier), drawn by `src/main.py`. `PROVISIONAL`; see [WP Playground-Werkzeuge, Nachtrag](../WP_PLAYGROUND_TOOLS_PROMOTION.md#nachtrag-2026-10-21-lasso-und-gizmo-in-die-app-manu). The Playground keeps its own wiring and the normal-space frames.

*Addendum 2026-10-28 (Manu A1/A4/A5; engineering E1–E5 `PROVISIONAL`, Discovery):* in the production app the axis
constraint is **one-shot** by default — the commit of the Move / Rotate / Scale gesture that used it clears it, Esc and a
tap keep it (sticky = the B4.1 behaviour, kept as a session switch on F7 for the comparison). For D3 this means: a handle
**click** sets the one-shot constraint (still "equivalent to pressing X/Y/Z"); a handle **drag** is constrained for that
drag only (commit clears; Esc restores what was pending before the press). Inside a handle's pick zone the handle also
wins the **hover** over the mesh (no mesh highlight under it); the centre circle is picked over its filled disc; hover on
the active handle has its own state. Gizmo sizes S/M/L are a session switch (F8). The tool contract (`space` fixed at
`begin()`) and AD-022 are unchanged. See [WP Playground-Werkzeuge, Nachtrag 2026-10-28](../WP_PLAYGROUND_TOOLS_PROMOTION.md#nachtrag-2026-10-28-achse-einmalig-tweak--halte-geste-gizmo-kleiner-manu).

### D4 — New Transform activation variant: "Hold-Key Hover" (Playground experiment)
Artist proposal (2026-09-21), implemented as an additional variant in the `transform` slot, selectable alongside the existing ones:
- **Tap Q/W/E (movement below `CLICK_THRESHOLD`):** sets the current tool. No execution.
- **Hold Q/W/E + move mouse + release key:** executes the chosen tool and commits on key release.
- **Target:**
  - If a selection exists → the **selection** is transformed, regardless of what is under the cursor *(Artist verdict: "like Blender G")*.
  - If nothing is selected → the element under the cursor at key-press time is the target (temporary selection, cleared after commit/cancel — reuse the existing Tweak temp-target mechanism).
  - Target is captured once at key press and not re-evaluated during the drag (consistent with the 2026-09-13 Tweak decision).
- Esc cancels as today.

This is the former V1 behavior, re-owned by Transform. Its product value is not yet validated → Artist verdict pending (KEEP / ITERATE / REJECT / UNKNOWN).

### D5 — Tweak family after this change
- **V1:** moved into Transform as D4 (ITERATE, behavior preserved).
- **V2 (Ctrl+LMB), V4 (Ctrl+move):** remain Tweak; they read the shared current tool (D2).
  *Production 2026-10-28 (Manu A2/A3):* V2's Ctrl+LMB-drag binding is removed from the app (`config/keymap.json` and the
  code default; the `Tweak` command stays bindable). In user-facing text "Tweak" now names the hold-key gesture (D4:
  W/E/R held + mouse).
- **V3 (hold key + LMB):** conflicts with D1. **Parked** — code kept, removed from the selectable Tweak variants until the Artist decides. Not deleted.

## Not decided here
- AD-013 A3 (Press/Hold as a global rule). D4 is one variant, not a global rule.
- Whether V3 returns in another form.
- Wings-style modifier-chooses-tool for Tweak (idea only).
- Distinct gizmo shapes for Rotate/Scale (next gizmo step).
- Any `src/` / production binding (AD-013: capability promotion ≠ UX promotion).

## Consequences
**Positive:** one owner per key; one current tool; the gizmo works under every Tweak variant; V1's feel is preserved and becomes comparable against the other Transform variants.
**Costs:** V3 temporarily unavailable; Tweak V2/V4 depend on shared Transform state; the transform dispatch gains one variant.

## Canonical Product Truth
> **Q/W/E gehören Transform und wählen das Werkzeug. Es gibt genau ein gewähltes Werkzeug. Ein Klick auf eine Gizmo-Achse setzt nur den Constraint; Klick + Ziehen führt das gewählte Werkzeug entlang der Achse aus, Loslassen committet. In der Variante „Hold-Key Hover" bewegt Halten + Ziehen + Loslassen die Auswahl; nur ohne Auswahl wird das Element unter der Maus genommen.**

**Note (2026-09-26):** The Artist Input Truth for transform bindings changed outside Playground scope (`transform.move/rotate/scale` → W/E/R, see AD-013's 2026-09-26 addendum). Playground/AD-016 still uses Q/W/E — recorded there as an open, unresolved discrepancy, not decided or closed here.
