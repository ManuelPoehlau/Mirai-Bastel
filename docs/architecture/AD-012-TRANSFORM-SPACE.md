# AD-012: Transform Space Unification

**Status:** Accepted — amended 2026-09-19 (see Amendment below)  
**Date:** 2026-09-19  
**Decision:** Unify Move/Rotate/Scale tools with a shared `space` parameter, replacing tool-specific `axis=`/`axes=` names and generalizing axis-masking math into vector projection.

## Problem

Move, Rotate, and Scale tools each had inconsistent APIs for constraining transformations:

- **RotateTool**: `axis="x"` (single-axis), `axis="xy"` (plane→perpendicular axis), `axis="normal"` (derived from selection)
- **MoveTool**: `axis="x"`, `axis="xy"` (plane mask) — no normal support
- **ScaleTool**: `axes="x"` (note: different parameter name), `axes="xy"` (plane mask) — no normal support

This fragmentation meant:
1. **Tool-specific learning curve**: developers had to remember `axis=` vs `axes=`
2. **Incomplete semantics**: Move and Scale couldn't access normal-constrained transformations
3. **No unified projection mechanism**: each tool reimplemented constraint logic locally
4. **Missing integration point**: Gate-4 hotkey wiring needed a stable, unified API before it could wire all three tools consistently

## Goals

1. **Unified API**: all three tools accept the same `space` parameter vocabulary
2. **One projection mechanism**: shared `_resolve_space()` handles all constraint types
3. **Normal support**: all three tools can transform along surface normals
4. **Backward compatibility**: old parameter names (`axis=`, `axes=`) still work
5. **No core changes**: tool layer only — `VertexTransformOperation` and friends stay frozen (per AD-003)

## Constraints

- **Core operations unchanged** (per AD-003): The tool layer translates `space` into operation deltas; core Rotate/Move/Scale operations are unchanged.
- **World-space behavior identical** (regression safety): Existing constraints ("x", "y", "z", "xy", "yz", "xz") must produce bit-identical output before and after refactoring.
- **Local/Gimbal space deferred** (ARCH-01 dependent): `space="local"` and gimbal rotation are out of scope; only world and normal are implemented.
- **Screen-space constraints deferred**: `space="screen"` with axis constraints (e.g., "x" on screen) is future work (requires camera basis integration at tool level).

## Solution: The `space` Parameter

All three tools now accept:

```python
def _on_begin(self, ..., space=None, derived_geometry=None, ...):
```

Where `space` is one of:

| Value | Semantics | Rotate | Move | Scale |
|-------|-----------|--------|------|-------|
| `None` | Unconstrained (default) | Camera forward (screen plane) | Screen plane | Uniform |
| `"x"` / `"y"` / `"z"` | Single world axis | Rotate around axis | Move along axis | Scale along axis |
| `"xy"` / `"yz"` / `"xz"` | Plane constraint | Rotate around perpendicular axis | Move in plane (other axis locked) | Scale in plane |
| `"normal"` | Selection-derived direction | Rotate around normal | Move along normal | Scale along normal |

### Implementation Architecture

**Transform.py** — Generalized space resolution:

```python
def _resolve_space(space: str | None, derived_geometry, mesh, selection, for_rotation=False) -> VEC3:
    """Resolve space specifier to a direction vector."""
    # Single axes ("x"/"y"/"z") → direct lookup from _WORLD_AXES
    # Planes ("xy"/"yz"/"xz") → mask for Move/Scale, perpendicular axis for Rotate (for_rotation=True)
    # "normal" → derived via selection_normal() with validation
```

**Move/Rotate/Scale tools** — Constrained interaction:

- **MoveTool**: applies component-wise masking, or projects delta onto normal for `space="normal"`
- **RotateTool**: stores resolved axis, rotates around it
- **ScaleTool**: applies per-axis scale factors, or interpolates based on normal components for `space="normal"`

### Key Design Decisions

#### 1. **Planes Are Interpreted Differently for Rotate vs Move/Scale**

- **Move/Scale**: `space="xy"` is a mask `(1, 1, 0)` — both X and Y are free, Z is locked.
- **Rotate**: `space="xy"` means "rotate in the XY plane" = "rotate around the Z axis" (perpendicular to the plane).

This is handled by the `for_rotation` parameter in `_resolve_space()`:

```python
if for_rotation:
    return _PLANE_ROTATION_AXES[key]  # e.g., "xy" → (0, 0, 1)
else:
    return plane_component(key)  # e.g., "xy" → (1, 1, 0)
```

