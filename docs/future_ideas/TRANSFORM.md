# Future Ideas – Transform

Ideen und Beobachtungen rund um Transform, die bewusst noch nicht umgesetzt werden.

> Im Hinterkopf behalten und später erneut bewerten.

## Tangent-Plane Movement (Deferred per AD-012)

**Status**: Deliberately not implemented in WP-03B.

Move perpendicular to the selection normal (i.e., within the tangent plane):

```python
space="tangent"  # Move in plane perpendicular to selection normal
```

The infrastructure is in place:
- Normal resolution via `selection_normal()` is available
- Projection math is straightforward (delta - projection onto normal)
- Tool layer can accept the parameter

**Deferred because**:
- No clear use case yet (existing `space="normal"` covers the opposite direction)
- Semantics: does "tangent" mean any tangent direction (freiform in plane), or constrained to a specific tangent axis?
- Requires clarification of what "constrained tangent movement" means (single axis within plane? Both? Free?)

**Next step**: gather use cases during Playground experimentation; revisit after WP-04 hotkey wiring stabilizes.
