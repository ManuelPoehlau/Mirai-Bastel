"""Contextual C topology capability (AD-017, WP-06 Slice B6): Split / Edge
Connect / Vertex Connect, promoted from the Playground Topology Lab.

Playground (`playground/topology_tools/`) imports from here so there is one
implementation shared between the Artist research host and Production.
WP-06 Slice B7 added the Knife session engine (`knife.py`, `knife_pick.py`,
moved from the Playground; `knife_preview.py`, new render data).
Not moved here: the rejected strip-semantics Connect (`connect_edges.py`),
loop/extrude tools, articulation.
"""

from __future__ import annotations
