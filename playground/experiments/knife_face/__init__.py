"""Knife Face Cut Lab — interaction variants for cutting into faces.

See docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md,
docs/research/topology/KNIFE_CROSS_FACE_DISCOVERY.md and the decision record
docs/research/topology/KNIFE_FACE_DECISIONS.md (moved there 2026-10-21; code comments saying "decision.md" mean it). Family "knife_face": Tab to focus, M cycles B / D / Q5.

The commit-time resolver of D and Q5 lives in `src/mirai/topology/knife_resolve.py`
(WP-KNIFE-01 S1); this package keeps the click-time Lab sessions, picking and the planner.
"""

from playground.experiments.knife_face.variant_b import KnifeFaceVariantB
from playground.experiments.knife_face.variant_d import KnifeFaceVariantD
from playground.experiments.knife_face.variant_q5 import KnifeFaceVariantQ5

__all__ = ["KnifeFaceVariantB", "KnifeFaceVariantD", "KnifeFaceVariantQ5"]