#### 2. **Normal Projection, Not Masking**

For `space="normal"`, Move and Scale use **vector projection**, not component-wise masking:

- **Move**: projects world delta onto normal direction via dot product: `(delta · normal) * normal`
- **Scale**: interpolates per-axis scale by normal component magnitude: `factor = 1 + (s-1) * |normal_i|`

This is necessary because normals are rarely axis-aligned; component masking would lose the direction information.

#### 3. **Backward Compatibility**

Both old and new parameter names are accepted; `space` takes priority:

```python
def _on_begin(self, ..., space=None, axis=None, axes=None, ...):
    if space is None and axis is not None:
        space = axis
    if space is None and axes is not None:
        space = axes
```

Existing code using `RotateTool(axis="normal")` or `MoveTool(axis="x")` continues to work unchanged.

## Implementation Details

### Files Modified

| File | Changes |
|------|---------|
| `src/mirai/interaction/tools/transform.py` | Added `axis_component()`, `plane_component()`, `_resolve_space()` |
| `src/mirai/interaction/tools/rotate.py` | Refactored to use `_resolve_space(for_rotation=True)`; kept `_resolve_axis()` wrapper for backward compat |
| `src/mirai/interaction/tools/move.py` | Added `space=` parameter, `_normal` field for projection |
| `src/mirai/interaction/tools/scale.py` | Renamed `axes=` → `space=`, added `_normal` field |

### Tests Added

**tests/test_space_parameter_regression.py** (15 tests):
- Backward compatibility: old parameter names still work
- New parameter: `space=` accepted for all tools
- Normal resolution: `space="normal"` works with face/vertex selection, raises if `derived_geometry` missing

All existing tests pass:
- 19 core transform operation tests
- 2 rotate normal axis integration tests
- 68 tool integration tests
- 15 new regression tests
- **Total: 103 passing**

## Constraints Honored

✅ **World-space regression**: existing "x", "y", "z", "xy", "yz", "xz" constraints produce bit-identical output  
✅ **No core changes**: `VertexTransformOperation` and subclasses unchanged  
✅ **Backward compatible**: old `axis=`/`axes=` still work  
✅ **Normal validation**: zero normals raise clear errors  

## Out of Scope (Future Work)

### ARCH-01: Local and Gimbal Space

Once ARCH-01 is finalized (coordinate system design):

```python
space="local"      # Transform in object-local space
space="gimbal"     # Gimbal rotation (Euler ZYX)
space="local_xy"   # Local plane (local X and Y axes)
```

This requires:
- Mesh-space basis extraction (object transform matrix)
- Gimbal ordering specification
- Screen-space projection in local coordinates

### Screen-Space Axis Constraints

```python
space="screen_x"   # Move/scale along screen X (camera right)
space="screen_y"   # Move/scale along screen Y (camera up)
space="screen_xy"  # Move/scale in screen plane
```

Currently `space=None` defaults to screen plane for Move (via `camera.screen_delta_to_world()`); explicit screen axis naming is deferred.

### Tangent-Plane Movement

Move along the plane *perpendicular* to the normal (not the normal itself):

```python
space="tangent"    # Move in plane perpendicular to selection normal
```

The infrastructure is in place (normal is available), but this is intentionally deferred pending clarification of Use Cases.

## Gate-4 Integration (WP-04)

The unified `space` API is now available for WP-04 hotkey wiring:

```python
# WP-04 can now wire keys uniformly:
"M+X"  → MOVE with space="x"
"M+Y"  → MOVE with space="y"
"R+N"  → ROTATE with space="normal"
"S+XY" → SCALE with space="xy"
```

Each tool recognizes the same vocabulary; no tool-specific wiring logic needed.

## Design Rationale

### Why Vector Projection for Normal?

Component-wise masking cannot represent arbitrary directions. For a normal at (0.7, 0.7, 0), masking via (1, 1, 0) would allow movement in X *and* Y independently, not along the diagonal. Vector projection ensures movement is constrained to exactly one direction.

### Why `for_rotation` Parameter?

Planes have two interpretations:
- **In Move/Scale context**: "a 2D region of freedom" → use as mask
- **In Rotate context**: "the plane in which rotation occurs" → use perpendicular axis

Rather than duplicate `_resolve_space()`, the `for_rotation` flag cleanly handles both.

### Why Keep _resolve_axis() Wrapper?

