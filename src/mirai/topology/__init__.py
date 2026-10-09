"""Contextual C topology capability (AD-017, WP-06 Slice B6): Split / Edge
Connect / Vertex Connect, promoted from the Playground Topology Lab.

Playground (`playground/topology_tools/`) imports from here so there is one
implementation shared between the Artist research host and Production.
WP-06 Slice B7 added the Knife session engine (`knife.py`, `knife_pick.py`,
moved from the Playground; `knife_preview.py`, new render data).
WP-KNIFE-01 S1 (One Knife, AD-017 addendum 2026-10-01) moved the Knife Face
Lab's commit-time resolver here (`knife_resolve.py`, Knife-owned; faces only
through `Mesh.split_face`) with the face geometry it shares with F2's
`chord_validity` (`face_geometry.py`); the Production `KnifeTool` does not use
it yet (slice S2).
WP-06 Slice B9 moved the Multi-Face-Extrude tool here (`extrude.py`, hold `T`,
PROVISIONAL); the Playground shares it.
Not moved here: the rejected strip-semantics Connect (`connect_edges.py`),
the loop tools, articulation.
"""

from __future__ import annotations
