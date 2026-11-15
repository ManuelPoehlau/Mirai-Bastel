"""Surface Slide, the pure core (Phase 1 of the Production Readiness Audit 2026-11-14, §13).

Vertices slide across a fixed copy of the surface (`SlideReference`), each anchored where it is and moved along
straightest geodesics, with a speed limit (`SurfaceSlide`, `geodesic_pursuit[transport]`). Research:
`docs/research/SURFACE_SLIDE_ALGORITHM_RESEARCH_2026-11-13.md`; decisions and specs:
`docs/research/SURFACE_SLIDE_PRODUCTION_READINESS_AUDIT_2026-11-14.md` §5.1, §13. Reference implementation:
`experiments/surface_slide/` (compared by the oracle `experiments/surface_slide/tests/test_production_oracle.py`, G1).

The core (`reference`, `tracer`, `curves`, `slide`) is pure: index arrays in, positions out; no `core.Mesh`, no camera,
no GUI, no input types; NumPy only through `viewport.packed_geometry` (AD-032). Phase 2 (§13.2) adds the mesh side,
which reads a `core.Mesh` through its query API and never writes it: `capture` (the drawn triangles of the driven
half, region-limited, `MeshHalf`, `SlideCapture`) and `plan` (`plan_surface_slide` -> `SlidePlan`: weights, the
symmetry driver rule, refusals; `SlideSession`: region growth with replay, the positions to write including the exact
mirrors). The gesture, the cursor mapping and the binding are Phase 3 (E6).

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
   the journal writes and the history entry (`controllers/gestures.py`, AD-027, Phase 3). The mirrored writes of the
   passive half are `SlideSession`'s (`SlideStep.positions`); the core slides the driven half only.
8. (Phase 2) Under symmetry only the pivot's half and the seam are driven (B3); the reference is the drawn triangles
   of that half (B1), the seam and every polygon that may not be captured (passive, hidden, straddling) are barriers,
   and a region capture gives the same positions as the full capture, bit for bit (B2, gate G2).
"""

from .capture import MeshHalf, SlideCapture
from .curves import EdgeChain
from .plan import (CAPTURE_MARGIN, SURFACE_SLIDE_LABEL, SlidePlan, SlideSession, SlideStep, SurfaceSlideRefused,
                   plan_surface_slide)
from .reference import BARRIER_EDGE, BOUNDARY_EDGE, CAPTURE_EDGE, SlideReference
from .slide import SlideFrame, SurfaceSlide, direct_frames, frame_jumps, minimal_rotations, tree_frames
from .tracer import (BARRIER_MAX_AMOUNT, FLAG_BARRIER, FLAG_BLOCKED, FLAG_BOUNDARY, FLAG_CAPTURE, FLAG_CHAIN_END,
                     FLAG_LAGGING, FLAG_MAXITER, FLAG_STUCK, WALL_FLAGS, Trace, back_off, trace)

__all__ = [
    "CAPTURE_MARGIN", "MeshHalf", "SURFACE_SLIDE_LABEL", "SlideCapture", "SlidePlan", "SlideSession", "SlideStep",
    "SurfaceSlideRefused", "plan_surface_slide",
    "BARRIER_EDGE", "BARRIER_MAX_AMOUNT", "BOUNDARY_EDGE", "CAPTURE_EDGE", "EdgeChain", "FLAG_BARRIER", "FLAG_BLOCKED",
    "FLAG_BOUNDARY", "FLAG_CAPTURE", "FLAG_CHAIN_END", "FLAG_LAGGING", "FLAG_MAXITER", "FLAG_STUCK", "SlideFrame",
    "SlideReference", "SurfaceSlide", "Trace", "WALL_FLAGS", "back_off", "direct_frames", "frame_jumps",
    "minimal_rotations", "trace", "tree_frames",
]
