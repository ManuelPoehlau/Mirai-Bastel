"""Support declarations for symmetric topology operations (AD-SYM-03 §2.5, D-b).

A declaration says "a coordinator exists for this resolved operation": one static table per
kind of key, in the module that will hold the coordinators, so the entry *is* the implementation
and cannot drift from it. Two keys exist today:

- the `C` operation contexts (`CContext`: Split, Edge Connect, Vertex Connect, Knife);
- the removal commands (`Delete`, `Dissolve`, `DissolveNoCleanup`).

Transforms keep `Operation.supports_symmetry`; there the Operation itself mirrors.

AD-SYM-03 slice 3a: both tables are empty, no coordinator exists yet (slice 3b adds the first
ones). Readers are the Symmetry Lab, which derives its gate row and MARK warning from them
(AD-013 H2 amendment of 2026-10-08, H2-R4 (h)), and later `Application`, which dispatches
coordinated operations. Nobody installs anything at runtime and the tables hold no gate data
(H2-R6): this module imports nothing but the `CContext` enum, so it carries no gate or mesh
dependency. It lives apart from `symmetry_coordination` because that module depends only on
`core` and `mirai.symmetry`, and a table keyed by `CContext` would pull `mirai.topology` in.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from .topology.contextual_c import CContext

#: Resolved `C` context -> coordinator. Empty until slice 3b.
C_CONTEXT_COORDINATORS: Mapping[CContext, Any] = MappingProxyType({})

#: Removal command constant (`mirai.interaction.commands`) -> coordinator. Empty until slice 3b.
#: Keyed per command, not per component mode (AD-013 H2 amendment, "Removal"): a mode-keyed
#: declaration would need a mode-keyed gate refusal, which is not decided (G-9).
REMOVAL_COORDINATORS: Mapping[str, Any] = MappingProxyType({})


def declared_c_contexts() -> frozenset[CContext]:
    """The `C` contexts that have a coordinator (read on every call, never cached)."""
    return frozenset(C_CONTEXT_COORDINATORS)


def declared_removal_commands() -> frozenset[str]:
    """The removal commands that have a coordinator (read on every call, never cached)."""
    return frozenset(REMOVAL_COORDINATORS)
