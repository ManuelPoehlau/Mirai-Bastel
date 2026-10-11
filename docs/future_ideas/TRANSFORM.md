# Future Ideas – Transform

Ideen und Beobachtungen rund um Transform, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten.

## Multi-Element Tangent-Basis Derivation (Deferred per AD-012 Amendment, WP-03C)

**Status**: Deliberately not implemented in WP-03C; single-face only.

WP-03C (commit a12f457) implements tangent basis derivation for **single-face 
selections only** — `space="normal", axis="x"/"y"` works for exactly one 
selected face, raises `ValueError` for multi-face or non-face selections.

Multi-element selections fall back to `selection_normal()`'s existing averaging:
- `space="normal", axis="z"` / `None`: works (returns averaged normal)
- `space="normal", axis="x"` / `"y"`: raises (no stable tangent for multiple faces)

**Why deferred**:
- Blender's own multi-element Normal orientation is a long-standing, unresolved 
  UX complaint (reference: https://developer.blender.org/T62124)
- No reference precedent for "correct" multi-face tangent behavior (row-vs-column 
  winding? averaged? principal axes? something else?)
- Requires real Playground research to settle on a convention, not hypothetical 
  design

**Next step**: Gather use cases and artist feedback during Playground 
experimentation with single-face basis (WP-03C validates the infrastructure 
works). Revisit only after concrete patterns emerge.

## Tangent-Plane Movement (Deferred per AD-012)

**Status**: Deliberately not implemented in WP-03B/WP-03C.

Move perpendicular to the selection normal (i.e., within the tangent plane):

```python
space="tangent"  # Move in plane perpendicular to selection normal
```

The infrastructure is in place:
- Normal resolution via `selection_normal()` is available
- Tangent basis via `_face_tangent_basis()` is now available (WP-03C)
- Projection math is straightforward (delta - projection onto normal)
- Tool layer can accept the parameter

**Deferred because**:
- No clear use case yet (existing `space="normal"` covers the opposite direction)
- Semantics: does "tangent" mean any tangent direction (freiform in plane), or constrained to a specific tangent axis?
- Requires clarification of what "constrained tangent movement" means (single axis within plane? Both? Free?)

**Next step**: gather use cases during Playground experimentation; revisit after WP-04 hotkey wiring stabilizes and multi-element tangent research completes.

## Soft Selection: Radius live während des Ziehens ändern (Idee, Manu S2c 2026-10-11)

**Status**: Bewusst nicht umgesetzt. Im S2c-Verdikt (AD-020, „S2c verdict“) steht der Radius-Schritt per Shift+Mausrad auf
KEEP („passt erstmal“); den Radius **während** einer laufenden Geste zu ändern bleibt eine Idee für später.

Heute gilt: der Radius ist pro Geste fest — `SoftSettings` wird bei `begin()` gelesen, ein Wechsel mitten in der Geste
gilt ab der nächsten (AD-020 §4.3). Live-Änderung hieße, die Gewichte aus dem Start-Snapshot der Geste neu auszuwerten,
solange die Maus gezogen wird (Kosten pro Wheel-Schritt: neue Influence-Berechnung plus neue Bänder, vgl.
`experiments/drag_cost/README.md`).

**Next step**: erst nach weiteren Soft-Selection-Tests (auch mit höher aufgelösten Meshes) neu bewerten; Voraussetzung für
eine Entscheidung ist ein konkreter Fall, in dem der feste Radius pro Geste stört.
