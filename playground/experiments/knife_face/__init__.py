"""Knife Face Cut Lab — two interaction variants for cutting into faces.

See docs/research/topology/KNIFE_FACE_CUT_DISCOVERY.md and this package's
decision.md. Family "knife_face": Tab to focus, M cycles B / D.
"""

from playground.experiments.knife_face.variant_b import KnifeFaceVariantB
from playground.experiments.knife_face.variant_d import KnifeFaceVariantD

__all__ = ["KnifeFaceVariantB", "KnifeFaceVariantD"]
