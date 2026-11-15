"""Surface Slide, the pure core (Phase 1 of the Production Readiness Audit 2026-11-14, §13).

Vertices slide across a fixed copy of the surface (`SlideReference`), each anchored where it is and moved along
straightest geodesics, with a speed limit (`SurfaceSlide`, `geodesic_pursuit[transport]`). Research:
`docs/research/SURFACE_SLIDE_ALGORITHM_RESEARCH_2026-11-13.md`; decisions and specs:
`docs/research/SURFACE_SLIDE_PRODUCTION_READINESS_AUDIT_2026-11-14.md` §5.1, §13. Reference implementation:
`experiments/surface_slide/` (compared by the oracle `experiments/surface_slide/tests/test_production_oracle.py`, G1).

Pure: index arrays in, positions out. No `core.Mesh`, no camera, no GUI, no input types; NumPy only through
`viewport.packed_geometry` (AD-032). Planning from a mesh, region capture and the symmetry driver rule are Phase 2;
the gesture, the cursor mapping and the binding Phase 3 (E6).

**Contract** (report §14.4 as amended by the audit):

1. `SurfaceSlide.update(delta)` depends on `delta` and on earlier calls only through the speed limit; a drag whose
   tangent is exactly zero returns the start positions bit for bit and clears all state.
2. Every returned position is `reference.point(anchor)` for an anchor on the reference: no position is produced by
   projection, and a vertex changes triangle only by crossing an edge (no region jumps).
3. A row moves at most `(1 + gain) x |change of its own tangent|` per `update` (flat evaluation).
4. Rows of weight 0 never move.
5. A trace stops at boundary, barrier and capture edges and says which (`FLAG_BOUNDARY`, `FLAG_BARRIER`,
   `FLAG_CAPTURE`); a barrier stop lies strictly off the barrier edge (`tracer.back_off`, E3). Rows on an `EdgeChain`
   (declared seam, open boundary, E5) stay on the chain; a seam row's plane coordinate stays exactly on the plane
   when the chain's vertices have it exactly.
6. Per-row flags `BOUNDARY | BARRIER | CAPTURE | BLOCKED | STUCK | MAXITER | CHAIN_END | LAGGING`; never a fallback
   to a global projection.
7. The reference is never modified (read-only arrays). Nothing here reads a camera or a pointer: the gesture maps
   the pointer to a world vector in the pivot's start tangent plane (M1, E4) and owns press / drag / release / Esc,
   the journal writes and the history entry (`controllers/gestures.py`, AD-027, Phase 3). Mirrored writes of the
   passive half are the planner's / gesture's (Phase 2), not this package's.
"""

from .curves import EdgeChain
from .reference import BARRIER_EDGE, BOUNDARY_EDGE, CAPTURE_EDGE, SlideReference
from .slide import SlideFrame, SurfaceSlide, direct_frames, frame_jumps, minimal_rotations, tree_frames
from .tracer import (BARRIER_MAX_AMOUNT, FLAG_BARRIER, FLAG_BLOCKED, FLAG_BOUNDARY, FLAG_CAPTURE, FLAG_CHAIN_END,
                     FLAG_LAGGING, FLAG_MAXITER, FLAG_STUCK, WALL_FLAGS, Trace, back_off, trace)

__all__ = [
    "BARRIER_EDGE", "BARRIER_MAX_AMOUNT", "BOUNDARY_EDGE", "CAPTURE_EDGE", "EdgeChain", "FLAG_BARRIER", "FLAG_BLOCKED",
    "FLAG_BOUNDARY", "FLAG_CAPTURE", "FLAG_CHAIN_END", "FLAG_LAGGING", "FLAG_MAXITER", "FLAG_STUCK", "SlideFrame",
    "SlideReference", "SurfaceSlide", "Trace", "WALL_FLAGS", "back_off", "direct_frames", "frame_jumps",
    "minimal_rotations", "trace", "tree_frames",
]