Existing experiment code (e.g., `tests/test_selection_normals.py`) imports `_resolve_axis()`. Rather than force all experiments to update, we keep it as a thin wrapper that delegates to `_resolve_space()`. This maintains compatibility without repeating logic.

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Numerical divergence in world-space | Regression tests verify bit-identical output for existing constraints |
| Normal resolution crashes on degenerate selection | `selection_normal()` validates non-zero, caller raises clear error |
| Tools accept both old and new parameters (confusion) | Parameter naming is consistent; old names are truly deprecated, not parallel |
| Missed normal constraint edge cases | Unit tests cover face/vertex/edge selection modes and zero-normal handling |

## References

- **AD-003**: Incremental update contract (Core operations unchanged)
- **AD-009**: Axis and plane constraints (the vocabulary this decision codifies)
- **ARCH-01**: Local and gimbal space (future extension point)
- **WP-03B**: Transform Space Unification (initial implementation)
- **WP-03C**: Normal Space Tangent Basis + space/axis Split (amendment implementation)
- **WP-04**: Gate-4 Hotkey Wiring (consumer of this API)

## Decision

✅ Implement unified `space` parameter across Move/Rotate/Scale tools.  
✅ Move shared resolution logic to `transform.py`.  
✅ Support normal-constrained transformations for all three tools.  
✅ Maintain backward compatibility with old parameter names.  
✅ Defer local/gimbal/screen-space to ARCH-01 and future work.

## Amendment (2026-09-19, same-day correction)

**Status:** Accepted — corrects the original `space="normal"` design before broader
adoption (Gate-4 hotkey wiring, Playground) builds on it.

### What was wrong

The original decision (above) treats `space="normal"` as a single direction vector,
identical in kind to a single world axis. Verified against `main` (commits `82372f7`,
`a83347a`): `_resolve_space()` returns one `Position` for `"normal"`, used unmodified
by all three tools.

This is insufficient for anisotropic Scale on a face not aligned to world axes: a
rectangular face scaled along a single normal-perpendicular direction shears unless
the *second* in-plane direction is also defined and orthogonal to the first. A single
vector cannot express this — a full basis is required.

Separately, and independently of the above: `space` was implemented as one flat
string parameter conflating **coordinate system** (world / normal) with **axis
selection within that system** (`"x"`, `"xy"`, ...). This was not the two-level
design the original request specified (space chosen first, axis constrained within
it, as in Blender/Max) — it happened to still work while Normal had only one
possible axis. It stops working now that Normal needs `x`/`y`/`z` sub-selection.

### What changes

1. **`space` and `axis` become two orthogonal parameters** on all three tools'
   `begin()`: `space: "world" | "normal"` (`"screen"` unchanged, still axis-less
   per the original deferral), `axis: "x" | "y" | "z" | "xy" | "yz" | "xz" | None`.
2. **Old flat strings remain valid as aliases**, resolved to the new two-parameter
   form internally: `space="x"` → `space="world", axis="x"`; `space="normal"`
   (no axis) → `space="normal", axis="z"`. No caller, test, or Playground wiring
   needs to change.
3. **`space="normal"` now resolves a basis, not a vector**, for a single selected
   face (`SelectionMode.FACE`, exactly one face in `selection.faces`):
   - `axis="z"` / `None` → the face normal (today's behavior, unchanged output).
   - `axis="x"` → tangent 1, derived from the face's first edge
     (`mesh.face_vertices(face_id)[1] - mesh.face_vertices(face_id)[0]`,
     projected onto the plane perpendicular to the normal, then normalized).
     Deterministic: winding order fixes which edge is "first", not an artist choice.
   - `axis="y"` → tangent 2 = `cross(normal, tangent_x)`.
   - `axis="xy"` / `"yz"` / `"xz"` → same plane-mask convention as World, expressed
     in this local basis instead of world axes.
4. **Multi-element selections (multiple faces, or vertex/edge mode) get no tangent
   basis.** `axis="x"`/`"y"` raises `ValueError` in this case; `axis="z"`/`None`
   continues to work exactly as today (falls back to `selection_normal()`'s
   existing averaging behavior — no regression). Deriving a stable tangent for
   multi-element selections is deferred to Artist Playground research — see
   `docs/future_ideas/TRANSFORM.md`; even Blender's own multi-element Normal
   orientation is a long-standing, unresolved UX complaint (not a solved reference
   to copy from).

### Not changed

- `space="screen"` — still axis-less, per the original deferral.
- `space="local"` / gimbal — still ARCH-01-blocked, unrelated to this amendment.
- Core (`VertexTransformOperation` and subclasses) — untouched, per AD-003.
