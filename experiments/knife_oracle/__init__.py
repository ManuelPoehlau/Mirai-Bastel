"""Knife oracle: the frozen Knife Face Lab engines (B, D, Q5) and the golden / differential tests that hold the
Production Knife (`src/mirai/topology/knife*.py`) and `Mesh.split_face` against them.

Moved out of `playground/` on 2026-10-21 ("Knife ist kein Playground-Thema mehr", Manu): the Knife is in Production, so
the Playground no longer hosts it; what stays is the reference side of the equivalence tests. Frozen on purpose -
change an engine only to keep it running, never to follow Production (that would blind the comparison).
The decision record is `docs/research/topology/KNIFE_FACE_DECISIONS.md`.
"""
