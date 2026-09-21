# AD-015 — Playground Input Ownership: Tweak vs. Transform on Q/W/E

**Status:** DECIDED ✓
**Date:** 2026-09-21
**Owner:** Manu (Project Owner)
**Scope:** Playground input dispatch (`playground/window.py::on_key_press`), Tweak family, Transform family

---

## Question

Tweak (`tweak` slot, variants V1/V3) and Transform (`transform` slot) both use Q/W/E. When both can respond, who owns the key at a given moment?

## Context / Evidence

Verified directly against `playground/window.py` (main, 2026-09-21):

- `tweak` and `transform` are already two separate registered families (`app.register_slot(trans_slot, "transform")`, `app.register_slot(tweak_slot, "tweak")`). The conflict is not caused by mixing variants inside one family.
- The Q/W/E branch in `on_key_press` does **not** consult `app.focused_family` at all. It instead runs a hardcoded, unconditional check: if `_active_tweak_variant()` is `"v1"` or `"v3"`, Tweak claims the key and the Transform activation logic is skipped entirely — regardless of what else is happening (e.g. a Gizmo handle already clicked). `app.active_tool` stays `None` as a result.
- `focused_family` is only consulted by Tab (family cycling), M/Shift+M (variant cycling within the focused family) and the Articulation mouse-press branch — not by Q/W/E, not by X/Y/Z, not by K.
- Tweak V2/V4 do not use Q/W/E at all (Ctrl+LMB / Ctrl+Move), so they are unaffected by this decision.

### External precedent

Blender's modal operators (Grab/Rotate/Scale) take over the window's event stream exclusively for the duration of the interaction and release it on `FINISHED`/`CANCELLED`; while one is running, no other keymap entry is evaluated. Ownership is decided by "is an interaction currently running", not by a separately-selected focus/context. Blender's "Keys Activate Tools" preference is a separate, opt-in layer on top of this — it does not replace the underlying exclusivity mechanism.

## Decision

**Key ownership on Q/W/E is resolved by runtime interaction state, not by `focused_family`.**

Tweak (V1/V3) claims Q/W/E only if no transform-owning interaction is already active. If a transform-owning interaction is already active (`app.active_tool is not None`, or an active Gizmo drag), Tweak backs off instead of silently consuming the key.

`focused_family` / Tab remains what it already is: a family-focus mechanism for the keys that already use it (Tab cycling, M/Shift+M). It is deliberately **not** extended to gate Q/W/E, X/Y/Z or K, because:

- Tweak's design intent (2026-09-13, SelectMethod-variant decision) is explicitly "usable immediately, no mode switch required." Requiring Tab before Q/W/E could trigger a Tweak gesture would contradict that intent.
- X/Y/Z/K are parameters of whatever transform-capable interaction is currently running, not mode switches. They must stay live regardless of `focused_family`, since Tweak itself is designed to be focus-independent.

## Relationship to AD-013

This decision implements AD-013 invariants **I3** (one interaction authority owns start and end) and **I4** (exactly one binding authority at a time) for the one concrete case where they were not yet honored. It does not reopen AD-013 A3 (Press/Hold as a global rule, still open) — ownership (*who* gets the key) and gesture semantics (*how* a gesture begins/ends once owned) are treated as separate questions, and A3 can be decided independently later without revisiting this AD.

## Non-Goals

This AD does not:

- change `focused_family` / Tab / M-Shift+M behavior;
- gate X/Y/Z or K on `focused_family` or on any new mechanism;
- change the selection-mode-gated keys (I, C, Shift+C, S, R, G, Shift+R, Shift+L);
- decide AD-013 A3 (Press/Hold);
- touch the Gizmo itself (WP-AP-GIZMO-01/02/03) or AD-012/AD-014 Transform Space;
- introduce a new input framework. A single ownership check at the existing Q/W/E branch is sufficient.

## Engineering Freedom

The exact implementation of "is a transform-owning interaction already active" (a direct `app.active_tool is not None` check, a small explicit ownership flag, or an equivalent) is left to implementation. The invariant that must hold is: **Tweak (V1/V3) must not claim Q/W/E while a transform-owning interaction is already running.**

## Consequences

### Positive

- Fixes the concrete Gizmo-click bug without introducing a new framework or a Tab requirement.
- Keeps Tweak's "instant, no mode switch" design intent intact.
- Brings this one case in line with AD-013 I3/I4; other keys are unaffected because no conflict has been demonstrated there yet.

### Costs

- Ownership is now decided by runtime state read at two points (Tweak's key handler and wherever a transform interaction is started/ended) instead of one static precedence check. Both sides must agree on what "active" means.

## Canonical Product Truth

> **Tweak (V1/V3) darf Q/W/E nur beanspruchen, wenn keine Transform-Interaktion bereits aktiv ist. Ist eine aktiv, tritt Tweak zurück statt die Taste stumm zu schlucken. `focused_family` bleibt auf die Tasten beschränkt, die es heute schon nutzen (Tab, M/Shift+M) und wird nicht auf Q/W/E, X/Y/Z oder K ausgeweitet.**
