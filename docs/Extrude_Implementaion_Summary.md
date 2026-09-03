All 153 tests pass (19 new + 134 existing), no regressions. The implementation is complete.

## Summary

### Files Changed

| File | Change |
|------|--------|
| `viewport/commands.py` | Added `EXTRUDE = "Extrude"` command constant |
| `viewport/extrude_tool.py` | **NEW** — `ExtrudeTool` class (211 lines) |
| `viewport/default_bindings.py` | Added `Alt+E` binding in topology context |
| `viewport/topology_app.py` | Added EXTRUDE command handling with selection management |
| `tests/test_extrude_tool.py` | **NEW** — 19 tests |

### Architecture

**`ExtrudeTool`** follows the existing `Tool` lifecycle exactly:

```
activate() → ACTIVE
begin(face_id) → INTERACTING  (topology built, snapshot taken)
update(dx,dy,width,height)* → INTERACTING  (vertex positions updated live)
commit() → ACTIVE  (single history entry, returns new FaceId)
cancel() → ACTIVE  (mesh restored from snapshot)
```

**Topology** (in `_on_begin`):
1. Validates the face
2. Takes a mesh snapshot for cancel
3. Computes face normal via **Newell's method** (works for arbitrary polygons)
4. Creates new vertices at original positions (distance=0)
5. Creates side-faces: `[v_curr, v_next, v_next_new, v_curr_new]`
6. Creates result-face from new vertices (same winding as original)

**Mouse mapping** (in `_on_update`):
- Uses `camera.screen_delta_to_world()` with the original face center as anchor
- Projects world delta onto face normal → incremental distance
- Updates new vertex positions: `original + normal * total_distance`

**Commit**: Uses `_SnapshotCommand` (same pattern as Connect Edges) — single history entry with before/after mesh state.

**Cancel**: `mesh.load_state()` restores the snapshot taken before any mutation.

**Selection after commit**: `topology_app.py` selects only the new result face.

### Tests (19 total)

| Category | Tests |
|----------|-------|
| Topology | new vertices created, side faces created, result face exists, original face preserved, vertices on boundary |
| Geometry | normal points along Z, distance accumulates |
| Selection | new face selected after commit, commit returns new face ID |
| History | single entry on commit, undo removes extrusion, redo restores it |
| Cancel | restores original state, no history entry, clears tool state |
| Validation | invalid face raises, begin without activate raises |
| Newell normal | correct direction for XY quad, normalized |

### Known Limitations

- Allocator counters not restored on cancel (by design in `IdAllocator.restore_counter` — only moves forward)
- No numeric input, no gizmo, no multi-face extrusion (as specified)