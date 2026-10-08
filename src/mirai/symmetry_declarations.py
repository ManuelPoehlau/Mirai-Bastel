"""Support declarations for symmetric topology operations (AD-SYM-03 §2.5, D-b).

A declaration says "a coordinator exists for this resolved operation": one static table per
kind of key, in the module that will hold the coordinators, so the entry *is* the implementation
and cannot drift from it. Two keys exist today:

- the `C` operation contexts (`CContext`: Split, Edge Connect, Vertex Connect, Knife);
- the removal commands (`Delete`, `Dissolve`, `DissolveNoCleanup`).

Transforms keep `Operation.supports_symmetry`; there the Operation itself mirrors.

AD-SYM-03 slice 3b: the `C` table holds the first coordinators (Edge Connect, Vertex Connect,
`mirai.symmetric_ops`); the removal table is still empty (slice 3c). Readers are the Symmetry
Lab, which derives its gate row and MARK warning from the keys (AD-013 H2 amendment of
2026-10-08, H2-R4 (h)), and `Application`, which runs the coordinator of a declared context
whenever a symmetry definition is set. Nobody installs anything at runtime and the tables hold
no gate data (H2-R6). The module imports the coordinators, so it depends on `mirai.symmetric_ops`
(and through it on `mirai.topology`), never on `application`. It lives apart from
`symmetry_coordination` because that module depends only on `core` and `mirai.symmetry`.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from .symmetric_ops import coordinate_edge_connect, coordinate_vertex_connect
from .topology.contextual_c import CContext

#: Resolved `C` context -> coordinator `(mesh, canonical selection ids) -> result`. Split and
#: Knife are undeclared (slices 4 and 6).
C_CONTEXT_COORDINATORS: Mapping[CContext, Any] = MappingProxyType(
    {
        CContext.EDGE_CONNECT: coordinate_edge_connect,
        CContext.VERTEX_CONNECT: coordinate_vertex_connect,
    }
)

#: Removal command constant (`mirai.interaction.commands`) -> coordinator. Empty until slice 3c.
#: Keyed per command, not per component mode (AD-013 H2 amendment, "Removal"): a mode-keyed
#: declaration would need a mode-keyed gate refusal, which is not decided (G-9).
REMOVAL_COORDINATORS: Mapping[str, Any] = MappingProxyType({})


def declared_c_contexts() -> frozenset[CContext]:
    """The `C` contexts that have a coordinator (read on every call, never cached)."""
    return frozenset(C_CONTEXT_COORDINATORS)


def declared_removal_commands() -> frozenset[str]:
    """The removal commands that have a coordinator (read on every call, never cached)."""
    return frozenset(REMOVAL_COORDINATORS)
